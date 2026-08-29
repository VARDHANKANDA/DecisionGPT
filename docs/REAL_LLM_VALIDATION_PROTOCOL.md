# Real-LLM Validation Protocol (FROZEN)

Status: **`REAL_LLM_VALIDATION = BLOCKED`** — no LLM provider is configured
(`settings.llm_enabled == False`; both `LLM_PROVIDER` and `LLM_API_KEY` are
empty). This protocol is registered **now** so the run, when a provider is
legitimately configured, cannot be tuned after the fact.

## 0. Scope — what a real LLM does and does not change

The LLM boundary is deliberately narrow (`app/agents/base.py`: *"No agent calls
an LLM"*; `app/services/llm_service.py`). With a real provider configured:

| Path | Uses the LLM? | Effect |
|---|---|---|
| `LLMService.parse_goal` | yes (structuring only; every field re-validated against real data) | goal → objective / target / horizon / constraints |
| `LLMService.evaluate_agent` / `generate_strategy_explanation` / `generate_business_response` | yes (**narration only** — "never invent, estimate, or alter any number/score/probability/causal claim") | wording of the AI Business Review / assistant answers |
| Business Analyst / Financial Advisor / Risk Manager **scores** | **no** | rule-based; identical with or without an LLM |
| Digital Twin predictions (revenue / profit / units / risk_score) | **no** | model-driven; identical |
| Candidate generation, optimizer, strategy selection, `goal_achievement` | **no** | identical |

**Therefore a real-LLM run measures goal-parsing robustness and
explanation faithfulness — not decision outcomes, risk calibration, or R0/R3.**
Any claim that a real LLM changes strategy selection would require a deliberate
architecture change (letting the LLM score), which is **out of scope** and
forbidden by the current task rules.

## 1. Preconditions

- A provider is genuinely configured by a human: `LLM_PROVIDER ∈ {openai,
  openai_compatible, anthropic}`, `LLM_API_KEY` set, optionally `LLM_MODEL` /
  `LLM_BASE_URL`. Verify with `get_settings().llm_enabled is True` — **never**
  print the key.
- No secret is written to the repo, a migration, a fixture, an experiment
  record, a log, or a commit. `.env` stays gitignored.
- Production defaults unchanged: `risk_model = None`, `risk_penalty_lambda =
  1.0`. R3 stays experimental.

## 2. Frozen inputs (identical across the two arms)

| Held fixed | Source |
|---|---|
| scenarios | the existing S01–S12 `ScenarioSpec`s (or a fixed real-SME record set) |
| seed policy | seeds `[42, 43, 44, 45, 46]`; the per-`(scenario, seed)` synthetic business is `random.Random("{scenario}:{seed}")` |
| candidate set | `strategy_generation_service.generate_candidates` output, unchanged |
| Digital Twin predictions | `digital_twin_service.simulate_strategy`, unchanged |
| causal evidence | the graph + evidence levels present at run time |
| available business data | the same seeded business / same real-SME record |
| agent scoring | rule-based BA/FA/RM (LLM-independent) |
| optimizer + selection | `strategy_optimizer` + `analyze_goal`, unchanged |

## 3. The ONE changed factor

`LLM mode`:
- **Arm A — `template`**: `LLM_PROVIDER` / `LLM_API_KEY` unset → deterministic
  templates (the current, reproducible baseline).
- **Arm B — `real_llm`**: provider configured → `LLMService` routes goal
  parsing + narration through `LLMClient`.

Nothing else differs. **Do not** compare Arm A of one config against Arm B of
another (e.g. never "R0 + template" vs "R3 + real LLM").

## 4. Experiment identity

- New experiment type: `risk_manager_real_llm_validation` (or
  `real_llm_narration_validation` if only the narration path is exercised).
- **New experiment ID.** Never overwrite a prior ID. The template arm re-uses
  the existing frozen result where one exists; the real-LLM arm is a fresh run.
- Registered in `experiments/experiment_manifest.json` as an additive entry.

## 5. Metadata recorded per run (no secrets)

```
provider                 (e.g. "anthropic")           — NOT the key
model_identifier         (e.g. "claude-…", "gpt-…")
temperature              (if the provider call sets one; else "provider default")
seed                     (if the provider supports it; else "n/a — nondeterministic")
timestamp_utc
prompt_version           (LLM_PROMPT_VERSION / the system-prompt hash)
llm_mode                 ("template" | "real_llm")
scenario_ids             (or real-SME record ids)
experiment_id
configuration            (risk_model=None, risk_penalty_lambda=1.0, seeds=…)
candidate_set            (per scenario/seed)
agent_outputs            (BA/FA/RM structured evaluations — rule-based, for parity check)
final_strategy
confidence
risk_score
goal_parse_result        (objective / target / horizon / constraints per goal string)
narration_text           (the AI-review / assistant text produced)
latency_ms               (per LLM call, if available)
token_usage              (prompt/completion tokens, if the provider returns them)
```

Store under the experiment's `metrics_json`. **Never** store `api_key`,
`Authorization` headers, or raw provider request bodies containing the key.

## 6. Comparison & metrics

- **Goal parsing:** for a fixed set of goal strings, compare Arm A vs Arm B on
  `objective`, `target_value`, `target_unit`, `time_horizon`, `constraints`.
  Report agreement rate and every disagreement. (Both arms are re-validated
  against real data downstream, so a disagreement is a parsing-quality signal,
  not a correctness failure.)
- **Determinism / parity:** confirm the candidate set, Digital Twin outputs,
  agent scores, selected strategy, `goal_achievement`, `risk_score` and
  `confidence` are **identical** between arms (they must be — the LLM is not in
  that path). Any difference is a bug to investigate, not a result.
- **Narration faithfulness:** check that every number / score / probability /
  causal term in `narration_text` also appears in the structured input
  (no invented figures). Report any hallucinated quantity.
- **Operational:** mean/median latency and token usage per call.

## 7. Anti-tuning rules

- The goal-string set, scenario set, seeds and metrics are fixed by this
  document before the run.
- Run **once** per arm. Do not iterate the prompt, temperature or model to
  improve agreement and then re-report.
- If the provider is nondeterministic, record enough metadata to reproduce the
  **protocol** and state the nondeterminism as a limitation — do not average
  many retries to manufacture a clean number.
- Do not use the real-LLM run to justify promoting R3 or changing any
  production default.

## 8. Reporting

Add a clearly-labelled section to `docs/RESEARCH_EXPERIMENT_REPORT.md`
("Real-LLM validation") and a row to
`docs/REAL_EVIDENCE_READINESS_REPORT.md`. State plainly:
- what the LLM does / does not affect (§0);
- goal-parsing agreement + disagreements;
- parity confirmation (or the bug found);
- narration faithfulness;
- that decision outcomes / R0 vs R3 are **unaffected by the LLM layer** unless
  the architecture is deliberately changed.

Never write "real-LLM validated" as a blanket claim. The precise claim is
"goal parsing and narration were exercised against provider `<name>` model
`<id>` on `<date>` with result `<…>`".

## 9. Exact human action required to unblock

1. Register an account with a supported provider and obtain an API key.
2. Set `LLM_PROVIDER`, `LLM_API_KEY` (and optionally `LLM_MODEL`,
   `LLM_BASE_URL`) in `backend/.env` — **not** committed.
3. Confirm `get_settings().llm_enabled is True`.
4. Run the two arms per §2–§5 and report per §8.
