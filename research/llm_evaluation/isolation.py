"""Ground-truth isolation checks for the requests the evaluated provider (OpenAI) receives.

The interpreter request must carry ONLY: the model name, the fixed classification instructions and schema (byte-identical to the
pre-registered set) and the frozen question text verbatim inside a fixed wrapper. Never an expected answer, the pandas ground truth,
a score, a tolerance or a task id. The explainer request carries the fixed instructions, the frozen question and the facts the
production engine computed from the data (those are the system's own output, not ground truth).

``check_interpreter_payload`` is a WHITELIST check (exact keys, exact instructions, exact schema, question verbatim);
``forbidden_fragments`` adds a belt-and-braces scan for the numeric ground-truth values and evaluation vocabulary.
"""
from __future__ import annotations

import json

INTERPRETER_KEYS = {"model", "instructions", "input", "store", "max_output_tokens", "text"}
EXPLAINER_KEYS = {"model", "instructions", "input", "store", "max_output_tokens"}
EVAL_WORDS = ("ground_truth", "ground truth", "expected_answer", "expected answer", "tolerance", "scorer", "task_id", "truth", "pandas")


def _indian(n: int) -> str:
    s = str(abs(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def forbidden_fragments(ground_truth: dict) -> list[str]:
    """String renderings of every numeric ground-truth value large enough to be unmistakable (>= 1000), in the formats an answer would use."""
    out: set[str] = set()
    for tid, rec in (ground_truth.get("answers") or {}).items():
        v = rec.get("answer")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or abs(v) < 1000:
            continue
        whole = int(round(abs(v)))
        out.update({str(whole), f"{whole:,}", _indian(whole), f"{abs(v):.2f}", f"{abs(v):.2f}".rstrip("0").rstrip(".")})
    return sorted(f for f in out if len(f) >= 4)


def expected_questions_payload() -> dict:
    """The pre-registered classification question set (the description of the fields the model fills in)."""
    from app.services.analytics_interpreter_service import QUESTIONS

    return {k: q.payload() for k, q in QUESTIONS.items()}


def _wrapped(question: str) -> str:
    return f"<text>\n{question}\n</text>"


def check_interpreter_payload(payload: dict, frozen_questions: set[str], expected_questions: dict | None = None, forbidden: list[str] | None = None) -> list[str]:
    """Return the list of violations (empty = the request carries nothing but the fixed instructions/schema and one frozen question)."""
    from app.services.analytics_interpreter_service import QUESTIONS
    from app.services.openai_client import SYSTEM_DECIDE, build_schema

    bad: list[str] = []
    if set(payload) - {"reasoning"} != INTERPRETER_KEYS:
        bad.append(f"unexpected payload keys {sorted((set(payload) - {'reasoning'}) ^ INTERPRETER_KEYS)}")
    if "reasoning" in payload and payload["reasoning"] != {"effort": "low"}:
        bad.append("reasoning setting differs from the pre-registered fixed value")
    if payload.get("instructions") != SYSTEM_DECIDE:
        bad.append("instructions differ from the pre-registered classification instructions")
    try:
        schema = payload["text"]["format"]["schema"]
    except (KeyError, TypeError):
        schema = None
    if schema != build_schema(QUESTIONS):
        bad.append("response schema differs from the pre-registered classification schema")
    inp = payload.get("input")
    question = None
    if isinstance(inp, str) and inp.startswith("<text>\n") and inp.endswith("\n</text>"):
        question = inp[len("<text>\n"):-len("\n</text>")]
    if question is None or question not in frozen_questions:
        bad.append("input is not a frozen task question verbatim in the fixed wrapper")
    blob = json.dumps(payload, ensure_ascii=False)
    for frag in forbidden or []:
        if frag in blob:
            bad.append(f"contains ground-truth value fragment {frag!r}")
            break
    low = blob.lower()
    stripped = low.replace(json.dumps(payload.get("text"), ensure_ascii=False).lower(), "").replace(str(payload.get("instructions")).lower(), "")
    stripped = stripped.replace(str(question).lower(), "")
    for w in EVAL_WORDS:
        if w in stripped:
            bad.append(f"contains evaluation vocabulary {w!r}")
            break
    return bad


def check_explainer_payload(payload: dict, frozen_questions: set[str]) -> list[str]:
    from app.services.openai_client import SYSTEM_EXPLAIN

    bad: list[str] = []
    if set(payload) - {"reasoning"} != EXPLAINER_KEYS:
        bad.append(f"unexpected payload keys {sorted((set(payload) - {'reasoning'}) ^ EXPLAINER_KEYS)}")
    if "reasoning" in payload and payload["reasoning"] != {"effort": "low"}:
        bad.append("reasoning setting differs from the pre-registered fixed value")
    if payload.get("instructions") != SYSTEM_EXPLAIN:
        bad.append("instructions differ from the pre-registered explanation instructions")
    inp = payload.get("input")
    first = inp.split("\n", 1)[0] if isinstance(inp, str) else ""
    if not first.startswith("Question: ") or first[len("Question: "):] not in {q.strip()[:500] for q in frozen_questions}:
        bad.append("explainer input does not begin with a frozen question verbatim")
    return bad


def audit_requests(requests: list[dict], frozen_questions: set[str], expected_questions: dict | None, forbidden: list[str]) -> dict:
    """Run the whitelist checks over recorded requests (the mock provider keeps them in memory)."""
    interp = [r for r in requests if r.get("role") == "interpreter"]
    expl = [r for r in requests if r.get("role") == "explainer"]
    violations = []
    for r in interp:
        v = check_interpreter_payload(r["body"], frozen_questions, expected_questions, forbidden)
        if v:
            violations.append({"task": r.get("task"), "ordinal": r.get("ordinal"), "violations": v})
    for r in expl:
        v = check_explainer_payload(r["body"], frozen_questions)
        if v:
            violations.append({"task": r.get("task"), "ordinal": r.get("ordinal"), "violations": v})
    return {"interpreter_requests_checked": len(interp), "interpreter_violations": violations, "explainer_requests_seen": len(expl),
            "explainer_note": "the explainer receives only the frozen question and the facts the production engine computed; its text is shown only if it passes the number / causal-claim guard",
            "forbidden_fragment_count": len(forbidden)}
