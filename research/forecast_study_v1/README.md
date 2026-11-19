# forecast_study_v1 — research package index

A pre-registered, leakage-controlled, multi-origin evaluation of gradient-boosting forecasters against validation-selected simple baselines on public retail data (M5 CA_1, M5 TX_1, Online Retail II top-100 SKUs; H ∈ {7, 28}), plus a customer-inactivity (proxy label) classification study. Written 2026-10-22. **Nothing here has been submitted or published; nothing frozen elsewhere in the repository was modified.**

**Headline (confirmatory, verified):** the learned model did *not* beat the best matched-information baseline in pooled WAPE in any of six cells (3 contradicted, 3 inconclusive), while it was ~2–3.5× better at store-day aggregate WAPE; the winner depends on the metric and aggregation level. See `manuscript/MANUSCRIPT.md`.

| Deliverable | File |
|---|---|
| Audit of the existing benchmark and baseline inventory | `RESEARCH_AUDIT.md`, `inventory/experiment_inventory.json`, `inventory/artifact_fingerprints.json` |
| Verified literature matrix and research gap | `LITERATURE_REVIEW.md` |
| Experiment plan, hypotheses, decision rules, deviations log | `EXPERIMENT_PLAN.md`; hashes in `FREEZE.json` |
| Code | `protocol.py`, `baselines.py`, `metrics.py`, `inference.py`, `run_forecast_study.py`, `run_classification_study.py`, `analyze.py`, `aggregate.py`, `ablation_report.py`, `verify_cell.py`, `make_report.py`; post-hoc: `exploratory_l1.py`, `s2_customer_disjoint.py` |
| Results, saved predictions, per-cell analysis and verification | `results/` (`fs1_*`, `s2_*`, `CONFIRMATORY_SUMMARY.md`, `TABLES.md`, `ABLATIONS_*.json`, `E1_l1_*`, `S2_customer_disjoint.json`) |
| Reproducibility record | `REPRODUCIBILITY.md`, `environment_freeze.txt`, `run_all.sh`, `audit/` |
| Manuscript (editable) and figures | `manuscript/MANUSCRIPT.md`, `manuscript/figures/*.svg` |
| Evidence-to-claim matrix | `EVIDENCE_CLAIM_MATRIX.md` |
| Limitations and threats | `manuscript/MANUSCRIPT.md` §19; `LIMITATIONS_AND_THREATS.md` |
| Venue comparison | `VENUE_COMPARISON.md` |
| Submission checklist | `SUBMISSION_CHECKLIST.md` |
| Tests | `tests/unit/test_forecast_study.py` |

Reproduce: `PYTHONPATH=. bash research/forecast_study_v1/run_all.sh` (see `REPRODUCIBILITY.md`).
