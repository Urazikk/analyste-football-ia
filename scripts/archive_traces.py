"""Archive les traces JSONL d'une journée de mesures en un fichier compressé versionné.

    python scripts/archive_traces.py 20261116    ->  traces/mesures-20261116.jsonl.gz

Une ligne par événement, dans l'ordre des exécutions ; le champ run_id est le nom du fichier d'origine
(celui du champ trace_path des résultats bruts). Les sorties de search_rules sont réduites aux identifiants
des extraits : le texte de l'IFAB n'est pas redistribué (licence).
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import TRACES_DIR  # noqa: E402


def slim(event: dict) -> dict:
    """Sortie de search_rules réduite aux identifiants (la sortie tracée peut être tronquée, d'où la recherche par motif)."""
    if event.get("event") == "tool" and event.get("name") == "search_rules":
        import re

        ids = re.findall(r'"id": "([^"]+)"', event.get("output", ""))
        event = {**event, "output": json.dumps({"ok": '"ok": true' in event.get("output", ""), "ids": ids})}
    return event


def archive(day: str) -> Path:
    out = TRACES_DIR / f"mesures-{day}.jsonl.gz"
    files = sorted(TRACES_DIR.glob(f"{day}-*.jsonl"))
    with gzip.open(out, "wt", encoding="utf-8") as f:
        for p in files:
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    f.write(json.dumps(slim(json.loads(line)), ensure_ascii=False) + "\n")
    print(f"{out} : {len(files)} exécutions")
    return out


if __name__ == "__main__":
    archive(sys.argv[1])
