# Complete Project Health Report

Independent end-to-end verification of the DecisionGPT repository — **not** a
paper-writing task. Every claim below was checked against the running code, not
taken from prior audit reports.

**Method:** repository discovery → environment/dependency check → DB & migration
round-trip → ORM-vs-migration drift check → live API flows via `TestClient`
(full SME journey, capability gating, invalid inputs, cross-business isolation,
research dashboard, real-SME pipeline, Table 2 ladder) → full backend suite →
frontend build/tsc/lint → `audit_e2e.py` → doc-vs-code consistency.

---

## A. Overall status

**HEALTHY WITH MINOR ISSUES.**

The complete pipeline works end-to-end. Two genuine defects were found and
fixed (one crash on an invalid upload `data_type`, one cosmetic version string).
One MEDIUM reproducibility issue (installed dependency versions have drifted
above `requirements.txt`) requires a **human decision** and was not changed.

---

## B. Component status

| Component | Status | Evidence | Issues |
|---|---|---|---|
| Backend | **HEALTHY** | 60 API routes enumerated via OpenAPI; `app.main` imports clean; 319 tests pass | — |
| Frontend | **HEALTHY** | `next build` clean (26 routes), `tsc --noEmit` clean, ESLint 0 errors (1 pre-existing unrelated warning in `auth-context.tsx`) | — |
| Database | **HEALTHY** | Alembic `0001→HEAD→base→HEAD` clean; head `0007`; 30 tables; **no ORM-vs-migration schema drift** (verified column-by-column) | — |
| Data ingestion | **HEALTHY** (after fix) | live: valid CSV → `completed`; `.exe` → failed job; binary → failed job "Could not read CSV"; **unknown `data_type` → was HTTP 500, now failed job** (BUG-1, fixed) | fixed |
| Forecasting | **HEALTHY** | live `POST /analytics/forecast` → 200 (model/metrics/points); no-data → 422 "No sales history on file yet"; naive/linear/xgboost registered; **6 v1 active models unchanged** | — |
| Digital Twin | **HEALTHY** | live `POST /digital-twin/simulate` → 200 (`output.expected_revenue/profit/units/risk`); invalid action → 422; out-of-bounds value → 422; production path uses R0 | cosmetic "vv1" version string (BUG-2, fixed) |
| Causal Graph | **HEALTHY** | live `POST /causal-graph/build` → 200; `GET` → 200 with `evidence_summary`; thresholds `MIN_OUTCOMES_FOR_OBSERVATIONAL=3`, `CONSISTENCY_THRESHOLD=2/3` unchanged; `CAUSALLY_VALIDATED=0` | — |
| Multi-Agent | **HEALTHY** | live decision returns `agent_reviews` = {business_analyst, financial_advisor, risk_manager}; `app/agents/base.py` — "No agent calls an LLM"; agent modules import no LLM layer (regression test present) | — |
| Risk Manager | **HEALTHY** | production `risk_model=None`, `risk_penalty_lambda=1.0`; R1/R2-λ/R3 are opt-in research configs only; penalty still applied in production | — |
| Optimizer / Strategy generation | **HEALTHY** | live decision produced 5 candidates incl. `Price +5%` / `Price +10%` (candidate-space correction active); Risk Manager is not a candidate filter (candidates generated before scoring) | — |
| Memory / DecisionOutcome | **HEALTHY** | live: decision stored & retrievable; `GET .../outcome` = 404 before, 200 after `POST`; `expected_outcome_json` built only from `predicted_*`/`baseline_*` (no-leakage tests); duplicate natural-key rejection; `outcome_date ≥ decision_date` enforced | — |
| Research Dashboard | **HEALTHY** | all 12 research endpoints → 200 with correct structure; metrics read from stored `ExperimentRun.metrics_json`; real-SME panel shows `0 / NOT READY / PENDING`; Real-LLM/R3/Production status derived live from settings + `PipelineOptions()` | — |
| Research infrastructure | **HEALTHY** | 16 experiments, all `completed`; `experiments/experiment_manifest.json` byte-identical before/after this audit; no experiment overwritten | — |
| Security | **HEALTHY** | live (auth on): Business B → A's business/kpis/decisions/capabilities all **403**; SME → research **403**; admin → research **200**; no-token → **401/403**; secrets not in `git ls-files` (`.env` gitignored; `raw/` gitignored) | — |
| Reproducibility | **MINOR ISSUE** | manifest traces every number to id/seed/version; migrations deterministic; **BUT installed deps (fastapi 0.141, pydantic 2.13, pandas 3.0, numpy 2.5, sklearn 1.9) are above the `requirements.txt` pins (0.115 / 2.9 / 2.2.3 / 1.26.4 / 1.5.2)** | ISSUE-3 (human decision) |

---

## C. Bugs discovered

### BUG-1 — Unknown `data_type` on upload crashes with HTTP 500 (MEDIUM)
- **Reproduction:** `POST /businesses/{id}/data/upload?data_type=aliens` with any CSV → uncaught `KeyError: 'aliens'` in `data_ingestion_service.process_upload` (`CANONICAL_TYPES[canonical_type_name]`), surfaced as HTTP 500.
- **Root cause:** `file_parsing.parse_upload` used `data_type_hint or detect_canonical_type(filename)` and returned `{hint: df}` without validating the hint against `CANONICAL_TYPES`.
- **Fix:** `parse_upload` now raises `ValidationFailedError("Unknown data type '<x>'. Supported: …")` for an unrecognised hint; `process_upload` already catches that → returns a **failed job** with a clear message (HTTP 200, `status="failed"`), consistent with other parse failures.
- **Test:** `tests/api/test_data_upload.py::test_unknown_data_type_fails_gracefully_not_500`.

### BUG-2 — Digital-Twin assumption text renders "vv1" (LOW / cosmetic)
- **Reproduction:** any DT simulation → `output.assumptions[0]` = "…using sales_forecast_xgboost **vv1**…" (also in the 3 agent assumption strings and `single_agent`).
- **Root cause:** `f"… v{model_row.version}"` where `model_row.version` is already `"v1"`.
- **Fix:** dropped the literal `v` prefix in 5 places (`digital_twin_service.py`, `business_analyst.py`, `financial_advisor.py`, `risk_manager.py`, `single_agent.py`) → "…using sales_forecast_xgboost v1…".
- **Test:** covered by existing decision / digital-twin integration tests (30 pass); no test asserted the old "vv1".

*No other defects found.* The SME collection pipeline, no-leakage guarantees,
Table 2 gate, security isolation, and production/research separation were all
already correct.

---

## D. Tests

```
Backend  : pytest -q  →  319 passed, 1 skipped, 0 failed
           (was 318; +1 = test_unknown_data_type_fails_gracefully_not_500)
           1 skipped = AGMARKNET committed-file test, gated on DATA_PENDING (intentional)
Frontend : next build → clean (26 routes) ; tsc --noEmit → clean ; eslint → 0 errors, 1 pre-existing warning
E2E      : scripts/audit_e2e.py → no assertion failures
Alembic  : 0001 → HEAD → base → HEAD → clean (head 0007, 30 tables)
Schema   : ORM create_all vs alembic-migrated schema → NO DRIFT
Manifest : experiments/experiment_manifest.json → byte-identical before/after
```

No test was weakened, deleted, skipped, or hard-coded to pass.

---

## E. End-to-end workflows

| Workflow | Result |
|---|---|
| Create business → profile → upload sales+products → capabilities | **PASS** — enables sales/forecast/pricing/profit; disables customer analytics with a useful reason; no synthetic substitution |
| Goal parse → decision analyze (candidates → DT → agents → Risk Manager → optimizer → recommendation) | **PASS** — 5 candidates incl. Price ±, 3 agents, risk level + confidence, reasoning present |
| Explanation / trace / decision list / decision get | **PASS** (all 200, correct ids) |
| Decision memory store + retrieve | **PASS** |
| Digital Twin direct simulate | **PASS** (200, full `output`) |
| Causal graph build + get | **PASS** |
| DecisionOutcome record (empty → 404, POST → 200, GET → 200) | **PASS** |
| Invalid data → validation error (missing field 422; bad file failed-job; unknown data_type failed-job [was 500]) | **PASS** (after BUG-1 fix) |
| Missing data → capability disabled (not fabricated) | **PASS** |
| Unauthorised cross-business access → denied | **PASS** (403 on business/kpis/decisions/capabilities) |
| No LLM → deterministic template mode | **PASS** (`llm_enabled=False`; agents never call an LLM) |
| Real-SME pipeline: reject synthetic/PII/Aadhaar/phone/GSTIN/non-IN/bad-horizon/leakage; accept valid | **PASS** |
| Table 2 ladder 0→4 NOT READY, 5 READY (fixtures only) | **PASS** |
| Real-SME duplicate rejection | **PASS** |

---

## F. Research integrity

| Check | Result |
|---|---|
| No fabricated real SME data | ✅ `REAL_INDIAN_SME_OUTCOME = 0` (dev.db); ladder tested with ephemeral in-memory fixtures only |
| No fabricated outcomes / `DecisionOutcome` records | ✅ `DecisionOutcome = 0`, `PredictionEvaluation = 0` |
| No fabricated LLM results | ✅ `llm_enabled=False`; template mode; no agent calls an LLM |
| No experiment overwritten | ✅ 16 experiments unchanged; `experiment_manifest.json` byte-identical |
| No production model changed | ✅ 6 v1 active models unchanged (naive/linear/xgboost forecast + logreg/rf/xgb churn) |
| No dataset category mixed | ✅ SME-private / INDIA_REAL_BUSINESS / INDIA_PUBLIC_CONTEXT / INDIA_AGRICULTURAL_PRICE / SYNTHETIC_CONTROLLED / SYNTHETIC_INDIAN_CONTEXT / RETIRED_NON_INDIAN all distinct; Benroshan is not Table-2 evidence; retired M5/UCI/Myanmar still retired |

---

## G. Production status

```
Production risk model         : None      (R0)
Production risk_penalty_lambda : 1.0       (D0)
R1 / R2-λ / R3                : EXPERIMENTAL, opt-in only, NOT PROMOTED
Active models                : 6 × v1 — unchanged
Production decision path      : POST /decisions/analyze → analyze_goal(db, business_id, goal_id)
                               with no options → PipelineOptions() defaults
```

---

## H. Real-world validation status  *(intentionally pending — not engineering failures)*

```
REAL_INDIAN_SME_OUTCOME      = 0
Table 2                      = NOT READY  (gate: ≥ 5 genuine matched real-SME records)
Digital Twin real-outcome    = NOT READY
Real LLM                     = BLOCKED    (LLM_PROVIDER="", LLM_API_KEY="")
Causal validation            = NOT READY  (CAUSALLY_VALIDATED = 0; thresholds unchanged)
AGMARKNET                    = DATA_PENDING (DATA_GOV_IN_API_KEY not in environment)
```

---

## I. Remaining issues

### CRITICAL
- **None.**

### HIGH
- **None.**

### MEDIUM
- **ISSUE-3 — dependency pin drift.** The venv has `fastapi 0.141.1`, `pydantic 2.13.4`, `pandas 3.0.5`, `numpy 2.5.2`, `scikit-learn 1.9.0`; `backend/requirements.txt` pins `0.115.0 / 2.9.2 / 2.2.3 / 1.26.4 / 1.5.2`. The 319-test suite passes on the **installed** stack, but a fresh `pip install -r requirements.txt` (what `docs/RESEARCH_REPRODUCIBILITY.md` describes) yields the older stack, and `pandas`/`numpy` crossed a major version. **Human decision required:** either (a) `pip install --force-reinstall -r requirements.txt` and re-run the suite to reproduce on the documented stack, or (b) deliberately bump the pins, re-run, and re-freeze `RESEARCH_REPRODUCIBILITY.md`. Not changed here — this is an environment-strategy call for the maintainer.
- **ISSUE-4 — `scipy` is a direct dependency but not declared.** `multi_scenario_service` / risk-calibration code `import scipy.stats` directly; `scipy` appears only transitively via scikit-learn. It should be an explicit line in `requirements.txt` (resolve together with ISSUE-3 so the pin is chosen deliberately).

### LOW
- `docs/RESEARCH_REPRODUCIBILITY.md` "Frozen at commit `eb7d392`" is stale (10+ later tasks each recorded their own state); the dependency line describes the file accurately but not the drifted environment (ISSUE-3).
- `docs/FINAL_DATASET_INVENTORY.md` "209 passed / Alembic 0006" verification table is a dated snapshot (pointer note added in the previous audit).
- ESLint: 1 pre-existing unused-eslint-disable-directive warning in `frontend/src/lib/auth-context.tsx` (unrelated to this work).
- Local scratch files `rsme_test.db`, `tunnel.log`, `backend/dev_cov.db` removed (gitignored; never tracked).

### HUMAN DEPENDENCY  *(cannot be solved by code)*
- ≥ 5 genuine `REAL_INDIAN_SME_OUTCOME` matched records (recruit real Indian SMEs).
- A legitimately configured LLM provider + key for `docs/REAL_LLM_VALIDATION_PROTOCOL.md`.
- Institutional / legal review for SME data collection.
- (Optional) a free `DATA_GOV_IN_API_KEY` for AGMARKNET.

---

## 35. FINAL DECISION

| Question | Answer |
|---|---|
| Is the entire application working end-to-end? | **YES** |
| Are there any critical bugs? | **NO** |
| Are there any high-severity bugs? | **NO** |
| Is the research infrastructure functioning? | **YES** |
| Is production still R0/D0? | **YES** |
| Were any historical experiment results changed? | **NO** |
| Were any production models changed? | **NO** |
| Was any real SME data fabricated? | **NO** |
| Is the project ready for an implementation freeze? | **YES** |

> **PROJECT FUNCTIONALLY VERIFIED — IMPLEMENTATION FREEZE RECOMMENDED.**

The two defects found (BUG-1 upload crash, BUG-2 cosmetic version string) are
fixed with a regression test and full suite green. The only open items are one
MEDIUM reproducibility decision about dependency pins (maintainer's call) and
the human-dependent real-world validation inputs. No architecture change, no
new experiment, no fabricated data, no production-default change.

Preparing the research paper is a **separate** task and was not started here.

## Git commit

`<filled on commit>`
