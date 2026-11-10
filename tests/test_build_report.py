"""Script du rapport : mise en forme des tableaux, sans LLM ni Chrome."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_report as br  # noqa: E402


def test_fmt():
    assert br._fmt(None) == "—"
    assert br._fmt(0.95, (0.85, 1.0)) == "0.95 [0.85-1.00]"
    assert br._fmt(0.00026) == "0.00026"


def test_table_skips_empty_columns():
    s = {"Cas": 25, "Exactitude": 0.95, "Citation": None, "_ci": {"Exactitude": (0.85, 1.0)}}
    t = br.table({1: s}, ["Exactitude", "Citation"], "Qualité")
    assert "Exactitude" in t and "Citation" not in t and "0.95 [0.85-1.00]" in t


def test_template_has_all_placeholders_filled_by_build():
    text = (br.DOC / "rapport.md").read_text(encoding="utf-8")
    for key in ("choix", "protocole", "table_qualite", "table_couts", "comparaison", "robustesse", "injection", "couts"):
        assert "{{" + key + "}}" in text
