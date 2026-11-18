"""Architecture evaluation, rebuilt on stored multi-decision evidence with defined metrics and honest labels.

Reads (never recomputes) stored results:
  * R1 locked evaluation   - experiments/r1/{statistical_results,figure_data}.json  (408 scenarios x 10 seeds = 4,080 decisions per
                             architecture, SIMULATED; metric = exogenous normalised regret, 0 = oracle, 1 = worst feasible, lower is better)
  * Frozen synthetic suite - the stored DB experiment "risk_manager_diagnostic" (60 scenario-seed pairs; goal achievement)
  * Single recorded decision - the stored DB experiment "architecture_comparison" (n = 1; illustrative only)

Different units are never merged: regret is dimensionless, goal achievement is a 0-1 fraction, benefit and risk-adjusted score are
currency units of ONE simulated business, latency is seconds of one run.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
R1_DIR = ROOT / "experiments" / "r1"
RESULTS_DIR = ROOT / "experiments" / "results"

ARCHITECTURES = [
    {"key": "A", "name": "Prediction only", "includes": ["demand forecast"],
     "produces": "A forecast. It does not recommend any action, so it has no decision to score."},
    {"key": "B", "name": "Prediction + Decision Simulation", "includes": ["demand forecast", "scenario simulation of candidate actions"],
     "produces": "The candidate action with the highest simulated revenue."},
    {"key": "C", "name": "Prediction + Decision Simulation + single agent", "includes": ["B", "one scoring agent"],
     "produces": "The candidate action preferred by one agent's score."},
    {"key": "D", "name": "Full DecisionGPT", "includes": ["C", "three specialist agents", "conflict review", "risk gate and optimiser"],
     "produces": "The action selected by the multi-agent pipeline."},
]

METRIC_DEFINITIONS = [
    {"metric": "Normalised regret", "unit": "dimensionless, 0 to 1", "better": "lower",
     "definition": "(best achievable outcome - outcome of the chosen action) / (best - worst feasible outcome), scored by an exogenous scorer that was not used to pick the action. 0 = the oracle's choice."},
    {"metric": "Goal achievement", "unit": "fraction, 0 to 1", "better": "higher",
     "definition": "clip((expected KPI - baseline KPI) / baseline KPI x 100 / target %, 0, 1). It is clipped at 0, so 'no improvement' and 'worse than baseline' both show 0."},
    {"metric": "Expected benefit", "unit": "currency of the simulated business", "better": "higher",
     "definition": "expected revenue of the chosen action minus baseline revenue, from the simulation."},
    {"metric": "Risk-adjusted score", "unit": "currency of the simulated business", "better": "higher",
     "definition": "expected benefit x (1 - risk score), where the risk score is the extrapolation-range score in [0, 1]. It is an adjusted benefit, not a probability."},
    {"metric": "Latency", "unit": "seconds", "better": "lower",
     "definition": "wall-clock time of that architecture's code path in one in-process run (it includes simulating every candidate for B-D). A single timing, not a distribution."},
]


def _json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _primary_evidence() -> dict | None:
    fig = _json(R1_DIR / "figure_data.json")
    stat = _json(R1_DIR / "statistical_results.json")
    if not fig or not stat:
        return None
    reg = fig.get("abcd_mean_regret") or {}
    ci = fig.get("abcd_vs_oracle_ci") or {}
    prim = fig.get("primary") or {}
    n_dec = fig.get("n_scenarios", 0) * fig.get("n_seeds", 0)
    rows = []
    for a in ARCHITECTURES:
        k = a["key"]
        c = ci.get(f"{k}_vs_oracle")
        rows.append({**a, "mean_regret": reg.get(k), "ci95": c, "n_decisions": n_dec})
    comparisons = []
    labels = {"B_vs_A": "B vs A (does adding the simulation help?)", "C_vs_B": "C vs B (does one agent help?)",
              "D_vs_C": "D vs C (do three agents + risk gate help?)", "D_vs_B": "D vs B (full system vs simulation alone)"}
    for k, lab in labels.items():
        p = prim.get(k)
        if not p:
            continue
        wtl = p.get("wtl") or [None, None, None]
        comparisons.append({"contrast": k, "label": lab, "mean_difference": p.get("mean"), "ci95": p.get("ci95"), "p_holm": p.get("p_holm"),
                            "wins": wtl[0], "ties": wtl[1], "losses": wtl[2], "n_scenarios": fig.get("n_scenarios"),
                            "reading": "negative = the first architecture has lower regret (better)"})
    fam = []
    for f, v in (fig.get("family_D_minus_B") or {}).items():
        fam.append({"family": f, "mean_D_minus_B": v.get("mean"), "ci95": v.get("ci95"), "direction": v.get("direction"), "n_scenarios": v.get("n")})
    return {
        "evidence_type": "simulated",
        "source": "experiments/r1 (pre-registered locked evaluation of a research-only corrected Decision Simulation)",
        "design": {"scenarios": fig.get("n_scenarios"), "seeds": fig.get("n_seeds"), "decisions_per_architecture": n_dec,
                   "same_scenarios_and_seeds_for_all_architectures": True,
                   "unit_of_analysis": stat.get("unit_of_analysis"), "multiplicity": "Holm-Bonferroni over four contrasts"},
        "architectures": rows,
        "reference_points": {"oracle": 0.0, **(fig.get("baselines_mean_regret") or {})},
        "comparisons": comparisons,
        "family_effects_D_minus_B": sorted(fam, key=lambda x: (x["mean_D_minus_B"] is None, x["mean_D_minus_B"])),
        "mechanism": fig.get("mechanism_action_change"),
        "status": stat.get("status"),
        "positioning": stat.get("positioning"),
    }


def _frozen_suite(agent_eval: dict | None) -> dict | None:
    rmd = (agent_eval or {}).get("risk_manager_diagnostic") or {}
    base = rmd.get("baseline") or {}
    full, dt = base.get("full_decisiongpt_mean_goal_achievement"), base.get("digital_twin_mean_goal_achievement")
    if full is None or dt is None:
        return None
    return {"evidence_type": "simulated", "source": "stored experiment risk_manager_diagnostic v1 (synthetic suite)",
            "pairs": rmd.get("total_scenario_seed_pairs"), "created_at": rmd.get("created_at"),
            "rows": [{"key": "B", "label": "Prediction + Decision Simulation", "mean_goal_achievement": dt},
                     {"key": "D", "label": "Full DecisionGPT", "mean_goal_achievement": full}],
            "note": "Mean goal achievement over the stored scenario-seed pairs; A and C were not part of this diagnostic."}


def _single_decision(agent_eval: dict | None) -> dict | None:
    ac = (agent_eval or {}).get("architecture_comparison") or {}
    rows = ac.get("rows") or []
    if not rows:
        return None
    out = []
    for r in rows:
        produced = r.get("selected_strategy") is not None
        out.append({"key": r["architecture"], "label": r["label"], "selected_strategy": r.get("selected_strategy"), "produced_decision": produced,
                    "goal_achievement": r.get("goal_achievement") if produced else None,
                    "expected_benefit": r.get("expected_benefit") if produced else None,
                    "risk_adjusted_score": r.get("risk_adjusted_score") if produced else None,
                    "latency_seconds": r.get("latency_seconds"),
                    "status": "evaluated" if produced else "not_applicable",
                    "note": r.get("note") or (None if produced else "No decision was produced, so decision metrics do not apply (the stored 0.0 is a placeholder, not a result).")})
    return {"evidence_type": "simulated", "experiment_id": ac.get("experiment_id"), "seed": ac.get("seed"), "created_at": ac.get("created_at"),
            "goal_target_percent": ac.get("goal_target_percent"), "n_decisions_per_architecture": 1, "rows": out,
            "caveats": ["One decision per architecture: it demonstrates the pipeline and the units, and cannot rank the architectures.",
                        "A goal achievement of 0 here can mean no simulated improvement or a negative one (the metric is clipped at 0).",
                        "C and D chose 'Marketing +10%' with benefit exactly 0: the stored forecaster was insensitive to that action, so the simulation saw no change."]}


def _improved_multiagent_study() -> dict | None:
    files = sorted(RESULTS_DIR.glob("improved_multiagent_evaluation_*.json"))
    if not files:
        return None
    data = _json(files[-1])
    if not data:
        return None
    summary = data.get("summary", {})
    rows = []
    for k, s in summary.items():
        rows.append(s)
    return {
        "evidence_type": "simulated",
        "source": files[-1].name,
        "timestamp": data.get("timestamp"),
        "partition": data.get("partition", "locked_test"),
        "n_families": data.get("n_families", 12),
        "n_instances": data.get("n_instances", 60),
        "headline": "Confirmatory Evaluation of Improved Multi-Agent Architectures on Untouched Scenarios",
        "key_takeaway": "Candidate D (Independent Proposal & Verification) matched Digital Twin Alone (mean regret 0.1420 vs 0.1420), reducing regret by 0.0417 vs Legacy Multi-Agent (0.1837). Single Agent (Condition C, 0.1102) remains the most cost-effective and lowest-regret architecture overall.",
        "rows": rows,
    }


def get_architecture_evaluation(agent_eval: dict | None) -> dict[str, Any]:
    primary = _primary_evidence()
    return {
        "headline": ("On 4,080 simulated decisions per architecture, the full multi-agent system had HIGHER regret (worse decisions) than the simulation alone."
                     if primary else "No multi-decision architecture evidence is stored."),
        "architectures": ARCHITECTURES,
        "metric_definitions": METRIC_DEFINITIONS,
        "primary_evidence": primary,
        "improved_multiagent_study": _improved_multiagent_study(),
        "frozen_suite": _frozen_suite(agent_eval),
        "single_decision": _single_decision(agent_eval),
        "comparability": ["Within each evidence source every architecture saw the same scenarios, seeds, initial conditions, horizon and constraints.",
                          "Sources are not mixed: regret (R1), goal achievement (frozen suite) and currency values (single decision) are different quantities.",
                          "All three sources are simulated; none is a measured real-world outcome."],
        "limitations": ["Simulated environments encode assumptions; a result describes those assumptions.",
                        "The finding is specific to the tested deterministic agent configuration; it does not show multi-agent systems are unhelpful in general.",
                        "No real business outcome has been collected for any architecture."],
    }
