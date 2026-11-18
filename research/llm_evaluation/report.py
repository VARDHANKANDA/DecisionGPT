"""Human-readable report generator. Reads ONLY recorded run files; invents nothing.

BLOCKED / smoke / not-run records produce a status page, never a results table. MOCK runs (wire-level fake provider) produce a
full-format report whose every page carries a "MOCK INFRASTRUCTURE VALIDATION - NOT RESEARCH RESULTS" banner.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS_DIR = HERE / "reports"

MOCK_BANNER = "**MOCK INFRASTRUCTURE VALIDATION - NOT RESEARCH RESULTS.** A wire-level fake provider replaced the network; every token count, model id, price and injected failure below is a MOCK value used only to exercise the measurement and accounting plumbing. Nothing here measures any model."

# What is - and is not - being measured. Reports must carry this verbatim.
METRIC_BOUNDARY = (
    "The deterministic query engine is the numerical authority. The evaluated AI component is the typed-decision classification of the "
    "natural-language question (OpenAI: schema-constrained labels only); periods, products and limits are extracted by deterministic code, "
    "and every answer sentence is a deterministic template (no model writes text)."
)
NOT_EVALUATED = (
    "This experiment evaluates the ability of the model's classification, together with deterministic extraction, to interpret natural-language business "
    "questions into valid structured analytics requests that lead to deterministic, correct calculations. It does NOT evaluate LLM arithmetic ability, causal reasoning, profit prediction, "
    "churn prediction, pricing optimisation, marketing optimisation, business outcomes, human decision quality, or SME representativeness."
)

LIMITATIONS = [
    "Provenance: the POS data appears to be real Indian POS data from its structure and content, but the uploader/store provenance is NOT independently verified. It is not an official or government dataset and no such claim is made.",
    "Licence: CC BY-NC-SA 4.0 as recorded in the repository (non-commercial, share-alike, attribution).",
    "Representativeness: one store, 89 days (1 Jan-31 Mar 2025), one season. NOT representative of Indian SMEs or Indian retail generally.",
    "Data view: 36% of lines (weighed/fractional quantities) cannot be stored by the production schema and are excluded; identical repeat lines are merged because the production upload rejects duplicates. Totals and units of the retained lines are exact; row grain is not a bill line. The view retains 78.22% of the source revenue.",
    "Scope: objective descriptive analytics / question answering only. Nothing here evaluates churn, causal effects, pricing or marketing optimisation, forecasting, business outcomes, or human decision quality.",
    "Scoring is a deterministic text parser. Verbose answers containing several numbers can be over-credited by the 'contains the truth' rule; the stricter first-number metric is reported beside it. 'Unsupported claim' is not assessed automatically; raw outputs are preserved for audit.",
    "No sampling parameter or seed is set; repeated requests are independent samples, not seeded replays. The client retries only rate-limit / connection errors, at most once; a timeout is never retried.",
    "One user question needs one classification request and, if the validated explanation is enabled, one explanation request. Tokens, latency and cost are reported only when the provider returned them (cost is an estimate from published prices, not a billing record).",
    "The reference tool-use system (a model that writes pandas code) needs text generation and was not run; no comparison with it exists in this run.",
    "A structured-request EXACT-MATCH accuracy is not available: the frozen task spec contains no gold structured requests. The recorded proxies are request validity, request execution, and agreement of the executed result with the independently computed ground truth.",
]


def _fmt(v, suffix=""):
    return "not available" if v is None else f"{v}{suffix}"


def _status_page(meta: dict) -> str:
    lines = [f"# LLM evaluation - run `{meta['run_id']}`", "", f"**Status: {meta['status']}**  |  research result: {meta.get('research_result')}", ""]
    if meta["status"] == "BLOCKED":
        lines += [f"**{meta.get('reason', 'The evaluation was not executed and no results exist.')}**", "",
                  f"Blockers: {', '.join(meta.get('blockers', [])) or 'see reason'}",
                  f"LLM configuration found: `{json.dumps(meta.get('llm'))}`",
                  f"Production LLM path: `{json.dumps(meta.get('production_llm_path'))}`", "", "Needed before execution:"] + [f"- {x}" for x in meta.get("needed", [])]
    else:
        lines += [meta.get("note", "This run is not a research result."), "", "No metrics are reported for this run."]
    lines += ["", "## Dataset disclosure"] + [f"- {x}" for x in LIMITATIONS[:3]]
    return "\n".join(lines) + "\n"


def _quality_block(L: list[str], key: str, track: str, blk: dict) -> None:
    q = blk["quality"]
    L += ["", f"### {key} - {track} track  (evaluable attempts {q.get('n_attempts', 0)} of {q.get('n_attempts_total', q.get('n_attempts', 0))}, tasks {q.get('n_tasks', 0)})"]
    if q.get("n_excluded_unsupported_by_design"):
        L.append(f"{q['n_excluded_unsupported_by_design']} attempts were refusals on the supplementary GST track (the production data has no GST field). "
                 "They are neither model failures nor successes and are excluded from the agreement rates.")
    if q.get("n_attempts"):
        L += [f"Agreement of the executed result with the ground truth: **{_fmt(q['accuracy_primary_pct'], '%')}** ({q['n_correct']}/{q['n_attempts']} attempts; "
              f"a fallback or failed attempt counts as not agreeing); first-number agreement {_fmt(q['accuracy_first_number_pct'], '%')}; "
              f"truth-mentioned (lenient) {_fmt(q['truth_mentioned_lenient_pct'], '%')}; repeat-consistent tasks "
              f"{q['repeat_consistency']['tasks_with_identical_verdict_across_repeats']}/{q['repeat_consistency']['of_tasks']}.",
              "", "| category | attempts | agreement % | unable % | invalid % | system/tool failure % |", "|---|---|---|---|---|---|"]
        for cat, cq in blk["by_category"].items():
            if not cq.get("n_attempts"):
                continue
            fr = cq["failure_rates_pct"]
            L.append(f"| {cat} | {cq['n_attempts']} | {_fmt(cq['accuracy_primary_pct'])} | {_fmt(fr['unable_to_answer'])} | {_fmt(fr['invalid_answer'])} | {_fmt(fr['tool_or_system_failure'])} |")
        L += ["", "Outcome taxonomy: " + ", ".join(f"{k}={v}" for k, v in q["outcomes"].items() if v) + "  (unsupported_claim is not assessed automatically)",
              f"Numeric error (first number): median relative {_fmt(q['numeric_error']['median_rel_error_first_number'])}, mean absolute {_fmt(q['numeric_error']['mean_abs_error_first_number'])} (units mixed - read by category)."]
        if q["ranking"]["n_attempts"]:
            L.append(f"Ranking tasks: top-1 correct {_fmt(q['ranking']['top1_correct_pct'], '%')}, mean overlap@k {_fmt(q['ranking']['mean_overlap_at_k'])}.")
    pa = q.get("path_accounting")
    if pa:
        g = pa["path_groups"]
        L += ["", "**Where the answers came from** (a legacy-router answer is never counted as an LLM-path success):",
              f"- answered by the LLM analytics path: {g['llm_path']}; declined as unsupported by the LLM path: {g['unsupported']}; "
              f"legacy-router fallback: {g['legacy_fallback']} (rate {_fmt(pa['fallback_rate_pct'], '%')}); infrastructure failure: {g['infrastructure_failure']}",
              f"- agreement among attempts answered by the LLM path: {_fmt(pa['accuracy_among_attempts_answered_by_llm_path_pct'], '%')}; "
              f"agreement over ALL attempts (fallbacks count as not agreeing): {_fmt(pa['llm_path_success_pct_of_all_attempts'], '%')}",
              f"- failure categories: {pa['failure_categories'] or 'none'}; fallback attempts whose text would have matched the truth anyway (not counted): "
              f"{pa['legacy_fallback_attempts_whose_text_would_have_scored_correct']}"]


def _efficiency_table(L: list[str], metrics: dict) -> None:
    L += ["", "| system / condition / track | end-to-end median s | p95 s | engine median s | LLM calls/attempt | tokens in / out (calls with usage) | cost USD |", "|---|---|---|---|---|---|---|"]
    for key, tracks in metrics.items():
        for track, blk in tracks.items():
            e = blk["efficiency"]
            tk = e["tokens"]
            eng = e.get("engine_latency_s") or {}
            cost = e["cost_usd_total"]
            costs = "not available" if cost is None else f"{cost}{' (lower bound)' if e.get('cost_is_lower_bound') else ''}"
            L.append(f"| {key} / {track} | {_fmt(e['latency_end_to_end_s']['median'])} | {_fmt(e['latency_end_to_end_s']['p95'])} | {_fmt(eng.get('median'))} | "
                     f"{_fmt(e['llm_calls_per_attempt_mean'])} | {_fmt(tk.get('input_total'))} / {_fmt(tk.get('output_total'))} | {costs} |")
    L += ["", "Per LLM call role (latency includes provider retries; p95 only with >= 20 observations):", "",
          "| system / track | role | calls | failed | calls with retries | retry attempts | latency median s | p95 s | input tokens | output tokens | calls without usage |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, tracks in metrics.items():
        for track, blk in tracks.items():
            for role, st in blk["efficiency"].get("by_llm_call_role", {}).items():
                lat = st["latency_s_including_retries"]
                L.append(f"| {key} / {track} | {role} | {st['n_calls']} | {st['n_failed_calls']} | {st['n_calls_with_retries']} | {st['retry_attempts_total']} | "
                         f"{_fmt(lat['median'])} | {_fmt(lat['p95'])} | {_fmt(st['input_tokens_total'])} | {_fmt(st['output_tokens_total'])} | {st['n_calls_without_usage']} |")


def write_report(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f"{meta['run_id']}.md"
    is_mock = bool(meta.get("mock"))
    if (not meta.get("research_result") and not is_mock) or meta["status"] in ("BLOCKED", "FAILED"):
        out.write_text(_status_page(meta), encoding="utf-8")
        return out

    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))["metrics"]
    llm = meta["llm"]
    mi = meta.get("model_identity") or {}
    L: list[str] = []
    if is_mock:
        L += ["# MOCK INFRASTRUCTURE VALIDATION (NOT RESEARCH RESULTS) - run `" + meta["run_id"] + "`", "", MOCK_BANNER, ""]
    else:
        L += [f"# LLM analytics-path evaluation (objective business-analytics questions, Indian POS data) - run `{meta['run_id']}`", ""]
    L += [f"**Status: {meta['status']}** - attempts {meta['completed_attempts']}/{meta['planned_attempts']} - finished {meta.get('finished_utc')}", ""]
    if meta.get("run_type") == "partial_pilot":
        sel = meta.get("selection") or {}
        L += ["> **PARTIAL / PILOT EVALUATION - NOT THE FULL BENCHMARK.** " + (meta.get("note") or ""),
              f"> Attempted tasks: {', '.join(sel.get('task_ids_attempted', []))}. Not attempted: {', '.join(sel.get('task_ids_not_attempted', [])) or 'none'}. "
              f"Repeats used {sel.get('repeats_used')} (frozen {sel.get('repeats_frozen')}). Percentages below are counts over this small sample and carry wide uncertainty.", ""]
    L += ["## 1. Research question",
          "How well does the LLM interpretation layer of DecisionGPT's analytics path turn natural-language business questions into valid structured analytics "
          "requests that the deterministic engine executes to results matching an independently computed ground truth?", "",
          "**Metric boundary.** " + METRIC_BOUNDARY, "", "**Not evaluated.** " + NOT_EVALUATED, ""]
    d = meta["view"]
    L += ["## 2-3. Dataset and provenance limitation",
          f"Indian POS retail register, {d['date_min']} to {d['date_max']}. Evaluation-compatible view derived from the approved dataset: {d['after_merge']:,} rows from "
          f"{d['processed_rows']:,} processed lines (view sha256 `{d['view_sha256'][:16]}...`). View rules: {d['rules']}",
          "", *[f"- {x}" for x in LIMITATIONS[:4]], ""]
    L += ["## 4-5. Task design and ground truth",
          f"{meta['n_tasks']} pre-registered tasks (spec sha256 `{meta['spec_sha256'][:16]}...`, frozen hash verified before and after the run), {meta['repeats']} independent repeats each. "
          f"Ground truth is computed by code from the view ({meta['ground_truth_version']}) and is never shown to any LLM; tolerances were fixed before execution. "
          "The 4 GST tasks are a separate supplementary track: the production data has no GST field, so a refusal is the correct behaviour and is not scored as a failure.", ""]
    L += ["## 6-8. Systems, model identity and configuration",
          *[f"- **{k}**: {v}" for k, v in (meta.get("system_labels") or {}).items()],
          "- Both systems read the same evaluation-compatible view derived from the approved POS dataset; the tool-use system is a capability reference, not a simpler baseline.",
          f"- Provider `{llm.get('provider')}`; model requested `{mi.get('model_requested') or llm.get('model_configured')}`; model(s) returned by the provider "
          f"`{', '.join(mi.get('models_returned_by_provider') or []) or 'not exposed'}`; no sampling parameter or seed; request parameters by role `{json.dumps(mi.get('request_parameters_by_role'))}`.",
          f"- Retry policy: {mi.get('retry_policy')}. Typed-question set sha256 `{str((meta.get('prompts') or {}).get('interpreter_questions_sha256', 'n/a'))[:16]}...`; "
          f"no explainer call; baseline prompts `{meta['prompt_version']}`; scorer `{meta['scorer_version']}`.",
          f"- Evaluation clock: `{json.dumps((meta.get('evaluation_clock') or {}).get('conditions'))}` via {(meta.get('evaluation_clock') or {}).get('mechanism')}. Code commit `{(meta.get('git') or {}).get('commit')}`.", ""]
    L += ["## 9-11. Results (per system, condition, track and category - never one combined score)"]
    for key, tracks in metrics.items():
        for track, blk in tracks.items():
            _quality_block(L, key, track, blk)
    L += ["", "## 12. Efficiency (reported separately from quality; one user question needs one classification request plus an optional explanation request)"]
    _efficiency_table(L, metrics)
    L += ["", "## 13. Limitations", *[f"- {x}" for x in LIMITATIONS], "",
          "## 14-15. What the results do / do not support",
          "They describe how this LLM interpretation layer, with the deterministic engine behind it, handled these pre-registered objective questions over this one store's 89 days. "
          "They do not show agreement on other businesses, other question types, forecasting, churn, causal or pricing decisions, business outcomes, or human decision quality.", "",
          "## 16-17. Reproducibility", f"Run ID `{meta['run_id']}`. Re-run: `python -m research.llm_evaluation.run_evaluation {'mock' if is_mock else 'run'}` (see README). Raw outputs: `runs/{meta['run_id']}/raw_outputs/`."]
    if is_mock:
        inj = meta.get("mock_injected_events") or []
        L += ["", "## Mock injections (infrastructure validation only)",
              f"{len(inj)} controlled provider events were injected to prove the accounting works: " + "; ".join(f"{e['task_id']}/{e['role']}#{e['ordinal']}={e['kind']}" for e in inj),
              "", MOCK_BANNER]
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    return out
