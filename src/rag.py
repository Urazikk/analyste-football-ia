"""Niveau 1 : RAG (découpage, embeddings, recherche dense ou hybride, citations, abstention).

Fait : lecture du corpus et découpage en morceaux à identifiants stables.
À faire (semaine 2) : index, recherche, réponse citée, abstention. Choix à mesurer :
taille des morceaux, modèle d'embeddings, dense seul ou hybride dense + BM25, seuil d'abstention.

Identifiants : « <doc>#<section> » puis « /<k> » si la section est coupée en plusieurs morceaux,
par exemple « ifab-loi-11#1-position-de-hors-jeu/2 ». Les cas de test citent le document ou la
section (« ifab-loi-11 », « ifab-loi-11#1-position-de-hors-jeu ») : un morceau est pertinent si
son identifiant commence par l'un d'eux. Les tests ne dépendent donc pas de la taille des morceaux.

Lister les identifiants pour écrire tests.jsonl : python -m src.rag --list
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from src.config import CORPUS_DIR
from src.result import Result

MAX_CHARS = 1200  # taille cible d'un morceau, à mesurer


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


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Regroupe les paragraphes jusqu'à max_chars ; coupe par phrases un paragraphe trop long."""
    parts: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if len(para) <= max_chars:
            parts.append(para)
        else:
            parts += re.split(r"(?<=[.!?])\s+", para)
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


def search(query: str, k: int = 5) -> list[tuple[Chunk, float]]:
    """Retourne les k meilleurs morceaux avec leur score."""
    raise NotImplementedError("Niveau 1 : recherche, semaine 2")


def answer(question: str) -> Result:
    """Recherche, puis réponse qui cite ses sources ou s'abstient."""
    raise NotImplementedError("Niveau 1 : réponse, semaine 2")


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
