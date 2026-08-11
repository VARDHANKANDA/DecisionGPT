# DecisionGPT

AI-powered decision-support platform for Indian SMEs, startups, D2C brands, and
e-commerce businesses. DecisionGPT turns business data + a stated goal into an
explainable, risk-aware strategic recommendation — combining predictive
analytics, a Business Digital Twin, an evidence-labelled causal graph, and a
multi-agent evaluation layer.

DecisionGPT is a **decision-support system**. It recommends and simulates
decisions; it never executes payments, ad spend, price changes, purchases, or
any other irreversible business action.

> Status: under active build. See "Build status" below for what's implemented.

## Architecture

```
PLATFORM / RESEARCH DATA -> Training Pipeline -> Model Registry
                                                        |
BUSINESS DATA -> Onboarding -> Business Knowledge Base  |
                                        |                |
                                        v                v
                              Goal Planner -> Analytics Engine
                                        |
                                        v
                              Business Digital Twin
                                        |
                                        v
                              Dynamic Causal Graph
                                        |
                                        v
                          Multi-Agent Decision Engine
                                        |
                                        v
                              Explainable AI + Memory
                                   /         \
                        SME Application   Research Console
```

Two completely separate data worlds:
- **Platform/research data** (`data/platform/**`) — used only to train and
  evaluate models offline. Never exposed to SME users or public APIs.
- **Business data** (`data/business/**`, and the `businesses`-scoped DB
  tables) — uploaded per-business through the SaaS app, isolated by
  `business_id`.

## Repository layout

```
DecisionGPT/
├── docs/            authoritative product & research specification
├── frontend/        Next.js + TypeScript + Tailwind SME app + Research Console
├── backend/         FastAPI service (API, services, ML inference, agents)
├── ml/              platform training/evaluation pipeline (offline)
├── data/            platform (research) vs business (per-tenant) data
├── experiments/     experiment configs, ablation configs, results
├── notebooks/       exploratory analysis
├── scripts/         operational scripts (seed demo data, run pipelines)
├── tests/           unit / integration / api / e2e
└── models/          trained model artifacts (registry storage)
```

## Setup

### Prerequisites
- Docker + Docker Compose (for the target deployment — not yet wired up, see Build status)
- Python 3.11+, Node 20+, PostgreSQL 15+ (for local dev)

### Quick start (Docker)

Docker Compose / Dockerfiles are Phase 29 of the build and aren't in this
repo yet. Once they land:

```bash
cp .env.example .env
docker compose up --build
docker compose exec backend alembic upgrade head
```

### Quick start (local dev, no Docker/Postgres)

This is the path actually verified so far. It uses SQLite instead of
Postgres purely as a local-dev convenience (see `app/db/types.py`'s
cross-dialect `GUID` type) — production always targets Postgres via Alembic
migrations.

```bash
# 1. Backend
cd backend
python -m venv .venv && .venv/Scripts/activate  # or source .venv/bin/activate
pip install -r requirements.txt
cd ..
DATABASE_URL=sqlite:///./backend/dev.db python backend/scripts/dev_bootstrap_sqlite.py

# repo root must be on PYTHONPATH so `ml.*` (feature engineering shared
# between training and inference) is importable — see AGENTS.md.
PYTHONPATH=. DATABASE_URL=sqlite:///./backend/dev.db \
  uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# 2. Train + register at least one forecasting/churn model (once)
python -m ml.training.train_forecasting
python -m ml.training.train_churn
curl -X POST http://localhost:8000/api/v1/research/models/sync \
  -H "X-Research-Token: change-me-research-console-token"

# 3. Frontend
cd frontend
npm install
npm run dev
```

- Backend: http://localhost:8000 (docs at `/docs`)
- Frontend: http://localhost:3000
- API base path: `/api/v1`

### Demo mode

No LLM key is required to explore the product. With `LLM_API_KEY` unset, the
system runs in deterministic demo mode: goal parsing falls back to rule-based
parsing, and agent/explanation text is generated from structured templates
instead of an LLM. Numerical outputs (forecasts, simulations, KPIs) never
depend on the LLM either way.

Use **"Try Demo Business"** on the landing page to load a synthetic Indian D2C
clothing business with sales, customers, products, marketing, and inventory
history, clearly labelled as synthetic demonstration data.

## Data upload

The SME app accepts a single Excel workbook (Sales/Customers/Products/
Marketing/Inventory sheets) or separate CSV files. See
`docs/DATA_SPECIFICATION.md` for canonical schemas.

## Platform data & model training

Platform datasets live under `data/platform/<domain>/` and are never served to
SME users. To (re)train models:

```bash
docker compose exec backend python -m ml.pipeline.run --dataset forecasting
```

Trained artifacts are versioned into the model registry (`models` table +
`models/` artifact directory) and picked up by the runtime analytics engine —
the runtime never touches raw platform training data directly.

## Research Console

A private console at `/research` (not linked from SME navigation) exposes the
dataset registry, model registry, experiment runner, ablation studies, and
paper-ready exports (CSV/JSON/Markdown/LaTeX). Every value shown there is read
from stored experiment/model records — nothing is hard-coded.

## Testing

```bash
docker compose exec backend pytest
```

Covers unit, integration, API, and the critical end-to-end business workflow
(create business → upload data → validate → KPIs → goal → forecast → digital
twin → causal graph → multi-agent → recommendation → save decision → record
outcome), plus a business-isolation test (Business A cannot read Business B).

## Research methodology & limitations

See `docs/RESEARCH_SPECIFICATION.md`, `docs/EXPERIMENT_PLAN.md`, and
`docs/PAPER_OUTLINE.md`. No result is reported anywhere in the product or
paper exports unless it was produced by a recorded experiment run.

## Build status

Tracked incrementally as the project is built out; see task list / commit
history for current phase.
