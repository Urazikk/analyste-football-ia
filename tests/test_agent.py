"""Tests de la boucle de l'agent avec un faux LLM (sans API)."""
from __future__ import annotations

import json

from src import agent
from src.llm import LLMResponse
from src.tools import Tool


def scripted(responses: list[LLMResponse]):
    it = iter(responses)
    return lambda messages, tools=None: next(it)


def call(name: str, **args) -> dict:
    return {"id": f"c-{name}", "name": name, "arguments": json.dumps(args)}


def boom(**_):
    raise RuntimeError("panne")


REG = {
    "boom": Tool("boom", "", {"type": "object", "properties": {}}, "read", boom),
    "act": Tool("act", "", {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"]},
                "irreversible", lambda x: {"done": x}),
}


def test_error_is_returned_to_model():
    llm = scripted([LLMResponse("", [call("boom")]), LLMResponse("fini")])
    res = agent.run("q", llm=llm, registry=REG)
    assert res.answer == "fini"
    assert '"ok": false' in res.tool_calls[0]["output"]


def test_max_steps():
    llm = lambda messages, tools=None: LLMResponse("", [call("boom")])  # noqa: E731
    res = agent.run("q", llm=llm, registry=REG, max_steps=3)
    assert res.stop_reason == "max_steps" and res.steps == 3


def test_irreversible_waits_without_confirm():
    llm = scripted([LLMResponse("", [call("act", x=1)])])
    res = agent.run("q", llm=llm, registry=REG)
    assert res.stop_reason == "awaiting_confirmation"
    assert res.pending_action == {"name": "act", "arguments": {"x": 1}}


def test_irreversible_refused():
    llm = scripted([LLMResponse("", [call("act", x=1)]), LLMResponse("ok")])
    res = agent.run("q", llm=llm, registry=REG, confirm=lambda n, a: False)
    assert "refusée" in res.tool_calls[0]["output"]


def test_invalid_arguments():
    llm = scripted([LLMResponse("", [call("act", x="pas un entier")]), LLMResponse("ok")])
    res = agent.run("q", llm=llm, registry=REG, confirm=lambda n, a: True)
    assert "Arguments invalides" in res.tool_calls[0]["output"]


def test_search_rules_sources_and_retrieved(monkeypatch):
    from src import rag, tools

    hits = [(rag.Chunk("ifab-loi-03#1", "ifab-loi-03", "Loi 3", "", "onze joueurs"), 0.9),
            (rag.Chunk("wiki-x#a", "wiki-x", "X", "", "autre"), 0.8)]
    monkeypatch.setattr(rag, "search", lambda q, k=5, mode=None: hits[:k])
    llm = scripted([LLMResponse("", [call("search_rules", query="nombre de joueurs")]),
                    LLMResponse("Onze joueurs [ifab-loi-03#1], pas [inventé#z].")])
    res = agent.run("q", llm=llm, registry=tools.REGISTRY)
    assert res.retrieved == ["ifab-loi-03#1", "wiki-x#a"]
    assert res.sources == ["ifab-loi-03#1"]
