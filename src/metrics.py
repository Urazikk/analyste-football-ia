"""Métriques de l'évaluation, identiques pour tous les niveaux."""
from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def is_relevant(chunk_id: str, relevant: list[str]) -> bool:
    """Un morceau est pertinent si son id commence par un id attendu (document ou section)."""
    return any(chunk_id == r or chunk_id.startswith(r + "#") or chunk_id.startswith(r + "/")
               for r in relevant)


def recall_at_k(retrieved: list[str], relevant: list[str], k: int = 5) -> float:
    """Part des sources attendues retrouvées dans les k premiers morceaux."""
    if not relevant:
        return 0.0
    found = {r for r in relevant if any(is_relevant(c, [r]) for c in retrieved[:k])}
    return len(found) / len(set(relevant))


def mrr(retrieved: list[str], relevant: list[str]) -> float:
    for rank, chunk_id in enumerate(retrieved, start=1):
        if is_relevant(chunk_id, relevant):
            return 1.0 / rank
    return 0.0


def keywords_match(answer: str, groups: list[list[str]]) -> bool:
    """Exactitude par règles : chaque groupe doit avoir au moins un synonyme présent."""
    a = _norm(answer)
    return all(any(_norm(w) in a for w in group) for group in groups)


def cites_relevant(sources: list[str], relevant: list[str]) -> bool:
    return any(is_relevant(s, relevant) for s in sources)


def check_state(checks: list[dict[str, Any]], state_dir: Path) -> bool:
    """Vérifie l'état final d'une tâche multi-étapes par du code."""
    for c in checks:
        kind = c["kind"]
        if kind == "report_published":
            p = state_dir / "reports" / f"{c['report']}.json"
            if not p.exists():
                return False
            content = _norm(json.loads(p.read_text(encoding="utf-8"))["content"])
            if not all(_norm(w) in content for w in c.get("must_contain", [])):
                return False
        elif kind == "no_report":
            if (state_dir / "reports").exists() and any((state_dir / "reports").iterdir()):
                return False
        else:
            raise ValueError(f"Vérification inconnue : {kind}")
    return True


def pass_hat_k(trials: list[bool]) -> bool:
    """pass^k : la tâche réussit seulement si les k essais réussissent."""
    return bool(trials) and all(trials)
