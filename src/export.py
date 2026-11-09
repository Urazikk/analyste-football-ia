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


def _para(pdf: Any, w: float, h: float, text: str, **kw: Any) -> None:
    """Paragraphe qui ramène le curseur à la marge de gauche (sinon fpdf2 enchaîne à droite)."""
    from fpdf.enums import XPos, YPos

    pdf.multi_cell(w, h, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, **kw)


IMAGE_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)$")


def _cells(line: str) -> list[str]:
    return [c.strip().replace("**", "") for c in line.strip().strip("|").split("|")]


def _render_markdown(pdf: Any, md: str, width: float) -> None:
    """Sous-ensemble du Markdown de report.to_markdown : titres, paragraphes, puces, tableaux, images."""
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        text = lines[i].strip()
        if text.startswith("|"):  # bloc de tableau : en-tête, séparateur, lignes
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.fullmatch(r"\|?[\s:|-]+\|?", lines[i].strip()):
                    block.append(_cells(lines[i]))
                i += 1
            from fpdf.fonts import FontFace

            pdf.set_font("DejaVu", "", 7.5)
            head = FontFace(emphasis="BOLD", fill_color=(238, 242, 247))
            with pdf.table(width=width, line_height=4.2, first_row_as_headings=True,
                           headings_style=head, text_align="LEFT") as table:
                for row in block:
                    r = table.row()
                    for c in row:
                        r.cell(c)
            pdf.set_font("DejaVu", "", 10)
            pdf.ln(2)
            continue
        i += 1
        if not text:
            pdf.ln(2)
        elif m := re.match(r"^(#{1,4})\s+(.*)", text):
            pdf.set_font("DejaVu", "B", {1: 16, 2: 13}.get(len(m.group(1)), 11))
            _para(pdf, width, 7, m.group(2).replace("**", ""))
            pdf.set_font("DejaVu", "", 10)
        elif m := IMAGE_RE.match(text):
            if Path(m.group(1)).is_file():
                pdf.image(m.group(1), w=min(width, 95))
        else:
            if re.match(r"^[-*•]\s+", text):
                text = "•  " + re.sub(r"^[-*•]\s+", "", text)
            if re.fullmatch(r"\*[^*].*[^*]\*", text):  # ligne en italique : *France - Espagne*
                text = text[1:-1]
            _para(pdf, width, 5.5, text, markdown=True)


def report_to_pdf(report_path: Path, out: Path | None = None) -> Path:
    """Écrit le PDF à côté du JSON (ou dans out) et renvoie son chemin.

    Rapport structuré (champ sections) : mise en page de report.to_markdown (forme, confrontations,
    dernier match et cartes des tirs). Sinon : titre, analyse et cartes des tirs trouvées.
    """
    from fpdf import FPDF

    from src import report as rep

    report = json.loads(report_path.read_text(encoding="utf-8"))
    out = out or report_path.with_suffix(".pdf")
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    fonts = _font_dir()
    pdf.add_font("DejaVu", "", str(fonts / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(fonts / "DejaVuSans-Bold.ttf"))
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    if report.get("sections"):
        _render_markdown(pdf, rep.to_markdown(report), width)
    else:
        _render_markdown(pdf, f"# {report.get('title') or 'Rapport d’avant-match'}\n\n"
                              f"{report.get('home_team', '')} - {report.get('away_team', '')}\n\n"
                              + report.get("content", ""), width)
        for img in report_plots(report, config.state_dir()):
            pdf.ln(3)
            pdf.image(str(img), w=min(width, 150))

    pdf.ln(4)
    pdf.set_font("DejaVu", "", 8)
    _para(pdf, width, 4, f"Exporté le {date.today().isoformat()}. Données : StatsBomb open data. Analyse rédigée "
                             "par l'agent (niveau 2), sections chiffrées calculées par le code, rapport publié après "
                             "validation de l'utilisateur.")
    out.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out))
    return out


def published_reports(state_dir: Path | None = None) -> list[Path]:
    """Rapports publiés, du plus récent au plus ancien."""
    d = (state_dir or config.state_dir()) / "reports"
    return sorted(d.glob("*.json"), key=os.path.getmtime, reverse=True) if d.is_dir() else []
