# POS analytics Q&A evaluation of the actual DecisionGPT system

**2026-10-13: the provider was migrated from OpenAI to TypeSafe AI Jev (typed decisions only) - see `DEVIATIONS.md` entry 8; the frozen spec, ground truth, scorer and manifest are unchanged and no real run has occurred.**

**Status (2026-10-08, readiness gate): infrastructure READY · task suite frozen (98f37037…) · manifest frozen (94aa419c…) · production LLM analytics path IMPLEMENTED · mock infrastructure validation PASSED (NOT research results) · execution BLOCKED only by the missing LLM provider (not configured, not executed). No research results exist. See `READINESS_GATE_2026-10-08.md`.**

Research question (from `research/ACTIVE_RESEARCH_PROGRAM.md`, restricted for this first evaluation to objective analytics questions):
how effectively does the actual DecisionGPT system answer objective business-analytics questions over real Indian POS data, compared with an LLM that has direct read-only access to the same data?

This evaluation does **not** evaluate churn, causal decision quality, pricing/marketing optimisation, business outcomes, forecasting validity, SME representativeness or human decision quality.

## Layout
| Path | Purpose |
|---|---|
| `data_view.py` | the evaluation data view (what the production system can ingest unchanged) + provenance hash check |
| `build_task_spec.py` → `tasks/tasks_v1.json` | the **frozen, pre-registered** task specification (27 tasks, tolerances, scoring rules, repeats) |
| `ground_truth.py` → `ground_truth/ground_truth_<spec>.json` | deterministic ground truth computed from the view by code; no LLM, no hand-typed values |
| `scoring.py` | deterministic scorers (numbers with lakh/crore, dates, entities, rankings, signed changes, refusals) — no LLM judge |
| `systems/decisiongpt.py` | the real production path: isolated DB, `POST /businesses`, production upload endpoints, `POST /businesses/{id}/chat` |
| `systems/llm_code_baseline.py`, `sandbox.py`, `prompts.py` | protocol B2 baseline: same LLM client + sandboxed pandas tool over the same data |
| `llm_instrument.py` | measurement-only wrapper recording provider/model/latency/token usage of every real LLM call |
| `metrics.py`, `report.py` | per-system / condition / track / category metrics; human-readable report |
| `run_evaluation.py` | runner (`check`, `run`, `smoke`, `report`) |
| `runs/<run_id>/` | `metadata.json`, `task_results.jsonl`, `raw_outputs/`, `metrics.json`, `errors.json` (never overwritten) |
| `PROTOCOL_ADDENDUM.md`, `DEVIATIONS.md` | how this extends the locked protocol; audit trail of changes made before execution |

## Run it
From the repository root (Windows shown; use `:` on Linux/macOS):

```bash
set PYTHONPATH=backend;.
python -m research.llm_evaluation.run_evaluation check     # data hash, spec, ground-truth reproduction, LLM status (no LLM needed)
# configure the provider (never committed): TYPESAFE_API_KEY in backend/.env or the environment (TypeSafe AI Jev; see docs/JEV_INTEGRATION.md)
python -m research.llm_evaluation.run_evaluation run       # full pre-registered evaluation; exit code 3 + a BLOCKED record if no LLM is configured
python -m research.llm_evaluation.run_evaluation report <run_id>
```

Optional cost: put verified prices in `research/llm_evaluation/pricing.json` as `{"models": {"<exact model string>": {"input_per_million_usd": x, "output_per_million_usd": y, "source": "<url + date>"}}}`. Without it, cost is reported as "not available". Nothing is estimated.

`smoke` runs only the DecisionGPT path with the LLM **disabled** to verify plumbing; its output is flagged `research_result: false`, never produces metrics or a report, and must not be cited.

## Information given to each system
- **DecisionGPT**: date, product, quantity, unit price (revenue is computed by ingestion) for every view line, through the production upload path. It cannot receive GST (no column in the canonical schema). Evaluation clock fixed at 2025-03-31 for the primary condition (`asof`) because the production chat windows use `date.today()`; the real clock (`realclock`) is the secondary condition. No production code is modified.
- **LLM + data tool**: the same fields as a DataFrame, plus `gst_pct` only for the 4 supplementary GST tasks. It is never shown the ground truth, task metadata or tolerances.
- A **full-context** LLM baseline (all rows in the prompt) is infeasible: 30,293 view rows are about 1.1 million characters (roughly 280k tokens by a 4-characters-per-token rule of thumb, not measured with a tokenizer), beyond most context windows and costly even where it fits, so the tool-using baseline is used instead (documented, not hidden).


## Commands added by the readiness gate
- `python -m research.llm_evaluation.run_evaluation mock` - wire-level fake-provider infrastructure run (27 tasks x 5 repeats, injected failures); never a research result.
- `python -m research.llm_evaluation.audit.readiness_gate [--reuse-mock RUN_ID]` - re-verifies every gate and rewrites `READINESS_GATE_2026-10-08.md`.
- `run` now defaults to `--conditions asof`; the provider must be configured with `TYPESAFE_API_KEY` (Jev); the reference tool-use system cannot run on Jev and `run` refuses it explicitly.
