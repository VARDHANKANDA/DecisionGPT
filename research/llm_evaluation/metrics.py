"""Aggregate per-attempt results into metrics. Quality and efficiency are reported separately; there is NO combined score.

Every number comes from recorded attempts. A quantity the provider/system did not return is reported as None
(rendered "not available"), never as 0 and never estimated.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from research.llm_evaluation.attempt_accounting import PATH_GROUPS
from research.llm_evaluation.scoring import OUTCOMES

# outcomes added by attempt accounting (the scorer itself is unchanged)
ALL_OUTCOMES = OUTCOMES + ("legacy_fallback", "unsupported_by_design")
MIN_N_FOR_P95 = 20  # a 95th percentile is not reported from fewer observations


def _pct(x: float | None) -> float | None:
    return None if x is None else round(100 * x, 2)


def _quantile(vals: list[float], q: float, min_n: int = 1) -> float | None:
    if len(vals) < min_n:
        return None
    s = sorted(vals)
    i = min(len(s) - 1, max(0, round(q * (len(s) - 1))))
    return round(s[i], 4)


def _quality_core(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n_attempts": 0}
    correct = sum(1 for r in rows if r["score"]["correct"])
    first_ok = [r["score"].get("first_number_correct") for r in rows if "first_number_correct" in r["score"]]
    lenient = [r["score"].get("truth_mentioned") for r in rows if "truth_mentioned" in r["score"]]
    outcomes = Counter(r["score"]["outcome"] for r in rows)
    abs_first = [r["score"]["abs_error_first"] for r in rows if r["score"].get("abs_error_first") is not None]
    abs_near = [r["score"]["abs_error_nearest"] for r in rows if r["score"].get("abs_error_nearest") is not None]
    rel_first = [r["score"]["rel_error_first"] for r in rows if r["score"].get("rel_error_first") is not None]
    rel_near = [r["score"]["rel_error_nearest"] for r in rows if r["score"].get("rel_error_nearest") is not None]
    rank_rows = [r for r in rows if r["task"]["expected_answer_type"] == "ranking"]

    # repeat consistency: per task, did every repeat get the same correct/incorrect verdict?
    by_task: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        by_task[r["task_id"]].append(bool(r["score"]["correct"]))
    consistent = sum(1 for v in by_task.values() if len(set(v)) == 1)

    return {
        "n_attempts": n,
        "n_tasks": len(by_task),
        "accuracy_primary_pct": _pct(correct / n),
        "n_correct": correct,
        "accuracy_first_number_pct": _pct(sum(bool(x) for x in first_ok) / len(first_ok)) if first_ok else None,
        "truth_mentioned_lenient_pct": _pct(sum(bool(x) for x in lenient) / len(lenient)) if lenient else None,
        "outcomes": {k: outcomes.get(k, 0) for k in ALL_OUTCOMES},
        "failure_rates_pct": {
            "unable_to_answer": _pct(outcomes.get("unable_to_answer", 0) / n),
            "invalid_answer": _pct(sum(1 for r in rows if r["score"].get("invalid_answer")) / n),
            "tool_or_system_failure": _pct(outcomes.get("tool_data_access_failure", 0) / n),
        },
        "numeric_error": {
            "n_numeric_attempts": len(abs_first),
            "mean_abs_error_first_number": round(statistics.fmean(abs_first), 4) if abs_first else None,
            "median_abs_error_first_number": round(statistics.median(abs_first), 4) if abs_first else None,
            "mean_abs_error_nearest_number": round(statistics.fmean(abs_near), 4) if abs_near else None,
            "median_rel_error_first_number": round(statistics.median(rel_first), 6) if rel_first else None,
            "median_rel_error_nearest_number": round(statistics.median(rel_near), 6) if rel_near else None,
            "note": "absolute errors mix units (rupees, units, percentage points) - read per category, not overall",
        },
        "ranking": {
            "n_attempts": len(rank_rows),
            "top1_correct_pct": _pct(sum(bool(r["score"].get("top1_correct")) for r in rank_rows) / len(rank_rows)) if rank_rows else None,
            "mean_overlap_at_k": round(statistics.fmean(r["score"].get("overlap_at_k", 0.0) for r in rank_rows), 4) if rank_rows else None,
        },
        "repeat_consistency": {"tasks_with_identical_verdict_across_repeats": consistent, "of_tasks": len(by_task)},
    }


def path_accounting(rows: list[dict]) -> dict:
    """Where the answers came from. Only meaningful for DecisionGPT rows; a fallback is NEVER an LLM-path success."""
    n = len(rows)
    groups = Counter(r.get("path_group") for r in rows)
    classes = Counter(r.get("path_class") for r in rows)
    cats = Counter(r.get("failure_category") for r in rows if r.get("failure_category"))
    llm_rows = [r for r in rows if r.get("path_group") == "llm_path"]
    return {
        "n_attempts": n,
        "path_groups": {g: groups.get(g, 0) for g in PATH_GROUPS},
        "path_classes": dict(sorted(classes.items(), key=lambda kv: str(kv[0]))),
        "failure_categories": dict(sorted(cats.items())),
        "llm_path_success_pct_of_all_attempts": _pct(sum(1 for r in rows if r.get("counts_as_llm_path_success")) / n) if n else None,
        "accuracy_among_attempts_answered_by_llm_path_pct": _pct(sum(1 for r in llm_rows if r["score"]["correct"]) / len(llm_rows)) if llm_rows else None,
        "n_answered_by_llm_path": len(llm_rows),
        "fallback_rate_pct": _pct(groups.get("legacy_fallback", 0) / n) if n else None,
        "unsupported_rate_pct": _pct(groups.get("unsupported", 0) / n) if n else None,
        "infrastructure_failure_rate_pct": _pct(groups.get("infrastructure_failure", 0) / n) if n else None,
        "legacy_fallback_attempts_whose_text_would_have_scored_correct": sum(
            1 for r in rows if r.get("path_group") == "legacy_fallback" and (r.get("score_unadjusted") or {}).get("correct")),
        "note": "a legacy-router answer is never counted as an LLM-path success, even if its text happens to match the truth",
    }


def quality(rows: list[dict]) -> dict:
    """Quality over the attempts that can be evaluated. Supplementary-track refusals (excluded_from_accuracy) are counted but are
    neither successes nor failures. Fallback / infrastructure attempts stay in the denominator as NOT correct."""
    if not rows:
        return {"n_attempts": 0}
    evaluable = [r for r in rows if not r.get("excluded_from_accuracy")]
    q = _quality_core(evaluable)
    q["n_attempts_total"] = len(rows)
    q["n_excluded_unsupported_by_design"] = len(rows) - len(evaluable)
    if any("path_group" in r for r in rows):
        q["path_accounting"] = path_accounting(rows)
    return q


def _role_stats(calls: list[dict]) -> dict:
    n = len(calls)
    lat = [c["latency_s"] for c in calls if isinstance(c.get("latency_s"), (int, float))]
    att = [c.get("attempts") for c in calls]
    with_usage = [c for c in calls if isinstance(c.get("input_tokens"), (int, float)) and isinstance(c.get("output_tokens"), (int, float))]
    in_t, out_t = [c["input_tokens"] for c in with_usage], [c["output_tokens"] for c in with_usage]
    return {
        "n_calls": n,
        "n_failed_calls": sum(1 for c in calls if not c.get("ok")),
        "n_calls_with_retries": sum(1 for a in att if isinstance(a, int) and a > 1),
        "retry_attempts_total": sum(a - 1 for a in att if isinstance(a, int) and a > 1),
        "n_calls_attempts_unknown": sum(1 for a in att if not isinstance(a, int)),
        "latency_s_including_retries": {"n": len(lat), "mean": round(statistics.fmean(lat), 4) if lat else None, "median": _quantile(lat, 0.5),
                                        "p95": _quantile(lat, 0.95, MIN_N_FOR_P95), "max": round(max(lat), 4) if lat else None,
                                        "p95_note": f"reported only with at least {MIN_N_FOR_P95} observations"},
        "n_calls_with_provider_usage": len(with_usage),
        "n_calls_without_usage": n - len(with_usage),
        "input_tokens_total": sum(in_t) if with_usage else None,
        "output_tokens_total": sum(out_t) if with_usage else None,
        "total_tokens": (sum(in_t) + sum(out_t)) if with_usage else None,
        "token_note": "totals cover the calls for which the provider returned usage (failed calls return none); nothing is estimated. "
                      "Totals are complete only when n_calls_without_usage = 0",
    }


def efficiency(rows: list[dict], pricing_cost: list[float | None] | None = None) -> dict:
    lat = [r["latency_s"] for r in rows if isinstance(r.get("latency_s"), (int, float))]
    n_calls = [r["llm_summary"].get("n_calls", 0) for r in rows]
    costs = [r.get("cost_usd") for r in rows]
    all_calls = [c for r in rows for c in (r.get("llm_calls") or [])]
    if all_calls:  # per-call records are authoritative: failed calls return no usage, which must not erase the totals of the calls that did
        used = [c for c in all_calls if isinstance(c.get("input_tokens"), (int, float)) and isinstance(c.get("output_tokens"), (int, float))]
        tokens = {
            "input_total": sum(c["input_tokens"] for c in used) if used else None,
            "output_total": sum(c["output_tokens"] for c in used) if used else None,
            "total": sum(c["input_tokens"] + c["output_tokens"] for c in used) if used else None,
            "calls_total": len(all_calls), "calls_with_provider_usage": len(used), "calls_without_usage": len(all_calls) - len(used),
            "complete": len(used) == len(all_calls),
            "note": "sum over calls for which the provider returned usage (failed calls return none); nothing is estimated",
        }
    else:
        in_tok = [r["llm_summary"].get("input_tokens") for r in rows]
        out_tok = [r["llm_summary"].get("output_tokens") for r in rows]
        full_tok = all(isinstance(v, (int, float)) for v in in_tok + out_tok) and bool(rows)
        tokens = {
            "input_total": sum(in_tok) if full_tok else None,
            "output_total": sum(out_tok) if full_tok else None,
            "attempts_with_complete_token_counts": sum(1 for a_, b_ in zip(in_tok, out_tok) if isinstance(a_, (int, float)) and isinstance(b_, (int, float))),
            "note": "None = the provider did not return usage for every call; nothing is estimated",
        }
    priced = [c for c in costs if isinstance(c, (int, float))]
    return {
        "n_attempts": len(rows),
        "latency_end_to_end_s": {"n": len(lat), "mean": round(statistics.fmean(lat), 4) if lat else None, "median": _quantile(lat, 0.5),
                                 "p95": _quantile(lat, 0.95, MIN_N_FOR_P95), "max": round(max(lat), 4) if lat else None,
                                 "p95_note": f"reported only with at least {MIN_N_FOR_P95} observations"},
        "llm_calls_per_attempt_mean": round(statistics.fmean(n_calls), 3) if n_calls else None,
        "llm_calls_total": sum(n_calls),
        "tokens": tokens,
        "cost_usd_total": round(sum(priced), 6) if priced else None,
        "cost_attempts_priced": len(priced),
        "cost_attempts_not_priced": len(costs) - len(priced),
        "cost_is_lower_bound": bool(len(priced) != len(costs) or any(not c.get("ok") for c in all_calls)),
        "by_llm_call_role": {role: _role_stats(cs) for role, cs in sorted(_calls_by_role(rows).items())},
        "llm_calls_per_attempt_by_role": {role: round(len(cs) / len(rows), 3) for role, cs in sorted(_calls_by_role(rows).items())} if rows else {},
        "engine_latency_s": _stage_stats([r.get("stages", {}).get("engine_s") for r in rows]),
        "cost_note": "Only from provider-reported token usage and a verified price for the exact model (pricing.json); failed calls return no usage and are excluded, so "
                     "a total with failures is a lower bound; None when no price is supplied. Never estimated.",
    }


def _calls_by_role(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        for c in r.get("llm_calls") or []:
            out[c.get("role") or "other"].append(c)
    return out


def _stage_stats(vals: list) -> dict | None:
    v = [x for x in vals if isinstance(x, (int, float))]
    if not v:
        return None
    return {"n": len(v), "mean": round(statistics.fmean(v), 4), "median": _quantile(v, 0.5), "p95": _quantile(v, 0.95, MIN_N_FOR_P95), "max": round(max(v), 4)}


def by_category(rows: list[dict]) -> dict:
    cats: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        cats[r["task"]["category"]].append(r)
    return {c: quality(v) for c, v in sorted(cats.items())}


def summarize(rows: list[dict]) -> dict:
    """rows -> {system|condition -> {track -> {overall, by_category, efficiency}}}"""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[f"{r['system']}|{r['condition']}"].append(r)
    out = {}
    for key, rs in sorted(groups.items()):
        per_track = {}
        for track in ("primary", "supplementary"):
            tr = [r for r in rs if r["task"]["track"] == track]
            if tr:
                per_track[track] = {"quality": quality(tr), "by_category": by_category(tr), "efficiency": efficiency(tr)}
        out[key] = per_track
    return out
