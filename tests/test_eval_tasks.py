"""Chaîne d'évaluation des tâches de bout en bout, sans API : un faux LLM joue les appels qu'un bon agent ferait.

Vérifie que les tâches sont faisables avec les outils réels, que check_state, les règles métier et le
diagnostic des chiffres non soutenus marchent dans eval.run_case, et que eval.py ne perd pas de résultats.
"""
from __future__ import annotations

import json

import pytest

import eval as ev
from src import agent, data
from src.llm import LLMResponse

pytestmark = pytest.mark.skipif(not (data.cache_dir() / "events" / "3943043.pkl").exists(),
                                reason="cache StatsBomb vide (python scripts/fetch_statsbomb.py)")
CASES = {c["id"]: c for c in ev.load_tests()}
FILLER = " Le rapport s'appuie sur les données StatsBomb des matchs disponibles pour les deux sélections."


def call(i: int, name: str, **args) -> dict:
    return {"id": f"c{i}", "name": name, "arguments": json.dumps(args, ensure_ascii=False)}


def oracle(*steps: list[dict] | str):
    """Faux LLM : chaque étape est une liste d'appels d'outils, ou le texte final."""
    it = iter(steps)

    def llm(messages, tools=None):
        step = next(it)
        return LLMResponse(step) if isinstance(step, str) else LLMResponse("", step, tokens_in=100, tokens_out=20)
    return llm


def run(case_id: str, llm) -> dict:
    fn = lambda q: agent.run(q, llm=llm, confirm=lambda name, args: True)  # noqa: E731
    return ev.run_case(fn, CASES[case_id], level=2)


def publish(i: int, home: str, away: str, content: str) -> list[dict]:
    return [call(i, "publish_report", home_team=home, away_team=away, title=f"{home} - {away}",
                 content=content + FILLER * 2)]


def test_task_03_solved_by_tools():
    row = run("task-03", oracle(
        [call(1, "list_matches", team="Espagne", limit=1)],
        [call(2, "team_stats", match_id=3943043, team="Espagne")],
        publish(3, "Angleterre", "Espagne", "En finale de l'Euro 2024, l'Espagne a cadré 6 tirs sur 16 (xG 1,79)."),
        "Rapport publié."))
    assert row["correct"] and row["unsupported_numbers"] == []
    assert [c["name"] for c in row["tool_calls"]] == ["list_matches", "team_stats", "publish_report"]


def test_invented_number_is_flagged_but_task_still_checked_on_state():
    row = run("task-03", oracle(
        [call(1, "team_stats", match_id=3943043, team="Spain")],
        publish(2, "England", "Spain", "L'Espagne a cadré 6 tirs et couru 112 kilomètres."),
        "Rapport publié."))
    assert row["correct"] and row["unsupported_numbers"] == [112.0]


def test_task_10_two_teams():
    row = run("task-10", oracle(
        [call(1, "list_matches", team="Allemagne", limit=3)],
        [call(2, "team_stats", match_id=3942226, team="Germany"), call(3, "team_stats", match_id=3942226, team="Spain")],
        publish(4, "Allemagne", "Espagne", "En quart de finale, l'Allemagne a tiré 23 fois et l'Espagne 19 fois."),
        "Rapport publié."))
    assert row["correct"]


@pytest.mark.parametrize("case_id,home,away", [("task-05", "France", "Atlantide"), ("task-07", "Brésil", "Brazil")])
def test_no_report_tasks_blocked_by_rules(case_id, home, away):
    row = run(case_id, oracle(publish(1, home, away, "Score 2-1."), "[PRECISION] Affiche impossible."))
    assert row["correct"] and row["unsupported_numbers"] is None
    assert "Règle métier" in row["tool_calls"][0]["output"]


def test_task_06_analysis_without_publication():
    row = run("task-06", oracle([call(1, "plot_shots", match_id=3943077, team="Argentine")],
                                "L'Argentine a tiré 11 fois, 1 but."))
    assert row["correct"] and row["unsupported_numbers"] is None


def test_task_fails_when_report_lacks_expected_number():
    row = run("task-09", oracle(publish(1, "Pays-Bas", "Angleterre", "Les Pays-Bas ont perdu 1-2."), "fait"))
    assert row["correct"] is False


def test_write_rows_keeps_other_cases_and_models(tmp_path):
    raw = tmp_path / "raw.jsonl"
    old = [{"id": "doc-01", "trial": 0, "model": "m1"}, {"id": "task-01", "trial": 0, "model": "m1", "v": 1}]
    ev._write_rows(raw, old)
    ev._write_rows(raw, [{"id": "task-01", "trial": 0, "model": "m1", "v": 2},
                         {"id": "task-01", "trial": 0, "model": "m2"}])
    rows = ev._read_rows(raw)
    assert {(r["id"], r["model"], r.get("v")) for r in rows} == {
        ("doc-01", "m1", None), ("task-01", "m1", 2), ("task-01", "m2", None)}


def test_bench_table_by_model(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import bench_models

    base = {"type": "task", "tokens_in": 1000, "tokens_out": 100, "latency_s": 2.0, "unsupported_numbers": []}
    rows = [base | {"id": "task-01", "trial": t, "model": m, "correct": ok}
            for m, oks in (("a", [True, True, True]), ("b", [True, False, True])) for t, ok in enumerate(oks)]
    raw = tmp_path / "raw.jsonl"
    ev._write_rows(raw, rows)
    table = bench_models.main(raw, tmp_path / "bench.md")
    assert "| a | 1 tâches, 3 essais | 1.00 | 1.00 |" in table and "| b | 1 tâches, 3 essais | 1.00 | 0.00 |" in table


def test_unicode_dashes_count_as_hyphen():
    """Le modèle écrit « 3‑3 » (U+2011) ou « 3 – 3 » (U+2013) : même score que « 3-3 » (mesures du 11 nov.)."""
    from src import metrics

    groups = [["3-3", "3 - 3", "3 à 3"]]
    for text in ("finale 3‑3", "Argentine 3 – 3 France", "3−3", "3-3"):
        assert metrics.keywords_match(text, groups), text
    assert not metrics.keywords_match("13‑3", [["3-3"]])  # nombre entier toujours exigé


def test_rescore_rebuilds_state_from_recorded_publish():
    """scripts/rescore.py rejoue check_state à partir des appels publish_report enregistrés."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import rescore

    case = CASES["task-02"]
    pub = {"name": "publish_report", "output": json.dumps({"ok": True, "result": {"published": True}}),
           "arguments": json.dumps({"home_team": "Argentine", "away_team": "France", "title": "t",
                                    "content": "Dernière confrontation : 3‑3, tab 4-2."})}
    refused = pub | {"output": json.dumps({"ok": False, "error": "Action refusée par l'utilisateur."})}
    assert rescore.rescore_row({"id": "task-02", "type": "task", "tool_calls": [pub]}, case) is True
    assert rescore.rescore_row({"id": "task-02", "type": "task", "tool_calls": [refused]}, case) is False
    no_rep = CASES["task-05"]
    assert rescore.rescore_row({"id": "task-05", "type": "task", "tool_calls": []}, no_rep) is True
    assert rescore.rescore_row({"id": "x", "type": "task", "error": "429", "tool_calls": []}, case) is None
