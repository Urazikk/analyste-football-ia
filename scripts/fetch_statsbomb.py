"""Remplit le cache StatsBomb (data/cache/statsbomb/) pour les compétitions de config.COMPETITIONS.

Usage : python scripts/fetch_statsbomb.py [--matches-only]
Relançable : les fichiers déjà présents ne sont pas retéléchargés.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import data  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--matches-only", action="store_true", help="liste des matchs seulement, sans événements")
    args = p.parse_args()

    matches = data.all_matches()
    print(f"{len(matches)} matchs, {len(data.team_names())} équipes")
    if args.matches_only:
        return
    ids = matches["match_id"].tolist()
    for i, match_id in enumerate(ids, 1):
        cached = (data.cache_dir() / "events" / f"{match_id}.pkl").exists()
        data.events(match_id)
        if not cached:
            print(f"[{i}/{len(ids)}] {match_id}")
    print(f"Cache : {data.cache_dir()}")


if __name__ == "__main__":
    main()
