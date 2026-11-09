"""Outils StatsBomb et règles métier de publish_report, sur un match réel en cache (sans réseau ni LLM).

Valeurs attendues vérifiées à la main dans les événements d'Espagne 2-1 France (Euro 2024, demi-finale).
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from src import data, tools
from src.tools import REGISTRY

MATCH = 3942752
needs_cache = pytest.mark.skipif(not (data.cache_dir() / "events" / f"{MATCH}.pkl").exists(),
                                 reason="cache StatsBomb vide (python scripts/fetch_statsbomb.py)")
pytestmark = needs_cache

CONTENT = ("Espagne et France se retrouvent après la demi-finale de l'Euro 2024 gagnée 2-1 par l'Espagne. "
           "La France avait tiré 9 fois contre 6, pour 0,85 xG contre 0,42. L'Espagne a eu 58 % des passes. "
           "Attention aux frappes de loin espagnoles.")


def test_list_matches_sorted_and_resolved():
    out = REGISTRY["list_matches"].fn(team="Espagne")
    assert [m["match_id"] for m in out[:2]] == [3943043, MATCH]
    assert out[0] == {"match_id": 3943043, "date": "2024-07-14", "competition": "Europe - UEFA Euro",
                      "stage": "Final", "home_team": "Spain", "away_team": "England", "score": "2-1"}
    assert len(out) == 10 and [m["date"] for m in out] == sorted((m["date"] for m in out), reverse=True)
    # Euro 2024 (7) + CdM 2022 (4) + Euro 2020 (6) + CdM 2018 (4) = 21, plafonné à 20
    assert len(REGISTRY["list_matches"].fn(team="Spain", limit=20)) == 20
    assert len(json.dumps(out)) < 8000


def test_match_events_filtered_and_short():
    goals = REGISTRY["match_events"].fn(match_id=MATCH, event_type="but")
    assert [(e["minute"], e["team"]) for e in goals["events"]] == [(8, "France"), (20, "Spain"), (24, "Spain")]
    shots = REGISTRY["match_events"].fn(match_id=MATCH, event_type="tir", team="Espagne")
    assert shots["total"] == 6
    passes = REGISTRY["match_events"].fn(match_id=MATCH, event_type="Pass")
    assert passes["shown"] == 30 and passes["total"] > 900 and len(json.dumps(passes)) < 8000
    with pytest.raises(ValueError, match="Type d'événement inconnu"):
        REGISTRY["match_events"].fn(match_id=MATCH, event_type="corner volant")


def test_team_stats_values():
    s = REGISTRY["team_stats"].fn(match_id=MATCH, team="France")
    assert (s["goals"], s["shots"], s["shots_on_target"], s["xg"]) == (1, 9, 3, 0.85)
    assert s["opponent"] == "Spain"
    assert REGISTRY["team_stats"].fn(match_id=MATCH, team="Spain")["possession_pct"] == pytest.approx(100 - s["possession_pct"])
    with pytest.raises(ValueError, match="n'a pas joué"):
        REGISTRY["team_stats"].fn(match_id=MATCH, team="Italie")


def test_plot_shots_writes_png():
    out = REGISTRY["plot_shots"].fn(match_id=MATCH, team="France")
    assert (out["shots"], out["goals"]) == (9, 1)
    assert Path(out["path"]).read_bytes()[:4] == b"\x89PNG"


def test_registry_schemas_valid():
    for t in REGISTRY.values():
        jsonschema.Draft7Validator.check_schema(t.parameters)
        assert t.effect in ("read", "compute", "irreversible")
    assert [t.name for t in REGISTRY.values() if t.effect == "irreversible"] == ["publish_report"]


# Règles métier de publish_report : une par test -------------------------------------

def args(**kw):
    return {"home_team": "France", "away_team": "Espagne", "title": "France - Espagne", "content": CONTENT} | kw


def test_rule_ok():
    assert tools.check_publish_report(args()) == []


def test_rule_teams_must_exist():
    errors = tools.check_publish_report(args(away_team="Atlantide"))
    assert len(errors) == 1 and "Équipe inconnue" in errors[0]


def test_rule_teams_must_differ():
    assert tools.check_publish_report(args(away_team="france")) == [
        "Les deux équipes de l'affiche doivent être différentes."]


def test_rule_needs_a_number():
    content = CONTENT.replace("2-1", "").translate(str.maketrans("", "", "0123456789")) + " " * 50
    assert tools.check_publish_report(args(content=content)) == [
        "Le rapport doit citer au moins un chiffre issu des données."]


def test_rule_min_length():
    assert "Rapport trop court" in " ".join(tools.check_publish_report(args(content="Espagne 2-1")))


def test_rule_single_report_per_fixture_and_english_slug():
    out = tools.publish_report(**args())
    assert out["path"].endswith("reports/france-vs-spain.json")
    assert json.loads(Path(out["path"]).read_text(encoding="utf-8"))["away_team"] == "Spain"
    assert tools.check_publish_report(args(away_team="Spain")) == ["Un rapport est déjà publié pour cette affiche."]
