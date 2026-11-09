"""Export PDF d'un rapport publié, sans LLM."""
from __future__ import annotations

import json

from pypdf import PdfReader

from src import config, export


def _report(tmp_path, **extra):
    p = config.state_dir() / "reports" / "france-vs-spain.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"home_team": "France", "away_team": "Spain", "title": "France - Espagne : l’avant-match",
                             "content": "## Forme\n- **France** : 9 tirs en demi-finale\n- Espagne : 16 tirs en finale\n\nÉlan défensif à surveiller.",
                             **extra}, ensure_ascii=False), encoding="utf-8")
    return p


def test_pdf_has_title_accents_and_bullets(tmp_path):
    out = export.report_to_pdf(_report(tmp_path))
    assert out.read_bytes().startswith(b"%PDF")
    text = PdfReader(str(out)).pages[0].extract_text()
    for s in ("l’avant-match", "Forme", "9 tirs", "Élan défensif", "StatsBomb"):
        assert s in text, s
    assert "**" not in text


def test_pdf_includes_shot_maps(tmp_path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    img = config.state_dir() / "plots" / "shots-3942752-france.png"
    img.parent.mkdir(parents=True, exist_ok=True)
    plt.figure(figsize=(2, 2)); plt.plot([0, 1]); plt.savefig(img); plt.close()
    report = json.loads(_report(tmp_path).read_text(encoding="utf-8"))
    assert export.report_plots(report, config.state_dir()) == [img]
    assert len(PdfReader(str(export.report_to_pdf(_report(tmp_path)))).pages[0].images) == 1


def test_published_reports_lists_json(tmp_path):
    p = _report(tmp_path)
    assert export.published_reports() == [p]
