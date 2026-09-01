# Final Project Health & Freeze Audit (post voice-access)

**Scope.** One comprehensive engineering / functionality / security /
research-integrity / reproducibility audit of the entire DecisionGPT repository
after the voice-access feature (`44459a9`). No paper written. No experiment
created or modified. No real-SME outcome, real-LLM result, or causal evidence
fabricated. R3 not promoted.

**Baseline commit audited:** `44459a9` ("Add accessible voice interaction").
**Audit commit:** `abe9e2e`.

---

## Executive verdict

> **HEALTHY WITH MINOR ISSUES → READY FOR FREEZE.**

The complete application is functional, secure, reproducible, and scientifically
consistent. The full typed SME journey and the voice journey both work and both
enter the **same** decision path. All frozen research artifacts are unchanged.
One **LOW-severity** UX bug in the voice recognition hook was found and fixed
(with a regression test) during this audit; two stale pre-experiment planning
docs were given a one-line "superseded" pointer. Nothing blocks the freeze.

The only remaining gaps are **human-dependent** (genuine SME outcomes, a real
LLM provider, institutional review, optional AGMARKNET) — not software defects.

---

## Functional status

| Area | Status | Evidence |
|---|---|---|
| Authentication | **OK** | `scripts/audit_e2e.py` step 1 (register + `/me`); `app/api/deps.py` `get_current_user` / `require_user`. |
| Authorization | **OK** | `audit_e2e.py`: SME→research 403, unauthenticated→research 403, admin→research 200. `require_admin` / `require_research_access`. |
| Business isolation | **OK** | `audit_e2e.py`: cross-business access blocked **403**. `require_business_access` keys ownership on `{business_id}`. Voice adds no path around this. |
| Data ingestion | **OK** | `audit_e2e.py` step 3 (360 sales rows) + research dataset upload (v1, 160 rows, valid). |
| Data parsing / capability gating | **OK** | `audit_e2e.py` steps 4–6; `capability_service._FEATURE_RULES` threshold map; `strategy_generation_service` returns an explicit insufficient-evidence result for goals lacking data. |
| Goal parsing | **OK** | `audit_e2e.py` step 5 (`increase_profit`, constraint `no_price_increase` parsed). LLM (when configured) only *structures* the sentence; every field is re-validated against data (`goal_service`). `llm_enabled=False` → deterministic rule-based parse. |
| Decision pipeline | **OK** | `audit_e2e.py` steps 6–13; `POST /businesses/{id}/decisions/analyze` → `decision_service.analyze_goal(db, business_id, goal_id)` with **no options** → `PipelineOptions()` = R0/D0. |
| Simulation (Digital Twin / decision-simulation layer) | **OK** | `audit_e2e.py` step 7 (selected strategy, expected revenue, risk band). `digital_twin_service.simulate_strategy`; `_risk_from_extrapolation` (R0) is the default; R1 only via explicit `risk_model="R1"` (never in production). |
| Association / evidence graph | **OK** | `audit_e2e.py` step 8 (`built=True`, `graph_version=v1`, strongest evidence `assumed`). `causal_context_service` / `causal_graph_service` (pairwise Granger). No auto-promotion. |
| Multi-agent evaluation | **OK** | `audit_e2e.py` steps 9–10 (3 rule-based agents, round-1 + peer review). `app/agents/*` are pure functions — **no LLM call** (`app/agents/base.py`). |
| Risk Manager | **OK** | `audit_e2e.py` (RM in round-1 set; conflicts surfaced). `agents/risk_manager.py` = `clamp(1 − DT_risk − uncertainty − inventory − causal_penalty)`. Rule-based. |
| Optimizer | **OK** | `audit_e2e.py` step 11 (`final_score`, `confidence`, documented `confidence_basis`). `agents/strategy_optimizer.py` fixed `v2` formula `(BA+FA)/2 − λ(1−RM)`, `λ=1`. |
| Explanation | **OK** | `audit_e2e.py` step 12 (`shap_available=True`, 5 local factors). `explainability_service` (SHAP); LLM narration only, post-selection. |
| Memory | **OK** | `audit_e2e.py` step 17 (`decision`, `goal`, `outcome` memory types). `memory_service`. |
| Outcome pipeline | **OK** | `audit_e2e.py` steps 15–16, 18 (outcome recorded via TestClient txn, DT prediction eval persisted with independent `rev_err`, causal feedback `evidence_updates=0`, `causally_validated_edges=0`). `real_sme_outcome_service` enforces PII rejection / anonymisation / India-only / decision-before-outcome / horizon-consistency / duplicate. `DecisionOutcome` in `dev.db` = **0**. |
| Voice input | **OK (1 LOW bug fixed)** | `frontend` vitest 47/47. Mic button; recognition starts only on explicit press; editable transcript review; **no auto-submit**; existing submit handler reused (integration test); Stop / cancel / timeout / unsupported / permission-denied / no-mic fallbacks. Fix: manual Stop with no speech now returns quietly to idle instead of showing a "no speech" error (§Defects VOICE-1). |
| Voice output | **OK** | vitest: opt-in Listen, play/pause/resume/stop, displayed text is what is spoken, `sanitizeForSpeech` strips UUID/bearer/JWT/hex/key-shaped strings before speaking, fallback when synthesis unavailable. No autoplay. |
| Voice language selection | **OK** | `VoiceLanguagePicker` (en/hi/ta → `en-IN`/`hi-IN`/`ta-IN`); localStorage-persisted; sets recognition + synthesis locale (vitest). Recognition accuracy across languages **not measured** — documented as such. |
| Accessibility | **OK** | Semantic buttons; `aria-label` / `aria-pressed` / `aria-describedby` / `aria-live` status; keyboard operable (Tab/Enter/Space, vitest); `focus-visible` outlines; text label beside every icon; ≥44px primary / ≥40px secondary targets; not colour-only; typed fallback always present. |
| Research APIs | **OK** | `audit_e2e.py`: overview, experiments, model performance, DT evaluation, causal evaluation, agent evaluation, 5 exports (csv+markdown) — all read stored `ExperimentRun.metrics_json` / evaluation rows. No hard-coded metric found (`grep` for `0.084` / `0.486` / `2614` in endpoints + `experiment_service` = none). |
| Research dashboard | **OK** | `audit_e2e.py` pages render from API; frontend research pages carry no hard-coded metric (`grep` = only a boolean-driven `"BLOCKED"` label). Real-SME panel / Table 2 status / reproducibility status sourced from `get_real_sme_outcome_report`. |
| Database / migrations | **OK** | Alembic `base → 0007 (7) → base (7) → 0007 (7)`; **30 tables** at head; head = `0007`. No voice migration (7 files `0001`–`0007`, none voice/audio). |
| Models | **OK** | 6 active v1 (`churn_{logistic_regression,random_forest,xgboost}` v1, `sales_forecast_{linear,naive,xgboost}` v1); 3 archived v2 (`sales_forecast_*` v2). Unchanged by the voice task; no retraining. |
| Reproducibility | **OK** | `backend/requirements.txt` internally resolvable (`pip install --dry-run` exit 0); documented pins present (fastapi 0.115.0, pydantic 2.9.2, numpy 2.5.2, pandas 2.2.3, scikit-learn 1.5.2, scipy 1.18.1, joblib 1.5.3, xgboost 3.4.0, shap 0.52.0). 16-experiment manifest byte-identical since the research freeze (`67a92d7`). |

---

## Research integrity

| Invariant | Value | Verified |
|---|---|---|
| Experiment count | **16** | manifest `experiment_count` + 16 unique IDs + 16 `ExperimentRun` rows |
| Experiment IDs | unchanged | `70617412, b8516eef, ba56e42b, f24abc1b, db58455b, 0e1bd8dc, c58c4537, 2f7da989, 7616425f, 36d0d404, 21e8e800, c2b3a2fa, be392694, 675cf17e, 1fcca452, a32933ca` |
| `experiments/experiment_manifest.json` | **byte-identical** since `67a92d7` | `git diff 67a92d7 HEAD` empty; sha256 `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff` |
| `experiments/paper_results_snapshot.json` | metadata-only change (Table-2 "not ready" reason string strengthened to "0/5 genuine REAL_INDIAN_SME_OUTCOME"); **no metric changed**; `available:false` unchanged | `git diff` = +6/-3, all label/reason text |
| `DecisionOutcome` | **0** | `dev.db` query |
| `REAL_INDIAN_SME_OUTCOME` | **0** | `real_sme_outcome_service` report; `PredictionEvaluation` = 0 |
| Table 2 | **NOT READY** | `paper_results_snapshot` `digital_twin_evaluation.available = false` (gate: ≥5 genuine real-SME matched records) |
| LLM status | **BLOCKED** | `llm_provider=""`, `llm_api_key` unset, `llm_model=""` → `llm_enabled = False` |
| Production config | **R0 / D0** | `PipelineOptions()` → `risk_model=None`, `risk_penalty_lambda=1.0`, `risk_penalty_in_ranking=True`, `label()='full'` |
| R1 / R2 / R3 / D1 default | **none is default** | `risk_model` defaults to `None`; every non-default `PipelineOptions(...)` is inside a research service (`ablation_service`, `risk_calibration_service`, `risk_manager_diagnostic_service`, `risk_manager_generalization_service`, `multi_scenario_service`) — none on the production path |
| R3 | **EXPERIMENTAL / NOT PROMOTED** | `docs/REAL_EVIDENCE_STATUS_REPORT.md`, `RISK_MANAGER_CALIBRATION_REPORT.md` verdict; no code change |
| `CAUSALLY_VALIDATED` | **0** | `audit_e2e.py` step 18 (`must be 0`); `causal_feedback_service` never auto-promotes (`MIN_OUTCOMES_FOR_OBSERVATIONAL=3`, `CONSISTENCY_THRESHOLD=2/3`) |
| Active model count | **6** (v1), 3 archived v2 | model registry query |
| Datasets | unchanged | `git diff 6455bf1 HEAD -- data/ ml/` = only `ml/preprocessing/india_festival_adapter.py` (numpy-2 deprecation fix from the reproducibility task, documented) |
| Scientific metrics | unchanged | no experiment re-run; manifest byte-identical |
| Fabricated outcomes | **0** | none created |
| Fabricated LLM results | **0** | none created; template mode never reported as real-LLM |

**Data-category separation** intact: `dataset_category.classify` keeps
`INDIA_REAL_BUSINESS` / `INDIA_PUBLIC_CONTEXT` / `INDIA_AGRICULTURAL_PRICE` /
`SYNTHETIC_CONTROLLED` / `SYNTHETIC_INDIAN_CONTEXT` / `RETIRED_NON_INDIAN`
separate; `REAL_INDIAN_SME_OUTCOME` is its own gated category. Benroshan stays
descriptive real-business data (provenance UNVERIFIED); AGMARKNET stays
`DATA_PENDING`; Kundan stays synthetic Indian-context (not an `MLModel`).

---

## Security

| Check | Result |
|---|---|
| Authentication | Bearer token (`localStorage` `decisiongpt.token`), server-verified (`get_current_user`). Unauthenticated → 403 on protected routes. |
| Authorization | `require_admin` / `require_research_access` gate `/research/**`; SME role → 403. |
| Cross-business isolation | **Enforced** — `require_business_access` checks ownership on the `{business_id}` path param. `audit_e2e.py`: Business A cannot read Business B analytics (403). |
| Research access | SME 403 / unauthenticated 403 / admin 200 (`audit_e2e.py`). |
| **Voice security** | A voice transcript is byte-for-byte a typed request: same field, same `api.*` call, same bearer token, same `{business_id}`. Voice code makes **zero** network calls (`grep fetch/XHR/WebSocket/sendBeacon` in `src/lib/voice` + `src/components/voice` = none) and never touches `MediaRecorder`/`getUserMedia`/`AudioContext` (grep across `frontend/src` = none). No endpoint, header or auth path is added or bypassed. |
| Privacy | No audio captured/stored/uploaded by app code; nothing written to the DB / `DecisionOutcome` / experiment artifacts. On Chromium the browser itself sends audio to its vendor STT service — documented in `docs/VOICE_ACCESSIBILITY.md`, not claimed as "never transmitted". TTS reads only displayed text, after `sanitizeForSpeech` removes ids/tokens/keys. |
| Frontend LLM calls | **none** (`grep openai/anthropic/completions` in `frontend/src` = none). |

---

## Reproducibility

| Step | Result |
|---|---|
| `backend/requirements.txt` resolvable | **PASS** — `pip install --dry-run -r backend/requirements.txt` exit 0; documented pins present and internally consistent (numpy 2.5.2 chosen because `shap==0.52.0` needs numpy≥2 — see `docs/FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md`). |
| Backend `pytest -q` | **319 passed, 1 skipped** (the skip is the API-key-gated AGMARKNET committed-file test). Run on the dev `.venv`; the frozen clean-room result (`.venv_b1`, sklearn 1.5.2) is identical. `InconsistentVersionWarning`s in the dev-venv run are pre-existing version drift (dev `.venv` has sklearn 1.9.0 vs pinned 1.5.2) and do not affect the result — see Remaining human dependencies. |
| Frontend `npm ci` | **PASS** — clean install, 518 packages, from the committed lockfile. |
| Frontend `npm run build` (`next build`) | **PASS** — compiled, 26 routes, in-build TypeScript check clean. |
| Frontend `tsc --noEmit` | **PASS** — exit 0. |
| Frontend `npm run lint` (eslint) | **PASS** — 0 errors, 1 pre-existing unrelated warning (`src/lib/auth-context.tsx:22`). |
| Frontend `vitest run` | **47 passed / 0 failed** (6 files) — includes the VOICE-1 regression test. |
| `scripts/audit_e2e.py` | **PASS** — full 18-step SME flow + research pipeline + 5 exports + access control; "no assertion failures". |
| Alembic `0001 → HEAD → base → HEAD` | **PASS** — head `0007`, 30 tables, round-trip clean, no schema change, no voice migration. |
| Experiment reproducibility | Not re-run (no code path affecting an experiment changed); manifest byte-identical. |

**CI limitation (stated):** the automated environment has no microphone and no
real `SpeechRecognition` / speech service. Voice behaviour is tested with a
deterministic mock (`src/lib/voice/mock-speech.ts`). **Real microphone hardware
was not exercised.** Manual verification on Chrome desktop + Chrome Android for
`en-IN` remains a pre-production human step.

---

## Defects

### VOICE-1 — manual Stop with no speech showed a "no speech" error
- **Severity:** LOW (cosmetic; feature fully functional; the message even ends
  "…or type instead").
- **Description:** In `useSpeechRecognition`, pressing the component's **Stop**
  button before saying anything ended recognition and then displayed
  *"I didn't catch anything. Tap the microphone and try again, or type instead."*
  — treating a deliberate user cancellation as a recognition failure.
- **Root cause:** `onend` could not distinguish a user-initiated `stop()` from
  the recognition service ending on its own; both took the
  `!gotResultRef.current → emitError("no-speech")` branch.
- **Fix (smallest surface):** added `userStoppedRef`, set in `stop()`, reset in
  `start()`. In `onend`, a user-initiated stop now returns quietly to `idle`
  with no error. A recognition service that ends by itself with no result still
  reports "no speech" (unchanged). File:
  `frontend/src/lib/voice/use-speech-recognition.ts` (+6 lines).
- **Regression test:** `frontend/src/components/voice/VoiceInput.test.tsx` —
  *"a manual Stop with no speech is a quiet cancellation, not a 'no speech'
  error"* (asserts no error text, `onError` not called).
- **Re-run:** `vitest run` → 47 passed / 0 failed; `tsc` clean; `eslint` clean;
  `next build` clean. Frozen research artifacts unchanged (frontend-only).

### DOC-1 — stale pre-experiment planning docs
- **Severity:** LOW (documentation hygiene; not an overclaim — the docs state
  hypotheses to be *tested*, not conclusions).
- **Description:** `docs/RESEARCH_SPECIFICATION.md` and `docs/PAPER_OUTLINE.md`
  predate every experiment and carry the original title/RQs/hypotheses (incl.
  H2/H3, which the results **refute**). A casual reader could mistake them for
  current claims.
- **Fix:** one-line "historical / superseded — see
  `docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md`" note added to the top of each.
  No content rewritten. No paper written.

**No other unresolved defects found.** The prior audits' fixes (BUG-1 upload
`data_type`, BUG-2 `vv1` string, the dependency-spec repair, the festival
numpy-2 deprecation) remain in place and verified.

---

## Remaining human dependencies (NOT software bugs)

| # | Item | Why it is not a bug |
|---|---|---|
| 1 | **≥ 5 genuine `REAL_INDIAN_SME_OUTCOME` matched records** | The import pipeline, validation, PII/duplicate/no-leakage checks and the ≥5 gate are all implemented and tested; there is simply no genuine data. This is the only thing that unblocks Table 2 / the Digital-Twin real-outcome evaluation. |
| 2 | **A legitimately configured LLM provider** (`LLM_PROVIDER` + `LLM_API_KEY`) | The real-LLM protocol is frozen (`docs/REAL_LLM_VALIDATION_PROTOCOL.md`); `settings.llm_enabled` correctly reports `False`. No credentials may be invented. By architecture a real LLM affects only goal parsing + narration. |
| 3 | **Institutional / legal review** for collecting anonymised SME decision data | Governance step, outside code. Consent/provenance templates exist. |
| 4 | **AGMARKNET raw pull** (free `DATA_GOV_IN_API_KEY`) — *optional* | Integration + tests present; one adapter test skips until the data is built. Not required for any current result. |
| 5 | **Rebuild the dev `backend/.venv`** from the corrected `requirements.txt` — *optional housekeeping* | The dev venv still has sklearn 1.9.0 (pre-reproducibility-fix); the frozen clean-room venv (`.venv_b1`) that validated the pinned stack was deleted after that task. Tests pass on the dev venv anyway (319/1). The maintainer can `python -m venv` + `pip install -r requirements.txt` at leisure. Documented in `docs/FINAL_REPRODUCIBILITY_VALIDATION_REPORT.md`. |

---

## Paper readiness

**The engineering / research implementation is READY for paper writing** — from
the blueprint (`docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md`) and the literature
foundation (`docs/PAPER_LITERATURE_FOUNDATION.md`). The paper has **not** been
written and is not written here.

**Ready evidence:** Table 1 (predictive performance), Table 3 (causal recovery,
synthetic method validation), Table 4 (architecture comparison), Table 5
(ablation), Table 6 (risk calibration, supplementary); the primary architecture
finding (Digital-Twin simulation is the only component with objective value; the
multi-agent layer significantly *reduces* goal achievement, `p < 0.0001`); the
candidate-space confound discovery + correction (byte-identical result); the
risk-penalty mechanism diagnosis; the reproducibility evidence; the controlled
negative result.

**Not ready / blocked:** Table 2 real predicted-vs-actual evaluation; real-SME
validation; real-LLM validation; causal validation from real interventions; an
explainability / user-understanding study.

**Voice access classification:**
`ACCESSIBILITY FEATURE — NOT SCIENTIFICALLY EVALUATED`. It is absent from the
experiment manifest, changes no metric, produces no `DecisionOutcome`, and the
paper may state only that the modality exists and that "usability and
speech-recognition performance were not evaluated in the present study"
(`docs/VOICE_ACCESSIBILITY.md` §Research note).

---

## Absolute final invariants — all confirmed

```
16 frozen experiments        = unchanged  (16 IDs, 16 ExperimentRun rows)
experiment_manifest.json     = byte-identical since 67a92d7 (sha256 94aa419c…)
DecisionOutcome              = 0
REAL_INDIAN_SME_OUTCOME      = 0
TABLE 2                      = NOT READY
REAL_LLM                     = BLOCKED (llm_enabled = False)
CAUSALLY_VALIDATED           = 0
R3                           = EXPERIMENTAL / NOT PROMOTED
Production                   = R0 / D0
risk_model                   = None
risk_penalty_lambda          = 1.0
active models                = unchanged (6 v1, 3 archived v2)
datasets                     = unchanged
scientific metrics           = unchanged
fabricated outcomes          = 0
fabricated LLM results       = 0
voice                        = accessibility feature only (no DB, no experiment, no metric)
```

---

## Git

Audit changes (frontend-only + docs; no backend, no experiment, no dataset,
no model, no schema):

- `frontend/src/lib/voice/use-speech-recognition.ts` — VOICE-1 fix (+6 lines).
- `frontend/src/components/voice/VoiceInput.test.tsx` — VOICE-1 regression test.
- `docs/RESEARCH_SPECIFICATION.md`, `docs/PAPER_OUTLINE.md` — DOC-1 "superseded"
  pointer notes.
- `docs/FINAL_PROJECT_HEALTH_AND_FREEZE_AUDIT.md` — this report.

Final audit commit hash: `abe9e2e` (this report's hash recorded by the
follow-up commit).
