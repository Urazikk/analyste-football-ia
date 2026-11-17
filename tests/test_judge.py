"""Juge de fidélité avec un faux LLM."""
from __future__ import annotations

from src import judge
from src.llm import LLMResponse


def test_parse_verdict():
    assert judge.parse_verdict('Voici : {"fidele": false, "non_soutenues": ["x"]} fin') == {"fidele": False, "non_soutenues": ["x"]}
    assert judge.parse_verdict("pas de json") is None
    assert judge.parse_verdict('{"autre": 1}') is None


def test_judge_sends_passages_and_reads_verdict():
    seen = []

    def llm(messages):
        seen.append(messages[1]["content"])
        return LLMResponse('{"fidele": true, "non_soutenues": []}', tokens_in=50, tokens_out=5)

    v = judge.judge_faithfulness("q", "Onze [a#b].", {"a#b": "onze joueurs"}, llm=llm)
    assert v == {"faithful": True, "unsupported": [], "tokens": 55}
    assert "[a#b]\nonze joueurs" in seen[0]


def test_judge_without_passages_is_undefined():
    assert judge.judge_faithfulness("q", "réponse", {}, llm=None)["faithful"] is None


def test_kappa():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import calibrate_judge as cj

    assert cj.kappa([(True, True), (False, False)]) == 1.0
    assert cj.kappa([(True, False), (False, True)]) < 0
    assert cj.kappa([(True, True), (True, True)]) is None


def test_second_annotator_does_not_touch_simon(monkeypatch, tmp_path):
    import json
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    import calibrate_judge as cj

    f = tmp_path / "a.jsonl"
    f.write_text("".join(json.dumps({"id": f"doc-{i}", "question": "q", "answer": "a", "sources": [], "humain": i % 2 == 0}) + "\n"
                         for i in range(4)), encoding="utf-8")
    monkeypatch.setattr(cj, "ANNOT", f)
    monkeypatch.setattr(cj, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(cj.judge, "passages_for", lambda sources: {})  # pas d'index ni de téléchargement
    answers = iter(["o", "", "n", "", "o", "", "n", ""])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    cj.annotate("gautier")
    rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()]
    assert [r["humain"] for r in rows] == [True, False, True, False]
    assert all(isinstance(r["humain_gautier"], bool) for r in rows)
    assert "4 réponses annotées par les deux" in cj.agreement("gautier")


def test_judge_never_receives_the_main_key(monkeypatch):
    import pytest

    from src import config, llm

    monkeypatch.setattr(config, "LLM_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(config, "LLM_API_KEY", "sk-cle-du-modele")
    monkeypatch.setattr(llm, "_clients", {})
    with pytest.raises(RuntimeError, match="JUDGE_API_KEY"):
        llm._get_client("https://api.groq.com/openai/v1", "")
    assert llm._get_client("https://api.groq.com/openai/v1", "gsk-juge").api_key == "gsk-juge"
    assert llm._get_client(None, "").api_key == "sk-cle-du-modele"
