"""Modèle de pronostic (Elo, Poisson, Monte-Carlo) sur des données synthétiques, sans réseau."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import predict


def _df(rows):
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_factors():
    assert predict.k_factor("FIFA World Cup") == 60 and predict.k_factor("Friendly") == 20
    assert predict.k_factor("UEFA Euro qualification") == 40
    assert predict.goal_factor(1) == 1 and predict.goal_factor(2) == 1.5 and predict.goal_factor(-4) == 15 / 8


def test_elo_is_zero_sum_and_rewards_winner():
    h = predict.run_elo(_df([("2020-01-01", "A", "B", 2, 0, "Friendly", True)]))
    assert h.ratings["A"] > 1500 > h.ratings["B"]
    assert h.ratings["A"] + h.ratings["B"] == pytest.approx(3000)
    assert list(h.pre["elo_home"]) == [1500]  # classement avant le match, pas après


def test_fit_goals_recovers_parameters():
    rng = np.random.default_rng(0)
    d = rng.normal(0, 300, 20000)
    a, b = 0.2, 0.8
    rows = [("2010-01-01", "H", "A", rng.poisson(np.exp(a + b * x / 400)), rng.poisson(np.exp(a - b * x / 400)), "Friendly", True)
            for x in d]
    pre = _df(rows)
    pre["elo_home"], pre["elo_away"] = d, 0.0
    fa, fb = predict.fit_goals(pre, "2000-01-01", "2030-01-01")
    assert fa == pytest.approx(a, abs=0.03) and fb == pytest.approx(b, abs=0.05)


def test_simulation_matches_exact_probabilities_and_is_reproducible():
    s1 = predict.simulate_scores(1.6, 0.9, seed=1)
    assert (s1 == predict.simulate_scores(1.6, 0.9, seed=1)).all()
    sim = predict.summarize_simulation(s1)
    exact = predict.poisson_probs(1.6, 0.9)
    assert sim["home_win"] + sim["draw"] + sim["away_win"] == pytest.approx(1)
    assert np.allclose([sim["home_win"], sim["draw"], sim["away_win"]], exact, atol=0.015)
    assert len(sim["likely_scores"]) == 5


def test_simulate_unknown_team(monkeypatch):
    hist = predict.run_elo(_df([("2020-01-01", "A", "B", 1, 0, "Friendly", False)]))
    monkeypatch.setattr(predict, "_model", lambda: (hist, (0.2, 0.8)))
    out = predict.simulate("A", "B", neutral=True, n=2000)
    assert out["home_win"] > out["away_win"] and out["simulations"] == 2000
    with pytest.raises(ValueError, match="inconnue"):
        predict.simulate("A", "Atlantide")


def test_animation_writes_a_video(monkeypatch, tmp_path):
    from src import animation

    hist = predict.run_elo(_df([("2020-01-01", "A", "B", 1, 0, "Friendly", False)]))
    monkeypatch.setattr(predict, "_model", lambda: (hist, (0.2, 0.8)))
    out = animation.animate_match("A", "B", neutral=True, out=tmp_path / "a.gif", n=200, seconds=0.5, fps=4, hold=0.25)
    assert out.exists() and out.stat().st_size > 1000
    assert len(animation.schedule(10_000, 100)) > 50
