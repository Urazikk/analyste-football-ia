"""Export PDF d'un rapport d'avant-match publié (STATE_DIR/reports/<affiche>.json).

Pas un outil de l'agent : la seule action est la publication, validée par l'utilisateur. L'export
se fait ensuite depuis l'interface. Police DejaVu fournie par matplotlib (accents, apostrophes).
"""
from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from src import config


def _font_dir() -> Path:
    import matplotlib

    return Path(matplotlib.get_data_path()) / "fonts" / "ttf"


def report_plots(report: dict[str, Any], state_dir: Path) -> list[Path]:
    """Images du rapport : champ « plots » s'il existe, sinon les cartes de tirs des deux équipes."""
    from src.tools import report_slug

    if report.get("plots"):
        return [Path(p) for p in report["plots"] if Path(p).is_file()]
    plots = state_dir / "plots"
    if not plots.is_dir():
        return []
    teams = {report_slug(report.get("home_team", "")), report_slug(report.get("away_team", ""))}
    return sorted(p for p in plots.glob("shots-*.png") if any(p.stem.endswith("-" + t) for t in teams if t))


def report_to_pdf(report_path: Path, out: Path | None = None) -> Path:
    """Écrit le PDF à côté du JSON (ou dans out) et renvoie son chemin."""
    from fpdf import FPDF

    report = json.loads(report_path.read_text(encoding="utf-8"))
    out = out or report_path.with_suffix(".pdf")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    fonts = _font_dir()
    pdf.add_font("DejaVu", "", str(fonts / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(fonts / "DejaVuSans-Bold.ttf"))
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("DejaVu", "B", 16)
    pdf.multi_cell(width, 8, report.get("title") or "Rapport d'avant-match")
    pdf.set_font("DejaVu", "", 10)
    pdf.multi_cell(width, 6, f"{report.get('home_team', '')} - {report.get('away_team', '')}   ·   "
                             f"exporté le {date.today().isoformat()}")
    pdf.ln(3)

    for line in report.get("content", "").splitlines():
        text = line.strip()
        if not text:
            pdf.ln(2)
            continue
        if m := re.match(r"^(#{1,4})\s+(.*)", text):
            pdf.set_font("DejaVu", "B", 13 if len(m.group(1)) <= 2 else 11)
            pdf.multi_cell(width, 7, m.group(2).replace("**", ""))
            pdf.set_font("DejaVu", "", 10)
            continue
        if re.match(r"^[-*•]\s+", text):
            text = "•  " + re.sub(r"^[-*•]\s+", "", text)
        pdf.multi_cell(width, 5.5, text, markdown=True)

    for img in report_plots(report, config.state_dir()):
        pdf.ln(3)
        pdf.image(str(img), w=min(width, 150))

    pdf.ln(4)
    pdf.set_font("DejaVu", "", 8)
    pdf.multi_cell(width, 4, "Données : StatsBomb open data. Rapport rédigé par l'agent (niveau 2) et publié après "
                             "validation de l'utilisateur. Chiffres issus des outils, voir la trace de l'exécution.")
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return out


def published_reports(state_dir: Path | None = None) -> list[Path]:
    """Rapports publiés, du plus récent au plus ancien."""
    d = (state_dir or config.state_dir()) / "reports"
    return sorted(d.glob("*.json"), key=os.path.getmtime, reverse=True) if d.is_dir() else []
