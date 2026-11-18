"""Classify every DecisionGPT attempt by WHICH path produced its answer, so a fallback is never counted as an LLM success.

Groups (``path_group``):
  llm_path               the LLM analytics path produced the answer (interpreter -> validated request -> engine)
  unsupported            the LLM path declined as unsupported (the correct behaviour for the GST supplementary track)
  legacy_fallback        the answer came from the legacy fixed-intent router (provider failure, invalid model output, or the
                         interpreter handing the question over). NOT an LLM answer: it is scored as not-correct for the LLM metrics
                         even if the router happened to produce the right text, and the would-be verdict is kept as ``score_unadjusted``.
  infrastructure_failure the request itself failed (HTTP error / adapter exception)

Supplementary-track (GST) refusals are ``excluded_from_accuracy``: neither a model failure nor a success.
"""
from __future__ import annotations

from typing import Any

PATH_GROUPS = ("llm_path", "unsupported", "legacy_fallback", "infrastructure_failure")

_FALLBACK_CATEGORY = {
    "timeout": "provider_failure",
    "provider_error": "provider_failure",
    "malformed_output": "invalid_output",
    "invalid_request": "invalid_output",
    "low_confidence": "low_confidence",
    "authentication_failed": "provider_failure",
    "rate_limited": "provider_failure",
    "overloaded": "provider_failure",
    "interpreter_routed_legacy": "interpreter_routed_legacy",
    "question_too_long": "question_too_long",
    "not_configured": "llm_path_not_active",
    "disabled": "llm_path_not_active",
}


def classify(system: str, track: str, out: dict[str, Any], audit: dict[str, Any] | None) -> dict[str, Any]:
    if system != "decisiongpt":
        return {"path_group": "baseline", "path_class": "baseline", "failure_category": None, "excluded_from_accuracy": False}
    if out.get("error") or out.get("path") is None:
        return {"path_group": "infrastructure_failure", "path_class": "infrastructure_failure",
                "failure_category": str(out.get("error") or "no_path")[:80], "excluded_from_accuracy": False}
    intent, path = out.get("intent"), out.get("path")
    if path == "llm_analytics":
        if intent == "analytics_unsupported":
            return {"path_group": "unsupported", "path_class": "llm_unsupported", "failure_category": None, "excluded_from_accuracy": track == "supplementary"}
        if intent == "analytics_clarification":
            return {"path_group": "llm_path", "path_class": "llm_clarification", "failure_category": None, "excluded_from_accuracy": False}
        if intent == "analytics_query" and out.get("sufficient_evidence") is False:
            return {"path_group": "llm_path", "path_class": "llm_no_data", "failure_category": None, "excluded_from_accuracy": False}
        return {"path_group": "llm_path", "path_class": "llm_answered", "failure_category": None, "excluded_from_accuracy": False}
    reason = (audit or {}).get("fallback_reason")
    return {"path_group": "legacy_fallback", "path_class": "legacy_fallback",
            "failure_category": _FALLBACK_CATEGORY.get(reason or "", reason or "unknown"), "excluded_from_accuracy": False}


def apply(row: dict[str, Any], acct: dict[str, Any]) -> dict[str, Any]:
    """Merge the classification into a scored result row and adjust the verdict where the answer was not an LLM-path answer."""
    row.update(acct)
    score = row["score"]
    if acct["path_group"] in ("legacy_fallback", "infrastructure_failure"):
        row["score_unadjusted"] = dict(score)
        score["correct"] = False
        if acct["path_group"] == "legacy_fallback":
            score["outcome"] = "legacy_fallback"
            score["detail"] = f"answered by the legacy router ({acct['failure_category']}); not an LLM-path answer"
    elif acct["excluded_from_accuracy"]:
        row["score_unadjusted"] = dict(score)
        score["correct"] = False
        score["outcome"] = "unsupported_by_design"
        score["detail"] = "supplementary GST track: production data has no GST field; refusal is the correct behaviour (excluded from accuracy)"
    row["counts_as_llm_path_success"] = bool(score["correct"]) and acct["path_group"] == "llm_path"
    return row
