"""Comparaison appariée des niveaux sur les mêmes cas, sans appel : python scripts/compare_levels.py

Pour chaque paire de niveaux et chaque métrique, différence moyenne (niveau b moins niveau a) sur les cas
communs, intervalle à 95 % par bootstrap apparié, et part des tirages où la différence est <= 0
(proche de 0 : le niveau b fait mieux de façon fiable). Sortie : results/comparaison.md.
"""
from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import eval as ev  # noqa: E402
from src import config, metrics  # noqa: E402
from src.config import RESULTS_DIR, SEED  # noqa: E402

METRICS = {"Exactitude": ("doc", "correct"), "Citation": ("doc", "cited"), "Fidélité": ("doc", "faithful"),
           "Recall@5": ("doc", "recall@5"), "Abstention": ("absent", "correct"),
           "Ambigu": ("ambiguous", "correct"), "Succès tâches": ("task", "correct")}


def per_case(level: int) -> dict[tuple[str, str], dict[str, float]]:
    """(type, id) -> valeurs du premier essai, pour le modèle courant, hors cas en erreur."""
    rows = ev._read_rows(RESULTS_DIR / f"raw_level{level}.jsonl")
    return {(r["type"], r["id"]): r for r in rows
            if r.get("trial", 0) == 0 and r.get("model") == config.LLM_MODEL and not r.get("error")}


def compare(levels: list[int]) -> str:
    data = {lv: per_case(lv) for lv in levels}
    lines = ["| Niveaux | Métrique | Cas communs | a | b | b − a [IC 95 %] | P(b − a ≤ 0) |", "|---|---|---|---|---|---|---|"]
    for a, b in itertools.combinations(levels, 2):
        for name, (kind, key) in METRICS.items():
            common = sorted(k for k in data[a].keys() & data[b].keys()
                            if k[0] == kind and data[a][k].get(key) is not None and data[b][k].get(key) is not None)
            if len(common) < 2:
                continue
            xa = [float(data[a][k][key]) for k in common]
            xb = [float(data[b][k][key]) for k in common]
            r = metrics.paired_bootstrap(xa, xb, seed=SEED)
            lines.append(f"| {a} → {b} | {name} | {len(common)} | {sum(xa) / len(xa):.2f} | {sum(xb) / len(xb):.2f} | "
                         f"{r['diff']:+.2f} [{r['lo']:+.2f} ; {r['hi']:+.2f}] | {r['p_le_0']:.3f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--levels", type=int, nargs="+", default=[0, 1, 2, 3])
    a = p.parse_args()
    levels = [lv for lv in a.levels if (RESULTS_DIR / f"raw_level{lv}.jsonl").exists()]
    table = compare(levels)
    (RESULTS_DIR / "comparaison.md").write_text(
        f"# Comparaison appariée des niveaux ({config.LLM_MODEL})\n\n" + table + "\n", encoding="utf-8")
    print(table)
