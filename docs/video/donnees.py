"""Données de la vidéo, tirées des résultats mesurés et d'une trace réelle : python docs/video/donnees.py <trace.jsonl> <sortie.js>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import ambigus  # noqa: E402
import eval as ev  # noqa: E402
from src import config  # noqa: E402
from src.config import RESULTS_DIR  # noqa: E402


def niveaux() -> list[dict]:
    cases = ambigus.load_cases()
    out = []
    for lv in range(4):
        rows = [r for r in ev._read_rows(RESULTS_DIR / f"raw_level{lv}.jsonl") if r.get("model") == config.LLM_MODEL]
        s = ev.summarize(lv, rows)
        amb = ambigus.per_case(lv, cases)
        score = [sum(bool(r["correct"]) for r in rs) / len(rs) for rs in amb.values()]
        out.append({"niveau": lv, "exactitude": s["Exactitude"], "abstention": s["Abstention"],
                    "taches": s["Succès tâches"], "ambigu": sum(score) / len(score), "tokens": s["Tokens/req"],
                    "cout": s["Coût/req ($)"], "latence": s["Latence (s)"]})
    return out


def trace(path: Path) -> list[dict]:
    """Événements de la trace, réduits à ce qui s'affiche (pas de texte long)."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        d = {"t": e["t"], "event": e["event"]}
        if e["event"] == "llm":
            d["detail"] = f"{e['tokens_in']} tokens en entrée, {e['tokens_out']} en sortie, {e['latency_s']:.1f} s".replace(".", ",")
        elif e["event"] == "tool":
            d["detail"] = f"{e['name']} ({e['effect']})  {str(e['arguments'])[:70]}"
            d["effect"] = e["effect"]
            d["ok"] = '"ok": true' in e.get("output", "")
        elif e["event"] == "confirmation":
            d["detail"] = f"{e['name']} : {'validée' if e['approved'] else 'refusée'} par l'utilisateur"
        elif e["event"] == "end":
            d["detail"] = f"{e.get('stop_reason')} : {e.get('steps')} étapes, {e.get('tokens')} tokens"
        elif e["event"] == "start":
            d["detail"] = e["question"][:95]
        out.append(d)
    return out


if __name__ == "__main__":
    data = {"niveaux": niveaux(), "trace": trace(Path(sys.argv[1])), "fichier": Path(sys.argv[1]).name}
    Path(sys.argv[2]).write_text("window.DONNEES = " + json.dumps(data, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(json.dumps(data["niveaux"], ensure_ascii=False)[:400])
