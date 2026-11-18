"""Rapport PDF : python scripts/build_report.py  ->  docs/rapport/rapport.pdf

Assemble docs/rapport/rapport.md (en-tête), simon.md et gautier.md, remplace les balises {{...}} par des
tableaux recalculés depuis results/ (aucun appel au LLM), convertit en HTML avec pandoc, puis imprime en PDF avec Chrome ou Chromium
(variable CHROME pour en donner le chemin). Vérifie la limite de 4 pages.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import eval as ev  # noqa: E402
from src import config  # noqa: E402
from src.config import RESULTS_DIR  # noqa: E402

DOC = ROOT / "docs" / "rapport"
LEVEL_NAMES = {0: "0 · LLM seul", 1: "1 · RAG", 2: "2 · Agent", 3: "3 · Agent avec plan"}
QUALITY = ["Exactitude", "Citation", "Fidélité", "Abstention", "Ambigu", "Succès tâches", "pass^3"]
COSTS = ["Recall@5", "MRR", "Tokens/req", "Coût/req ($)", "Latence (s)"]
PARTS = ["simon.md", "gautier.md"]

CHOIX = """| Choix | Options comparées | Mesure et résultat |
|---|---|---|
| LLM : gpt-6-luna, raisonnement désactivé | gpt-oss-120b (Groq, poids ouverts) | quota gratuit Groq : 20 essais de tâches sur 60 en un jour ; gpt-6-luna : 360 exécutions d'une traite. gpt-oss-120b reste la référence ouverte |
| Embeddings e5-small, recherche dense, extraits de 600 caractères | bge-m3 ; BM25 et hybride ; 1200 et 2000 caractères | Recall@5 et MRR sur 40 cas et 40 reformulations, bootstrap apparié : aucun écart fiable pour bge-m3 ni l'hybride, plus lents ou fragiles aux fautes |
| Abstention par le modèle, sans seuil sur le score | seuil sur le cosinus | les scores des cas présents et absents se recouvrent |
| Juge de fidélité qwen3.8-27b (autre famille) | | 30 annotations, deux annotateurs : accord 30/30, kappa 1,00 |
| Extension : planification | vérificateur multi-agents, RAG avancé, routage | cas ambigus : seul critère où l'agent fait moins bien que le LLM seul ; chiffres non soutenus à 0,00 une fois la métrique corrigée |"""

# Lignes de la comparaison appariée gardées dans le rapport (le détail est dans results/comparaison.md)
KEEP = [("0 → 1", "Abstention"), ("0 → 1", "Exactitude"), ("1 → 2", "Succès tâches"), ("1 → 2", "Exactitude"),
        ("2 → 3", "Ambigu"), ("2 → 3", "Abstention"), ("2 → 3", "Succès tâches")]


def _rows(path: Path) -> list[dict]:
    return [r for r in ev._read_rows(path) if r.get("model") == config.LLM_MODEL]


def _fmt(v, ci=None) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        s = f"{v:.2g}" if 0 < abs(v) < 0.01 else f"{v:.2f}"
    else:
        s = str(v)
    return s + (f" [{ci[0]:.2f}-{ci[1]:.2f}]" if ci else "")


def summaries(out: Path = RESULTS_DIR) -> dict[int, dict]:
    return {lv: ev.summarize(lv, rows) for lv in range(4) if (rows := _rows(out / f"raw_level{lv}.jsonl"))}


def table(sums: dict[int, dict], cols: list[str], caption: str) -> str:
    cols = [c for c in cols if any(s.get(c) is not None for s in sums.values())]
    head = "| Niveau | Cas | " + " | ".join(cols) + " |\n|---|---|" + "---|" * len(cols) + "\n"
    body = "".join(f"| {LEVEL_NAMES[lv]} | {s['Cas']} | " + " | ".join(_fmt(s.get(c), s["_ci"].get(c)) for c in cols) + " |\n"
                   for lv, s in sums.items())
    return f"**{caption}**\n\n" + head + body


def comparaison() -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    import compare_levels as cl

    levels = [lv for lv in range(4) if (RESULTS_DIR / f"raw_level{lv}.jsonl").exists()]
    lines = cl.compare(levels).splitlines()
    keep = [l for l in lines[2:] if any(f"| {a} | {m} |" in l for a, m in KEEP)]
    if not keep:
        return ""
    return ("**Comparaison appariée des niveaux successifs** (mêmes cas ; gain fiable si l'intervalle est au-dessus de 0)\n\n"
            + "\n".join(lines[:2] + keep))


def protocole() -> str:
    cases = ev.load_tests()
    n = {t: sum(c["type"] == t for c in cases) for t in ("doc", "absent", "task", "ambiguous")}
    return (f"Même jeu de test pour tous les niveaux : {len(cases)} cas ({n['doc']} réponses dans les documents, "
            f"{n['absent']} absentes, {n['task']} tâches multi-étapes vérifiées sur l'état final, {n['ambiguous']} "
            "demandes ambiguës ou hors sujet). Température 0, un seul modèle. Intervalles de confiance à 95 % "
            "par bootstrap (entre crochets).")


def robustesse() -> str:
    """Exactitude sur les reformulations, une ligne par niveau (origine, familier, mise en situation)."""
    p = RESULTS_DIR / "robustesse" / "robustesse.md"
    if not p.exists():
        return "_Robustesse : mesure à venir._"
    by: dict[str, dict[str, list[str]]] = {}
    for l in p.read_text(encoding="utf-8").splitlines():
        c = [x.strip() for x in l.split("|")]
        if len(c) > 6 and c[1].isdigit():
            by.setdefault(c[1], {})[c[2]] = c[4:7]
    lines = ["**Exactitude sur 40 reformulations relues de 20 questions** (stabilité : même résultat que la question d'origine)",
             "", "| Niveau | Question d'origine | Familier, avec fautes | Mise en situation | Stabilité |", "|---|---|---|---|---|"]
    for lv, d in by.items():
        fam, sit = d.get("familier", ["—"] * 3), d.get("situation", ["—"] * 3)
        lines.append(f"| {LEVEL_NAMES[int(lv)]} | {fam[1]} | {fam[0]} | {sit[0]} | {fam[2]} et {sit[2]} |")
    return "\n".join(lines)


def injection() -> str:
    sums = summaries(RESULTS_DIR / "injection")
    if not sums:
        return "Injection de consignes : mesure à venir."
    rates = ", ".join(f"niveau {lv} : {_fmt(s.get('Injection obéie'))}" for lv, s in sums.items())
    return (f"Injection de consignes (10 cas : 5 documents piégés, 5 sorties d'outils piégées), part des cas où le "
            f"système obéit : {rates}.")


def ambigus() -> str:
    """Tableau des cas ambigus à 3 essais (niveaux 2 et 3) et écart apparié, depuis results/ambigus/ambigus.md."""
    p = RESULTS_DIR / "ambigus" / "ambigus.md"
    if not p.exists():
        return "_Cas ambigus à 3 essais : mesure à venir._"
    lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("|")]
    head = [l for l in lines if l.startswith("| Niveau |") or l.startswith("|---|---|---|---|---|---|---|---|")][:2]
    levels = [l for l in lines if l.split("|")[1].strip() in ("0", "2", "3") and "→" not in l]
    diff = next((l for l in lines if l.startswith("| 2 → 3 |")), "")
    cells = [c.strip() for c in diff.split("|")]
    note = f"\n\nNiveau 3 moins niveau 2, apparié sur {cells[2]} cas : {cells[5]}." if diff else ""
    return "\n".join(head + levels) + note


def absents() -> str:
    """Abstention sur les cas absents complémentaires, niveaux 2 et 3."""
    out = []
    for lv in (2, 3):
        rows = _rows(RESULTS_DIR / "absents" / f"raw_level{lv}.jsonl")
        if rows:
            out.append(f"{sum(bool(r['correct']) for r in rows)} sur {len(rows)} au niveau {lv}")
    return " et ".join(out) or "mesure à venir"


def benchmark() -> str:
    """Benchmark de modèles au niveau 2 sur les 20 tâches (3 essais), depuis results/raw_level2.jsonl."""
    rows = [r for r in ev._read_rows(RESULTS_DIR / "raw_level2.jsonl") if r["type"] == "task"]
    poids = {"gpt-6-luna": "fermés", "openai/gpt-oss-120b": "ouverts"}
    lines = ["| Modèle | Poids | Essais aboutis | Succès tâches | pass^3 | Chiffres non soutenus | Tokens par tâche | Latence (s) |",
             "|---|---|---|---|---|---|---|---|"]
    for model in poids:
        mr = [r for r in rows if r.get("model") == model]
        if not mr:
            continue
        s = ev.summarize(2, mr)
        ok = [r for r in mr if not r.get("error")]
        lines.append(f"| {model} | {poids[model]} | {len(ok)} sur {len(mr)} | {_fmt(s['Succès tâches'])} | "
                     f"{_fmt(s['pass^3'])} | {_fmt(s['Chiffres non soutenus'])} | "
                     f"{sum(r['tokens_in'] + r['tokens_out'] for r in ok) / max(len(ok), 1):.0f} | "
                     f"{sum(r['latency_s'] for r in ok) / max(len(ok), 1):.1f} |")
    return ("**Niveau 2, 20 tâches, 3 essais par tâche** (essais en erreur d'infrastructure exclus ; pass^3 sur les "
            "tâches dont les 3 essais ont abouti)\n\n" + "\n".join(lines))


def couts(sums: dict[int, dict]) -> str:
    rows = [r for lv in range(4) for r in _rows(RESULTS_DIR / f"raw_level{lv}.jsonl")]
    tok = sum(r["tokens_in"] + r["tokens_out"] for r in rows)
    usd = sum(config.cost_usd(r["tokens_in"], r["tokens_out"]) for r in rows)
    per = " ; ".join(f"niveau {lv} : {1000 * s['Coût/req ($)']:.2f} $" for lv, s in sums.items())
    return (f"Coût pour 1 000 requêtes avec {config.LLM_MODEL} : {per}. Toutes les mesures du tableau : "
            f"{tok:,} tokens, soit {usd:.2f} $.".replace(",", " "))


def assemble() -> str:
    """En-tête de rapport.md, puis chaque partie à partir de son premier titre « ## »."""
    text = (DOC / "rapport.md").read_text(encoding="utf-8")
    for name in PARTS:
        p = DOC / name
        if p.exists():
            body = p.read_text(encoding="utf-8")
            text += "\n" + body[max(body.find("\n## "), 0):] + "\n"
    return text


def chrome() -> str:
    cands = [os.getenv("CHROME"), shutil.which("chromium"), shutil.which("google-chrome"), shutil.which("chrome"),
             *sorted(glob.glob("/opt/pw-browsers/chromium*/chrome-linux*/chrome"))]
    for c in cands:
        if c and Path(c).exists():
            return c
    raise SystemExit("Chrome ou Chromium introuvable : définir la variable CHROME.")


def build() -> Path:
    sums = summaries()
    fill = {"choix": CHOIX, "protocole": protocole(),
            "table_qualite": table(sums, QUALITY, "Qualité par niveau") if sums else "_Mesures à venir._",
            "table_couts": table(sums, COSTS, "Recherche, coût et latence par niveau") if sums else "",
            "table_recherche": table(sums, COSTS, "Recherche, coût et latence par niveau") if sums else "",
            "comparaison": comparaison(), "robustesse": robustesse(), "injection": injection(),
            "ambigus": ambigus(), "absents": absents(), "benchmark": benchmark(), "couts": couts(sums) if sums else ""}
    text = assemble()
    for k, v in fill.items():
        text = text.replace("{{" + k + "}}", re.sub(r"(\d)\.(\d)", r"\1,\2", v))  # décimales à la française
    md = DOC / "_build.md"
    md.write_text(text, encoding="utf-8")
    html = DOC / "_build.html"
    subprocess.run(["pandoc", str(md), "-s", "--embed-resources", "--css", str(DOC / "style.css"),
                    "--metadata", "lang=fr", "-o", str(html)], check=True, cwd=DOC)
    pdf = DOC / "rapport.pdf"
    subprocess.run([chrome(), "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html.as_uri()], check=True, capture_output=True)
    md.unlink()
    html.unlink()
    from pypdf import PdfReader

    pages = len(PdfReader(str(pdf)).pages)
    print(f"{pdf} : {pages} page(s)" + ("  ATTENTION : plus de 4 pages" if pages > 4 else ""))
    return pdf


if __name__ == "__main__":
    build()
