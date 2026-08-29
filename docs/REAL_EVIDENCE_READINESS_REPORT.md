# REAL EVIDENCE READINESS REPORT

Readiness / audit task. **No experiment run. No synthetic `DecisionOutcome`
created. No production behaviour changed.** Production stays **R0 / D0**
(`risk_model = None`, `risk_penalty_lambda = 1.0`); R3 stays **EXPERIMENTAL /
NOT PROMOTED**.

> **The engineering workflow being ready is not real-world evidence.**
> `REAL SME EVIDENCE = PENDING` until genuine Indian SME decisions and outcomes
> are actually supplied.

---

## Exact current state (read live from the DB / config)

```
Real Indian SME businesses:        0
Real decisions:                    0
Implemented decisions:             0        (no lifecycle field; import implies implemented + outcome recorded)
Real actual outcomes:              0
Outcome horizons:                  none recorded
Real LLM configured:               NO       (LLM_PROVIDER="", LLM_API_KEY="" -> settings.llm_enabled = False)
Real LLM validation:               BLOCKED
DecisionOutcome records (total):   0
  of which REAL_INDIAN_SME_OUTCOME: 0
PredictionEvaluation records:      0
Table 2:                           NOT READY   (needs >= 5 genuine REAL_INDIAN_SME_OUTCOME matched records; have 0)
Causal observational evidence:     0 from real interventions
                                   (dev scratch DB has 5 graph-construction "observational" + 1 "data_supported"
                                    edges from synthetic/demo business history — NOT intervention evidence)
Causal validated evidence:         0        (evidence_type "causally_validated" count = 0)
R3 production status:               EXPERIMENTAL / NOT PROMOTED
Production risk model:              R0 / D0  (risk_model = None, risk_penalty_lambda = 1.0)
AGMARKNET:                          DATA_PENDING  (DATA_GOV_IN_API_KEY not in environment)
Experiment count (manifest):       16 (unchanged; this task adds none)
```

---

## 1. What was audited

- Real-SME collection pipeline: `real_sme_outcome_service.py`,
  `scripts/import_real_sme_outcomes.py`, `DecisionOutcome` model + migration
  `0007`, the outcome API (`memory.py`), and the Research → Digital Twin
  Evaluation → **Real Indian SME Outcomes** panel.
- No-leakage guarantees across validation + import + `PredictionEvaluation`.
- LLM configuration (`core/config.py`, `llm_service.py`, `llm_provider.py`,
  `agents/base.py`) — why real-LLM validation is blocked and what it would
  actually measure.
- Table 2 readiness in `paper_results_service.py`.
- Causal-feedback thresholds (`causal_feedback_service.py`).
- AGMARKNET acquisition path (`scripts/download_india_datasets.py`).
- Research-claim language in the experiment reports.

## 2. What was already correct

- **India-only / anonymised / consent / provenance / supported-decision-type /
  horizon ∈ {7,14,30,60,90} / horizon↔window consistency / decision-before-
  outcome / PII rejection / example-row rejection / `source_type =
  real_indian_sme` / synthetic isolation** — all enforced by `validate_record`
  and the importer (18 pre-existing tests).
- **Duplicate rejection** — the `_sme_natural_key` guard added in the previous
  task works (verified).
- **No leakage:** `expected_outcome_json` is built only from `predicted_*` /
  `baseline_*`; `actual_outcome_json` only from `actual_*`;
  `PredictionEvaluation` computes `predicted_change` and `actual_change`
  independently (tests: `test_no_leakage_*`, `test_horizon_and_actual_window_must_align`).
- **LLM boundary:** `app/agents/base.py` — *"No agent calls an LLM."* The
  BA/FA/RM **scores**, the Digital Twin predictions, candidate generation, the
  optimizer and strategy selection are all rule-/model-based and **LLM-independent**.
- **Causal thresholds:** `MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`,
  `CONSISTENCY_THRESHOLD = 2/3` — unchanged.
- **Digital Twin metrics:** revenue / profit / units reported separately; MAPE
  only where `actual_change ≠ 0`; honest empty state.

## 3. Genuine bugs found

**One.** `paper_results_service` marked **Table 2 available at the first matched
outcome** (`n_matched > 0`) and counted **every** `PredictionEvaluation` row
regardless of `source_type`. This contradicted the documented condition
(**≥ 5 genuine `REAL_INDIAN_SME_OUTCOME` records**) and could have let a
synthetic / demo-recorded outcome populate the paper table.

(No bug in the SME collection pipeline itself — it was already sound.)

## 4. Exact changes made

| File | Change |
|---|---|
| `backend/app/services/real_sme_outcome_service.py` | added `TABLE_2_MIN_REAL_OUTCOMES = 5`, `matched_real_sme_eval_count(db)`, `real_sme_eval_rows(db)` (real-SME-only), `table_2_status(db)` |
| `backend/app/services/paper_results_service.py` | Table 2 gate now uses `table_2_status` — `available` only at **≥ 5** genuine real-SME matched records; preview rows restricted to real-SME outcomes; `data_category = "REAL_INDIAN_SME_OUTCOME"`; removed the now-unused `PredictionEvaluation` import |
| `backend/app/services/... (Decision lifecycle)` | **no change** — see §11; documented instead of migrated |
| `frontend/src/lib/research-api.ts` | `PaperResults.tables[].data_category?: string` (additive) |
| `docs/REAL_LLM_VALIDATION_PROTOCOL.md` | **new** — frozen real-LLM protocol (same inputs, only LLM mode changes, anti-tuning rules, metadata-without-secrets, scope: LLM affects goal parsing + narration only) |
| `docs/RESEARCH_EXPERIMENT_REPORT.md` | tightened one heading: "R3 was then externally validated" → "R3 was then **probed against** real Indian data (not validated)" |
| `docs/REAL_EVIDENCE_READINESS_REPORT.md` | this file |
| tests | `table_2_status` ladder (0→4→5); synthetic-recorded outcome never counts; `llm_enabled` needs both provider + key; agents never import/call the LLM; paper-results Table 2 stays NOT READY below 5 real records |

## 5. Tests run / results

```
Backend:   pytest -q — 316 passed, 1 skipped  (all green; no test weakened or deleted)
Frontend:  npm run build — compiled ; tsc — clean ; npm run lint — 0 errors
E2E:       scripts/audit_e2e.py — no assertion failures
Alembic:   0001 -> head -> base -> head — clean (head = 0007)
```

Targeted coverage: real-SME importer, PII rejection, duplicate rejection,
no-leakage, horizon/window alignment, DecisionOutcome, Digital Twin evaluation,
causal feedback thresholds, LLM configuration, Table 2 gate, Research Dashboard
real-SME block.

## 6. Current real-SME evidence count

**0 businesses · 0 decisions · 0 outcomes · 0 matched `PredictionEvaluation`.**
`REAL_INDIAN_SME_OUTCOME = 0`.

## 7. Current real-LLM status

**`REAL_LLM_VALIDATION = BLOCKED`.** `settings.llm_enabled == False` — both
`LLM_PROVIDER` and `LLM_API_KEY` are empty in `backend/.env`. The app runs in
deterministic template mode. No provider was invented; no key was fabricated.
Frozen protocol registered: `docs/REAL_LLM_VALIDATION_PROTOCOL.md`. Note: a real
LLM would exercise **goal parsing + narration only** — agent scores and
strategy selection are LLM-independent by architecture.

## 8. Table 2 status

**NOT READY.** Requires **≥ 5** genuine `REAL_INDIAN_SME_OUTCOME` records with a
matched predicted/actual pair; currently **0**. The gate now enforces this
(previously it flipped at 1 and ignored `source_type`). Categories
`INDIA_REAL_BUSINESS`, `INDIA_PUBLIC_CONTEXT`, `SYNTHETIC_CONTROLLED`,
`SYNTHETIC_INDIAN_CONTEXT`, `INDIA_AGRICULTURAL_PRICE` are never mixed in.

## 9. Causal-validation status

**NOT READY.** `causally_validated` edges = 0. Real intervention feedback
(`ASSUMED → OBSERVATIONAL`) still requires `MIN_OUTCOMES_FOR_OBSERVATIONAL = 3`
consistent per-edge real outcomes (`CONSISTENCY_THRESHOLD = 2/3`); nothing
weakened. `CAUSALLY_VALIDATED` is never automatic. The `observational` /
`data_supported` edges present in the dev scratch DB are **graph-construction**
evidence from synthetic/demo business *history* (correlation / Granger), not
intervention evidence.

**Required before `ASSUMED → OBSERVATIONAL`:** ≥ 3 real decision outcomes that
move both endpoint nodes of an edge in the hypothesised direction, agreeing
≥ 2/3 of the time (per-edge). **Before `→ CAUSALLY_VALIDATED`:** the existing
higher bar in `causal_feedback_service` / `causal_graph_service` (a validated
causal method, not one agreeing outcome) — unchanged and not reachable from the
current data.

## 10. Production status

`risk_model = None`, `risk_penalty_lambda = 1.0` → **R0 / D0**. R3 / R1 /
R2-λ remain labelled experimental. Active model registry unchanged. No
experiment ID overwritten (`experiments/experiment_manifest.json`
byte-identical, 16 experiments).

## 11. Remaining human actions

1. **Real SME evidence (primary):** obtain institutional/legal review
   (`docs/templates/real_sme_consent_and_provenance.md`); recruit genuine
   Indian SMEs who used DecisionGPT for a supported (price / marketing /
   inventory) decision and can report the **actual** outcome at a fixed
   horizon; fill `docs/templates/real_indian_sme_outcome_template.{csv,json}`
   per `docs/REAL_SME_DATA_COLLECTION_GUIDE.md` + the checklist; run
   `python scripts/import_real_sme_outcomes.py <file>`. At **≥ 5** genuine
   outcomes, Table 2 auto-populates (real-SME only) and analysis proceeds
   **descriptively** (`docs/REAL_INDIAN_SME_VALIDATION_METHODOLOGY.md`).
2. **Real LLM:** register with a supported provider, set `LLM_PROVIDER` /
   `LLM_API_KEY` (and optionally `LLM_MODEL` / `LLM_BASE_URL`) in
   `backend/.env` (never committed), confirm `get_settings().llm_enabled is
   True`, then run the two arms of `docs/REAL_LLM_VALIDATION_PROTOCOL.md`.
3. **AGMARKNET (optional):** register a free key at data.gov.in, set
   `DATA_GOV_IN_API_KEY`, run `python scripts/download_india_datasets.py` then
   `scripts/build_external_datasets.py --only agmarknet` and
   `scripts/register_external_datasets.py`. Stays `INDIA_AGRICULTURAL_PRICE` —
   never described as Indian SME retail transaction data.
4. **Decision lifecycle (only if a future study needs it):** the `Decision`
   model has no explicit `generated / accepted / rejected / implemented /
   outcome_pending / outcome_recorded` field — states are implicit (row exists
   → generated; no `DecisionOutcome` → pending; `DecisionOutcome` exists →
   recorded). The real-SME importer's contract is *implemented + outcome
   recorded*, and `DecisionOutcome.outcome_status` captures
   achieved/partial/not/inconclusive. Add a status column **only** if a study
   needs to track accepted-but-not-implemented decisions — documented here,
   not migrated now.

## 12. Files changed

```
backend/app/services/real_sme_outcome_service.py
backend/app/services/paper_results_service.py
frontend/src/lib/research-api.ts
docs/REAL_LLM_VALIDATION_PROTOCOL.md          (new)
docs/REAL_EVIDENCE_READINESS_REPORT.md        (new)
docs/RESEARCH_EXPERIMENT_REPORT.md            (one heading tightened)
tests/unit/test_real_sme_outcome_service.py
tests/unit/test_llm_integration.py
tests/api/test_research_evaluations.py
```

## 13. Git commit hash

`<filled on commit>`

---

**Scientific status: `REAL SME EVIDENCE = PENDING`.** The collection workflow,
the frozen real-LLM protocol and the corrected Table 2 gate are ready; there is
no real-world evidence yet, and none was fabricated.
