"""Research Console — Causal Evaluation (docs/PRD.md §16).

Generates synthetic time series with a *known* causal structure, runs the
same Granger-causality method causal_graph_service uses on real business
data (ml/causal/granger.py), and scores how well it recovers the known
ground truth — precision, recall, and structural Hamming distance (SHD).
This validates the *method*, not any business's data — the two must never
be confused (docs/CAUSAL_GRAPH_SPECIFICATION.md §9 "synthetic data with
known causal structure").
"""
from dataclasses import dataclass, field
from itertools import permutations

import numpy as np

from ml.causal.granger import best_granger_result

VARIABLES = ["A", "B", "C", "D"]
GROUND_TRUTH_EDGES = {("A", "B"), ("B", "C")}  # D is intentionally disconnected noise


@dataclass
class CausalEvaluationResult:
    n_timesteps: int
    seed: int
    ground_truth_edges: list[list[str]]
    predicted_edges: list[list[str]]
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float | None
    recall: float | None
    structural_hamming_distance: int
    label: str = "SYNTHETIC_CAUSAL_VALIDATION"
    notes: list[str] = field(default_factory=list)


def _generate_synthetic_series(n: int, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    noise = lambda: rng.normal(0, 1, n)  # noqa: E731

    a = noise()
    b = np.zeros(n)
    c = np.zeros(n)
    d = noise()  # fully independent — should show up in no recovered edge

    b_noise = noise()
    c_noise = noise()
    for t in range(1, n):
        b[t] = 0.6 * a[t - 1] + 0.3 * b[t - 1] + b_noise[t]
        c[t] = 0.6 * b[t - 1] + 0.3 * c[t - 1] + c_noise[t]

    return {"A": a, "B": b, "C": c, "D": d}


def run_causal_evaluation(n_timesteps: int = 250, seed: int = 42) -> CausalEvaluationResult:
    series = _generate_synthetic_series(n_timesteps, seed)

    predicted: set[tuple[str, str]] = set()
    for source, target in permutations(VARIABLES, 2):
        result = best_granger_result(series[source], series[target], max_lag=3)
        if result is not None and result[1] < 0.05:
            predicted.add((source, target))

    all_possible = set(permutations(VARIABLES, 2))
    true_positives = len(predicted & GROUND_TRUTH_EDGES)
    false_positives = len(predicted - GROUND_TRUTH_EDGES)
    false_negatives = len(GROUND_TRUTH_EDGES - predicted)
    true_negatives = len(all_possible - predicted - GROUND_TRUTH_EDGES)

    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) else None
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) else None
    shd = false_positives + false_negatives

    notes = [
        f"{n_timesteps} synthetic timesteps, seed {seed}. Ground truth: A->B->C (lag 1 each), D independent noise.",
        f"{true_negatives} correctly-absent edges out of {len(all_possible) - len(GROUND_TRUTH_EDGES)} true negatives.",
        "No multiple-comparison correction is applied (matches causal_graph_service.py's per-edge testing) — "
        "expect some false positives from testing many pairs at p<0.05, plus indirect/transitive edges "
        "(e.g. A->C via B) that pairwise Granger causality cannot distinguish from a direct effect. This is a "
        "known limitation of the method, not a bug in this evaluation.",
    ]

    return CausalEvaluationResult(
        n_timesteps=n_timesteps,
        seed=seed,
        ground_truth_edges=[list(e) for e in sorted(GROUND_TRUTH_EDGES)],
        predicted_edges=[list(e) for e in sorted(predicted)],
        true_positives=true_positives,
        false_positives=false_positives,
        false_negatives=false_negatives,
        precision=round(precision, 4) if precision is not None else None,
        recall=round(recall, 4) if recall is not None else None,
        structural_hamming_distance=shd,
        notes=notes,
    )
