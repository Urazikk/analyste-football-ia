"""Rapport d'avant-match structuré : sections calculées par le code à la publication, mise en page Markdown."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import data, report, tools

pytestmark = pytest.mark.skipif(not (data.cache_dir() / "matches").exists(),
                                reason="cache StatsBomb vide (python scripts/fetch_statsbomb.py)")
CONTENT = "L'Argentine arrive en forme, la France a calé en demi-finale. " * 5


def test_published_report_has_sections_computed_by_code():
    out = tools.publish_report("Argentine", "France", "Argentine - France", CONTENT)
    rep = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert (rep["home_team"], rep["away_team"], rep["content"]) == ("Argentina", "France", CONTENT)
    sec = rep["sections"]
    assert sec["form"]["home"]["team"] == "Argentina" and len(sec["form"]["away"]["matches"]) == 5
    assert [g["score"] for g in sec["head_to_head"]["matches"]] == ["3-3", "3-4"]
    last = sec["last_match"]["away"]
    assert (last["match"]["match_id"], last["stats"]["shots"]) == (3942752, 9)  # France, demi-finale Euro 2024
    assert Path(last["shot_map"]).read_bytes()[:4] == b"\x89PNG"
    assert rep["plots"] == [sec["last_match"]["home"]["shot_map"], last["shot_map"]]  # pour src/export.py


def test_markdown_layout():
    tools.publish_report("Japon", "Pays de Galles", "Japon - Pays de Galles", CONTENT)
    rep = json.loads(tools.report_path("Japan", "Wales").read_text(encoding="utf-8"))
    md = report.to_markdown(rep)
    for heading in ("# Japon - Pays de Galles", "## Analyse", "## Forme récente", "## Confrontations directes",
                    "## Dernier match de chaque équipe"):
        assert heading in md
    assert "Aucune confrontation dans les données" in md
    assert md.count("![Carte des tirs") == 2


def test_markdown_without_sections_still_renders():
    md = report.to_markdown({"home_team": "A", "away_team": "B", "title": "T", "content": "texte"})
    assert md.startswith("# T") and "texte" in md and "## Forme" not in md


def test_nothing_written_when_sections_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "build_sections", lambda h, a: (_ for _ in ()).throw(ValueError("x")))
    with pytest.raises(ValueError):
        tools.publish_report("France", "Espagne", "t", CONTENT)
    assert not tools.report_path("France", "Spain").exists()


def test_pdf_export_includes_the_two_shot_maps():
    from src import export

    out = tools.publish_report("Argentine", "France", "Argentine - France", CONTENT)
    rep = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert len(export.report_plots(rep, Path(out["path"]).parent.parent)) == 2
    assert export.report_to_pdf(Path(out["path"])).read_bytes()[:4] == b"%PDF"
