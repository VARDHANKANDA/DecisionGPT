"""Single source of truth for the Dataset Registry category label
(docs/INDIAN_SME_DATA_ARCHITECTURE.md §19).

    INDIA_REAL_BUSINESS        real Indian business/transaction data
    INDIA_PUBLIC_CONTEXT       Indian public context (festivals, macro, ...)
    INDIA_AGRICULTURAL_PRICE   AGMARKNET agri-commodity price series
    SYNTHETIC_CONTROLLED       bundled synthetic research datasets
    RETIRED_NON_INDIAN         archived non-Indian benchmarks (not active)
    EXTERNAL_BENCHMARK         other external benchmark (fallback)
    UNCLASSIFIED               could not be determined
"""

INDIA_REAL_BUSINESS = "INDIA_REAL_BUSINESS"
INDIA_REAL_CUSTOMER = "INDIA_REAL_CUSTOMER"
INDIA_PUBLIC_CONTEXT = "INDIA_PUBLIC_CONTEXT"
INDIA_AGRICULTURAL_PRICE = "INDIA_AGRICULTURAL_PRICE"
SYNTHETIC_INDIAN_CONTEXT = "SYNTHETIC_INDIAN_CONTEXT"
SYNTHETIC_CONTROLLED = "SYNTHETIC_CONTROLLED"
RETIRED_NON_INDIAN = "RETIRED_NON_INDIAN"
EXTERNAL_BENCHMARK = "EXTERNAL_BENCHMARK"
UNCLASSIFIED = "UNCLASSIFIED"


def classify(*, source: str | None = None, evidence_level: str | None = None,
             dataset_id: str | None = None, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    blob = " ".join(str(x) for x in (source, evidence_level, dataset_id) if x).lower()

    if "retired_non_indian" in blob:
        return RETIRED_NON_INDIAN
    if "synthetic_indian_context" in blob:
        return SYNTHETIC_INDIAN_CONTEXT
    if "synthetic" in blob or "simulated" in blob:
        return SYNTHETIC_INDIAN_CONTEXT if "india" in blob else SYNTHETIC_CONTROLLED
    if "agmarknet" in blob or "agri-commodity" in blob or "agricultural_price" in blob:
        return INDIA_AGRICULTURAL_PRICE
    if "public_context" in blob or "festival" in blob or "macro" in blob or "repo rate" in blob:
        return INDIA_PUBLIC_CONTEXT
    if "external benchmark" in blob and "india" in blob:
        if "customer" in blob:
            return INDIA_REAL_CUSTOMER
        return INDIA_REAL_BUSINESS
    if "external benchmark" in blob:
        return EXTERNAL_BENCHMARK
    return UNCLASSIFIED
