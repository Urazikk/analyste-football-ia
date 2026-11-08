"""Niveau 1 : RAG (découpage, embeddings, recherche dense ou hybride, citations, abstention).

Choix mesurés par scripts/bench_retrieval.py (results/retrieval.md) : multilingual-e5-small,
morceaux de 600 caractères, recherche dense seule. L'abstention est laissée au modèle (marqueur),
le seuil sur le score dense ne séparant pas les cas absents des cas doc.

Identifiants : « <doc>#<section> » puis « /<k> » si la section est coupée en plusieurs morceaux,
par exemple « ifab-loi-11#1-position-de-hors-jeu/2 ». Les cas de test citent le document ou la
section (« ifab-loi-11 », « ifab-loi-11#1-position-de-hors-jeu ») : un morceau est pertinent si
son identifiant commence par l'un d'eux. Les tests ne dépendent donc pas de la taille des morceaux.

Lister les identifiants pour écrire tests.jsonl : python -m src.rag --list
"""
from __future__ import annotations

import argparse
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from src import config
from src.config import CORPUS_DIR, EMBEDDING_MODEL, INDEX_DIR
from src.result import Result
from src.tracing import Tracer

MAX_CHARS = 600  # taille d'un morceau, mesurée (docs/decisions.md, results/retrieval.md)
SEARCH_MODE = "dense"  # dense, bm25 ou hybrid : l'hybride n'améliore ni Recall@5 ni MRR (results/retrieval.md)


@dataclass
class Chunk:
    id: str        # identifiant cité dans la réponse
    doc_id: str
    title: str     # « titre du document > section »
    source: str    # URL ou référence d'origine
    text: str


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def parse_document(raw: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """En-tête de métadonnées et sections « ## » d'un document du corpus."""
    _, head, body = raw.split("---", 2)
    meta = dict(re.findall(r"^(\w+): (.*)$", head, re.M))
    sections = []
    for block in re.split(r"(?m)^## ", body)[1:]:
        title, _, text = block.partition("\n")
        sections.append((title.strip(), text.strip()))
    return meta, sections


def _hard_split(text: str, max_chars: int) -> list[str]:
    """Coupe un bloc sans ponctuation (liste à puces) par lignes, puis par mots."""
    out, buf = [], ""
    for word in re.split(r"(?<=\n)|(?<= )", text):
        if buf and len(buf) + len(word) > max_chars:
            out.append(buf.strip())
            buf = ""
        buf += word
    return out + [buf.strip()] if buf.strip() else out


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Regroupe les paragraphes jusqu'à max_chars ; coupe par phrases un paragraphe trop long."""
    parts: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if len(para) <= max_chars:
            parts.append(para)
        else:
            for sent in re.split(r"(?<=[.!?;])\s+", para):
                parts += _hard_split(sent, max_chars) if len(sent) > max_chars else [sent]
    chunks, buf = [], ""
    for part in filter(None, parts):
        if buf and len(buf) + len(part) + 2 > max_chars:
            chunks.append(buf)
            buf = part
        else:
            buf = f"{buf}\n\n{part}" if buf else part
    if buf:
        chunks.append(buf)
    return chunks


def chunk_document(raw: str, max_chars: int = MAX_CHARS) -> list[Chunk]:
    meta, sections = parse_document(raw)
    chunks: list[Chunk] = []
    seen: dict[str, int] = {}
    for title, text in sections:
        slug = slugify(title) or "section"
        seen[slug] = seen.get(slug, 0) + 1
        if seen[slug] > 1:
            slug = f"{slug}-{seen[slug]}"
        pieces = split_text(text, max_chars)
        for k, piece in enumerate(pieces, start=1):
            cid = f"{meta['id']}#{slug}" + (f"/{k}" if len(pieces) > 1 else "")
            chunks.append(Chunk(cid, meta["id"], f"{meta['title']} > {title}", meta.get("source", ""), piece))
    return chunks


def load_corpus(corpus_dir: Path = CORPUS_DIR, max_chars: int = MAX_CHARS) -> list[Chunk]:
    """Lit tous les documents de data/corpus/ (wiki/, ifab/) et les découpe."""
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*/*.md")):
        chunks += chunk_document(path.read_text(encoding="utf-8"), max_chars)
    return chunks


# Index et recherche -----------------------------------------------------------------

STOPWORDS = set("""a au aux avec ce ces dans de des du elle en est et il ils la le les leur lui
ma mais me meme mes ne nos notre nous on ou par pas pour qu que qui sa se ses son sur ta te
tes ton tu un une vos votre vous y d l s n c j m t quel quelle quels quelles est-ce
etre doit doivent peut peuvent fait faire si lors""".split())
RRF_K = 60  # constante usuelle de la fusion par rangs (Cormack et al., 2009), non réglée


def tokenize(text: str) -> list[str]:
    """Mots sans accents ni mots vides, pluriel simple retiré (pour BM25)."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+(?:[,.][0-9]+)?", text)
    return [w[:-1] if len(w) > 3 and w[-1] in "sx" else w for w in words if w not in STOPWORDS]


def _prefixes(model_name: str) -> tuple[str, str]:
    """Préfixes requête / passage attendus par le modèle (e5 en a besoin, bge-m3 non)."""
    return ("query: ", "passage: ") if "e5" in model_name.lower() else ("", "")


def passage_text(c: Chunk) -> str:
    return f"{c.title}\n{c.text}"


_models: dict[str, object] = {}


def _encoder(model_name: str):
    if model_name not in _models:
        from sentence_transformers import SentenceTransformer

        _models[model_name] = SentenceTransformer(model_name, device="cpu")
    return _models[model_name]


class Index:
    """Morceaux, embeddings normalisés (en cache dans data/index/) et BM25."""

    def __init__(self, chunks: list[Chunk], model_name: str = EMBEDDING_MODEL, cache_dir: Path | None = INDEX_DIR):
        import hashlib

        import numpy as np
        from rank_bm25 import BM25Okapi

        self.chunks, self.model_name = chunks, model_name
        self.q_prefix, p_prefix = _prefixes(model_name)
        texts = [passage_text(c) for c in chunks]
        key = hashlib.sha256((model_name + "\0" + "\0".join(c.id + c.text for c in chunks)).encode()).hexdigest()[:16]
        path = cache_dir / f"{slugify(model_name)}-{key}.npy" if cache_dir else None
        if path and path.exists():
            self.emb = np.load(path)
        else:
            self.emb = _encoder(model_name).encode([p_prefix + t for t in texts], batch_size=16,
                                                   normalize_embeddings=True, show_progress_bar=False)
            if path:
                path.parent.mkdir(parents=True, exist_ok=True)
                np.save(path, self.emb)
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])

    def dense_scores(self, query: str):
        q = _encoder(self.model_name).encode([self.q_prefix + query], normalize_embeddings=True)[0]
        return self.emb @ q

    def search(self, query: str, k: int = 5, mode: str = "hybrid") -> list[tuple[Chunk, float]]:
        """k meilleurs morceaux. Le score renvoyé est toujours le cosinus dense (sert à l'abstention)."""
        import numpy as np

        dense = self.dense_scores(query)
        if mode == "dense":
            order = np.argsort(-dense)
        elif mode in ("bm25", "hybrid"):
            sparse = self.bm25.get_scores(tokenize(query))
            if mode == "bm25":
                order = np.argsort(-sparse)
            else:
                rrf = np.zeros(len(self.chunks))
                for scores in (dense, sparse):
                    rrf[np.argsort(-scores)] += 1.0 / (RRF_K + np.arange(1, len(self.chunks) + 1))
                order = np.argsort(-rrf)
        else:
            raise ValueError(f"mode inconnu : {mode}")
        return [(self.chunks[i], float(dense[i])) for i in order[:k]]


_index: Index | None = None


def get_index() -> Index:
    global _index
    if _index is None:
        _index = Index(load_corpus())
    return _index


def search(query: str, k: int = 5, mode: str = SEARCH_MODE) -> list[tuple[Chunk, float]]:
    """Retourne les k meilleurs morceaux avec leur score dense."""
    return get_index().search(query, k, mode)


ABSTAIN_THRESHOLD = 0.0  # désactivé : avec e5-small, les scores des cas absents recouvrent ceux des cas doc
CITE_RE = re.compile(r"\[([a-z0-9][a-z0-9#/\-]*)\]")

SYSTEM_PROMPT = f"""Tu es un analyste de football rigoureux. Tu réponds en français, brièvement,
uniquement à partir des extraits fournis.
Règles :
- Chaque affirmation cite l'identifiant de l'extrait entre crochets, par exemple [ifab-loi-11#1-position-de-hors-jeu].
- Si les extraits ne contiennent pas la réponse, réponds seulement {config.ABSTAIN_MARK} suivi d'une phrase.
- Si la demande est ambiguë, commence par {config.CLARIFY_MARK} et pose une seule question de précision.
- Si la demande sort du football, commence par {config.REFUSE_MARK} et explique brièvement.
- N'invente rien qui ne soit pas dans les extraits."""


def build_context(hits: list[tuple[Chunk, float]]) -> str:
    return "\n\n".join(f"[{c.id}] ({c.title})\n{c.text}" for c, _ in hits)


def cited_ids(text: str, allowed: list[str]) -> list[str]:
    """Identifiants cités dans la réponse, limités aux extraits fournis (sans doublon)."""
    out: list[str] = []
    for cid in CITE_RE.findall(text):
        if cid in allowed and cid not in out:
            out.append(cid)
    return out


def answer(question: str, llm=None, k: int = 5, mode: str | None = None,
           threshold: float | None = None) -> Result:
    """Niveau 1 : recherche, puis réponse qui cite ses sources ou s'abstient.

    Abstention à deux étages : par le code si le meilleur score dense est sous le seuil
    (aucun appel au LLM), sinon par le modèle avec le marqueur.
    """
    from src.llm import chat, parse_marks

    llm = llm or chat
    threshold = ABSTAIN_THRESHOLD if threshold is None else threshold
    tracer = Tracer(level=1, question=question)
    t0 = time.perf_counter()
    hits = search(question, k, mode or SEARCH_MODE)
    retrieved = [c.id for c, _ in hits]
    top = max((s for _, s in hits), default=0.0)
    tracer.log("search", mode=mode or SEARCH_MODE, k=k, retrieved=retrieved, scores=[round(s, 4) for _, s in hits],
               latency_s=round(time.perf_counter() - t0, 3))
    if not hits or top < threshold:
        res = Result(level=1, answer=f"{config.ABSTAIN_MARK} Aucun document pertinent trouvé.",
                     retrieved=retrieved, abstained=True, latency_s=time.perf_counter() - t0,
                     stop_reason="below_threshold")
        tracer.log("end", result=res.to_dict())
        return res
    resp = llm([{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Extraits :\n\n{build_context(hits)}\n\nQuestion : {question}"}])
    tracer.log("llm", tokens_in=resp.tokens_in, tokens_out=resp.tokens_out, latency_s=resp.latency_s)
    marks = parse_marks(resp.text)
    res = Result(level=1, answer=resp.text, sources=[] if marks["abstained"] else cited_ids(resp.text, retrieved),
                 retrieved=retrieved, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
                 latency_s=time.perf_counter() - t0, steps=1, **marks)
    tracer.log("end", result=res.to_dict())
    return res


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true", help="affiche les identifiants des morceaux")
    p.add_argument("--max-chars", type=int, default=MAX_CHARS)
    a = p.parse_args()
    chunks = load_corpus(max_chars=a.max_chars)
    if a.list:
        for c in chunks:
            print(f"{c.id}\t{len(c.text)}")
    sizes = [len(c.text) for c in chunks] or [0]
    print(f"{len({c.doc_id for c in chunks})} documents, {len(chunks)} morceaux, "
          f"taille moyenne {sum(sizes) / len(sizes):.0f} caractères, max {max(sizes)}")
