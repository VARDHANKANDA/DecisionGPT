"""Assemble MANUSCRIPT_R3.md from quality_gate/manuscript_parts_r3/part*.md, generated tables (v2 tables/ and quality_gate/tables/), figures and the reference list.
R2 (MANUSCRIPT_R2.md) is never modified. Fails on unresolved placeholders.

    python research/forecast_study_v2/quality_gate/tools/assemble_r3.py
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
QG = HERE / "quality_gate"
src = (HERE / "tools" / "assemble_manuscript.py").read_text(encoding="utf-8")
g = {"__file__": str(HERE / "tools" / "assemble_manuscript.py"), "__name__": "x"}
exec(compile(src.split("order = sorted(refs")[0], "assemble_manuscript.py", "exec"), g)
fmt, refs, KEY = g["fmt"], g["refs"], g["KEY"]
order = sorted(refs, key=lambda e: (KEY[e["id"]].split("|")[0], KEY[e["id"]].split("|")[1]))
body = "\n\n".join(fmt(e) for e in order)
PARTS = sorted((QG / "manuscript_parts_r3").glob("part*.md"))
text = "\n\n".join(p.read_text(encoding="utf-8").strip() for p in PARTS)


def table(m):
    for d in (QG / "tables", HERE / "tables"):
        f = d / f"{m.group(1)}.md"
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
    raise FileNotFoundError(m.group(1))


def fig(m):
    name, cap = m.group(1), m.group(2)
    path = f"quality_gate/figures/{name}.png" if (QG / "figures" / f"{name}.png").exists() else f"figures/{name}.png"
    assert (HERE / path).exists(), path
    return f"![{cap}]({path})\n\n*{cap}*"


import json


def nums():
    S = json.loads((QG / "results" / "audit_sensitivity.json").read_text(encoding="utf-8"))
    A = S["A_weekly_dependence"]
    cells = [r for w in A.values() for r in w.values()]
    width = lambda ci: ci[1] - ci[0]  # noqa: E731
    widen = max(100 * (width(r["H1_stationary_weeks"]["ci95"]) - width(r["frozen_ci_H1"])) for r in cells)
    E1 = json.loads((QG / "results" / "e1_reproduction.json").read_text(encoding="utf-8"))
    out = {"e1_methods": str(sum(r["methods_compared"] for r in E1["cells"].values())), "e1_arrays": str(sum(r["arrays_compared"] for r in E1["cells"].values()))}
    out.update({"max_lag1": f"+{max(r['lag1_weekly_difference'] for r in cells):.2f}", "h1_same_all": str(sum(r["H1_stationary_weeks"]["verdict_frozen_rule"] == r["frozen"]["H1"] for r in cells)),
            "h2_same_all": str(sum(1 for r in cells if r["H2_stationary_weeks"] and r["H2_stationary_weeks"]["verdict_frozen_rule"] == r["frozen"]["H2"])),
            "pin_neg_09": str(sum(1 for r in S["C_pinball_exploratory"].values() if r["0.9"]["improvement"] < 0)), "max_widen_pp": f"{widen:.1f}"})
    return out


NUM = nums()
text = re.sub(r"\{\{NUM:([A-Za-z0-9_]+)\}\}", lambda m: NUM[m.group(1)], text)
text = re.sub(r"\{\{TABLE:([A-Za-z0-9_]+)\}\}", table, text)
text = re.sub(r"\{\{FIG:([A-Za-z0-9_]+)\|(.*?)\}\}", fig, text, flags=re.S)
assert "{{" not in text, re.findall(r"\{\{[^}]*\}\}", text)
text += ("\n\n## References\n\n*Bibliographic metadata from Crossref (29 DOI entries; `REFERENCE_AUDIT.csv`); Ke et al. checked on the NeurIPS proceedings page, Damato et al. on the arXiv API, Chen (2012) on the UCI page, "
         "Koenker & Bassett pages on the Econometric Society page (2026-10-22). The level at which each source was read (full text, abstract, metadata, not accessed) is in `quality_gate/REFERENCE_AND_RIGHTS_AUDIT.md`; most claims were checked against abstracts only, "
         "the M5 report was read in a pre-publication copy, and Kolassa (2020) and the published M5 article were not read.*\n\n" + body + "\n")
(HERE / "MANUSCRIPT_R3.md").write_text(text, encoding="utf-8")
print("MANUSCRIPT_R3.md words:", len(text.split()), "| parts:", [p.name for p in PARTS], "| tables:", text.count("*Source:"), "| figures:", text.count("](figures/"))
