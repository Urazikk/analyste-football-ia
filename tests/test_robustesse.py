"""Cohérence du jeu de reformulations avec le jeu de test principal."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name: str) -> list[dict]:
    return [json.loads(l) for l in (ROOT / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def test_paraphrases_match_originals():
    originals = {c["id"]: c for c in load("tests.jsonl")}
    paras = load("tests_robustesse.jsonl")
    assert len({c["id"] for c in paras}) == len(paras)
    for c in paras:
        o = originals[c["original"]]
        assert c["expected"] == o["expected"] and c["type"] == o["type"] and c["question"] != o["question"]
        assert c["style"] in ("familier", "situation")
