"""Pre-registered prompts for the LLM + data-tool baseline (protocol B2). Versioned; never edited after a run starts."""

PROMPT_VERSION = "b2-prompts-1"

CODE_SYSTEM = (
    "You are a careful data analyst. A small shop's sales register is available as a pandas DataFrame named `df`. "
    "Write a short Python snippet (pandas/numpy only) that computes the answer to the owner's question from `df`, "
    "and assigns the answer to a variable named `result`. Do not read or write files. Output ONLY the code in a single "
    "```python block, no explanation."
)

ANSWER_SYSTEM = (
    "You are a business analytics assistant for a small-shop owner. You are given the owner's question and the exact result of a "
    "calculation run on their sales register. Answer the question in 1-3 plain sentences using ONLY that result. Keep every number "
    "exactly as given (you may add Indian digit grouping or the rupee sign). If the calculation failed or the result does not answer "
    "the question, say so plainly instead of guessing."
)

_COLUMN_DESC = {
    "date": "sale date (datetime64)",
    "product": "product name as written in the register (string, upper-case abbreviations)",
    "quantity": "units sold (integer)",
    "unit_price": "price per unit in rupees (float)",
    "revenue": "quantity * unit_price in rupees (float) - 'sales' means the sum of this column",
    "gst_pct": "GST rate recorded for the line, in percent (float)",
}


def schema_description(columns: list[str], date_min: str, date_max: str, sample_csv: str) -> str:
    lines = "\n".join(f"- {c}: {_COLUMN_DESC[c]}" for c in columns)
    return (f"DataFrame `df` columns:\n{lines}\nThe register covers {date_min} to {date_max}. Weekday names come from `date`.\n"
            f"First rows:\n{sample_csv}")


def code_user(schema: str, question: str) -> str:
    return f"{schema}\n\nOwner's question: {question}"


def repair_user(schema: str, question: str, code: str, error: str) -> str:
    return (f"{schema}\n\nOwner's question: {question}\n\nYour previous snippet:\n```python\n{code}\n```\n"
            f"It failed with: {error}\nReturn a corrected snippet in a single ```python block.")


def answer_user(question: str, result: str) -> str:
    return f"Owner's question: {question}\n\nCalculation result:\n{result}"
