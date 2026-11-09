"""Robustesse aux reformulations (axe A3 de docs/plan.md), sur tests_robustesse.jsonl.

    python scripts/robustesse.py --retrieval      # recherche seule, sans LLM : Recall@5 et MRR par style
    python eval.py --tests tests_robustesse.jsonl --out results/robustesse --levels 0 1 2 --resume
    python scripts/robustesse.py                  # réponses : exactitude par style et stabilité

Stabilité : part des reformulations dont l'exactitude est la même que celle de la question d'origine
(résultats de results/raw_level{n}.jsonl). Sortie : results/robustesse/robustesse.md.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import eval as ev  # noqa: E402
from src import config, metrics  # noqa: E402
from src.config import RESULTS_DIR  # noqa: E402

OUT = RESULTS_DIR / "robustesse"


def load() -> list[dict]:
    return ev.load_tests(ROOT / "tests_robustesse.jsonl")


def retrieval_table(cases: list[dict]) -> str:
    from src import rag

    originals = {c["id"]: c for c in ev.load_tests() if c["type"] == "doc"}
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in cases:
        groups[c["style"]].append(c)
    groups["origine"] = [originals[o] for o in sorted({c["original"] for c in cases})]
    lines = ["| Style | Cas | Recall@5 | MRR |", "|---|---|---|---|"]
    for style in ("origine", "familier", "situation"):
        rec, mrr = [], []
        for c in groups[style]:
            ids = [ch.id for ch, _ in rag.search(c["question"], 50)]
            rel = c["expected"]["relevant_sources"]
            rec.append(metrics.recall_at_k(ids, rel, 5))
            mrr.append(metrics.mrr(ids, rel))
        lines.append(f"| {style} | {len(rec)} | {statistics.mean(rec):.2f} | {statistics.mean(mrr):.2f} |")
    return "\n".join(lines)


def answers_table(cases: list[dict]) -> str:
    lines = ["| Niveau | Style | Cas | Exactitude (reformulation) | Exactitude (origine) | Stabilité |", "|---|---|---|---|---|---|"]
    by_id = {c["id"]: c for c in cases}
    for level in (0, 1, 2, 3):
        para = {r["id"]: r for r in ev._read_rows(OUT / f"raw_level{level}.jsonl")
                if r.get("model") == config.LLM_MODEL and not r.get("error")}
        orig = {r["id"]: r for r in ev._read_rows(RESULTS_DIR / f"raw_level{level}.jsonl")
                if r.get("model") == config.LLM_MODEL and not r.get("error") and r.get("trial", 0) == 0}
        for style in ("familier", "situation"):
            pairs = [(bool(r["correct"]), bool(orig[by_id[i]["original"]]["correct"]))
                     for i, r in para.items() if i in by_id and by_id[i]["style"] == style and by_id[i]["original"] in orig]
            if pairs:
                lines.append(f"| {level} | {style} | {len(pairs)} | {statistics.mean(p for p, _ in pairs):.2f} | "
                             f"{statistics.mean(o for _, o in pairs):.2f} | {statistics.mean(p == o for p, o in pairs):.2f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--retrieval", action="store_true")
    a = p.parse_args()
    cases = load()
    OUT.mkdir(parents=True, exist_ok=True)
    name, table = ("recherche.md", retrieval_table(cases)) if a.retrieval else ("robustesse.md", answers_table(cases))
    (OUT / name).write_text(f"# Robustesse aux reformulations ({'recherche, sans LLM' if a.retrieval else config.LLM_MODEL})\n\n"
                            + table + "\n", encoding="utf-8")
    print(table)
