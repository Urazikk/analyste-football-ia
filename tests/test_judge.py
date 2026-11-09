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
