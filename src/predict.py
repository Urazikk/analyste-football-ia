"""Pronostic d'un match de sélections : Elo, buts attendus (Poisson) et simulation de Monte-Carlo.

Données : résultats de tous les matchs internationaux depuis 1872 (jeu public martj42/international_results,
sans clé), mis en cache dans data/cache/intl/. Rien n'est appris d'un match postérieur à la date du pronostic :
les classements sont calculés dans l'ordre chronologique, et le modèle de buts est ajusté sur une période fixe
antérieure à l'évaluation (FIT_END).

Ce module est statistique, pas génératif : l'agent l'appelle comme un outil de calcul et explique le résultat.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src import config

RESULTS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
FIT_START, FIT_END = "2000-01-01", "2024-12-31"   # ajustement du modèle de buts, avant la période évaluée
HOME_ADV = 100.0                                 # points d'Elo pour l'équipe à domicile (hors terrain neutre)
N_SIMULATIONS = 10_000


def cache_path() -> Path:
    return config.CACHE_DIR / "intl" / "results.csv"


def load_results(refresh: bool = False) -> pd.DataFrame:
    """Matchs joués (score connu), triés par date ; téléchargés une fois puis lus depuis le cache."""
    path = cache_path()
    if refresh or not path.exists():
        import requests

        path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(RESULTS_URL, timeout=60)
        r.raise_for_status()
        path.write_bytes(r.content)
    df = pd.read_csv(path)
    df = df.dropna(subset=["home_score", "away_score"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["neutral"] = df["neutral"].astype(str).str.upper().eq("TRUE")
    df[["home_score", "away_score"]] = df[["home_score", "away_score"]].astype(int)
    return df.sort_values("date", kind="stable").reset_index(drop=True)


# Elo (formule des World Football Elo Ratings) -----------------------------------------

def k_factor(tournament: str) -> float:
    t = tournament.lower()
    if t == "fifa world cup":
        return 60
    if "qualification" in t:
        return 40
    if t in {"uefa euro", "copa américa", "african cup of nations", "afc asian cup", "gold cup", "confederations cup"}:
        return 50
    if "nations league" in t:
        return 40
    if t == "friendly":
        return 20
    return 30


def goal_factor(diff: int) -> float:
    d = abs(diff)
    return 1.0 if d <= 1 else 1.5 if d == 2 else (11 + d) / 8


def expected(dr: float) -> float:
    """Résultat attendu (victoire 1, nul 0,5) pour un écart d'Elo dr, avantage du terrain inclus."""
    return 1 / (10 ** (-dr / 400) + 1)


def elo_diff(r_home: float, r_away: float, neutral: bool) -> float:
    return r_home - r_away + (0 if neutral else HOME_ADV)


@dataclass
class EloHistory:
    """Classements après chaque match, et classements avant chaque match (pour l'évaluation)."""
    ratings: dict[str, float] = field(default_factory=dict)
    pre: pd.DataFrame | None = None   # une ligne par match : elo_home, elo_away avant le match


def run_elo(df: pd.DataFrame, initial: float = 1500.0) -> EloHistory:
    ratings: dict[str, float] = {}
    pre_h, pre_a = np.empty(len(df)), np.empty(len(df))
    for i, m in enumerate(df.itertuples(index=False)):
        rh, ra = ratings.get(m.home_team, initial), ratings.get(m.away_team, initial)
        pre_h[i], pre_a[i] = rh, ra
        we = expected(elo_diff(rh, ra, m.neutral))
        w = 1.0 if m.home_score > m.away_score else 0.5 if m.home_score == m.away_score else 0.0
        delta = k_factor(m.tournament) * goal_factor(m.home_score - m.away_score) * (w - we)
        ratings[m.home_team], ratings[m.away_team] = rh + delta, ra - delta
    pre = df[["date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"]].copy()
    pre["elo_home"], pre["elo_away"] = pre_h, pre_a
    return EloHistory(ratings, pre)


# Buts attendus : régression de Poisson sur l'écart d'Elo -----------------------------------

def fit_goals(pre: pd.DataFrame, start: str = FIT_START, end: str = FIT_END) -> tuple[float, float]:
    """log(buts attendus) = a + b * écart/400, ajusté par IRLS sur les deux équipes de chaque match."""
    w = pre[(pre["date"] >= start) & (pre["date"] <= end)]
    d = (w["elo_home"] - w["elo_away"] + np.where(w["neutral"], 0, HOME_ADV)).to_numpy() / 400
    x = np.concatenate([d, -d])
    y = np.concatenate([w["home_score"].to_numpy(), w["away_score"].to_numpy()]).astype(float)
    X = np.column_stack([np.ones_like(x), x])
    beta = np.array([np.log(y.mean()), 0.0])
    for _ in range(50):
        mu = np.exp(X @ beta)
        step = np.linalg.solve(X.T @ (X * mu[:, None]), X.T @ (y - mu))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    return float(beta[0]), float(beta[1])


def expected_goals(dr: float, coef: tuple[float, float]) -> tuple[float, float]:
    a, b = coef
    return float(np.exp(a + b * dr / 400)), float(np.exp(a - b * dr / 400))


# Probabilités : analytique et Monte-Carlo --------------------------------------------------

def poisson_probs(lh: float, la: float, max_goals: int = 15) -> tuple[float, float, float]:
    """Victoire, nul, défaite de l'équipe à domicile, calculés exactement (sans simulation)."""
    from scipy.stats import poisson

    g = np.arange(max_goals + 1)
    m = np.outer(poisson.pmf(g, lh), poisson.pmf(g, la))
    return float(np.tril(m, -1).sum()), float(np.trace(m)), float(np.triu(m, 1).sum())


def simulate_scores(lh: float, la: float, n: int = N_SIMULATIONS, seed: int | None = None) -> np.ndarray:
    """n scores simulés (tableau n x 2), graine fixée pour la reproductibilité."""
    rng = np.random.default_rng(config.SEED if seed is None else seed)
    return np.column_stack([rng.poisson(lh, n), rng.poisson(la, n)])


def summarize_simulation(scores: np.ndarray, top: int = 5) -> dict[str, Any]:
    h, a = scores[:, 0], scores[:, 1]
    pairs, counts = np.unique(scores, axis=0, return_counts=True)
    order = np.argsort(-counts)[:top]
    return {"home_win": float((h > a).mean()), "draw": float((h == a).mean()), "away_win": float((h < a).mean()),
            "likely_scores": [{"score": f"{int(pairs[i][0])}-{int(pairs[i][1])}", "p": round(float(counts[i] / len(h)), 3)}
                              for i in order]}


# Noms des sélections -------------------------------------------------------------------------

# Noms FIFA ou français vers le nom du jeu international. Les 59 sélections StatsBomb ont le même nom
# anglais des deux côtés (vérifié par tests/test_predict_tool.py) ; ces alias couvrent les autres.
INTL_ALIASES: dict[str, str] = {
    "Korea Republic": "South Korea", "Corée": "South Korea", "Czechia": "Czech Republic",
    "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast", "IR Iran": "Iran", "China PR": "China",
    "Türkiye": "Turkey", "Ireland": "Republic of Ireland", "Irlande": "Republic of Ireland",
    "Irlande du Nord": "Northern Ireland", "Chine": "China", "Algérie": "Algeria", "Grèce": "Greece",
    "Norvège": "Norway", "Nouvelle-Zélande": "New Zealand", "Cap-Vert": "Cape Verde", "RD Congo": "DR Congo",
    "Bosnie-Herzégovine": "Bosnia and Herzegovina", "Afrique du Sud": "South Africa", "Égypte": "Egypt",
    "Irak": "Iraq", "Jordanie": "Jordan", "Ouzbékistan": "Uzbekistan", "Émirats arabes unis": "United Arab Emirates",
    "Mali": "Mali", "Burkina Faso": "Burkina Faso", "Haïti": "Haiti", "Curaçao": "Curaçao", "Israël": "Israel",
}


def resolve_intl(name: str) -> str:
    """Nom français, StatsBomb ou FIFA vers le nom du jeu international. ValueError sinon, avec suggestion."""
    import difflib

    from src import data

    known = set(_model()[0].ratings)
    try:
        sb = data.resolve_team(name)  # « Espagne » -> Spain (sélections StatsBomb)
        if sb in known:
            return sb
    except ValueError:
        pass
    lookup = {data._norm(t): t for t in known}
    lookup.update({data._norm(a): t for a, t in INTL_ALIASES.items() if t in known})
    key = data._norm(name)
    if key in lookup:
        return lookup[key]
    close = difflib.get_close_matches(key, lookup, n=3, cutoff=0.6)
    hint = f" Vouliez-vous dire : {', '.join(dict.fromkeys(lookup[c] for c in close))} ?" if close else ""
    raise ValueError(f"Sélection inconnue dans les résultats internationaux : « {name} ».{hint}")


# Point d'entrée pour l'outil de l'agent ----------------------------------------------------

@lru_cache(maxsize=1)
def _model() -> tuple[EloHistory, tuple[float, float]]:
    hist = run_elo(load_results())
    return hist, fit_goals(hist.pre)


def simulate(home: str, away: str, neutral: bool = False, n: int = N_SIMULATIONS) -> dict[str, Any]:
    """Pronostic avec les classements Elo les plus récents (noms anglais du jeu de données)."""
    hist, coef = _model()
    missing = [t for t in (home, away) if t not in hist.ratings]
    if missing:
        raise ValueError(f"Sélection inconnue dans les résultats internationaux : {', '.join(missing)}.")
    rh, ra = hist.ratings[home], hist.ratings[away]
    lh, la = expected_goals(elo_diff(rh, ra, neutral), coef)
    out = summarize_simulation(simulate_scores(lh, la, n))
    last = hist.pre["date"].max().date().isoformat()
    return {"home": home, "away": away, "neutral": neutral, "elo_home": round(rh), "elo_away": round(ra),
            "expected_goals": [round(lh, 2), round(la, 2)], "simulations": n, **out,
            "note": f"Elo et modèle de buts de Poisson, données jusqu'au {last}. Un pronostic, pas une certitude."}
