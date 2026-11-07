"""Tests du corpus sans réseau : découpage Wikipédia, découpage IFAB, morceaux."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_corpus as bc  # noqa: E402

from src import metrics, rag  # noqa: E402

WIKI = """Intro du hors-jeu.

== Règle ==
Un joueur est hors-jeu si...

=== Exceptions ===
Pas de hors-jeu sur une rentrée de touche.

== Notes et références ==
[1] une référence

=== Sous-notes ===
à retirer aussi

== Histoire ==
Créé en 1863.
"""


def test_wiki_sections_drop_references():
    titles = [t for t, _ in bc.wiki_sections(WIKI)]
    assert titles == ["Introduction", "Règle", "Exceptions", "Histoire"]


def _fake_laws(with_toc: bool) -> str:
    toc = "".join(f"Loi {n} Titre {n}\n" for n in range(1, 18)) if with_toc else ""
    body = "".join(f"Loi {n} – Titre {n}\n1. Partie A\nTexte de la loi {n}.\n2. Partie B\nSuite.\n"
                   for n in range(1, 18))
    return "Sommaire\n" + toc + body + "Glossaire\nLoi 11 citée ici en passant.\n"


def test_split_laws_skips_table_of_contents():
    laws = bc.split_laws(_fake_laws(with_toc=True))
    assert sorted(laws) == list(range(1, 18))
    assert "Texte de la loi 11." in laws[11][1]
    assert "Texte de la loi 12." not in laws[11][1]


def test_split_laws_with_page_headers():
    body = "".join(f"Loi {n} – Titre {n}\nDébut {n}.\nLoi {n} – Titre {n}\nFin {n}.\n" for n in range(1, 18))
    laws = bc.split_laws("Sommaire\n" + "".join(f"Loi {n} Titre {n}\n" for n in range(1, 18)) + body)
    assert "Début 11." in laws[11][1] and "Fin 11." in laws[11][1]
    assert "Loi 11" not in laws[11][1]


def test_law_sections():
    sections = bc.law_sections("1. Partie A\nTexte.\n2. Partie B\nSuite.")
    assert [t for t, _ in sections] == ["1. Partie A", "2. Partie B"]


def test_split_laws_incomplete():
    assert bc.split_laws("Loi 1 – Le terrain\ntexte") == {}


def test_chunk_ids_are_stable():
    doc = bc.to_markdown({"id": "ifab-loi-11", "title": "Loi 11 : Hors-jeu", "source": "IFAB"},
                         [("1. Position de hors-jeu", "a. " * 900), ("2. Infraction", "Court.")])
    chunks = rag.chunk_document(doc, max_chars=1200)
    ids = [c.id for c in chunks]
    assert ids[0] == "ifab-loi-11#1-position-de-hors-jeu/1"
    assert ids[-1] == "ifab-loi-11#2-infraction"
    assert all(len(c.text) <= 1200 for c in chunks)
    assert metrics.is_relevant(ids[0], ["ifab-loi-11"])
    assert not metrics.is_relevant(ids[0], ["ifab-loi-1"])


def test_load_corpus(tmp_path):
    (tmp_path / "wiki").mkdir()
    (tmp_path / "wiki" / "wiki-x.md").write_text(
        bc.to_markdown({"id": "wiki-x", "title": "X", "source": "u"}, bc.wiki_sections(WIKI)), encoding="utf-8")
    chunks = rag.load_corpus(tmp_path)
    assert [c.id for c in chunks] == ["wiki-x#introduction", "wiki-x#regle", "wiki-x#exceptions", "wiki-x#histoire"]


def test_law_number():
    assert bc.law_number("Loi 11 – Hors-jeu") == 11
    assert bc.law_number("11 Le hors-jeu") == 11
    assert bc.law_number("Le coup de pied de but") == 16
    assert bc.law_number("Le ballon") == 2
    assert bc.law_number("Glossaire") is None


def test_law_ranges_from_outline():
    outline = [(0, "Avant-propos", 0)]
    for n in range(1, 18):
        outline += [(0, f"Loi {n} – Titre {n}", 10 * n), (1, f"1. Partie {n}", 10 * n + 2)]
    outline += [(0, "Modifications des Lois", 180)]
    r = bc.law_ranges(outline, 200)
    assert sorted(r) == list(range(1, 18))
    assert (r[11]["start"], r[11]["stop"], r[11]["title"]) == (110, 120, "Titre 11")
    assert r[17]["stop"] == 180 and r[17]["subs"] == [("1. Partie 17", 172)]
    assert bc.law_ranges(outline[:5], 200) == {}


def test_strip_repeated_lines():
    pages = [f"Lois du Jeu 2025/26\ncontenu {i}" for i in range(20)]
    assert bc.strip_repeated_lines(pages)[3] == "contenu 3"


def _separator_pdf() -> list[str]:
    pages = ["Sommaire\nLoi 1 Terrain\nLoi 2 Ballon"]
    for n in range(1, 18):
        pages += [f"Loi\n{n}", f"{len(pages) + 2}\nLois du Jeu 2026/27 | Loi {n} | Titre {n}\n1. Partie\nTexte {n}."]
    return pages + ["99", "Protocole\nd'assistance\nvidéo à\nl'arbitrage", "1. Principes\nTexte VAR.\n" + "ligne\n" * 10, "Glossaire"]


def test_separator_ranges():
    pages = _separator_pdf()
    seps = bc.separator_ranges(pages)
    assert sorted(seps) == list(range(1, 18))
    start, stop = seps[11]
    assert "Texte 11." in "".join(pages[start:stop]) and "Texte 12." not in "".join(pages[start:stop])
    assert bc.law_title(pages[start:stop], 11) == "Titre 11"
    assert "Lois du Jeu" not in bc.clean_page(pages[start])
    title, body = bc.var_protocol(pages, seps[17][1])
    assert title.startswith("Protocole") and "Texte VAR." in body and "Glossaire" not in body


def test_separator_ranges_missing_law():
    assert bc.separator_ranges(["Loi\n1", "texte"]) == {}


def test_law_sections_ignores_numbered_lists():
    body = "1. Principes\nIntro.\n1. Un arbitre assistant vidéo est un officiel de match ayant accès\nsuite\n2. Procédures\nFin."
    assert [t for t, _ in bc.law_sections(body)] == ["1. Principes", "2. Procédures"]
