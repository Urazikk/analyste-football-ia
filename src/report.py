"""Rapport d'avant-match structuré (plan, C2) : les données sont calculées par le code, pas par le modèle.

Le modèle écrit l'analyse (`content`) ; à la publication, le code ajoute des sections chiffrées
(forme, confrontations, dernier match de chaque équipe avec sa carte des tirs). Les chiffres des
sections ne peuvent donc pas être inventés. `to_markdown` donne la mise en page commune à
l'interface et à l'export PDF.

Format du fichier `STATE_DIR/reports/<domicile>-vs-<exterieur>.json` :
    home_team, away_team, title, content          (rédigés par le modèle)
    sections.form.{home,away}                      team_form : 5 derniers matchs et bilan
    sections.head_to_head                          head_to_head : confrontations directes
    sections.last_match.{home,away}                match, team_stats, shot_map (chemin du PNG)
"""
from __future__ import annotations

from typing import Any

from src import tools


def _last_match(team: str) -> dict[str, Any] | None:
    matches = tools.list_matches(team, limit=1)
    if not matches:
        return None
    m = matches[0]
    return {"match": m, "stats": tools.team_stats(m["match_id"], team),
            "shot_map": tools.plot_shots(m["match_id"], team)["path"]}


def build_sections(home: str, away: str) -> dict[str, Any]:
    """Sections chiffrées d'une affiche (noms StatsBomb). Lève ValueError si une équipe est inconnue."""
    return {
        "form": {"home": tools.team_form(home), "away": tools.team_form(away)},
        "head_to_head": tools.head_to_head(home, away),
        "last_match": {"home": _last_match(home), "away": _last_match(away)},
    }


def _form_table(form: dict[str, Any]) -> list[str]:
    s = form["summary"]
    lines = [f"**{form['team']}** : {s['won']} V, {s['drawn']} N, {s['lost']} D ; buts {s['goals_for']}-"
             f"{s['goals_against']} ; xG {s['xg_for']:.2f}-{s['xg_against']:.2f}", "",
             "| Date | Compétition | Tour | Adversaire | Score | Rés. | xG pour | xG contre |", "|---|---|---|---|---|---|---|---|"]
    for g in form["matches"]:
        score = g["score"] + (f" (tab {g['penalties']})" if g.get("penalties") else "")
        lines.append(f"| {g['date']} | {g['competition']} | {g['stage']} | {g['opponent']} | {score} | {g['result']} "
                     f"| {g['xg_for']:.2f} | {g['xg_against']:.2f} |")
    return lines + [""]


def to_markdown(report: dict[str, Any]) -> str:
    """Mise en page du rapport publié (interface et PDF). Les images sont référencées par leur chemin."""
    home, away = report["home_team"], report["away_team"]
    out = [f"# {report['title']}", "", f"*{home} - {away}*", "", "## Analyse", "", report["content"], ""]
    sec = report.get("sections")
    if not sec:
        return "\n".join(out)
    out += ["## Forme récente (5 derniers matchs disponibles)", ""]
    out += _form_table(sec["form"]["home"]) + _form_table(sec["form"]["away"])
    h2h = sec["head_to_head"]
    out += ["## Confrontations directes", ""]
    if h2h["matches"]:
        out += [f"- {g['date']}, {g['competition']} ({g['stage']}) : {home} {g['score']} {away}"
                + (f", tirs au but {g['penalties']}" if g.get("penalties") else "") for g in h2h["matches"]]
    else:
        out.append("Aucune confrontation dans les données (Euro 2020 et 2024, Copa América 2024, "
                   "Coupe du monde 2018 et 2022).")
    out += ["", "## Dernier match de chaque équipe", ""]
    for side in ("home", "away"):
        last = sec["last_match"][side]
        if not last:
            continue
        m, s = last["match"], last["stats"]
        out += [f"### {s['team']} : {m['home_team']} {m['score']} {m['away_team']} ({m['date']}, {m['stage']})", "",
                f"{s['shots']} tirs dont {s['shots_on_target']} cadrés, xG {s['xg']:.2f}, "
                f"{s['pass_accuracy_pct']:.1f} % de passes réussies, possession estimée {s['possession_pct']:.1f} %.", "",
                f"![Carte des tirs de {s['team']}]({last['shot_map']})", ""]
    return "\n".join(out)
