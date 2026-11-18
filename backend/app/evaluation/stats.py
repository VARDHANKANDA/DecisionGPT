"""Statistical primitives for the upgraded controlled evaluation.

PURE: imports only stdlib + numpy + scipy. No production dependency.

Design decisions (fixed here, to be echoed in the pre-registration):

  * The **experimental unit is the scenario**, not the (scenario, seed)
    observation. ``scenario_level_aggregate`` collapses seeds within a scenario
    first; the primary paired tests then operate on one value per scenario.
  * The **primary effect size is the matched-pairs rank-biserial correlation**
    (Kerby's simple-difference formula, ``(wins - losses) / n_nonzero``), an
    estimator computed from the data. This module deliberately does NOT expose a
    p-derived ``|Z| / sqrt(N)`` quantity as a primary statistic. The frozen
    historical study's ``multi_scenario_service._paired`` still reports its
    ``effect_size_r`` unchanged; that historical value is not touched here.
  * The **primary interval is a paired cluster (scenario) bootstrap** of the mean
    paired difference; a Student-t interval is reported alongside as a secondary,
    clearly-labelled reference.
  * Multiplicity across the pre-registered contrast family is controlled with the
    **Holm-Bonferroni** step-down procedure.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
from scipy import stats as _sps

PRIMARY_EFFECT_SIZE = "matched_pairs_rank_biserial"
PRIMARY_INTERVAL = "paired_scenario_cluster_bootstrap"
MULTIPLICITY_METHOD = "holm_bonferroni"

_TOL = 1e-9


# --------------------------------------------------------------------------- #
# descriptive                                                                #
# --------------------------------------------------------------------------- #
def summary(values: Iterable[float]) -> dict:
    xs = np.asarray([v for v in values if v is not None], dtype=float)
    if xs.size == 0:
        return {"n": 0}
    n = int(xs.size)
    mean = float(xs.mean())
    sd = float(xs.std(ddof=1)) if n > 1 else 0.0
    if n > 1 and sd > 0:
        half = float(_sps.t.ppf(0.975, n - 1) * sd / np.sqrt(n))
        t_ci = [round(mean - half, 6), round(mean + half, 6)]
    else:
        t_ci = None
    return {
        "n": n, "mean": round(mean, 6), "median": round(float(np.median(xs)), 6),
        "sd": round(sd, 6), "min": round(float(xs.min()), 6), "max": round(float(xs.max()), 6),
        "student_t_ci95": t_ci,
    }


# --------------------------------------------------------------------------- #
# paired difference primitives                                               #
# --------------------------------------------------------------------------- #
def paired_diffs(a: Iterable[float], b: Iterable[float]) -> np.ndarray:
    aa = np.asarray(list(a), dtype=float)
    bb = np.asarray(list(b), dtype=float)
    if aa.shape != bb.shape:
        raise ValueError(f"paired_diffs: shape mismatch {aa.shape} vs {bb.shape}")
    return aa - bb


def win_tie_loss(a: Iterable[float], b: Iterable[float], tol: float = _TOL) -> dict:
    d = paired_diffs(a, b)
    wins = int((d > tol).sum())
    losses = int((d < -tol).sum())
    ties = int(d.size - wins - losses)
    return {"n": int(d.size), "a_wins": wins, "ties": ties, "a_losses": losses,
            "n_nonzero": wins + losses}


def rank_biserial(a: Iterable[float], b: Iterable[float], tol: float = _TOL) -> float | None:
    """Matched-pairs rank-biserial correlation (Kerby simple-difference formula):
    ``(n_favourable - n_unfavourable) / n_nonzero`` in [-1, 1], where 'favourable'
    means ``a > b``. Returns ``None`` when there are no non-zero pairs.
    Estimator-based; NOT derived from the p-value."""
    wtl = win_tie_loss(a, b, tol)
    nz = wtl["n_nonzero"]
    if nz == 0:
        return None
    return round((wtl["a_wins"] - wtl["a_losses"]) / nz, 6)


def wilcoxon_signed_rank(a: Iterable[float], b: Iterable[float], tol: float = _TOL) -> dict:
    """Two-sided paired Wilcoxon signed-rank. Uses the exact distribution when
    scipy can (small n, no zeros/ties) and the normal approximation otherwise.
    Returns ``p_value = None`` with a reason when the test is undefined
    (all differences zero, or < 1 non-zero pair)."""
    d = paired_diffs(a, b)
    nz = int((np.abs(d) > tol).sum())
    if nz == 0:
        return {"test": "wilcoxon_signed_rank", "n": int(d.size), "n_nonzero": 0,
                "statistic": None, "p_value": None,
                "reason": "all paired differences are zero — test undefined"}
    if nz < 2:
        return {"test": "wilcoxon_signed_rank", "n": int(d.size), "n_nonzero": nz,
                "statistic": None, "p_value": None,
                "reason": f"only {nz} non-zero paired difference — test undefined"}
    aa = np.asarray(list(a), dtype=float)
    bb = np.asarray(list(b), dtype=float)
    try:
        mode = "exact" if nz <= 25 else "approx"
        res = _sps.wilcoxon(aa, bb, zero_method="wilcox", correction=False,
                            alternative="two-sided", mode=mode)
    except TypeError:  # older scipy without ``mode``
        res = _sps.wilcoxon(aa, bb, zero_method="wilcox", correction=False, alternative="two-sided")
    except ValueError as exc:
        return {"test": "wilcoxon_signed_rank", "n": int(d.size), "n_nonzero": nz,
                "statistic": None, "p_value": None, "reason": str(exc)}
    return {"test": "wilcoxon_signed_rank", "n": int(d.size), "n_nonzero": nz,
            "statistic": round(float(res.statistic), 6), "p_value": float(res.pvalue),
            "mode": mode}


# --------------------------------------------------------------------------- #
# scenario-level aggregation + cluster bootstrap                             #
# --------------------------------------------------------------------------- #
def scenario_level_aggregate(observations: list[dict], *, metric: str,
                             by: str = "scenario_id", agg: str = "mean") -> dict[str, float]:
    """Collapse per-(scenario, seed) observations to one value per scenario.
    ``observations`` is a list of dicts each having ``by`` and ``metric`` keys."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for o in observations:
        v = o.get(metric)
        if v is None:
            continue
        buckets[o[by]].append(float(v))
    fn = {"mean": np.mean, "median": np.median}[agg]
    return {k: float(fn(v)) for k, v in buckets.items() if v}


def cluster_bootstrap_paired(a_by_unit: dict[str, float], b_by_unit: dict[str, float], *,
                             n_boot: int = 10_000, seed: int = 12345,
                             statistic: str = "mean") -> dict:
    """Paired bootstrap that resamples the CLUSTERS (scenarios), not individual
    observations. ``a_by_unit`` / ``b_by_unit`` map unit id -> one aggregated
    value. Returns a 95% percentile interval of the resampled paired statistic
    (mean or median of ``a - b``)."""
    keys = sorted(set(a_by_unit) & set(b_by_unit))
    if len(keys) < 2:
        return {"n_units": len(keys), "point": None, "ci95": None,
                "reason": "need >= 2 shared units"}
    d = np.array([a_by_unit[k] - b_by_unit[k] for k in keys], dtype=float)
    fn = {"mean": np.mean, "median": np.median}[statistic]
    point = float(fn(d))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(n_boot, d.size))
    boot = fn(d[idx], axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"n_units": int(d.size), "statistic": statistic, "point": round(point, 6),
            "ci95": [round(float(lo), 6), round(float(hi), 6)],
            "n_boot": n_boot, "seed": seed}


def paired_scenario_analysis(a_by_scenario: dict[str, float], b_by_scenario: dict[str, float], *,
                             label: str = "A_vs_B", n_boot: int = 10_000,
                             boot_seed: int = 12345) -> dict:
    """The full primary-analysis bundle for one scenario-level paired contrast."""
    keys = sorted(set(a_by_scenario) & set(b_by_scenario))
    a = [a_by_scenario[k] for k in keys]
    b = [b_by_scenario[k] for k in keys]
    d = paired_diffs(a, b)
    wtl = win_tie_loss(a, b)
    return {
        "label": label,
        "n_scenarios": len(keys),
        "mean_difference": round(float(d.mean()), 6) if d.size else None,
        "median_difference": round(float(np.median(d)), 6) if d.size else None,
        "sd_difference": round(float(d.std(ddof=1)), 6) if d.size > 1 else 0.0,
        "wins_ties_losses": [wtl["a_wins"], wtl["ties"], wtl["a_losses"]],
        "n_nonzero": wtl["n_nonzero"],
        "wilcoxon": wilcoxon_signed_rank(a, b),
        "rank_biserial": rank_biserial(a, b),
        "cluster_bootstrap": cluster_bootstrap_paired(a_by_scenario, b_by_scenario,
                                                      n_boot=n_boot, seed=boot_seed),
        "student_t_ci95_of_mean_difference": summary(d).get("student_t_ci95"),
        "primary_effect_size": PRIMARY_EFFECT_SIZE,
        "primary_interval": PRIMARY_INTERVAL,
    }


# --------------------------------------------------------------------------- #
# multiple-comparison correction                                             #
# --------------------------------------------------------------------------- #
def holm_correction(pvalues: dict[str, float], alpha: float = 0.05) -> dict:
    """Holm-Bonferroni step-down. ``pvalues`` maps contrast name -> raw two-sided
    p. Entries with a ``None`` p (undefined test) are passed through with
    ``reject = False`` and excluded from the correction count."""
    testable = {k: v for k, v in pvalues.items() if v is not None}
    passthrough = {k: v for k, v in pvalues.items() if v is None}
    m = len(testable)
    ordered = sorted(testable.items(), key=lambda kv: kv[1])
    out: dict[str, dict] = {}
    running_max = 0.0
    for i, (name, p) in enumerate(ordered):
        adj = min(1.0, (m - i) * p)
        running_max = max(running_max, adj)   # enforce monotonicity
        out[name] = {"p_raw": round(float(p), 8), "p_holm": round(float(running_max), 8),
                     "reject_at_alpha": bool(running_max < alpha), "rank": i + 1}
    for name in passthrough:
        out[name] = {"p_raw": None, "p_holm": None, "reject_at_alpha": False,
                     "rank": None, "note": "test undefined; excluded from correction"}
    return {"alpha": alpha, "method": MULTIPLICITY_METHOD, "n_tests_corrected": m, "results": out}


# --------------------------------------------------------------------------- #
# simulation-based power (used BEFORE locked-test results exist)             #
# --------------------------------------------------------------------------- #
@dataclass
class PowerAssumptions:
    """All values MUST be set before any locked-test result is observed."""
    n_scenarios: int
    n_seeds: int
    min_effect_of_interest: float          # on the primary metric (e.g. normalised regret difference)
    metric_sd_between_scenarios: float     # assumed scenario-level SD of the paired difference
    within_scenario_seed_sd: float         # assumed seed noise SD
    alpha: float = 0.05
    target_power: float = 0.80
    primary_comparison: str = "D_vs_B"
    n_sim: int = 2000
    rng_seed: int = 20260906

    def to_dict(self) -> dict:
        return {**self.__dict__, "note": "assumptions fixed pre-registration; not derived from observed results"}


def simulate_power(assump: PowerAssumptions) -> dict:
    """Monte-Carlo power for a scenario-level paired Wilcoxon at
    ``assump.min_effect_of_interest``. Generates synthetic paired scenario
    differences under the assumed variance components and counts rejections."""
    rng = np.random.default_rng(assump.rng_seed)
    n = assump.n_scenarios
    se_scen = assump.metric_sd_between_scenarios
    se_seed = assump.within_scenario_seed_sd / max(1, np.sqrt(assump.n_seeds))
    sd_eff = float(np.hypot(se_scen, se_seed))
    rejections = 0
    for _ in range(assump.n_sim):
        d = rng.normal(loc=assump.min_effect_of_interest, scale=sd_eff, size=n)
        # scenario-level paired Wilcoxon vs 0
        res = wilcoxon_signed_rank(d, np.zeros_like(d))
        if res["p_value"] is not None and res["p_value"] < assump.alpha:
            rejections += 1
    power = rejections / assump.n_sim
    return {
        "assumptions": assump.to_dict(),
        "assumed_effective_sd": round(sd_eff, 6),
        "estimated_power": round(power, 4),
        "meets_target": bool(power >= assump.target_power),
        "n_sim": assump.n_sim,
    }
