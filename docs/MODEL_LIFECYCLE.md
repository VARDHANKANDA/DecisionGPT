# Model and dataset lifecycle

Applies to the registered forecasting and churn models (`models/`, the `models` table). Implemented 2026-10-15; tests:
`tests/integration/test_model_lifecycle.py`, `tests/unit/test_ml_production_alignment.py`.

## 1. States

```
trained (file registry)  --sync-->  candidate  --validate-->  validated  --promote (actor + reason)-->  active
                                         \--validate (blocking check fails)--> rejected
active  --superseded by a promotion--> archived        archived --rollback--> active (previous version)
```

* **Registering is not deploying.** `POST /research/models/sync` registers every `(model_name, version)` in `registry_index.jsonl` as a
  `candidate`. Re-running the sync, or training a newer version, never changes what is deployed.
* **One bootstrap exception:** if a model name has *no* active version, its newest version is activated once and logged as
  `bootstrap_activation` (actor `system:sync`), so a fresh installation has something to serve. Nothing else is activated automatically.
* **Only `active` models are used for inference.** `select_forecast_model` / `select_best_model` read active rows only, and compare candidates
  on recorded *validation* metrics when every candidate has them.

## 2. Artifacts
* Versions are **immutable**. `save_model_artifact` raises `ArtifactExistsError` instead of overwriting; the trainers and the Training
  Center allocate `next_version(model_name)` (looks at the artifact directory, the index and the database).
* Writes are **atomic**: temp file in the same directory, flush + fsync, `os.replace`; the index line is one fsynced append. An
  interrupted run leaves no partial artifact and no index line (tested).
* Each new model has a `run_metadata.json` sidecar: dataset sha256, split boundaries, seed, parameters, feature list, package versions,
  git revision, label provenance. It is copied into `models.lifecycle_json` at sync.
* Historical versions (`v1`) and `experiments/ml_benchmark_v1/HISTORICAL_HASHES.json` artifacts are never rewritten.

## 3. Automated validation (`POST /research/models/{id}/validate`)
Blocking checks (all must pass): artifact loads; it accepts the current feature contract's columns in order and returns finite output;
`dataset_version` recorded; `feature_version` equals the current contract version; stored feature list equals the contract; validation
metrics present; **forecasting:** `val_mae` beats the naive lag-1 forecast on the *same* validation block; **churn:** `val_roc_auc` and test
`roc_auc` ≥ 0.60; no regression beyond 5% against the active model **when measured on the same dataset**; ≥ 200 training rows when recorded.

Warnings (recorded, shown, not blocking): trained on synthetic platform data only; churn output is a score, not a calibrated probability;
comparison with the active model is not like-for-like (different datasets). The thresholds are deliberately modest and live in
`model_lifecycle_service.py`; stricter bars need real-business data to be defined honestly.

## 4. Promotion and rollback
* `POST /research/models/{id}/promote {"reason": ...}`: needs `validated`, a non-empty reason; archives the previous active version in the
  **same transaction** (never zero or two active versions). Actor = the signed-in admin (or `research-token`); recorded in
  `model_lifecycle_events` and `lifecycle_json.promotion`.
* `POST /research/models/rollback {"model_name", "reason"}`: re-activates the version that was active before the current one, after
  checking its artifact still loads; a version that was itself rolled back from is never a target; refused when nothing earlier exists.
* `GET /research/models/{id}/history`: the ordered event log for that model name.
* There is **no automatic promotion**, including after a successful training command, and no force flag.

## 5. Data side
* Raw uploads and downloaded datasets are never modified; processed outputs are new files with checksums (`DATASET_REGISTRY.json`,
  research preprocessing run records with config, rows in/out, input/output sha256).
* Upload limits: `MAX_UPLOAD_BYTES` (25 MB) and `MAX_UPLOAD_ROWS` (200,000) per file; a violation fails the job with a plain message and
  stores nothing. The request body is read at most limit + 1 bytes.
* Public datasets, synthetic data and tenant data are stored and labelled separately (`data/external`, `data/platform`, business tables).

## 6. What still needs real-world validation
No model has been validated on real SME outcomes. Every registered model was trained on synthetic platform data; the lifecycle makes that
visible (warning on validation, label provenance and `trained_on` in API responses) but cannot make it good. See
`docs/PRODUCTION_ML_ROADMAP.md`.


## 7. Applicability and validation status (added 2026-10-15)
* Each model has an applicability record (provenance, target, units, aggregation, population, task/horizon, eligibility flags with reasons).
  New training runs record it (`run_metadata.applicability`); legacy models get an inferred record marked `source = inferred`.
* Validation gains a blocking check `applicability_recorded` (an inferred record is not evidence) and a non-blocking
  `eligible_for_production_use` warning. A synthetic-trained model can pass validation and still be ineligible for business use.
* `validation_status` is exposed on every model: `validated`, `rejected`, `not_validated`, or `not_validated_bootstrap` for the first version
  activated by the bootstrap rule. The bootstrap rule is unchanged (backward compatible) but never labels a model validated.
* Ordinary tests do not train, replace or promote production models: the suite uses temporary registries and result directories.
See `docs/BUSINESS_FORECASTING.md`.

## 8. Artifact integrity (added with the real-world validation phase)

* A `sha256` of `model.joblib` is recorded in `lifecycle_json.artifact` when a version is registered (`system:sync`) or trained in the
  Training Center, with the `basis` (`at_registration`, `at_training`).
* Versions registered before this existed have no hash. Validation pins the current hash and labels it `pinned_at_validation`
  (promotion uses `pinned_at_promotion` if validation predates the change): it detects a later swap but cannot prove the file equals what
  training produced, and the check says so.
* `validate` adds an `artifact_integrity` check (blocking when a recorded hash no longer matches). `promote` and `rollback` refuse a
  mismatching artifact with the recorded and current hash prefixes in the message. A missing file is still reported by the existing load
  check.
* Evaluation (`/validation/*`, section 6 of `REAL_WORLD_VALIDATION_PLAN.md`) never reads or writes lifecycle state.

