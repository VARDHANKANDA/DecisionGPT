"""Private, local overlap scan between the current manuscript and the authors' earlier manuscripts (no external service is used).

    python research/decisiongpt_architecture_v1/analysis/overlap_scan.py

Prose: k-word shingle overlap (k = 6 and 10) on lower-cased, LaTeX-stripped text; reported as the share of the CURRENT paper's shingles that also occur in each earlier manuscript, and
the longest verbatim run. Numbers: share of the numeric tokens of the current paper's compiled PDF that also occur in each earlier manuscript's text.
Writes results/prior_overlap_scan.json. Read-only with respect to every manuscript.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "research" / "decisiongpt_architecture_v1" / "results" / "prior_overlap_scan.json"
CUR_DIR = REPO / "overleaf" / "architecture_paper_v1"


def strip_tex(t: str) -> str:
    t = re.sub(r"(?m)^\s*%.*$", " ", t)
    t = re.sub(r"\\(cite|ref|label|input|includegraphics|cref|eqref)\{[^}]*\}", " ", t)
    t = re.sub(r"\\(begin|end)\{[^}]*\}", " ", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?", " ", t)
    t = re.sub(r"[\$\{\}\\~&^_]", " ", t)
    return re.sub(r"\s+", " ", t).lower()


def words(t: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9.\-+]*", t)


def shingles(w: list[str], k: int) -> set[tuple]:
    return {tuple(w[i:i + k]) for i in range(len(w) - k + 1)}


def longest_run(cur: list[str], prior_sh: set[tuple], k: int) -> int:
    best = run = 0
    for i in range(len(cur) - k + 1):
        if tuple(cur[i:i + k]) in prior_sh:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return best + k - 1 if best else 0


def pdf_text(p: Path) -> str:
    import fitz
    return " ".join(pg.get_text() for pg in fitz.open(p)).lower()


def nums(t: str) -> set[str]:
    return {x.rstrip(".") for x in re.findall(r"(?<![a-z\d])[+\-\u2212]?\d+(?:\.\d+)?(?:e-?\d+)?", t) if len(x.replace("0.", "").strip("+-\u2212")) >= 3}


def main():
    cur_pdf = pdf_text(CUR_DIR / "main.pdf")
    # use the .tex sources of the current paper for prose (macro names removed) and the PDF for numbers
    cur_tex = " ".join(strip_tex(p.read_text(encoding="utf-8")) for p in sorted((CUR_DIR / "sections").glob("*.tex")))
    cw = words(cur_tex)
    priors = {
        "docs/ieee_paper (original 60-pair paper)": REPO / "docs/ieee_paper/main.tex",
        "docs/ieee_paper_r1 (R1 paper, same title)": REPO / "docs/ieee_paper_r1/main.tex",
        "docs/ieee_paper_r2 (component composition)": REPO / "docs/ieee_paper_r2/main.tex",
        "overleaf/main.tex (broad system paper = DecisionGPT (1).pdf)": REPO / "overleaf/main.tex",
    }
    cur_nums = nums(cur_pdf)
    res = {"current_words": len(cw), "current_numeric_tokens": len(cur_nums), "priors": {}}
    for name, p in priors.items():
        pt = strip_tex(p.read_text(encoding="utf-8"))
        pw = words(pt)
        row = {"prior_words": len(pw)}
        for k in (6, 10):
            ps = shingles(pw, k)
            cs = shingles(cw, k)
            row[f"share_of_current_{k}word_shingles_found_in_prior"] = round(len(cs & ps) / max(1, len(cs)), 4)
        row["longest_verbatim_run_words"] = longest_run(cw, shingles(pw, 6), 6)
        pn = nums(pt)
        row["share_of_current_numeric_tokens_found_in_prior"] = round(len(cur_nums & pn) / max(1, len(cur_nums)), 4)
        res["priors"][name] = row
    pdf_prev = Path(r"C:\Users\VARDHAN\Downloads\DecisionGPT (1).pdf")
    if pdf_prev.exists():
        pt = pdf_text(pdf_prev)
        pw = words(pt)
        row = {"prior_words": len(pw)}
        for k in (6, 10):
            row[f"share_of_current_{k}word_shingles_found_in_prior"] = round(len(shingles(cw, k) & shingles(pw, k)) / max(1, len(shingles(cw, k))), 4)
        row["share_of_current_numeric_tokens_found_in_prior"] = round(len(cur_nums & nums(pt)) / max(1, len(cur_nums)), 4)
        res["priors"]["DecisionGPT (1).pdf (compiled previous paper, text only)"] = row
    OUT.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
