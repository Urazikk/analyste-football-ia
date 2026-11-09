"""Calibration du juge de fidélité contre des annotations humaines.

    python scripts/calibrate_judge.py --prepare   # crée docs/annotations_fidelite.jsonl à annoter
    python scripts/calibrate_judge.py --annotate  # annotation guidée dans le terminal (o/n)
    python scripts/calibrate_judge.py             # compare juge et annotations

Annoter à la main le champ "humain" (true : chaque affirmation est soutenue par les extraits cités,
false sinon), sans regarder le verdict du juge. Sortie : results/judge_calibration.md.
Le fichier ne garde que les identifiants des extraits (texte IFAB non redistribué) : corpus local requis.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import judge, rag  # noqa: E402
from src.config import JUDGE_MODEL, RESULTS_DIR  # noqa: E402

ANNOT = ROOT / "docs" / "annotations_fidelite.jsonl"
SOURCE = ROOT / "results" / "choix-llm" / "gpt-oss-120b-l1.jsonl"


def prepare(source: Path, n: int = 20) -> None:
    if ANNOT.exists():
        raise SystemExit(f"{ANNOT} existe déjà : ne pas écraser des annotations.")
    rows = [json.loads(l) for l in source.read_text(encoding="utf-8").splitlines() if l.strip()]
    cases = {c["id"]: c for c in map(json.loads, (ROOT / "tests.jsonl").read_text(encoding="utf-8").splitlines())}
    out = []
    for r in rows:
        if r["type"] == "doc" and not r["abstained"] and len(out) < n:
            out.append({"id": r["id"], "question": cases[r["id"]]["question"], "answer": r["answer"],
                        "sources": rag.cited_ids(r["answer"], r["retrieved"]), "humain": None, "note": ""})
    ANNOT.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
    print(f"{len(out)} réponses à annoter dans {ANNOT}")


def annotate() -> None:
    """Affiche chaque réponse et ses extraits, enregistre o/n après chaque cas (reprise possible)."""
    rows = [json.loads(l) for l in ANNOT.read_text(encoding="utf-8").splitlines() if l.strip()]
    for i, r in enumerate(rows):
        if isinstance(r["humain"], bool):
            continue
        print(f"\n===== {r['id']} ({i + 1}/{len(rows)}) =====\nQuestion : {r['question']}\n\nRéponse :\n{r['answer']}\n")
        for cid, text in judge.passages_for(r["sources"]).items():
            print(f"--- extrait [{cid}]\n{text}\n")
        ans = ""
        while ans not in ("o", "n", "q"):
            ans = input("Chaque affirmation est-elle soutenue par les extraits ? [o/n, q pour quitter] ").strip().lower()
        if ans == "q":
            break
        r["humain"] = ans == "o"
        r["note"] = input("Note (facultatif) : ").strip()
        ANNOT.write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in rows), encoding="utf-8")
    print(f"{sum(isinstance(r['humain'], bool) for r in rows)}/{len(rows)} annotées.")


def kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Kappa de Cohen ; None si indéfini (une seule classe chez les deux annotateurs)."""
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pa, pb = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def calibrate() -> None:
    rows = [json.loads(l) for l in ANNOT.read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if isinstance(r["humain"], bool)]
    if not rows:
        raise SystemExit("Aucune annotation : remplir le champ \"humain\" (true ou false).")
    lines, pairs = [], []
    for r in rows:
        v = judge.judge_faithfulness(r["question"], r["answer"], judge.passages_for(r["sources"]))
        j = v["faithful"] if v["faithful"] is not None else False
        pairs.append((r["humain"], j))
        mark = "" if r["humain"] == j else " **désaccord**"
        lines.append(f"| {r['id']} | {r['humain']} | {j} | {'; '.join(v['unsupported'])[:120]}{mark} |")
    agree = sum(a == b for a, b in pairs) / len(pairs)
    fn = sum(h and not j for h, j in pairs)
    fp = sum(not h and j for h, j in pairs)
    k = kappa(pairs)
    report = (f"# Calibration du juge de fidélité ({JUDGE_MODEL})\n\n"
              f"{len(pairs)} réponses annotées ({sum(h for h, _ in pairs)} fidèles selon l'humain). Accord : {agree:.2f}. "
              f"Kappa de Cohen : {'indéfini (une seule classe)' if k is None else f'{k:.2f}'}. "
              f"Juge trop sévère : {fn}. Juge trop indulgent : {fp}.\n\n"
              "| Cas | Humain | Juge | Affirmations non soutenues selon le juge |\n|---|---|---|---|\n"
              + "\n".join(lines) + "\n")
    RESULTS_DIR.mkdir(exist_ok=True)
    (RESULTS_DIR / "judge_calibration.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--prepare", action="store_true")
    p.add_argument("--annotate", action="store_true")
    p.add_argument("--source", type=Path, default=SOURCE, help="résultats bruts du niveau 1 à annoter")
    a = p.parse_args()
    if a.prepare:
        prepare(a.source)
    elif a.annotate:
        annotate()
    else:
        calibrate()
