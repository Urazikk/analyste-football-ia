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
    # minimums du sujet (20, 5, 10, 5) ; le plan ambitieux vise 80 cas (docs/plan.md, axe A)
    counts = (types.count("doc"), types.count("absent"), types.count("task"), types.count("ambiguous"))
    assert all(n >= m for n, m in zip(counts, (20, 5, 10, 5))), counts


def test_task_01_last_match_shots_france_spain():
    france = tools.list_matches("France", limit=1)[0]
    spain = tools.list_matches("Espagne", limit=1)[0]
    assert (france["stage"], spain["stage"]) == ("Semi-finals", "Final")
    shots = (tools.team_stats(france["match_id"], "France")["shots"], tools.team_stats(spain["match_id"], "Espagne")["shots"])
    assert shots == (9, 16) and [["9"], ["16"]] == numbers("task-01")[1:]


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


# task-11 à task-20 (plan, A2) : chaque chiffre attendu recalculé avec les outils de l'agent

def h2h(a: str, b: str, stage: str | None = None) -> list[dict]:
    games = tools.head_to_head(a, b)["matches"]
    return [g for g in games if stage is None or g["stage"] == stage]


def expects(case_id: str, i: int, value: str) -> bool:
    return value in numbers(case_id)[i]


def test_task_11_all_argentina_france_meetings():
    assert [g["score"] for g in h2h("Argentine", "France")] == ["3-3", "3-4"]
    assert expects("task-11", 0, "3-3") and expects("task-11", 1, "3-4")


def test_task_12_france_xg_last_five():
    xg = tools.team_form("France")["summary"]["xg_for"]
    assert xg == 6.29 and expects("task-12", 0, "6,29") and expects("task-12", 0, "6,3")


def test_task_13_euro_2020_final():
    (g,) = h2h("Angleterre", "Italie", "Final")
    assert (g["date"][:4], g["score"], g["penalties"]) == ("2021", "1-1", "2-3")
    assert expects("task-13", 0, "1-1") and expects("task-13", 1, "2-3")


def test_task_14_world_cup_2018_semi():
    (g,) = h2h("Croatie", "Angleterre", "Semi-finals")
    assert g["date"][:4] == "2018" and expects("task-14", 0, g["score"])


def test_task_15_brazil_shots_2018_quarter():
    (g,) = h2h("Brésil", "Belgique", "Quarter-finals")
    assert str(tools.team_stats(g["match_id"], "Brazil")["shots"]) in numbers("task-15")[1]


def test_task_16_france_portugal_shootout():
    (g,) = h2h("France", "Portugal", "Quarter-finals")
    assert g["penalties"] == "5-3" and expects("task-16", 0, "5-3")


def test_task_18_unknown_team_blocked():
    with pytest.raises(ValueError):
        data.resolve_team("Chine")


def test_task_19_netherlands_argentina_2022():
    (g,) = h2h("Pays-Bas", "Argentine", "Quarter-finals")
    assert (g["score"], g["penalties"]) == ("2-2", "3-4")
    assert expects("task-19", 0, "2-2") and expects("task-19", 1, "3-4")


def test_task_20_morocco_xg_conceded():
    xg = tools.team_form("Maroc")["summary"]["xg_against"]
    assert xg == 5.18 and expects("task-20", 0, "5,18") and expects("task-20", 0, "5,2")
