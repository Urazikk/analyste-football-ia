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
# Juge de fidélité : autre famille que le modèle évalué, pour limiter le biais d'auto-évaluation
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen/qwen3.8-27b")
# Tarif payant équivalent (USD par million de tokens), pour afficher le coût ; Groq gpt-oss-120b, nov. 2026.
# On reste sur l'offre gratuite : c'est ce que coûterait la même requête en offre payante.
PRICE_IN_PER_MTOK = float(os.getenv("PRICE_IN_PER_MTOK", "0.15"))
PRICE_OUT_PER_MTOK = float(os.getenv("PRICE_OUT_PER_MTOK", "0.60"))


def cost_usd(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * PRICE_IN_PER_MTOK + tokens_out * PRICE_OUT_PER_MTOK) / 1e6

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
