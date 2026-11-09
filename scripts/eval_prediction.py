"""Évaluation du pronostic sur le passé, sans LLM : python scripts/eval_prediction.py

Chaque match international joué depuis EVAL_START est prédit avec les seules données d'avant (classements
Elo calculés dans l'ordre chronologique, modèle de buts ajusté jusqu'au 31 décembre 2024). Cinq méthodes :
uniforme, fréquences historiques, Elo seul, Elo + Poisson calculé, Elo + Poisson simulé (Monte-Carlo).
Mesures : score de Brier (plus bas est mieux), log-loss, taux de bons pronostics, calibration, avec
intervalles de confiance à 95 % (bootstrap) et comparaison appariée avec la simulation.
Sorties : results/prediction/backtest.md, predictions.jsonl, calibration.png.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import metrics, predict  # noqa: E402
from src.config import RESULTS_DIR, SEED  # noqa: E402

EVAL_START = "2025-01-01"
OUT = RESULTS_DIR / "prediction"
METHODS = ["Uniforme", "Fréquences historiques", "Elo seul", "Elo + Poisson (calcul)", "Elo + Poisson (simulation)"]


def outcome(h: int, a: int) -> int:
    return 0 if h > a else 1 if h == a else 2


def predictions() -> tuple[list[dict], np.ndarray, dict[str, np.ndarray]]:
    hist = predict.run_elo(predict.load_results())
    pre = hist.pre
    coef = predict.fit_goals(pre)
    fit = pre[(pre["date"] >= predict.FIT_START) & (pre["date"] <= predict.FIT_END)]
    freq = {}
    for neutral in (False, True):
        f = fit[fit["neutral"] == neutral]
        o = np.array([outcome(h, a) for h, a in zip(f["home_score"], f["away_score"])])
        freq[neutral] = np.bincount(o, minlength=3) / len(o)
    p_draw = float(np.mean(fit["home_score"] == fit["away_score"]))

    ev = pre[pre["date"] >= EVAL_START].reset_index(drop=True)
    y = np.array([outcome(h, a) for h, a in zip(ev["home_score"], ev["away_score"])])
    probs = {m: np.zeros((len(ev), 3)) for m in METHODS}
    rows = []
    for i, m in enumerate(ev.itertuples(index=False)):
        dr = predict.elo_diff(m.elo_home, m.elo_away, m.neutral)
        we = predict.expected(dr)
        lh, la = predict.expected_goals(dr, coef)
        sim = predict.summarize_simulation(predict.simulate_scores(lh, la, seed=SEED + i))
        probs["Uniforme"][i] = [1 / 3] * 3
        probs["Fréquences historiques"][i] = freq[m.neutral]
        ph, pa = max(we - p_draw / 2, 0.01), max(1 - we - p_draw / 2, 0.01)
        probs["Elo seul"][i] = np.array([ph, p_draw, pa]) / (ph + p_draw + pa)
        probs["Elo + Poisson (calcul)"][i] = predict.poisson_probs(lh, la)
        probs["Elo + Poisson (simulation)"][i] = [sim["home_win"], sim["draw"], sim["away_win"]]
        rows.append({"date": m.date.date().isoformat(), "home": m.home_team, "away": m.away_team,
                     "score": f"{m.home_score}-{m.away_score}", "tournament": m.tournament, "neutral": bool(m.neutral),
                     "elo_home": round(m.elo_home), "elo_away": round(m.elo_away),
                     "p_simulation": [round(x, 3) for x in probs["Elo + Poisson (simulation)"][i]]})
    return rows, y, probs


def scores(p: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
    onehot = np.eye(3)[y]
    return {"brier": ((p - onehot) ** 2).sum(axis=1),
            "logloss": -np.log(np.clip(p[np.arange(len(y)), y], 1e-6, 1)),
            "acc": (p.argmax(axis=1) == y).astype(float)}


def table(y: np.ndarray, probs: dict[str, np.ndarray], mask: np.ndarray, title: str) -> str:
    ref = scores(probs["Elo + Poisson (simulation)"][mask], y[mask])
    lines = [f"**{title}** ({int(mask.sum())} matchs)", "",
             "| Méthode | Brier [IC 95 %] | Log-loss | Bons pronostics | Brier − simulation [IC 95 %] |",
             "|---|---|---|---|---|"]
    for m in METHODS:
        s = scores(probs[m][mask], y[mask])
        lo, hi = metrics.bootstrap_ci(list(s["brier"]), seed=SEED)
        d = metrics.paired_bootstrap(list(ref["brier"]), list(s["brier"]), seed=SEED)
        diff = "—" if m == "Elo + Poisson (simulation)" else f"{d['diff']:+.3f} [{d['lo']:+.3f} ; {d['hi']:+.3f}]"
        lines.append(f"| {m} | {s['brier'].mean():.3f} [{lo:.3f} ; {hi:.3f}] | {s['logloss'].mean():.3f} | "
                     f"{s['acc'].mean():.1%} | {diff} |")
    return "\n".join(lines)


def calibration(y: np.ndarray, p: np.ndarray, path: Path) -> str:
    """Probabilités annoncées (les trois issues ensemble) contre fréquences observées, par tranche de 10 %."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pred, obs = p.ravel(), np.eye(3)[y].ravel()
    bins = np.minimum((pred * 10).astype(int), 9)
    lines = ["| Probabilité annoncée | Cas | Fréquence observée |", "|---|---|---|"]
    xs, ys, ns = [], [], []
    for b in range(10):
        sel = bins == b
        if sel.sum() >= 20:
            xs.append(pred[sel].mean()); ys.append(obs[sel].mean()); ns.append(int(sel.sum()))
            lines.append(f"| {b * 10}-{b * 10 + 10} % | {sel.sum()} | {obs[sel].mean():.1%} |")
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.plot([0, 1], [0, 1], color="#999", lw=1, ls="--", label="calibration parfaite")
    ax.plot(xs, ys, marker="o", color="#2b5d8a", label="Elo + Poisson (simulation)")
    ax.set_xlabel("probabilité annoncée"); ax.set_ylabel("fréquence observée")
    ax.set_title(f"Calibration, {len(y)} matchs depuis {EVAL_START[:4]}", fontsize=10)
    ax.legend(fontsize=8, loc="upper left"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, y, probs = predictions()
    with (OUT / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    friendly = np.array([r["tournament"] == "Friendly" for r in rows])
    wc = np.array([r["tournament"] == "FIFA World Cup" for r in rows])
    parts = [f"# Pronostic évalué sur le passé : matchs internationaux depuis le {EVAL_START}\n",
             "Chaque match est prédit avec les seules données d'avant. Brier : 0 = parfait, 0,667 = uniforme. "
             "Une différence négative dans la dernière colonne signifie que la méthode fait mieux que la simulation.\n",
             table(y, probs, np.ones(len(y), bool), "Tous les matchs"),
             table(y, probs, ~friendly, "Matchs officiels (hors amicaux)"),
             table(y, probs, wc, "Coupe du monde 2026"),
             "**Calibration de la simulation** (voir calibration.png)\n\n" + calibration(y, probs["Elo + Poisson (simulation)"], OUT / "calibration.png")]
    text = "\n\n".join(parts) + "\n"
    (OUT / "backtest.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
