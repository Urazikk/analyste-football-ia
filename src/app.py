"""Interface Streamlit : choix du niveau, réponse, sources, coûts, confirmation des actions.

Lancement : streamlit run src/app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src import agent, config, llm, rag  # noqa: E402
from src.result import Result  # noqa: E402

LEVELS = {0: "0 · LLM seul", 1: "1 · RAG", 2: "2 · Agent", 3: "3 · Extension"}
STATUS = {"abstained": ("Abstention : rien de fiable dans les documents.", st.info),
          "clarified": ("Question de précision.", st.info),
          "refused": ("Refus : hors sujet.", st.warning)}


def show_status(res: Result) -> None:
    if res.error:
        st.error(f"Erreur : {res.error[:300]}")
    for attr, (text, box) in STATUS.items():
        if getattr(res, attr):
            box(text)
    if res.stop_reason not in ("final", "awaiting_confirmation", "below_threshold"):
        st.caption(f"Arrêt : {res.stop_reason}")


@st.cache_resource(show_spinner=False)
def chunks_by_id() -> dict[str, rag.Chunk]:
    return {c.id: c for c in rag.get_index().chunks}


def show_sources(res: Result) -> None:
    """Extraits cités, avec leur texte et leur origine ; puis les extraits retrouvés non cités."""
    if not (res.sources or res.retrieved):
        return
    by_id = chunks_by_id()
    st.subheader(f"Sources citées ({len(res.sources)})")
    if not res.sources:
        st.caption("Aucun extrait cité.")
    for cid in res.sources:
        c = by_id.get(cid)
        with st.expander(f"[{cid}] {c.title if c else ''}"):
            if c:
                st.write(c.text)
                st.caption(c.source if c.source.startswith("http") else f"Source : {c.source}")
    others = [cid for cid in res.retrieved if cid not in res.sources]
    if others:
        st.caption("Retrouvés mais non cités : " + ", ".join(others))


def show_costs(res: Result) -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tokens entrée", res.tokens_in)
    c2.metric("Tokens sortie", res.tokens_out)
    c3.metric("Coût équivalent", f"{config.cost_usd(res.tokens_in, res.tokens_out):.5f} $",
              help="Offre gratuite utilisée : coût de la même requête au tarif payant de .env")
    c4.metric("Latence (s)", f"{res.latency_s:.2f}")
    c5.metric("Étapes", res.steps)


def show_plots(res: Result) -> None:
    """Cartes des tirs produites par plot_shots pendant l'exécution."""
    for call in res.tool_calls:
        if call["name"] != "plot_shots":
            continue
        out = json.loads(call.get("output") or "{}")
        path = Path(out.get("result", {}).get("path", "")) if out.get("ok") else None
        if path and path.is_file():
            st.image(str(path), caption=path.name)


def last_trace() -> Path | None:
    files = sorted(config.TRACES_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


st.set_page_config(page_title="Analyste de football", layout="wide")
st.title("Analyste de football")

level = st.sidebar.radio("Niveau", list(LEVELS), format_func=LEVELS.get)
st.sidebar.caption(f"Modèle : {config.LLM_MODEL}")
question = st.text_area("Question")

if st.button("Envoyer", type="primary") and question:
    try:
        with st.spinner("Réponse en cours..."):
            if level == 0:
                res = llm.answer(question)
            elif level == 1:
                res = rag.answer(question)
            elif level == 2:
                res = agent.answer(question)
            else:
                raise NotImplementedError("Niveau 3 : semaine 4")
        st.session_state["res"] = res
        st.session_state.pop("action", None)
    except NotImplementedError as e:
        st.warning(str(e))

res = st.session_state.get("res")
if res:
    show_status(res)
    st.markdown(res.answer)
    show_plots(res)
    show_sources(res)
    show_costs(res)
    if res.tool_calls:
        with st.expander(f"Appels d'outils ({len(res.tool_calls)})"):
            st.json(res.tool_calls)
    trace = Path(res.trace_path) if res.trace_path else last_trace()
    if trace:
        st.caption(f"Trace : traces/{trace.name}")
    if res.pending_action:
        st.warning(f"Action irréversible demandée : {res.pending_action['name']}")
        st.json(res.pending_action["arguments"])
        ok, ko = st.columns(2)
        if ok.button("Valider"):
            out = json.loads(agent.confirm_pending(res.pending_action, trace_path=res.trace_path))
            st.session_state["action"] = (("success", f"Rapport publié : {out['result']['path']}") if out["ok"]
                                          else ("error", f"Action bloquée : {out['error']}"))
            res.pending_action = None
        elif ko.button("Refuser"):
            agent.refuse_pending(res.pending_action, trace_path=res.trace_path)
            st.session_state["action"] = ("info", "Action annulée, rien n'a été publié.")
            res.pending_action = None
    if "action" in st.session_state:
        kind, text = st.session_state["action"]
        getattr(st, kind)(text)
