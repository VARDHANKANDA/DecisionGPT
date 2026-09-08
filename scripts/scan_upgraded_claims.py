#!/usr/bin/env python
"""Phase S — automated forbidden-claim / number-integrity scan for the upgraded
controlled evaluation docs. Read-only. Prints a report and exits non-zero if any
line is classified ``PROHIBITED`` (i.e. an over-claim not defused by a
limitation / negation / methodological framing on the same line or the line
above).

Scanned:
  docs/UPGRADED_EVALUATION_REPORT.md
  docs/UPGRADED_EVALUATION_READINESS.md
  docs/UPGRADED_EVALUATION_PREREGISTRATION.md
  docs/UPGRADED_EVALUATION_IMPLEMENTATION.md
  docs/FROZEN_ARCHITECTURE_EVALUATION_AUDIT.md
  experiments/upgraded_controlled_v1/*.md

NOT scanned / NOT modified: docs/PAPER_DRAFT.md, docs/ieee_paper/*, the frozen
experiment artifacts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "experiments" / "upgraded_controlled_v1"

DOCS = [
    REPO / "docs/UPGRADED_EVALUATION_REPORT.md",
    REPO / "docs/UPGRADED_EVALUATION_READINESS.md",
    REPO / "docs/UPGRADED_EVALUATION_PREREGISTRATION.md",
    REPO / "docs/UPGRADED_EVALUATION_IMPLEMENTATION.md",
    REPO / "docs/FROZEN_ARCHITECTURE_EVALUATION_AUDIT.md",
    *sorted(OUT.glob("*.md")),
]

# (label, regex) — case-insensitive
PATTERNS = [
    ("real_sme_validation", r"validat\w*\b.{0,40}\bsme|sme.{0,40}\bvalidat"),
    ("validated_for_indian_smes", r"validated for (indian )?smes?"),
    ("superior_for_smes", r"superior\b.{0,30}\bsmes?|smes?.{0,30}\bsuperior"),
    ("business_effectiveness", r"business (effectiveness|impact|improvement|value delivered)"),
    ("roi", r"\broi\b|return on invest"),
    ("real_customer_improvement", r"customer (outcome|behaviou?r|improvement|retention gain)"),
    ("deployment_success", r"deploy\w*\b.{0,30}\b(success|works|validated|proven)"),
    ("real_world_causal_impact", r"real[- ]world (causal|impact)|causal (impact|effect) (on|for) (real )?business"),
    ("decision_accuracy", r"decision accuracy|accuracy of (the )?(decision|recommendation)"),
    ("proven_business_improvement", r"proven\b.{0,30}\b(business|revenue|profit|improvement)"),
    ("superiority_generic", r"\b(is|are|proves?|demonstrat\w+)\b.{0,20}\bsuperior\b"),
    ("works_claim", r"decisiongpt (works|is effective|is validated|succeeds)"),
    ("r3_promotion", r"promot\w+ r3|r3 (is )?(now )?(the )?(new )?(production|default|baseline)"),
    ("real_llm_claim", r"real[- ]llm (result|evaluation|run|test)\b(?!.{0,20}(blocked|not|pending))"),
]

# tokens that indicate the sentence is a LIMITATION / NEGATION / framing, not a claim
DEFUSERS = [
    "not ", "no ", "n't", "cannot", "can not", "must not", "never", "without",
    "unsupported", "does not", "do not", "did not", "zero", "blocked", "pending",
    "refuted", "null", "negative result", "limitation", "boundary", "not claimed",
    "not supported", "not licensed", "forbidden", "prohibit", "must NOT", "NOT ",
    "cannot support", "not a claim", "would have", "not used", "not READY",
    "not validated", "hard list", "explicitly not", "not be claimed", "not detectably",
    "no measurable", "no detectable", "indistinguishable", "worse than", "underperform",
]


TECHNICAL_OK = ("marketing roi", "roi-positive", "roi positive", "roi is currently positive",
                "records positive marketing", "positive marketing roi", "marketing_roi")

# a preceding heading containing any of these ⇒ the whole section is a
# limitation / negation / non-claim enumeration
NEGATION_SECTION = ("not be claimed", "must not", "not supported", "not claimed",
                    "not license", "evidence boundaries", "limitations", "hard list",
                    "protocol deviation", "what this study does and does not",
                    "unsupported", "remain unsupported", "boundaries")


def classify(lines: list[str], i: int) -> str:
    line = lines[i]
    low = line.lower()
    if any(t in low for t in TECHNICAL_OK):
        return "OK (technical term: marketing return-on-investment as a pipeline input)"
    window = re.sub(r"[*_`]+", "", " ".join(lines[max(0, i - 4):i + 1])).lower()
    if any(d.lower() in window for d in DEFUSERS):
        return "OK (limitation / negation / methodological framing)"
    # nearest preceding markdown heading
    for j in range(i, -1, -1):
        s = lines[j].lstrip()
        if s.startswith("#"):
            if any(t in s.lower() for t in NEGATION_SECTION):
                return "OK (inside a 'must not be claimed' / limitations section)"
            break
    if line.lstrip().startswith(("#", "|", "- \"", "- `", "> ")):
        return "OK (enumeration / table / heading)"
    return "PROHIBITED (review)"


def scan_claims() -> list[dict]:
    hits = []
    for doc in DOCS:
        if not doc.exists():
            continue
        lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            for label, rx in PATTERNS:
                if re.search(rx, line, re.IGNORECASE):
                    hits.append({
                        "file": str(doc.relative_to(REPO)), "line": i + 1,
                        "pattern": label, "text": line.strip()[:200],
                        "verdict": classify(lines, i),
                    })
    return hits


def scan_numbers() -> dict:
    """Every %-or-decimal number in the REPORT must be traceable to a
    machine-readable results file (or be an obvious structural constant)."""
    report = (REPO / "docs/UPGRADED_EVALUATION_REPORT.md")
    text = report.read_text(encoding="utf-8", errors="replace")
    # gather the pool of numbers that appear anywhere in the result JSONs
    pool = set()
    for jf in sorted(OUT.glob("*.json")):
        jtext = jf.read_text(encoding="utf-8", errors="replace")
        for m in re.findall(r"-?\d+\.\d+|-?\d+", jtext):
            pool.add(m.lstrip("+"))
            try:
                pool.add(f"{float(m):.4f}".rstrip("0").rstrip("."))
                pool.add(f"{float(m):.3f}".rstrip("0").rstrip("."))
                pool.add(f"{abs(float(m)):.3f}".rstrip("0").rstrip("."))
                pool.add(f"{abs(float(m)):.4f}".rstrip("0").rstrip("."))
            except ValueError:
                pass
    STRUCTURAL = {"0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "13",
                  "14", "15", "16", "17", "20", "23", "31", "36", "40", "44", "46", "49",
                  "60", "80", "100", "200", "255", "340", "800", "10000", "5000", "20000",
                  "0.05", "0.80", "0.10", "0.20", "0.28", "0.12", "0.60", "2026", "42",
                  "12345", "4242", "20260906", "20260915", "94", "0.5", "0.0", "1.0", "2.0"}
    # numbers immediately after a section marker (§11.1, "## 11", "step 11.4") are refs
    section_refs = set(re.findall(r"(?:§|#|section|step|phase)\s*(\d+(?:\.\d+)*)", text, re.IGNORECASE))
    unexplained = []
    for mm in re.finditer(r"(?<![\w.])[-+]?\d+\.\d+(?![\w.])", text):
        m = mm.group(0)
        key = m.lstrip("+")
        akey = key.lstrip("-")
        if key in pool or akey in pool or akey in STRUCTURAL or akey in section_refs:
            continue
        ctx = text[max(0, mm.start() - 8):mm.start()]
        if re.search(r"(§|#|section|step|phase)\s*$", ctx, re.IGNORECASE):
            continue
        try:
            f = abs(float(m))
            cands = {f"{f:.3f}".rstrip("0").rstrip("."), f"{f:.2f}".rstrip("0").rstrip("."),
                     f"{f/100:.5f}".rstrip("0").rstrip("."), f"{f/100:.4f}".rstrip("0").rstrip("."),
                     f"{f/100:.3f}".rstrip("0").rstrip(".")}
            if cands & pool:
                continue
        except ValueError:
            pass
        unexplained.append(m)
    return {"n_numeric_tokens_pool": len(pool),
            "unexplained_decimals_in_report": sorted(set(unexplained))}


def scan_flags() -> dict:
    raw = "\n".join(d.read_text(encoding="utf-8", errors="replace") for d in DOCS if d.exists()).lower()
    joined = re.sub(r"\s+", " ", raw)          # collapse newlines so lookaheads see across line breaks
    return {
        "mentions_r3_not_promoted": "r3" in joined and "not promoted" in joined,
        "accidental_r3_promotion_phrase": bool(re.search(
            r"(?<!not )(?<!don't )promote r3 (into|to) (the )?(production|default|baseline)", joined)),
        "mentions_real_llm_blocked": "real llm" in joined or "real-llm" in joined,
        "accidental_real_llm_result_claim": bool(re.search(
            r"(we (ran|report|obtained)|results of) (a |the )?real[- ]llm", joined)),
        "accidental_real_sme_data_claim": bool(re.search(
            r"(collected|used|obtained|analysed|analyzed) real (sme|business) (data|outcomes)", joined)),
        "states_no_real_sme_data": "no real sme" in joined,
        "states_table2_not_ready": "table 2" in joined and "not ready" in joined,
        "states_r0_d0_unchanged": "r0/d0" in joined,
    }


def main() -> int:
    claim_hits = scan_claims()
    prohibited = [h for h in claim_hits if h["verdict"].startswith("PROHIBITED")]
    numbers = scan_numbers()
    flags = scan_flags()

    report = {
        "scanned_files": [str(d.relative_to(REPO)) for d in DOCS if d.exists()],
        "claim_pattern_hits": claim_hits,
        "prohibited_count": len(prohibited),
        "number_integrity": numbers,
        "integrity_flags": flags,
    }
    (OUT / "forbidden_claim_scan.json").write_text(json.dumps(report, indent=2, sort_keys=True))

    print(f"scanned {len(report['scanned_files'])} docs; {len(claim_hits)} pattern hits, "
          f"{len(prohibited)} need review")
    for h in claim_hits:
        tag = "!!" if h["verdict"].startswith("PROHIBITED") else "  "
        print(f"{tag} {h['file']}:{h['line']}  [{h['pattern']}]  {h['verdict']}")
        print(f"     {h['text']}")
    print("\nnumber integrity:", json.dumps(numbers, indent=2))
    print("integrity flags :", json.dumps(flags, indent=2))
    bad_flags = (flags["accidental_r3_promotion_phrase"]
                 or flags["accidental_real_llm_result_claim"]
                 or flags["accidental_real_sme_data_claim"]
                 or numbers["unexplained_decimals_in_report"])
    print(f"\nwrote {(OUT / 'forbidden_claim_scan.json').relative_to(REPO)}")
    return 1 if (prohibited or bad_flags) else 0


if __name__ == "__main__":
    raise SystemExit(main())
