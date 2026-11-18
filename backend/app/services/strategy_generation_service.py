"""Goal-aware candidate strategy generation — docs/GOAL_PLANNER_SPECIFICATION.md
+ docs/DIGITAL_TWIN_SPECIFICATION.md §7.

Replaces the old fixed six-combo ``CANDIDATE_GRID`` in decision_service:
the set of candidate strategies now depends on the goal's objective, on
what data the business actually has, and on the goal's constraints.

Honesty rules (AGENTS.md "no fabrication"):
- The only levers the Digital Twin transition function actually responds
  to are ``price`` and ``marketing_spend`` (the registered forecasting
  model's features) plus an inventory availability cap. So every candidate
  here is expressed purely in those three action types
  (``price_change`` / ``marketing_change`` / ``inventory_change``). We do
  not invent action types the simulator cannot execute.
- For objectives the simulator cannot fully model (e.g. reduce_churn — the
  twin has no retention mechanism), candidates are still generated from the
  levers that *are* simulatable, and each one's ``assumptions`` list says
  plainly what is and isn't being modelled.
- Candidate families that need data the business hasn't provided
  (marketing spend, inventory) are excluded with a stated reason rather
  than simulated against zeros.
- If nothing can be generated, the caller gets an explicit
  insufficient-evidence result.
"""
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.analytics import kpi_service
from app.analytics.digital_twin_service import (
    ACTION_VALUE_BOUNDS,
    _current_inventory_units,
)

# --- Constraint vocabulary -------------------------------------------------
# Recognised constraint tokens (stored on Goal.constraints_json). Anything
# else is passed through untouched and simply has no filtering effect.
NO_PRICE_INCREASE = "no_price_increase"
NO_PRICE_DECREASE = "no_price_decrease"
NO_PRICE_CHANGE = "no_price_change"
NO_MARKETING_INCREASE = "no_marketing_increase"
NO_MARKETING_DECREASE = "no_marketing_decrease"

KNOWN_CONSTRAINTS = {
    NO_PRICE_INCREASE,
    NO_PRICE_DECREASE,
    NO_PRICE_CHANGE,
    NO_MARKETING_INCREASE,
    NO_MARKETING_DECREASE,
}

ACTION_LABELS = {
    "marketing_change": "Marketing",
    "price_change": "Price",
    "inventory_change": "Inventory",
}


@dataclass
class CandidateStrategy:
    name: str
    actions: list[dict]  # [{"type": "marketing_change", "value": 10}, ...]
    rationale: str
    goal_alignment: str
    targets: list[str] = field(default_factory=list)  # causal / KPI nodes it acts on
    assumptions: list[str] = field(default_factory=list)


@dataclass
class StrategyGenerationResult:
    goal_id: str
    objective: str
    candidates: list[CandidateStrategy]
    excluded: list[str] = field(default_factory=list)
    constraints_applied: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _name_for_actions(actions: list[dict]) -> str:
    parts = []
    for a in actions:
        sign = "+" if a["value"] >= 0 else ""
        parts.append(f"{ACTION_LABELS[a['type']]} {sign}{a['value']:g}%")
    return " & ".join(parts)


def _within_bounds(actions: list[dict]) -> bool:
    for a in actions:
        low, high = ACTION_VALUE_BOUNDS[a["type"]]
        if not (low <= a["value"] <= high):
            return False
    return True


def _normalise_constraints(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = list(raw.keys())
    return [str(c).strip().lower().replace(" ", "_") for c in raw]


def _violates_constraints(actions: list[dict], constraints: list[str]) -> bool:
    for a in actions:
        v = a["value"]
        if a["type"] == "price_change":
            if NO_PRICE_CHANGE in constraints and v != 0:
                return True
            if NO_PRICE_INCREASE in constraints and v > 0:
                return True
            if NO_PRICE_DECREASE in constraints and v < 0:
                return True
        if a["type"] == "marketing_change":
            if NO_MARKETING_INCREASE in constraints and v > 0:
                return True
            if NO_MARKETING_DECREASE in constraints and v < 0:
                return True
    return False


# --- Per-objective candidate templates -----------------------------------
# Each template is (actions, rationale, goal_alignment, targets).
def _revenue_templates() -> list[tuple]:
    return [
        ([{"type": "marketing_change", "value": 10}],
         "Grow reach and top-of-funnel demand by increasing marketing spend.",
         "More marketing spend is the most direct lever on order volume and revenue.",
         ["marketing_spend", "orders", "revenue"]),
        ([{"type": "marketing_change", "value": 20}],
         "A larger marketing push to test whether demand still responds at higher spend.",
         "Tests the upper end of the marketing response curve for revenue.",
         ["marketing_spend", "orders", "revenue"]),
        ([{"type": "price_change", "value": 5}],
         "Raise price modestly — revenue can rise if demand is not fully price-sensitive.",
         "Revenue = price x volume; a small price rise lifts revenue where the volume it "
         "costs is smaller than the price gain (the simulation checks which).",
         ["price", "demand", "sales", "revenue"]),
        ([{"type": "price_change", "value": 10}],
         "A larger price increase to test whether the revenue gain outweighs volume lost.",
         "Tests the upper end of the price-response curve for revenue.",
         ["price", "demand", "sales", "revenue"]),
        ([{"type": "price_change", "value": -3}],
         "A small price reduction to nudge unit demand with minimal margin give-up.",
         "Low-risk demand lever — small price move, small volume response.",
         ["price", "demand", "sales", "revenue"]),
        ([{"type": "price_change", "value": -5}],
         "Lower prices modestly to lift unit demand.",
         "A price cut trades margin for volume — can raise revenue if demand is elastic.",
         ["price", "demand", "sales", "revenue"]),
        ([{"type": "price_change", "value": -10}],
         "A deeper discount to maximise unit demand.",
         "Larger price cut for a bigger volume response.",
         ["price", "demand", "sales", "revenue"]),
        ([{"type": "marketing_change", "value": 10}, {"type": "price_change", "value": -5}],
         "Combine a marketing increase with a modest discount to compound the demand effect.",
         "Two demand levers at once — reach plus price.",
         ["marketing_spend", "price", "demand", "revenue"]),
    ]


def _sales_templates() -> list[tuple]:
    # Same demand levers as revenue, framed around unit volume.
    templates = _revenue_templates()
    return [
        (actions, rationale, "Targets unit sales volume directly via " + ", ".join(targets) + ".", targets)
        for actions, rationale, _align, targets in templates
    ]


def _profit_templates(marketing_roi: float | None) -> list[tuple]:
    templates = [
        ([{"type": "price_change", "value": 5}],
         "Raise prices modestly to widen margin on existing volume.",
         "A price increase lifts margin directly; the simulation checks how much volume it costs.",
         ["price", "revenue", "profit"]),
        ([{"type": "price_change", "value": 10}],
         "A larger price increase to test margin gains against demand loss.",
         "Tests whether the margin gain outweighs the volume the model predicts is lost.",
         ["price", "revenue", "profit"]),
        ([{"type": "marketing_change", "value": -10}],
         "Cut marketing spend to reduce cost, keeping only the most efficient spend.",
         "Lower spend improves profit if the marginal marketing return is below break-even.",
         ["marketing_spend", "profit"]),
        ([{"type": "marketing_change", "value": -20}],
         "A deeper marketing cut to test how much revenue is genuinely spend-driven.",
         "Isolates baseline demand from paid demand for the profit calculation.",
         ["marketing_spend", "profit"]),
        ([{"type": "price_change", "value": 5}, {"type": "marketing_change", "value": -10}],
         "Raise price and trim marketing together — a margin-and-cost play.",
         "Attacks profit from both sides: higher margin, lower cost.",
         ["price", "marketing_spend", "profit"]),
    ]
    if marketing_roi is not None and marketing_roi > 0:
        templates.append((
            [{"type": "marketing_change", "value": 10}],
            "Marketing ROI is currently positive, so more spend may still add profit.",
            "Only proposed because recorded marketing ROI is above break-even.",
            ["marketing_spend", "revenue", "profit"],
        ))
    return templates


def _marketing_roi_templates() -> list[tuple]:
    return [
        ([{"type": "marketing_change", "value": -30}],
         "Sharply reduce marketing spend to find the efficient core.",
         "If revenue holds while spend drops, ROI improves.",
         ["marketing_spend"]),
        ([{"type": "marketing_change", "value": -20}],
         "Reduce marketing spend and measure the revenue give-back.",
         "Directly tests marketing efficiency.",
         ["marketing_spend"]),
        ([{"type": "marketing_change", "value": -10}],
         "Trim marketing spend modestly.",
         "Small efficiency test with limited downside.",
         ["marketing_spend"]),
        ([{"type": "marketing_change", "value": 10}],
         "Increase spend to check whether ROI is still rising (not yet saturated).",
         "ROI improves only if incremental revenue outpaces the extra spend.",
         ["marketing_spend"]),
        ([{"type": "marketing_change", "value": 20}],
         "A larger spend increase to locate the point of diminishing returns.",
         "Maps the marketing response curve for the ROI calculation.",
         ["marketing_spend"]),
    ]


def _inventory_risk_templates() -> list[tuple]:
    return [
        ([{"type": "inventory_change", "value": 20}],
         "Increase stock on hand to reduce the chance of stockouts capping sales.",
         "More availability lifts the sales the simulation is allowed to fulfil.",
         ["inventory", "availability", "sales"]),
        ([{"type": "inventory_change", "value": 10}],
         "A modest stock increase to buffer demand variability.",
         "Reduces fulfilment risk with less working-capital exposure.",
         ["inventory", "availability", "sales"]),
        ([{"type": "inventory_change", "value": -10}],
         "Reduce stock to lower overstock/holding risk when demand is soft.",
         "Cuts inventory exposure; the simulation flags if it starts capping sales.",
         ["inventory", "availability"]),
        ([{"type": "inventory_change", "value": -20}],
         "A deeper stock reduction to test how much inventory is genuinely needed.",
         "Finds the leanest stock level that still meets projected demand.",
         ["inventory", "availability"]),
        ([{"type": "price_change", "value": 5}, {"type": "inventory_change", "value": -10}],
         "Slow demand slightly with a price rise while trimming stock.",
         "Rebalances supply and demand to lower inventory risk.",
         ["price", "inventory", "availability"]),
    ]


def _churn_templates() -> list[tuple]:
    retention_note = (
        "The Digital Twin does not model customer retention directly — it projects the "
        "revenue/volume effect of this action only. Treat the churn impact as a hypothesis, "
        "not a simulated result."
    )
    return [
        ([{"type": "price_change", "value": -5}],
         "Lower prices as a retention lever — a cheaper offer can reduce churn among price-sensitive customers.",
         "Price is the only retention-adjacent lever the simulator can act on.",
         ["price", "retention", "repeat_purchases"],
         [retention_note]),
        ([{"type": "price_change", "value": -10}],
         "A deeper price reduction aimed at at-risk, price-sensitive customers.",
         "Stronger retention-pricing signal.",
         ["price", "retention", "repeat_purchases"],
         [retention_note]),
        ([{"type": "marketing_change", "value": 10}],
         "Increase marketing spend on re-engagement / loyalty campaigns.",
         "More spend can fund win-back and loyalty touchpoints.",
         ["marketing_spend", "retention", "repeat_purchases"],
         [retention_note]),
    ]


def generate_candidates(db: Session, business_id: str, goal) -> StrategyGenerationResult:
    """Build the goal-aware candidate strategy set for a business + goal.

    ``goal`` is an app.models.goal.Goal (or any object exposing
    ``objective``, ``constraints_json``, ``id``).
    """
    objective = goal.objective
    constraints = _normalise_constraints(getattr(goal, "constraints_json", None))
    applied = [c for c in constraints if c in KNOWN_CONSTRAINTS]

    kpis = kpi_service.compute_kpis(db, business_id)
    has_marketing = kpis.marketing_spend > 0
    has_inventory = _current_inventory_units(db, business_id) is not None
    has_cost = kpis.profit is not None

    excluded: list[str] = []
    notes: list[str] = []

    # --- pick the objective's raw template set --------------------------
    raw: list[tuple]
    if objective == "increase_revenue":
        raw = _revenue_templates()
    elif objective == "increase_sales":
        raw = _sales_templates()
    elif objective == "increase_profit":
        raw = _profit_templates(kpis.marketing_roi)
        if not has_cost:
            notes.append(
                "No product unit_cost on file — profit strategies are scored on revenue impact "
                "instead, and margin effects of price changes cannot be quantified."
            )
    elif objective == "improve_marketing_roi":
        if not has_marketing:
            return StrategyGenerationResult(
                goal_id=goal.id, objective=objective, candidates=[],
                excluded=["All marketing-ROI strategies need recorded marketing spend > 0."],
                constraints_applied=applied,
                notes=["Upload marketing campaign data with real spend to analyse this goal."],
            )
        raw = _marketing_roi_templates()
    elif objective == "reduce_inventory_risk":
        if not has_inventory:
            return StrategyGenerationResult(
                goal_id=goal.id, objective=objective, candidates=[],
                excluded=["All inventory-risk strategies need inventory or product stock data."],
                constraints_applied=applied,
                notes=["Upload inventory data (or product stock_quantity) to analyse this goal."],
            )
        raw = _inventory_risk_templates()
    elif objective == "reduce_churn":
        raw = _churn_templates()
        notes.append(
            "Churn-reduction strategies are simulated for their revenue/volume effect only; "
            "the retention effect itself is not modelled by the Digital Twin."
        )
    else:
        # Unknown objective — fall back to the general demand grid.
        raw = _revenue_templates()
        notes.append(f"Objective '{objective}' has no dedicated strategy set; using general demand levers.")

    # --- filter by data availability & constraints ---------------------
    candidates: list[CandidateStrategy] = []
    dropped_marketing = dropped_inventory = 0
    for tpl in raw:
        actions = tpl[0]
        rationale = tpl[1]
        alignment = tpl[2]
        targets = tpl[3]
        assumptions = list(tpl[4]) if len(tpl) > 4 else []

        types = {a["type"] for a in actions}
        if "marketing_change" in types and not has_marketing:
            dropped_marketing += 1
            continue
        if "inventory_change" in types and not has_inventory:
            dropped_inventory += 1
            continue
        if not _within_bounds(actions):
            continue
        if _violates_constraints(actions, constraints):
            continue

        candidates.append(
            CandidateStrategy(
                name=_name_for_actions(actions),
                actions=actions,
                rationale=rationale,
                goal_alignment=alignment,
                targets=targets,
                assumptions=assumptions,
            )
        )

    if dropped_marketing:
        excluded.append(
            f"{dropped_marketing} marketing-based candidate(s) skipped — no recorded marketing spend."
        )
    if dropped_inventory:
        excluded.append(
            f"{dropped_inventory} inventory-based candidate(s) skipped — no inventory data."
        )

    # De-duplicate by action signature (constraints/data filters can leave
    # a family with only its no-op survivors).
    seen: set = set()
    unique: list[CandidateStrategy] = []
    for c in candidates:
        sig = tuple(sorted((a["type"], a["value"]) for a in c.actions))
        if sig in seen:
            continue
        seen.add(sig)
        unique.append(c)

    return StrategyGenerationResult(
        goal_id=goal.id,
        objective=objective,
        candidates=unique,
        excluded=excluded,
        constraints_applied=applied,
        notes=notes,
    )
