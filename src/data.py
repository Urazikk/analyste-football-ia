"""Données StatsBomb (open data, sans clé) : matchs, événements, cache disque, noms d'équipes.

Cache dans data/cache/statsbomb/ : un fichier par compétition et un par match.
Un deuxième appel ne touche pas au réseau.
"""
from __future__ import annotations

import difflib
import unicodedata
import warnings
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src import config

# Noms français (et variantes courantes) vers le nom StatsBomb, pour les sélections des 5 compétitions.
FRENCH_NAMES: dict[str, str] = {
    "Albanie": "Albania", "Argentine": "Argentina", "Australie": "Australia", "Autriche": "Austria",
    "Belgique": "Belgium", "Bolivie": "Bolivia", "Brésil": "Brazil", "Cameroun": "Cameroon",
    "Canada": "Canada", "Chili": "Chile", "Colombie": "Colombia", "Costa Rica": "Costa Rica",
    "Croatie": "Croatia", "République tchèque": "Czech Republic", "Tchéquie": "Czech Republic",
    "Danemark": "Denmark", "Équateur": "Ecuador", "Angleterre": "England", "France": "France",
    "Géorgie": "Georgia", "Allemagne": "Germany", "Ghana": "Ghana", "Hongrie": "Hungary", "Iran": "Iran",
    "Italie": "Italy", "Jamaïque": "Jamaica", "Japon": "Japan", "Mexique": "Mexico", "Maroc": "Morocco",
    "Pays-Bas": "Netherlands", "Hollande": "Netherlands", "Panama": "Panama", "Paraguay": "Paraguay",
    "Pérou": "Peru", "Pologne": "Poland", "Portugal": "Portugal", "Qatar": "Qatar", "Roumanie": "Romania",
    "Arabie saoudite": "Saudi Arabia", "Écosse": "Scotland", "Sénégal": "Senegal", "Serbie": "Serbia",
    "Slovaquie": "Slovakia", "Slovénie": "Slovenia", "Corée du Sud": "South Korea", "Espagne": "Spain",
    "Suisse": "Switzerland", "Tunisie": "Tunisia", "Turquie": "Turkey", "Ukraine": "Ukraine",
    "États-Unis": "United States", "USA": "United States", "Uruguay": "Uruguay", "Venezuela": "Venezuela",
    "Pays de Galles": "Wales",
    # Euro 2020 et Coupe du monde 2018
    "Égypte": "Egypt", "Finlande": "Finland", "Islande": "Iceland", "Nigeria": "Nigeria",
    "Macédoine du Nord": "North Macedonia", "Russie": "Russia", "Suède": "Sweden",
}


def cache_dir() -> Path:
    return config.CACHE_DIR / "statsbomb"


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.strip().lower())
    return "".join(c for c in s if not unicodedata.combining(c)).replace("-", " ")


def _cached(path: Path, fetch) -> pd.DataFrame:
    """Lit le fichier s'il existe, sinon appelle fetch() et l'écrit."""
    if path.exists():
        return pd.read_pickle(path)
    df = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df


def _sb():
    with warnings.catch_warnings():  # statsbombpy avertit à chaque appel sans identifiants
        warnings.simplefilter("ignore")
        from statsbombpy import sb
    return sb


def competition_matches(competition_id: int, season_id: int) -> pd.DataFrame:
    def fetch() -> pd.DataFrame:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return _sb().matches(competition_id=competition_id, season_id=season_id)

    return _cached(cache_dir() / "matches" / f"{competition_id}_{season_id}.pkl", fetch)


@lru_cache(maxsize=1)
def all_matches() -> pd.DataFrame:
    """Matchs des compétitions retenues (config.COMPETITIONS), du plus récent au plus ancien."""
    df = pd.concat([competition_matches(c, s) for c, s in config.COMPETITIONS], ignore_index=True)
    df["match_date"] = pd.to_datetime(df["match_date"])
    return df.sort_values(["match_date", "kick_off"], ascending=False).reset_index(drop=True)


def get_match(match_id: int) -> pd.Series:
    m = all_matches()
    row = m[m["match_id"] == match_id]
    if row.empty:
        raise ValueError(f"Match {match_id} absent des données. Utiliser list_matches pour trouver un identifiant.")
    return row.iloc[0]


def events(match_id: int) -> pd.DataFrame:
    """Événements d'un match (un fichier de cache par match)."""
    get_match(match_id)  # erreur claire si le match n'est pas dans le périmètre

    def fetch() -> pd.DataFrame:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return _sb().events(match_id=match_id)

    return _cached(cache_dir() / "events" / f"{match_id}.pkl", fetch)


@lru_cache(maxsize=1)
def team_names() -> tuple[str, ...]:
    m = all_matches()
    return tuple(sorted(set(m["home_team"]) | set(m["away_team"])))


def resolve_team(name: str) -> str:
    """Nom français ou anglais (casse et accents libres) vers le nom StatsBomb. ValueError sinon."""
    teams = team_names()
    lookup = {_norm(t): t for t in teams}
    lookup.update({_norm(fr): en for fr, en in FRENCH_NAMES.items() if en in teams})
    key = _norm(name)
    if key in lookup:
        return lookup[key]
    close = difflib.get_close_matches(key, lookup, n=3, cutoff=0.6)
    hint = f" Vouliez-vous dire : {', '.join(dict.fromkeys(lookup[c] for c in close))} ?" if close else ""
    raise ValueError(f"Équipe inconnue : « {name} ». Elle n'a joué aucun match des compétitions retenues "
                     f"(Euro 2020 et 2024, Copa América 2024, Coupe du monde 2018 et 2022).{hint}")
