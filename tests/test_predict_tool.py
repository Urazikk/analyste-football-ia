"""Pronostic côté agent et rapport (GAUTIER.md, section 8) : noms, outil simulate_match, section du rapport.

Sans réseau : modèle synthétique (monkeypatch) ou cache des résultats internationaux (sauté s'il est absent,
`python scripts/eval_prediction.py` le télécharge).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src import data, predict, report, tools
from src.tools import REGISTRY

needs_intl = pytest.mark.skipif(not predict.cache_path().exists(),
                                reason="résultats internationaux absents (python scripts/eval_prediction.py)")
needs_sb = pytest.mark.skipif(not (data.cache_dir() / "matches").exists(),
                              reason="cache StatsBomb vide (python scripts/fetch_statsbomb.py)")
CONTENT = "La France reste solide derrière, l'Espagne domine le ballon et les occasions. " * 4


@pytest.fixture
def toy_model(monkeypatch):
    """Deux sélections, Spain nettement plus forte : aucun téléchargement."""
    rows = [("2020-01-01", "Spain", "France", 3, 0, "Friendly", True)] * 5
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"])
    df["date"] = pd.to_datetime(df["date"])
    hist = predict.run_elo(df)
    monkeypatch.setattr(predict, "_model", lambda: (hist, (0.2, 0.8)))


# 1. Correspondance des noms -------------------------------------------------------------

@needs_intl
@needs_sb
def test_every_statsbomb_team_exists_in_intl_results():
    known = set(predict._model()[0].ratings)
    assert set(data.team_names()) <= known
    assert set(predict.INTL_ALIASES.values()) <= known


@needs_intl
@pytest.mark.parametrize("name,expected", [("Espagne", "Spain"), ("Corée du Sud", "South Korea"),
                                           ("Korea Republic", "South Korea"), ("Côte d'Ivoire", "Ivory Coast"),
                                           ("Türkiye", "Turkey"), ("Chine", "China"), ("USA", "United States"),
                                           ("czechia", "Czech Republic"), ("Irlande", "Republic of Ireland")])
def test_resolve_intl(name, expected):
    assert predict.resolve_intl(name) == expected


@needs_intl
def test_resolve_intl_unknown_with_suggestion():
    with pytest.raises(ValueError, match="Vouliez-vous dire : France"):
        predict.resolve_intl("Fance")


# 2. Outil simulate_match ------------------------------------------------------------------

def test_simulate_match_tool(toy_model):
    tool = REGISTRY["simulate_match"]
    assert tool.effect == "compute"
    out = tool.fn(home_team="Espagne", away_team="France")
    p = out["probabilities"]
    assert (out["home_team"], out["away_team"], out["neutral"]) == ("Spain", "France", True)
    assert p["home_win"] > p["away_win"] and sum(p.values()) == pytest.approx(1, abs=0.002)
    assert len(out["likely_scores"]) == 3 and out["elo"]["home"] > out["elo"]["away"]
    assert out == tool.fn(home_team="Spain", away_team="France")  # graine fixée : reproductible
    assert len(json.dumps(out)) < 800  # sortie courte
    with pytest.raises(ValueError, match="différentes"):
        tool.fn(home_team="Espagne", away_team="Spain")


def test_home_advantage_when_not_neutral(toy_model):
    neutral = tools.simulate_match("France", "Espagne", neutral=True)["probabilities"]["home_win"]
    at_home = tools.simulate_match("France", "Espagne", neutral=False)["probabilities"]["home_win"]
    assert at_home > neutral


# 3. Section « Pronostic » du rapport (et du PDF, qui reprend to_markdown) -------------------

@needs_sb
def test_report_has_prediction_section(toy_model, monkeypatch, tmp_path):
    csv = tmp_path / "results.csv"
    csv.write_text("x")
    monkeypatch.setattr(predict, "cache_path", lambda: csv)
    out = tools.publish_report("Espagne", "France", "Espagne - France", CONTENT)
    rep = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    pred = rep["sections"]["prediction"]
    assert pred["home_team"] == "Spain" and pred["neutral"] is True
    md = report.to_markdown(rep)
    assert "## Pronostic" in md and f"Victoire Spain {100 * pred['probabilities']['home_win']:.0f} %" in md

    from src import export

    assert export.report_to_pdf(Path(out["path"])).read_bytes()[:4] == b"%PDF"


@needs_sb
def test_report_published_without_intl_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(predict, "cache_path", lambda: tmp_path / "absent.csv")
    out = tools.publish_report("Japon", "Pays de Galles", "Japon - Pays de Galles", CONTENT)
    rep = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
    assert rep["sections"]["prediction"] is None and "## Pronostic" not in report.to_markdown(rep)
