#!/usr/bin/env python
"""Phase 39 — forbidden-term / claim-discipline scan for the R1 documentation.

Read-only. Scans the R1 docs (and any file passed on the command line) for
unsupported use of over-claiming terms and for "accuracy" used where the metric
is regret / MAE / RMSE / MAPE / precision / recall / F1 / AUC. Prints a report
and exits non-zero if any line is classified PROHIBITED (an over-claim not
defused by a negation / limitation / methodological framing / direct quote of a
forbidden phrase in a "must not" list).

NOT scanned / NOT modified: docs/PAPER_DRAFT.md, docs/ieee_paper/*, V1/V2
artifacts, production code.
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
OUT = REPO / "experiments" / "r1"
DOCS = [
    REPO / "docs/R1_DT_DIAGNOSTIC.md",
    REPO / "docs/R1_INFORMATION_BOUNDARY.md",
    REPO / "docs/R1_PREREGISTRATION.md",
    REPO / "docs/R1_PRELOCK_GATE.md",
    REPO / "docs/R1_RESULTS.md",
    REPO / "docs/R1_AUDIT.md",
    REPO / "docs/R1_HOSTILE_REVIEW.md",
    REPO / "docs/R1_PUBLICATION_READINESS.md",
    REPO / "docs/R1_FINAL_REPORT.md",
    REPO / "docs/FINAL_SUBMISSION_AUDIT.md",
    REPO / "docs/ieee_paper_r1/main.tex",
    REPO / "docs/ieee_paper_r1/README.md",
    *sorted(OUT.glob("*.md")),
]

PATTERNS = [
    ("validated", r"\bvalidat(e|ed|es|ion)\b"),
    ("real_world", r"\breal[- ]world\b"),
    ("causal", r"\bcausal(ly)?\b|\bcauses? better\b"),
    ("roi", r"\broi\b|return on invest"),
    ("sme_impact", r"\bsme (impact|outcome|effect|improvement)\b|indian sme"),
    ("business_impact", r"\bbusiness (impact|improvement|outcome|performance)\b"),
    ("superior", r"\bsuperior(ity)?\b"),
    ("proves", r"\bprove(s|d|n)?\b|\bguarantee(s|d)?\b"),
    ("production_validated", r"production[- ]validated|validated in production"),
    ("customer_outcome", r"\bcustomer (outcome|behaviou?r|improvement)\b"),
    ("accuracy_misuse", r"\baccurac(y|ies)\b|\baccurate\b"),
]

DEFUSERS = [
    "development/validation", "development / validation", "validation partition",
    "validation set", "validation famil", "include-validation", "dev/validation",
    "pre-lock diagnostic", "prelock-diagnose", "proves nothing", "prove nothing",
    "nothing about", "/ validation", "development 11", "outperforming them",
    "not ", "no ", "n't", "cannot", "can not", "must not", "never", "without",
    "unsupported", "does not", "do not", "did not", "zero", "blocked", "pending",
    "not established", "not claim", "not a claim", "not licensed", "forbidden",
    "prohibit", "must NOT", "NOT ", "not supported", "not proven", "not validated",
    "not causal", "not superior", "regret", "mae", "rmse", "mape", "not accuracy",
    "not real-world", "not sme", "not roi", "would require", "not be claimed",
    "hostile", "reviewer could", "threat", "limitation", "does NOT establish",
    "cannot establish", "not establish", "nothing here transfers", "stop short of",
    "regret metric", "validation partition", "to the validation", "makes no claim",
    "no claim of", "carries no", "we make no",
]
NEG_SECTION = ("must not", "forbidden", "not be claimed", "not supported", "not established",
               "threats to validity", "limitations", "what this experiment can not",
               "cannot establish", "claims the paper", "claim discipline", "audit")
# "accuracy" is fine only if it is NOT about a regret/error metric
_ACC_OK_CONTEXT = ("bot detection", "not accuracy", "never .*accuracy", "misuse", "forbidden-term")


def classify(lines: list[str], i: int, label: str) -> str:
    line = lines[i]
    low = line.lower()
    window = re.sub(r"[*_`]+", "", " ".join(lines[max(0, i - 4):i + 1])).lower()
    if label == "accuracy_misuse":
        # allowed only when explicitly discussing that the term is misused / forbidden
        if any(re.search(p, low) for p in _ACC_OK_CONTEXT) or "never call" in window or "not call" in window \
                or "forbidden" in window or "regret metric" in window or "scan" in window:
            return "OK (discussing the term itself / forbidden-term scan)"
        return "PROHIBITED (regret is not accuracy)"
    if any(d.lower() in window for d in DEFUSERS):
        return "OK (negation / limitation / methodological framing)"
    for j in range(i, -1, -1):
        s = lines[j].lstrip()
        is_md_head = s.startswith("#")
        is_tex_head = s.startswith(("\\section", "\\subsection", "\\section*", "\\subsection*"))
        if is_md_head or is_tex_head:
            if any(t in s.lower() for t in NEG_SECTION):
                return "OK (inside a limitations / must-not-claim / audit section)"
            break
    if line.lstrip().startswith(("#", "|", "- \"", "> ", "- `")):
        return "OK (heading / table / quoted forbidden phrase)"
    return "PROHIBITED (review)"


def main() -> int:
    hits = []
    for doc in DOCS:
        if not doc.exists():
            continue
        lines = doc.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines):
            for label, rx in PATTERNS:
                if re.search(rx, line, re.IGNORECASE):
                    hits.append({"file": str(doc.relative_to(REPO)), "line": i + 1, "pattern": label,
                                 "text": line.strip()[:200], "verdict": classify(lines, i, label)})
    prohibited = [h for h in hits if h["verdict"].startswith("PROHIBITED")]
    rep = {"scanned": [str(d.relative_to(REPO)) for d in DOCS if d.exists()],
           "n_hits": len(hits), "n_prohibited": len(prohibited), "hits": hits}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "forbidden_term_scan.json").write_text(json.dumps(rep, indent=2))
    print(f"scanned {len(rep['scanned'])} docs; {len(hits)} term hits, {len(prohibited)} PROHIBITED")
    for h in hits:
        tag = "!!" if h["verdict"].startswith("PROHIBITED") else "  "
        print(f"{tag} {h['file']}:{h['line']} [{h['pattern']}] {h['verdict']}")
        if tag == "!!":
            print(f"     {h['text']}")
    print(f"\nwrote {(OUT / 'forbidden_term_scan.json').relative_to(REPO)}")
    return 1 if prohibited else 0


if __name__ == "__main__":
    raise SystemExit(main())
