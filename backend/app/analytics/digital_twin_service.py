"""Business Digital Twin — docs/DIGITAL_TWIN_SPECIFICATION.md.

"Try the decision before you make it." Simulates the effect of one or more
controlled actions (price_change / marketing_change / inventory_change) by
running the business's own registered forecasting model twice — once
unmodified (baseline) and once with the action's adjusted price/marketing
inputs (scenario) — and taking the difference. This is the transition
function `S(t+1) = F(S(t), A(t), X(t))` from the spec: F is
forecast_service.run_recursive_forecast, the exact model trained and
evaluated for this business's forecasting task. No effect size (e.g.
"marketing +10% -> revenue +8%") is ever hand-picked; every number here is
either read from the business's own data or produced by a registered model
(see AGENTS.md "no fabrication").

This module does not yet consult the Dynamic Causal Graph (docs/
CAUSAL_GRAPH_SPECIFICATION.md, built in a later phase) — the assumptions
list says so explicitly, because a forecasting model's response to a
feature is a *correlational* pattern until a causal method validates it.
"""
from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy.orm import Session

from app.analytics import forecast_service, kpi_service
from app.analytics.churn_service import check_churn_sufficiency
from app.core.errors import InsufficientDataError, ValidationFailedError
from app.models.digital_twin import DigitalTwinSimulation, DigitalTwinState
from app.models.goal import Goal
from app.models.inventory import InventoryRecord
from app.models.product import Product
from app.models.sale import Sale

SUPPORTED_ACTION_TYPES = {"price_change", "marketing_change", "inventory_change"}
ACTION_VALUE_BOUNDS = {
    "price_change": (-50.0, 100.0),
    "marketing_change": (-100.0, 500.0),
    "inventory_change": (-100.0, 500.0),
}
MAX_ACTIONS_PER_SIMULATION = 3


@dataclass
class Action:
    type: str
    value: float


@dataclass
class SimulationOutput:
    expected_units_sold: float
    baseline_units_sold: float
    expected_revenue: float
    baseline_revenue: float
    expected_profit: float | None
    baseline_profit: float | None
    profit_note: str | None
    customer_impact: int | None
    inventory_constrained: bool
    risk_level: str
    risk_score: float
    revenue_lower_bound: float
    revenue_upper_bound: float
    model_name: str
    model_version: str
    assumptions: list[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    id: str
    business_id: str
    goal_id: str | None
    input_state: dict
    actions: list[dict]
    output: SimulationOutput


def _validate_actions(actions: list[Action]) -> None:
    if not actions:
        raise ValidationFailedError("At least one action is required to run a simulation.")
    if len(actions) > MAX_ACTIONS_PER_SIMULATION:
        raise ValidationFailedError(
            f"At most {MAX_ACTIONS_PER_SIMULATION} actions can be combined in a single simulation."
        )
    seen_types = set()
    for action in actions:
        if action.type not in SUPPORTED_ACTION_TYPES:
            raise ValidationFailedError(
                f"Unsupported action type '{action.type}'.",
                details={"supported_types": sorted(SUPPORTED_ACTION_TYPES)},
            )
        if action.type in seen_types:
            raise ValidationFailedError(f"Duplicate action type '{action.type}' — combine into one action.")
        seen_types.add(action.type)
        low, high = ACTION_VALUE_BOUNDS[action.type]
        if not (low <= action.value <= high):
            raise ValidationFailedError(
                f"'{action.type}' value {action.value} is outside the supported range ({low}% to {high}%)."
            )


def get_current_state(db: Session, business_id: str) -> dict:
    """The Digital Twin's initial state vector (spec §2), built entirely
    from the business's own real analytics — never a placeholder."""
    kpis = kpi_service.compute_kpis(db, business_id)
    inventory = _current_inventory_units(db, business_id)
    churn_available, _ = check_churn_sufficiency(db, business_id)

    return {
        "sales": kpis.orders,
        "revenue": kpis.revenue,
        "customers": kpis.customers,
        "average_order_value": kpis.average_order_value,
        "marketing_spend": kpis.marketing_spend,
        "inventory": inventory,
        "profit": kpis.profit,
        "conversion_rate": kpis.conversion_rate,
        "churn_data_available": churn_available,
    }


def _avg_unit_cost_and_coverage(db: Session, business_id: str) -> tuple[float | None, float]:
    """Historical revenue-weighted average cost per unit, only over sales
    whose product has a known unit_cost — mirrors kpi_service's profit
    honesty rule (partial/no coverage is surfaced, never assumed)."""
    sales = db.query(Sale).filter(Sale.business_id == business_id).all()
    if not sales:
        return None, 0.0
    costs = {
        p.id: float(p.unit_cost)
        for p in db.query(Product).filter(Product.business_id == business_id).all()
        if p.unit_cost is not None
    }
    sales_with_cost = [s for s in sales if s.product_id in costs]
    if not sales_with_cost:
        return None, 0.0
    total_units = sum(s.quantity for s in sales_with_cost)
    total_cost = sum(costs[s.product_id] * s.quantity for s in sales_with_cost)
    coverage = len(sales_with_cost) / len(sales)
    return (total_cost / total_units if total_units else None), coverage


def _avg_orders_per_customer(db: Session, business_id: str) -> float | None:
    total_orders = db.query(Sale).filter(Sale.business_id == business_id).count()
    distinct_customers = (
        db.query(Sale.customer_id)
        .filter(Sale.business_id == business_id, Sale.customer_id.isnot(None))
        .distinct()
        .count()
    )
    if not distinct_customers:
        return None
    return total_orders / distinct_customers


def _current_inventory_units(db: Session, business_id: str) -> float | None:
    latest_stock_by_product: dict[str, int] = {}
    for record in (
        db.query(InventoryRecord)
        .filter(InventoryRecord.business_id == business_id)
        .order_by(InventoryRecord.product_id, InventoryRecord.date)
        .all()
    ):
        latest_stock_by_product[record.product_id] = record.stock_level
    if latest_stock_by_product:
        return float(sum(latest_stock_by_product.values()))
    stock_quantities = [
        p.stock_quantity
        for p in db.query(Product).filter(Product.business_id == business_id).all()
        if p.stock_quantity is not None
    ]
    return float(sum(stock_quantities)) if stock_quantities else None


def _risk_from_extrapolation(history: dict[str, tuple[float, float]], scenario: dict[str, float]) -> tuple[str, float]:
    """Risk is how far the requested scenario pushes a feature outside the
    range the model was actually shown for this business (tree/linear
    models are unreliable outside their training range) — a documented,
    computed heuristic, not an invented confidence score (spec §9).

    `history` maps feature name -> (observed_min, observed_max) from this
    business's own daily series. `risk_score` is the largest fractional
    overshoot beyond that range across features, clipped to [0, 1].
    """
    overshoot = 0.0
    for feature, value in scenario.items():
        lo, hi = history.get(feature, (value, value))
        span = max(hi - lo, 1e-9)
        if value < lo:
            overshoot = max(overshoot, (lo - value) / span)
        elif value > hi:
            overshoot = max(overshoot, (value - hi) / span)
    risk_score = round(min(overshoot, 1.0), 4)
    return _risk_band(risk_score), risk_score


def _risk_band(risk_score: float) -> str:
    if risk_score < 0.15:
        return "LOW"
    if risk_score < 0.5:
        return "MODERATE"
    return "HIGH"


# --- Risk formulation versions (docs/RISK_CALIBRATION_ANALYSIS.md) ---------
# R0 = the production formula above: extrapolation overshoot normalised by the
#      raw observed range (max - min), floored at 1e-9. Degenerates when a
#      feature's history barely varies (denominator -> 0 -> any move reads as
#      risk 1.0). Unchanged; the default everywhere.
RISK_FORMULA_VERSION = "extrapolation_range_v1"

# R1 = same overshoot logic, but the normaliser is a *robust historical scale*
#      that cannot collapse to zero for a low-variance series:
#          scale = max( hi - lo,
#                       1.4826 * MAD(series),        # robust sigma estimate
#                       REL_FLOOR * |median(series)| ) # scale-aware floor
#      REL_FLOOR is pre-specified (not tuned): a price/marketing move of this
#      fraction off the historical median is the unit of extrapolation distance
#      when the history is otherwise flat. 0.15 == a "materially large" business
#      move. This never *reduces* the normaliser below the observed range, so a
#      genuinely wide history is unaffected; it only lifts the denominator when
#      the raw range is degenerate.
RISK_FORMULA_VERSION_ROBUST = "extrapolation_robust_v1"
ROBUST_SCALE_REL_FLOOR = 0.15
_MAD_TO_SIGMA = 1.4826


def _robust_feature_scale(series: "pd.Series") -> dict[str, float]:
    """lo / hi / mad-sigma / relative-floor for one history series."""
    vals = [float(x) for x in series if x is not None]
    if not vals:
        return {"lo": 0.0, "hi": 0.0, "mad_sigma": 0.0, "rel_floor": 0.0, "median": 0.0}
    s = sorted(vals)
    n = len(s)
    med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
    devs = sorted(abs(v - med) for v in vals)
    mad = devs[n // 2] if n % 2 else (devs[n // 2 - 1] + devs[n // 2]) / 2
    return {
        "lo": min(vals), "hi": max(vals),
        "mad_sigma": _MAD_TO_SIGMA * mad,
        "rel_floor": ROBUST_SCALE_REL_FLOOR * abs(med),
        "median": med,
    }


def _feature_history_stats(history: "pd.DataFrame") -> dict[str, dict[str, float]]:
    return {
        "price": _robust_feature_scale(history["price"]),
        "marketing_spend": _robust_feature_scale(history["marketing_spend"]),
    }


def _calibrated_risk_from_extrapolation(
    stats: dict[str, dict[str, float]], scenario: dict[str, float], model: str
) -> tuple[str, float]:
    """R1 (`extrapolation_robust_v1`). Identical overshoot / clip / banding to
    R0 — only the per-feature normaliser changes to a robust scale that does
    not collapse for a low-variance history. `model` must be "R1"."""
    if model != "R1":
        raise ValueError(f"Unknown calibrated risk model '{model}'.")
    overshoot = 0.0
    for feature, value in scenario.items():
        st = stats.get(feature)
        if st is None:
            continue
        lo, hi = st["lo"], st["hi"]
        scale = max(hi - lo, st["mad_sigma"], st["rel_floor"], 1e-9)
        if value < lo:
            overshoot = max(overshoot, (lo - value) / scale)
        elif value > hi:
            overshoot = max(overshoot, (value - hi) / scale)
    risk_score = round(min(overshoot, 1.0), 4)
    return _risk_band(risk_score), risk_score


def compute_scenario_inputs(
    history: pd.DataFrame, actions: list[Action]
) -> tuple[float, float, float, float, dict[str, Action]]:
    """Baseline vs scenario (price, marketing_spend), given this business's
    real recent history and a strategy's actions — the exact inputs fed to
    forecast_service.run_recursive_forecast for both runs. Factored out so
    explainability_service can reconstruct the identical feature rows a
    decision's simulation actually used, without duplicating this logic.
    """
    baseline_price = float(history["price"].iloc[-1])
    baseline_marketing_spend = forecast_service.recent_marketing_spend(history)

    by_type = {a.type: a for a in actions}
    price_pct = by_type["price_change"].value if "price_change" in by_type else 0.0
    marketing_pct = by_type["marketing_change"].value if "marketing_change" in by_type else 0.0

    scenario_price = round(baseline_price * (1 + price_pct / 100), 2)
    scenario_marketing_spend = round(max(0.0, baseline_marketing_spend * (1 + marketing_pct / 100)), 2)

    return baseline_price, baseline_marketing_spend, scenario_price, scenario_marketing_spend, by_type


def simulate_strategy(
    db: Session,
    business_id: str,
    actions: list[Action],
    goal_id: str | None = None,
    horizon_days: int = 14,
    strategy_id: str | None = None,
    causal_context=None,
    risk_model: str | None = None,
) -> SimulationResult:
    """`risk_model` is a research-only override for how extrapolation risk is
    scored (docs/RISK_CALIBRATION_ANALYSIS.md). None / "R0" = the production
    formula (`_risk_from_extrapolation`); "R1" = the robust-scale variant.
    It changes ONLY `SimulationOutput.risk_score` / `.risk_level` — the
    predicted units / revenue / profit and every other field are identical."""
    from ml.features.forecasting_features import build_forecasting_features

    _validate_actions(actions)

    if goal_id is not None:
        goal = db.get(Goal, goal_id)
        if goal is None or goal.business_id != business_id:
            raise ValidationFailedError(f"Goal {goal_id} not found for this business.")

    sufficient, reason = forecast_service.check_forecast_sufficiency(db, business_id)
    if not sufficient:
        raise InsufficientDataError(reason or "Not enough sales history to run a simulation.")

    model_row = forecast_service.select_best_model(
        db, forecast_service.FORECAST_MODEL_CANDIDATES, metric="mae", minimize=True
    )
    if model_row is None:
        raise InsufficientDataError(
            "No forecasting model is registered yet. Run `python -m ml.training.train_forecasting` "
            "and sync the registry before running a simulation."
        )
    model = forecast_service.load_model(model_row)
    rmse = float(model_row.metrics_json.get("rmse", 0.0))

    daily = forecast_service.build_daily_series(db, business_id)
    history = daily.copy()
    history["date"] = pd.to_datetime(history["date"])
    featured_history = build_forecasting_features(history)
    if featured_history.empty:
        raise InsufficientDataError("Not enough contiguous sales history to build forecasting features.")

    units_series = list(history["units_sold"])
    last_date = history["date"].iloc[-1]
    baseline_price, baseline_marketing_spend, scenario_price, scenario_marketing_spend, by_type = (
        compute_scenario_inputs(history, actions)
    )
    inventory_pct = by_type["inventory_change"].value if "inventory_change" in by_type else None

    if inventory_pct is not None and _current_inventory_units(db, business_id) is None:
        raise ValidationFailedError(
            "No inventory data on file — upload inventory or product stock data to simulate an inventory change."
        )

    zero_baseline_notes: list[str] = []
    if "marketing_change" in by_type and baseline_marketing_spend == 0:
        zero_baseline_notes.append(
            "Your recorded marketing spend is ₹0, so a percentage change has no effect on this simulation — "
            "upload marketing campaign data with real spend to simulate a marketing change."
        )

    baseline_points = forecast_service.run_recursive_forecast(
        model, units_series, last_date, baseline_price, baseline_marketing_spend, horizon_days, rmse
    )
    scenario_points = forecast_service.run_recursive_forecast(
        model, units_series, last_date, scenario_price, scenario_marketing_spend, horizon_days, rmse
    )

    baseline_units = sum(p.predicted_value for p in baseline_points)
    scenario_units = sum(p.predicted_value for p in scenario_points)
    units_lower = sum(p.lower_bound for p in scenario_points)
    units_upper = sum(p.upper_bound for p in scenario_points)

    assumptions = [
        f"Uses your registered forecasting model ({model_row.model_name} v{model_row.version}), "
        "re-run with the requested price/marketing inputs — the projected effect is that model's own "
        "learned response to those inputs, not a fixed multiplier.",
        "Aggregates across all products using a single business-wide average daily price; it does not "
        "model per-product price elasticity.",
        f"Assumes marketing/price effects observed in your history (last {len(units_series)} days) "
        "continue to hold at the requested scale.",
    ]
    if causal_context is not None and getattr(causal_context, "built", False):
        assumptions.append(
            f"Causal context ({causal_context.method}, graph {causal_context.graph_version}): "
            f"{causal_context.summary} Strongest end-to-end evidence: "
            f"{causal_context.strongest_pathway_evidence.replace('_', ' ')}."
        )
    else:
        assumptions.append(
            "Reflects a correlational pattern learned from your historical data, not a causally "
            "validated effect (no causal graph was available to attach)."
        )
    assumptions = zero_baseline_notes + assumptions

    inventory_constrained = False
    if inventory_pct is not None:
        current_inventory = _current_inventory_units(db, business_id) or 0.0
        available = current_inventory * (1 + inventory_pct / 100)
        if scenario_units > available:
            scenario_units = available
            inventory_constrained = True
            assumptions.append(
                f"Projected demand ({round(sum(p.predicted_value for p in scenario_points), 1)} units) exceeds "
                f"available inventory ({round(available, 1)} units) — sales are capped at what you can fulfil."
            )

    avg_cost, cost_coverage = _avg_unit_cost_and_coverage(db, business_id)
    profit_note = None
    baseline_profit = expected_profit = None
    if avg_cost is not None:
        baseline_profit = round(baseline_units * baseline_price - baseline_units * avg_cost, 2)
        expected_profit = round(scenario_units * scenario_price - scenario_units * avg_cost, 2)
        if cost_coverage < 1.0:
            profit_note = f"Cost coverage: {round(cost_coverage * 100)}% of historical sales had a known unit_cost."
    else:
        profit_note = "Profit is unavailable — no products have a unit_cost on file."

    avg_orders_per_customer = _avg_orders_per_customer(db, business_id)
    customer_impact = None
    if avg_orders_per_customer:
        delta_orders = scenario_units - baseline_units
        customer_impact = round(delta_orders / avg_orders_per_customer)
        assumptions.append(
            "Customer impact is estimated from your historical orders-per-customer ratio "
            f"({round(avg_orders_per_customer, 2)}), not tracked per-customer in the simulation."
        )

    history_ranges = {
        "price": (float(history["price"].min()), float(history["price"].max())),
        "marketing_spend": (float(history["marketing_spend"].min()), float(history["marketing_spend"].max())),
    }
    scenario_features = {"price": scenario_price, "marketing_spend": scenario_marketing_spend}
    if risk_model in (None, "R0"):
        risk_level, risk_score = _risk_from_extrapolation(history_ranges, scenario_features)
    else:
        risk_level, risk_score = _calibrated_risk_from_extrapolation(
            _feature_history_stats(history), scenario_features, risk_model
        )

    output = SimulationOutput(
        expected_units_sold=round(scenario_units, 2),
        baseline_units_sold=round(baseline_units, 2),
        expected_revenue=round(scenario_units * scenario_price, 2),
        baseline_revenue=round(baseline_units * baseline_price, 2),
        expected_profit=expected_profit,
        baseline_profit=baseline_profit,
        profit_note=profit_note,
        customer_impact=customer_impact,
        inventory_constrained=inventory_constrained,
        risk_level=risk_level,
        risk_score=risk_score,
        revenue_lower_bound=round(units_lower * scenario_price, 2),
        revenue_upper_bound=round(units_upper * scenario_price, 2),
        model_name=model_row.model_name,
        model_version=model_row.version,
        assumptions=assumptions,
    )

    input_state = get_current_state(db, business_id)

    state_row = DigitalTwinState(business_id=business_id, goal_id=goal_id, state_json=input_state)
    db.add(state_row)

    simulation_row = DigitalTwinSimulation(
        business_id=business_id,
        goal_id=goal_id,
        strategy_id=strategy_id,
        input_state_json=input_state,
        actions_json=[{"type": a.type, "value": a.value} for a in actions],
        output_state_json=output_to_dict(output),
        risk_score=risk_score,
        model_version=f"{model_row.model_name}:{model_row.version}",
        graph_version=(getattr(causal_context, "graph_version", None) if causal_context is not None else None),
        assumptions_json=assumptions,
    )
    db.add(simulation_row)
    db.commit()
    db.refresh(simulation_row)

    return SimulationResult(
        id=simulation_row.id,
        business_id=business_id,
        goal_id=goal_id,
        input_state=input_state,
        actions=simulation_row.actions_json,
        output=output,
    )


def output_to_dict(output: SimulationOutput) -> dict:
    return {
        "expected_units_sold": output.expected_units_sold,
        "baseline_units_sold": output.baseline_units_sold,
        "expected_revenue": output.expected_revenue,
        "baseline_revenue": output.baseline_revenue,
        "expected_profit": output.expected_profit,
        "baseline_profit": output.baseline_profit,
        "profit_note": output.profit_note,
        "customer_impact": output.customer_impact,
        "inventory_constrained": output.inventory_constrained,
        "risk_level": output.risk_level,
        "risk_score": output.risk_score,
        "revenue_lower_bound": output.revenue_lower_bound,
        "revenue_upper_bound": output.revenue_upper_bound,
        "model_name": output.model_name,
        "model_version": output.model_version,
        "assumptions": output.assumptions,
    }


def get_simulation(db: Session, business_id: str, simulation_id: str) -> SimulationResult:
    from app.core.errors import NotFoundError

    row = db.get(DigitalTwinSimulation, simulation_id)
    if row is None or row.business_id != business_id:
        raise NotFoundError(f"Simulation {simulation_id} not found.")

    output_dict = row.output_state_json
    output = SimulationOutput(**output_dict)
    return SimulationResult(
        id=row.id,
        business_id=row.business_id,
        goal_id=row.goal_id,
        input_state=row.input_state_json,
        actions=row.actions_json,
        output=output,
    )
