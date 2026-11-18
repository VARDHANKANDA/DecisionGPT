"""Generate the pre-registered task specification (tasks/tasks_v1.json).

Run ONCE, before any model is executed. The output is frozen: this script refuses to overwrite an
existing spec (a changed spec would need a new version number and a logged deviation).

Parameters such as "which product" are chosen by the fixed rules below from the DATA ONLY — never from
any model output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from research.llm_evaluation.data_view import VIEW_RULES, build_view
from research.llm_evaluation.ground_truth import compute, spec_sha256

HERE = Path(__file__).resolve().parent
SPEC_PATH = HERE / "tasks" / "tasks_v1.json"

JAN = {"start": "2025-01-01", "end": "2025-01-31"}
FEB = {"start": "2025-02-01", "end": "2025-02-28"}
MAR = {"start": "2025-03-01", "end": "2025-03-31"}
ALL = {"start": "2025-01-01", "end": "2025-03-31"}

CURRENCY_TOL = {"type": "relative", "value": 0.005, "min_abs": 1.0,
                "rule": "correct if |answer - truth| <= max(0.5% of truth, INR 1)"}
EXACT_TOL = {"type": "absolute", "value": 0.0, "rule": "correct only if the integer equals the truth"}
PCT_TOL = {"type": "absolute_pp", "value": 0.5, "rule": "correct if |answer - truth| <= 0.5 percentage points"}
CAT_TOL = {"type": "normalized_first_mention", "rule": "the first candidate entity named in the answer must equal the truth"}


def _task(task_id, category, question, answer_type, defn, tol, required, window, *, track="primary",
          notes="", signed=False, k=None, candidates=None, definition_text=""):
    return {
        "task_id": task_id,
        "track": track,
        "category": category,
        "natural_language_question": question,
        "expected_answer_type": answer_type,
        "required_fields": required,
        "date_range": window,
        "aggregation_definition": definition_text,
        "ground_truth_definition": defn,
        "tolerance": tol,
        "signed_change": signed,
        "ranking_k": k,
        "candidate_entities": candidates,
        "source_dataset": "data/external/india_pos_register (evaluation data view, see view_rules)",
        "notes": notes,
    }


def build() -> dict:
    view, info = build_view()

    # --- parameter selection rules (data only) ------------------------------------------------
    rev_rank = view.groupby("product")["revenue"].sum().sort_values(ascending=False)
    qty_rank = view.groupby("product")["quantity"].sum().sort_values(ascending=False)
    p_rev1, p_rev2 = str(rev_rank.index[0]), str(rev_rank.index[1])
    qa, qb = sorted([str(qty_rank.index[2]), str(qty_rank.index[3])])  # alphabetical to avoid order bias
    selection_rules = {
        "C04_product": "2nd-ranked product by total revenue over 1 Jan-31 Mar 2025",
        "C05_products": "3rd- and 4th-ranked products by total units over 1 Jan-31 Mar 2025, listed alphabetically",
        "C06_product": "top-ranked product by total revenue over 1 Jan-31 Mar 2025",
        "selected": {"C04": p_rev2, "C05": [qa, qb], "C06": p_rev1},
    }

    sales_def = "sales = sum(quantity x unit price) of the recorded lines; GST treatment of the recorded rate is not known"
    T = [
        _task("A01", "aggregation", "What were my total sales in January 2025?", "currency",
              {"op": "sum_revenue", "params": JAN}, CURRENCY_TOL, ["date", "quantity", "unit_price"], JAN, definition_text=sales_def),
        _task("A02", "aggregation", "How much did I sell in February 2025 in total?", "currency",
              {"op": "sum_revenue", "params": FEB}, CURRENCY_TOL, ["date", "quantity", "unit_price"], FEB, definition_text=sales_def),
        _task("A03", "aggregation", "What were my total sales for the three months from January to March 2025?", "currency",
              {"op": "sum_revenue", "params": ALL}, CURRENCY_TOL, ["date", "quantity", "unit_price"], ALL, definition_text=sales_def),
        _task("A04", "aggregation", "How many units did I sell in March 2025?", "exact_number",
              {"op": "sum_quantity", "params": MAR}, EXACT_TOL, ["date", "quantity"], MAR, definition_text="units = sum of quantity"),
        _task("A05", "aggregation", "How many units did I sell in February 2025?", "exact_number",
              {"op": "sum_quantity", "params": FEB}, EXACT_TOL, ["date", "quantity"], FEB, definition_text="units = sum of quantity"),

        _task("B01", "time_comparison", "How did February 2025 sales compare with January? Tell me the percentage change.", "percentage",
              {"op": "pct_change_revenue", "params": {"new": FEB, "base": JAN}}, PCT_TOL, ["date", "quantity", "unit_price"], ALL,
              signed=True, definition_text="(Feb total - Jan total) / Jan total x 100"),
        _task("B02", "time_comparison", "By what percentage did sales change in March 2025 compared with February 2025?", "percentage",
              {"op": "pct_change_revenue", "params": {"new": MAR, "base": FEB}}, PCT_TOL, ["date", "quantity", "unit_price"], ALL,
              signed=True, definition_text="(Mar total - Feb total) / Feb total x 100"),
        _task("B03", "time_comparison", "Which day had the highest total sales between January and March 2025?", "date",
              {"op": "argmax_day_revenue", "params": ALL}, CAT_TOL, ["date", "quantity", "unit_price"], ALL,
              definition_text="calendar day with the largest daily total"),
        _task("B04", "time_comparison", "Which day had the lowest total sales between January and March 2025, counting only days that have any sales recorded?", "date",
              {"op": "argmin_day_revenue", "params": ALL}, CAT_TOL, ["date", "quantity", "unit_price"], ALL,
              definition_text="calendar day with the smallest daily total among days with >=1 sale"),
        _task("B05", "time_comparison", "How did sales from 1 to 15 March 2025 compare with 1 to 15 February 2025, as a percentage change?", "percentage",
              {"op": "pct_change_revenue", "params": {"new": {"start": "2025-03-01", "end": "2025-03-15"}, "base": {"start": "2025-02-01", "end": "2025-02-15"}}},
              PCT_TOL, ["date", "quantity", "unit_price"], ALL, signed=True, definition_text="(1-15 Mar total - 1-15 Feb total) / 1-15 Feb total x 100"),

        _task("C01", "product", "Which product sold the most units in February 2025?", "ranking",
              {"op": "top_products", "params": {**FEB, "metric": "quantity", "k": 1}}, CAT_TOL, ["date", "product", "quantity"], FEB,
              k=1, definition_text="product with the largest unit total"),
        _task("C02", "product", "What were my top 3 products by sales value from January to March 2025?", "ranking",
              {"op": "top_products", "params": {**ALL, "metric": "revenue", "k": 3}}, {"type": "ordered_list", "rule": "primary: exact ordered match of the 3 products"},
              ["date", "product", "quantity", "unit_price"], ALL, k=3, definition_text="products ranked by revenue"),
        _task("C03", "product", "Which three products sold the most units in March 2025?", "ranking",
              {"op": "top_products", "params": {**MAR, "metric": "quantity", "k": 3}}, {"type": "ordered_list", "rule": "primary: exact ordered match of the 3 products"},
              ["date", "product", "quantity"], MAR, k=3, definition_text="products ranked by units"),
        _task("C04", "product", f"How many units of {p_rev2} did I sell between January and March 2025?", "exact_number",
              {"op": "product_quantity", "params": {**ALL, "product": p_rev2}}, EXACT_TOL, ["date", "product", "quantity"], ALL,
              notes="product selected by rule C04_product", definition_text="sum of quantity for the named product"),
        _task("C05", "product", f"Which sold more units between January and March 2025, {qa} or {qb}?", "comparison",
              {"op": "compare_products_quantity", "params": {**ALL, "products": [qa, qb]}}, CAT_TOL, ["date", "product", "quantity"], ALL,
              candidates=[qa, qb], notes="products selected by rule C05_products", definition_text="larger unit total wins"),
        _task("C06", "product", f"What share of my total sales came from {p_rev1} from January to March 2025? Give a percentage.", "percentage",
              {"op": "product_revenue_share", "params": {**ALL, "product": p_rev1}}, PCT_TOL, ["date", "product", "quantity", "unit_price"], ALL,
              notes="product selected by rule C06_product", definition_text="product revenue / total revenue x 100"),

        _task("D01", "calendar", "Which day of the week brings in the most sales for me?", "categorical",
              {"op": "weekday_extreme", "params": {**ALL, "which": "max"}}, CAT_TOL, ["date", "quantity", "unit_price"], ALL,
              candidates=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
              definition_text="weekday with the largest total sales over the whole period"),
        _task("D02", "calendar", "Which day of the week is my weakest for sales?", "categorical",
              {"op": "weekday_extreme", "params": {**ALL, "which": "min"}}, CAT_TOL, ["date", "quantity", "unit_price"], ALL,
              candidates=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
              definition_text="weekday with the smallest total sales over the whole period"),
        _task("D03", "calendar", "How much did I sell on Sundays in total between January and March 2025?", "currency",
              {"op": "sum_revenue_weekday", "params": {**ALL, "weekday": "Sunday"}}, CURRENCY_TOL, ["date", "quantity", "unit_price"], ALL,
              definition_text=sales_def + "; summed over all Sundays"),
        _task("D04", "calendar", "On an average day that I had sales, how much did I sell between January and March 2025?", "currency",
              {"op": "mean_daily_revenue", "params": ALL}, CURRENCY_TOL, ["date", "quantity", "unit_price"], ALL,
              definition_text="mean of daily totals over days with at least one sale"),

        _task("F01", "exact_numeric", "How many different products did I sell in January 2025?", "exact_number",
              {"op": "distinct_products", "params": JAN}, EXACT_TOL, ["date", "product"], JAN, definition_text="count of distinct product names"),
        _task("F02", "exact_numeric", "On an average day that I had sales, how many units did I sell in March 2025?", "number",
              {"op": "mean_daily_quantity", "params": MAR}, {"type": "relative", "value": 0.005, "min_abs": 0.5, "rule": "correct if |answer - truth| <= max(0.5% of truth, 0.5)"},
              ["date", "quantity"], MAR, definition_text="mean of daily unit totals over days with at least one sale"),
        _task("F03", "exact_numeric", "What was the highest total sales I made on any single day between January and March 2025?", "currency",
              {"op": "max_day_revenue", "params": ALL}, CURRENCY_TOL, ["date", "quantity", "unit_price"], ALL,
              definition_text="maximum daily total over days in the window"),

        # Supplementary track: needs the GST column, which the production schema cannot hold.
        _task("E01", "gst", "How much of my sales between January and March 2025 came from items with 5% GST?", "currency",
              {"op": "gst_revenue", "params": {**ALL, "gst": 5.0}}, CURRENCY_TOL, ["date", "quantity", "unit_price", "gst_pct"], ALL,
              track="supplementary", definition_text=sales_def + "; lines whose recorded GST slab is 5%",
              notes="GST is not representable in DecisionGPT's canonical sales schema; the LLM baseline receives gst_pct only on this track."),
        _task("E02", "gst", "What percentage of my sales came from items with 18% GST?", "percentage",
              {"op": "gst_share", "params": {**ALL, "gst": 18.0}}, PCT_TOL, ["date", "quantity", "unit_price", "gst_pct"], ALL,
              track="supplementary", definition_text="revenue of 18% lines / total revenue x 100"),
        _task("E03", "gst", "What percentage of my sales came from items with 0% GST?", "percentage",
              {"op": "gst_share", "params": {**ALL, "gst": 0.0}}, PCT_TOL, ["date", "quantity", "unit_price", "gst_pct"], ALL,
              track="supplementary", definition_text="revenue of 0% lines / total revenue x 100"),
        _task("E04", "gst", "Which GST rate brought in the most sales between January and March 2025?", "categorical",
              {"op": "gst_argmax", "params": ALL}, CAT_TOL, ["date", "quantity", "unit_price", "gst_pct"], ALL,
              track="supplementary", candidates=["0%", "5%", "18%", "28%", "40%", "121%"], definition_text="GST slab with the largest total sales"),
    ]

    spec = {
        "spec_version": "tasks_v1",
        "preregistration": ("Frozen BEFORE any model was run. Tolerances, scoring rules, task wording and repeat counts must not change after "
                            "results are seen; any change requires a new spec version and a logged deviation."),
        "research_question": ("How effectively does the actual DecisionGPT system answer objective business-analytics questions over real "
                              "Indian POS data, compared with an LLM given direct read-only access to the same data?"),
        "dataset": {
            "path": "data/external/india_pos_register/",
            "description": "Indian POS retail register, 1 Jan-31 Mar 2025",
            "provenance_limitation": "Appears to be real Indian POS data from its structure and content; uploader/store provenance is NOT independently verified.",
            "license": "CC BY-NC-SA 4.0 (as recorded in the repository)",
            "representativeness": "NOT representative of Indian SMEs or Indian retail generally.",
        },
        "view_rules": VIEW_RULES,
        "selection_rules": selection_rules,
        "repeats_per_task": 5,
        "conditions": {
            "primary": "DecisionGPT with the evaluation clock fixed at 2025-03-31 (emulates a user asking right after the data period; production code unmodified)",
            "secondary": "DecisionGPT with the real clock (a user asking about stale data); 'realclock'",
        },
        "systems": {
            "decisiongpt": "POST /businesses/{id}/chat on a business created and filled through the production upload endpoints; the configured LLM only rephrases a computed template answer (production behaviour).",
            "llm_code_baseline": ("Protocol B2: the same configured LLM client, given the schema, sample rows and read-only access to the same data view through a sandboxed "
                                  "pandas snippet it writes itself (<=1 repair attempt), then phrases the executed result. No DecisionGPT routing/analytics."),
        },
        "information_given": {
            "decisiongpt": "date, product, quantity, unit_price (and computed revenue) for every view line, via the production ingestion path. No GST column (cannot be stored).",
            "llm_code_baseline": "the same four fields plus computed revenue as a DataFrame; plus gst_pct ONLY for supplementary-track tasks. Never the ground truth, task metadata or tolerances.",
        },
        "scoring": {
            "numbers": "primary = the ground truth appears among the numbers in the answer within tolerance (dates/years removed first; lakh/crore/K/M multipliers understood); secondary = first number only; n_numbers recorded",
            "signed_change": "a signed change is correct only if the magnitude is within tolerance AND the direction (up/down) matches; missing direction -> partially_correct",
            "entities": "first candidate entity named in the answer (products: names present in the view; weekdays; dates; GST slabs); secondary lenient metric: truth mentioned anywhere",
            "ranking": "primary = exact ordered top-k; secondary = top-1 correct and overlap@k",
            "refusal": "answers that decline or say there is not enough information are 'unable_to_answer' (checked by pattern list in scoring.py)",
            "unsupported_claim": "NOT assessed automatically; raw outputs preserved for human audit",
            "judge": "no LLM judge is used",
        },
        "tasks": T,
    }

    # Every defined task must be computable and unambiguous on the view (fails loudly otherwise).
    for t in T:
        compute(t["ground_truth_definition"], view)
    return spec


def main() -> int:
    if SPEC_PATH.exists():
        print(f"REFUSING to overwrite frozen spec {SPEC_PATH} (sha256 {spec_sha256(json.loads(SPEC_PATH.read_text(encoding='utf-8')))[:16]}...)")
        return 2
    spec = build()
    SPEC_PATH.parent.mkdir(parents=True, exist_ok=True)
    SPEC_PATH.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {SPEC_PATH}  tasks={len(spec['tasks'])}  sha256={spec_sha256(spec)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
