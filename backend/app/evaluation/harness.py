"""Per-instance evaluation harness.

Runs the FROZEN A/B/C/D conditions READ-ONLY against an upgraded parameterised
scenario, scores every condition's selected action with the EXOGENOUS
``ground_truth`` objective (never the Digital Twin's own metric), records the
DecisionGPT-internal ``goal_achievement`` as a labelled SECONDARY metric, and
collects agent diagnostics + mechanism factors.

Compliance:
  * Production services are imported LAZILY inside functions and called only
    through public entry points. ``decision_service.analyze_goal`` is called with
    NO ``PipelineOptions`` (i.e. the R0/D0 defaults) for condition D.
  * The identical-feasible-action-space invariant (task requirement 4) is
    explicitly verified per instance; a violation is recorded and the instance is
    flagged for exclusion from the primary paired analysis (a pre-registered
    exclusion rule), never silently.
  * No production code is modified. No frozen experiment is touched. Importing
    this module runs nothing.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from statistics import pstdev
from typing import Any

from sqlalchemy.orm import Session

from app.evaluation import ground_truth as gt
from app.evaluation import mechanism

HARNESS_VERSION = "eval_harness_v1"
CONDITIONS = ("A", "B", "C", "D")

# objective kpi -> the SimulationOutput attribute B/C rank on, and the Goal kpi
_KPI_TO_SIM_ATTR = {"revenue": "expected_revenue", "profit": "expected_profit",
                    "orders": "expected_units_sold"}
_GOAL_KPI = {"revenue": "revenue", "profit": "profit", "orders": "orders",
             "holding_cost": "inventory_risk"}


# --------------------------------------------------------------------------- #
# result records                                                             #
# --------------------------------------------------------------------------- #
@dataclass
class ConditionResult:
    condition: str
    status: str                              # "ok" | "insufficient_data" | "error" | "pick_outside_feasible_set"
    selected_action: list | None             # list[dict] or None (A recommends nothing)
    selected_action_key: str | None
    primary_value: float | None              # EXOGENOUS objective value of the selected action
    primary_normalized: float | None
    primary_regret: float | None
    secondary_goal_achievement: float | None  # DecisionGPT internal metric (SECONDARY, labelled)
    dt_projection: dict | None
    latency_seconds: float
    note: str = ""


@dataclass
class AgentDiagnostics:
    assessable: bool
    per_action_scores: dict = field(default_factory=dict)     # action_key -> {"BA","FA","RM","single","dt_risk_score"}
    score_variance: dict = field(default_factory=dict)        # {"BA","FA","RM"} variance across actions
    score_range: dict = field(default_factory=dict)
    inter_agent_agreement_mean: float | None = None           # 1 - normalised pstdev of {BA,FA,RM}, averaged over actions
    agent_changed_selection_vs_C: bool | None = None
    agent_changed_selection_vs_greedy: bool | None = None
    contribution_note: str = ""


@dataclass
class InstanceResult:
    scenario_id: str
    family_id: str
    partition: str
    seed: int
    perturbation: str | None
    perturbation_severity: float
    action_space_invariant_ok: bool
    action_space_detail: dict
    action_space_hash: str
    exclude_from_primary: bool
    exclude_reason: str | None
    conditions: dict                        # "A".."D" -> ConditionResult (asdict)
    baselines: dict                         # naive/greedy/oracle/classical (from ground_truth)
    agent_diagnostics: dict
    factors: dict
    harness_version: str = HARNESS_VERSION


# --------------------------------------------------------------------------- #
# ephemeral synthetic business (analogue of decision_architecture_service._seed_synthetic_business) #
# --------------------------------------------------------------------------- #
def _seed_eval_business(db: Session, scenario: Any, history: dict) -> tuple[str, str]:
    from app.models.business import Business
    from app.models.goal import Goal
    from app.models.inventory import InventoryRecord
    from app.models.marketing import MarketingCampaign
    from app.models.product import Product
    from app.models.sale import Sale

    p = dict(scenario.params)
    hist = history
    offs = hist.get("day_offsets") or list(range(hist.get("days", 0)))
    price = hist["price"]
    units = hist["units"]
    mkt = hist["marketing_spend"]
    stock = hist.get("stock")

    biz = Business(
        name=f"UpgradedEval {scenario.scenario_id}", industry="SyntheticEval",
        business_type="Synthetic", business_size="N/A", country="IN", currency="INR",
        description="Ephemeral business for the upgraded controlled evaluation (auto-deleted).",
    )
    db.add(biz)
    db.flush()

    product = Product(business_id=biz.id, external_product_id="E000", name="Eval Product",
                      unit_cost=float(p["unit_cost"]), selling_price=float(p["base_price"]))
    db.add(product)
    db.flush()

    span = max(offs) + 1 if offs else 0
    start = date.today() - timedelta(days=span + 1)
    for k, d in enumerate(offs):
        sale_date = start + timedelta(days=int(d))
        q = max(1.0, float(units[k]))
        pr = max(0.01, float(price[k]))
        db.add(Sale(business_id=biz.id, product_id=product.id, sale_date=sale_date,
                    quantity=q, unit_price=pr, discount=0, revenue=pr * q))
        db.add(MarketingCampaign(business_id=biz.id, campaign_date=sale_date, channel="Eval",
                                 spend=float(mkt[k]), impressions=5000, clicks=200, conversions=15,
                                 attributed_revenue=float(mkt[k]) * 3.0))
        if stock is not None:
            db.add(InventoryRecord(business_id=biz.id, product_id=product.id, date=sale_date,
                                   stock_level=max(0.0, float(stock[k])), reorder_level=float(p["base_demand"]) * 0.3))

    objective = scenario.provenance.get("goal_objective", "increase_revenue")
    goal = Goal(business_id=biz.id, objective=objective,
                target_value=float(p.get("target_percent", 12.0)), target_unit="percent",
                primary_kpi=_GOAL_KPI.get(scenario.objective["kpi"], "revenue"),
                time_horizon=int(p.get("horizon_days", 2)), status="active")
    db.add(goal)
    db.commit()
    return biz.id, goal.id


def _cleanup(db: Session, business_id: str) -> None:
    from app.services.decision_architecture_service import _cleanup_synthetic_business
    _cleanup_synthetic_business(db, business_id)


# --------------------------------------------------------------------------- #
# action-space helpers                                                       #
# --------------------------------------------------------------------------- #
def _sig(action: tuple | list) -> frozenset:
    return frozenset((a["type"], round(float(a["value"]), 6)) for a in action)


def _to_sim_actions(action: tuple | list):
    from app.analytics.digital_twin_service import Action
    return [Action(type=a["type"], value=float(a["value"])) for a in action]


def resolve_production_actions(db: Session, business_id: str, goal) -> list[tuple]:
    from app.services.strategy_generation_service import generate_candidates
    gen = generate_candidates(db, business_id, goal)
    return [tuple({"type": a["type"], "value": float(a["value"])} for a in c.actions)
            for c in gen.candidates]


def verify_identical_action_space(scenario: Any, resolved: list[tuple]) -> tuple[bool, dict]:
    declared = {_sig(a) for a in scenario.feasible_actions}
    got = {_sig(a) for a in resolved}
    ok = declared == got
    return ok, {
        "declared_count": len(declared), "resolved_count": len(got),
        "only_declared": [sorted(list(s)) for s in (declared - got)],
        "only_resolved": [sorted(list(s)) for s in (got - declared)],
        "identical": ok,
    }


# --------------------------------------------------------------------------- #
# condition selection (frozen primitives, read-only)                         #
# --------------------------------------------------------------------------- #
def _sim_all(db: Session, business_id: str, feasible: list[tuple], scenario: Any) -> dict:
    """Run the frozen Digital Twin once per feasible action. Returns
    action_key -> SimulationResult (or {"error": ...})."""
    from app.analytics import digital_twin_service as dts
    horizon = int(dict(scenario.params).get("horizon_days", 14))
    out: dict[str, Any] = {}
    for a in feasible:
        key = gt.action_key(a)
        try:
            out[key] = dts.simulate_strategy(db, business_id, _to_sim_actions(a), horizon_days=horizon)
        except Exception as exc:   # InsufficientDataError / ValidationFailedError
            out[key] = {"error": type(exc).__name__, "message": str(exc)}
    return out


def _pick_argmax(sims: dict, feasible: list[tuple], score_fn) -> tuple | None:
    best_a, best_s = None, None
    for a in feasible:
        s = sims.get(gt.action_key(a))
        if isinstance(s, dict):     # error entry
            continue
        val = score_fn(s.output)
        if val is None:
            continue
        if best_s is None or val > best_s:
            best_s, best_a = val, a
    return best_a


def _agent_scores(db: Session, goal_id: str, sims: dict, feasible: list[tuple]) -> dict:
    from app.agents import business_analyst, financial_advisor, risk_manager, single_agent
    from app.models.goal import Goal
    goal = db.get(Goal, goal_id)
    rows: dict[str, dict] = {}
    for a in feasible:
        s = sims.get(gt.action_key(a))
        if isinstance(s, dict):
            continue
        o = s.output
        rows[gt.action_key(a)] = {
            "BA": float(business_analyst.evaluate(o, goal).score),
            "FA": float(financial_advisor.evaluate(o, goal).score),
            "RM": float(risk_manager.evaluate(o, goal).score),
            "single": float(single_agent.evaluate(o).score),
            "dt_risk_score": float(o.risk_score),
        }
    return rows


def _agent_diagnostics(scores: dict, d_key: str | None, c_key: str | None,
                       greedy_key: str | None) -> AgentDiagnostics:
    if not scores:
        return AgentDiagnostics(assessable=False, contribution_note="no successful simulations to score")
    def col(name):
        return [v[name] for v in scores.values()]
    variance = {n: round(float(pstdev(col(n))) ** 2, 8) if len(scores) > 1 else 0.0
                for n in ("BA", "FA", "RM")}
    rng = {n: round(max(col(n)) - min(col(n)), 6) for n in ("BA", "FA", "RM")}
    per_action_agree = []
    for v in scores.values():
        trio = [v["BA"], v["FA"], v["RM"]]
        per_action_agree.append(1.0 - min(1.0, 2.0 * pstdev(trio)) if len(trio) > 1 else 1.0)
    agreement = round(float(sum(per_action_agree) / len(per_action_agree)), 6)
    return AgentDiagnostics(
        assessable=True, per_action_scores=scores, score_variance=variance, score_range=rng,
        inter_agent_agreement_mean=agreement,
        agent_changed_selection_vs_C=(None if (d_key is None or c_key is None) else d_key != c_key),
        agent_changed_selection_vs_greedy=(None if (d_key is None or greedy_key is None) else d_key != greedy_key),
        contribution_note=(
            "agent scores vary meaningfully across actions"
            if max(rng.values()) > 0.05 else
            "agent scores are near-constant across actions on this instance"
        ),
    )


def _dt_secondary_goal_achievement(sim_result, scenario: Any) -> float | None:
    """DecisionGPT-internal metric, SECONDARY. Reproduces
    ``decision_architecture_service._goal_achievement`` semantics WITHOUT importing
    it, so this stays an evaluation-side quantity. Never the primary."""
    if sim_result is None or isinstance(sim_result, dict):
        return None
    o = sim_result.output
    kpi = scenario.objective["kpi"]
    target = float(dict(scenario.params).get("target_percent", 12.0))
    if kpi == "profit" and o.expected_profit is not None and o.baseline_profit not in (None, 0):
        exp, base = o.expected_profit, o.baseline_profit
    elif kpi == "orders":
        exp, base = o.expected_units_sold, o.baseline_units_sold
    else:
        exp, base = o.expected_revenue, o.baseline_revenue
    if not base or base <= 1e-9:
        return 0.0
    pct = (exp - base) / base * 100.0
    return round(min(1.0, max(0.0, pct / target)), 6)


# --------------------------------------------------------------------------- #
# top-level runner                                                           #
# --------------------------------------------------------------------------- #
def run_instance(db: Session, scenario: Any, *, seed: int, perturbation: str | None = None,
                 severity: float = 0.0, perturb_seed: int | None = None,
                 run_D: bool = True, realise_history=None) -> InstanceResult:
    from app.services import decision_service
    from app.evaluation import scenario_families as sf

    # 1. realise the per-seed history (genuine replicate), then optionally perturb
    #    the OBSERVED history the system ingests. Ground-truth params/constraints
    #    (used by every ``gt.*`` call below) are NEVER perturbed.
    #    ``realise_history`` is an OPTIONAL injection point: a different evaluation
    #    *version* (e.g. upgraded_controlled_v2) can supply its own action-
    #    responsive history generator. When omitted the behaviour is byte-identical
    #    to upgraded_controlled_v1 (``scenario_families.realise_history``).
    history = (realise_history or sf.realise_history)(scenario, seed)
    perturb_meta = None
    if perturbation:
        from app.evaluation import perturbations as pz
        ps = perturb_seed if perturb_seed is not None else (
            int(hashlib.sha256(f"{scenario.scenario_id}:{seed}:{perturbation}:{severity}".encode())
                .hexdigest(), 16) % (2 ** 31))
        history, _c2, perturb_meta = pz.apply(perturbation, history, dict(scenario.constraints),
                                              float(severity), ps)

    business_id, goal_id = _seed_eval_business(db, scenario, history)
    try:
        from app.models.goal import Goal
        goal = db.get(Goal, goal_id)

        # 2. identical-feasible-action-space invariant
        resolved = resolve_production_actions(db, business_id, goal)
        inv_ok, inv_detail = verify_identical_action_space(scenario, resolved)
        feasible = list(scenario.feasible_actions)            # the decision set (A/B/C constrained to this)
        eval_ref = list(scenario.eval_reference_actions)      # + no-op, for oracle worst / naive

        # 3. exogenous baselines (never call DecisionGPT)
        oracle_res = gt.oracle(scenario, eval_ref)
        baselines = {
            "oracle": oracle_res,
            "naive": gt.naive_baseline(scenario, eval_ref),
            "greedy": gt.greedy_baseline(scenario, feasible),
            "classical_optimizer": gt.classical_optimizer(scenario, feasible),
        }

        # 4. run frozen A/B/C/D over the identical feasible set
        sims = _sim_all(db, business_id, feasible, scenario)
        cond: dict[str, ConditionResult] = {}
        # The frozen pipeline needs >= forecast_service.MIN_HISTORY_DAYS of history.
        # When the Digital Twin cannot evaluate ANY feasible action (e.g. a
        # ``low_data`` instance below that threshold), B/C have not genuinely run;
        # they are marked ``insufficient_data`` so the pre-registered exclusion
        # rule (UPGRADED_EVALUATION_PREREGISTRATION.md §10.2) drops the instance
        # from the primary paired analysis. Not tuned, not silently dropped.
        sims_all_failed = bool(sims) and all(isinstance(v, dict) for v in sims.values())
        bc_status = "insufficient_data" if sims_all_failed else "ok"

        # A — prediction only: no strategy mechanism -> recommends nothing (scored as no-op)
        t0 = time.perf_counter()
        a_score = gt.score_selection(scenario, None, feasible, oracle_res)
        cond["A"] = ConditionResult(
            "A", "ok", None, a_score.get("selected_action_key"),
            a_score.get("primary_value"), a_score.get("normalized_performance"), a_score.get("regret"),
            None, None, round(time.perf_counter() - t0, 4),
            note="prediction-only: no action recommended; scored as status quo",
        )

        sim_attr = _KPI_TO_SIM_ATTR[scenario.objective["kpi"]]
        # B — Prediction + Decision Simulation (greedy on the twin's projected KPI)
        t0 = time.perf_counter()
        b_pick = _pick_argmax(sims, feasible, lambda o: getattr(o, sim_attr, None))
        cond["B"] = _score_condition("B", b_pick, scenario, feasible, oracle_res, sims, bc_status)
        cond["B"].latency_seconds = round(time.perf_counter() - t0, 4)
        if sims_all_failed:
            cond["B"].note = "Digital Twin returned no usable simulation for any feasible action"

        # C — + single agent
        from app.agents import single_agent
        t0 = time.perf_counter()
        c_pick = _pick_argmax(sims, feasible, lambda o: single_agent.evaluate(o).score)
        cond["C"] = _score_condition("C", c_pick, scenario, feasible, oracle_res, sims, bc_status)
        cond["C"].latency_seconds = round(time.perf_counter() - t0, 4)
        if sims_all_failed:
            cond["C"].note = "Digital Twin returned no usable simulation for any feasible action"

        # D — full production pipeline, DEFAULT PipelineOptions (R0/D0)
        d_pick = None
        if run_D:
            t0 = time.perf_counter()
            try:
                dres = decision_service.analyze_goal(db, business_id, goal_id)
                d_pick, in_set = _map_selection_to_action(dres.selected_strategy_name, feasible)
                status = "ok" if in_set else "pick_outside_feasible_set"
                cr = _score_condition("D", d_pick, scenario, feasible, oracle_res, sims, status)
                cr.secondary_goal_achievement = _extract_secondary_from_pipeline(dres, scenario)
                cr.latency_seconds = round(time.perf_counter() - t0, 4)
                cr.note = ("" if in_set else
                           f"D selected {dres.selected_strategy_name!r} not in the controlled feasible set")
                cond["D"] = cr
            except Exception as exc:
                nm = type(exc).__name__
                d_status = ("insufficient_data"
                            if ("insufficientdata" in nm.lower() or "insufficient" in str(exc).lower())
                            else "error")
                cond["D"] = ConditionResult("D", d_status, None, None, None, None, None, None, None,
                                            round(time.perf_counter() - t0, 4), note=f"{nm}: {exc}")
        else:
            cond["D"] = ConditionResult("D", "skipped", None, None, None, None, None, None, None, 0.0,
                                        note="run_D=False")

        # 5. agent diagnostics
        agent_scores = _agent_scores(db, goal_id, sims, feasible)
        diag = _agent_diagnostics(
            agent_scores,
            d_key=(gt.action_key(d_pick) if d_pick is not None else None),
            c_key=(gt.action_key(c_pick) if c_pick is not None else None),
            greedy_key=baselines["greedy"].get("action_key"),
        )

        # 6. mechanism factors (pre-run + merged post-run)
        pre = mechanism.extract_factors(scenario)
        pred_err, real_risk, agent_dis = _post_run_factor_inputs(
            scenario, sims, agent_scores, oracle_res
        )
        factors = mechanism.merge_run_factors(pre, prediction_error=pred_err,
                                              agent_disagreement=agent_dis, real_risk_score=real_risk)
        if perturb_meta is not None:
            factors = {**factors, "perturbation_meta": perturb_meta}

        exclude, reason = _exclusion(inv_ok, cond)
        return InstanceResult(
            scenario_id=scenario.scenario_id, family_id=scenario.family_id, partition=scenario.partition,
            seed=int(seed), perturbation=perturbation, perturbation_severity=float(severity),
            action_space_invariant_ok=inv_ok, action_space_detail=inv_detail,
            action_space_hash=_space_hash(feasible),
            exclude_from_primary=exclude, exclude_reason=reason,
            conditions={k: asdict(v) for k, v in cond.items()},
            baselines=_baselines_to_jsonable(baselines),
            agent_diagnostics=asdict(diag),
            factors=factors,
        )
    finally:
        _cleanup(db, business_id)


# --------------------------------------------------------------------------- #
# small helpers                                                              #
# --------------------------------------------------------------------------- #
def _score_condition(name: str, pick: tuple | None, scenario: Any, feasible: list[tuple],
                     oracle_res: dict, sims: dict, status: str) -> ConditionResult:
    sc = gt.score_selection(scenario, pick, feasible, oracle_res)
    sim = sims.get(gt.action_key(pick)) if pick is not None else None
    dt_proj = None
    if sim is not None and not isinstance(sim, dict):
        o = sim.output
        dt_proj = {"expected_revenue": o.expected_revenue, "expected_profit": o.expected_profit,
                   "expected_units_sold": o.expected_units_sold, "risk_score": o.risk_score,
                   "risk_level": o.risk_level}
    return ConditionResult(
        condition=name,
        status=status if sc.get("status") == "ok" else sc.get("status", status),
        selected_action=[dict(a) for a in pick] if pick is not None else None,
        selected_action_key=sc.get("selected_action_key"),
        primary_value=sc.get("primary_value"),
        primary_normalized=sc.get("normalized_performance"),
        primary_regret=sc.get("regret"),
        secondary_goal_achievement=_dt_secondary_goal_achievement(sim, scenario),
        dt_projection=dt_proj,
        latency_seconds=0.0,
    )


def _map_selection_to_action(name: str, feasible: list[tuple]) -> tuple[tuple | None, bool]:
    from app.services.decision_service import strategy_name_for_actions
    for a in feasible:
        if strategy_name_for_actions([dict(x) for x in a]) == name:
            return a, True
    parsed = _parse_strategy_name(name)
    return (parsed, False) if parsed is not None else (None, False)


def _parse_strategy_name(name: str) -> tuple | None:
    label_to_type = {"Marketing": "marketing_change", "Price": "price_change", "Inventory": "inventory_change"}
    try:
        parts = [s.strip() for s in name.split("&")]
        acts = []
        for part in parts:
            label, rest = part.rsplit(" ", 1)
            acts.append({"type": label_to_type[label.strip()], "value": float(rest.replace("%", ""))})
        return tuple(acts)
    except Exception:
        return None


def _extract_secondary_from_pipeline(dres, scenario: Any) -> float | None:
    """DecisionGPT-internal goal achievement for D, from the pipeline's own
    expected_outcome. SECONDARY metric, labelled. Never primary."""
    out = getattr(dres, "expected_outcome", None) or {}
    kpi = scenario.objective["kpi"]
    target = float(dict(scenario.params).get("target_percent", 12.0))
    if kpi == "profit":
        exp, base = out.get("expected_profit"), out.get("baseline_profit")
    elif kpi == "orders":
        exp, base = out.get("expected_units_sold"), out.get("baseline_units_sold")
    else:
        exp, base = out.get("expected_revenue"), out.get("baseline_revenue")
    if exp is None or not base:
        return None
    return round(min(1.0, max(0.0, (exp - base) / base * 100.0 / target)), 6)


def _post_run_factor_inputs(scenario, sims, agent_scores, oracle_res):
    pred_err = real_risk = agent_dis = None
    if oracle_res.get("status") == "ok":
        okey = gt.action_key(oracle_res["action"])
        s = sims.get(okey)
        if s is not None and not isinstance(s, dict):
            o = s.output
            real_risk = float(o.risk_score)
            kpi = scenario.objective["kpi"]
            dt_kpi = {"revenue": o.expected_revenue, "profit": o.expected_profit,
                      "orders": o.expected_units_sold}.get(kpi)
            gt_raw = gt.evaluate(scenario, oracle_res["action"]).raw_value
            if dt_kpi is not None and gt_raw is not None:
                pred_err = abs(dt_kpi - gt_raw) / max(1.0, abs(gt_raw))
        row = agent_scores.get(okey)
        if row:
            agent_dis = float(pstdev([row["BA"], row["FA"], row["RM"]]))
    return pred_err, real_risk, agent_dis


def _exclusion(inv_ok: bool, cond: dict) -> tuple[bool, str | None]:
    if not inv_ok:
        return True, "identical_action_space_invariant_failed"
    bad = [k for k, v in cond.items() if k in ("A", "B", "C") and v.status not in ("ok",)]
    if bad:
        statuses = {cond[k].status for k in bad}
        if statuses == {"insufficient_data"}:
            return True, "insufficient_data"
        return True, f"condition(s) {bad} did not complete ({sorted(statuses)})"
    return False, None


def _space_hash(feasible: list[tuple]) -> str:
    import hashlib
    payload = sorted(sorted((a["type"], round(float(a["value"]), 6)) for a in act) for act in feasible)
    return hashlib.sha256(repr(payload).encode()).hexdigest()[:16]


def _baselines_to_jsonable(b: dict) -> dict:
    def conv(x):
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, tuple):
            return [dict(a) if isinstance(a, dict) else a for a in x]
        return x
    return conv(b)
