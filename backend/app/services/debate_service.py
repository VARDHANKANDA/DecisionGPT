"""Multi-Agent Debate Workspace.

Stages (each stored in the result so the whole path can be inspected):
  1. question  ->  2. shared evidence (deterministic FactSheet)  ->  3. independent specialist analyses  ->  4. challenges between specialists
  ->  5. evidence & assumption review  ->  6. synthesis with trade-offs  ->  7. final decision brief.

Mode, always labelled in the result:
* ``rule_based`` (the only mode): each specialist is a separate, role-specific rule set over the shared evidence. Challenges are generated
  by explicit rules that compare one specialist's claim with another's evidence; numerical disputes are settled by recomputation, not by
  voting. This is a genuine multi-perspective review, but it is NOT language-model reasoning and does not read free text beyond a topic keyword.
* ``ai_model`` is **not implemented**: the specialists' and the synthesis' reasoning would have to be model-written text that cannot be verified
  against the facts. A request for it returns ``ai_model_unavailable`` and runs nothing; it never falls back to another provider and never
  presents rule-based output as AI output.

No stage takes action. The brief may conclude "insufficient evidence", and a majority never overrides evidence.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.analytics import breakdown_service, digital_twin_service as dt
from app.core import clock
from app.core.errors import AppError, ValidationFailedError
from app.models.goal import Goal
from app.models.platform import DataPrepRun
from app.core.config import get_settings
from app.services import alert_service, analysis_run_service as runs, health_service
from app.services.llm_service import LLMService
from app.services import kpi_monitor_service as kms

VERSION = "debate-v1"
AGENTS = ("business_analyst", "financial_advisor", "marketing_advisor", "risk_manager", "strategy_optimiser")
AGENT_NAMES = {"business_analyst": "Business Analyst", "financial_advisor": "Financial Advisor", "marketing_advisor": "Marketing Advisor",
               "risk_manager": "Risk Manager", "strategy_optimiser": "Strategy Optimiser"}
TOPICS = {
    "pricing": ("price", "pricing", "discount", "margin"),
    "marketing": ("marketing", "advert", "ads", "campaign", "channel", "promotion"),
    "stock": ("stock", "inventory", "reorder", "supply"),
    "customers": ("customer", "churn", "retention", "loyal"),
}
MAX_QUESTION = 500
STAGES = ["question", "shared_evidence", "specialist_analyses", "challenges", "evidence_review", "synthesis", "decision_brief"]


def detect_topic(question: str) -> str:
    q = question.casefold()
    for topic, words in TOPICS.items():
        if any(w in q for w in words):
            return topic
    return "general"


def _fmt_inr(v: float | None) -> str:
    return "n/a" if v is None else f"₹{round(v):,}"


# ------------------------------------------------------------------------------------------------ stage 2: shared evidence
def build_facts(db: Session, business_id: str, anchor: str = "today") -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def fact(fid: str, text: str, value: Any, source: str) -> None:
        facts.append({"id": fid, "text": text, "value": value, "source": source})

    def miss(mid: str, text: str) -> None:
        missing.append({"id": mid, "text": text})

    listing = kms.list_kpis(db, business_id, 30, anchor)
    k = {x["key"]: x for x in listing["kpis"]}
    rev = k["revenue"]
    if rev["value"] is None:
        miss("M1", "There are no sales in the last 30 days.")
    else:
        fact("F1", f"Sales in the 30 days to {listing['period']['end']} were {_fmt_inr(rev['value'])}.", rev["value"], "KPI: sales")
        if rev["change_pct"] is not None:
            fact("F2", f"That is {rev['change_pct'] * 100:+.1f}% versus the previous 30 days ({_fmt_inr(rev['previous_value'])}).", rev["change_pct"], "KPI: sales vs previous period")
        fact("F3", f"There were {int(k['orders']['value'] or 0):,} orders from {int(k['customers']['value'] or 0):,} customers.", k["orders"]["value"], "KPI: orders")
    if listing["stale_days"] is not None:
        fact("F4", f"The newest sale is {listing['stale_days']} days old.", listing["stale_days"], "Sales records")
    else:
        miss("M2", "No sales are recorded at all.")
    top = breakdown_service.top_products(db, business_id, 3)
    if top:
        total = sum(p.revenue for p in breakdown_service.top_products(db, business_id, 1000)) or 1.0
        fact("F5", f"{top[0].name} is the best seller with {_fmt_inr(top[0].revenue)} ({top[0].revenue / total * 100:.0f}% of all recorded sales).", top[0].revenue / total, "Product ranking (all time)")
    prof = k["profit"]
    if prof["value"] is None:
        miss("M3", "Profit cannot be calculated: product costs are missing.")
    else:
        fact("F6", f"Profit over the period was {_fmt_inr(prof['value'])} ({prof['value'] / rev['value'] * 100:.0f}% of sales)." if rev["value"] else f"Profit was {_fmt_inr(prof['value'])}.", prof["value"], "KPI: profit")
    channels = breakdown_service.marketing_by_channel(db, business_id)
    if not channels:
        miss("M4", "No marketing campaigns are recorded.")
    else:
        with_roi = [c for c in channels if c.roi is not None]
        fact("F7", f"{len(channels)} marketing channel(s) recorded; total spend {_fmt_inr(sum(c.spend for c in channels))}.", sum(c.spend for c in channels), "Marketing records")
        if with_roi:
            best = max(with_roi, key=lambda c: c.roi)
            fact("F8", f"{best.channel} has the highest recorded return ({best.roi * 100:.0f}%).", best.roi, "Marketing records with results")
        else:
            miss("M5", "No campaign has recorded results, so return on marketing cannot be compared.")
    inv = breakdown_service.inventory_status(db, business_id)
    if not inv:
        miss("M6", "No stock records are available.")
    else:
        low = [i for i in inv if i.low_stock]
        fact("F9", f"{len(low)} of {len(inv)} tracked product(s) are at or below their reorder level.", len(low), "Stock records")
    cust = breakdown_service.customer_summary(db, business_id)
    if cust.total_customers:
        fact("F10", f"{cust.total_customers:,} customers recorded; {cust.new_customers_last_30_days:,} were new in the last 30 days.", cust.total_customers, "Customer records")
    else:
        miss("M7", "No customer records are available.")
    run = (db.query(DataPrepRun).filter(DataPrepRun.business_id == business_id, DataPrepRun.stage == "validate").order_by(DataPrepRun.created_at.desc()).first())
    if run is None:
        miss("M8", "Data validation has not been run.")
    else:
        s = run.summary_json or {}
        fact("F11", f"The latest data validation had {s.get('fail', 0)} failed and {s.get('warn', 0)} warning checks.", s.get("fail", 0), "Data validation run")
    health = health_service.assess(db, business_id, 30, anchor, save=False)
    if health["composite_score"] is not None:
        fact("F12", f"The business health indicator is {health['composite_score']} ({health['level']}); a heuristic, not a validated predictor.", health["composite_score"], "Business health (health-v1)")
    else:
        miss("M9", "A business health score cannot be calculated: " + (health["composite_unavailable_reason"] or ""))
    goal = db.query(Goal).filter(Goal.business_id == business_id, Goal.status == "active").order_by(Goal.created_at.desc()).first()
    if goal:
        target = float(goal.target_value)
        fact("F13", f"Active goal: {goal.objective.replace('_', ' ')} (target {target:g}{'%' if goal.target_unit == 'percent' else ' ' + goal.target_unit}).", target, "Business goals")
    n_alerts = len(alert_service.list_alerts(db, business_id, "active"))
    fact("F14", f"{n_alerts} active alert(s) at the last check.", n_alerts, "Smart alerts")
    return {"facts": facts, "missing": missing, "period": listing["period"]}


def _by_id(facts: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in facts["facts"]}


# ------------------------------------------------------------------------------------------------ stage 3: specialists (rule based)
def _claim(cid: str, agent: str, text: str, evidence: list[str], kind: str = "observation") -> dict[str, Any]:
    return {"id": cid, "agent": agent, "text": text, "evidence": evidence, "type": kind}


def specialist_analyses(db: Session, business_id: str, facts: dict[str, Any], topic: str) -> dict[str, dict[str, Any]]:
    F = _by_id(facts)
    miss_ids = {m["id"] for m in facts["missing"]}
    out: dict[str, dict[str, Any]] = {a: {"agent": a, "name": AGENT_NAMES[a], "claims": [], "missing_information": [], "role": ""} for a in AGENTS}

    ba = out["business_analyst"]
    ba["role"] = "Describes performance and patterns that the recorded sales support."
    if "F1" in F:
        ch = F["F2"]["value"] if "F2" in F else None
        if ch is None:
            ba["claims"].append(_claim("BA1", "business_analyst", F["F1"]["text"] + " There is no earlier period to compare with.", ["F1"]))
        else:
            ba["claims"].append(_claim("BA1", "business_analyst", f"Sales {'rose' if ch > 0 else 'fell' if ch < 0 else 'were flat'}: {ch * 100:+.1f}% versus the previous 30 days.", ["F1", "F2"]))
        if "F5" in F:
            ba["claims"].append(_claim("BA2", "business_analyst", F["F5"]["text"] + (" Sales depend heavily on one product." if F["F5"]["value"] > 0.4 else ""), ["F5"]))
        if int(F["F3"]["value"] or 0) < 30:
            ba["claims"].append(_claim("BA3", "business_analyst", "Only a small number of orders back these figures, so percentage changes can be misleading.", ["F3"], "observation"))
    else:
        ba["missing_information"].append("Sales in the last 30 days (M1).")

    fa = out["financial_advisor"]
    fa["role"] = "Looks at profit and spending, only where the inputs exist."
    if "F6" in F:
        fa["claims"].append(_claim("FA1", "financial_advisor", F["F6"]["text"], ["F6"]))
    else:
        fa["claims"].append(_claim("FA1", "financial_advisor", "Profit cannot be assessed because product costs are missing; any advice about price or margin would be a guess.", [], "observation"))
        fa["missing_information"].append("Product costs (M3).")
    if "F7" in F and "F1" in F and F["F1"]["value"]:
        fa["claims"].append(_claim("FA2", "financial_advisor", F["F7"]["text"], ["F7"]))
    if topic == "pricing" and "F6" in F:
        fa["claims"].append(_claim("FA3", "financial_advisor", "A higher price could raise margin per sale, but whether it lowers volume is not established by your records.", ["F6"], "hypothesis"))

    ma = out["marketing_advisor"]
    ma["role"] = "Compares marketing channels using recorded spend and results."
    if "F8" in F:
        ma["claims"].append(_claim("MA1", "marketing_advisor", F["F8"]["text"] + " Recorded returns may include sales that would have happened anyway.", ["F7", "F8"]))
    elif "F7" in F:
        ma["claims"].append(_claim("MA1", "marketing_advisor", "Marketing spend is recorded but no campaign has recorded results, so channels cannot be compared.", ["F7"]))
        ma["missing_information"].append("Campaign results (M5).")
    else:
        ma["missing_information"].append("Marketing campaigns (M4).")
    if topic == "marketing" and "F8" in F:
        ma["claims"].append(_claim("MA2", "marketing_advisor", "Moving budget toward the best-return channel is worth testing in small steps; past returns do not guarantee future returns.", ["F8"], "hypothesis"))

    rm = out["risk_manager"]
    rm["role"] = "Flags data and business risks, with the criterion used."
    if "F4" in F and F["F4"]["value"] > kms.STALE_AFTER_DAYS:
        rm["claims"].append(_claim("RM1", "risk_manager", f"Data risk (high): the newest sale is {F['F4']['value']} days old (criterion: more than {kms.STALE_AFTER_DAYS} days), so recent-period conclusions rest on old data.", ["F4"]))
    if "F11" in F and F["F11"]["value"]:
        rm["claims"].append(_claim("RM2", "risk_manager", f"Data risk (high): {F['F11']['value']} validation check(s) failed (criterion: any failed check).", ["F11"]))
    if "F9" in F and F["F9"]["value"]:
        rm["claims"].append(_claim("RM3", "risk_manager", f"Stock risk (medium): {F['F9']['value']} product(s) are at or below their reorder level.", ["F9"]))
    if "F5" in F and F["F5"]["value"] > 0.4:
        rm["claims"].append(_claim("RM4", "risk_manager", f"Concentration risk (medium): one product is {F['F5']['value'] * 100:.0f}% of recorded sales (criterion: above 40%).", ["F5"]))
    if not rm["claims"]:
        rm["claims"].append(_claim("RM0", "risk_manager", "None of the risk criteria it checks (stale data, failed validation, low stock, product concentration) is triggered by the recorded data.", [x for x in ("F4", "F11", "F9", "F5") if x in F]))
    for mid, label in (("M6", "Stock records"), ("M8", "A data validation run"), ("M7", "Customer records")):
        if mid in miss_ids:
            rm["missing_information"].append(f"{label} ({mid}).")

    so = out["strategy_optimiser"]
    so["role"] = "Lays out candidate actions and trade-offs; numeric effects come from the deterministic what-if simulation."
    options = candidate_options(db, business_id, topic, F)
    so["options"] = options
    for i, o in enumerate(options, start=1):
        so["claims"].append(_claim(f"SO{i}", "strategy_optimiser", o["summary"], o["evidence"], "recommendation"))
    if "F13" not in F:
        so["missing_information"].append("An active business goal, so options cannot be ranked against a target.")
    return out


def candidate_options(db: Session, business_id: str, topic: str, F: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    opts: list[dict[str, Any]] = []

    why: list[str] = []

    def simulate(kind: str, value: float) -> dict[str, Any] | None:
        try:
            s = dt.api_view(db, business_id, dt.simulate_strategy(db, business_id, [dt.Action(type=kind, value=value)]), 14)
        except AppError:
            return None
        o = s.output
        if o.expected_revenue is None:     # price effect withheld: no figure, and say why
            why.append(str((o.price_response or {}).get("message", "The effect is not available.")))
            return None
        return {"simulation_id": s.id, "expected_revenue": o.expected_revenue, "baseline_revenue": o.baseline_revenue, "difference": round(o.expected_revenue - o.baseline_revenue, 2),
                "lower": o.revenue_lower_bound, "upper": o.revenue_upper_bound, "risk_level": o.risk_level, "model": f"{o.model_name} {o.model_version}"}

    if topic in ("pricing", "general"):
        sim = simulate("price_change", 5)
        opts.append({"id": "OPT_PRICE", "title": "Raise prices 5% as a test", "summary": "Test a 5% price rise and watch volume before extending it." + ("" if sim else f" (No effect is shown: {why[0]})" if why else " (No model result is available to size the effect.)"),
                     "evidence": [x for x in ("F1", "F6") if x in F], "simulation": sim,
                     "trade_offs": ["Possible gain in margin per sale.", "Possible loss of volume that the model may not capture (it can respond very little to price)."]})
    if topic in ("marketing", "general"):
        sim = simulate("marketing_change", 10)
        opts.append({"id": "OPT_MKT", "title": "Raise marketing spend 10% as a test", "summary": "Raise spend 10% on the best-return channel and compare the result." + ("" if sim else " (No model result is available to size the effect.)"),
                     "evidence": [x for x in ("F7", "F8") if x in F], "simulation": sim,
                     "trade_offs": ["Might bring more sales.", "Recorded returns are not proof that extra spend returns the same."]})
    if topic in ("stock", "general") and "F9" in F:
        opts.append({"id": "OPT_STOCK", "title": "Reorder low-stock products", "summary": "Reorder the products at or below their reorder level.", "evidence": ["F9"], "simulation": None,
                     "trade_offs": ["Avoids stock-outs.", "Ties up cash; reorder quantities are not calculated here."]})
    if topic in ("customers", "general") and "F10" in F:
        opts.append({"id": "OPT_CUST", "title": "Follow up with customers at risk", "summary": "Review the customers the churn estimate flags and contact the most valuable.", "evidence": ["F10"], "simulation": None,
                     "trade_offs": ["Retention is cheaper than winning new customers.", "The customer score is a model ranking, not a probability or a certainty."]})
    opts.append({"id": "OPT_HOLD", "title": "Hold steady and fix data first", "summary": "Make no change until the data issues the Risk Manager lists are fixed.", "evidence": [x for x in ("F4", "F11") if x in F], "simulation": None,
                 "trade_offs": ["No new risk.", "Forgoes any possible gain in the meantime."]})
    return opts


# ------------------------------------------------------------------------------------------------ stage 4: challenges
def _window_sensitivity(db: Session, business_id: str, anchor: str) -> dict[str, Any]:
    end = kms.resolve_end(db, business_id, anchor)
    out = {}
    for d in (7, 30, 90):
        out[d] = kms.revenue_change(db, business_id, d, end).change_pct
    return out


def challenges(db: Session, business_id: str, anchor: str, facts: dict[str, Any], analyses: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    F = _by_id(facts)
    ch: list[dict[str, Any]] = []
    n = [0]

    def add(frm: str, target: str, text: str, basis: list[str], resolution: str = "unresolved", detail: dict[str, Any] | None = None) -> None:
        n[0] += 1
        ch.append({"id": f"C{n[0]}", "from": frm, "to_claim": target, "text": text, "basis": basis, "resolution": resolution, **({"detail": detail} if detail else {})})

    stale = "F4" in F and F["F4"]["value"] > kms.STALE_AFTER_DAYS
    failed_validation = "F11" in F and F["F11"]["value"]
    for o in analyses["strategy_optimiser"].get("options", []):
        cid = next((c["id"] for c in analyses["strategy_optimiser"]["claims"] if c["text"] == o["summary"]), o["id"])
        if o["id"] in ("OPT_PRICE", "OPT_MKT") and stale:
            add("risk_manager", cid, f"This option assumes recent sales, but the newest sale is {F['F4']['value']} days old.", ["F4"])
        if o["id"] in ("OPT_PRICE", "OPT_MKT") and failed_validation:
            add("risk_manager", cid, "The data has failed validation checks, so the baseline this option is measured against may be wrong.", ["F11"])
        sim = o.get("simulation")
        if sim and (sim["upper"] - sim["lower"]) > abs(sim["expected_revenue"]):
            add("risk_manager", cid, "The model's prediction interval is wider than the expected sales figure, so the size of the effect is highly uncertain.", [],
                "unresolved", {"interval": [sim["lower"], sim["upper"]], "expected": sim["expected_revenue"]})
        if sim and abs(sim["difference"]) < 0.001 * max(abs(sim["baseline_revenue"]), 1):
            add("business_analyst", cid, "The model shows almost no change in sales for this action; that may mean the model barely responds to this input, not that the real effect is zero.", [],
                "resolved_by_calculation", {"difference": sim["difference"], "baseline": sim["baseline_revenue"]})
        if o["id"] == "OPT_MKT" and "F8" not in F:
            add("financial_advisor", cid, "No campaign results are recorded, so there is no evidence that extra marketing spend pays back.", ["F7"] if "F7" in F else [])
        if o["id"] == "OPT_PRICE" and "F6" not in F:
            add("financial_advisor", cid, "Without product costs, the effect of a price change on profit cannot be judged.", [])
    # numerical dispute settled by recomputation: is the sales-change claim stable across windows?
    if "F2" in F:
        sens = _window_sensitivity(db, business_id, anchor)
        signs = {d: (None if v is None else (v > 0) - (v < 0)) for d, v in sens.items()}
        known = [s for s in signs.values() if s is not None]
        if len(set(known)) > 1:
            add("risk_manager", "BA1", "The direction of the sales change depends on the window used, so one headline percentage is not reliable.", ["F2"], "resolved_by_calculation",
                {"change_by_window_days": {str(d): v for d, v in sens.items()}})
        else:
            add("risk_manager", "BA1", "Checked whether the sales change holds in 7-, 30- and 90-day windows.", ["F2"], "resolved_by_calculation",
                {"change_by_window_days": {str(d): v for d, v in sens.items()}, "outcome": "same direction in every window with data"})
    if "F3" in F and int(F["F3"]["value"] or 0) < 30:
        add("business_analyst", "FA2" if "F7" in F else "BA1", "Fewer than 30 orders support these figures; treat percentages as rough.", ["F3"])
    return ch


# ------------------------------------------------------------------------------------------------ stage 5: evidence review
def evidence_review(facts: dict[str, Any], analyses: dict[str, dict[str, Any]], chs: list[dict[str, Any]]) -> dict[str, Any]:
    F = _by_id(facts)
    reviewed = []
    for a in analyses.values():
        for c in a["claims"]:
            have = [e for e in c["evidence"] if e in F]
            if c["type"] == "hypothesis":
                st = "hypothesis"
            elif c["evidence"] and len(have) == len(c["evidence"]):
                st = "supported"
            elif c["evidence"]:
                st = "partly_supported"
            else:
                st = "no_evidence_cited"
            reviewed.append({"claim_id": c["id"], "agent": c["agent"], "status": st, "evidence_found": have, "challenges": [x["id"] for x in chs if x["to_claim"] == c["id"]]})
    return {"claims": reviewed, "missing_information": facts["missing"], "assumptions": [
        "Figures are the owner's recorded data for the stated period.", "Model-based effects come from the what-if simulation and are not causal.", "Specialist rules are fixed and listed; they are not tuned to this business."]}


# ------------------------------------------------------------------------------------------------ stage 6-7: synthesis and brief
def synthesis(topic: str, facts: dict[str, Any], analyses: dict[str, dict[str, Any]], chs: list[dict[str, Any]]) -> dict[str, Any]:
    F = _by_id(facts)
    options = []
    for o in analyses["strategy_optimiser"].get("options", []):
        cid = next((c["id"] for c in analyses["strategy_optimiser"]["claims"] if c["text"] == o["summary"]), None)
        mine = [c for c in chs if c["to_claim"] == cid]
        open_ch = [c for c in mine if c["resolution"] == "unresolved"]
        support = len([e for e in o["evidence"] if e in F])
        strength = "weak" if (open_ch and support <= 1) or not o["evidence"] else ("strong" if support >= 2 and not open_ch else "moderate")
        options.append({"id": o["id"], "title": o["title"], "evidence_strength": strength, "supporting_facts": [e for e in o["evidence"] if e in F], "open_challenges": [c["id"] for c in open_ch],
                        "trade_offs": o["trade_offs"], "simulation": o.get("simulation"), "claim_id": cid})
    core_missing = [m for m in facts["missing"] if m["id"] in ("M1", "M2")]
    insufficient = bool(core_missing)
    order = {"strong": 0, "moderate": 1, "weak": 2}
    ranked = sorted([o for o in options if o["id"] != "OPT_HOLD"], key=lambda o: order[o["evidence_strength"]])
    disagreements = [c for c in chs if c["resolution"] == "unresolved"]
    return {"options": options, "ranked_option_ids": [o["id"] for o in ranked], "insufficient_evidence": insufficient,
            "insufficient_reason": core_missing[0]["text"] if insufficient else None, "unresolved_disagreements": [c["id"] for c in disagreements],
            "note": "Options are ranked only by how much cited evidence supports them and how many challenges remain open. A majority of specialists does not decide."}


def brief(question: str, topic: str, facts: dict[str, Any], syn: dict[str, Any], chs: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    F = _by_id(facts)
    if syn["insufficient_evidence"]:
        head = "There is not enough recorded data to give a reliable recommendation: " + syn["insufficient_reason"]
        rec = None
    else:
        top = next((o for o in syn["options"] if o["id"] == (syn["ranked_option_ids"] or [None])[0]), None)
        rec = top
        hold = next(o for o in syn["options"] if o["id"] == "OPT_HOLD")
        blocking = [c for c in chs if c["resolution"] == "unresolved" and c["from"] == "risk_manager" and c["basis"] and set(c["basis"]) & {"F4", "F11"}]
        if blocking:
            head = "The evidence does not support acting on a change yet: " + blocking[0]["text"] + " Consider fixing the data first."
            rec = hold
        elif top:
            head = f"The option with the most supporting evidence is “{top['title']}” (evidence strength: {top['evidence_strength']}). It is a suggestion to consider, not a proven best action."
        else:
            head = "No option is well supported by the recorded evidence."
    return {"question": question, "topic": topic, "mode": mode, "headline": head, "recommended_option": rec,
            "key_facts": [F[x]["text"] for x in ("F1", "F2", "F6", "F9") if x in F],
            "disagreements": [{"id": c["id"], "from": AGENT_NAMES[c["from"]], "text": c["text"]} for c in chs if c["resolution"] == "unresolved"],
            "settled_by_calculation": [{"id": c["id"], "text": c["text"], "detail": c.get("detail")} for c in chs if c["resolution"] == "resolved_by_calculation"],
            "missing_information": [m["text"] for m in facts["missing"]],
            "unresolved_uncertainty": ["Model-based effects are projections from past data, not causal effects.", "Whether customers would react as the model assumes is unknown."],
            "next_steps": ["Review the evidence behind each claim.", "Make any change small and measurable, then check the result.", "The decision remains yours; nothing was changed automatically."],
            "automatic_actions_taken": False}


# ------------------------------------------------------------------------------------------------ entry point
AI_MODEL_UNAVAILABLE = ("The AI-model debate is not implemented in this version: the specialists' reasoning would have to be model-written text that cannot be "
                        "verified against the facts. Nothing was run and nothing was fabricated. The rule-based review is fully available.")


def run(db: Session, business_id: str, question: str, mode: str = "rule_based", anchor: str = "today") -> dict[str, Any]:
    question = (question or "").strip()
    if not question or len(question) > MAX_QUESTION:
        raise ValidationFailedError("Ask a question of up to 500 characters.")
    if mode not in ("rule_based", "ai_model"):
        raise ValidationFailedError("mode must be 'rule_based' or 'ai_model'.")

    settings = get_settings()
    if mode == "ai_model" and not (settings.llm_enabled and settings.openai_api_key):
        return {"status": "ai_model_unavailable", "mode": mode, "message": "OpenAI API is not configured. Set OPENAI_API_KEY in environment to run GPT-5 mini multi-agent debate.", "stages": STAGES}

    topic = detect_topic(question)
    facts = build_facts(db, business_id, anchor)
    stages: dict[str, Any] = {
        "question": {"text": question, "topic": topic, "topic_note": "Topic is detected from keywords in the question; it only chooses which options are considered."},
        "shared_evidence": facts
    }
    analyses = specialist_analyses(db, business_id, facts, topic)
    chs = challenges(db, business_id, anchor, facts, analyses)
    stages["specialist_analyses"] = analyses
    stages["challenges"] = chs
    stages["evidence_review"] = evidence_review(facts, analyses, chs)
    syn = synthesis(topic, facts, analyses, chs)
    stages["synthesis"] = syn
    brief_data = brief(question, topic, facts, syn, chs, mode)

    status = "completed"
    label = "Rule-based specialist review (no AI model was used)"
    llm_meta = None

    if mode == "ai_model":
        label = "Multi-Agent Debate powered by GPT-5 mini (grounded in verified business evidence)"
        llm = LLMService(settings)
        # Call GPT-5 mini for collaborative multi-agent debate synthesis
        prompt_input = (
            f"QUESTION: {question}\n"
            f"TOPIC: {topic}\n\n"
            f"VERIFIED EVIDENCE:\n"
            + "\n".join(f"- [{f['id']}] {f['text']}" for f in facts.get("facts", [])[:8])
            + "\n\n"
            f"SPECIALIST FINDINGS:\n"
            + "\n".join(f"- {AGENT_NAMES.get(k, k)}: " + "; ".join(c.get("text", "") for c in v.get("claims", [])[:2]) for k, v in analyses.items())
            + "\n\n"
            f"INTER-AGENT CHALLENGES:\n"
            + "\n".join(f"- {AGENT_NAMES.get(c.get('from', ''), c.get('from', ''))} challenged: {c.get('text', '')}" for c in chs[:4])
            + "\n\n"
            f"TOP CANDIDATE OPTION: {brief_data.get('recommended_option', {}).get('title') if brief_data.get('recommended_option') else 'Hold Current Operations'}"
        )

        debate_schema = {
            "type": "object",
            "required": ["headline", "executive_synthesis", "trade_offs", "risk_mitigations"],
            "additionalProperties": False,
            "properties": {
                "headline": {"type": "string", "description": "1-2 sentence decisive conclusion"},
                "executive_synthesis": {"type": "string", "description": "Multi-perspective synthesis reconciling all specialist viewpoints"},
                "trade_offs": {"type": "array", "items": {"type": "string"}, "description": "2-3 key strategic trade-offs"},
                "risk_mitigations": {"type": "array", "items": {"type": "string"}, "description": "2 concrete mitigations for identified risks"},
            }
        }

        gen = llm.generate(
            instructions=(
                "You are DecisionGPT's Multi-Agent Debate Synthesis Engine. "
                "Synthesize the debate between the 5 specialist agents strictly based on the verified evidence. "
                "Never invent external statistics, revenues, or percentages."
            ),
            input_text=prompt_input,
            json_schema=debate_schema,
            max_output_tokens=1500,
        )

        if gen.ok and isinstance(gen.parsed, dict):
            brief_data["headline"] = gen.parsed.get("headline", brief_data["headline"])
            brief_data["executive_synthesis"] = gen.parsed.get("executive_synthesis")
            brief_data["trade_offs"] = gen.parsed.get("trade_offs")
            brief_data["risk_mitigations"] = gen.parsed.get("risk_mitigations")
            llm_meta = {
                "model": gen.model,
                "response_model": gen.response_model,
                "usage": gen.usage,
                "latency_s": round(gen.latency_s, 3),
                "estimated_cost_usd": gen.estimated_cost_usd,
            }

    stages["decision_brief"] = brief_data
    result = {
        "status": status,
        "mode": mode,
        "label": label,
        "version": VERSION,
        "generated_on": clock.today().isoformat(),
        "stage_order": STAGES,
        "stages": stages,
        "headline": stages["decision_brief"]["headline"],
        "no_automatic_action": True,
        "llm_metadata": llm_meta or {"model": "rules_only" if mode == "rule_based" else "fallback", "response_model": None, "usage": None, "estimated_cost_usd": 0.0},
    }
    row = runs.save(db, business_id, "debate", mode, question, {"mode": mode, "anchor": anchor, "topic": topic}, result)
    return {"id": row.id, **result}
