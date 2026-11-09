"""Benchmark de modèles au niveau 2 : un tableau par modèle depuis results/raw_level2.jsonl, sans appel.

Lancer d'abord, pour chaque modèle (résultats ajoutés au même fichier, étiquetés par modèle) :
    python eval.py --levels 2 --types task --model qwen/qwen3.8-27b --resume
    python eval.py --levels 2 --types task --model qwen3:8b --base-url http://localhost:11434/v1 --resume
Puis : python scripts/bench_models.py   ->  results/bench-llm.md
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import eval as ev  # noqa: E402
from src.config import RESULTS_DIR  # noqa: E402

COLS = ["modèle", "Cas", "Succès tâches", "pass^3", "Chiffres non soutenus", "Erreurs",
        "Tokens/req", "Latence (s)", "Coût/req ($)"]


def main(raw: Path = RESULTS_DIR / "raw_level2.jsonl", out: Path = RESULTS_DIR / "bench-llm.md") -> str:
    by_model: dict[str, list] = defaultdict(list)
    for r in ev._read_rows(raw):
        if r["type"] == "task":
            by_model[r["model"]].append(r)
    if not by_model:
        raise SystemExit(f"Aucune tâche dans {raw} : lancer eval.py --levels 2 --types task d'abord.")
    rows = []
    for model, rs in sorted(by_model.items()):
        s = ev.summarize(2, rs)
        s["modèle"] = model
        s["Cas"] = f"{len({r['id'] for r in rs})} tâches, {len(rs)} essais"
        rows.append({c: s[c] for c in COLS})
    table = ev.to_markdown(rows)
    out.write_text("# Benchmark de modèles, niveau 2 (tâches multi-étapes)\n\n" + table + "\n", encoding="utf-8")
    print(table)
    return table


if __name__ == "__main__":
    main()
