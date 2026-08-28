"""Run the Training Center on every genuinely-compatible
(external dataset x task x model_type), through the EXISTING training_service.
Each run:

  * creates a TrainingRun row (seed, dataset version, timings, metrics, status)
  * registers an MLModel with status = "experimental" (never "active")

Prints a summary and asserts that (a) all new models are experimental and
(b) the set of ACTIVE models is unchanged.

    python scripts/run_external_benchmarks.py [--seed 42] [--only india]
    python scripts/run_external_benchmarks.py --retired [--only uci|m5|regional]

Default target is the active **Indian** dataset(s). ``--retired`` reproduces
the archived non-Indian benchmark runs.

Run scripts/register_external_datasets.py first.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import app.models  # noqa: E402,F401
from app.core.errors import AppError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.ml_model import MLModel  # noqa: E402
from app.models.research import ResearchDataset, ResearchDatasetVersion  # noqa: E402
from app.services import training_service  # noqa: E402

# dataset registry slug -> (task, [model_types])
ACTIVE_PLAN = {
    "india": [
        ("external-india-mandi-prices-forecasting", "forecasting",
         ["naive", "linear", "xgboost"]),
    ],
}

RETIRED_PLAN = {
    "uci": [
        ("external-uci-online-retail-forecasting", "forecasting", ["naive", "linear", "xgboost"]),
        ("external-uci-online-retail-derived-churn", "churn",
         ["logistic_regression", "random_forest", "xgboost"]),
    ],
    "m5": [
        ("external-m5-forecasting-benchmark", "forecasting", ["naive", "linear", "xgboost"]),
    ],
    "regional": [
        ("external-regional-retail-myanmar-forecasting", "forecasting",
         ["naive", "linear", "xgboost"]),
    ],
}


def _latest_version(db, slug: str) -> ResearchDatasetVersion | None:
    ds = db.query(ResearchDataset).filter(ResearchDataset.dataset_id == slug).one_or_none()
    if ds is None:
        # retired datasets are registered with a RETIRED_NON_INDIAN_BENCHMARK- prefix
        ds = (
            db.query(ResearchDataset)
            .filter(ResearchDataset.dataset_id.like(f"%{slug}"))
            .order_by(ResearchDataset.created_at.desc())
            .first()
        )
    if ds is None:
        return None
    return (
        db.query(ResearchDatasetVersion)
        .filter(ResearchDatasetVersion.dataset_id == ds.id)
        .order_by(ResearchDatasetVersion.version.desc())
        .first()
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--retired", action="store_true")
    ap.add_argument("--only", default=None)
    args = ap.parse_args()

    plan = RETIRED_PLAN if args.retired else ACTIVE_PLAN
    if args.only and args.only not in plan:
        ap.error(f"--only must be one of {list(plan)} ({'retired' if args.retired else 'active'} set)")

    db = SessionLocal()
    try:
        active_before = {
            (m.model_name, m.version) for m in db.query(MLModel).filter(MLModel.status == "active").all()
        }

        rows = []
        keys = [args.only] if args.only else list(plan)
        for key in keys:
            for slug, task, model_types in plan[key]:
                version = _latest_version(db, slug)
                if version is None:
                    print(f"SKIP {slug}: not registered (run register_external_datasets.py)")
                    continue
                for mt in model_types:
                    try:
                        run = training_service.start_training(
                            db, task=task, model_type=mt,
                            dataset_version_id=version.id, random_seed=args.seed,
                        )
                        m = run.metrics_json
                        headline = (
                            f"MAE={m.get('mae'):.3f} RMSE={m.get('rmse'):.3f}"
                            if task == "forecasting"
                            else f"F1={m.get('f1'):.3f} AUC={m.get('roc_auc'):.3f}"
                        )
                        rows.append((slug, task, mt, run.status, run.model_name, run.model_version, headline))
                        print(f"OK   {slug} / {task} / {mt}: {run.status} "
                              f"-> {run.model_name} {run.model_version}  {headline}")
                    except AppError as exc:
                        rows.append((slug, task, mt, "failed", "-", "-", str(exc)[:120]))
                        print(f"FAIL {slug} / {task} / {mt}: {exc}")

        new_models = db.query(MLModel).filter(MLModel.source == "training_center").all()
        non_experimental = [
            (m.model_name, m.version, m.status) for m in new_models if m.status != "experimental"
        ]
        active_after = {
            (m.model_name, m.version) for m in db.query(MLModel).filter(MLModel.status == "active").all()
        }

        print("\n--- safety checks ---")
        print(f"training-center models: {len(new_models)} | non-experimental: {non_experimental or 'none'}")
        print(f"active models unchanged: {active_before == active_after} "
              f"(before={len(active_before)}, after={len(active_after)})")
        assert not non_experimental, f"a training-center model is not experimental: {non_experimental}"
        assert active_before == active_after, "the set of ACTIVE models changed - this must never happen"

        ok = sum(1 for r in rows if r[3] == "completed")
        print(f"\n{ok}/{len(rows)} benchmark training runs completed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
