"""R1 per-instance harness.

Reuses the V1/V2 harness (``app.evaluation.harness.run_instance``) verbatim — the
identical-action-space invariant, the A/B/C/D wiring, the exogenous scoring, the
agent diagnostics, the mechanism factors — and adds exactly two things:

  1. the R1 history generator (``r1.scenario_families.realise_history``) via the
     harness's optional ``realise_history=`` injection point;
  2. the ``r1_dt`` correction, installed for the duration of the instance by
     ``r1_dt.r1_dt_active(scenario)`` (a context manager that patches
     ``digital_twin_service.simulate_strategy`` and restores it afterwards).

Because conditions B and C call ``digital_twin_service.simulate_strategy``
directly and condition D reaches it through
``decision_architecture_service._simulate_all_candidates``, this single patch
routes the entire A/B/C/D pipeline through ``r1_dt`` while leaving every
production module byte-identical on disk and outside the ``with`` block.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

HARNESS_VERSION = "r1_harness_v1"


def run_instance(db: Session, scenario: Any, *, seed: int, perturbation: str | None = None,
                 severity: float = 0.0, perturb_seed: int | None = None, run_D: bool = True):
    from app.evaluation import harness as base_h
    from app.evaluation.r1 import scenario_families as r1sf
    from app.evaluation.r1.r1_dt import r1_dt_active

    with r1_dt_active(scenario) as patched:
        res = base_h.run_instance(
            db, scenario, seed=seed, perturbation=perturbation, severity=severity,
            perturb_seed=perturb_seed, run_D=run_D, realise_history=r1sf.realise_history,
        )
    # record the r1_dt elasticity estimate(s) used for this instance
    est = {}
    try:
        est = {k: dict(v) for k, v in dict(getattr(patched, "_r1_estimates", {})).items()}
    except Exception:
        est = {}
    res.factors = {**(res.factors or {}), "r1_dt_estimates": est,
                   "r1_dt_method": (next(iter(est.values()), {}) or {}).get("method")}
    return res
