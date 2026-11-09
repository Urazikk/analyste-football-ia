"""Tests du niveau 1 sans réseau : faux encodeur pour l'index, faux LLM pour la réponse."""
from __future__ import annotations

import numpy as np

from src import config, rag
from src.llm import LLMResponse

WORDS = ["hors-jeu", "touche", "ballon", "penalty"]


class FakeEncoder:
    """Un axe par mot clé : le cosinus compte les mots partagés."""

    def encode(self, texts, normalize_embeddings=True, **_):
        v = np.array([[t.lower().count(w) for w in WORDS] + [0.01] for t in texts], dtype=float)
        return v / np.linalg.norm(v, axis=1, keepdims=True)


CHUNKS = [
    rag.Chunk("a#hors-jeu", "a", "A > Hors-jeu", "", "Le hors-jeu ne s'applique pas sur une touche."),
    rag.Chunk("b#ballon", "b", "B > Ballon", "", "Le ballon pèse entre 410 et 450 g."),
    rag.Chunk("c#penalty", "c", "C > Penalty", "", "Le penalty se tire à 11 m."),
]


def make_index(monkeypatch) -> rag.Index:
    monkeypatch.setitem(rag._models, "fake", FakeEncoder())
    return rag.Index(CHUNKS, "fake", cache_dir=None)


def test_tokenize():
    assert rag.tokenize("Les Rentrées de touche à 9,15 m") == ["rentree", "touche", "9,15"]


def test_search_modes(monkeypatch):
    index = make_index(monkeypatch)
    for mode in ("dense", "bm25", "hybrid"):
        assert index.search("poids du ballon", 1, mode)[0][0].id == "b#ballon"
    assert index.search("hors-jeu touche", 3, "hybrid")[0][0].id == "a#hors-jeu"


def test_cited_ids_keeps_only_retrieved():
    text = "Oui [a#hors-jeu], voir aussi [inventé#x] et [a#hors-jeu]."
    assert rag.cited_ids(text, ["a#hors-jeu", "b#ballon"]) == ["a#hors-jeu"]
    assert rag.cited_ids("Oui【b#ballon】.", ["b#ballon"]) == ["b#ballon"]


def _patch(monkeypatch, index: rag.Index) -> list:
    monkeypatch.setattr(rag, "_index", index)
    calls: list = []

    def llm(messages, tools=None):
        calls.append(messages)
        return LLMResponse("Entre 410 et 450 g [b#ballon].", tokens_in=100, tokens_out=10)

    return calls, llm


def test_answer_cites_sources(monkeypatch):
    calls, llm = _patch(monkeypatch, make_index(monkeypatch))
    res = rag.answer("poids du ballon", llm=llm, k=2, mode="hybrid", threshold=0.0)
    assert res.sources == ["b#ballon"] and res.retrieved[0] == "b#ballon"
    assert "[b#ballon]" in calls[0][1]["content"]
    assert res.tokens == 110 and not res.abstained


def test_answer_abstains_below_threshold_without_llm(monkeypatch):
    calls, llm = _patch(monkeypatch, make_index(monkeypatch))
    res = rag.answer("salaire de l'arbitre", llm=llm, threshold=0.5)
    assert res.abstained and res.stop_reason == "below_threshold"
    assert calls == [] and res.tokens == 0


def test_answer_model_abstention(monkeypatch):
    monkeypatch.setattr(rag, "_index", make_index(monkeypatch))
    llm = lambda messages, tools=None: LLMResponse(f"{config.ABSTAIN_MARK} Pas dans les extraits [b#ballon].")  # noqa: E731
    res = rag.answer("poids du ballon", llm=llm, threshold=0.0)
    assert res.abstained and res.sources == []
