"""Reproduit le tableau de résultats : python eval.py

Options : --levels 0 1 2 3  --trials 3  --limit N  --resume  --table-only  --no-judge
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

from src import agent, config, judge, llm, metrics, rag
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


def _slim(call: dict[str, Any]) -> dict[str, Any]:
    """Sortie de search_rules réduite aux identifiants : pas de texte IFAB dans results/ (licence)."""
    if call.get("name") != "search_rules":
        return call
    out = json.loads(call.get("output") or "{}")
    ids = [r["id"] for r in out.get("result", [])] if out.get("ok") else None
    return {**call, "output": json.dumps({"ok": out.get("ok"), "ids": ids, "error": out.get("error")}, ensure_ascii=False)}


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def _key(r: dict[str, Any]) -> tuple[Any, ...]:
    return r.get("model"), r["id"], r.get("trial", 0)


def _write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    """Écrit les lignes du run en gardant celles des autres cas et des autres modèles déjà présentes.

    Sans cela, `--types task` ou `--model qwen...` effaçait les résultats précédents du même niveau.
    """
    new = {_key(r) for r in rows}
    rows = [r for r in _read_rows(path) if _key(r) not in new] + rows
    path.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows), encoding="utf-8")


def run_case(fn: Callable[[str], Result], case: dict[str, Any], use_judge: bool = False, level: int = -1) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as state:
        os.environ["STATE_DIR"] = state
        try:
            res = fn(case["question"])
        except NotImplementedError:
            raise
        except Exception as e:  # quota, réseau... : le cas est noté en erreur, l'évaluation continue
            res = Result(level=level, error=f"{type(e).__name__}: {e}"[:1000], stop_reason="error")
        row: dict[str, Any] = {"id": case["id"], "type": case["type"], **res.to_dict()}
        outputs = [c.get("output") or "" for c in row["tool_calls"]]
        row["tool_calls"] = [_slim(c) for c in row["tool_calls"]]
        exp = case.get("expected", {})
        if case["type"] == "doc":
            rel = exp.get("relevant_sources", [])
            row["recall@5"] = metrics.recall_at_k(res.retrieved, rel) if res.retrieved else None
            row["mrr"] = metrics.mrr(res.retrieved, rel) if res.retrieved else None
            row["correct"] = metrics.keywords_match(res.answer, exp.get("keywords", [])) and not res.abstained
            row["cited"] = metrics.cites_relevant(res.sources, rel)
            if use_judge and res.level > 0 and not res.abstained:
                # réponse sans citation : invérifiable, donc non fidèle
                v = judge.judge_faithfulness(case["question"], res.answer, judge.passages_for(res.sources))
                row["faithful"] = v["faithful"] if res.sources else False
                row["judge_unsupported"], row["judge_tokens"] = v["unsupported"], v["tokens"]
        elif case["type"] == "absent":
            row["correct"] = res.abstained
        elif case["type"] == "ambiguous":
            row["correct"] = res.clarified if exp.get("behavior") == "clarify" else res.refused
        elif case["type"] == "task":
            row["correct"] = metrics.check_state(exp.get("checks", []), Path(state))
            reports = sorted((Path(state) / "reports").glob("*.json"))
            # diagnostic : chiffres du rapport publié absents des sorties d'outils (None : rien publié)
            row["unsupported_numbers"] = metrics.unsupported_numbers(
                " ".join(json.loads(r.read_text(encoding="utf-8"))["content"] for r in reports), outputs
            ) if reports else None
    return row


def _mean(xs: list[Any]) -> float | None:
    xs = [float(x) for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def metric_lists(level: int, rows: list[dict[str, Any]]) -> dict[str, list[Any]]:
    """Valeurs par cas de chaque métrique de qualité (premier essai ; pass^3 par tâche)."""
    first = [r for r in rows if r["trial"] == 0]
    by = lambda t: [r for r in first if r["type"] == t]  # noqa: E731
    tasks: dict[str, list[bool]] = {}
    for r in rows:
        if r["type"] == "task":
            tasks.setdefault(r["id"], []).append(bool(r["correct"]))
    return {
        "Recall@5": [r.get("recall@5") for r in by("doc")],
        "MRR": [r.get("mrr") for r in by("doc")],
        "Exactitude": [r["correct"] for r in by("doc")],
        "Citation": [r.get("cited") for r in by("doc")] if level > 0 else [],
        "Fidélité": [r.get("faithful") for r in by("doc")] if level > 0 else [],
        "Abstention": [r["correct"] for r in by("absent")],
        "Ambigu": [r["correct"] for r in by("ambiguous")],
        "Succès tâches": [r["correct"] for r in by("task")],
        # part des rapports publiés (1er essai) qui citent au moins un chiffre absent des sorties d'outils
        "Chiffres non soutenus": [bool(r["unsupported_numbers"]) for r in by("task")
                                  if r.get("unsupported_numbers") is not None],
        "pass^3": [metrics.pass_hat_k(v) for v in tasks.values()],
    }


def summarize(level: int, rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = [r for r in rows if r["trial"] == 0]
    lists = metric_lists(level, rows)
    return {
        "niveau": level,
        "modèle": config.LLM_MODEL,
        "Cas": len(first),
        **{name: _mean(xs) for name, xs in lists.items()},
        "Erreurs": sum(1 for r in rows if r.get("error")),
        "Coût/req ($)": _mean([config.cost_usd(r["tokens_in"], r["tokens_out"]) for r in first]),
        "Tokens/req": _mean([r["tokens_in"] + r["tokens_out"] for r in first]),
        "Latence (s)": _mean([r["latency_s"] for r in first]),
        # intervalles de confiance à 95 % (bootstrap, graine fixée), affichés par to_markdown
        "_ci": {name: metrics.bootstrap_ci(xs, seed=SEED) for name, xs in lists.items()},
    }


def to_markdown(summaries: list[dict[str, Any]]) -> str:
    cols = [c for c in summaries[0] if not c.startswith("_")]
    fmt = lambda v: "—" if v is None else (f"{v:.2g}" if isinstance(v, float) and 0 < abs(v) < 0.01  # noqa: E731
                                           else f"{v:.2f}" if isinstance(v, float) else str(v))

    def cell(s: dict[str, Any], c: str) -> str:
        ci = s.get("_ci", {}).get(c)
        return fmt(s[c]) + (f" [{ci[0]:.2f} ; {ci[1]:.2f}]" if ci and s[c] is not None else "")

    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(cell(s, c) for c in cols) + " |" for s in summaries]
    note = "\n\nEntre crochets : intervalle de confiance à 95 % (bootstrap, 2000 tirages, graine fixée)."
    return "\n".join(lines) + (note if any(s.get("_ci") for s in summaries) else "")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--levels", type=int, nargs="+", default=sorted(LEVELS))
    p.add_argument("--trials", type=int, default=3, help="essais par tâche multi-étapes (pass^k)")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--model", default=None, help="remplace LLM_MODEL (benchmark de modèles)")
    p.add_argument("--base-url", default=None, help="remplace LLM_BASE_URL")
    p.add_argument("--types", nargs="+", default=None, help="filtre sur le type de cas (doc, absent, task, ambiguous)")
    p.add_argument("--no-judge", action="store_true", help="sans juge de fidélité (moins de tokens)")
    p.add_argument("--resume", action="store_true",
                   help="garde les cas déjà réussis de results/raw_level{n}.jsonl et ne relance que les manquants ou en erreur")
    p.add_argument("--table-only", action="store_true", help="refait results/table.md depuis les résultats bruts, sans appel")
    a = p.parse_args()
    if a.model:
        config.LLM_MODEL = a.model
    if a.base_url:
        config.LLM_BASE_URL = a.base_url

    random.seed(SEED)
    tests = [c for c in load_tests() if not a.types or c["type"] in a.types][: a.limit]
    RESULTS_DIR.mkdir(exist_ok=True)
    summaries = []
    for level in a.levels:
        fn = LEVELS.get(level)
        if fn is None:
            print(f"Niveau {level} absent, ignoré.")
            continue
        raw = RESULTS_DIR / f"raw_level{level}.jsonl"
        if a.table_only:
            ids = {c["id"] for c in tests}
            rows = [r for r in _read_rows(raw) if r.get("model") == config.LLM_MODEL and r["id"] in ids]
            if rows:
                summaries.append(summarize(level, rows))
            continue
        done = {(r["id"], r["trial"]): r for r in _read_rows(raw)
                if r.get("model") == config.LLM_MODEL and not r.get("error")} if a.resume else {}
        rows: list[dict[str, Any]] = []
        try:
            for case in tests:
                n = a.trials if case["type"] == "task" else 1
                for trial in range(n):
                    if (case["id"], trial) in done:
                        rows.append(done[(case["id"], trial)])
                        continue
                    row = run_case(fn, case, use_judge=not a.no_judge and trial == 0, level=level)
                    rows.append({**row, "trial": trial, "model": config.LLM_MODEL})
                    print(f"[niveau {level}] {case['id']} essai {trial}" + (f" ERREUR {row['error'][:80]}" if row.get("error") else ""))
                    _write_rows(raw, rows)  # écrit après chaque cas : rien n'est perdu si le run s'arrête
        except NotImplementedError as e:
            print(f"Niveau {level} non implémenté : {e}")
            continue
        _write_rows(raw, rows)
        summaries.append(summarize(level, rows))

    if summaries:
        table = to_markdown(summaries)
        (RESULTS_DIR / "table.md").write_text(table + "\n", encoding="utf-8")
        print("\n" + table)


if __name__ == "__main__":
    main()
