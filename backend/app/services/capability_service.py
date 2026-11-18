"""Data-aware capability detection (docs/INDIAN_SME_DATA_ARCHITECTURE.md §24).

Given what data an SME has actually provided, report which DecisionGPT
features are available and, for the rest, exactly what upload unlocks them.
This is what lets the platform say

    "Marketing ROI cannot be assessed because campaign spend data was not
     provided."

instead of fabricating a value.
"""
from sqlalchemy.orm import Session

from app.services.data_ingestion_service import get_data_summary

# feature key -> (label, [(summary_field, min_count, human_requirement), ...])
# every listed requirement must be met for the feature to be enabled.
_FEATURE_RULES: list[tuple[str, str, list[tuple[str, int, str]]]] = [
    ("sales_analysis", "Sales analysis",
     [("sales", 1, "sales data")]),
    ("forecasting", "Demand / sales forecasting",
     [("sales", 30, "at least ~30 rows of dated sales data")]),
    ("pricing_simulation", "Pricing simulation",
     [("sales", 30, "dated sales with unit price + quantity")]),
    ("profit_analysis", "Profit analysis",
     [("sales", 1, "sales data (with cost, from products or finance)")]),
    ("customer_analytics", "Customer analytics / segmentation",
     [("customers", 5, "customer records")]),
    ("churn_analysis", "Churn / retention analysis",
     [("customers", 20, "customer records with purchase history")]),
    ("marketing_optimization", "Marketing optimization",
     [("marketing_campaigns", 1, "marketing campaign data (spend + outcomes)")]),
    ("inventory_optimization", "Inventory optimization",
     [("inventory_records", 1, "inventory / stock movement data")]),
    ("finance_analysis", "Financial health analysis",
     [("finance_records", 1, "finance data (revenue, costs, cash)")]),
    ("business_context_conditioning", "Region / industry context conditioning",
     [("business_profile_set", 1, "business profile (state, industry, enterprise type)")]),
]


def get_capabilities(db: Session, business_id: str) -> dict:
    summary = get_data_summary(db, business_id)
    capabilities = []
    for key, label, rules in _FEATURE_RULES:
        missing: list[str] = []
        for field_name, minimum, requirement in rules:
            value = summary.get(field_name, 0)
            have = int(value) if not isinstance(value, bool) else (1 if value else 0)
            if have < minimum:
                missing.append(requirement)
        enabled = not missing
        if enabled:
            reason = "Available."
        else:
            reason = "Upload " + "; ".join(missing) + " to enable."
        capabilities.append(
            {"feature": label, "enabled": enabled, "reason": reason, "requires": missing}
        )
    return {"business_id": business_id, "data_summary": summary, "capabilities": capabilities}
