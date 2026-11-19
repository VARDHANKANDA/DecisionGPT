"""Assemble MANUSCRIPT_R2.md: manuscript_parts/part{0,1,2}*.md + generated tables (tables/*.md) + figures + reference list. Fails on unresolved placeholders.

    python research/forecast_study_v2/tools/assemble_manuscript_r2.py
"""
import html
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
src = (HERE / "tools" / "assemble_manuscript.py").read_text(encoding="utf-8")
# reuse the reference formatter without running the R1 assembly side effects
head = src.split("order = sorted(refs")[0]
g = {"__file__": str(HERE / "tools" / "assemble_manuscript.py"), "__name__": "x"}
exec(compile(head, "assemble_manuscript.py", "exec"), g)
fmt, refs, KEY = g["fmt"], g["refs"], g["KEY"]
order = sorted(refs, key=lambda e: (KEY[e["id"]].split("|")[0], KEY[e["id"]].split("|")[1]))
body = "\n\n".join(fmt(e) for e in order)
parts = [(HERE / "manuscript_parts" / f).read_text(encoding="utf-8").strip() for f in ("part0_front.md", "part1_front_and_methods.md", "part2_results_and_discussion.md")]
text = "\n\n".join(parts)


def table(m):
    return (HERE / "tables" / f"{m.group(1)}.md").read_text(encoding="utf-8").strip()


def fig(m):
    name, cap = m.group(1), m.group(2)
    return f"![{cap}](figures/{name}.png)\n\n*{cap}*"


text = re.sub(r"\{\{TABLE:([A-Za-z0-9_]+)\}\}", table, text)
text = re.sub(r"\{\{FIG:([A-Za-z0-9_]+)\|(.*?)\}\}", fig, text, flags=re.S)
assert "{{" not in text, re.findall(r"\{\{[^}]*\}\}", text)
text += ("\n\n## References\n\n*Bibliographic metadata from Crossref (29 DOI entries; `REFERENCE_AUDIT.csv`); Ke et al. checked on the NeurIPS proceedings page, Damato et al. on the arXiv API, Chen (2012) on the UCI page; Koenker & Bassett pages checked on the Econometric Society page (2026-10-22). Claim-level support is in `REFERENCE_CLAIM_CHECK.csv`: most claims were checked against abstracts only; the M5 report was read in a pre-publication copy.*\n\n" + body + "\n")
(HERE / "MANUSCRIPT_R2.md").write_text(text, encoding="utf-8")
print("MANUSCRIPT_R2.md words:", len(text.split()), "| tables:", text.count("*Source:"), "| figures:", text.count("](figures/"))
