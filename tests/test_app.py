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


def test_app_validation_publishes_traces_and_shows_plot(monkeypatch, tmp_path):
    import json

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from src import agent, tools
    from src.tracing import Tracer

    png = tmp_path / "shots.png"
    plt.figure(figsize=(1, 1)).savefig(png)
    tracer = Tracer(level=2, question="q")
    pending = {"name": "publish_report", "arguments": {"home_team": "France", "away_team": "Spain",
                                                       "title": "t", "content": "c"}}
    monkeypatch.setattr(tools, "check_publish_report", lambda a: [])
    monkeypatch.setitem(tools.REGISTRY, "publish_report", tools.Tool(
        "publish_report", "", {}, "irreversible", tools.publish_report, tools.check_publish_report))
    plot_out = json.dumps({"ok": True, "result": {"path": str(png), "shots": 9, "goals": 1}})
    monkeypatch.setattr(agent, "answer", lambda q: Result(
        level=2, answer="Rapport prêt.", pending_action=pending, stop_reason="awaiting_confirmation",
        tool_calls=[{"name": "plot_shots", "arguments": "{}", "output": plot_out}], trace_path=str(tracer.path)))
    at = AppTest.from_file("../src/app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value(2).run()
    at.text_area[0].input("Publie le rapport France - Espagne").run()
    at.button[0].click().run()
    assert not at.exception and sum(type(e).__name__ == "Image" for e in at.main) == 1
    at.button[1].click().run()  # Valider
    assert not at.exception
    assert any("Rapport publié" in s.value for s in at.success)
    assert tools.report_path("France", "Spain").exists()
    events = [json.loads(line)["event"] for line in tracer.path.read_text(encoding="utf-8").splitlines()]
    assert events[-2:] == ["confirmation", "tool"]


def test_compare_tab_runs_all_levels(monkeypatch):
    from src import agent, level3, llm

    monkeypatch.setattr(rag, "get_index", lambda: SimpleNamespace(chunks=[]))
    for mod, lv in ((llm, 0), (rag, 1), (agent, 2), (level3, 3)):
        monkeypatch.setattr(mod, "answer", lambda q, lv=lv: Result(level=lv, answer=f"réponse {lv}", tokens_in=10 * (lv + 1)))
    at = AppTest.from_file("../src/app.py", default_timeout=30).run()
    at.text_area(key="cmp_q").input("Combien de joueurs ?").run()
    at.button(key="cmp_go").click().run()
    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert all(f"réponse {lv}" in texts for lv in (0, 1, 2, 3))


def test_reports_tab_offers_pdf(monkeypatch):
    import json

    p = config.state_dir() / "reports" / "france-vs-spain.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"home_team": "France", "away_team": "Spain", "title": "Avant-match",
                             "content": "France : 9 tirs."}), encoding="utf-8")
    at = AppTest.from_file("../src/app.py", default_timeout=30).run()
    assert not at.exception
    assert any("Avant-match" in e.label for e in at.expander)
    assert p.with_suffix(".pdf").exists()


def test_catalog_questions_and_match_prompts():
    from src import catalog

    assert all(lv in (0, 1, 2, 3) for _, qs in catalog.QUESTIONS for _, lv, _ in qs)
    m = {"match_id": 1, "date": "2021-07-11", "competition": "Europe - UEFA Euro", "stage": "Final",
         "home_team": "Italy", "away_team": "England", "score": "1-1"}
    assert catalog.competition(m) == "Euro 2020"
    m = {**m, "home_fr": "Italie", "away_fr": "Angleterre", "competition_fr": "Euro 2020", "stage_fr": "finale"}
    prompts = catalog.match_questions(m)
    assert len(prompts) == 4 and all("Italie - Angleterre" in q for _, q, _ in prompts)

