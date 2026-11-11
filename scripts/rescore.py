"""Recalcule l'exactitude des résultats bruts avec les métriques actuelles, sans appel au LLM.

Sert quand une métrique est corrigée après coup (ex. tirets Unicode dans « 3‑3 », docs/decisions.md) :
- doc  : mots clés sur la réponse enregistrée, et pas d'abstention ;
- task : état final reconstruit à partir des appels réussis à publish_report enregistrés dans tool_calls
         (contenu, équipes), vérifié par metrics.check_state comme pendant l'évaluation.
Les autres types et champs ne changent pas.

Usage : python scripts/rescore.py [--check] [results/raw_level2.jsonl ...]
  --check : n'écrit rien, affiche les lignes dont le score changerait.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import eval as ev  # noqa: E402
from src import metrics, tools  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def published_reports(row: dict) -> list[dict]:
    """Rapports réellement écrits pendant l'essai : appels à publish_report dont la sortie dit published."""
    out = []
    for c in row.get("tool_calls", []):
        if c.get("name") != "publish_report":
            continue
        try:
            res = json.loads(c.get("output") or "{}")
            args = json.loads(c["arguments"]) if isinstance(c["arguments"], str) else c["arguments"]
        except (json.JSONDecodeError, KeyError):
            continue
        if res.get("ok") and res.get("result", {}).get("published"):
            out.append(args)
    return out


def task_correct(row: dict, case: dict) -> bool:
    """Rejoue check_state sur un STATE_DIR reconstruit (un fichier par rapport publié, nom calculé par le code)."""
    with tempfile.TemporaryDirectory() as state:
        old = os.environ.get("STATE_DIR")
        os.environ["STATE_DIR"] = state
        try:
            for a in published_reports(row):
                p = tools.report_path(a.get("home_team", ""), a.get("away_team", ""))
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps({"content": a.get("content", "")}, ensure_ascii=False), encoding="utf-8")
            return metrics.check_state(case["expected"].get("checks", []), Path(state))
        finally:
            if old is None:
                os.environ.pop("STATE_DIR", None)
            else:
                os.environ["STATE_DIR"] = old


def rescore_row(row: dict, case: dict) -> bool | None:
    """Nouvelle valeur de correct, ou None si la ligne ne se recalcule pas (erreur, autre type)."""
    if row.get("error"):
        return None
    if row["type"] == "doc":
        return metrics.keywords_match(row.get("answer", ""), case["expected"].get("keywords", [])) \
            and not row.get("abstained")
    if row["type"] == "task":
        return task_correct(row, case)
    return None


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="*", type=Path)
    p.add_argument("--check", action="store_true")
    p.add_argument("--tests", type=Path, default=ROOT / "tests.jsonl")
    a = p.parse_args()
    cases = {c["id"]: c for c in ev.load_tests(a.tests)}
    files = a.files or sorted((ROOT / "results").glob("raw_level*.jsonl"))
    for path in files:
        rows, changed = ev._read_rows(path), []
        for r in rows:
            case = cases.get(r["id"])
            new = rescore_row(r, case) if case else None
            if new is not None and new != r.get("correct"):
                changed.append((r.get("model"), r["id"], r.get("trial", 0), r.get("correct"), new))
                r["correct"] = new
        print(f"{path.name} : {len(changed)} ligne(s) changée(s) sur {len(rows)}")
        for c in changed:
            print("  ", *c)
        if changed and not a.check:
            path.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
