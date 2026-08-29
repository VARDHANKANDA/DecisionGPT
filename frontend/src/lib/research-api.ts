const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const TOKEN_STORAGE_KEY = "decisiongpt.research_token";

export class ResearchApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function getResearchToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setResearchToken(token: string): void {
  sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearResearchToken(): void {
  sessionStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let code = "UNKNOWN_ERROR";
    let message = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
      }
    } catch {
      // not JSON
    }
    throw new ResearchApiError(response.status, code, message);
  }
  return response.json() as Promise<T>;
}

function authHeaders(): HeadersInit {
  const token = getResearchToken();
  return token ? { "X-Research-Token": token } : {};
}

async function researchGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { headers: authHeaders(), cache: "no-store" });
  return handleResponse<T>(response);
}

async function researchPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  return handleResponse<T>(response);
}

async function researchUpload<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { ...authHeaders() },
    body: form,
    cache: "no-store",
  });
  return handleResponse<T>(response);
}

async function researchPostText(path: string, body?: unknown): Promise<string> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!response.ok) {
    return handleResponse(response); // throws
  }
  return response.text();
}

// ---- Types ----

export interface PlatformDatasetEntry {
  domain: string;
  dataset_id: string;
  name: string;
  source: string;
  license: string;
  version: string;
  row_count: number;
  feature_count: number;
  date_range: [string, string] | null;
  preprocessing: string[];
  limitations: string[];
  evidence_level: string;
  data_category: string;
}

export interface ExternalDatasetEntry {
  dataset_id: string;
  name: string;
  display_label: string;
  data_category: string;
  status: string;
  source: string;
  license: string;
  geography: string;
  business_domain: string;
  date_range: string | null;
  supported_tasks: string[];
  limitations: string[];
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version: number;
  file_type: string;
  row_count: number;
  column_count: number;
  columns: { name: string; dtype: string }[];
  missing_summary: Record<string, number>;
  duplicates_summary: Record<string, number>;
  quality_report: {
    missing_value_counts?: Record<string, number>;
    duplicate_row_count?: number;
    issues?: string[];
  };
  validation_ok: boolean;
  created_at: string;
  created_by: string | null;
}

export interface UploadedDataset {
  id: string;
  dataset_id: string;
  name: string;
  description: string | null;
  domain: string;
  source: string | null;
  license: string | null;
  data_category: string;
  created_at: string;
  created_by: string | null;
  version_count: number;
  latest_version: number | null;
  versions: DatasetVersion[];
}

export interface DatasetsResponse {
  platform: PlatformDatasetEntry[];
  external: ExternalDatasetEntry[];
  uploaded: UploadedDataset[];
}

export interface ModelEntry {
  id: string;
  model_name: string;
  model_type: string;
  version: string;
  dataset_version: string;
  feature_version: string;
  parameters_json: Record<string, unknown>;
  metrics_json: Record<string, number | Record<string, number>>;
  model_path: string;
  status: string;
  created_at: string;
  task: string | null;
  source: string | null;
  promoted_at: string | null;
}

export interface TrainingRun {
  id: string;
  task: string;
  model_type: string;
  dataset_version_id: string | null;
  platform_domain: string | null;
  dataset_version_label: string | null;
  features_json: string[];
  target: string | null;
  parameters_json: Record<string, unknown>;
  random_seed: number;
  status: "pending" | "running" | "completed" | "failed";
  started_at: string | null;
  completed_at: string | null;
  metrics_json: Record<string, number>;
  model_id: string | null;
  model_name: string | null;
  model_version: string | null;
  artifact_path: string | null;
  error_message: string | null;
  created_at: string;
}

export type ExperimentType =
  | "forecasting"
  | "churn"
  | "digital_twin"
  | "causal"
  | "decision_architecture"
  | "multi_agent"
  | "ablation"
  | "multi_scenario_architecture"
  | "multi_scenario_ablation"
  | "multi_agent_diagnostic"
  | "risk_manager_diagnostic"
  | "risk_manager_calibration"
  | "risk_manager_real_data_validation";

export interface ExperimentRun {
  id: string;
  experiment_name: string;
  experiment_type: ExperimentType;
  dataset_version: string | null;
  model_version: string | null;
  configuration_json: Record<string, unknown>;
  metrics_json: Record<string, unknown>;
  random_seed: number | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface ExperimentManifest {
  generated_at: string;
  experiment_count: number;
  experiments: {
    experiment_id: string;
    experiment_name: string;
    experiment_type: string;
    status: string;
    random_seed: number | null;
    dataset_version: string | null;
    model_versions: Record<string, string>;
    configuration: Record<string, unknown>;
    created_at: string | null;
    started_at: string | null;
    completed_at: string | null;
    error_message: string | null;
    metric_summary: Record<string, unknown>;
  }[];
}

export interface ResearchOverview {
  uploaded_dataset_count: number;
  uploaded_dataset_version_count: number;
  platform_dataset_count: number;
  model_count: number;
  active_model_count: number;
  experimental_model_count: number;
  training_run_count: number;
  training_runs_failed: number;
  experiment_count: number;
  experiments_completed: number;
  experiments_failed: number;
  latest_experiment: { id: string; experiment_type: string; status: string; created_at: string } | null;
  best_metrics: Record<string, { value: number; model: string }>;
}

export type ExportFormat = "csv" | "json" | "markdown" | "latex";
export type ExportTable =
  | "forecasting_performance"
  | "churn_performance"
  | "decision_architecture"
  | "decision_architecture_detail"
  | "ablation"
  | "ablation_detail"
  | "causal_evaluation"
  | "digital_twin_evaluation";

export const researchApi = {
  overview: () => researchGet<ResearchOverview>("/research/overview"),

  listDatasets: () => researchGet<DatasetsResponse>("/research/datasets"),
  uploadDataset: (input: {
    file: File;
    name: string;
    domain: string;
    description?: string;
    source?: string;
    license?: string;
  }) => {
    const form = new FormData();
    form.append("file", input.file);
    form.append("name", input.name);
    form.append("domain", input.domain);
    if (input.description) form.append("description", input.description);
    if (input.source) form.append("source", input.source);
    if (input.license) form.append("license", input.license);
    return researchUpload<DatasetVersion>("/research/datasets/upload", form);
  },

  listModels: (opts?: { modelType?: string; status?: string }) => {
    const q = new URLSearchParams();
    if (opts?.modelType) q.set("model_type", opts.modelType);
    if (opts?.status) q.set("status", opts.status);
    const qs = q.toString();
    return researchGet<ModelEntry[]>(`/research/models${qs ? `?${qs}` : ""}`);
  },
  syncModels: () => researchPost<ModelEntry[]>("/research/models/sync"),
  promoteModel: (id: string) => researchPost<ModelEntry>(`/research/models/${id}/promote`),
  archiveModel: (id: string) => researchPost<ModelEntry>(`/research/models/${id}/archive`),

  trainingTasks: () =>
    researchGet<Record<string, { model_types: string[]; metrics: string[] }>>("/research/training/tasks"),
  runTraining: (input: {
    task: string;
    model_type: string;
    dataset_version_id?: string;
    platform_domain?: string;
    parameters?: Record<string, unknown>;
    seed?: number;
  }) => researchPost<TrainingRun>("/research/training/run", input),
  listTrainingRuns: (task?: string) =>
    researchGet<TrainingRun[]>(`/research/training/runs${task ? `?task=${task}` : ""}`),

  runExperiment: (experimentType: ExperimentType, configuration: Record<string, unknown> = {}) =>
    researchPost<ExperimentRun>("/research/experiments/run", { experiment_type: experimentType, configuration }),
  listExperiments: (experimentType?: ExperimentType) =>
    researchGet<ExperimentRun[]>(`/research/experiments${experimentType ? `?experiment_type=${experimentType}` : ""}`),
  getExperiment: (id: string) => researchGet<ExperimentRun>(`/research/experiments/${id}`),
  experimentManifest: () => researchGet<ExperimentManifest>("/research/experiments/manifest"),

  exportTable: (table: ExportTable, format: ExportFormat, experimentId?: string) =>
    researchPostText("/research/export", { table, format, experiment_id: experimentId ?? null }),

  // --- dedicated evaluation pages (real recorded data) ----------------
  modelPerformance: (params?: {
    task?: string;
    dataset_version?: string;
    model_name?: string;
    training_run_id?: string;
  }) => {
    const q = new URLSearchParams();
    Object.entries(params ?? {}).forEach(([k, v]) => v && q.set(k, String(v)));
    const qs = q.toString();
    return researchGet<ModelPerformance>(`/research/model-performance${qs ? `?${qs}` : ""}`);
  },
  digitalTwinEvaluation: () => researchGet<DigitalTwinEvaluation>("/research/digital-twin-evaluation"),
  digitalTwinEvaluationBackfill: () =>
    researchPost<{ evaluations_created: number }>("/research/digital-twin-evaluation/backfill"),
  causalEvaluation: () => researchGet<CausalEvaluation>("/research/causal-evaluation"),
  agentEvaluation: () => researchGet<AgentEvaluation>("/research/agent-evaluation"),
  paperResults: () => researchGet<PaperResults>("/research/paper-results"),
};

// ---- Evaluation response types ----

interface MetricAgg {
  mae: number | null;
  rmse: number | null;
  sample_size: number;
  mape?: number | null;
}
export interface BestMetric {
  metric: string;
  value: number;
  model: string;
  model_id: string;
}
export interface PerfModelRow {
  id: string;
  model_name: string;
  model_type: string;
  version: string;
  status: string;
  source: string;
  task: string | null;
  dataset_version: string;
  training_run_id: string | null;
  created_at: string | null;
  metrics: Record<string, number | null>;
}
export interface ModelPerformance {
  summary: {
    registered_models: number;
    active_models: number;
    experimental_models: number;
    completed_training_runs: number;
    failed_training_runs: number;
    best_forecasting: BestMetric | null;
    best_churn: BestMetric | null;
  };
  forecasting: { metrics: string[]; models: PerfModelRow[]; chart: Record<string, number | string | null>[] };
  classification: { metrics: string[]; models: PerfModelRow[]; chart: Record<string, number | string | null>[] };
  training_history: {
    id: string;
    task: string;
    model_type: string;
    status: string;
    dataset_version_label: string | null;
    model_name: string | null;
    model_version: string | null;
    metrics: Record<string, unknown>;
    error_message: string | null;
    created_at: string | null;
  }[];
  filters: { tasks: string[]; dataset_versions: string[]; model_names: string[] };
  empty_state: string | null;
}

export interface DtEvalRow {
  evaluation_id: string;
  decision_id: string;
  outcome_id: string;
  simulation_id: string | null;
  strategy_name: string | null;
  predicted_baseline: number | null;
  predicted: number | null;
  actual: number | null;
  predicted_change: number | null;
  actual_change: number | null;
  error: number | null;
  abs_pct_error: number | null;
  metrics: Record<string, { predicted_change: number; actual_change: number; error: number; abs_pct_error: number | null }>;
  causal_graph_version: string | null;
  model_versions: Record<string, string>;
  recorded_at: string | null;
}
export interface DigitalTwinEvaluation {
  summary: {
    evaluated_predictions: number;
    outcomes_recorded: number;
    decisions_awaiting_outcome: number;
    revenue_mae: number | null;
    revenue_mape: number | null;
  };
  metrics: { revenue: MetricAgg; profit: MetricAgg };
  rows: DtEvalRow[];
  charts: {
    predicted_vs_actual: { decision_id: string; predicted: number | null; actual: number | null }[];
    error_over_time: { recorded_at: string | null; error: number | null }[];
    error_distribution: { range: string; count: number }[];
  };
  method: string;
  real_indian_sme: RealSmeOutcomeReport;
  empty_state: string | null;
}

export interface RealSmeOutcomeReport {
  data_category: string;
  collection_status: string;
  table_2: string;
  table_2_reason?: string | null;
  n_businesses: number;
  n_decisions: number;
  n_outcomes: number;
  empty_state?: string;
  message?: string;
  r0_vs_r3: string;
  causal_evidence: string;
  statistical_inference: string;
  decision_types?: Record<string, number>;
  outcome_horizons?: number[];
  digital_twin?: {
    revenue: { n: number; mae: number | null; rmse: number | null; mape: number | null };
    profit: { n: number; mae: number | null; rmse: number | null; mape: number | null };
    units: { n: number; mae: number | null; rmse: number | null; mape: number | null };
  };
  goal_achievement?: { achieved: number; n: number; rate: number | null };
  confidence_calibration?: string;
  provenance?: {
    all_anonymized: boolean; all_real_source: boolean; all_india: boolean; consent_recorded: boolean;
  };
  clustering_note?: string;
  rows?: {
    outcome_id: string; decision_id: string; business_industry: string | null;
    horizon_days: number | null; outcome_status: string | null;
    metrics: Record<string, { error?: number | null; abs_pct_error?: number | null }>;
    source_type: string | null; anonymization_status: string | null;
  }[];
}

export interface CausalGraphSummary {
  graph_id: string;
  business_id: string;
  version: string;
  method: string;
  created_at: string | null;
  node_count: number;
  edge_count: number;
  evidence_counts: Record<"assumed" | "observational" | "data_supported" | "causally_validated", number>;
  edges: {
    source: string;
    target: string;
    relationship: string;
    evidence_type: string;
    strength: number | null;
    confidence: number | null;
    time_lag: number | null;
  }[];
}
export interface CausalEvaluation {
  overview: {
    total_graph_versions: number;
    businesses_with_a_graph: number;
    evidence_counts_latest_per_business: Record<string, number>;
  };
  graphs: CausalGraphSummary[];
  method_validation: {
    experiment_id: string;
    seed: number | null;
    label: string;
    precision: number | null;
    recall: number | null;
    f1: number | null;
    structural_hamming_distance: number | null;
    recovered_edges: string[][];
    missing_edges: string[][];
    extra_edges: string[][];
    notes: string[];
  } | null;
  ground_truth_comparison: { available: boolean; message: string };
  evidence_feedback_log: {
    id: string;
    graph_version: string;
    edge: string;
    previous_evidence: string;
    new_evidence: string;
    method: string;
    rationale: string | null;
    sample_size: number;
    consistent_direction_count: number;
    supporting_decision_ids: string[];
    created_at: string | null;
  }[];
  empty_state: string | null;
}

export interface AgentEvaluation {
  architecture_comparison: {
    experiment_id: string | null;
    seed: number | null;
    created_at: string | null;
    goal_target_percent: number | null;
    rows: {
      architecture: string;
      label: string;
      selected_strategy: string | null;
      goal_achievement: number | null;
      risk_adjusted_score: number | null;
      expected_benefit: number | null;
      latency_seconds: number | null;
      note: string;
    }[];
  };
  single_vs_multi_agent: { experiment_id: string; single_agent: unknown; multi_agent: unknown } | null;
  ablation: { experiment_id: string | null; configs: unknown[]; comparisons: unknown[] };
  debate_analysis: {
    decisions_with_debate: number;
    message?: string;
    avg_agents_involved?: number | null;
    total_conflicts?: number;
    avg_conflicts_per_decision?: number;
    decisions_with_full_agreement?: number;
    post_review_score_changes?: number;
    avg_confidence?: number | null;
    latest_decision?: {
      decision_id: string;
      rounds: number;
      round1_scores: Record<string, number> | null;
      round2_scores: Record<string, number> | null;
      conflicts: { raised_by: string; concern: string }[] | null;
      resolution_rationale: string | null;
      confidence: number | null;
    };
  };
  multi_agent_diagnostic: MultiAgentDiagnostic | null;
  multi_agent_diagnostic_previous: MultiAgentDiagnostic | null;
  risk_manager_diagnostic: RiskManagerDiagnostic | null;
  risk_manager_calibration: RiskManagerCalibration | null;
  risk_manager_generalization: RiskManagerGeneralization | null;
  empty_state: string | null;
}

export interface RiskRegimeAgg {
  label: string;
  n_rows: number;
  n_sub_series?: number;
  spearman_rho_dist_vs_r0: number | null;
  spearman_rho_dist_vs_r1: number | null;
  monotonicity_violations_r0: number;
  monotonicity_violations_r1: number;
  r0_equals_r1_all_rows?: boolean;
  r1_never_below_r0?: boolean;
  mean_r0_risk_legit_moves: number | null;
  mean_r1_risk_legit_moves: number | null;
  mean_r0_risk_extreme_probes: number | null;
  mean_r1_risk_extreme_probes: number | null;
  extreme_outside_range_penalised_r1: number | null;
  n_extreme_probes_outside_range?: number;
}

export interface RiskManagerGeneralization {
  experiment_id: string;
  experiment_name?: string;
  created_at: string | null;
  dataset: { id: string; name: string; category: string; provenance: string; license: string; geography: string } | null;
  synthetic_calibration_reference: { experiment: string; r3_verdict: string } | null;
  regime_classifier: { statistic: string; low_max: number; moderate_max: number } | null;
  regime_counts: Record<string, number> | null;
  sub_series: {
    sub_series: string; grain: string; n_points: number; n_line_items: number;
    price_variance_regime: string; historical_price_scale_rcv: number;
    historical_price_min: number; historical_price_max: number; historical_price_median: number;
  }[] | null;
  risk_regime_by_regime: Record<string, RiskRegimeAgg> | null;
  risk_regime_overall: RiskRegimeAgg | null;
  decision_comparison_simulated: Record<string, {
    selected_strategy: string | null; goal_achievement: number; risk_adjusted_score: number;
    confidence: number | null; selected_dt_risk: number | null; mean_strategy_dt_risk: number | null;
    strategy_changed_vs_r0: boolean;
  }> | null;
  decision_business_meta: Record<string, unknown> | null;
  leakage_check: Record<string, unknown> | null;
  real_llm: { status: string; reason?: string; provider?: string | null; model?: string | null } | null;
  decision_outcome: { decision_outcome_records: number; matched_prediction_evaluations: number; status: string; table_2: string } | null;
  hypotheses: Record<string, string> | null;
  external_validation: {
    criteria: Record<string, boolean>;
    core_criteria_passed: boolean;
    central_benefit_confirmed_on_real_data: boolean;
    anything_regressed_on_real_data: boolean;
    verdict: string;
  } | null;
  production_default: string | null;
}

export interface RiskCalibrationVariantAgg {
  variant: string;
  n_pairs: number;
  goal_achievement: StatSummary | null;
  risk_adjusted_score: StatSummary | null;
  confidence: StatSummary | null;
  mean_selected_dt_risk: number | null;
  mean_strategy_dt_risk: number | null;
  mean_strategy_rm_score: number | null;
  dt_best_agreement_rate: number | null;
  override_rate: number | null;
  override_improved: number;
  override_degraded: number;
  override_neutral: number;
  risk_monotonicity: {
    spearman_rho_distance_vs_risk: number | null;
    price10_safer_than_price5_violations: number;
    violation_pairs: { scenario_id: string; seed: number; price5_risk: number; price10_risk: number }[];
  };
}

export interface RiskManagerCalibration {
  experiment_id: string;
  experiment_name?: string;
  created_at: string | null;
  seeds: number[] | null;
  total_scenario_seed_pairs: number;
  risk_formula_versions: { R0: string; R1_R3: string; robust_scale_rel_floor: number } | null;
  r3_selection: { lambda: number; rule: string } | null;
  digital_twin_mean_goal_achievement: number | null;
  variants: string[] | null;
  aggregates: Record<string, RiskCalibrationVariantAgg> | null;
  paired_vs_r0: Record<string, {
    comparison: string; difference_is: string; n_pairs: number;
    mean_difference: number; median_difference: number; std_difference: number;
    ties: number; mean_difference_ci95: [number, number] | null;
    test?: string; p_value?: number | null; effect_size_r?: number | null;
    interpretation: string;
    [k: string]: unknown;
  }> | null;
  zero_variance_diagnostic: Record<string, Record<string, { R0: number; R1: number }>> | null;
  pre_specified_criteria: string[] | null;
  criteria_evaluation: Record<string, {
    checks: Record<string, boolean>;
    criteria_passed: number; criteria_total: number; verdict: string;
  }> | null;
  verdict: string | null;
  verdict_by_variant: Record<string, string> | null;
  best_calibration_variant: string | null;
}

export interface StatSummary {
  n: number; mean: number; median: number; std: number; min: number; max: number;
  ci95: [number, number] | null;
}

export interface RiskManagerDiagnostic {
  experiment_id: string;
  experiment_name?: string;
  created_at: string | null;
  seeds: number[] | null;
  total_scenario_seed_pairs: number;
  baseline: {
    full_decisiongpt_mean_goal_achievement: number | null;
    digital_twin_mean_goal_achievement: number | null;
    d1_risk_penalty_sensitivity_mean_goal_achievement: number | null;
  } | null;
  formula_verification: {
    checked: string; max_deviation_observed: number; holds_for_all_rows: boolean; rows_checked: number;
  } | null;
  risk_manager_disagreement: { disagreements_vs_dt_best: number; disagreement_rate: number | null } | null;
  rm_decisive: {
    count: number; percentage: number | null; improved: number; degraded: number; neutral: number;
    definition: string;
    pairs: { scenario_id: string; seed: number; d0_pick: string | null; penalty_free_pick: string | null; outcome: string | null }[];
  } | null;
  risk_score_mismatch: {
    count: number; strategy_rows_inspected: number; percentage: number | null; definition: string;
    rm_distinguishes_low_vs_high_risk_price_strategies: {
      assessable: boolean; note?: string; price_strategy_observations?: number;
      rm_score_spread?: number; dt_risk_spread?: number; rm_score_all_zero_for_price?: boolean; verdict?: string;
    };
    calibration_table: {
      strategy: string; observations: number;
      mean_digital_twin_risk?: number; mean_risk_manager_score?: number;
      rm_score_zero_rate?: number; dt_risk_low_rate?: number;
    }[];
  } | null;
  d0_vs_d1: {
    goal_achievement: { D0: StatSummary | null; D1: StatSummary | null };
    risk_adjusted_score: { D0: StatSummary | null; D1: StatSummary | null };
    confidence: { D0: StatSummary | null; D1: StatSummary | null };
    dt_best_agreement_rate: { D0: number | null; D1: number | null };
    override_rate_vs_dt_best: { D0: number | null; D1: number | null };
  } | null;
  paired_d1_minus_d0: {
    comparison: string; metric: string; n_pairs: number;
    mean_difference: number; median_difference: number; std_difference: number;
    d1_wins: number; ties: number; d0_wins: number;
    mean_difference_ci95: [number, number] | null;
    test?: string; statistic?: number | null; p_value?: number | null; effect_size_r?: number | null;
    interpretation: string; difference_is: string;
  } | null;
  interpretation: {
    outcome: string;
    removing_rm_penalty_improves_full: string;
    rm_penalty_explains_the_gap: string;
    paired_significant: boolean;
    delta_d1_minus_d0: number;
    fraction_of_gap_closed: number | null;
    text: string;
  } | null;
  scenario_drilldown: {
    scenario_id: string; seed: number; goal_objective: string;
    d0_selected_strategy: string | null; d1_selected_strategy: string | null;
    d0_goal_achievement: number; d1_goal_achievement: number;
    d0_confidence: number | null; d1_confidence: number | null;
    rm_decisive: boolean; rm_decisive_outcome: string | null;
    rm_top_pick: string | null; dt_sweep_best_strategy: string | null;
    risk_score_mismatch_count: number;
  }[];
}

export interface CandidateCoverage {
  pairs_checked: number;
  dt_best_present_in_full: number;
  candidate_coverage_rate: number | null;
  missing_supported_strategy_rate: number | null;
  mean_dt_candidate_count: number | null;
  mean_full_candidate_count: number | null;
  invariant_dt_best_present_when_supported: boolean;
  missing_pairs: { scenario_id: string; seed: number; dt_best_strategy: string; goal_objective: string }[];
}

export interface MultiAgentDiagnostic {
  experiment_id: string;
  experiment_name?: string;
  created_at: string | null;
  seeds: number[] | null;
  total_scenario_seed_pairs: number;
  candidate_coverage: CandidateCoverage | null;
  digital_twin_to_final: { unchanged: number; overridden: number; override_rate: number };
  override_outcomes: {
    improved: number; degraded: number; neutral: number;
    override_improvement_rate: number; override_degradation_rate: number; override_neutral_rate: number;
  };
  failure_modes: Record<string, { count: number; percent: number; mean_dt_revenue: number | null; mean_final_goal_achievement: number | null; note?: string }>;
  central_hypothesis: {
    statement: string;
    agent_layer_overrides_dt_best_in_its_own_set: number;
    of_those_improved: number; of_those_degraded: number; of_those_neutral: number;
    verdict: string;
  };
  risk_manager_effect: { disagreement_rate_vs_dt_best: number; disagreements: number; of_those_degraded: number; of_those_improved: number };
  optimizer_effect: { dt_best_to_final_change_rate: number; mean_goal_achievement_when_unchanged: number | null; mean_goal_achievement_when_changed: number | null; note: string };
  causal_evidence_effect: { by_level: Record<string, { count: number; mean_final_goal_achievement: number; mean_confidence: number | null }>; note: string };
  digital_twin_mean_goal_achievement: number;
  full_decisiongpt_mean_goal_achievement: number;
  failure_analysis_figure: {
    digital_twin_best: number; unchanged: number; overridden: number;
    overridden_improved: number; overridden_degraded: number; overridden_neutral: number;
  };
  scenario_drilldown: {
    scenario_id: string; seed: number; goal_objective: string;
    digital_twin_best: string | null; final_strategy: string | null; disagreement: boolean;
    failure_mode: string; improvement: number; final_goal_achievement: number;
    risk_manager_top_pick: string | null; mechanism_evidence: string;
  }[];
}

export interface PaperResults {
  summary: { tables_total: number; tables_ready: number; tables_missing: number };
  tables: {
    key: string;
    title: string;
    available: boolean;
    missing_reason: string | null;
    export_tables: string[];
    sections: { name: string; headers: string[]; rows: (string | number | null)[][]; row_count: number }[];
    source_refs: Record<string, unknown>;
  }[];
  export_formats: string[];
}
