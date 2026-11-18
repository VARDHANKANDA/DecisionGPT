"""Tests for the architecture-paper analysis scripts (research/decisiongpt_architecture_v1/analysis).

These cover the pure statistical helpers and, when the generated results exist, consistency of the stored-vs-recomputed contrasts. They never run the cost measurement.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
AN = REPO / "research" / "decisiongpt_architecture_v1" / "analysis"
RES = REPO / "research" / "decisiongpt_architecture_v1" / "results"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"arch_{name}", AN / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def dq():
    return _load("decision_quality")


def test_holm_matches_hand_calculation(dq):
    out = dq.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert out["a"] == pytest.approx(0.03)          # 3 * 0.01
    assert out["c"] == pytest.approx(0.06)          # 2 * 0.03
    assert out["b"] == pytest.approx(0.06)          # max(previous, 1 * 0.04) is 0.06: monotone


def test_holm_caps_at_one(dq):
    assert dq.holm({"a": 0.6, "b": 0.7})["b"] == 1.0


def test_reference_regret_formula(dq):
    base = {"oracle": {"value": 10.0, "worst_value": 0.0}, "naive": {"value": 4.0}}
    assert dq.ref_regret(base, "naive") == pytest.approx(0.6)


def test_reference_regret_degenerate_span_is_none(dq):
    base = {"oracle": {"value": 5.0, "worst_value": 5.0}, "naive": {"value": 5.0}}
    assert dq.ref_regret(base, "naive") is None


def test_paired_contrast_sign_and_counts(dq):
    per = {f"s{i}": {"X": [0.2], "Y": [0.5]} for i in range(10)}
    fam = {k: "f" for k in per}
    out = dq.paired(per, fam, "X", "Y", np.random.default_rng(0))
    assert out["mean_diff_a_minus_b"] == pytest.approx(-0.3)
    assert out["a_better_(lower)"] == 10 and out["a_worse_(higher)"] == 0 and out["ties"] == 0
    assert out["ci95"][1] < 0 and out["rank_biserial_a_vs_b"] < 0


def test_paired_all_ties_gives_p_one(dq):
    per = {f"s{i}": {"X": [0.3], "Y": [0.3]} for i in range(5)}
    out = dq.paired(per, {k: "f" for k in per}, "X", "Y", np.random.default_rng(0))
    assert out["wilcoxon_p"] == 1.0 and out["ties"] == 5


@pytest.mark.skipif(not (RES / "replication_check.json").exists(), reason="analysis results not generated")
def test_recomputation_matches_stored_means_and_p_values():
    rc = json.loads((RES / "replication_check.json").read_text(encoding="utf-8"))
    assert rc["summary"]["mean_and_p_all_match"], rc["summary"]["mismatches"]


@pytest.mark.skipif(not (RES / "cost_summary.json").exists(), reason="cost summary not generated")
def test_cost_summary_has_no_llm_requests_and_no_errors():
    cs = json.loads((RES / "cost_summary.json").read_text(encoding="utf-8"))
    assert cs["counts_per_decision"]["llm_network_requests_attempted_all"]["max"] == 0
    assert cs["n_errors"] == 0
