"""Réponses attendues des tâches multi-étapes, recalculées depuis les données en cache (sans LLM).

Si les données ou un outil changent, ces tests disent quel cas du jeu de test devient faux.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import data, metrics, tools

ROOT = Path(__file__).resolve().parent.parent
CASES = {c["id"]: c for c in map(json.loads, (ROOT / "tests.jsonl").read_text(encoding="utf-8").splitlines())}
pytestmark = pytest.mark.skipif(not (data.cache_dir() / "matches").exists(),
                                reason="cache StatsBomb vide (python scripts/fetch_statsbomb.py)")


def find(team: str, opponent: str, stage: str) -> int:
    """Identifiant du match entre deux équipes à un tour donné, via list_matches comme l'agent."""
    opp = data.resolve_team(opponent)
    ms = [m for m in tools.list_matches(team, limit=20)
          if opp in (m["home_team"], m["away_team"]) and m["stage"] == stage]
    assert len(ms) == 1, (team, opponent, stage)
    return ms[0]["match_id"]


def numbers(case_id: str) -> list[list[str]]:
    return CASES[case_id]["expected"]["checks"][0]["must_contain"]


def test_counts_by_type():
    types = [c["type"] for c in CASES.values()]
    assert (types.count("doc"), types.count("absent"), types.count("task"), types.count("ambiguous")) == (20, 5, 10, 5)


def test_task_02_argentina_france_final():
    m = tools.list_matches("Argentine", limit=20)
    last = next(x for x in m if "France" in (x["home_team"], x["away_team"]))
    assert (last["stage"], last["score"]) == ("Final", "3-3") and "3-3" in numbers("task-02")[0]


def test_task_03_spain_shots_on_target_final():
    mid = find("Espagne", "Angleterre", "Final")
    assert str(tools.team_stats(mid, "Spain")["shots_on_target"]) in numbers("task-03")[1]


def test_task_04_morocco_last_match():
    last = tools.list_matches("Maroc", limit=1)[0]
    assert str(tools.team_stats(last["match_id"], "Morocco")["shots"]) in numbers("task-04")[1]


def test_task_08_colombia_uruguay_semi():
    m = tools.list_matches("Colombie", limit=20)
    semi = next(x for x in m if x["stage"] == "Semi-finals")
    assert {semi["home_team"], semi["away_team"]} == {"Colombia", "Uruguay"}
    assert semi["score"] in numbers("task-08")[0]


def test_task_09_netherlands_semi():
    mid = find("Pays-Bas", "Angleterre", "Semi-finals")
    assert str(tools.team_stats(mid, "Netherlands")["shots"]) in numbers("task-09")[1]


def test_task_10_germany_spain_quarter():
    mid = find("Allemagne", "Espagne", "Quarter-finals")
    assert [str(tools.team_stats(mid, t)["shots"]) for t in ("Germany", "Spain")] == [g[0] for g in numbers("task-10")]


def test_no_report_tasks_are_blocked_by_rules():
    content = "x" * 190 + " 2-1 et 9 tirs"
    assert tools.check_publish_report({"home_team": "France", "away_team": "Atlantide", "title": "t", "content": content})
    assert tools.check_publish_report({"home_team": "Brésil", "away_team": "Brazil", "title": "t", "content": content})


@pytest.mark.parametrize("cid", [c for c in CASES if CASES[c]["type"] == "task"])
def test_report_names_match_tool_slug(cid):
    for check in CASES[cid]["expected"]["checks"]:
        if check["kind"] == "report_published":
            home, away = check["report"].split("-vs-")
            assert tools.report_path(home, away).stem == check["report"]


def test_check_state_synonym_groups(tmp_path):
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "a-vs-b.json").write_text(json.dumps({"content": "Finale : 3 à 3, tirs cadrés."}))
    ok = [{"kind": "report_published", "report": "a-vs-b", "must_contain": [["3-3", "3 à 3"], "cadres"]}]
    ko = [{"kind": "report_published", "report": "a-vs-b", "must_contain": [["2-2"]]}]
    assert metrics.check_state(ok, tmp_path) and not metrics.check_state(ko, tmp_path)
