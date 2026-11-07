"""Construit le corpus du RAG dans data/corpus/.

    python scripts/build_corpus.py                         # Wikipédia seul
    python scripts/build_corpus.py --ifab-download         # + lois du jeu IFAB 2026/27 (PDF FR téléchargé)
    python scripts/build_corpus.py --ifab-pdf lois.pdf     # + lois du jeu IFAB depuis un PDF local
    python scripts/build_corpus.py --inspect lois.pdf      # diagnostic du PDF si le découpage échoue

Lois IFAB : découpage par les signets du PDF, sinon par les pages séparatrices « Loi / N »
(édition 2026/27), sinon par le texte (« Loi N » en début de ligne).

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
# Lois du jeu 2026/27 en français, pages simples (page « PDF Downloads » de theifab.com)
IFAB_PDF_URL = "https://downloads.theifab.com/downloads/lois-du-jeu-202627-pages-simples?l=fr"
IFAB_PDF_PATH = Path(__file__).resolve().parent.parent / "data" / "cache" / "lois-du-jeu-2026-27.pdf"
USER_AGENT = "analyste-football-ia/0.1 (https://github.com/Urazikk/analyste-football-ia; projet etudiant ECE)"

# Articles retenus : une page par loi du jeu, plus l'arbitrage et la discipline.
# Les titres absents sont signalés puis ignorés ; les redirections vers une même page sont dédoublonnées.
WIKI_TITLES = [f"Loi {n} du football" for n in range(1, 18)] + [
    "Lois du jeu (football)",
    "Hors-jeu (football)",
    "Penalty (football)",
    "Corner (football)",
    "Carton jaune",
    "Carton rouge",
    "Arbitre (football)",
    "Assistance vidéo à l'arbitrage en football",
    "Tirs au but",
    "Gardien de but (football)",
    "Remplaçant (football)",
    "Ballon de football",
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
    for attempt in range(6):  # 429 : on attend le délai demandé par l'API
        r = requests.get(WIKI_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        if r.status_code != 429:
            break
        wait = int(r.headers.get("retry-after", 2 ** attempt * 5))
        print(f"  429, nouvel essai dans {wait} s")
        time.sleep(wait)
    r.raise_for_status()
    page = r.json()["query"]["pages"][0]
    return None if page.get("missing") else page


def build_wiki(out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    docs = []
    for title in WIKI_TITLES:
        page = fetch_wiki(title)
        time.sleep(3)  # politesse : l'IP partagée est vite limitée (429)
        if page is None:
            print(f"  absent : {title}")
            continue
        doc_id = "wiki-" + slugify(page["title"])
        if any(d["id"] == doc_id for d in docs):
            print(f"  doublon : {title} -> {page['title']}")
            continue
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
SUB_MAX = 60  # longueur maximale d'un sous-titre


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
    """Sections d'une loi d'après ses sous-titres numérotés (« 1. Surface de jeu »).

    Un sous-titre est court, sans ponctuation finale, et suit la numérotation (1, 2, 3...) :
    une liste numérotée dans le texte n'ouvre donc pas de section.
    """
    sections: list[tuple[str, str]] = []
    title, buf, expected = "Introduction", [], 1
    for line in body.splitlines():
        m = SUB_RE.match(line.strip())
        if (m and int(m.group(1)) == expected and len(line.strip()) <= SUB_MAX
                and not line.strip().endswith((".", ",", ";", ":"))):
            sections.append((title, "\n".join(buf)))
            title, buf, expected = f"{m.group(1)}. {m.group(2).strip()}", [], expected + 1
        else:
            buf.append(line)
    sections.append((title, "\n".join(buf)))
    return [(t, re.sub(r"[ \t]+", " ", x).strip()) for t, x in sections if x.strip()]


# Titres officiels des 17 lois, pour reconnaître un signet sans numéro
LAW_TITLES = {
    1: "terrain", 2: "ballon", 3: "joueurs", 4: "equipement", 5: "arbitre", 6: "autres arbitres",
    7: "duree", 8: "coup d'envoi", 9: "ballon en jeu", 10: "issue", 11: "hors-jeu",
    12: "fautes", 13: "coups francs", 14: "penalty", 15: "rentree de touche",
    16: "coup de pied de but", 17: "coup de pied de coin",
}
OUTLINE_NUM_RE = re.compile(r"^\s*(?:loi\s*)?(\d{1,2})\b\s*[-–—:.|]?\s*(.*)$", re.I)


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower().replace("’", "'"))
    return "".join(c for c in s if not unicodedata.combining(c))


def read_outline(reader) -> list[tuple[int, str, int]]:
    """Signets du PDF à plat : (profondeur, titre, page de départ, à partir de 0)."""
    flat: list[tuple[int, str, int]] = []

    def walk(items, depth: int) -> None:
        for it in items:
            if isinstance(it, list):
                walk(it, depth + 1)
            else:
                try:
                    flat.append((depth, str(it.title).strip(), reader.get_destination_page_number(it)))
                except Exception:
                    pass

    walk(reader.outline, 0)
    return flat


def law_number(title: str) -> int | None:
    m = OUTLINE_NUM_RE.match(title)
    if m and 1 <= int(m.group(1)) <= 17:
        return int(m.group(1))
    t = _plain(title)
    # titre seul : la correspondance la plus longue gagne (« coup de pied de but » avant « ballon »)
    hits = [(len(v), n) for n, v in LAW_TITLES.items() if t.strip(" .") in (v, f"le {v}", f"la {v}", f"les {v}", f"l'{v}")
            or t.endswith(" " + v)]
    return max(hits)[1] if hits else None


def law_ranges(outline: list[tuple[int, str, int]], n_pages: int) -> dict[int, dict]:
    """Pages de chaque loi d'après les signets : {n: {title, start, stop, subs: [(titre, page)]}}.

    On garde la première suite croissante de signets 1..17 au même niveau ; la loi 17 s'arrête
    au signet suivant de même niveau (ex. « Modifications ») ou à la fin du document.
    """
    found: dict[int, tuple[int, int, str, int]] = {}  # n -> (index, profondeur, titre, page)
    for i, (depth, title, page) in enumerate(outline):
        n = law_number(title)
        if n and n not in found and all(m < n for m in found) and (not found or depth == found[min(found)][1]):
            found[n] = (i, depth, title, page)
    if sorted(found) != list(range(1, 18)):
        return {}
    laws = {}
    for n in range(1, 18):
        i, depth, title, start = found[n]
        if n < 17:
            j, stop = found[n + 1][0], found[n + 1][3]
        else:
            j = next((k for k in range(i + 1, len(outline)) if outline[k][0] <= depth), len(outline))
            stop = outline[j][2] if j < len(outline) else n_pages
        subs = [(t, p) for d, t, p in outline[i + 1:j] if d == depth + 1]
        m = OUTLINE_NUM_RE.match(title)
        clean = m.group(2).strip() if m and m.group(2).strip() else title
        laws[n] = {"title": clean, "start": start, "stop": max(stop, start + 1), "subs": subs}
    return laws


def strip_repeated_lines(pages: list[str], min_pages: int = 15) -> list[str]:
    """Retire en-têtes et pieds de page : lignes courtes répétées sur beaucoup de pages."""
    count: dict[str, int] = {}
    for text in pages:
        for line in {l.strip() for l in text.splitlines() if l.strip()}:
            count[line] = count.get(line, 0) + 1
    rep = {l for l, c in count.items() if c >= min_pages and len(l) < 80}
    return ["\n".join(l for l in t.splitlines() if l.strip() not in rep) for t in pages]


HEADER_RE = re.compile(r"^Lois du Jeu \d{4}/\d{2}\s*\|.*$")  # en-tête courant des pages
HEADER_LAW_RE = re.compile(r"\|\s*Loi\s+(\d{1,2})\s*\|\s*(.+)$")


def _lines(page: str) -> list[str]:
    return [l.strip() for l in page.splitlines() if l.strip()]


def is_title_page(page: str) -> bool:
    """Page de titre : 1 à 4 lignes de texte hors numéro de page, sans en-tête courant."""
    ls = [l for l in _lines(page) if not l.isdigit()]
    return 1 <= len(ls) <= 4 and not any("|" in l for l in ls)


def separator_ranges(pages: list[str]) -> dict[int, tuple[int, int]]:
    """Pages de chaque loi d'après les pages séparatrices « Loi / N » (édition 2026/27 sans signets).

    La loi N va de sa page séparatrice (exclue) à celle de la loi N+1 ; la loi 17 s'arrête
    à la page de titre suivante (ex. « Protocole d'assistance vidéo à l'arbitrage »).
    """
    seps: dict[int, int] = {}
    for i, page in enumerate(pages):
        ls = _lines(page)
        if len(ls) == 2 and ls[0].lower() == "loi" and ls[1].isdigit() and 1 <= int(ls[1]) <= 17:
            seps.setdefault(int(ls[1]), i)
    if sorted(seps) != list(range(1, 18)) or any(seps[n] >= seps[n + 1] for n in range(1, 17)):
        return {}
    stop17 = next((i for i in range(seps[17] + 1, len(pages)) if is_title_page(pages[i])), len(pages))
    return {n: (seps[n] + 1, seps[n + 1] if n < 17 else stop17) for n in range(1, 18)}


def clean_page(page: str) -> str:
    """Retire numéros de page et en-têtes courants."""
    return "\n".join(l for l in page.splitlines() if not l.strip().isdigit() and not HEADER_RE.match(l.strip()))


def law_title(pages: list[str], n: int) -> str:
    """Titre officiel lu dans l'en-tête courant « Lois du Jeu 2026/27 | Loi N | Titre »."""
    for page in pages:
        for line in _lines(page):
            m = HEADER_LAW_RE.search(line)
            if m and int(m.group(1)) == n:
                return m.group(2).strip()
    return LAW_TITLES[n].capitalize()


def var_protocol(pages: list[str], start: int) -> tuple[str, str] | None:
    """Protocole VAR : de sa page de titre à la page de titre suivante."""
    if start >= len(pages) or "vid" not in _plain(" ".join(_lines(pages[start]))):
        return None
    title = " ".join(l for l in _lines(pages[start]) if not l.isdigit())
    stop = next((i for i in range(start + 1, len(pages)) if is_title_page(pages[i])), len(pages))
    return title, "\n".join(clean_page(p) for p in pages[start + 1:stop])


def build_ifab(pdf: Path, out: Path) -> list[dict]:
    from pypdf import PdfReader

    reader = PdfReader(pdf)
    raw = [p.extract_text() or "" for p in reader.pages]
    pages = strip_repeated_lines(raw)
    extra: tuple[str, str] | None = None
    ranges = law_ranges(read_outline(reader), len(pages))
    laws: dict[int, tuple[str, list[tuple[str, str]]]] = {}
    if ranges:
        print("  découpage par signets")
        for n, r in ranges.items():
            subs = [(t, p) for t, p in r["subs"] if r["start"] <= p < r["stop"]]
            if subs:
                bounds = [(r["title"], r["start"])] + subs + [("", r["stop"])]
                sections = [(t, "\n".join(pages[p:max(q, p + 1)]) if p < q else pages[p])
                            for (t, p), (_, q) in zip(bounds, bounds[1:])]
                sections = [("Introduction" if k == 0 else t, x) for k, (t, x) in enumerate(sections)]
            else:
                sections = law_sections("\n".join(pages[r["start"]:r["stop"]]))
            laws[n] = (r["title"], [(t, re.sub(r"[ \t]+", " ", x).strip()) for t, x in sections if x.strip()])
    elif seps := separator_ranges(raw):
        print("  découpage par pages séparatrices « Loi N »")
        for n, (start, stop) in seps.items():
            laws[n] = (law_title(raw[start:stop], n), law_sections("\n".join(clean_page(p) for p in raw[start:stop])))
        extra = var_protocol(raw, seps[17][1])
    else:
        print("  pas de signets exploitables : découpage par le texte")
        for n, (title, body) in split_laws("\n".join(pages)).items():
            laws[n] = (title, law_sections(body))
    if not laws:
        raise SystemExit("Découpage IFAB impossible. Lancer avec --inspect et envoyer la sortie.")

    out.mkdir(parents=True, exist_ok=True)
    docs = []
    for n, (title, sections) in laws.items():
        doc_id = f"ifab-loi-{n:02d}"
        meta = {"id": doc_id, "title": f"Loi {n} : {title}", "source": f"IFAB, Lois du jeu ({pdf.name})",
                "licence": "IFAB, usage pédagogique, non redistribué", "retrieved": date.today().isoformat()}
        path = out / f"{doc_id}.md"
        path.write_text(to_markdown(meta, sections), encoding="utf-8")
        docs.append({**meta, "path": path})
        print(f"  Loi {n:2d} : {title} ({len(sections)} sections, {sum(len(x) for _, x in sections)} caractères)")
    if extra:
        title, body = extra
        meta = {"id": "ifab-protocole-var", "title": title, "source": f"IFAB, Lois du jeu ({pdf.name})",
                "licence": "IFAB, usage pédagogique, non redistribué", "retrieved": date.today().isoformat()}
        path = out / "ifab-protocole-var.md"
        path.write_text(to_markdown(meta, law_sections(body)), encoding="utf-8")
        docs.append({**meta, "path": path})
        print(f"  {title} ({len(body)} caractères)")
    return docs


def inspect_pdf(pdf: Path) -> None:
    """Affiche de quoi corriger le découpage sans ouvrir le PDF : signets et débuts de pages."""
    from pypdf import PdfReader

    reader = PdfReader(pdf)
    outline = read_outline(reader)
    print(f"{len(reader.pages)} pages, {len(outline)} signets")
    for depth, title, page in outline[:150]:
        n = law_number(title)
        print(f"{'  ' * depth}p{page + 1:>3} {title}" + (f"   -> loi {n}" if n else ""))
    print("\nDébut de quelques pages :")
    for i in range(0, len(reader.pages), 12):
        lines = [l.strip() for l in (reader.pages[i].extract_text() or "").splitlines() if l.strip()][:3]
        print(f"p{i + 1:>3} | " + " / ".join(lines)[:150])


def download_ifab(dest: Path = IFAB_PDF_PATH) -> Path:
    """Télécharge le PDF IFAB dans data/cache/ (non versionné), sauf s'il y est déjà."""
    import requests

    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(IFAB_PDF_URL, headers={"User-Agent": USER_AGENT}, timeout=120)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            raise SystemExit(f"Le lien IFAB ne renvoie plus un PDF : {IFAB_PDF_URL}")
        dest.write_bytes(r.content)
    print(f"  PDF IFAB : {dest} ({dest.stat().st_size // 1024} Ko)")
    return dest


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
    p.add_argument("--ifab-download", action="store_true", help="télécharge le PDF IFAB 2026/27 dans data/cache/")
    p.add_argument("--no-wiki", action="store_true", help="garder les articles Wikipédia déjà téléchargés")
    p.add_argument("--inspect", type=Path, metavar="PDF", help="affiche signets et débuts de pages, puis s'arrête")
    a = p.parse_args()
    if a.inspect:
        inspect_pdf(a.inspect)
        return

    print("Wikipédia :")
    docs = existing_docs(CORPUS_DIR / "wiki") if a.no_wiki else build_wiki(CORPUS_DIR / "wiki")
    print("IFAB :")
    if a.ifab_download:
        a.ifab_pdf = download_ifab()
    docs += build_ifab(a.ifab_pdf, CORPUS_DIR / "ifab") if a.ifab_pdf else existing_docs(CORPUS_DIR / "ifab")
    write_manifest(docs, CORPUS_DIR)


if __name__ == "__main__":
    main()
