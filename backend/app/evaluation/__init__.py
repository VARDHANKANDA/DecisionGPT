"""Upgraded controlled evaluation — EVALUATION-ONLY layer.

This package exists to make the *existing, frozen* DecisionGPT architecture
evaluation more scientifically rigorous using controlled synthetic experimentation
only. It is completely separate from the production decision pipeline and from the
16 frozen experiments.

HARD RULES (enforced by design, verified by tests):
  * Nothing here modifies production code. Production services are imported and
    called READ-ONLY, and only through public functions / the pre-existing
    ``decision_service.PipelineOptions`` evaluation knobs (production always uses
    the defaults, i.e. R0/D0).
  * ``ground_truth`` is fully independent of the Digital Twin, ``decision_service``
    and ``decision_architecture_service._goal_achievement`` — it never imports or
    calls them (see ``tests/unit/test_eval_ground_truth.py``).
  * No real SME / customer / prospective / human / real-LLM data is used or
    assumed. Every scenario is parameterised synthetic.
  * The frozen ``experiments/experiment_manifest.json`` /
    ``experiments/paper_results_snapshot.json`` are never regenerated. New runs
    write to ``experiments/upgraded_controlled_v1/`` and (optionally) a separate
    scratch database.
  * Importing this package runs nothing. Experiments are driven explicitly by
    ``scripts/run_upgraded_eval.py``.

Modules:
  scenario_families  parameterised scenario generation (>=15 families, 50 -> 100+ instances)
  ground_truth       exogenous objective, oracle, naive/greedy/classical baselines
  harness            per-instance runner: invokes the frozen A/B/C/D read-only, scores with ground_truth
  perturbations      evaluation-only input transformations for robustness testing
  stats              scenario-level paired stats, cluster bootstrap, Holm, rank-biserial
  mechanism          scenario-property extraction + B-A / C-B / D-B interaction analysis
"""

EVALUATION_LAYER_VERSION = "upgraded_controlled_v1"

# The frozen manifest this evaluation must never touch.
FROZEN_MANIFEST_SHA256 = "94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff"
