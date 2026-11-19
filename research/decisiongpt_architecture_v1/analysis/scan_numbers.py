"""Claims-audit helper: list every numeric literal in the paper text that is NOT produced by a generated macro, for manual review.

    python research/decisiongpt_architecture_v1/analysis/scan_numbers.py  > results/hand_typed_numbers.txt
"""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SEC = REPO / "overleaf" / "architecture_paper_v1" / "sections"
for f in sorted(SEC.glob("*.tex")):
    for i, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
        s = re.sub(r"\\(cite|ref|label|input|includegraphics|texttt|cref)\{[^}]*\}", "", line)
        s = re.sub(r"\\[A-Za-z]+\{\}", "", s)                      # generated macros are used as \name{}
        s = re.sub(r"\\(RR|UU|mech|rob|fb|near|sOne|sTwo|sThree|mfive|ret|ch|reg|sec|ratio|ovh|det|rerun|n[A-Z]|simcalls|fcruns|agentevals|llmreq|costerrors)[A-Za-z]*", "", s)
        nums = re.findall(r"(?<![A-Za-z\\{])\d+(?:[.,]\d+)?(?:\\,\d+)?%?", s)
        nums = [n for n in nums if n not in ("1", "2", "3")]
        if nums:
            print(f"{f.name}:{i}: {nums}  | {line.strip()[:150]}")
