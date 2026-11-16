"""Jeu complémentaire de cas absents, jamais utilisé pour régler le niveau 3 (docs/decisions.md, 16 novembre)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import CORPUS_DIR

ROOT = Path(__file__).resolve().parent.parent
needs_corpus = pytest.mark.skipif(not any((CORPUS_DIR / "ifab").glob("*.md")),
                                  reason="corpus IFAB non construit (scripts/build_corpus.py --ifab-download)")


def load(name: str) -> list[dict]:
    return [json.loads(l) for l in (ROOT / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def test_extra_absent_cases_are_new_and_well_formed():
    main, extra = load("tests.jsonl"), load("tests_absents.jsonl")
    assert len(extra) == 10 and len({c["id"] for c in extra}) == 10
    assert not {c["id"] for c in extra} & {c["id"] for c in main}
    for c in extra:
        assert c["type"] == "absent" and c["expected"] == {"behavior": "abstain"} and c["absent_terms"]


@needs_corpus
def test_absent_terms_are_not_in_the_corpus():
    corpus = " ".join(p.read_text(encoding="utf-8").lower() for d in ("wiki", "ifab")
                      for p in (CORPUS_DIR / d).glob("*.md"))
    for c in load("tests_absents.jsonl"):
        found = [t for t in c["absent_terms"] if t.lower() in corpus]
        assert not found, f"{c['id']} : {found} présent dans le corpus"
