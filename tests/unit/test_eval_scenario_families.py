"""Unit tests for backend/app/evaluation/scenario_families.py (Phase 2).

Pure module — no DB, no pipeline, no upgraded experiment executed.
"""

import pytest

from app.evaluation import scenario_families as sf

_VOCAB = {"price_change", "marketing_change", "inventory_change"}
_REQUIRED_KEYS = {
    "scenario_id", "family_id", "seed", "master_seed", "partition", "params",
    "history_spec", "reference_history",
    "constraints", "objective", "feasible_actions", "eval_reference_actions",
    "uncertainty", "noise", "perturbation_config", "provenance", "content_hash",
}


def test_at_least_15_families_declared():
    assert len(sf.FAMILY_IDS) >= 15
    assert len(set(sf.FAMILY_IDS)) == len(sf.FAMILY_IDS)


def test_generate_suite_deterministic_and_balanced():
    a = sf.generate_suite(51, master_seed=20260906)
    b = sf.generate_suite(51, master_seed=20260906)
    assert [s.scenario_id for s in a] == [s.scenario_id for s in b]
    assert sf.suite_checksum(a) == sf.suite_checksum(b)
    assert len(a) == 51
    # a different master seed changes content
    c = sf.generate_suite(51, master_seed=99)
    assert sf.suite_checksum(c) != sf.suite_checksum(a)
    # balanced round-robin: family counts differ by at most 1
    counts = {}
    for s in a:
        counts[s.family_id] = counts.get(s.family_id, 0) + 1
    assert max(counts.values()) - min(counts.values()) <= 1


def test_generate_suite_scales_to_100_plus():
    big = sf.generate_suite(120, master_seed=7)
    assert len(big) == 120
    assert len({s.scenario_id for s in big}) == 120
    assert sf.MAX_SUPPORTED_INSTANCES >= 100


def test_generate_suite_rejects_too_small_or_too_large():
    with pytest.raises(ValueError):
        sf.generate_suite(3, master_seed=1)
    with pytest.raises(ValueError):
        sf.generate_suite(sf.MAX_SUPPORTED_INSTANCES + 1, master_seed=1)


def test_every_scenario_is_complete_and_uses_only_production_action_vocabulary():
    for s in sf.generate_suite(60, master_seed=20260906):
        d = s.to_dict()
        assert _REQUIRED_KEYS.issubset(d), f"{s.scenario_id} missing keys {_REQUIRED_KEYS - set(d)}"
        assert s.feasible_actions, f"{s.scenario_id} has no feasible actions"
        assert s.eval_reference_actions[-1] == sf.NOOP  # explicit no-op present for oracle worst / naive
        for act in s.feasible_actions:
            assert 1 <= len(act) <= 3
            for a in act:
                assert a["type"] in _VOCAB
                assert isinstance(a["value"], float)
        assert s.objective["kpi"] in {"revenue", "profit", "orders", "holding_cost"}
        assert s.objective["sense"] in {"max", "min"}
        assert s.reference_history["price"] and s.reference_history["units"] and s.reference_history["marketing_spend"]
        rh2 = sf.realise_history(s, s.seed + 1)
        assert rh2["units"] != s.reference_history["units"]   # seeds are genuine replicates, not re-runs
        assert set(s.params) >= {"base_price", "unit_cost", "base_demand", "price_elasticity",
                                 "marketing_response", "marketing_base_spend"}


def test_scenarios_are_not_copies_of_the_frozen_twelve():
    ids = {s.scenario_id for s in sf.generate_suite(51, master_seed=20260906)}
    assert not (ids & {f"S{n:02d}" for n in range(1, 13)})
    # families span genuinely different regimes
    fams = {s.family_id for s in sf.generate_suite(51, master_seed=20260906)}
    assert {"price_uncertainty", "competing_objectives", "adversarial_risk_trap",
            "delayed_effects", "low_data"}.issubset(fams)


def test_content_hash_changes_with_params():
    s = sf.generate_suite(len(sf.FAMILY_IDS), master_seed=1)[0]
    h1 = s.content_hash()
    s.params = {**s.params, "base_price": s.params["base_price"] + 1.0}
    assert s.content_hash() != h1


# ---- family-level partition invariants ---------------------------------------
def test_partition_is_deterministic_disjoint_and_covers_every_family():
    p1 = sf.partition_families(master_seed=20260906)
    p2 = sf.partition_families(master_seed=20260906)
    assert p1 == p2
    allf = p1["development"] + p1["validation"] + p1["locked_test"]
    assert sorted(allf) == sorted(sf.FAMILY_IDS)          # covers every family exactly once
    assert len(set(allf)) == len(allf)                     # no overlap
    for name in ("development", "validation", "locked_test"):
        assert p1[name], f"{name} partition is empty"


def test_no_family_crosses_partitions_after_assignment():
    scenarios = sf.generate_suite(60, master_seed=20260906)
    parts = sf.partition_families(master_seed=20260906)
    sf.assign_partitions(scenarios, parts)
    fam_to_part = {}
    for s in scenarios:
        assert s.partition in ("development", "validation", "locked_test")
        fam_to_part.setdefault(s.family_id, s.partition)
        assert fam_to_part[s.family_id] == s.partition, f"family {s.family_id} split across partitions"


def test_partition_rejects_bad_fractions():
    with pytest.raises(ValueError):
        sf.partition_families(master_seed=1, dev=0.5, val=0.3, test=0.3)


def test_from_dict_round_trips_and_checks_content_hash():
    suite = sf.generate_suite(len(sf.FAMILY_IDS) * 2, master_seed=20260906)
    for s in suite:
        d = s.to_dict()
        back = sf.EvalScenario.from_dict(d)
        assert back.scenario_id == s.scenario_id
        assert back.content_hash() == s.content_hash() == d["content_hash"]
        assert back.partition == s.partition
        # realised histories match for the same seed after a round trip
        assert sf.realise_history(back, 123) == sf.realise_history(s, 123)
    # a tampered param is caught
    bad = suite[0].to_dict()
    bad["params"] = {**bad["params"], "base_price": bad["params"]["base_price"] + 1}
    with pytest.raises(ValueError):
        sf.EvalScenario.from_dict(bad)


def test_profit_families_declare_the_roi_positive_candidate_set():
    suite = sf.generate_suite(len(sf.FAMILY_IDS), master_seed=20260906)
    for s in suite:
        if s.provenance["goal_objective"] == "increase_profit":
            # 5 base + the extra "marketing +10%" candidate = 6
            assert len(s.feasible_actions) == 6
            assert s.provenance["marketing_roi_positive"] is True
            assert any(a == ({"type": "marketing_change", "value": 10.0},) for a in s.feasible_actions)


def test_production_candidate_actions_match_known_objectives():
    rev = sf.production_candidate_actions("increase_revenue")
    assert len(rev) == 8
    prof = sf.production_candidate_actions("increase_profit")
    assert len(prof) == 5
    prof_roi = sf.production_candidate_actions("increase_profit", marketing_roi_positive=True)
    assert len(prof_roi) == 6
    inv = sf.production_candidate_actions("reduce_inventory_risk", has_inventory=True)
    assert len(inv) == 5
    assert sf.production_candidate_actions("reduce_inventory_risk", has_inventory=False) == []
