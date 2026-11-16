"""Niveau 3 : planification avant la boucle de l'agent (docs/plan.md, section 6).

Défaut visé, mesuré au niveau 2 : l'agent appelle un outil avant de décider si la demande est claire,
puis devine (match le plus récent, affiche inventée, parfois publiée).

1. Plan : un appel au modèle, sans outils, qui renvoie un JSON (décision, étapes, publication prévue).
2. Précision ou refus : réponse immédiate, marqueur posé par le code, aucun outil appelé.
3. Exécution : les étapes dont tous les arguments sont connus sont exécutées par le code, sans appel au
   modèle entre elles, puis la boucle du niveau 2 termine (src/agent.py, inchangé). publish_report est
   refusé par une règle métier si le plan ne l'a pas prévu pour cette affiche.
"""
from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from src import agent, config, tools
from src.llm import chat, parse_marks
from src.rag import cited_ids
from src.result import Result
from src.tools import Tool
from src.tracing import Tracer

MAX_PLANNED_CALLS = 6

PLAN_PROMPT = """Tu prépares le travail d'un analyste de football qui dispose d'outils. Tu n'appelles aucun outil :
tu décides quoi faire et tu réponds par un seul objet JSON, sans autre texte.

{"decision": "clarify" | "refuse" | "execute",
 "message": "question de précision ou motif du refus (vide si execute)",
 "steps": [{"tool": "nom de l'outil", "args": {}}],
 "publish": {"home_team": "...", "away_team": "..."} ou null}

Règles :
- "refuse" si la demande ne porte pas sur le football.
- "clarify" si la demande ne dit pas de quelle équipe, de quel match, de quelle affiche ou de quelle situation
  de jeu il s'agit. Ne comble jamais ce manque par le match le plus récent, ni par une équipe ou une affiche
  de ton choix : pose une seule question.
- "execute" sinon. Une question sur les règles du jeu est claire dès qu'elle nomme la règle ou la situation.
- steps : seulement les appels dont tous les arguments se déduisent de la demande (pas ceux qui dépendent
  du résultat d'un autre outil). Jamais publish_report.
- publish : non nul seulement si l'utilisateur demande explicitement de publier et nomme les deux équipes.

Outils :
TOOLS"""

CONTINUE = ("Les étapes préparées ci-dessus sont exécutées. Termine la demande d'origine : appelle d'autres "
            "outils seulement s'il manque une information, puis réponds.")


def describe(registry: dict[str, Tool]) -> str:
    return "\n".join(f"- {t.name} ({t.effect}) : {t.description} Arguments : "
                     f"{json.dumps(t.parameters.get('properties', {}), ensure_ascii=False)}"
                     for t in registry.values())


def parse_plan(text: str) -> dict[str, Any] | None:
    """Plan lu dans la réponse du modèle (premier « { » au dernier « } »), None s'il est illisible."""
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start:end + 1]) if start >= 0 else None
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("decision") not in ("clarify", "refuse", "execute"):
        return None
    steps = [s for s in data.get("steps") or []
             if isinstance(s, dict) and isinstance(s.get("tool"), str) and isinstance(s.get("args", {}), dict)]
    pub = data.get("publish")
    ok = isinstance(pub, dict) and all(isinstance(pub.get(k), str) and pub[k].strip() for k in ("home_team", "away_team"))
    return {"decision": data["decision"], "message": str(data.get("message") or "").strip(),
            "steps": [{"tool": s["tool"], "args": s.get("args", {})} for s in steps],
            "publish": {"home_team": pub["home_team"], "away_team": pub["away_team"]} if ok else None}


def _teams(home: Any, away: Any) -> frozenset[str]:
    """Les deux équipes d'une affiche, noms normalisés, sans ordre."""
    def norm(name: Any) -> str:
        try:
            return tools._team_or_raw(str(name)).lower()
        except Exception:  # données absentes : on compare les noms tels quels
            return str(name).strip().lower()
    return frozenset({norm(home), norm(away)})


def guarded(registry: dict[str, Tool], publish: dict[str, str] | None) -> dict[str, Tool]:
    """Registre où publish_report n'est permis que pour l'affiche prévue par le plan (règle vérifiée par du code)."""
    tool = registry.get("publish_report")
    if tool is None:
        return registry

    def check(args: dict[str, Any]) -> list[str]:
        if publish is None:
            return ["Publication non prévue : l'utilisateur ne l'a pas demandée pour une affiche précise. Ne publie pas."]
        if _teams(args.get("home_team"), args.get("away_team")) != _teams(publish["home_team"], publish["away_team"]):
            return [f"L'affiche publiée doit être celle demandée : {publish['home_team']} - {publish['away_team']}."]
        return tool.check(args) if tool.check else []

    return {**registry, "publish_report": replace(tool, check=check)}


def _planned_calls(plan: dict[str, Any], registry: dict[str, Tool]) -> list[dict[str, Any]]:
    """Étapes du plan exécutables par le code : outils connus, sans effet irréversible."""
    steps = [s for s in plan["steps"] if s["tool"] in registry and registry[s["tool"]].effect != "irreversible"]
    return [{"id": f"plan-{i}", "name": s["tool"], "arguments": json.dumps(s["args"], ensure_ascii=False)}
            for i, s in enumerate(steps[:MAX_PLANNED_CALLS], 1)]


def run(question: str, llm=chat, registry: dict[str, Tool] | None = None,
        confirm: agent.Confirm | None = None) -> Result:
    registry = tools.REGISTRY if registry is None else registry
    tracer = Tracer(level=3, question=question)
    res = Result(level=3, trace_path=str(tracer.path), steps=1)
    t0 = time.perf_counter()

    try:
        resp = llm([{"role": "system", "content": PLAN_PROMPT.replace("TOOLS", describe(registry))},
                    {"role": "user", "content": question}])
    except Exception as e:
        res.error, res.stop_reason = f"{type(e).__name__}: {e}"[:1000], "llm_error"
        tracer.log("llm_error", step=1, error=res.error)
        return res
    res.tokens_in, res.tokens_out = resp.tokens_in, resp.tokens_out
    plan = parse_plan(resp.text)
    tracer.log("plan", tokens_in=resp.tokens_in, tokens_out=resp.tokens_out, latency_s=resp.latency_s,
               text=resp.text, plan=plan)

    if plan and plan["decision"] in ("clarify", "refuse"):
        mark = config.CLARIFY_MARK if plan["decision"] == "clarify" else config.REFUSE_MARK
        res.answer = f"{mark} {plan['message'].replace(mark, '').strip()}".strip()
        res.clarified, res.refused = plan["decision"] == "clarify", plan["decision"] == "refuse"
        res.latency_s = time.perf_counter() - t0
        tracer.log("end", stop_reason=res.stop_reason, steps=1, tokens=res.tokens, latency_s=res.latency_s,
                   answer=res.answer, pending_action=None)
        return res

    # Exécution : étapes indépendantes par le code, puis boucle du niveau 2. Plan illisible : niveau 2 tel quel.
    pre = Result(level=3)
    history, loop_question = None, question
    if plan:
        calls = _planned_calls(plan, registry)
        outputs = [agent._handle_call(c, registry, None, pre, tracer) for c in calls]
        if calls:
            history = [{"role": "user", "content": question},
                       {"role": "assistant", "content": None,
                        "tool_calls": [{"id": c["id"], "type": "function",
                                        "function": {"name": c["name"], "arguments": c["arguments"]}} for c in calls]},
                       *({"role": "tool", "tool_call_id": c["id"], "content": o} for c, o in zip(calls, outputs))]
            pub = plan["publish"]
            loop_question = CONTINUE + (f" Publication prévue pour l'affiche {pub['home_team']} - {pub['away_team']}."
                                        if pub else " Aucune publication n'est prévue : ne publie pas.")
        registry = guarded(registry, plan["publish"])

    loop = agent.run(loop_question, llm=llm, registry=registry, confirm=confirm,
                     max_steps=config.AGENT_MAX_STEPS - 1, max_tokens=config.AGENT_MAX_TOKENS - res.tokens,
                     history=history)
    _merge_trace(tracer, loop.trace_path)

    res.tool_calls = pre.tool_calls + loop.tool_calls
    res.answer, res.pending_action = loop.answer, loop.pending_action
    res.stop_reason, res.error = loop.stop_reason, loop.error
    res.tokens_in += loop.tokens_in
    res.tokens_out += loop.tokens_out
    res.steps = 1 + loop.steps
    res.latency_s = time.perf_counter() - t0
    for k, v in parse_marks(res.answer).items():
        setattr(res, k, v)
    res.retrieved, seen = agent.search_results(res.tool_calls)
    res.sources = [] if res.abstained else cited_ids(res.answer, seen)
    return res


def _merge_trace(tracer: Tracer, loop_path: str | None) -> None:
    """Une seule trace par exécution : les événements de la boucle sont ajoutés à celle du plan."""
    if not loop_path or not Path(loop_path).exists():
        return
    with tracer.path.open("a", encoding="utf-8") as f:
        f.write(Path(loop_path).read_text(encoding="utf-8"))
    Path(loop_path).unlink()


def answer(question: str, confirm: agent.Confirm | None = None) -> Result:
    return run(question, confirm=confirm)
