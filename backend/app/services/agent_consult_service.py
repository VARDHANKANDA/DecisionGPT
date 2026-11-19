"""Individual Agent Consultation Service.

Provides dedicated, domain-specific execution for each of the 5 specialized DecisionGPT agents:
  1. Business Analyst (sales, revenue momentum, product velocities, baseline trends)
  2. Financial Advisor (profit margins, cost structures, budget allocation)
  3. Marketing Advisor (channel ROI, campaign lift, customer acquisition)
  4. Risk Manager (inventory stockouts, churn indicators, data quality, downside exposure)
  5. Strategy Optimiser (alternative comparison, what-if simulations, trade-off scoring)

Outputs structured, professional advice formatted in 6 executive sections:
  - Executive Summary
  - Key Findings
  - Supporting Evidence
  - Business Implications
  - Recommended Actions
  - Assumptions and Limitations
"""
from __future__ import annotations

import json
from typing import Any
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import debate_service
from app.services.llm_service import LLMService

AGENT_CONFIGS: dict[str, dict[str, Any]] = {
    "business-analyst": {
        "key": "business_analyst",
        "name": "Business Analyst",
        "role": "Sales Velocity & Performance Audit Specialist",
        "purpose": "Analyze sales and revenue trends, compare business periods, evaluate KPIs, and identify underperforming areas.",
        "icon": "📊",
    },
    "financial-advisor": {
        "key": "financial_advisor",
        "name": "Financial Advisor",
        "role": "Gross Margin Sustainability & Capital Allocation Specialist",
        "purpose": "Analyze revenue, expenses, profitability, and financial implications of business decisions.",
        "icon": "💰",
    },
    "marketing-advisor": {
        "key": "marketing_advisor",
        "name": "Marketing Advisor",
        "role": "Campaign Performance & Customer Channel Specialist",
        "purpose": "Analyze marketing spend, channel ROI, campaign results, and customer acquisition opportunities.",
        "icon": "📣",
    },
    "risk-manager": {
        "key": "risk_manager",
        "name": "Risk Manager",
        "role": "Operational Downside & Vulnerability Specialist",
        "purpose": "Scan for stockout liabilities, customer churn, data coverage gaps, and downside exposure.",
        "icon": "🛡️",
    },
    "strategy-optimiser": {
        "key": "strategy_optimiser",
        "name": "Strategy Optimiser",
        "role": "Strategic Synthesis & Trade-off Optimization Specialist",
        "purpose": "Synthesize operational evidence, compare alternatives via what-if simulation, and rank actionable strategies.",
        "icon": "🎯",
    },
}


def normalize_agent_id(agent_id: str) -> str:
    cleaned = agent_id.strip().lower().replace("_", "-")
    if cleaned in AGENT_CONFIGS:
        return cleaned
    for k in AGENT_CONFIGS:
        if k.replace("-", "") == cleaned.replace("-", ""):
            return k
    raise ValueError(f"Unknown agent: {agent_id}. Supported agents: {list(AGENT_CONFIGS.keys())}")


def consult_agent(db: Session, business_id: str, agent_id: str, task: str) -> dict[str, Any]:
    aid = normalize_agent_id(agent_id)
    cfg = AGENT_CONFIGS[aid]
    agent_key = cfg["key"]

    # 1. Gather verified factual baseline for the business
    facts_bundle = debate_service.build_facts(db, business_id, anchor="today")
    topic = debate_service.detect_topic(task)
    specialists = debate_service.specialist_analyses(db, business_id, facts_bundle, topic)
    spec_data = specialists.get(agent_key, {})

    facts_list = facts_bundle.get("facts", [])
    missing_list = facts_bundle.get("missing", [])
    agent_claims = spec_data.get("claims", [])
    agent_missing = spec_data.get("missing_information", [])

    # Extract clean text evidence
    evidence_items = [
        {"id": f.get("id"), "text": f.get("text"), "source": f.get("source")}
        for f in facts_list[:6]
    ]

    # Deterministic default analysis
    findings = [c.get("text") for c in agent_claims] if agent_claims else [
        f"Verified {len(facts_list)} operational data points across sales, products, and inventory."
    ]

    implications = []
    actions = []
    assumptions = [
        "All calculations derived strictly from verified business records scoped by business_id.",
        "Estimates reflect past transaction patterns and do not constitute professional financial or legal advice.",
    ]

    if aid == "business-analyst":
        exec_summary = (
            f"Based on your recent sales history, the Business Analyst has evaluated the revenue velocity, "
            f"product performance concentration, and period comparisons regarding '{task}'."
        )
        implications = [
            "Sales distribution highlights key revenue drivers that warrant continued inventory availability.",
            "Short-term velocity fluctuations require monitoring against monthly baseline targets.",
        ]
        actions = [
            "Focus reorder capital on the top-ranking revenue contributors.",
            "Review transaction counts weekly to confirm momentum continuity.",
        ]

    elif aid == "financial-advisor":
        exec_summary = (
            f"The Financial Advisor evaluated gross profit margins, recorded expenditures, and cost structure viability "
            f"for '{task}'."
        )
        implications = [
            "Gross margin stability is essential to maintain working capital headroom under changing supplier costs.",
            "Unrecorded product costs limit profitability visibility on select catalog items.",
        ]
        actions = [
            "Record exact unit purchase costs for all active SKUs to ensure complete margin visibility.",
            "Test small-scale pricing adjustments before rolling them out across high-volume categories.",
        ]

    elif aid == "marketing-advisor":
        exec_summary = (
            f"The Marketing Advisor evaluated recorded campaign expenditures, channel yields, and acquisition returns "
            f"for '{task}'."
        )
        implications = [
            "Marketing efficiency depends on attributing recorded transaction lift to specific campaign channels.",
            "Budget allocations produce maximum impact when concentrated on channels with verified historical returns.",
        ]
        actions = [
            "Reallocate marketing budget toward top-performing verified channels in controlled increments.",
            "Tag promotional campaigns with distinct discount codes to improve return measurement.",
        ]

    elif aid == "risk-manager":
        exec_summary = (
            f"The Risk Manager scanned for operational vulnerabilities, inventory stockout risks, data freshness, "
            f"and churn liabilities for '{task}'."
        )
        implications = [
            "Out-of-date records or missing stock thresholds reduce warning lead-times before inventory stockouts.",
            "Concentration of revenue in a single product creates vulnerability to supplier disruptions.",
        ]
        actions = [
            "Keep daily sales records up to date to maintain reliable forecasting and risk detection.",
            "Establish safety stock reorder triggers on leading SKUs to mitigate stockout liabilities.",
        ]

    else:  # strategy-optimiser
        exec_summary = (
            f"The Strategy Optimiser synthesized multi-agent perspectives and evaluated scenario trade-offs "
            f"for '{task}'."
        )
        options = spec_data.get("options", [])
        if options:
            top_opt = options[0]
            findings.insert(0, f"Ranked Strategy: {top_opt.get('title', 'Targeted Rebalancing')}")
            for t in top_opt.get("trade_offs", []):
                implications.append(t)
        implications.append("Executing strategy adjustments in phases minimizes downside capital exposure.")
        actions = [
            "Review simulated revenue impacts against your quarterly business goals.",
            "Implement recommended inventory and pricing adjustments in structured milestones.",
        ]

    # If LLM is available, consult GPT-5 mini with evidence grounding
    settings = get_settings()
    llm_meta = None
    if settings.llm_enabled and settings.openai_api_key:
        try:
            llm = LLMService(settings)
            res = llm.consult_agent(
                agent_key=agent_key,
                agent_name=cfg["name"],
                agent_role=cfg["role"],
                agent_purpose=cfg["purpose"],
                task=task,
                evidence_items=evidence_items,
            )
            if res and isinstance(res, dict):
                exec_summary = res.get("executive_summary", exec_summary)
                findings = res.get("key_findings", findings)
                implications = res.get("business_implications", implications)
                actions = res.get("recommended_actions", actions)
                assumptions = res.get("assumptions_and_limitations", assumptions)
                llm_meta = res.get("_llm_metadata")
        except Exception:
            # Deterministic fallback is always safe and guaranteed
            pass

    return {
        "agent_id": aid,
        "agent_name": cfg["name"],
        "role": cfg["role"],
        "purpose": cfg["purpose"],
        "icon": cfg["icon"],
        "task": task,
        "executive_summary": exec_summary,
        "key_findings": findings,
        "supporting_evidence": evidence_items,
        "business_implications": implications,
        "recommended_actions": actions,
        "assumptions_and_limitations": assumptions,
        "llm_metadata": llm_meta or {"model": "rules_fallback", "response_model": None, "usage": None, "estimated_cost_usd": 0.0},
    }

