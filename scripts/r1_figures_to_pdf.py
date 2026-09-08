#!/usr/bin/env python
"""Convert the frozen R1 figure SVGs to PDF for IEEEtran (pdflatex) compilation.

Read-only w.r.t. the numbers: this ONLY rasterises/vectorises the existing
`docs/ieee_paper_r1/figures/r1_figure{1..5}.svg` (themselves produced by
`scripts/r1_figures.py` from `experiments/r1/figure_data.json`). It does not read
`results.json`, recompute anything, or alter any value.

Usage:  python scripts/r1_figures_to_pdf.py
Requires: svglib + reportlab  (already in the repo's Python env), OR any of
          rsvg-convert / inkscape / cairosvg if you prefer those.
"""
from __future__ import annotations

import pathlib
import sys

FIG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "ieee_paper_r1" / "figures"


def main() -> int:
    try:
        from reportlab.graphics import renderPDF
        from svglib.svglib import svg2rlg
    except ImportError as e:  # pragma: no cover
        print(f"svglib/reportlab unavailable ({e}); "
              f"convert manually, e.g.  rsvg-convert -f pdf -o r1_figureN.pdf r1_figureN.svg")
        return 2

    svgs = sorted(FIG_DIR.glob("r1_figure*.svg"))
    if not svgs:
        print(f"no SVGs found in {FIG_DIR}")
        return 1
    n_ok = 0
    for svg in svgs:
        drawing = svg2rlg(str(svg))
        if drawing is None:
            print(f"FAIL  {svg.name}: svg2rlg returned None")
            continue
        out = svg.with_suffix(".pdf")
        renderPDF.drawToFile(drawing, str(out))
        print(f"OK    {svg.name} -> {out.name}  ({out.stat().st_size} bytes)")
        n_ok += 1
    print(f"\n{n_ok}/{len(svgs)} converted")
    return 0 if n_ok == len(svgs) else 1


if __name__ == "__main__":
    raise SystemExit(main())
