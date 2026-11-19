"""Freeze record of forecast_study_v2: SHA-256 of the protocol documents, the code and the tests, taken BEFORE any confirmatory (W2/W3, and the fresh-store W1) validation or test outcome is read.

    python -m research.forecast_study_v2.freeze create     # writes FREEZE.json (refuses to overwrite)
    python -m research.forecast_study_v2.freeze verify     # recomputes and compares; exits 1 on any difference

The freeze is an INTERNAL, timestamped hash record (not a public pre-registration). The test stage of the pipeline calls ``verify()`` and stops if anything changed.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

from .common import ROOT, STUDY, sha256_file, versions

FREEZE = STUDY / "FREEZE.json"
PROTOCOL_FILES = ["EXPERIMENT_PROTOCOL.md", "RESEARCH_QUESTION_AND_CONTRIBUTIONS.md", "DATA_AUDIT.md", "LEAKAGE_AUDIT.md", "WINDOW_USE_AUDIT.md", "PREREGISTRATION_DRAFT.md"]


def _files() -> list[Path]:
    fs = [STUDY / n for n in PROTOCOL_FILES if (STUDY / n).exists()]
    fs += sorted(STUDY.glob("*.py")) + sorted(STUDY.glob("*.sh")) + sorted((STUDY / "tests").glob("*.py")) + sorted((STUDY / "tools").glob("*.py"))
    fs += [ROOT / "tests" / "unit" / "test_forecast_study_v2.py"] if (ROOT / "tests" / "unit" / "test_forecast_study_v2.py").exists() else []
    return fs


def current() -> dict:
    return {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in _files()}


def create() -> dict:
    if FREEZE.exists():
        raise SystemExit("FREEZE.json exists; the freeze record is append-only history and is never overwritten")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    rec = {"frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "git_head": head,
           "statement": "INTERNAL freeze (timestamped hash record, not a public pre-registration): protocol documents, code and tests were fixed before any confirmatory outcome was read. "
                        "Later changes are only allowed as dated entries in DEVIATIONS.md.", "versions": versions(), "sha256": current()}
    FREEZE.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def verify() -> None:
    if not FREEZE.exists():
        raise SystemExit("FREEZE.json is missing: the test stage is not allowed before the freeze")
    rec = json.loads(FREEZE.read_text(encoding="utf-8"))
    cur = current()
    bad = [k for k, v in rec["sha256"].items() if cur.get(k) != v]
    if bad:
        raise SystemExit(f"frozen files changed since the freeze: {bad}")


if __name__ == "__main__":
    if sys.argv[1] == "create":
        print(json.dumps({k: v[:12] for k, v in create()["sha256"].items()}, indent=1))
    else:
        verify()
        print("freeze verified:", len(json.loads(FREEZE.read_text(encoding="utf-8"))["sha256"]), "files unchanged")
