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

def report_path(home_team: str, away_team: str):
    """Un rapport par affiche : STATE_DIR/reports/<domicile>-vs-<exterieur>.json"""
    slug = lambda s: re.sub(r"[^a-z0-9]+", "-", unicodedata.normalize("NFKD", s.lower())  # noqa: E731
                            .encode("ascii", "ignore").decode()).strip("-")
    return config.state_dir() / "reports" / f"{slug(home_team)}-vs-{slug(away_team)}.json"


def publish_report(home_team: str, away_team: str, title: str, content: str) -> dict[str, Any]:
    """Publie le rapport d'avant-match d'une affiche. Irréversible."""
    path = report_path(home_team, away_team)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"home_team": home_team, "away_team": away_team, "title": title,
                                "content": content}, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"published": True, "path": str(path)}


def check_publish_report(args: dict[str, Any]) -> list[str]:
    errors = []
    if report_path(args.get("home_team", ""), args.get("away_team", "")).exists():
        errors.append("Un rapport est déjà publié pour cette affiche.")
    if len(args.get("content", "").strip()) < 200:
        errors.append("Rapport trop court (200 caractères minimum).")
    # À compléter (Gautier) : équipes présentes dans les données, équipes différentes,
    # chiffres cités présents dans les résultats d'outils...
    return errors


REGISTRY: dict[str, Tool] = {t.name: t for t in [
    Tool("search_rules", "Cherche dans les lois du jeu (IFAB 2026/27) et Wikipédia. Renvoie des extraits avec leur "
         "identifiant, à citer entre crochets dans la réponse. À utiliser pour toute question sur les règles.",
         {"type": "object", "properties": {"query": {"type": "string", "minLength": 3},
                                           "k": {"type": "integer", "minimum": 1, "maximum": 8}},
          "required": ["query"], "additionalProperties": False},
         "read", search_rules),
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
    Tool("publish_report", "Publie le rapport d'avant-match d'une affiche. Action irréversible, confirmation requise.",
         {"type": "object", "properties": {"home_team": {"type": "string"}, "away_team": {"type": "string"},
                                           "title": {"type": "string"}, "content": {"type": "string"}},
          "required": ["home_team", "away_team", "title", "content"], "additionalProperties": False},
         "irreversible", publish_report, check_publish_report),
]}
