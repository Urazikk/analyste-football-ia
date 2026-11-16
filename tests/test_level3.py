"""Tests du niveau 3 (planification) avec un faux LLM, sans API."""
from __future__ import annotations

import json
from pathlib import Path

from src import config, level3
from src.llm import LLMResponse
from src.tools import Tool

REG = {
    "lire": Tool("lire", "Lit une valeur.", {"type": "object", "properties": {"x": {"type": "integer"}},
                                             "required": ["x"]}, "read", lambda x: {"valeur": x}),
    "publish_report": Tool("publish_report", "Publie.",
                           {"type": "object", "properties": {"home_team": {"type": "string"},
                                                             "away_team": {"type": "string"}}},
                           "irreversible", lambda home_team, away_team: {"published": True}),
}


def plan(decision: str, message: str = "", steps: list | None = None, publish: dict | None = None) -> LLMResponse:
    return LLMResponse(json.dumps({"decision": decision, "message": message, "steps": steps or [],
                                   "publish": publish}, ensure_ascii=False), tokens_in=50, tokens_out=10)


def call(name: str, **args) -> LLMResponse:
    return LLMResponse("", [{"id": f"c-{name}", "name": name, "arguments": json.dumps(args)}],
                       tokens_in=100, tokens_out=20)


def scripted(*responses: LLMResponse):
    it, seen = iter(responses), []

    def llm(messages, tools=None):
        seen.append((messages, tools))
        return next(it)
    llm.seen = seen
    return llm


def test_parse_plan():
    assert level3.parse_plan('Voici : {"decision": "clarify", "message": "Quel match ?"}')["message"] == "Quel match ?"
    assert level3.parse_plan("pas de json") is None
    assert level3.parse_plan('{"decision": "autre"}') is None
    p = level3.parse_plan('{"decision": "execute", "steps": [{"tool": "lire", "args": {"x": 1}}, "bruit"], '
                          '"publish": {"home_team": "France"}}')
    assert p["steps"] == [{"tool": "lire", "args": {"x": 1}}] and p["publish"] is None


def test_clarify_answers_without_any_tool():
    llm = scripted(plan("clarify", "De quel match parlez-vous ?"))
    res = level3.run("Quel est le score ?", llm=llm, registry=REG)
    assert res.clarified and res.answer == f"{config.CLARIFY_MARK} De quel match parlez-vous ?"
    assert res.tool_calls == [] and res.steps == 1 and res.level == 3
    assert llm.seen[0][1] is None  # le plan est demandé sans outils


def test_refuse_marks_the_answer_once():
    llm = scripted(plan("refuse", f"{config.REFUSE_MARK} Ce n'est pas du football."))
    res = level3.run("Une recette ?", llm=llm, registry=REG)
    assert res.refused and res.answer.count(config.REFUSE_MARK) == 1 and not res.tool_calls


def test_planned_reads_run_before_the_loop():
    llm = scripted(plan("execute", steps=[{"tool": "lire", "args": {"x": 7}}]), LLMResponse("La valeur est 7."))
    res = level3.run("Lis 7.", llm=llm, registry=REG)
    assert res.answer == "La valeur est 7." and res.steps == 2
    assert [c["name"] for c in res.tool_calls] == ["lire"] and '"valeur": 7' in res.tool_calls[0]["output"]
    loop_messages = llm.seen[1][0]
    assert any(m["role"] == "tool" and '"valeur": 7' in m["content"] for m in loop_messages)
    assert loop_messages[1] == {"role": "user", "content": "Lis 7."}


def test_unplanned_publication_is_blocked_by_code():
    llm = scripted(plan("execute"), call("publish_report", home_team="France", away_team="Espagne"),
                   LLMResponse("Je ne publie pas."))
    res = level3.run("Analyse France - Espagne.", llm=llm, registry=REG, confirm=lambda n, a: True)
    assert "Publication non prévue" in res.tool_calls[0]["output"] and res.pending_action is None


def test_publication_only_for_the_planned_fixture():
    wanted = {"home_team": "France", "away_team": "Espagne"}
    llm = scripted(plan("execute", publish=wanted), call("publish_report", home_team="Brésil", away_team="Chili"),
                   call("publish_report", home_team="Espagne", away_team="France"), LLMResponse("Publié."))
    res = level3.run("Publie France - Espagne.", llm=llm, registry=REG, confirm=lambda n, a: True)
    assert "doit être celle demandée" in res.tool_calls[0]["output"]
    assert '"published": true' in res.tool_calls[1]["output"]


def test_planned_publication_waits_for_confirmation():
    llm = scripted(plan("execute", publish={"home_team": "France", "away_team": "Espagne"}),
                   call("publish_report", home_team="France", away_team="Espagne"))
    res = level3.run("Publie France - Espagne.", llm=llm, registry=REG)
    assert res.stop_reason == "awaiting_confirmation" and res.pending_action["name"] == "publish_report"


def test_irreversible_step_in_plan_is_never_run_by_code():
    step = {"tool": "publish_report", "args": {"home_team": "France", "away_team": "Espagne"}}
    llm = scripted(plan("execute", steps=[step]), LLMResponse("Rien publié."))
    res = level3.run("Analyse.", llm=llm, registry=REG, confirm=lambda n, a: True)
    assert res.tool_calls == []


def test_unreadable_plan_falls_back_to_level_2():
    llm = scripted(LLMResponse("je ne sais pas"), call("lire", x=1), LLMResponse("fini"))
    res = level3.run("Lis 1.", llm=llm, registry=REG)
    assert res.answer == "fini" and res.steps == 3 and res.level == 3


def test_one_trace_with_plan_and_loop():
    llm = scripted(plan("execute", steps=[{"tool": "lire", "args": {"x": 1}}]), LLMResponse("fini"))
    res = level3.run("Lis 1.", llm=llm, registry=REG)
    events = [json.loads(l)["event"] for l in Path(res.trace_path).read_text(encoding="utf-8").splitlines()]
    assert events[:3] == ["start", "plan", "tool"] and events[-1] == "end" and "llm" in events
