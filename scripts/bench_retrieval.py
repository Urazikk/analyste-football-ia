"""Mesure de la recherche du RAG sans LLM : Recall@5 et MRR sur les cas doc de tests.jsonl.

    python scripts/bench_retrieval.py                       # grille complète
    python scripts/bench_retrieval.py --models intfloat/multilingual-e5-small --sizes 1200

Compare modèles d'embeddings, modes (dense, bm25, hybride RRF) et tailles de morceaux.
Relève aussi le meilleur score dense des cas doc et absent, pour choisir le seuil d'abstention.
Sorties : results/retrieval.md et results/retrieval.jsonl.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import metrics, rag  # noqa: E402
from src.config import RESULTS_DIR  # noqa: E402

MODELS = ["intfloat/multilingual-e5-small", "BAAI/bge-m3"]
MODES = ["dense", "bm25", "hybrid"]
SIZES = [600, 1200, 2000]
K = 5
DEPTH = 50  # profondeur de classement pour le MRR


def load_cases() -> list[dict]:
    lines = (ROOT / "tests.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(l) for l in lines if l.strip()]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--models", nargs="+", default=MODELS)
    p.add_argument("--modes", nargs="+", default=MODES)
    p.add_argument("--sizes", nargs="+", type=int, default=SIZES)
    a = p.parse_args()

    cases = load_cases()
    docs = [c for c in cases if c["type"] == "doc"]
    absents = [c for c in cases if c["type"] == "absent"]
    rows = []
    for model in a.models:
        for size in a.sizes:
            t0 = time.perf_counter()
            index = rag.Index(rag.load_corpus(max_chars=size), model)
            build_s = time.perf_counter() - t0
            top_doc = [index.search(c["question"], 1, "dense")[0][1] for c in docs]
            top_abs = [index.search(c["question"], 1, "dense")[0][1] for c in absents]
            for mode in a.modes:
                t0 = time.perf_counter()
                per_case = []
                for c in docs:
                    ids = [ch.id for ch, _ in index.search(c["question"], DEPTH, mode)]
                    rel = c["expected"]["relevant_sources"]
                    per_case.append({"id": c["id"], "recall@5": metrics.recall_at_k(ids, rel, K),
                                     "mrr": metrics.mrr(ids, rel), "top5": ids[:K]})
                query_ms = (time.perf_counter() - t0) / len(docs) * 1000
                row = {"model": model, "mode": mode, "max_chars": size, "chunks": len(index.chunks),
                       "recall@5": statistics.mean(r["recall@5"] for r in per_case),
                       "mrr": statistics.mean(r["mrr"] for r in per_case),
                       "query_ms": query_ms, "index_s": build_s,
                       "top_dense_doc_min": min(top_doc), "top_dense_doc_mean": statistics.mean(top_doc),
                       "top_dense_absent_max": max(top_abs), "top_dense_absent_mean": statistics.mean(top_abs),
                       "cases": per_case}
                rows.append(row)
                print(f"{model:32s} {mode:6s} {size:5d}  R@5 {row['recall@5']:.2f}  MRR {row['mrr']:.2f}"
                      f"  {query_ms:.0f} ms/req", flush=True)

    RESULTS_DIR.mkdir(exist_ok=True)
    with (RESULTS_DIR / "retrieval.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    head = ("| Modèle | Mode | Taille | Morceaux | Recall@5 | MRR | ms/req | "
            "score dense doc (min / moy.) | score dense absent (max / moy.) |\n|---|---|---|---|---|---|---|---|---|\n")
    body = "".join(
        f"| {r['model'].split('/')[-1]} | {r['mode']} | {r['max_chars']} | {r['chunks']} | {r['recall@5']:.2f} | "
        f"{r['mrr']:.2f} | {r['query_ms']:.0f} | {r['top_dense_doc_min']:.3f} / {r['top_dense_doc_mean']:.3f} | "
        f"{r['top_dense_absent_max']:.3f} / {r['top_dense_absent_mean']:.3f} |\n" for r in rows)
    (RESULTS_DIR / "retrieval.md").write_text(
        f"# Recherche : {len(docs)} cas doc, {len(absents)} cas absents\n\n" + head + body, encoding="utf-8")
    print(f"\nÉcrit : {RESULTS_DIR / 'retrieval.md'}")


if __name__ == "__main__":
    main()
