"""Cohérence du jeu complémentaire de cas ambigus (docs/plan.md, section 6)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(name: str) -> list[dict]:
    return [json.loads(l) for l in (ROOT / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def test_extra_ambiguous_cases_are_new_and_well_formed():
    main = load("tests.jsonl")
    extra = load("tests_ambigus.jsonl")
    assert len(extra) == 20 and len({c["id"] for c in extra}) == 20
    assert not {c["id"] for c in extra} & {c["id"] for c in main}
    assert not {c["question"] for c in extra} & {c["question"] for c in main}
    for c in extra:
        assert c["type"] == "ambiguous" and c["expected"]["behavior"] in ("clarify", "refuse")
