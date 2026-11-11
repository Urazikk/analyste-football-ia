"""Métriques de l'évaluation, identiques pour tous les niveaux."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


# Tirets et signe moins Unicode -> trait d'union : le modèle écrit souvent « 3‑3 » (U+2011) ou « 3 – 3 » (U+2013)
_DASHES = str.maketrans({c: "-" for c in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\u2043\ufe63\uff0d"})


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower()).translate(_DASHES)
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


def term_in(term: str, text: str) -> bool:
    """Terme présent dans un texte normalisé. Un nombre en début ou en fin de terme doit apparaître entier :
    « 6 » ne compte pas dans « 16 », « 2026 » ou « 6,5 », ni « 1 m » dans « 11 m »."""
    t = _norm(term)
    before = r"(?<![\d.,])" if t[:1].isdigit() else ""
    after = r"(?!\d|[.,]\d)" if t[-1:].isdigit() else ""
    return re.search(before + re.escape(t) + after, text) is not None


def keywords_match(answer: str, groups: list[list[str]]) -> bool:
    """Exactitude par règles : chaque groupe doit avoir au moins un synonyme présent."""
    a = _norm(answer)
    return all(any(term_in(w, a) for w in group) for group in groups)


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
            # chaque élément : un mot, ou un groupe de synonymes dont un seul suffit
            groups = [[w] if isinstance(w, str) else w for w in c.get("must_contain", [])]
            if not keywords_match(content, groups):
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


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_in(text: str) -> list[float]:
    """Nombres d'un texte, virgule ou point décimal (« 0,85 » et « 0.85 » donnent 0.85)."""
    return [float(n.replace(",", ".")) for n in _NUMBER.findall(text)]


def unsupported_numbers(report: str, tool_outputs: list[str]) -> list[float]:
    """Chiffres du rapport absents des sorties d'outils du run, arrondis tolérés (58,1 cité 58).

    Diagnostic de fidélité du niveau 2 : ne change pas le succès de la tâche.
    """
    seen = {round(x, d) for out in tool_outputs for x in numbers_in(out) for d in (0, 1, 2)}
    return sorted({x for x in numbers_in(report) if x not in seen})


def bootstrap_ci(xs: list[float], b: int = 2000, seed: int = 42, alpha: float = 0.05) -> tuple[float, float] | None:
    """Intervalle de confiance de la moyenne par bootstrap percentile (graine fixée) ; None si moins de 2 valeurs."""
    import random

    xs = [float(x) for x in xs if x is not None]
    if len(xs) < 2:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(xs, k=len(xs))) / len(xs) for _ in range(b))
    return means[int(b * alpha / 2)], means[int(b * (1 - alpha / 2)) - 1]


def paired_bootstrap(a: list[float], b_: list[float], b: int = 2000, seed: int = 42) -> dict[str, float]:
    """Différence moyenne b_ - a sur les mêmes cas : intervalle à 95 % et part des tirages où elle est <= 0."""
    import random

    d = [float(y) - float(x) for x, y in zip(a, b_)]
    rng = random.Random(seed)
    means = sorted(sum(rng.choices(d, k=len(d))) / len(d) for _ in range(b))
    return {"diff": sum(d) / len(d), "lo": means[int(b * 0.025)], "hi": means[int(b * 0.975) - 1],
            "p_le_0": sum(m <= 0 for m in means) / b}
