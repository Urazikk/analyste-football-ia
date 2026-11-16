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


_clients: dict[str | None, Any] = {}


def _get_client(base_url: str | None = None, api_key: str = ""):
    url = base_url or config.LLM_BASE_URL
    if url not in _clients:
        from openai import OpenAI

        # max_retries : reprise avec attente sur 429 (offre gratuite limitée en tokens par minute)
        _clients[url] = OpenAI(base_url=url, api_key=api_key or config.LLM_API_KEY or "none", max_retries=8)
    return _clients[url]


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str = "",
) -> LLMResponse:
    """Un appel au modèle. Les outils sont au format OpenAI (type=function).

    Sans température donnée, celle de la configuration s'applique (omise si elle est vide).
    """
    kwargs: dict[str, Any] = {"model": model or config.LLM_MODEL, "messages": messages,
                              "max_completion_tokens": max_tokens or config.LLM_MAX_TOKENS}
    temperature = config.LLM_TEMPERATURE if temperature is None else temperature
    if temperature is not None:
        kwargs["temperature"] = temperature
    if config.LLM_REASONING_EFFORT and kwargs["model"] == config.LLM_MODEL:
        kwargs["reasoning_effort"] = config.LLM_REASONING_EFFORT
    if tools:
        kwargs["tools"] = tools
    t0 = time.perf_counter()
    resp = _get_client(base_url, api_key).chat.completions.create(**kwargs)
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
