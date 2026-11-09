"""Niveau 2 : agent outillé. Boucle écrite à la main, sans framework.

- bornée en étapes et en tokens ;
- erreurs d'outils (inconnu, arguments invalides, exception, règle métier) renvoyées au modèle ;
- toute action irréversible attend une confirmation : sans callback, la boucle s'arrête
  et renvoie l'action en attente (pending_action) que l'interface fera valider.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

import jsonschema

from src import config
from src.llm import chat, parse_marks
from src.rag import cited_ids
from src.result import Result
from src.tools import REGISTRY, Tool
from src.tracing import Tracer

Confirm = Callable[[str, dict[str, Any]], bool]

SYSTEM_PROMPT = f"""Tu es un analyste de football qui utilise des outils pour répondre.
- Appuie chaque chiffre sur un résultat d'outil, n'invente rien.
- Pour une question sur les règles du jeu, appelle search_rules et cite chaque extrait utilisé
  par son identifiant entre crochets, par exemple [ifab-loi-11#1-position-de-hors-jeu].
- Si un outil renvoie une erreur, corrige les arguments ou explique le blocage.
- Si l'information est introuvable, commence par {config.ABSTAIN_MARK}.
- Si la demande est ambiguë, commence par {config.CLARIFY_MARK} et pose une question.
- Hors football, commence par {config.REFUSE_MARK}.
- Publier un rapport est irréversible : ne le fais que si l'utilisateur le demande."""


def execute(tool: Tool, args: dict[str, Any]) -> str:
    """Exécute un outil et renvoie toujours une chaîne (résultat ou erreur) pour le modèle."""
    try:
        return json.dumps({"ok": True, "result": tool.fn(**args)}, ensure_ascii=False, default=str)[:8000]
    except Exception as e:  # l'erreur est renvoyée au modèle, pas levée
        return json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False)


def run(
    question: str,
    llm=chat,
    registry: dict[str, Tool] = REGISTRY,
    confirm: Confirm | None = None,
    max_steps: int = config.AGENT_MAX_STEPS,
    max_tokens: int = config.AGENT_MAX_TOKENS,
    history: list[dict[str, Any]] | None = None,
) -> Result:
    tracer = Tracer(level=2, question=question)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *(history or []),
                {"role": "user", "content": question}]
    schemas = [t.schema() for t in registry.values()]
    res = Result(level=2)
    t0 = time.perf_counter()

    for step in range(1, max_steps + 1):
        res.steps = step
        if res.tokens >= max_tokens:
            res.stop_reason = "max_tokens"
            break
        resp = llm(messages, tools=schemas)
        res.tokens_in += resp.tokens_in
        res.tokens_out += resp.tokens_out
        tracer.log("llm", step=step, tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
                   latency_s=resp.latency_s, tool_calls=resp.tool_calls, text=resp.text)

        if not resp.tool_calls:
            res.answer = resp.text
            res.stop_reason = "final"
            break

        messages.append({"role": "assistant", "content": resp.text or None,
                         "tool_calls": [{"id": c["id"], "type": "function",
                                         "function": {"name": c["name"], "arguments": c["arguments"]}}
                                        for c in resp.tool_calls]})
        for call in resp.tool_calls:
            output = _handle_call(call, registry, confirm, res, tracer)
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": output})
            if res.pending_action:
                break
        if res.pending_action:
            res.stop_reason = "awaiting_confirmation"
            res.answer = resp.text or "Action en attente de confirmation."
            break
    else:
        res.stop_reason = "max_steps"

    res.latency_s = time.perf_counter() - t0
    for k, v in parse_marks(res.answer).items():
        setattr(res, k, v)
    res.retrieved, seen = search_results(res.tool_calls)
    res.sources = [] if res.abstained else cited_ids(res.answer, seen)
    tracer.log("end", stop_reason=res.stop_reason, steps=res.steps, tokens=res.tokens,
               latency_s=res.latency_s, answer=res.answer, pending_action=res.pending_action)
    return res


def _handle_call(call: dict[str, Any], registry: dict[str, Tool], confirm: Confirm | None,
                 res: Result, tracer: Tracer) -> str:
    name = call["name"]
    record: dict[str, Any] = {"name": name, "arguments": call["arguments"]}
    res.tool_calls.append(record)

    tool = registry.get(name)
    if tool is None:
        out = json.dumps({"ok": False, "error": f"Outil inconnu : {name}"})
    else:
        try:
            args = json.loads(call["arguments"] or "{}")
            jsonschema.validate(args, tool.parameters)
        except (json.JSONDecodeError, jsonschema.ValidationError) as e:
            out = json.dumps({"ok": False, "error": f"Arguments invalides : {e}"}, ensure_ascii=False)
        else:
            errors = tool.check(args) if tool.check else []
            if errors:
                out = json.dumps({"ok": False, "error": "Règle métier : " + " ".join(errors)}, ensure_ascii=False)
            elif tool.effect == "irreversible" and confirm is None:
                res.pending_action = {"name": name, "arguments": args}
                out = json.dumps({"ok": False, "error": "En attente de confirmation de l'utilisateur."})
            elif tool.effect == "irreversible" and not confirm(name, args):
                out = json.dumps({"ok": False, "error": "Action refusée par l'utilisateur."}, ensure_ascii=False)
            else:
                out = execute(tool, args)

    record["output"] = out
    tracer.log("tool", name=name, effect=tool.effect if tool else None,
               arguments=call["arguments"], output=out[:2000])
    return out


def search_results(tool_calls: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Morceaux du premier appel réussi à search_rules (pour Recall@5 et MRR) et tous ceux vus."""
    first: list[str] = []
    seen: list[str] = []
    for call in tool_calls:
        if call["name"] != "search_rules":
            continue
        out = json.loads(call.get("output") or "{}")
        ids = [r["id"] for r in out.get("result", [])] if out.get("ok") else []
        first = first or ids
        seen += [i for i in ids if i not in seen]
    return first, seen


def confirm_pending(pending: dict[str, Any], registry: dict[str, Tool] = REGISTRY) -> str:
    """Appelé par l'interface après validation explicite de l'utilisateur."""
    tool = registry[pending["name"]]
    errors = tool.check(pending["arguments"]) if tool.check else []
    if errors:
        return json.dumps({"ok": False, "error": " ".join(errors)}, ensure_ascii=False)
    return execute(tool, pending["arguments"])


def answer(question: str, confirm: Confirm | None = None) -> Result:
    return run(question, confirm=confirm)
