"""Reproduit le tableau de résultats : python eval.py

Options : --levels 0 1 2 3  --trials 3  --limit N
Sorties : results/raw_level{n}.jsonl (une ligne par cas et essai) et results/table.md.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import tempfile
from pathlib import Path
from typing import Any, Callable

from src import agent, llm, metrics, rag
from src.config import RESULTS_DIR, ROOT, SEED
from src.result import Result

LEVELS: dict[int, Callable[[str], Result]] = {
    0: llm.answer,
    1: rag.answer,
    # En éval, l'utilisateur simulé valide toute action demandée : on vérifie l'état final.
    2: lambda q: agent.answer(q, confirm=lambda name, args: True),
    # 3: extension, semaine 4
}


def load_tests(path: Path = ROOT / "tests.jsonl") -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_case(fn: Callable[[str], Result], case: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as state:
        os.environ["STATE_DIR"] = state
        res = fn(case["question"])
        row: dict[str, Any] = {"id": case["id"], "type": case["type"], **res.to_dict()}
        exp = case.get("expected", {})
        if case["type"] == "doc":
            rel = exp.get("relevant_sources", [])
            row["recall@5"] = metrics.recall_at_k(res.retrieved, rel) if res.retrieved else None
            row["mrr"] = metrics.mrr(res.retrieved, rel) if res.retrieved else None
            row["correct"] = metrics.keywords_match(res.answer, exp.get("keywords", [])) and not res.abstained
            row["cited"] = metrics.cites_relevant(res.sources, rel)
        elif case["type"] == "absent":
            row["correct"] = res.abstained
        elif case["type"] == "ambiguous":
            row["correct"] = res.clarified if exp.get("behavior") == "clarify" else res.refused
        elif case["type"] == "task":
            row["correct"] = metrics.check_state(exp.get("checks", []), Path(state))
    return row


def _mean(xs: list[Any]) -> float | None:
    xs = [float(x) for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def summarize(level: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = [r for r in rows if r["trial"] == 0]
    by = lambda t: [r for r in first if r["type"] == t]  # noqa: E731
    tasks: dict[str, list[bool]] = {}
    for r in rows:
        if r["type"] == "task":
            tasks.setdefault(r["id"], []).append(bool(r["correct"]))
    return {
        "niveau": level,
        "Recall@5": _mean([r.get("recall@5") for r in by("doc")]),
        "MRR": _mean([r.get("mrr") for r in by("doc")]),
        "Exactitude": _mean([r["correct"] for r in by("doc")]),
        "Citation": _mean([r.get("cited") for r in by("doc")]) if level > 0 else None,
        "Abstention": _mean([r["correct"] for r in by("absent")]),
        "Ambigu": _mean([r["correct"] for r in by("ambiguous")]),
        "Succès tâches": _mean([r["correct"] for r in by("task")]),
        "pass^3": _mean([metrics.pass_hat_k(v) for v in tasks.values()]),
        "Tokens/req": _mean([r["tokens_in"] + r["tokens_out"] for r in first]),
        "Latence (s)": _mean([r["latency_s"] for r in first]),
    }


def to_markdown(summaries: list[dict[str, Any]]) -> str:
    cols = list(summaries[0])
    fmt = lambda v: "—" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))  # noqa: E731
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(fmt(s[c]) for c in cols) + " |" for s in summaries]
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--levels", type=int, nargs="+", default=sorted(LEVELS))
    p.add_argument("--trials", type=int, default=3, help="essais par tâche multi-étapes (pass^k)")
    p.add_argument("--limit", type=int, default=None)
    a = p.parse_args()

    random.seed(SEED)
    tests = load_tests()[: a.limit]
    RESULTS_DIR.mkdir(exist_ok=True)
    summaries = []
    for level in a.levels:
        fn = LEVELS.get(level)
        if fn is None:
            print(f"Niveau {level} absent, ignoré.")
            continue
        rows: list[dict[str, Any]] = []
        try:
            for case in tests:
                n = a.trials if case["type"] == "task" else 1
                for trial in range(n):
                    rows.append({**run_case(fn, case), "trial": trial})
                    print(f"[niveau {level}] {case['id']} essai {trial}")
        except NotImplementedError as e:
            print(f"Niveau {level} non implémenté : {e}")
            continue
        with (RESULTS_DIR / f"raw_level{level}.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
        summaries.append(summarize(level, rows))

    if summaries:
        table = to_markdown(summaries)
        (RESULTS_DIR / "table.md").write_text(table + "\n", encoding="utf-8")
        print("\n" + table)


if __name__ == "__main__":
    main()
