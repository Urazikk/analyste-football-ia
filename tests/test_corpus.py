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
