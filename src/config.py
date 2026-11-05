"""Configuration centralisée, lue depuis .env."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CORPUS_DIR = DATA_DIR / "corpus"
CACHE_DIR = DATA_DIR / "cache"
INDEX_DIR = DATA_DIR / "index"
TRACES_DIR = ROOT / "traces"
RESULTS_DIR = ROOT / "results"

LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")

AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "8"))
AGENT_MAX_TOKENS = int(os.getenv("AGENT_MAX_TOKENS", "20000"))
SEED = int(os.getenv("SEED", "42"))

# Compétitions StatsBomb retenues : (competition_id, season_id), sélections nationales
COMPETITIONS: list[tuple[int, int]] = [
    (55, 282),   # UEFA Euro 2024
    (223, 282),  # Copa America 2024
    (43, 106),   # FIFA World Cup 2022
]

# Marqueurs imposés au modèle, détectés par du code dans eval.py
ABSTAIN_MARK = "[ABSTENTION]"
CLARIFY_MARK = "[PRECISION]"
REFUSE_MARK = "[REFUS]"


def state_dir() -> Path:
    """Dossier où l'agent écrit (rapports publiés). Surchargé par eval.py à chaque essai."""
    return Path(os.getenv("STATE_DIR", DATA_DIR / "state"))
