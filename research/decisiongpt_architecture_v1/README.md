# decisiongpt_architecture_v1 — reproducibility package for the architecture paper

Paper: *Does a Multi-Agent Layer Help? A Controlled Component-Level Evaluation of an Integrated Decision-Support Architecture for Data-Constrained SMEs* (LaTeX in `overleaf/architecture_paper_v1/`).

Everything here is **read-only with respect to the frozen project artifacts** (`experiments/**`, `experiments/experiment_manifest.json` sha256 `94aa419c…`). The only new measurement is `analysis/cost_measurement.py`; every other script re-analyses stored results.

## Files

| Path | Purpose |
|---|---|
| `EXPERIMENT_PROTOCOL.md`, `PROTOCOL.sha256`, `PROTOCOL_AMENDMENTS.md` | internal protocol (hash-frozen before the cost run), amendments 1–2 |
| `analysis/freeze_inputs.py` | writes the protocol hash and `results/input_hashes_{before,after}.json` (sha256 of every read-only input) |
| `analysis/decision_quality.py` | RQ2/RQ3 re-computation from `experiments/{r1,upgraded_controlled_v1}/results.json` → `results/decision_quality.json` |
| `analysis/replication_check.py` | compares the re-computation with the stored statistical results → `results/replication_check.json` |
| `analysis/sensitivity.py` | post-hoc sensitivity (fallback exclusion, first seed, leave-one-family-out, near-optimal shares) → `results/sensitivity.json` |
| `analysis/cost_measurement.py` | **new measurement** (RQ4): wall-clock and invocation counts per workflow → `results/cost_measurement.jsonl` (append-only, resumable) |
| `analysis/cost_analysis.py` | summarises the cost run and combines it with stored regret → `results/cost_summary.json` |
| `analysis/rq1_tables.py` | RQ1 tables from stored benchmark runs and the registry re-scoring → `results/rq1_summary.json` |
| `analysis/make_tables.py`, `analysis/make_figures.py` | LaTeX tables, number macros (`tables/numbers.tex`) and figures, generated from `results/*.json` only |
| `logs/` | run logs; `pilot_v0_first40_instances_without_sim_timing.jsonl` is a set-aside first launch (unused, see Amendment 2) |

## Commands (from the repository root; backend virtual environment)

```bash
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/freeze_inputs.py before
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/decision_quality.py
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/replication_check.py
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/sensitivity.py
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/cost_measurement.py main      # ~1 h on a laptop CPU
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/cost_measurement.py repeats   # ~20 min
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/cost_analysis.py
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/rq1_tables.py
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/make_tables.py
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/make_figures.py
backend/.venv/Scripts/python.exe research/decisiongpt_architecture_v1/analysis/freeze_inputs.py after        # prints "inputs unchanged"
```

Seeds: cost measurement uses the first locked seed (20260906) of the R1 locked run; bootstrap seeds 20261023 (decision quality), 20261024 (cost), 20261025 (sensitivity), 10 000 resamples.

## Known reproducibility caveats

1. The harness anchors each synthetic history to the run date (`date.today()`), so re-execution on another date is not bit-identical: in the cost run, D's selected action differed from the stored locked run in a few near-tie instances (A, B, C identical). Contrasts are unaffected (see `results/cost_summary.json: rerun_on_new_date`).
2. Timing was taken on one laptop with other processes running; use ratios and medians, not absolute seconds.
3. `rq1_tables.py` reads the registry re-scoring from `backend/dev.db` (read-only). That database is local and git-ignored; the extracted values are written to `results/rq1_summary.json`.
4. Third-party datasets (M5, Online Retail II) are not redistributed.
