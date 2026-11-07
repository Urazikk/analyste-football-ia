"""Cohérence du jeu de test avec le corpus : chaque réponse attendue est dans les sources citées."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import metrics, rag
from src.config import CORPUS_DIR

ROOT = Path(__file__).resolve().parent.parent
CASES = [json.loads(l) for l in (ROOT / "tests.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
needs_corpus = pytest.mark.skipif(not any((CORPUS_DIR / "ifab").glob("*.md")),
                                  reason="corpus IFAB non construit (scripts/build_corpus.py --ifab-download)")


def test_ids_unique_and_types_known():
    assert len({c["id"] for c in CASES}) == len(CASES)
    assert {c["type"] for c in CASES} <= {"doc", "absent", "task", "ambiguous"}


@needs_corpus
@pytest.mark.parametrize("case", [c for c in CASES if c["type"] == "doc"], ids=lambda c: c["id"])
def test_doc_answer_in_sources(case):
    exp = case["expected"]
    text = " ".join(ch.text for ch in rag.load_corpus() if metrics.is_relevant(ch.id, exp["relevant_sources"]))
    assert text, f"aucune source {exp['relevant_sources']}"
    assert metrics.keywords_match(text, exp["keywords"])
