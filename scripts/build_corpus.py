"""Construit le corpus du RAG dans data/corpus/.

    python scripts/build_corpus.py                         # Wikipédia seul
    python scripts/build_corpus.py --ifab-pdf lois.pdf     # + lois du jeu IFAB (PDF FR téléchargé à la main)

Sorties :
- data/corpus/wiki/*.md  : articles Wikipédia (CC BY-SA 4.0), versionnés dans git avec leur révision
- data/corpus/ifab/*.md  : une loi par fichier, NON versionnés (licence IFAB)
- data/corpus/manifest.json : liste des documents, source, licence, empreinte sha256

Chaque document est un Markdown avec un en-tête de métadonnées et des sections « ## ».
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CORPUS_DIR  # noqa: E402

WIKI_API = "https://fr.wikipedia.org/w/api.php"
USER_AGENT = "analyste-football-ia/0.1 (projet etudiant ECE)"

# Articles retenus : règles et arbitrage. Les titres absents sont signalés puis ignorés.
WIKI_TITLES = [
    "Lois du jeu (football)",
    "Hors-jeu (football)",
    "Faute (football)",
    "Coup franc (football)",
    "Coup de pied de réparation",
    "Coup de pied de coin",
    "Rentrée de touche",
    "Coup de pied de but",
    "Carton jaune",
    "Carton rouge",
    "Arbitre (football)",
    "Arbitre assistant vidéo",
    "Tirs au but",
    "Prolongation (sport)",
    "Main (football)",
    "Gardien de but (football)",
    "Remplaçant (football)",
    "Terrain de football",
    "Ballon de football",
    "Équipement de football",
]

DROP_SECTIONS = {"notes et references", "references", "voir aussi", "liens externes",
                 "bibliographie", "articles connexes", "annexes", "notes"}


# Outils communs -------------------------------------------------------------------

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def to_markdown(meta: dict[str, str], sections: list[tuple[str, str]]) -> str:
    head = "---\n" + "".join(f"{k}: {v}\n" for k, v in meta.items()) + "---\n\n"
    body = f"# {meta['title']}\n\n"
    for title, text in sections:
        if text.strip():
            body += f"## {title}\n\n{text.strip()}\n\n"
    return head + body


# Wikipédia ------------------------------------------------------------------------

def wiki_sections(extract: str) -> list[tuple[str, str]]:
    """Découpe un extrait texte brut (exsectionformat=wiki) en sections de niveau 2 et 3.

    Les sections bibliographiques sont retirées avec leurs sous-sections.
    """
    sections: list[tuple[str, str]] = []
    title, buf, dropping = "Introduction", [], False
    for line in extract.splitlines():
        m = re.match(r"^(={2,4})\s*(.+?)\s*\1\s*$", line)
        if m:
            if not dropping:
                sections.append((title, "\n".join(buf)))
            level, title, buf = len(m.group(1)), m.group(2), []
            if level == 2:
                dropping = slugify(title).replace("-", " ") in DROP_SECTIONS
        else:
            buf.append(line)
    if not dropping:
        sections.append((title, "\n".join(buf)))
    clean = [(t, re.sub(r"\n{3,}", "\n\n", x).strip()) for t, x in sections]
    return [(t, x) for t, x in clean if x]


def fetch_wiki(title: str) -> dict | None:
    import requests

    params = {"action": "query", "prop": "extracts|revisions|info", "rvprop": "ids", "inprop": "url",
              "explaintext": 1, "exsectionformat": "wiki", "redirects": 1, "titles": title,
              "format": "json", "formatversion": 2}
    r = requests.get(WIKI_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    page = r.json()["query"]["pages"][0]
    return None if page.get("missing") else page


def build_wiki(out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    docs = []
    for title in WIKI_TITLES:
        page = fetch_wiki(title)
        time.sleep(0.5)  # politesse envers l'API
        if page is None:
            print(f"  absent : {title}")
            continue
        doc_id = "wiki-" + slugify(page["title"])
        meta = {"id": doc_id, "title": page["title"], "source": page["fullurl"],
                "licence": "CC BY-SA 4.0", "revision": str(page["revisions"][0]["revid"]),
                "retrieved": date.today().isoformat()}
        path = out / f"{doc_id}.md"
        path.write_text(to_markdown(meta, wiki_sections(page["extract"])), encoding="utf-8")
        docs.append({**meta, "path": path})
        print(f"  ok : {page['title']}")
    return docs


# IFAB -----------------------------------------------------------------------------

LAW_RE = re.compile(r"(?mi)^\s*loi\s+(\d{1,2})\s*[-–—:.]?\s*(.*)$")
SUB_RE = re.compile(r"^(\d{1,2})\.\s+(\S.{0,80})$")


def split_laws(text: str) -> dict[int, tuple[str, str]]:
    """Découpe le texte des Lois du jeu en 17 lois {numéro: (titre, texte)}.

    Deux pièges : le sommaire cite « Loi 1 ... Loi 17 », et chaque page peut répéter
    « Loi N » en en-tête. 1) En remontant depuis la fin, on fixe pour chaque loi sa dernière
    mention avant la loi suivante (elle est dans le corps). 2) Le début de la loi N est sa
    première mention après toute mention d'une autre loi qui précède ce point.
    """
    matches = [(int(m.group(1)), m.start(), m.end(), m.group(2).strip()) for m in LAW_RE.finditer(text)]
    last: dict[int, int] = {}
    pos = len(text) + 1
    for n in range(17, 0, -1):
        cands = [m[1] for m in matches if m[0] == n and m[1] < pos]
        if not cands:
            return {}
        last[n] = pos = cands[-1]
    starts: dict[int, tuple[int, int, str]] = {}
    for n in range(1, 18):
        before = [m[1] for m in matches if m[0] != n and m[1] < last[n]]
        floor = max(before, default=-1)
        _, start, end, title = next(m for m in matches if m[0] == n and floor < m[1] <= last[n])
        starts[n] = (start, end, title)
    laws = {}
    for n in range(1, 18):
        start, end, title = starts[n]
        stop = starts[n + 1][0] if n < 17 else len(text)
        body = LAW_RE.sub("", text[end:stop])  # retire les en-têtes de page « Loi N »
        laws[n] = (title or f"Loi {n}", body)
    return laws


def law_sections(body: str) -> list[tuple[str, str]]:
    """Sections d'une loi d'après ses sous-titres numérotés (« 1. Surface de jeu »)."""
    sections: list[tuple[str, str]] = []
    title, buf = "Introduction", []
    for line in body.splitlines():
        m = SUB_RE.match(line.strip())
        if m and not line.strip().endswith((".", ",", ";")):
            sections.append((title, "\n".join(buf)))
            title, buf = f"{m.group(1)}. {m.group(2).strip()}", []
        else:
            buf.append(line)
    sections.append((title, "\n".join(buf)))
    return [(t, re.sub(r"[ \t]+", " ", x).strip()) for t, x in sections if x.strip()]


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def build_ifab(pdf: Path, out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    laws = split_laws(pdf_text(pdf))
    if not laws:
        raise SystemExit("Découpage IFAB impossible : vérifier que le PDF est bien les Lois du jeu en français.")
    docs = []
    for n, (title, body) in laws.items():
        doc_id = f"ifab-loi-{n:02d}"
        meta = {"id": doc_id, "title": f"Loi {n} : {title}", "source": f"IFAB, Lois du jeu ({pdf.name})",
                "licence": "IFAB, usage pédagogique, non redistribué", "retrieved": date.today().isoformat()}
        path = out / f"{doc_id}.md"
        path.write_text(to_markdown(meta, law_sections(body)), encoding="utf-8")
        docs.append({**meta, "path": path})
    print(f"  ok : {len(docs)} lois IFAB")
    return docs


# Manifeste ------------------------------------------------------------------------

def write_manifest(docs: list[dict], corpus: Path) -> None:
    rows = []
    for d in sorted(docs, key=lambda d: d["id"]):
        path: Path = d.pop("path")
        rows.append({**d, "file": str(path.relative_to(corpus)),
                     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (corpus / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifeste : {len(rows)} documents")


def existing_docs(folder: Path) -> list[dict]:
    """Documents déjà construits d'un dossier (pour ne pas les perdre du manifeste)."""
    docs = []
    for path in sorted(folder.glob("*.md")):
        meta = dict(re.findall(r"^(\w+): (.*)$", path.read_text(encoding="utf-8").split("---")[1], re.M))
        docs.append({**meta, "path": path})
    return docs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ifab-pdf", type=Path, help="PDF des Lois du jeu en français (theifab.com)")
    p.add_argument("--no-wiki", action="store_true", help="garder les articles Wikipédia déjà téléchargés")
    a = p.parse_args()

    print("Wikipédia :")
    docs = existing_docs(CORPUS_DIR / "wiki") if a.no_wiki else build_wiki(CORPUS_DIR / "wiki")
    print("IFAB :")
    docs += build_ifab(a.ifab_pdf, CORPUS_DIR / "ifab") if a.ifab_pdf else existing_docs(CORPUS_DIR / "ifab")
    write_manifest(docs, CORPUS_DIR)


if __name__ == "__main__":
    main()
