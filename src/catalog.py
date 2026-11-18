"""Contenu proposé dans l'interface : questions d'exemple et matchs à analyser.

Les questions viennent du jeu de test ou du scénario de la vidéo (réponses connues) ; chacune indique le niveau
le plus parlant. Les matchs sont lus dans les données StatsBomb en cache.
"""
from __future__ import annotations

from typing import Any

# (catégorie, [(question, niveau conseillé, ce que la question montre)])
QUESTIONS: list[tuple[str, list[tuple[str, int, str]]]] = [
    ("Lois du jeu", [
        ("À quelle distance du ballon doivent se placer les adversaires lors d'un coup franc ?", 1, "réponse citée"),
        ("Un but peut-il être marqué directement sur corner ?", 1, "réponse citée"),
        ("Quelles parties du corps sont prises en compte pour juger une position de hors-jeu ?", 1, "réponse citée"),
        ("Où le gardien de but doit-il se placer lors de l'exécution d'un penalty ?", 1, "réponse citée"),
        ("Combien de remplacements une équipe peut-elle effectuer au maximum dans un match de compétition "
         "officielle ?", 1, "réponse citée"),
    ]),
    ("Données de match", [
        ("Combien de tirs cadrés l'Espagne a-t-elle réalisés lors de la finale de l'Euro 2024 ?", 3, "outils"),
        ("Quelle est la forme de l'Argentine sur ses cinq derniers matchs disponibles ?", 3, "outils"),
        ("Combien de fois la France et l'Argentine se sont-elles affrontées dans les données ?", 3, "outils"),
        ("Montre la carte des tirs du Maroc lors de son dernier match disponible.", 3, "graphique"),
    ]),
    ("Rapports d'avant-match", [
        ("Prépare et publie le rapport d'avant-match Angleterre - Espagne avec le nombre de tirs cadrés de "
         "l'Espagne lors de la finale de l'Euro 2024.", 3, "action à valider"),
        ("Publie le rapport d'avant-match Allemagne - Espagne avec le nombre de tirs de chaque équipe lors de "
         "leur quart de finale de l'Euro 2024.", 3, "action à valider"),
        ("Prépare une analyse d'avant-match France - Portugal, sans rien publier.", 3, "sans publication"),
    ]),
    ("Cas limites", [
        ("Quelle est la durée maximale d'un contrat de joueur professionnel ?", 1, "abstention"),
        ("Publie le rapport d'avant-match de la Coupe du monde 2026.", 3, "demande de précision"),
        ("Qui a gagné le match ?", 2, "le niveau 2 devine, le niveau 3 demande"),
        ("Donne-moi une recette de crêpes.", 3, "refus"),
    ]),
]

STAGES = {"Final": "finale", "3rd Place Final": "match pour la 3e place", "Semi-finals": "demi-finale",
          "Quarter-finals": "quart de finale", "Round of 16": "huitième de finale", "Group Stage": "phase de groupes"}


def competition(m: dict[str, Any]) -> str:
    """« Euro 2024 », « Coupe du monde 2018 »... (l'Euro 2020 s'est joué en 2021)."""
    year = int(m["date"][:4])
    if "Euro" in m["competition"]:
        return f"Euro {2020 if year == 2021 else year}"
    if "Copa" in m["competition"]:
        return f"Copa América {year}"
    return f"Coupe du monde {year}"


def french(team: str) -> str:
    from src.animation import french as fr

    return fr(team)


def matches() -> list[dict[str, Any]]:
    """Tous les matchs en cache, du plus récent au plus ancien, avec un libellé en français."""
    from src import tools

    out = []
    for m in tools.list_matches(None, limit=1000):
        home, away = french(m["home_team"]), french(m["away_team"])
        stage = STAGES.get(m["stage"], m["stage"])
        out.append({**m, "home_fr": home, "away_fr": away, "competition_fr": competition(m), "stage_fr": stage,
                    "label": f"{home} {m['score']} {away}  ·  {competition(m)}, {stage}  ·  {m['date']}"})
    return out


def match_questions(m: dict[str, Any]) -> list[tuple[str, str, int]]:
    """Analyses proposées pour un match : (libellé court, question, niveau conseillé)."""
    home, away, comp, stage = m["home_fr"], m["away_fr"], m["competition_fr"], m["stage_fr"]
    where = f"le match {home} - {away} ({stage}, {comp}, {m['date']})"
    return [
        ("Statistiques", f"Donne les statistiques des deux équipes pour {where} : tirs, tirs cadrés, xG, passes "
                         "réussies et possession.", 3),
        ("Carte des tirs", f"Montre la carte des tirs de chaque équipe pour {where}.", 3),
        ("Buts et cartons", f"Quels ont été les buts et les cartons de {where} ?", 3),
        ("Rapport d'avant-match", f"Prépare et publie le rapport d'avant-match {home} - {away}, en citant les "
                                  f"chiffres de leur confrontation du {m['date']}.", 3),
    ]
