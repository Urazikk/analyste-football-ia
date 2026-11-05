"""Client LLM (API compatible OpenAI) et niveau 0 : LLM seul."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from src import config
from src.result import Result
from src.tracing import Tracer


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)  # {"id", "name", "arguments"(str)}
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY or "none")
    return _client


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 0.0,
    max_tokens: int = 1024,
) -> LLMResponse:
    """Un appel au modèle. Les outils sont au format OpenAI (type=function)."""
    kwargs: dict[str, Any] = {"model": config.LLM_MODEL, "messages": messages,
                              "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        kwargs["tools"] = tools
    t0 = time.perf_counter()
    resp = _get_client().chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    calls = [{"id": c.id, "name": c.function.name, "arguments": c.function.arguments}
             for c in (msg.tool_calls or [])]
    usage = resp.usage
    return LLMResponse(
        text=msg.content or "",
        tool_calls=calls,
        tokens_in=usage.prompt_tokens if usage else 0,
        tokens_out=usage.completion_tokens if usage else 0,
        latency_s=time.perf_counter() - t0,
    )


def parse_marks(text: str) -> dict[str, bool]:
    return {
        "abstained": config.ABSTAIN_MARK in text,
        "clarified": config.CLARIFY_MARK in text,
        "refused": config.REFUSE_MARK in text,
    }


SYSTEM_PROMPT = f"""Tu es un analyste de football rigoureux. Tu réponds en français, brièvement.
Règles :
- Si tu ne connais pas la réponse avec certitude, commence par {config.ABSTAIN_MARK}.
- Si la demande est ambiguë, commence par {config.CLARIFY_MARK} et pose une seule question de précision.
- Si la demande sort du football, commence par {config.REFUSE_MARK} et explique brièvement.
- N'invente jamais de statistique."""


def answer(question: str, llm=chat) -> Result:
    """Niveau 0 : prompt soigné, sans documents ni outils."""
    tracer = Tracer(level=0, question=question)
    resp = llm([{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}])
    tracer.log("llm", tokens_in=resp.tokens_in, tokens_out=resp.tokens_out, latency_s=resp.latency_s)
    res = Result(level=0, answer=resp.text, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
                 latency_s=resp.latency_s, steps=1, **parse_marks(resp.text))
    tracer.log("end", result=json.loads(json.dumps(res.to_dict(), default=str)))
    return res
