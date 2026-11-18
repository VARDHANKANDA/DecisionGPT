"""Unit tests for backend/app/evaluation/scenario_families_v2.py (V2 environment).

Pure module tests: no DB, no pipeline. Verify (a) System A is independent of the
pipeline and of System B, (b) the generated history is genuinely action-responsive
and the response is identifiable, (c) deterministic generation + round-trip,
(d) family-partition disjointness, (e) no id collision with V1 / the frozen study.
"""
import ast
import math

import numpy as np
import pytest

from app.evaluation import ground_truth as gt
from app.evaluation import scenario_families_v2 as v2


def test_system_A_imports_nothing_from_the_pipeline_or_system_B():
    src = (
        __import__("pathlib").Path(v2.__file__).read_text()
    )
    mods = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, ast.Import):
            mods += [a.name for a in n.names]
        elif isinstance(n, ast.ImportFrom):
            mods.append(n.module or "")
    for forbidden in ("digital_twin_service", "decision_service", "ground_truth",
                      "forecast_service", "app.agents", "app.services.decision"):
        assert not any(forbidden in m for m in mods), f"System A must not import {forbidden}"


def test_at_least_20_structurally_distinct_families():
    assert len(v2.FAMILY_IDS_V2) >= 20
    assert len(set(v2.FAMILY_IDS_V2)) == len(v2.FAMILY_IDS_V2)


def test_generation_is_deterministic_and_balanced():
    a = v2.generate_suite(110, master_seed=20260906)
    b = v2.generate_suite(110, master_seed=20260906)
    assert [s.scenario_id for s in a] == [s.scenario_id for s in b]
    assert v2.suite_checksum(a) == v2.suite_checksum(b)
    assert v2.suite_checksum(v2.generate_suite(110, master_seed=99)) != v2.suite_checksum(a)
    counts = {}
    for s in a:
        counts[s.family_id] = counts.get(s.family_id, 0) + 1
    assert max(counts.values()) - min(counts.values()) <= 1


def test_history_is_action_responsive_and_identifiable():
    """log(units) regressed on log(price)+log(spend) over the GENERATED history
    should recover a_elast reasonably (the V1 bug was zero recoverable signal)."""
    suite = v2.generate_suite(len(v2.FAMILY_IDS_V2) * 3, master_seed=20260906)
    errs, logp_sd = [], []
    for s in suite:
        if s.family_id in ("inventory_bound", "capacity_bound", "asymmetric_risk"):
            continue  # censored demand / deliberately narrow price -> not identifiable, by design
        h = v2.realise_history(s, s.seed)
        lp = np.log(np.asarray(h["price"])); lu = np.log(np.asarray(h["units"]))
        ls = np.log(np.asarray(h["marketing_spend"]))
        X = np.column_stack([np.ones_like(lp), lp - lp.mean(), ls - ls.mean()])
        beta, *_ = np.linalg.lstsq(X, lu, rcond=None)
        errs.append(abs(float(beta[1]) - s.params["a_elast"]))
        logp_sd.append(float(lp.std()))
    assert np.median(logp_sd) > 0.04, "historical price must carry real variation"
    assert np.median(errs) < 0.6, "true elasticity must be recoverable from the generated history"


def test_system_A_and_system_B_are_different_functional_forms():
    s = v2.generate_suite(len(v2.FAMILY_IDS_V2), master_seed=1)[0]
    # System B (ground_truth) is additive-linear and deterministic in (scenario, action)
    r1 = gt.evaluate(s, ())
    r2 = gt.evaluate(s, ())
    assert r1.value == r2.value  # deterministic
    # coupling: eps is related to a_elast but NOT equal
    assert s.params["price_elasticity"] != s.params["a_elast"]
    assert abs(s.params["price_elasticity"] - s.params["a_elast"]) < 1.6  # monotone-ish coupling


def test_seeds_are_genuine_replicates():
    s = v2.generate_suite(len(v2.FAMILY_IDS_V2), master_seed=20260906)[0]
    h1 = v2.realise_history(s, 20260906)
    h2 = v2.realise_history(s, 20260907)
    assert h1["units"] != h2["units"] and h1["price"] != h2["price"]


def test_from_dict_round_trips_and_checks_hash():
    for s in v2.generate_suite(len(v2.FAMILY_IDS_V2) * 2, master_seed=20260906):
        back = v2.EvalScenarioV2.from_dict(s.to_dict())
        assert back.content_hash() == s.content_hash()
        assert v2.realise_history(back, 123) == v2.realise_history(s, 123)


def test_family_partition_is_deterministic_disjoint_and_stratified():
    p1 = v2.partition_families(20260906)
    p2 = v2.partition_families(20260906)
    assert p1 == p2
    allf = p1["development"] + p1["validation"] + p1["locked_test"]
    assert sorted(allf) == sorted(v2.FAMILY_IDS_V2)
    assert len(set(allf)) == len(allf)
    for k in ("development", "validation", "locked_test"):
        assert p1[k]
    # locked families come from >= 3 distinct structural super-groups (stratified)
    groups = {v2.F[f].partition_group for f in p1["locked_test"]}
    assert len(groups) >= 3


def test_no_scenario_id_collision_with_v1_or_frozen_study():
    ids = {s.scenario_id for s in v2.generate_suite(132, master_seed=20260906)}
    assert not (ids & {f"S{n:02d}" for n in range(1, 13)})
    assert all(i.startswith("v2_") for i in ids)


def test_objective_is_the_unchanged_v1_system_B():
    assert gt.GROUND_TRUTH_VERSION == "exogenous_objective_v1"
