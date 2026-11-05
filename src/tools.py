"""Outils de l'agent : schéma JSON, classe d'effet, règles métier vérifiées par du code."""
from __future__ import annotations

import json
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


# Outils de lecture (StatsBomb) --------------------------------------------------

def list_matches(team: str | None = None) -> list[dict[str, Any]]:
    """Matchs des compétitions retenues, filtrés par équipe."""
    raise NotImplementedError("Semaine 3 : fixer config.COMPETITIONS d'abord")


def match_events(match_id: int, event_type: str | None = None, team: str | None = None) -> list[dict[str, Any]]:
    raise NotImplementedError("Semaine 3")


def team_stats(match_id: int, team: str) -> dict[str, Any]:
    raise NotImplementedError("Semaine 3")


def plot_shots(match_id: int, team: str) -> str:
    """Génère une carte des tirs, retourne le chemin de l'image."""
    raise NotImplementedError("Semaine 3")


# Outil qui agit -----------------------------------------------------------------

def publish_report(match_id: int, title: str, content: str) -> dict[str, Any]:
    """Publie le rapport d'avant-match (écrit dans STATE_DIR/reports). Irréversible."""
    out = config.state_dir() / "reports"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{match_id}.json"
    path.write_text(json.dumps({"match_id": match_id, "title": title, "content": content},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return {"published": True, "path": str(path)}


def check_publish_report(args: dict[str, Any]) -> list[str]:
    errors = []
    if (config.state_dir() / "reports" / f"{args.get('match_id')}.json").exists():
        errors.append("Un rapport est déjà publié pour ce match.")
    if len(args.get("content", "").strip()) < 200:
        errors.append("Rapport trop court (200 caractères minimum).")
    # À compléter : match existant et pas encore joué, chiffres cités présents dans les données...
    return errors


REGISTRY: dict[str, Tool] = {t.name: t for t in [
    Tool("list_matches", "Liste les matchs disponibles, filtrables par équipe.",
         {"type": "object", "properties": {"team": {"type": "string"}}, "additionalProperties": False},
         "read", list_matches),
    Tool("match_events", "Événements d'un match (tirs, passes...), filtrables par type et équipe.",
         {"type": "object", "properties": {"match_id": {"type": "integer"},
                                           "event_type": {"type": "string"},
                                           "team": {"type": "string"}},
          "required": ["match_id"], "additionalProperties": False},
         "read", match_events),
    Tool("team_stats", "Statistiques agrégées d'une équipe sur un match (tirs, xG, possession...).",
         {"type": "object", "properties": {"match_id": {"type": "integer"}, "team": {"type": "string"}},
          "required": ["match_id", "team"], "additionalProperties": False},
         "compute", team_stats),
    Tool("plot_shots", "Carte des tirs d'une équipe sur un match. Retourne le chemin de l'image.",
         {"type": "object", "properties": {"match_id": {"type": "integer"}, "team": {"type": "string"}},
          "required": ["match_id", "team"], "additionalProperties": False},
         "compute", plot_shots),
    Tool("publish_report", "Publie le rapport d'avant-match. Action irréversible, confirmation requise.",
         {"type": "object", "properties": {"match_id": {"type": "integer"}, "title": {"type": "string"},
                                           "content": {"type": "string"}},
          "required": ["match_id", "title", "content"], "additionalProperties": False},
         "irreversible", publish_report, check_publish_report),
]}
