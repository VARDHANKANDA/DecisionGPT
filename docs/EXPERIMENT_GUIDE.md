# DecisionGPT — Experiment Guide

Reproducible steps to generate **every** research result the paper needs.
Nothing here contains expected metric values — only the commands, the
records they produce, and where each result surfaces in the dashboard and
in Paper Results.

This complements `docs/EXPERIMENT_PLAN.md` (the *what*) with the *how*.

---

## 0. Prerequisites

```bash
# backend deps + DB
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.txt

# Option A — Postgres (production parity), from repo root:
cp .env.example .env                       # DATABASE_URL points at Postgres
docker compose up --build -d postgres
docker compose exec backend alembic upgrade head

# Option B — local SQLite (fastest; migrations verified on SQLite too):
DATABASE_URL=sqlite:///./dev.db python -m alembic upgrade head
# (or: DATABASE_URL=sqlite:///./dev.db python scripts/dev_bootstrap_sqlite.py)
```

Run the API and the Research Console:

```bash
DATABASE_URL=sqlite:///./dev.db uvicorn app.main:app --port 8000      # from backend/
cd frontend && npm install && npm run dev                             # http://localhost:3000/research
```

**Research access** — every `/api/v1/research/**` route needs one of:
- header `X-Research-Token: <RESEARCH_CONSOLE_TOKEN from .env>` (default `change-me-research-console-token`), or
- a bearer token for an `admin` user (`POST /api/v1/auth/register` with `"role":"admin"`), when `AUTH_ENABLED=true`.

In this guide, `RT` is shorthand for `-H "X-Research-Token: $RESEARCH_CONSOLE_TOKEN"`.

**Register the bundled models once** (needed before any SME analytics/decision or the model-performance page):

```bash
cd backend
python -m ml.training.train_forecasting            # writes models/ + registry_index.jsonl
python -m ml.training.train_churn
curl -X POST localhost:8000/api/v1/research/models/sync $RT     # syncs file registry -> DB, marks active
```

**Whole-pipeline smoke test** (drives all 18 SME steps + the research pipeline against an in-memory DB):

```bash
python scripts/audit_e2e.py                        # from repo root
```

---

## Reproducibility record (applies to every experiment below)

Every `POST /api/v1/research/experiments/run` writes one `experiment_runs`
row containing: `id`, `experiment_type`, `experiment_name`, `random_seed`,
`configuration_json`, `dataset_version`, `model_versions_json`,
`status` (`pending→running→completed|failed`), `started_at`, `completed_at`,
`error_message`, `metrics_json`, `created_at`.

Pull the full manifest for a methods appendix:

```bash
curl -s localhost:8000/api/v1/research/experiments/manifest $RT > experiment_manifest.json
```

(Also available in the UI: **Research → Experiments → “Download reproducibility manifest”**.)

---

## Experiment 1 — Predictive Model Performance  (Paper Table 1)

**Required dataset:** `data/platform/forecasting/sales_timeseries.csv`
(`platform-forecasting-v1`, synthetic, 40 series × 730 days) and
`data/platform/churn/customers.csv` (`platform-churn-v1`, synthetic, 6000 rows).
Or upload your own via **Research → Dataset Registry → Upload** (CSV/XLSX/Parquet;
forecasting needs columns `series_id,date,units_sold,price,marketing_spend,promotion_flag`;
churn needs `tenure_days,recency_days,frequency,avg_order_value,monetary_value,churned`).

**Preprocessing (automatic):** `clean_dataframe` (parse dates, dedupe),
`build_forecasting_features` (lag_1/lag_7/rolling means — backward-only,
no leakage), `chronological_split` (unique-date boundaries; train ends
strictly before test starts). Churn: `build_churn_features`,
`train_test_split(stratify=y)`; `support_tickets` / `discount_usage_rate`
are deliberately excluded (an SME cannot supply them).

**Run — retrain all baselines + candidate on the platform datasets:**

```bash
curl -X POST localhost:8000/api/v1/research/experiments/run $RT \
  -H "Content-Type: application/json" \
  -d '{"experiment_type":"forecasting","configuration":{"seed":42}}'
curl -X POST localhost:8000/api/v1/research/experiments/run $RT \
  -H "Content-Type: application/json" \
  -d '{"experiment_type":"churn","configuration":{"seed":42}}'
```

**Or single-model on a registered dataset** (**Research → Training Center**, or):

```bash
curl -X POST localhost:8000/api/v1/research/training/run $RT -H "Content-Type: application/json" \
  -d '{"task":"forecasting","model_type":"xgboost","dataset_version_id":"<VERSION_ID>","seed":42}'
```

**Records produced:**
- `experiment_runs` row(s) (forecasting / churn) with `metrics_json` keyed by model type.
- `training_runs` rows (one per Training-Center run) + one `models` row each (`status=experimental`).
- Model artifacts under `models/<name>/<version>/` + `models/registry_index.jsonl` (for the CLI path).

**Metrics produced:** forecasting `MAE`, `RMSE`, `MAPE`; churn `precision`,
`recall`, `f1`, `roc_auc` (+ `shap_global_importance` for tree models).

**Where it appears:**
- **Research → Model Performance** — summary, forecasting table + chart, classification table + chart, training history, filters.
- **Research → Model Registry** — per-version metrics + promote/archive.
- **Paper Results → “Table 1 — Predictive Model Performance”** (`available` once any model is registered).
- Export: `POST /research/export {"table":"forecasting_performance"|"churn_performance","format":"csv|json|markdown|latex"}`.

---

## Experiment 2 — Digital Twin Prediction Evaluation  (Paper Table 2)

**Required data:** at least one **recorded actual outcome** for a real
decision. There is no synthetic substitute — the page shows an explicit
empty state until an SME records an outcome.

**Steps (UI or API):**
1. Create a business + upload data (or `POST /api/v1/businesses/demo` for a
   fully-seeded synthetic Indian D2C business — its data is clearly marked synthetic).
2. Create a goal → `POST /businesses/{id}/goals {"text":"Increase revenue by 10% in 3 months"}`.
3. Analyse → `POST /businesses/{id}/decisions/analyze {"goal_id":"..."}` (persists the Decision, the selected strategy's `digital_twin_simulations` row, agent runs, causal context).
4. Record the real result → `POST /businesses/{id}/decisions/{decision_id}/outcome`
   `{"actual_outcome":{"revenue":<num>,"profit":<num>,"orders":<num>,...}}`.
   The **Decision** page and **Decision History** page both generate this
   form from the metrics the decision actually predicted.

**On step 4 the feedback loop runs automatically** (in its own transaction,
after the outcome is safely stored; it never retrains a model):
- `digital_twin_evaluation_service.evaluate_decision_outcome` → one
  `prediction_evaluations` row: `decision_id`, `outcome_id`,
  `simulation_id`, `strategy_name`, `model_versions_json`,
  `causal_graph_version`, per-metric predicted/actual/error/`abs_pct_error`
  (`metrics_json`), plus denormalised `revenue_error` / `revenue_abs_pct_error`.
- `causal_feedback_service.apply_outcome_feedback` — see Experiment 3b.

**Backfill** older outcomes that predate the loop:

```bash
curl -X POST localhost:8000/api/v1/research/digital-twin-evaluation/backfill $RT
```

**Metrics produced (revenue change, and profit where recorded):** `MAE`,
`RMSE`, `MAPE` (MAPE only where the actual change ≠ 0). Charts: predicted
vs actual, error distribution, error over time.

**Where it appears:**
- **Research → Digital Twin Evaluation** — summary, metric blocks, 3 charts, traceable detail table.
- **Paper Results → “Table 2”** (`available` once ≥1 matched outcome exists).
- Export: `{"table":"digital_twin_evaluation","format":"..."}` — falls back to persisted `prediction_evaluations` rows if no `digital_twin` experiment was run.
- Optional: `POST /research/experiments/run {"experiment_type":"digital_twin"}` to snapshot the aggregate into an `experiment_runs` row.

---

## Experiment 3 — Causal Graph Evaluation  (Paper Table 3)

### 3a. Method validation (synthetic ground truth)

```bash
curl -X POST localhost:8000/api/v1/research/experiments/run $RT -H "Content-Type: application/json" \
  -d '{"experiment_type":"causal","configuration":{"seed":42}}'
```

**What it does:** generates a time series with a *known* structure
(`A→B→C` at lag 1, `D` independent noise), runs the same Granger method
`causal_graph_service` uses, and scores recovery.

**Metrics produced:** `precision`, `recall`, `structural_hamming_distance`,
`true/false positives/negatives`, `predicted_edges`, `ground_truth_edges`
(F1 computed in the dashboard from precision/recall).

### 3b. Real graph state + conservative outcome feedback

- Every analysed goal builds/updates a per-business `causal_graphs` +
  `causal_edges` graph (evidence: `assumed` → `observational` →
  `data_supported`; **`causally_validated` is never auto-assigned**).
- When the SME records outcomes that also include a downstream metric
  (`orders`/`sales` and/or `profit`, not only `revenue`), the feedback
  loop checks **per-edge, per-variable** direction consistency:
  intervention lever → downstream node → hypothesised sign → the actual
  recorded metric for that node. After **≥ 3** interventions move both
  ends of a specific `assumed` edge consistently (**≥ 2/3**), that one edge
  is lifted to `observational` — nothing more. Each change writes a
  `causal_evidence_updates` row (graph id + new version, edge,
  previous/new level, supporting decision & outcome ids, method,
  per-edge sample size + consistency count, timestamp) and a **new
  `causal_graphs` version**.

**Where it appears:**
- **Research → Causal Graph Evaluation** — evidence-level counts across
  stored graphs, per-graph edge tables, the synthetic method-validation
  block (recovered / missing / extra edges), an explicit *“no ground-truth
  causal graph is registered”* state, and the evidence-feedback log.
- **Paper Results → “Table 3”** (`available` once a `causal` experiment has run).
- Export: `{"table":"causal_evaluation","format":"..."}`.

> **Honest limitation:** there is no registered ground-truth causal graph
> for any real business, so quantitative *business-graph* recovery accuracy
> is not reported — only the synthetic method validation is.

---

## Experiment 4 — Decision Architecture Comparison  (Paper Table 4)

```bash
curl -X POST localhost:8000/api/v1/research/experiments/run $RT -H "Content-Type: application/json" \
  -d '{"experiment_type":"decision_architecture","configuration":{"seed":42}}'
# single vs multi-agent slice:
curl -X POST localhost:8000/api/v1/research/experiments/run $RT -H "Content-Type: application/json" \
  -d '{"experiment_type":"multi_agent","configuration":{"seed":42}}'
```

**What it does:** on one controlled synthetic scenario, runs the **real**
production code for four architectures —
**A** prediction only · **B** + Digital Twin · **C** + single agent ·
**D** full DecisionGPT (goal-aware strategies + causal context + 3-agent
round-1 + peer-review round-2 + optimizer). The synthetic business is
created and deleted inside the run and is never visible to any SME.

**Metrics produced per architecture:** `goal_achievement`,
`expected_benefit`, `risk_adjusted_score`, `latency_seconds`
(+ `selected_strategy_name`). `model_versions_json` records the active
forecasting model versions used.

**Where it appears:**
- **Research → Multi-Agent Evaluation** — architecture comparison chart +
  table, single-vs-multi slice, and **debate statistics aggregated from
  real `decisions`** (agents involved, conflicts raised, post-review score
  changes, average confidence, latest-decision detail).
- **Paper Results → “Table 4”**.
- Export: `{"table":"decision_architecture","format":"..."}` (auto-picks
  the latest completed run; pass `"experiment_id"` to pin one).

---

## Experiment 5 — Ablation Study  (Paper Table 5)

```bash
curl -X POST localhost:8000/api/v1/research/experiments/run $RT -H "Content-Type: application/json" \
  -d '{"experiment_type":"ablation","configuration":{"seed":42}}'
```

**What it does:** runs the real pipeline on the same synthetic scenario at
full strength (**A**) and with each component switched off:
**B** without Digital Twin · **C** without Causal Graph · **D** without
Multi-Agent (single blended agent) · **E** without Explainability ·
**F** without Memory. Deltas are measured, never fabricated. On a scenario
with no recorded outcomes, E and F show a genuine zero delta on the
quantitative metrics (they act on trust/understanding, not scoring) — this
is reported as such.

**Metrics produced per config:** `goal_achievement`, `risk_adjusted_score`,
`confidence`; and per comparison vs Full: `delta_goal_achievement`,
`delta_risk_adjusted_score`, `delta_confidence`, plus a `note`.
`model_versions_json` recorded.

**Where it appears:**
- **Research → Ablation Studies** — run control + config table + Δ-vs-Full cards.
- **Paper Results → “Table 5”**.
- Export: `{"table":"ablation","format":"..."}`.

---

## Experiment F — Human Evaluation (not implemented)

`docs/EXPERIMENT_PLAN.md §7` lists an optional human study (understanding,
usefulness, trust, explanation quality). No instrument or data-collection
UI is implemented; run it externally if desired.

---

## Scenario coverage (`docs/EXPERIMENT_PLAN.md §8`)

The synthetic scenario in Experiments 4–5 is a **revenue-growth** scenario.
Marketing-budget / pricing / inventory scenarios are exercised through the
SME pipeline by setting the corresponding goal
(`improve_marketing_roi`, `increase_profit` with `no_price_increase`,
`reduce_inventory_risk`) on a business that has the matching data, then
recording outcomes — those flow into Experiment 2 and Experiment 3b.

---

## One-command sequence to populate all five tables

```bash
cd backend
python -m ml.training.train_forecasting && python -m ml.training.train_churn
curl -sX POST localhost:8000/api/v1/research/models/sync $RT >/dev/null
for E in forecasting churn causal decision_architecture ablation; do
  curl -sX POST localhost:8000/api/v1/research/experiments/run $RT \
    -H "Content-Type: application/json" -d "{\"experiment_type\":\"$E\",\"configuration\":{\"seed\":42}}" >/dev/null
done
# Table 2 additionally needs >=1 real recorded outcome (see Experiment 2).
curl -s localhost:8000/api/v1/research/paper-results $RT | python -m json.tool
```

After this, **Paper Results** shows Tables 1, 3, 4, 5 as `available`;
Table 2 becomes `available` after the first recorded decision outcome.

---

## External benchmark dataset — Indian real-world data (hybrid strategy)

The five experiments above run on **controlled synthetic** data (reproducible
architecture / causal / ablation evaluation). To also evaluate the
**predictive pipeline on real Indian data**, one external benchmark is
integrated through the *existing* Dataset Registry + Training Center — see
`docs/INDIAN_DATASET_INTEGRATION_REPORT.md` and `docs/FINAL_DATASET_INVENTORY.md`.

Strategy: `REAL INDIAN DATA  +  CONTROLLED SYNTHETIC DATA`.

| Registry dataset | Geography | Category | Task | Notes |
|---|---|---|---|---|
| `external-india-e-commerce-forecasting` | **India** | `INDIA_REAL_BUSINESS` | small forecasting | Benroshan Kaggle e-commerce (CC0). Real, ~500 orders / 12 months. `price` is a DERIVED implied unit price. Small — indicative only. |
| `external-india-e-commerce-category-state-analytics` / `-target-attainment` | India | `INDIA_REAL_BUSINESS` | analytics | category×state revenue/profit/margin; monthly actual vs target. Not trained. |
| `external-india-agmarknet-forecasting` | India (multi-state) | `INDIA_AGRICULTURAL_PRICE` | **price** forecasting | AGMARKNET daily mandi modal prices, GODL-India. `units_sold` carries the modal price — **no quantity field**. `DATA_PENDING`. |
| `external-india-customer-behaviour-simulated-purchase-prediction` | India | `SYNTHETIC_INDIAN_CONTEXT` | purchase prediction | Kundan Kaggle (CC BY 4.0). **Simulated.** Standalone `scripts/run_india_customer_benchmark.py` — NOT an `MLModel`, NOT in the Training Center. |

**Retired** (non-Indian, reproducibility only, `--retired` flag):
`external-uci-online-retail-*` (UK), `external-m5-forecasting-benchmark` (USA),
`external-regional-retail-myanmar-forecasting` (Myanmar). See
`data/external/_retired_non_indian/README.md`.

### Reproduce
```bash
# 1a. Indian e-commerce + customer datasets (Kaggle public CC0 / CC-BY, anonymous)
python scripts/download_india_business_datasets.py

# 1b. AGMARKNET raw (public data.gov.in JSON API; slow on the demo key,
#     <1 min with a free DATA_GOV_IN_API_KEY) — optional, DATA_PENDING otherwise
python scripts/download_india_datasets.py

# 2. build processed CSVs (seed 42)
python scripts/build_external_datasets.py                 # india (agmarknet), festivals, macro
python scripts/build_external_datasets.py --only benroshan
python scripts/build_external_datasets.py --only kundan

# 3. register into the existing Dataset Registry (idempotent)
DATABASE_URL=sqlite:///./backend/dev.db python scripts/register_external_datasets.py             # agmarknet
DATABASE_URL=sqlite:///./backend/dev.db python scripts/register_external_datasets.py --only benroshan
DATABASE_URL=sqlite:///./backend/dev.db python scripts/register_external_datasets.py --only kundan

# 4. benchmarks
#    - forecasting through the existing Training Center (status=experimental; active models untouched)
DATABASE_URL=sqlite:///./backend/dev.db python scripts/run_external_benchmarks.py --seed 42                  # agmarknet (if DATA_PENDING -> SKIP)
DATABASE_URL=sqlite:///./backend/dev.db python scripts/run_external_benchmarks.py --only benroshan --seed 42
#    - purchase prediction: standalone, NOT registered as an MLModel
python scripts/run_india_customer_benchmark.py --seed 42
```

The e-commerce / customer / festival / macro processed CSVs are committed, so
steps 3–4 work on a fresh clone without re-downloading. Only AGMARKNET needs
step 1b.

### Where the results appear
- **Research → Dataset Registry** — the Indian dataset shows `Source: External Benchmark - India … (data_type=real)` + `GODL-India`, next to (not merged with) the `SYNTHETIC` platform datasets.
- **Research → Training Center / Model Registry** — one `TrainingRun` + one `experimental` `MLModel` per model_type, with full reproducibility metadata (seed, dataset version label `upload:<slug>:v<n>`, metrics, timings).
- **Research → Model Performance** and **Paper Results → Table 1** — filter by `dataset_version` to compare the synthetic baseline vs the Indian benchmark. Report `REAL INDIAN` and `CONTROLLED SYNTHETIC` rows separately; never average across them.

### Honesty
- No external dataset feeds the SME Digital Twin / Causal Graph / Multi‑Agent engines.
- The Indian dataset is agri-commodity **wholesale price** data — a genuine Indian benchmark, but not SME retail transactions. A real Indian transaction-level / churn dataset is **pending** (see `docs/DATASET_DOWNLOAD_INSTRUCTIONS.md §2`).
- `units_sold` = daily modal price; `price` = 28-day backward rolling median (no leakage); `marketing_spend` / `promotion_flag` = `0` (absent in source — not invented).
- `MAPE` can be noisy on price series with sharp spikes; prefer `MAE` / `RMSE`.

---

## Frozen paper run

The complete frozen experimental evaluation (all **16** experiments — the "7"
here is a point-in-time count from an earlier freeze — seed 42, with results,
negative/zero/missing findings, and per-table READY / NOT READY) is in
**`docs/RESEARCH_EXPERIMENT_REPORT.md`**. Reproduction environment, dataset and
model versions, and the exact command sequence are in
**`docs/RESEARCH_REPRODUCIBILITY.md`**. The machine-readable artifacts are
`experiments/experiment_manifest.json` (`experiment_count = 16`) and
`experiments/paper_results_snapshot.json`.
