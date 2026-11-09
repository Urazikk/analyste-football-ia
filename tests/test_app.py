"""Interface Streamlit testée sans LLM : faux niveau 1, faux index."""
from __future__ import annotations

from types import SimpleNamespace

from streamlit.testing.v1 import AppTest

from src import config, rag
from src.result import Result


def test_app_shows_answer_sources_and_cost(monkeypatch):
    chunk = rag.Chunk("ifab-loi-03#1", "ifab-loi-03", "Loi 3 : Joueurs > 1. Nombre", "IFAB", "onze joueurs au maximum")
    monkeypatch.setattr(rag, "get_index", lambda: SimpleNamespace(chunks=[chunk]))
    monkeypatch.setattr(rag, "answer", lambda q: Result(
        level=1, answer="Onze [ifab-loi-03#1].", sources=["ifab-loi-03#1"], retrieved=["ifab-loi-03#1", "wiki-x#a"],
        tokens_in=1000, tokens_out=100, latency_s=1.0, steps=1))
    at = AppTest.from_file("../src/app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value(1).run()
    at.text_area[0].input("Combien de joueurs ?").run()
    at.button[0].click().run()
    assert not at.exception
    assert "Onze" in at.markdown[0].value
    assert any("ifab-loi-03#1" in e.label for e in at.expander)
    cost = f"{config.cost_usd(1000, 100):.5f} $"
    assert any(m.value == cost for m in at.metric)
    assert any("non cités : wiki-x#a" in c.value for c in at.caption)


def test_app_shows_abstention(monkeypatch):
    monkeypatch.setattr(rag, "get_index", lambda: SimpleNamespace(chunks=[]))
    monkeypatch.setattr(rag, "answer", lambda q: Result(level=1, answer="[ABSTENTION] rien", abstained=True))
    at = AppTest.from_file("../src/app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value(1).run()
    at.text_area[0].input("Salaire de l'arbitre ?").run()
    at.button[0].click().run()
    assert not at.exception
    assert any("Abstention" in i.value for i in at.info)
