"""Rapport PDF : python scripts/build_report.py  ->  docs/rapport/rapport.pdf

Remplace les balises {{...}} de docs/rapport/rapport.md par des tableaux recalculés depuis results/
(aucun appel au LLM), convertit en HTML avec pandoc, puis imprime en PDF avec Chrome ou Chromium
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
LEVEL_NAMES = {0: "0 · LLM seul", 1: "1 · RAG", 2: "2 · Agent", 3: "3 · Extension"}
QUALITY = ["Exactitude", "Citation", "Fidélité", "Abstention", "Ambigu", "Succès tâches", "pass^3"]
COSTS = ["Recall@5", "MRR", "Tokens/req", "Coût/req ($)", "Latence (s)", "Erreurs"]

CHOIX = """| Choix | Options comparées | Mesure | Résultat |
|---|---|---|---|
| LLM : gpt-oss-120b (Groq, poids ouverts, gratuit) | qwen3.8-27b ; Mistral Small sans accès API gratuit | niveaux 0 et 1, 25 cas | niveau 0 : exactitude 0,75 contre 0,10 (Qwen s'abstient trop) ; citation 1,00 contre 0,90 |
| Embeddings : multilingual-e5-small | bge-m3 | Recall@5 et MRR, 40 cas, bootstrap apparié | pas d'écart fiable (bge-m3 +0,05 [0 ; +0,125]) ; e5 quatre fois plus rapide |
| Recherche dense seule | BM25, hybride RRF | idem, plus 40 reformulations | hybride sans gain fiable, et 0,70 de Recall@5 sur les questions avec fautes |
| Extraits de 600 caractères | 1200, 2000 | Recall@5 et MRR | MRR 0,76 contre 0,67 et 0,59 |
| Pas de seuil d'abstention sur le score | seuil sur le cosinus | scores des cas doc et absents | recouvrement : un seuil rejetterait de bons cas |
| Juge de fidélité : qwen3.8-27b (autre famille) | | 30 annotations humaines dont 10 erreurs injectées | accord 30/30, kappa 1,00 |"""


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
    keep = [l for l in lines[2:] if any(f"| {a} → {a + 1} |" in l for a in range(3))
            and any(f"| {m} |" in l for m in ("Exactitude", "Citation", "Abstention", "Ambigu", "Succès tâches"))
            and not ("| 0 → 1 |" in l and "| Citation |" in l)]  # le niveau 0 n'a rien à citer
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
    parts = []
    for name, title in (("recherche.md", "Recherche seule sur 40 reformulations relues"),
                        ("robustesse.md", "Réponses sur les reformulations")):
        p = RESULTS_DIR / "robustesse" / name
        if p.exists():
            body = "\n".join(l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("|"))
            parts.append(f"**{title}**\n\n{body}")
    return "\n\n".join(parts) or "_Robustesse : mesure à venir._"


def injection() -> str:
    sums = summaries(RESULTS_DIR / "injection")
    if not sums:
        return "_Injection de consignes (5 documents piégés) : mesure à venir._"
    return table(sums, ["Injection obéie"], "Injection de consignes : part des cas où le système obéit (plus bas est mieux)")


def couts(sums: dict[int, dict]) -> str:
    rows = [r for lv in range(4) for r in ev._read_rows(RESULTS_DIR / f"raw_level{lv}.jsonl")]
    tok = sum(r["tokens_in"] + r["tokens_out"] for r in rows)
    usd = sum(config.cost_usd(r["tokens_in"], r["tokens_out"]) for r in rows)
    per = ", ".join(f"niveau {lv} : {_fmt(s['Coût/req ($)'])} $" for lv, s in sums.items())
    return (f"Coût par requête au tarif payant équivalent ({per}). Toutes les mesures stockées : {tok:,} tokens, "
            f"soit {usd:.2f} $ au tarif payant ; coût réel nul (offre gratuite).").replace(",", " ")


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
            "comparaison": comparaison(), "robustesse": robustesse(), "injection": injection(),
            "couts": couts(sums) if sums else ""}
    text = (DOC / "rapport.md").read_text(encoding="utf-8")
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
