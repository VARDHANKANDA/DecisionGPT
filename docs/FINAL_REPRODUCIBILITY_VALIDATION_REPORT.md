# Final Reproducibility Validation Report

**Task:** Final reproducible-environment validation (dependency audit + clean-room
rebuild + full re-validation). No research paper is written in this task.

**Date:** 2026-08-30
**Baseline commit (pre-task HEAD):** `7fa543b` ("Record commit hash in project health report")
**Validation Python:** 3.12.0 · **Validation venv:** `backend/.venv_b1` (fresh, throwaway — deleted at end of task)

---

## 1. Dependency decision and why

### 1.1 What was inspected

| Source | Finding |
|---|---|
| `backend/requirements.txt` | The **only** dependency specification. 22 pinned packages + 3 test pins. |
| `pyproject.toml` / `setup.cfg` / `setup.py` | **None present.** |
| Lock files (`requirements.lock`, `pip-tools`, `poetry.lock`, `Pipfile.lock`, `uv.lock`) | **None present.** |
| `backend/Dockerfile` | `FROM python:3.11-slim`; `pip install --no-cache-dir -r backend/requirements.txt`. Defines the intended deployment stack = the pinned requirements. |
| CI config (`.github/`, `.gitlab-ci.yml`, etc.) | **None present.** No CI-pinned stack to reconcile against. |
| `frontend/package-lock.json` | Present and committed → `npm ci` is reproducible. |
| `pytest.ini` | `testpaths = tests`, `pythonpath = backend .`. No dependency assertions. |
| Direct third-party imports (backend + `ml/`) | `fastapi, pydantic, pydantic_settings, sqlalchemy, alembic, psycopg, starlette, pandas, numpy, scipy, sklearn, xgboost, shap, joblib, holidays, httpx, tenacity, openpyxl, pyarrow, dateutil, uvicorn, multipart` |

### 1.2 The documented stack cannot install (Option A is impossible)

`requirements.txt` pinned `numpy==1.26.4` **and** `shap==0.52.0`. `shap==0.52.0`
declares `numpy>=2`. `pip install -r backend/requirements.txt` therefore fails
with `ResolutionImpossible` — the frozen spec is internally inconsistent and has
never been installable as written. (`pandas==2.2.3` additionally requires
`numpy>=1.26.0` and, on Python ≥3.12, resolves toward numpy 2.x.)

Per the task rule *"If the documented stack cannot install cleanly, STOP and
diagnose rather than silently changing pins"* — the conflict was diagnosed to the
exact package pair before any pin was touched.

### 1.3 Decision: **Option B, minimal** — repair the inconsistency, declare the direct deps

The smallest coherent change that makes the spec installable **and** keeps every
independently-validated pin:

| Line | Before | After | Reason |
|---|---|---|---|
| numpy | `numpy==1.26.4` | `numpy==2.5.2` | Forced by `shap==0.52.0` (`numpy>=2`). `pandas==2.2.3` and `scikit-learn==1.5.2` both officially support numpy 2.x. This is the **only** version pin changed. |
| scipy | *(absent — transitive via scikit-learn)* | `scipy==1.18.1` **(new, explicit)** | Directly imported by `app/services/multi_scenario_service.py`, `risk_calibration_service.py`, `ml/causal/granger.py`. A direct import must be a declared dependency. |
| joblib | *(absent — transitive via scikit-learn)* | `joblib==1.5.3` **(new, explicit)** | Directly imported by `app/services/forecast_service.py`, `churn_service.py`, `ml/pipeline` + registry model load/save. |

`fastapi==0.115.0`, `pydantic==2.9.2`, `pandas==2.2.3`, `scikit-learn==1.5.2`,
`xgboost==3.4.0`, `shap==0.52.0` and all others are **unchanged** and were
confirmed to resolve to their exact pins in the clean environment
(`starlette==0.38.6` comes in transitively, matching fastapi 0.115.0's range).

Only genuinely-direct imports were added. Transitive-only packages
(`threadpoolctl`, `slicer`, `cloudpickle`, `numba`, `llvmlite`, …) were **not**
added.

### 1.4 One project-code change required by the numpy 2.x move

`ml/preprocessing/india_festival_adapter.py` computed festival-distance features
via `int(timedelta64[D] / pd.Timedelta(days=1))`. Under numpy 2.x that division
path is deprecated and emitted **3272 `DeprecationWarning`s** per test session
(*"The 'generic' unit for NumPy timedelta is deprecated, and will raise an error
in the future"*). Fixed to `int((a - b).astype("int64"))` — behaviour-identical
(the difference is already `timedelta64[D]`, so the int cast **is** the exact day
count), no deprecated path. A regression assertion was added to
`tests/unit/test_india_context_adapters.py` (day counts are integer dtype; the
day before a festival is exactly `1`). No research number changed; no test
weakened.

---

## 2. Clean environment — Python and package versions

Fresh venv `backend/.venv_b1`, created with `python -m venv`, **not** derived
from any pre-existing/contaminated environment.

```
Python 3.12.0

alembic==1.13.3            openpyxl==3.1.5           pytest-asyncio==0.24.0
fastapi==0.115.0          pandas==2.2.3            pytest-cov==5.0.0
holidays==0.103           psycopg==3.2.2           python-dateutil==2.9.0.post0
httpx==0.27.2             pyarrow==17.0.0          python-multipart==0.0.9
joblib==1.5.3             pydantic==2.9.2          scikit-learn==1.5.2
numpy==2.5.2              pydantic-settings==2.5.2 scipy==1.18.1
shap==0.52.0              SQLAlchemy==2.0.35       starlette==0.38.6
tenacity==9.0.0          uvicorn==0.30.6         xgboost==3.4.0
pytest==8.3.3
```

Every pin in `requirements.txt` resolved to **exactly** its pinned version.
Deployment image target remains Python 3.11 (`backend/Dockerfile`); the corrected
spec also installs and passes the full suite on 3.12.0, matching
`docs/RESEARCH_REPRODUCIBILITY.md`.

---

## 3. Installation result — **PASS**

| | |
|---|---|
| `pip install -r backend/requirements.txt` (corrected) | **Success**, exit 0 |
| Dependency conflicts | **0** |
| Failed installations | **0** |
| Warnings | none blocking (standard build-isolation notices only) |
| `pip check` | no broken requirements |

`pip install -r backend/requirements.txt` against the **pre-task** file was also
run and confirmed to fail (`ResolutionImpossible`, `shap 0.52.0 → numpy>=2` vs
`numpy==1.26.4`), establishing that the change was necessary, not cosmetic.

---

## 4. Backend test suite — exact result

Command: `python -m pytest -q -p no:cacheprovider` (from repo root; `pytest.ini`
sets `testpaths = tests`, `pythonpath = backend .`), clean `.venv_b1`.

```
319 passed, 1 skipped, 30 warnings in 1098.23s (0:18:18)
```

* **Matches the expected baseline `319 passed, 1 skipped`.**
* The **1 skipped** test is `tests/unit/test_india_agmarknet_adapter.py::test_committed_india_processed_file_trains`
  — skipped because `data/external/india_agmarknet/processed/india_agmarknet_forecasting.csv`
  is not built (building it needs a `data.gov.in` API key). The API key was **not**
  invented; the skip is correct and expected.
* **Warnings fell from 6583 → 30** after the festival-adapter fix. The 30
  residual warnings are third-party (`pytest-asyncio` loop-scope notice,
  `pydantic` protected-namespace `model_` notice) plus one pre-existing
  `DeprecationWarning` inside a *test* assertion
  (`tests/unit/test_india_business_adapters.py:68`, `d.diff() == pd.Timedelta(days=1)`);
  none is in shipped project code and none is a failure. Left untouched under
  strict change control.

### 4.1 One clean-env failure, root-caused, fixed without weakening anything

First clean-venv run: `1 failed, 318 passed` —
`test_churn_with_sufficient_customers_and_registered_model` failed with
`InconsistentVersionWarning: Trying to unpickle estimator … from version 1.9.0
when using version 1.5.2`. **Root cause:** the gitignored `models/*.pkl` build
products had been trained by a contaminated venv (scikit-learn 1.9.0). **Fix:**
deleted `models/` and let the pytest session fixture `_ensure_baseline_models`
retrain the forecasting + churn baselines at seed 42 on scikit-learn 1.5.2. No
test code changed. Re-run: `319 passed, 1 skipped`. The retrained model metrics
reproduce the frozen values **exactly** (§7).

---

## 5. Frontend — build / tsc / eslint

Using the committed `frontend/package-lock.json` (Node v24.14.0, npm 11.9.0).

| Step | Command | Result |
|---|---|---|
| Install | `npm ci` | **PASS** — 402 packages, 0 vulnerabilities |
| Production build | `npm run build` (`next build`) | **PASS** — compiled successfully in 19.1s, 26 routes prerendered, exit 0 |
| Types | `npx tsc --noEmit` | **PASS** — exit 0, no errors |
| Lint | `npm run lint` (`eslint`) | **PASS** — 0 errors, 1 warning (pre-existing: unused `eslint-disable` directive in `src/lib/auth-context.tsx:22`; not introduced or touched by this task) |

---

## 6. End-to-end audit

Command: `python scripts/audit_e2e.py` (clean `.venv_b1`, `dev.db`).

```
AUDIT COMPLETE — no assertion failures.
```

Covers: business onboarding → upload → analytics → goals → decision analyze →
digital-twin simulation → causal graph → agent evaluation → paper-results tables
→ research exports (CSV+Markdown) → access control (cross-business 403, SME→research
403, unauth→research 403, admin→research 200). The `digital_twin_evaluation`
paper table correctly reports `available=False — 0/5 genuine REAL_INDIAN_SME_OUTCOME
records` (Table 2 stays NOT READY).

---

## 7. Database migration round-trip

Clean SQLite DB, `.venv_b1`, Alembic.

| Step | Result |
|---|---|
| `alembic upgrade head` (from empty: `0001 → 0002 → … → 0007`) | **OK** |
| `alembic current` | `0007 (head)` |
| `alembic downgrade base` (`0007 → … → 0001 → base`) | **OK**, no errors |
| `alembic upgrade head` again (`base → … → 0007`) | **OK**, no errors |
| Table count at head | **30** |

Head is `0007` as expected. **No schema change was made** — no defect was found.

---

## 8. Experiment reproducibility (frozen experiments preserved)

Representative deterministic experiments recomputed in the clean environment and
compared to the stored/committed values. **No stored result file, experiment ID,
dataset version, model version, seed, or metric in
`experiments/experiment_manifest.json` was modified** (`git diff` on
`experiments/` is empty; manifest byte-identical).

| Experiment | Seed | Metric | Stored / documented | Clean-env recompute | Match |
|---|---|---|---|---|---|
| Forecasting — naive | 42 | MAE / RMSE / MAPE | 24.660 / 38.275 / 15.46% | 24.660 / 38.275 / 15.46% | **exact** |
| Forecasting — linear | 42 | MAE / RMSE / MAPE | 17.291 / 25.511 / 12.49% | 17.291 / 25.511 / 12.49% | **exact** |
| Forecasting — xgboost | 42 | MAE / RMSE / MAPE | 15.139 / 21.863 / 10.30% | 15.139 / 21.863 / 10.30% | **exact** |
| Churn — logistic regression | 42 | F1 / ROC-AUC | 0.669 / 0.798 | 0.669 / 0.798 | **exact** |
| Churn — random forest | 42 | F1 / ROC-AUC | 0.661 / 0.793 | 0.661 / 0.793 | **exact** |
| Churn — xgboost | 42 | F1 / ROC-AUC | 0.658 / 0.792 | 0.658 / 0.792 | **exact** |
| Causal discovery | 42 | precision / recall / SHD | 0.40 / 1.00 / 3 | 0.40 / 1.00 / 3 | **exact** |

**No dependency-induced numerical difference was observed.** The `numpy 1.26 →
2.5` move produced no metric drift on any recomputed experiment; the retrained
baseline model artifacts are numerically identical to the frozen metrics. No
stored result was updated.

The 16 experiment IDs in the manifest are unchanged:
`70617412`, `b8516eef`, `ba56e42b`, `f24abc1b`, `db58455b`, `0e1bd8dc`,
`c58c4537`, `2f7da989`, `7616425f`, `36d0d404`, `21e8e800`, `c2b3a2fa`,
`be392694`, `675cf17e`, `1fcca452`, `a32933ca`.

---

## 9. Production invariants — confirmed

| Invariant | Expected | Observed |
|---|---|---|
| `PipelineOptions().risk_model` | `None` | `None` |
| `PipelineOptions().risk_penalty_lambda` | `1.0` | `1.0` |
| `PipelineOptions().risk_penalty_in_ranking` | `True` | `True` |
| `PipelineOptions().label()` | `full` (R0 / D0) | `full` |
| Active v1 models | 6 | 6 — `churn_{logistic_regression,random_forest,xgboost}` v1, `sales_forecast_{linear,naive,xgboost}` v1 |
| v2 models | archived, inactive | 3 archived (`training_center` source), unchanged |
| `ExperimentRun` rows | 16 | 16, all `seed=42`, all `completed` |
| `experiments/experiment_manifest.json` | byte-identical | byte-identical (`git diff` empty) |
| `DecisionOutcome` rows (REAL_INDIAN_SME_OUTCOME) | 0 | **0** |
| Table 2 (`digital_twin_evaluation`) | NOT READY | NOT READY (0/5 genuine records) |
| Real LLM (`settings.llm_enabled`) | BLOCKED / False | **False** (`llm_provider` unset, `llm_api_key` unset) |
| R3 | EXPERIMENTAL / NOT PROMOTED | EXPERIMENTAL / NOT PROMOTED (`docs/REAL_EVIDENCE_STATUS_REPORT.md` unchanged) |
| Alembic head | `0007` (30 tables) | `0007` (30 tables) |

---

## 10. Research integrity — confirmed

The dependency cleanup did **NOT**:

- regenerate any experiment — `git diff experiments/` is empty
- alter any experiment ID — 16 IDs unchanged
- overwrite any stored result — no result file touched; recomputes were compared, not written back
- alter any synthetic dataset — no `data/platform/**` change
- alter Benroshan real e-commerce data — no change
- alter AGMARKNET status — still not built; its one test still skips (API key not invented)
- alter any `DecisionOutcome` record — count still 0; none created
- create any synthetic / demo outcome — none created
- create any fake LLM result — LLM stays disabled; template mode not reported as real-LLM evidence
- promote R3 — still experimental / opt-in only
- change any production model — 6 active v1 models unchanged (baselines retrained at seed 42 to the **same** frozen metrics after the sklearn-version contamination was removed)
- rewrite any research conclusion — `docs/RESEARCH_REPRODUCIBILITY.md` edit is limited to the dependency table + a note that gitignored `.pkl`s are rebuilt in a clean env

### Files changed in this task (5)

| File | Change |
|---|---|
| `backend/requirements.txt` | `numpy==1.26.4 → 2.5.2` (forced by shap); **+** `scipy==1.18.1`, `joblib==1.5.3` (declare direct imports). No other pin changed. |
| `ml/preprocessing/india_festival_adapter.py` | numpy-2 deprecation fix (`.astype("int64")` instead of `/ pd.Timedelta(days=1)`), behaviour-identical. |
| `tests/unit/test_india_context_adapters.py` | +regression assertions for the above. No test weakened. |
| `docs/RESEARCH_REPRODUCIBILITY.md` | dependency table updated (numpy pin, scipy/joblib declared, why); clean-env model-rebuild note. No research conclusion changed. |
| `docs/FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md` | this file (new). |

No architectural refactoring was performed.

---

## 11. Remaining human dependencies (not blockers to the freeze; out of scope for automation)

1. **Genuine Indian SME decision outcomes** — Table 2 (`digital_twin_evaluation`)
   stays `NOT READY` until ≥ 5 real `REAL_INDIAN_SME_OUTCOME` records with matched
   predicted/actual values are collected through the existing import workflow
   (`scripts/import_real_sme_outcomes.py`). Currently 0. No synthetic outcome may
   be substituted.
2. **Real LLM provider credentials** — `settings.llm_enabled` is `False`
   (`LLM_PROVIDER` / `LLM_API_KEY` unset). Real-LLM validation is `BLOCKED` per
   the frozen `docs/REAL_LLM_VALIDATION_PROTOCOL.md`. By architecture a real LLM
   affects goal parsing + narration only — not decision outcomes, risk
   calibration, or R0/R3.
3. **AGMARKNET dataset (optional)** — needs a `data.gov.in` API key to download +
   build `india_agmarknet_forecasting.csv`; until then one adapter test skips
   (expected).
4. **Institutional / legal review** — any real-SME data collection and any
   publication of results is a human governance step outside this validation.

---

## 12. Final decision

| Question | Answer |
|---|---|
| Is the environment reproducible from a clean state? | **YES** — fresh Python 3.12.0 venv, `pip install -r backend/requirements.txt` succeeds with 0 conflicts. |
| Is the dependency specification now correct? | **YES** — internally consistent, installable, every pin resolves exactly. |
| Are direct dependencies (incl. SciPy) explicitly declared? | **YES** — `scipy` and `joblib` added as explicit pins; no transitive-only packages added. |
| Is the backend test suite passing? | **YES** — `319 passed, 1 skipped` (the skip is the API-key-gated AGMARKNET test). |
| Is the frontend build passing? | **YES** — `npm ci` + `next build` + `tsc --noEmit` clean; eslint 0 errors (1 pre-existing warning). |
| Is the E2E audit passing? | **YES** — `audit_e2e.py`: no assertion failures. |
| Are DB migrations clean (round-trip)? | **YES** — `0001 → 0007 → base → 0007`, head `0007`, 30 tables, no schema change. |
| Are the frozen experiments preserved and reproducible? | **YES** — forecasting / churn / causal reproduce **exactly**; no stored result modified; manifest byte-identical. |
| Is production still R0 / D0? | **YES** — `risk_model=None`, `risk_penalty_lambda=1.0`, `label()='full'`. |
| Was any experiment overwritten? | **NO.** |
| Was any production model changed? | **NO** — 6 active v1 models unchanged (baselines retrained to identical frozen metrics after removing a stale-pickle contamination). |
| Was any real SME data fabricated? | **NO** — `DecisionOutcome` count still 0. |
| Was any real LLM result fabricated? | **NO** — LLM stays disabled; template mode is not reported as real-LLM evidence. |
| Is the project ready for final implementation freeze? | **YES.** |

## FINAL IMPLEMENTATION AND REPRODUCIBILITY FREEZE — VERIFIED

The research paper is **not** written in this task, by instruction. The next task
is deciding how to structure and write the paper from this verified evidence.
