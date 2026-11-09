"""Juge LLM de fidélité : chaque affirmation de la réponse est-elle soutenue par les extraits cités ?

Calibré contre des annotations humaines (scripts/calibrate_judge.py). Le juge est d'une autre
famille que le modèle évalué (config.JUDGE_MODEL) et tourne à température 0.
"""
from __future__ import annotations

import json
import re
from typing import Any

from src import config

PROMPT = """Tu es un vérificateur strict. On te donne une question, une réponse et les extraits cités par la réponse.
Une réponse est fidèle si chacune de ses affirmations factuelles est soutenue par au moins un extrait.
Une affirmation vraie mais absente des extraits n'est PAS soutenue. Ignore le style et la mise en forme.
Réponds uniquement par un objet JSON : {"fidele": true ou false, "non_soutenues": ["affirmation", ...]}"""


def parse_verdict(text: str) -> dict[str, Any] | None:
    """Premier objet JSON du texte contenant la clé « fidele », sinon None."""
    for m in re.finditer(r"\{.*?\}", text, re.S):
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("fidele"), bool):
            return data
    return None


def judge_faithfulness(question: str, answer: str, passages: dict[str, str], llm=None) -> dict[str, Any]:
    """Verdict {faithful, unsupported, tokens}. faithful vaut None si le verdict est illisible ou sans extrait."""
    from src.llm import chat

    if not passages:
        return {"faithful": None, "unsupported": [], "tokens": 0}
    llm = llm or (lambda messages: chat(messages, model=config.JUDGE_MODEL, max_tokens=512))
    extraits = "\n\n".join(f"[{cid}]\n{text}" for cid, text in passages.items())
    resp = llm([{"role": "system", "content": PROMPT},
                {"role": "user", "content": f"Question : {question}\n\nRéponse :\n{answer}\n\nExtraits cités :\n\n{extraits}"}])
    verdict = parse_verdict(resp.text)
    return {"faithful": verdict["fidele"] if verdict else None,
            "unsupported": verdict.get("non_soutenues", []) if verdict else [],
            "tokens": resp.tokens_in + resp.tokens_out}


def passages_for(sources: list[str]) -> dict[str, str]:
    """Texte des morceaux cités, depuis l'index du RAG."""
    from src import rag

    by_id = {c.id: c.text for c in rag.get_index().chunks}
    return {s: by_id[s] for s in sources if s in by_id}
