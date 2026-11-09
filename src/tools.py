"""Outils de l'agent : schéma JSON, classe d'effet, règles métier vérifiées par du code."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Literal

from src import config

Effect = Literal["read", "compute", "irreversible"]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]                  # schéma JSON des arguments
    effect: Effect
    fn: Callable[..., Any]
    check: Callable[[dict[str, Any]], list[str]] | None = None  # règles métier, liste d'erreurs

    def schema(self) -> dict[str, Any]:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description,
                             "parameters": self.parameters}}


# Outil de lecture des lois du jeu (RAG du niveau 1) ------------------------------

def search_rules(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Extraits des lois du jeu (IFAB) et de Wikipédia les plus proches de la question."""
    from src import rag

    return [{"id": c.id, "title": c.title, "text": c.text} for c, _ in rag.search(query, k)]


# Outils de lecture (StatsBomb) --------------------------------------------------

# Types d'événements : nom français ou StatsBomb vers le nom StatsBomb
EVENT_TYPES = {"tir": "Shot", "tirs": "Shot", "passe": "Pass", "passes": "Pass", "faute": "Foul Committed",
               "fautes": "Foul Committed", "dribble": "Dribble", "dribbles": "Dribble",
               "interception": "Interception", "interceptions": "Interception", "remplacement": "Substitution",
               "remplacements": "Substitution", "carton": "card", "cartons": "card", "but": "goal", "buts": "goal"}
ON_TARGET = {"Goal", "Saved", "Saved To Post"}
SHOOTOUT = 5  # période des tirs au but, exclue des statistiques


def _match_team(match_id: int, team: str) -> tuple[Any, str]:
    """Match et nom StatsBomb de l'équipe ; erreur si elle n'a pas joué ce match."""
    from src import data

    m = data.get_match(match_id)
    name = data.resolve_team(team)
    if name not in (m["home_team"], m["away_team"]):
        raise ValueError(f"{name} n'a pas joué le match {match_id} ({m['home_team']} - {m['away_team']}).")
    return m, name


def _match_summary(m: Any) -> dict[str, Any]:
    return {"match_id": int(m["match_id"]), "date": m["match_date"].strftime("%Y-%m-%d"),
            "competition": m["competition"], "stage": m["competition_stage"],
            "home_team": m["home_team"], "away_team": m["away_team"],
            "score": f"{int(m['home_score'])}-{int(m['away_score'])}"}


def list_matches(team: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Derniers matchs disponibles, du plus récent au plus ancien, filtrés par équipe."""
    from src import data

    m = data.all_matches()
    if team:
        name = data.resolve_team(team)
        m = m[(m["home_team"] == name) | (m["away_team"] == name)]
    return [_match_summary(row) for _, row in m.head(limit).iterrows()]


def _is_card(ev: Any) -> bool:
    return any(isinstance(ev.get(c), str) for c in ("foul_committed_card", "bad_behaviour_card"))


def match_events(match_id: int, event_type: str | None = None, team: str | None = None,
                 limit: int = 30) -> dict[str, Any]:
    """Événements d'un match, résumés en une ligne chacun (pas le tableau brut)."""
    from src import data

    ev = data.events(match_id)
    if team:
        ev = ev[ev["team"] == _match_team(match_id, team)[1]]
    if event_type:
        kind = EVENT_TYPES.get(event_type.strip().lower(), event_type.strip())
        if kind == "card":
            ev = ev[ev.apply(_is_card, axis=1)]
        elif kind == "goal":
            ev = ev[(ev["type"] == "Shot") & (ev.get("shot_outcome") == "Goal") & (ev["period"] != SHOOTOUT)]
        elif kind in set(ev["type"]):
            ev = ev[ev["type"] == kind]
        else:
            known = sorted(set(EVENT_TYPES) | {"Shot", "Pass", "Foul Committed", "Dribble"})
            raise ValueError(f"Type d'événement inconnu ou absent du match : « {event_type} ». "
                             f"Exemples valides : {', '.join(known)}.")
    ev = ev.sort_values("index")
    rows = []
    for _, e in ev.head(limit).iterrows():
        row = {"minute": int(e["minute"]), "team": e["team"], "player": e.get("player"), "type": e["type"]}
        if e["type"] == "Shot":
            row |= {"outcome": e.get("shot_outcome"), "xg": round(float(e.get("shot_statsbomb_xg") or 0), 3)}
        elif e["type"] == "Pass":
            row["outcome"] = e.get("pass_outcome") if isinstance(e.get("pass_outcome"), str) else "Complete"
        for c in ("foul_committed_card", "bad_behaviour_card"):
            if isinstance(e.get(c), str):
                row["card"] = e[c]
        rows.append({k: v for k, v in row.items() if v is not None and v == v})  # retire les NaN
    return {"total": len(ev), "shown": len(rows), "events": rows}


def team_stats(match_id: int, team: str) -> dict[str, Any]:
    """Statistiques d'une équipe sur un match, hors tirs au but."""
    from src import data

    m, name = _match_team(match_id, team)
    ev = data.events(match_id)
    ev = ev[ev["period"] != SHOOTOUT]
    own = ev[ev["team"] == name]
    shots = own[own["type"] == "Shot"]
    passes = own[own["type"] == "Pass"]
    all_passes = (ev["type"] == "Pass").sum()
    completed = passes["pass_outcome"].isna().sum() if "pass_outcome" in passes else len(passes)
    home = name == m["home_team"]
    return {
        "match_id": int(match_id), "team": name,
        "opponent": m["away_team"] if home else m["home_team"],
        "goals": int(m["home_score"] if home else m["away_score"]),
        "shots": len(shots),
        "shots_on_target": int(shots["shot_outcome"].isin(ON_TARGET).sum()) if len(shots) else 0,
        "xg": round(float(shots["shot_statsbomb_xg"].sum()), 2) if len(shots) else 0.0,
        "passes": len(passes), "pass_accuracy_pct": round(100 * completed / len(passes), 1) if len(passes) else 0.0,
        "possession_pct": round(100 * len(passes) / all_passes, 1) if all_passes else 0.0,
        "note": "possession estimée par la part des passes ; buts = score officiel (sans tirs au but)",
    }


def plot_shots(match_id: int, team: str) -> dict[str, Any]:
    """Carte des tirs (PNG) dans STATE_DIR/plots/, renvoie le chemin et le décompte."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from src import data

    m, name = _match_team(match_id, team)
    ev = data.events(match_id)
    shots = ev[(ev["team"] == name) & (ev["type"] == "Shot") & (ev["period"] != SHOOTOUT)]

    fig, ax = plt.subplots(figsize=(6, 4.4))
    _draw_half_pitch(ax)
    for _, s in shots.iterrows():
        x, y = s["location"][:2]
        goal = s["shot_outcome"] == "Goal"
        ax.scatter(y, x, s=60 + 900 * float(s["shot_statsbomb_xg"]), alpha=0.75, zorder=3,
                   c="#d62728" if goal else "#1f77b4", edgecolors="black", linewidths=0.6)
    ax.set_title(f"Tirs de {name} : {m['home_team']} {int(m['home_score'])}-{int(m['away_score'])} "
                 f"{m['away_team']}\n{len(shots)} tirs, xG {shots['shot_statsbomb_xg'].sum():.2f} "
                 "(rouge : but, taille : xG)", fontsize=9)
    path = config.state_dir() / "plots" / f"shots-{match_id}-{report_slug(name)}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return {"path": str(path), "shots": len(shots), "goals": int((shots["shot_outcome"] == "Goal").sum())}


def _draw_half_pitch(ax: Any) -> None:
    """Moitié offensive d'un terrain StatsBomb (120 x 80), but en haut."""
    kw = {"color": "#555", "lw": 1, "fill": False}
    import matplotlib.patches as pt

    for patch in (pt.Rectangle((0, 60), 80, 60, **kw), pt.Rectangle((18, 102), 44, 18, **kw),
                  pt.Rectangle((30, 114), 20, 6, **kw), pt.Rectangle((36, 120), 8, 1.5, **kw),
                  pt.Arc((40, 60), 20, 20, theta1=0, theta2=180, **{"color": "#555", "lw": 1})):
        ax.add_patch(patch)
    ax.set_xlim(-2, 82)
    ax.set_ylim(58, 123)
    ax.set_aspect("equal")
    ax.axis("off")


# Outil qui agit -----------------------------------------------------------------

def report_slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", s.lower())
                  .encode("ascii", "ignore").decode()).strip("-")


def _team_or_raw(name: str) -> str:
    """Nom StatsBomb si l'équipe est connue (« Espagne » -> Spain), sinon le nom tel quel."""
    from src import data

    try:
        return data.resolve_team(name)
    except ValueError:
        return name


def report_path(home_team: str, away_team: str):
    """Un rapport par affiche : STATE_DIR/reports/<domicile>-vs-<exterieur>.json (noms StatsBomb)."""
    return (config.state_dir() / "reports"
            / f"{report_slug(_team_or_raw(home_team))}-vs-{report_slug(_team_or_raw(away_team))}.json")


def publish_report(home_team: str, away_team: str, title: str, content: str) -> dict[str, Any]:
    """Publie le rapport d'avant-match d'une affiche. Irréversible."""
    home, away = _team_or_raw(home_team), _team_or_raw(away_team)
    path = report_path(home, away)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"home_team": home, "away_team": away, "title": title,
                                "content": content}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"published": True, "path": str(path)}


def check_publish_report(args: dict[str, Any]) -> list[str]:
    """Règles métier vérifiées par du code avant toute confirmation."""
    from src import data

    errors = []
    teams = []
    for key in ("home_team", "away_team"):
        try:
            teams.append(data.resolve_team(args.get(key, "")))
        except ValueError as e:
            errors.append(str(e))
    if len(teams) == 2 and teams[0] == teams[1]:
        errors.append("Les deux équipes de l'affiche doivent être différentes.")
    if report_path(args.get("home_team", ""), args.get("away_team", "")).exists():
        errors.append("Un rapport est déjà publié pour cette affiche.")
    content = args.get("content", "")
    if len(content.strip()) < 200:
        errors.append("Rapport trop court (200 caractères minimum).")
    if not re.search(r"\d", content):
        errors.append("Le rapport doit citer au moins un chiffre issu des données.")
    return errors


REGISTRY: dict[str, Tool] = {t.name: t for t in [
    Tool("search_rules", "Cherche dans les lois du jeu (IFAB 2026/27) et Wikipédia. Renvoie des extraits avec leur "
         "identifiant, à citer entre crochets dans la réponse. À utiliser pour toute question sur les règles.",
         {"type": "object", "properties": {"query": {"type": "string", "minLength": 3},
                                           "k": {"type": "integer", "minimum": 1, "maximum": 8}},
          "required": ["query"], "additionalProperties": False},
         "read", search_rules),
    Tool("list_matches", "Derniers matchs disponibles (Euro 2020 et 2024, Copa América 2024, Coupe du monde 2018 et 2022), du "
         "plus récent au plus ancien : match_id, date, compétition, équipes, score. Équipe en français ou en anglais.",
         {"type": "object", "properties": {"team": {"type": "string"},
                                           "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
          "additionalProperties": False},
         "read", list_matches),
    Tool("match_events", "Événements d'un match résumés (minute, équipe, joueur, issue). event_type : tir, passe, "
         "faute, carton, but, dribble, interception, remplacement (ou nom StatsBomb).",
         {"type": "object", "properties": {"match_id": {"type": "integer"},
                                           "event_type": {"type": "string"},
                                           "team": {"type": "string"},
                                           "limit": {"type": "integer", "minimum": 1, "maximum": 50}},
          "required": ["match_id"], "additionalProperties": False},
         "read", match_events),
    Tool("team_stats", "Statistiques d'une équipe sur un match : buts, tirs, tirs cadrés, xG, passes, précision des "
         "passes (%), possession estimée (%). Hors tirs au but.",
         {"type": "object", "properties": {"match_id": {"type": "integer"}, "team": {"type": "string"}},
          "required": ["match_id", "team"], "additionalProperties": False},
         "compute", team_stats),
    Tool("plot_shots", "Carte des tirs d'une équipe sur un match (image PNG). Retourne le chemin, tirs et buts.",
         {"type": "object", "properties": {"match_id": {"type": "integer"}, "team": {"type": "string"}},
          "required": ["match_id", "team"], "additionalProperties": False},
         "compute", plot_shots),
    Tool("publish_report", "Publie le rapport d'avant-match d'une affiche. Action irréversible, confirmation requise.",
         {"type": "object", "properties": {"home_team": {"type": "string"}, "away_team": {"type": "string"},
                                           "title": {"type": "string"}, "content": {"type": "string"}},
          "required": ["home_team", "away_team", "title", "content"], "additionalProperties": False},
         "irreversible", publish_report, check_publish_report),
]}
