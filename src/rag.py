"""Niveau 1 : RAG (découpage, embeddings, recherche dense ou hybride, citations, abstention).

À implémenter en semaine 2. Choix à justifier par des mesures (docs/decisions.md) :
taille des morceaux, modèle d'embeddings, dense seul vs hybride dense + BM25, seuil d'abstention.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.result import Result


@dataclass
class Chunk:
    id: str        # ex. "loi-11#2" : identifiant cité dans la réponse
    source: str    # document d'origine
    text: str


def load_corpus() -> list[Chunk]:
    """Lit data/corpus/ et découpe en morceaux."""
    raise NotImplementedError("Niveau 1 : semaine 2")


def search(query: str, k: int = 5) -> list[tuple[Chunk, float]]:
    """Retourne les k meilleurs morceaux avec leur score."""
    raise NotImplementedError("Niveau 1 : semaine 2")


def answer(question: str) -> Result:
    """Recherche, puis réponse qui cite ses sources ou s'abstient."""
    raise NotImplementedError("Niveau 1 : semaine 2")
