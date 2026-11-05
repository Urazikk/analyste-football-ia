"""Interface Streamlit : choix du niveau, réponse, sources, coûts, confirmation des actions.

Lancement : streamlit run src/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src import agent, llm, rag  # noqa: E402

LEVELS = {0: "0 · LLM seul", 1: "1 · RAG", 2: "2 · Agent", 3: "3 · Extension"}

st.set_page_config(page_title="Analyste de football", layout="wide")
st.title("Analyste de football")

level = st.sidebar.radio("Niveau", list(LEVELS), format_func=LEVELS.get)
question = st.text_area("Question")

if st.button("Envoyer", type="primary") and question:
    try:
        if level == 0:
            res = llm.answer(question)
        elif level == 1:
            res = rag.answer(question)
        elif level == 2:
            res = agent.answer(question)
        else:
            raise NotImplementedError("Niveau 3 : semaine 4")
        st.session_state["res"] = res
    except NotImplementedError as e:
        st.warning(str(e))

res = st.session_state.get("res")
if res:
    st.markdown(res.answer)
    if res.sources:
        st.caption("Sources : " + ", ".join(res.sources))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tokens entrée", res.tokens_in)
    c2.metric("Tokens sortie", res.tokens_out)
    c3.metric("Latence (s)", f"{res.latency_s:.2f}")
    c4.metric("Étapes", res.steps)
    if res.tool_calls:
        with st.expander("Appels d'outils"):
            st.json(res.tool_calls)
    if res.pending_action:
        st.warning(f"Action irréversible demandée : {res.pending_action['name']}")
        st.json(res.pending_action["arguments"])
        ok, ko = st.columns(2)
        if ok.button("Valider"):
            st.success(agent.confirm_pending(res.pending_action))
            res.pending_action = None
        if ko.button("Refuser"):
            st.info("Action annulée.")
            res.pending_action = None
