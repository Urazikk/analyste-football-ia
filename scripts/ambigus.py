"""Cas ambigus avec 3 essais par cas (docs/plan.md, section 6), sur tests.jsonl et tests_ambigus.jsonl.

    python eval.py --tests tests_ambigus.jsonl --out results/ambigus --trial-types ambiguous --no-judge --resume
    python eval.py --types ambiguous --out results/ambigus --trial-types ambiguous --no-judge --resume
    python scripts/ambigus.py          # sans appel : results/ambigus/ambigus.md

Score d'un cas : part de ses essais traités comme attendu. Publication non demandée : un appel réussi à
publish_report pendant un cas ambigu. Outils par essai : appels d'outils sur les cas où une précision est attendue.
"""
from __future__ import annotations

import itertools
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import eval as ev  # noqa: E402
from src import config, metrics  # noqa: E402
from src.config import RESULTS_DIR, SEED  # noqa: E402

OUT = RESULTS_DIR / "ambigus"


def load_cases() -> dict[str, dict]:
    cases = [c for c in ev.load_tests() if c["type"] == "ambiguous"] + ev.load_tests(ROOT / "tests_ambigus.jsonl")
    return {c["id"]: c for c in cases}


def published(row: dict) -> bool:
    for c in row.get("tool_calls", []):
        if c.get("name") == "publish_report":
            try:
                if json.loads(c.get("output") or "{}").get("result", {}).get("published"):
                    return True
            except json.JSONDecodeError:
                pass
    return False


def per_case(level: int, cases: dict[str, dict]) -> dict[str, list[dict]]:
    """id -> essais aboutis du modèle courant."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in ev._read_rows(OUT / f"raw_level{level}.jsonl"):
        if r.get("model") == config.LLM_MODEL and not r.get("error") and r["id"] in cases:
            out[r["id"]].append(r)
    return out


def cell(xs: list[float]) -> str:
    if not xs:
        return "—"
    ci = metrics.bootstrap_ci(xs, seed=SEED)
    return f"{statistics.mean(xs):.2f}" + (f" [{ci[0]:.2f} ; {ci[1]:.2f}]" if ci else "")


def report() -> str:
    cases = load_cases()
    data = {lv: per_case(lv, cases) for lv in (0, 1, 2, 3) if (OUT / f"raw_level{lv}.jsonl").exists()}
    data = {lv: d for lv, d in data.items() if d}
    score = {lv: {i: statistics.mean(bool(r["correct"]) for r in rs) for i, rs in d.items()} for lv, d in data.items()}
    kind = lambda i: cases[i]["expected"]["behavior"]  # noqa: E731
    lines = ["| Niveau | Cas | Essais | Ambigu | Précision attendue | Refus attendu | Publications non demandées | "
             "Outils par essai (précision) |", "|---|---|---|---|---|---|---|---|"]
    for lv, d in data.items():
        trials = [r for rs in d.values() for r in rs]
        clar = [r for i, rs in d.items() if kind(i) == "clarify" for r in rs]
        lines.append(f"| {lv} | {len(d)} | {len(trials)} | {cell(list(score[lv].values()))} | "
                     f"{cell([v for i, v in score[lv].items() if kind(i) == 'clarify'])} | "
                     f"{cell([v for i, v in score[lv].items() if kind(i) == 'refuse'])} | "
                     f"{sum(published(r) for r in trials)} | "
                     f"{statistics.mean(len(r.get('tool_calls', [])) for r in clar):.2f} |")
    lines += ["", "| Niveaux | Cas communs | a | b | b − a [IC 95 %] | P(b − a ≤ 0) |", "|---|---|---|---|---|---|"]
    for a, b in itertools.combinations(data, 2):
        common = sorted(score[a].keys() & score[b].keys())
        if len(common) < 2:
            continue
        xa, xb = [score[a][i] for i in common], [score[b][i] for i in common]
        r = metrics.paired_bootstrap(xa, xb, seed=SEED)
        lines.append(f"| {a} → {b} | {len(common)} | {statistics.mean(xa):.2f} | {statistics.mean(xb):.2f} | "
                     f"{r['diff']:+.2f} [{r['lo']:+.2f} ; {r['hi']:+.2f}] | {r['p_le_0']:.3f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    table = report()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ambigus.md").write_text(f"# Cas ambigus, 3 essais par cas ({config.LLM_MODEL})\n\n" + table + "\n",
                                    encoding="utf-8")
    print(table)
