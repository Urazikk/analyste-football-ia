"""Animation verticale (format vidéo courte, 9:16) d'un pronostic : les simulations s'accumulent.

Le compteur monte de 1 à 10 000 matchs simulés ; les barres victoire, nul, défaite se stabilisent ; la grille
des scores se remplit ; la dernière image affiche le pronostic. Les tirages sont ceux de predict.simulate_scores
(graine fixée) : l'animation montre exactement la simulation qui produit le pronostic.

    python -m src.animation France Spain --neutral --out results/prediction/france-spain.mp4
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from src import predict

BG, FG, MUTED = "#0e1117", "#f2f2f2", "#9aa0a6"
HOME_C, DRAW_C, AWAY_C = "#3b82f6", "#9ca3af", "#ef4444"
MAX_G = 5  # grille 0 à 5 buts, la dernière case regroupe « 5 et plus »


def french(team: str) -> str:
    """Nom français pour l'affichage si on le connaît (« Spain » donne « Espagne »)."""
    try:
        from src.data import FRENCH_NAMES

        inv = {en: fr for fr, en in FRENCH_NAMES.items() if fr.upper() != fr}
        return inv.get(team, team)
    except Exception:
        return team


def schedule(n: int, frames: int) -> np.ndarray:
    """Nombre de simulations affichées à chaque image : progression rapide au début, puis plus lente."""
    return np.unique(np.clip(np.round(np.geomspace(1, n, frames)), 1, n).astype(int))


def animate_match(home: str, away: str, neutral: bool = False, out: Path | None = None, n: int = predict.N_SIMULATIONS,
                  seconds: float = 9.0, fps: int = 20, hold: float = 2.5) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.animation import FFMpegWriter, FuncAnimation, PillowWriter

    hist, coef = predict._model()
    for t in (home, away):
        if t not in hist.ratings:
            raise ValueError(f"Sélection inconnue dans les résultats internationaux : {t}.")
    lh, la = predict.expected_goals(predict.elo_diff(hist.ratings[home], hist.ratings[away], neutral), coef)
    scores = predict.simulate_scores(lh, la, n)
    steps = schedule(n, int(seconds * fps))
    steps = np.concatenate([steps, np.full(int(hold * fps), n)])
    hn, an = french(home), french(away)
    out = out or Path("results/prediction") / f"{home.lower().replace(' ', '-')}-{away.lower().replace(' ', '-')}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": FG})
    fig = plt.figure(figsize=(5.4, 9.6), dpi=100, facecolor=BG)
    fig.text(0.5, 0.95, f"{hn}  vs  {an}", ha="center", fontsize=24, fontweight="bold")
    fig.text(0.5, 0.915, "terrain neutre" if neutral else f"à domicile : {hn}", ha="center", fontsize=11, color=MUTED)
    counter = fig.text(0.5, 0.855, "", ha="center", fontsize=20, fontweight="bold")
    fig.text(0.5, 0.83, "matchs simulés", ha="center", fontsize=11, color=MUTED)

    ax_bar = fig.add_axes([0.08, 0.6, 0.84, 0.2], facecolor=BG)
    labels = [f"Victoire {hn}", "Match nul", f"Victoire {an}"]
    ys = (2.6, 1.3, 0)
    bars = ax_bar.barh(ys, [0, 0, 0], color=[HOME_C, DRAW_C, AWAY_C], height=0.55)
    pct = [ax_bar.text(0, y, "", va="center", fontsize=15, fontweight="bold") for y in ys]
    for y, lab in zip(ys, labels):
        ax_bar.text(0, y + 0.36, lab, fontsize=10.5, color=MUTED, va="bottom")
    ax_bar.set_xlim(0, 1)
    ax_bar.set_ylim(-0.4, 3.4)
    ax_bar.axis("off")

    ax_grid = fig.add_axes([0.14, 0.17, 0.74, 0.38], facecolor=BG)
    grid_img = ax_grid.imshow(np.zeros((MAX_G + 1, MAX_G + 1)), cmap="magma", vmin=0, vmax=0.16, origin="lower")
    cells = [[ax_grid.text(j, i, "", ha="center", va="center", fontsize=8) for j in range(MAX_G + 1)]
             for i in range(MAX_G + 1)]
    ticks = [str(g) for g in range(MAX_G)] + [f"{MAX_G}+"]
    ax_grid.set_xticks(range(MAX_G + 1), ticks, color=FG)
    ax_grid.set_yticks(range(MAX_G + 1), ticks, color=FG)
    ax_grid.set_xlabel(f"buts {an}", color=MUTED)
    ax_grid.set_ylabel(f"buts {hn}", color=MUTED)
    ax_grid.tick_params(colors=MUTED, length=0)
    for s in ax_grid.spines.values():
        s.set_visible(False)
    ax_grid.set_title("Scores simulés", color=FG, fontsize=12, pad=8)

    verdict = fig.text(0.5, 0.075, "", ha="center", fontsize=15, fontweight="bold", linespacing=1.5)
    fig.text(0.5, 0.03, f"Modèle Elo + Poisson, {hist.pre['date'].max():%d/%m/%Y}. Un pronostic, pas une certitude.",
             ha="center", fontsize=8, color=MUTED)

    def draw(k: int):
        s = scores[:k]
        h, a = s[:, 0], s[:, 1]
        p = [(h > a).mean(), (h == a).mean(), (h < a).mean()]
        counter.set_text(f"{k:,}".replace(",", " "))
        for bar, t, v in zip(bars, pct, p):
            bar.set_width(v)
            t.set_text(f"{v * 100:.0f} %")
            t.set_x(min(v + 0.02, 0.86))
        g = np.zeros((MAX_G + 1, MAX_G + 1))
        np.add.at(g, (np.minimum(h, MAX_G), np.minimum(a, MAX_G)), 1)
        g /= k
        grid_img.set_data(g)
        for i in range(MAX_G + 1):
            for j in range(MAX_G + 1):
                cells[i][j].set_text(f"{g[i, j] * 100:.0f} %" if g[i, j] >= 0.01 else "")
                cells[i][j].set_color(BG if g[i, j] > 0.1 else FG)
        if k == n:
            best = np.unravel_index(g[:MAX_G, :MAX_G].argmax(), (MAX_G, MAX_G))
            fav = int(np.argmax(p))
            name = [f"Favori : {hn}", "Issue la plus probable : nul", f"Favori : {an}"][fav]
            verdict.set_text(f"{name} ({p[fav] * 100:.0f} %)\nscore le plus probable : {best[0]}-{best[1]}")
            verdict.set_color([HOME_C, FG, AWAY_C][fav])
        return []

    anim = FuncAnimation(fig, draw, frames=list(steps), blit=False)
    writer = FFMpegWriter(fps=fps, bitrate=1800) if out.suffix == ".mp4" else PillowWriter(fps=fps)
    anim.save(str(out), writer=writer, savefig_kwargs={"facecolor": BG})
    plt.close(fig)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("home")
    p.add_argument("away")
    p.add_argument("--neutral", action="store_true")
    p.add_argument("--out", type=Path, default=None)
    a = p.parse_args()
    print(animate_match(a.home, a.away, a.neutral, a.out))
