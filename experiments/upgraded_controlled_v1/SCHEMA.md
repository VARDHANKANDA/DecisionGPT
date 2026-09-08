# Machine-readable output schemas — upgraded_controlled_v1

All files are JSON, UTF-8, `sort_keys=true`, 2-space indent. Every file also has a
SHA-256 recorded in `checksums.txt`. Files are produced by
`scripts/run_upgraded_eval.py` subcommands:

| file | produced by | phase |
|---|---|---|
| `scenario_manifest.json` | `generate` + `split` | 4 |
| `power_assumptions.json` (input), `power_analysis.json` | `power` | 5 |
| `config.json` (`prereg` block, `prereg_frozen: true`) | `freeze-prereg` | 6 |
| `dry_run_report.json` | `dry-run` | 3 |
| `results_<partition>.jsonl` (append log), `results.json` (locked) / `results_<partition>.json` | `run` | 7–8 |
| `statistical_results.json`, `analysis_supplement.json` | `analyze` | 9–11, 13–14 |
| `robustness_runs.jsonl`, `robustness_results.json` | `robustness` | 12 |
| `checksums.txt`, `REPRODUCIBILITY_AUDIT.md` | `audit` / manual | 15 |

`generator_version` is `upgraded_eval_scenarios_v2` (a scenario stores a history
*spec*; the ingested history is realised per `(scenario, seed)` — see the
pre-registration §4).

## `scenario_manifest.json`
```
{
  "evaluation_layer_version": "upgraded_controlled_v1",
  "generator_version": "upgraded_eval_scenarios_v1",
  "master_seed": <int>,
  "n_scenarios": <int>,
  "n_families": <int>,
  "family_ids": [<str>, ...],
  "suite_checksum": <sha256 hex>,
  "action_space_policy": <str>,
  "status": "generated",
  "scenarios": [
    {
      "scenario_id": "<family>__NNNN",
      "family_id": <str>, "family_label": <str>, "family_description": <str>,
      "seed": <int>, "master_seed": <int>, "partition": "development|validation|locked_test|unassigned",
      "params": { "base_price","unit_cost","base_demand","price_elasticity",
                  "marketing_response","marketing_base_spend","kappa","holding_rate",
                  "capacity_cap","inventory_cap","horizon_days" : <float> },
      "history_spec": { "days": <int>, "demand_noise_sd"?, "price_band_pct"?,
                        "drop_rate"?, "trend_break"?, "obs_price_jitter_pct"?,
                        "constant_price"?, "with_inventory_cap"? },
      "reference_history": { "days": <int>, "day_offsets": [<int>], "price": [<float>],
                   "units": [<float>], "marketing_spend": [<float>], "stock": [<float>]|null },
      # ^ reference_history is the realisation at the canonical seed; the ingested
      #   history for run seed S is scenario_families.realise_history(scenario, S)
      "constraints": { "cash_cap"?,"inventory_cap"?,"capacity_cap"?,
                       "price_floor_pct"?,"price_ceiling_pct"? : <float> },
      "objective": { "kpi": "revenue|profit|orders|holding_cost", "sense": "max|min" },
      "feasible_actions":       [ [ {"type","value"} , ... ] , ... ],
      "eval_reference_actions": [ ... , [] ],
      "uncertainty": {<str>: <number|bool>},
      "noise": {<str>: <number|bool>},
      "perturbation_config": { "supported": { "<name>": [<severity float>, ...] } },
      "provenance": { "generator_version","family_id","family_index","master_seed","goal_objective" },
      "content_hash": <sha256 hex>
    }
  ]
}
```

## `power_analysis.json`
```
{
  "assumptions": { "n_scenarios","n_seeds","min_effect_of_interest",
                   "metric_sd_between_scenarios","within_scenario_seed_sd",
                   "alpha","target_power","primary_comparison","n_sim","rng_seed" },
  "assumed_effective_sd": <float>,
  "estimated_power": <float 0..1>,
  "meets_target": <bool>,
  "n_sim": <int>
}
```

## `results_<partition>.jsonl`  (append-only run log; one JSON object per line)
```
{"scenario_id","family_id","partition","seed",
 "result": <InstanceResult asdict>            # on success
 | "error": <str>, "traceback": <str> }        # on harness failure
```

## `results.json`  (locked_test) / `results_<partition>.json`  (dev/val)
```
{
  "status": "complete",
  "evaluation_layer_version": "upgraded_controlled_v1",
  "partition": "development|validation|locked_test",
  "generator_version","master_seed","suite_checksum",
  "seeds": [<int> x 10],
  "frozen_manifest_sha256": <sha256 hex>,
  "architecture_fingerprint": { "sha256", "pipeline_options_defaults", "pipeline_options_label":"full",
                                "candidate_grid", "optimizer_formula_version":"v2",
                                "risk_formula_version":"extrapolation_range_v1",
                                "supported_action_types","action_value_bounds","max_actions_per_simulation" },
  "n_instances","n_ok","n_error",
  "records": [
    { "scenario_id","family_id","partition","seed",
      "result": {                               # InstanceResult
      "scenario_id","family_id","partition","seed",
      "perturbation": null|<str>, "perturbation_severity": <float>,
      "action_space_invariant_ok": <bool>, "action_space_detail": {...}, "action_space_hash": <str>,
      "exclude_from_primary": <bool>, "exclude_reason": null|<str>,
      "conditions": { "A|B|C|D": {
          "condition","status",
          "selected_action": null|[{"type","value"}],
          "selected_action_key": null|<str>,
          "primary_value": null|<float>,          # EXOGENOUS objective value
          "primary_normalized": null|<float>,     # 0..1, 1 == oracle   (PRIMARY)
          "primary_regret": null|<float>,         # 0..1, 0 == oracle   (PRIMARY)
          "secondary_goal_achievement": null|<float>,   # DecisionGPT internal (SECONDARY, labelled)
          "dt_projection": null|{...}, "latency_seconds": <float>, "note": <str> } },
      "baselines": { "oracle": {...}, "naive": {...}, "greedy": {...}, "classical_optimizer": {...} },
      "agent_diagnostics": { "assessable","per_action_scores","score_variance","score_range",
                             "inter_agent_agreement_mean","agent_changed_selection_vs_C",
                             "agent_changed_selection_vs_greedy","contribution_note" },
      "factors": { "uncertainty","constraint_tightness","objective_conflict","prediction_error",
                   "risk_exposure","risk_exposure_source","action_space_size","agent_disagreement",
                   "perturbation_meta"? }
      }
    }
  ]
}
```

## `analysis_supplement.json`  (Phases 11, 13, 14)
```
{
  "status": "complete", "source_results": "results.json",
  "agent_diagnostics": { "n_scenarios_eligible","mean_score_range":{BA,FA,RM},
    "max_score_range":{...}, "mean_inter_agent_agreement",
    "frac_agent_changed_selection_vs_C","frac_agent_changed_selection_vs_greedy",
    "C_minus_B","D_minus_B","finding": <str> },
  "mechanism_associational": { "B_vs_A"|"C_vs_B"|"D_vs_B": {
     "contrast","n_scenarios","usable_factors",
     "ols_coefficients_on_standardised_factors": {"<factor>": {"beta","ci95":[lo,hi]}},
     "tertile_contrast_means": {"<factor>": {"low","mid","high"}},
     "note": "...associational within the designed suite, not causal" } },
  "failure_cases": { "worst_D_minus_B ...","best_D_minus_B ...","highest_absolute_regret_D",
     "greedy_beats_D","naive_beats_D","near_oracle_D (regret <= 0.02)" }
}
```

## `statistical_results.json`
```
{
  "status": "not_run" | "complete",
  "unit_of_analysis": "scenario",
  "primary_metric": "exogenous normalised regret (lower is better) / performance ratio",
  "secondary_metric": "DecisionGPT internal goal_achievement (labelled; never primary)",
  "contrasts": {
    "B_vs_A": { <paired_scenario_analysis> },
    "C_vs_B": { ... },
    "D_vs_B": { ... },
    "D_vs_A": { ... },
    "D_vs_oracle": { ... },
    "D_vs_greedy": { ... },
    "D_vs_classical_optimizer": { ... }
  },
  "holm_family": { "alpha": 0.05, "method": "holm_bonferroni",
                   "n_tests_corrected": <int>, "results": { "<contrast>": {"p_raw","p_holm","reject_at_alpha","rank"} } },
  "power_analysis_ref": "power_analysis.json"
}

# <paired_scenario_analysis> =
{ "label","n_scenarios","mean_difference","median_difference","sd_difference",
  "wins_ties_losses":[w,t,l], "n_nonzero",
  "wilcoxon": {"test","n","n_nonzero","statistic","p_value","mode"|"reason"},
  "rank_biserial": <float|null>,             # matched-pairs, estimator-based (PRIMARY effect size)
  "cluster_bootstrap": {"n_units","statistic","point","ci95":[lo,hi],"n_boot","seed"},   # PRIMARY interval
  "student_t_ci95_of_mean_difference": [lo,hi]|null,   # secondary reference only
  "primary_effect_size": "matched_pairs_rank_biserial",
  "primary_interval": "paired_scenario_cluster_bootstrap" }
```

## `robustness_results.json`
```
{
  "status": "not_run" | "complete",
  "perturbation_version": "eval_perturbations_v1",
  "curves": {
    "<perturbation_name>": {
      "<condition A|B|C|D>": {
         "severities":[<float>], "values":[<float>], "baseline":<float>,
         "degradation":[<float>], "severity_at_50pct_degradation": <float|null>,
         "auc_degradation": <float> }
    }
  }
}
```
