"""Couche de données StatsBomb : cache disque et noms d'équipes (sans réseau, depuis le cache)."""
from __future__ import annotations

import pandas as pd
import pytest

from src import data

MATCH = 3942752  # Euro 2024, demi-finale Espagne 2-1 France
needs_cache = pytest.mark.skipif(not (data.cache_dir() / "events" / f"{MATCH}.pkl").exists(),
                                 reason="cache StatsBomb vide (python scripts/fetch_statsbomb.py)")


@pytest.fixture
def offline(monkeypatch):
    """Tout appel à statsbombpy échoue : prouve que la lecture se fait depuis le cache."""
    def no_network():
        raise AssertionError("appel réseau alors que le cache existe")
    monkeypatch.setattr(data, "_sb", no_network)


def test_cache_written_once(tmp_path, monkeypatch):
    calls = []

    def fetch():
        calls.append(1)
        return pd.DataFrame({"a": [1]})

    path = tmp_path / "x.pkl"
    assert data._cached(path, fetch).equals(data._cached(path, fetch))
    assert calls == [1] and path.exists()


@needs_cache
@pytest.mark.parametrize("name,expected", [("Espagne", "Spain"), ("spain", "Spain"), ("ÉTATS-UNIS", "United States"),
                                           ("etats unis", "United States"), ("Pays-Bas", "Netherlands"),
                                           ("Corée du Sud", "South Korea"), ("France", "France")])
def test_resolve_team(offline, name, expected):
    assert data.resolve_team(name) == expected


@needs_cache
def test_resolve_team_unknown_with_suggestion(offline):
    with pytest.raises(ValueError, match="Vouliez-vous dire : France"):
        data.resolve_team("Fance")
    with pytest.raises(ValueError, match="Équipe inconnue"):
        data.resolve_team("Atlantide")


@needs_cache
def test_all_teams_have_french_name(offline):
    assert set(data.team_names()) <= set(data.FRENCH_NAMES.values())


@needs_cache
def test_matches_and_events_from_cache(offline):
    m = data.all_matches()
    assert len(m) == 262 and m["match_date"].is_monotonic_decreasing
    assert (data.events(MATCH)["type"] == "Shot").sum() == 15


@needs_cache
def test_unknown_match(offline):
    with pytest.raises(ValueError, match="absent des données"):
        data.events(1)
