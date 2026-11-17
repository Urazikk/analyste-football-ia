"""Interface Streamlit : choix du niveau, réponse, sources, coûts, confirmation des actions.

Lancement : streamlit run src/app.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from src import agent, catalog, config, export, level3, llm, rag, report  # noqa: E402
from src.result import Result  # noqa: E402

LEVELS = {0: "0 · LLM seul", 1: "1 · RAG", 2: "2 · Agent", 3: "3 · Agent avec plan"}
LEVEL_INFO = {0: ("#6b7684", "Le modèle seul, sans documents ni outils : la référence à battre."),
              1: ("#3b6ea5", "Cherche dans les lois du jeu, cite ses sources, s'abstient si rien n'est trouvé."),
              2: ("#1f6f4a", "Utilise les outils sur les données de matchs ; toute publication attend votre validation."),
              3: ("#e8892b", "Planifie avant d'agir : demande une précision si la demande est floue.")}
CSS = (Path(__file__).parent / "style.css").read_text(encoding="utf-8")
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


def run_level(level: int, question: str) -> Result:
    """Réponse d'un niveau ; l'agent n'exécute jamais d'action irréversible ici sans validation."""
    if level == 0:
        return llm.answer(question)
    if level == 1:
        return rag.answer(question)
    if level == 2:
        return agent.answer(question)
    return level3.answer(question)


def tab_compare() -> None:
    """Même question aux niveaux 0 à 3, côte à côte : réponse, sources, coût."""
    q = st.text_area("Question à comparer", key="cmp_q")
    if st.button("Comparer les niveaux 0 à 3", key="cmp_go") and q:
        with st.spinner("Quatre réponses en cours..."):
            st.session_state["cmp"] = {lv: run_level(lv, q) for lv in LEVELS}
    results = st.session_state.get("cmp")
    if not results:
        return
    for col, (lv, r) in zip(st.columns(len(results)), results.items()):
        with col:
            st.subheader(LEVELS[lv])
            show_status(r)
            st.markdown(r.answer or "_(pas de réponse)_")
            st.caption(f"Sources : {', '.join(r.sources) or 'aucune'}")
            st.caption(f"{r.tokens} tokens · {config.cost_usd(r.tokens_in, r.tokens_out):.5f} $ · "
                       f"{r.latency_s:.1f} s · {r.steps} étape(s)")
            if r.pending_action:
                st.warning("Action demandée, non exécutée ici : utiliser l'onglet Question pour la valider.")


def show_report(data: dict) -> None:
    """Mise en page de report.to_markdown ; les images (cartes des tirs) sont affichées avec st.image."""
    md = report.to_markdown(data) if data.get("title") else data.get("content", "")
    buf: list[str] = []
    for line in md.splitlines():
        m = export.IMAGE_RE.match(line.strip())
        if m:
            st.markdown("\n".join(buf))
            buf = []
            if Path(m.group(1)).is_file():
                st.image(m.group(1), width=480)
        else:
            buf.append(line)
    st.markdown("\n".join(buf))


def tab_reports() -> None:
    """Rapports publiés : contenu et export PDF."""
    reports = export.published_reports()
    if not reports:
        st.info("Aucun rapport publié pour l'instant.")
        return
    for path in reports:
        data = json.loads(path.read_text(encoding="utf-8"))
        with st.expander(f"{data.get('title') or path.stem} ({path.stem})"):
            show_report(data)
            pdf = export.report_to_pdf(path)
            st.download_button("Télécharger le PDF", pdf.read_bytes(), file_name=pdf.name,
                               mime="application/pdf", key=f"pdf_{path.stem}")


@st.cache_resource(show_spinner=False)
def prediction_teams() -> list[str]:
    from src import predict

    hist, _ = predict._model()
    last = hist.pre[hist.pre["date"] >= "2022-01-01"]
    return sorted(set(last["home_team"]) | set(last["away_team"]))


def tab_prediction() -> None:
    """Pronostic d'une affiche future : Elo, Poisson et 10 000 matchs simulés, avec l'animation."""
    from src import animation, predict

    if not predict.cache_path().exists():
        st.info("Résultats internationaux absents : lancer `python scripts/eval_prediction.py` (téléchargement puis évaluation).")
        return
    teams = prediction_teams()
    c1, c2, c3 = st.columns([2, 2, 1])
    home = c1.selectbox("Équipe 1 (à domicile)", teams, index=teams.index("France") if "France" in teams else 0,
                        format_func=animation.french)
    away = c2.selectbox("Équipe 2", teams, index=teams.index("Spain") if "Spain" in teams else 1,
                        format_func=animation.french)
    neutral = c3.checkbox("Terrain neutre", value=True)
    if st.button("Simuler 10 000 matchs", key="pred_go") and home != away:
        with st.spinner("Simulation et animation..."):
            res = predict.simulate(home, away, neutral)
            video = animation.animate_match(home, away, neutral, config.state_dir() / "animations" / f"{home}-{away}.mp4")
        st.session_state["pred"] = (res, str(video))
    if "pred" not in st.session_state:
        st.caption("Modèle évalué sur 1 803 matchs depuis 2025 : voir results/prediction/backtest.md.")
        return
    res, video = st.session_state["pred"]
    a, b = st.columns([1, 1])
    with a:
        st.metric(f"Victoire {animation.french(res['home'])}", f"{res['home_win']:.0%}")
        st.metric("Match nul", f"{res['draw']:.0%}")
        st.metric(f"Victoire {animation.french(res['away'])}", f"{res['away_win']:.0%}")
        st.caption("Scores les plus probables : " + ", ".join(f"{s['score']} ({s['p']:.0%})" for s in res["likely_scores"]))
        st.caption(f"Elo {res['elo_home']} contre {res['elo_away']} · buts attendus {res['expected_goals'][0]} - "
                   f"{res['expected_goals'][1]} · {res['note']}")
    with b:
        st.video(video)


def _pick(key: str, choices: dict[str, tuple[str, int]]) -> None:
    """Puce choisie : remplit la question et le niveau conseillé, puis libère la puce."""
    picked = st.session_state.get(key)
    if picked:
        st.session_state["question"], st.session_state["level"] = choices[picked]
        st.session_state[key] = None


@st.cache_data(show_spinner=False)
def match_list() -> list[dict]:
    from src import data

    if not (data.cache_dir() / "matches").exists():
        return []
    return catalog.matches()


def suggestions() -> None:
    """Questions proposées par thème, et matchs à analyser."""
    left, right = st.container(key="sugg").columns([3, 2], gap="large")
    with left:
        st.html('<div class="af-section">Questions proposées</div>')
        cats = [c for c, _ in catalog.QUESTIONS]
        cat = st.segmented_control("Thème", cats, default=cats[0], key="theme", label_visibility="collapsed") or cats[0]
        qs = dict(catalog.QUESTIONS)[cat]
        choices = {f"{q}  ({what})": (q, lv) for q, lv, what in qs}
        st.pills("Questions", list(choices), key="pick_q", label_visibility="collapsed",
                 on_change=_pick, args=("pick_q", choices))
    with right:
        st.html('<div class="af-section">Matchs à analyser</div>')
        ms = match_list()
        if not ms:
            st.caption("Données StatsBomb absentes : `python scripts/fetch_statsbomb.py`.")
            return
        comps = sorted({m["competition_fr"] for m in ms}, key=lambda c: (c[-4:], c.startswith("Euro")), reverse=True)
        comp = st.selectbox("Compétition", comps, key="comp")
        pool = [m for m in ms if m["competition_fr"] == comp]
        m = st.selectbox("Match", pool, key="match", format_func=lambda x: x["label"].split("  ·  ")[0]
                         + f"  ·  {x['stage_fr']}")
        choices = {name: (q, lv) for name, q, lv in catalog.match_questions(m)}
        st.pills("Analyses", list(choices), key="pick_m", label_visibility="collapsed",
                 on_change=_pick, args=("pick_m", choices))


def tab_question() -> None:
    suggestions()
    question = st.text_area("Question", key="question", height=90,
                            placeholder="Posez une question, ou choisissez une suggestion ci-dessus.")

    if st.button("Envoyer", type="primary") and question:
        try:
            with st.spinner("Réponse en cours..."):
                res = run_level(level, question)
            st.session_state["res"] = res
            st.session_state.pop("action", None)
        except NotImplementedError as e:
            st.warning(str(e))

    res = st.session_state.get("res")
    if res:
        show_status(res)
        with st.container(key=f"answer_{res.level}"):
            # images citées par le modèle avec un chemin local : affichées en dessous par show_plots
            st.markdown(re.sub(r"!\[[^\]]*\]\([^)]*\)", "", res.answer))
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
            args = res.pending_action["arguments"]
            st.warning(f"Action irréversible demandée : {res.pending_action['name']}. Rien n'est fait sans votre validation.")
            if args.get("content"):  # rapport lisible avant validation, arguments bruts en dessous
                st.markdown(f"**{args.get('title', '')}** ({args.get('home_team', '')} - {args.get('away_team', '')})")
                st.markdown(args["content"])
            with st.expander("Arguments de l'action"):
                st.json(args)
            ok, ko = st.columns(2)
            if ok.button("Valider"):
                out = json.loads(agent.confirm_pending(res.pending_action, trace_path=res.trace_path))
                st.session_state["action"] = (("success", f"Rapport publié : {out['result']['path']}") if out["ok"]
                                              else ("error", f"Action bloquée : {out['error']}"))
                res.pending_action = None
                st.rerun()  # l'action en attente et ses boutons disparaissent : pas de seconde validation
            elif ko.button("Refuser"):
                agent.refuse_pending(res.pending_action, trace_path=res.trace_path)
                st.session_state["action"] = ("info", "Action annulée, rien n'a été publié.")
                res.pending_action = None
                st.rerun()
        if "action" in st.session_state:
            kind, text = st.session_state["action"]
            getattr(st, kind)(text)


st.set_page_config(page_title="Analyste de football", page_icon="⚽", layout="wide")
st.html("<style>" + CSS + "".join(f".st-key-answer_{lv}{{--af-c:{c}}}" for lv, (c, _) in LEVEL_INFO.items())
        + ''.join(f'.st-key-answer_{lv}{{background:#fff;border-radius:18px;padding:18px 22px;'
                  'border:1px solid #e3e8e4;border-left:6px solid var(--af-c);box-shadow:0 6px 18px rgba(18,55,42,.07)}'
                  for lv in LEVEL_INFO) + "</style>")

level = st.sidebar.radio("Niveau (onglet Question)", list(LEVELS), format_func=LEVELS.get, key="level")
color, info = LEVEL_INFO[level]
st.sidebar.html(f'<div class="af-level" style="--af-c:{color}"><b>{LEVELS[level]}</b><span>{info}</span></div>')
st.sidebar.caption(f"Modèle : {config.LLM_MODEL} · coût au tarif du modèle")
st.html('<div class="af-hero"><h1>Analyste de football</h1>'
        "<p>Lois du jeu avec sources citées, statistiques des matchs StatsBomb, rapports d'avant-match validés "
        "par vous. Quatre niveaux, mesurés sur le même protocole.</p><div class=\"af-chips\">"
        + "".join(f'<span class="af-chip{" af-on" if lv == level else ""}">{name}</span>' for lv, name in LEVELS.items())
        + "</div></div>")
tab_q, tab_c, tab_p, tab_r = st.tabs(["Question", "Comparer les niveaux", "Pronostic", "Rapports publiés"])
with tab_q:
    tab_question()
with tab_c:
    tab_compare()
with tab_p:
    tab_prediction()
with tab_r:
    tab_reports()
