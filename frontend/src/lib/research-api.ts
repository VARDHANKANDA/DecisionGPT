import { TOKEN_STORAGE_KEY as BEARER_TOKEN_KEY } from "@/lib/api";

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
  const headers: Record<string, string> = {};
  // Preferred: the signed-in session. The backend grants research access to a
  // user whose role is "admin"; a non-admin bearer token is rejected (403), so
  // this never widens access.
  const bearer =
    typeof window !== "undefined" ? window.localStorage.getItem(BEARER_TOKEN_KEY) : null;
  if (bearer) headers["Authorization"] = `Bearer ${bearer}`;
  // Fallback for CI / scripts / a researcher without an account.
  const consoleToken = getResearchToken();
  if (consoleToken) headers["X-Research-Token"] = consoleToken;
  return headers;
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
  lifecycle_json?: { validation?: { passed: boolean; warnings: string[] }; promotion?: { by: string; reason: string; at: string } } | null;
  /** validated | rejected | not_validated | not_validated_bootstrap (activated as the first version; never validated) */
  validation_status?: string;
  applicability?: {
    provenance?: string;
    target?: string;
    target_unit?: string;
    aggregation?: string;
    population?: string;
    source?: string;
    eligible_for?: { business_level_forecast: boolean; price_scenarios: boolean; customer_scoring: boolean };
    eligible_for_production_use?: boolean;
    reasons?: string[];
  } | null;
}

export interface ModelValidation {
  model_id: string;
  model_name: string;
  version: string;
  status: string;
  passed: boolean;
  warnings: string[];
  checks: { name: string; passed: boolean; blocking: boolean; detail: string }[];
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

export interface LlmEvalQuality {
  n_attempts: number;
  n_tasks?: number;
  accuracy_primary_pct?: number | null;
  n_correct?: number;
  accuracy_first_number_pct?: number | null;
  outcomes?: Record<string, number>;
  failure_rates_pct?: Record<string, number | null>;
  numeric_error?: { median_rel_error_first_number: number | null; mean_abs_error_first_number: number | null };
  repeat_consistency?: { tasks_with_identical_verdict_across_repeats: number; of_tasks: number };
}
export interface LlmEvalEfficiency {
  latency_end_to_end_s: { median: number | null; p95: number | null };
  llm_calls_per_attempt_mean: number | null;
  tokens: { input_total: number | null; output_total: number | null };
  cost_usd_total: number | null;
}
export interface LlmEvalTrack {
  quality: LlmEvalQuality;
  by_category: Record<string, LlmEvalQuality>;
  efficiency: LlmEvalEfficiency;
}
export interface LlmEvalTaskRow {
  task_id: string;
  category: string | null;
  track: string | null;
  question: string | null;
  attempts: number;
  correct: number;
  excluded: number;
  errors: number;
  outcomes: Record<string, number>;
  paths?: Record<string, number>;
  path_classes?: Record<string, number>;
  failure_category?: string | null;
  answer_excerpt?: string | null;
  ground_truth?: unknown;
  median_latency_s: number | null;
}

export interface LlmEvalTrackCounts {
  attempts: number;
  correct: number;
  excluded: number;
  errors: number;
  outcomes: Record<string, number>;
}

export interface LlmEvalRunSummary {
  run_type: "full" | "partial_pilot" | null;
  note: string | null;
  tasks_in_spec: number | null;
  task_ids_attempted: string[] | null;
  task_ids_not_attempted: string[] | null;
  repeats_used: number | null;
  repeats_frozen: number | null;
  primary: LlmEvalTrackCounts;
  supplementary: LlmEvalTrackCounts;
  answer_paths: Record<string, number> | null;
  provider_requests: number | null;
  attempt_errors: number | null;
  models_returned: string[] | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd_at_list_price: number | null;
  spec_sha256: string | null;
  manifest_sha256: string | null;
}

export interface LlmEvalRunRow {
  run_id: string;
  kind: "live_evaluation" | "mock_validation" | "plumbing_check" | "blocked" | "other";
  status: string | null;
  mode: string | null;
  research_result: boolean;
  mock: boolean;
  created_utc: string | null;
  finished_utc: string | null;
  planned_attempts: number | null;
  completed_attempts: number | null;
  n_tasks: number | null;
  repeats: number | null;
  run_type?: string | null;
  tasks_attempted?: number | null;
  tasks_in_spec?: number | null;
  provider: string | null;
  model: string | null;
  errors: number | null;
  note: string | null;
}

export interface LlmEvaluationStatus {
  state:
    | "blocked_production_path"
    | "blocked_provider_not_configured"
    | "not_configured"
    | "ready_to_run"
    | "running"
    | "completed"
    | "partial"
    | "failed";
  /** "run" once a research run exists; "not_run" otherwise (no metrics are shown for not_run). */
  evaluation: "run" | "not_run";
  production_llm_path: {
    status: "available" | "disabled" | "not_connected_to_analytics_chat" | "unknown";
    detail: string;
    frozen_questions_total?: number | null;
    frozen_questions_that_reach_the_llm_interpreter_when_configured?: number | null;
    legacy_router_recognizes?: number;
    audit_date?: string;
  };
  blockers: string[];
  class_counts: Record<string, Record<string, number>> | null;
  label: string;
  evaluated: boolean;
  llm: { enabled: boolean; provider: string | null; model: string | null };
  infrastructure: { task_spec: boolean; ground_truth: boolean; dataset_present: boolean; ready: boolean };
  dataset: { description?: string; provenance_limitation?: string; license?: string; representativeness?: string } | null;
  tasks: { n: number; n_primary: number; n_supplementary: number; repeats_per_task: number | null; categories: string[] };
  view_rules: string | null;
  latest_run: null | {
    run_id: string;
    status: string;
    finished_utc: string | null;
    completed_attempts: number | null;
    planned_attempts: number | null;
    llm: { provider?: string | null; model_configured?: string | null } | null;
    metrics: Record<string, Record<string, LlmEvalTrack>> | null;
    per_task?: LlmEvalTaskRow[];
    summary?: LlmEvalRunSummary;
  };
  /** Coverage of the frozen tasks by genuine research runs, one entry per provider (providers are never pooled). */
  live_coverage?: null | Array<{
    provider: string;
    is_active_provider: boolean;
    runs: Array<{ run_id: string; run_type: string | null; tasks: number; repeats: number | null; primary_correct: number; primary_attempts: number; provider_requests: number | null; input_tokens: number | null; model?: string | null; estimated_cost_usd_at_list_price: number | null }>;
    tasks_in_spec: number;
    tasks_attempted_at_least_once: number;
    task_ids_never_attempted: string[];
    repeats_frozen: number | null;
    max_repeats_any_run: number;
    primary_correct_sum: number;
    primary_attempts_sum: number;
    provider_requests_sum: number;
    estimated_cost_usd_sum: number | null;
    note: string;
  }>;
  /** Every stored run, newest first, labelled by what it is (live_evaluation | mock_validation | plumbing_check | blocked | other). */
  run_history?: LlmEvalRunRow[];
  /** Real connectivity checks against the provider. Never an evaluation. */
  live_verification?: null | {
    records: number;
    requests_total: number;
    latest_date: string | null;
    provider: string | null;
    all_http_200: boolean | null;
    summary: string | null;
    does_not_show: string[];
    requests: Array<{
      step: string;
      through_production_client: boolean;
      http_status: number;
      model_reported?: string | null;
      input_tokens?: number | null;
      output_tokens?: number | null;
      latency_s?: number | null;
      answers_accepted?: number | null;
      note?: string;
    }>;
  };
  run_plan?: {
    provider?: string | null;
    model?: string | null;
    tasks: number;
    repeats_per_task: number;
    planned_attempts: number;
    primary_attempts: number;
    provider_requests_per_attempt: number;
    measured_input_tokens_per_request: number | null;
    estimated_input_tokens: number | null;
    estimated_cost_usd_at_list_price: number | null;
    estimate_basis: string;
    runnable_now: boolean;
  };
  baselines?: Array<{ id: string; name: string; runs_on_provider: boolean; reason: string }>;
  last_blocked_attempt: null | { run_id: string; created_utc: string | null; reason: string | null };
  /** Infrastructure validation with a fake provider. Never a research result; no metrics are exposed. */
  mock_validation: null | { run_id: string; status: string | null; completed_attempts: number | null; planned_attempts: number | null; finished_utc: string | null; note: string };
  limitations: string[];
}


// ---------------------------------------------------------------- Research Console v2 read models
export type EvidenceType = "measured" | "measured_on_synthetic_data" | "estimated" | "simulated" | "not_evaluated";

export interface ResearchSummary {
  objective: string;
  datasets: Array<{ name: string; provenance: string; observations: number | null; period: string | null; status: string }>;
  algorithms: string[];
  n_algorithms: number;
  methodology: string[];
  status: {
    experiments_completed: number | null;
    experiments_failed: number | null;
    model_comparison_runs: number;
    live_llm_runs: number;
    validation_state: string;
    validation_counts: Record<string, number>;
  };
  measured_metrics: string[];
  key_findings: Array<{ evidence: EvidenceType; area: string; text: string; source: string | null }>;
  limitations: string[];
  latest_verified_run: string | null;
  evidence_legend: Array<{ key: string; label: string; meaning: string }>;
  generated_utc: string;
}

export interface ModelMetrics {
  n: number;
  mae: number;
  rmse: number;
  bias: number;
  r2: number | null;
  r2_note: string | null;
  mape_pct: number | null;
  mape_note: string | null;
  rmse_change_vs_baseline_pct?: number | null;
  beats_baseline_on_test_rmse?: boolean;
}

export interface ModelComparisonRun {
  status: string;
  run_id: string;
  created_utc: string;
  evidence_type: EvidenceType;
  dataset: { name: string; provenance: string; source: string; target: string; unit: string };
  n_usable_observations: number;
  period: { first: string; last: string };
  features: string[];
  split: Record<string, { first: string; last: string; dates: number; rows: number }>;
  cv: { scheme: string; folds: Array<{ train: string[]; validate: string[] }> };
  baseline: { key: string; label: string };
  models: Record<
    string,
    {
      label: string;
      params: Record<string, unknown>;
      cv_rmse_mean: number;
      cv_rmse_sd: number;
      validation?: {
        rmse: number;
        mae: number;
        r2: number | null;
        r2_note?: string;
      };
      test: ModelMetrics;
      paired_vs_baseline?: { mean_abs_error_diff_model_minus_baseline: number; ci95: number[]; reading: string; draws: number };
    }
  >;
  selection: { rule: string; selected: string; selected_label: string; test: ModelMetrics; beats_baseline_on_test_rmse: boolean };
  uncertainty: { model: string; method: string; nominal_coverage: number; empirical_coverage_test: number; test_points: number; mean_interval_width: number; reading: string };
  test_error_by_date: Array<{ date: string; mean_abs_error: number }>;
  checks: Record<string, unknown>;
  reproducibility: Record<string, string>;
  limitations: string[];
}

export interface ModelComparison {
  datasets: Record<string, ModelComparisonRun | null>;
  available: string[];
  not_run: string[];
  dataset_catalogue: Record<string, { name: string; provenance: string; source: string; target: string; unit: string }>;
}

export interface ValidationCheck {
  id: string;
  group: string;
  subject: string;
  rule: string;
  status: "passed" | "failed" | "warning" | "not_applicable";
  observed: unknown;
  explanation: string;
  remedy: string | null;
}

export interface ValidationReport {
  state: "no_checks_run" | "failed" | "passed_with_warnings" | "passed";
  counts: Record<"passed" | "failed" | "warning" | "not_applicable", number>;
  checks_run: number;
  total_checks: number;
  datasets: Array<{ key: string; label: string; rows: number | null }>;
  checks: ValidationCheck[];
  generated_utc: string;
}

export interface ArchitectureEvaluation {
  headline: string;
  architectures: Array<{ key: string; name: string; includes: string[]; produces: string }>;
  metric_definitions: Array<{ metric: string; unit: string; better: string; definition: string }>;
  primary_evidence: null | {
    evidence_type: EvidenceType;
    source: string;
    design: { scenarios: number; seeds: number; decisions_per_architecture: number; multiplicity: string };
    architectures: Array<{ key: string; name: string; mean_regret: number; ci95: number[]; n_decisions: number }>;
    reference_points: Record<string, number>;
    comparisons: Array<{ contrast: string; label: string; mean_difference: number; ci95: number[]; p_holm: number | null; wins: number; ties: number; losses: number; n_scenarios: number }>;
    family_effects_D_minus_B: Array<{ family: string; mean_D_minus_B: number; ci95: number[]; direction: string; n_scenarios: number }>;
    mechanism: { n: number; changed: number; improved: number; worsened: number; no_change: number } | null;
  };
  improved_multiagent_study?: null | {
    evidence_type: EvidenceType;
    source: string;
    timestamp: string;
    partition: string;
    n_families: number;
    n_instances: number;
    headline: string;
    key_takeaway: string;
    rows: Array<{
      key: string;
      label: string;
      mean_regret: number;
      sd_regret: number;
      median_regret: number;
      ci95_regret: [number, number];
      delta_vs_B: number;
      ci95_vs_B: [number, number];
      p_raw_vs_B: number;
      p_holm_vs_B: number;
      delta_vs_D: number;
      ci95_vs_D: [number, number];
      p_raw_vs_D: number;
      p_holm_vs_D: number;
      constraint_violations: number;
      goal_achievement_pct: number;
      mean_latency_sec: number;
      mean_cost_usd: number;
      n_instances: number;
    }>;
  };
  frozen_suite: null | { source: string; pairs: number; rows: Array<{ key: string; label: string; mean_goal_achievement: number }>; note: string };
  single_decision: null | {
    n_decisions_per_architecture: number;
    goal_target_percent: number;
    caveats: string[];
    rows: Array<{
      key: string;
      label: string;
      status: "evaluated" | "not_applicable";
      selected_strategy: string | null;
      goal_achievement: number | null;
      expected_benefit: number | null;
      risk_adjusted_score: number | null;
      latency_seconds: number;
      note: string | null;
    }>;
  };
  comparability: string[];
  limitations: string[];
}

export interface CausalAssessment {
  assessment: {
    pairs: Array<{
      pair: string;
      treatment: string;
      outcome: string;
      status: "unsupported" | "identified_by_design" | "identified_by_backdoor" | string;
      status_label?: string;
      ate_estimate?: string;
      smd_balance?: Record<string, number>;
      reasons: string[];
      needs: string[];
      note?: string;
      n?: number;
    }>;
    distinguish: Array<{ term: string; meaning: string }>;
    multiple_testing?: {
      fdr_benjamini_hochberg: Record<string, any>;
      fwer_holm_bonferroni: Record<string, any>;
      interpretation: string;
    };
  };
  known_truth_simulation: null | {
    run_id: string;
    created_utc: string;
    known_truth_simulation: {
      estimand: string;
      estimator: string;
      n_rows: number;
      n_series: number;
      n_treated_days: number;
      estimate_pct: number;
      ci95_pct: number[];
      documented_truth_pct: number;
      truth_inside_ci: boolean;
      bootstrap_draws: number;
      balance_standardised_mean_differences: Record<string, number>;
      reading: string;
    };
  };
  graph_evidence: {
    overview: { total_graph_versions: number; businesses_with_a_graph: number; evidence_counts_latest_per_business: Record<string, number> };
    method_validation: { precision: number; recall: number; f1: number; structural_hamming_distance: number; label: string; notes: string[] } | null;
  };
}

export interface RiskAssessment {
  definitions: Array<{ kind: string; is_probability: boolean; meaning: string; calibration: string; why: string }>;
  churn_probability_calibration: null | {
    run_id: string;
    created_utc: string;
    evidence_type: EvidenceType;
    event: string;
    model: string;
    split: { scheme: string; train_rows: number; test_rows: number };
    baseline: string;
    metrics: {
      n: number;
      positives: number;
      prevalence: number;
      brier: number;
      brier_baseline_prevalence: number;
      brier_skill_score: number | null;
      brier_ci95: number[];
      log_loss: number;
      log_loss_baseline_prevalence: number;
      roc_auc: number | null;
      ece: number;
      ece_definition: string;
      reliability_table: Array<{ bin: number[]; n: number; mean_predicted: number | null; observed_rate: number | null }>;
    };
    limitations: string[];
  };
  forecast_uncertainty: Array<{
    dataset: string;
    provenance: string;
    run_id: string;
    model: string;
    nominal_coverage: number;
    empirical_coverage: number;
    test_points: number;
    mean_interval_width: number;
    unit: string;
    method: string;
    reading: string;
  }>;
  decision_risk_score: {
    status: string;
    is_calibrated?: boolean;
    recorded_real_outcomes: number;
    prerequisites: Array<{ need: string; met: boolean; observed?: number }>;
    metrics?: {
      brier: number;
      brier_baseline_prevalence: number;
      brier_skill_score: number | null;
      brier_ci95: number[];
      log_loss: number;
      log_loss_baseline_prevalence: number;
      ece: number;
      reliability_table: Array<{ bin: number[]; n: number; mean_predicted: number | null; observed_rate: number | null }>;
    };
    risk_categories?: Array<{ range: string; title: string; description: string }>;
    next_step: string;
  };
  synthetic_variant_study: { evidence_type: EvidenceType; note: string; verdict: string; variants: Array<{ variant: string; mean_goal_achievement: number | null; verdict: string | null }> };
}

export interface LlmRunDetail {
  run_id: string;
  kind: string;
  status: string | null;
  is_live_result: boolean;
  created_utc: string | null;
  finished_utc: string | null;
  provider: string | null;
  model_requested: string | null;
  models_returned: string[] | null;
  summary: LlmEvalRunSummary;
  attempts: Array<{
    task_id: string;
    repeat: number | null;
    track: string;
    category: string;
    question: string;
    answer: string | null;
    expected: unknown;
    outcome: string;
    correct: boolean;
    path: string | null;
    path_class: string | null;
    failure_category: string | null;
    excluded_from_accuracy: boolean;
    error: string | null;
    latency_s: number | null;
    input_tokens: number | null;
    output_tokens: number | null;
    cost_usd: number | null;
  }>;
  technical: Record<string, unknown>;
}

export interface PreprocessStep {
  id: string;
  title: string;
  rationale: string;
  applies: boolean;
  default_enabled: boolean;
  affected_rows: number | null;
  affected_columns: string[];
  detail: string;
  status: string;
}

export interface PreprocessPlan {
  version_id: string;
  rows: number;
  columns: number;
  schema: Array<{ name: string; dtype: string; missing: number }>;
  duplicate_rows: number;
  steps: PreprocessStep[];
  runs: Array<{ run_id: string; status: string; created_utc: string; rows_in: number | null; rows_out: number | null; columns_in: number | null; columns_out: number | null; error: string | null }>;
}

export interface PreprocessRun {
  status: string;
  run_id: string;
  source_version_id: string;
  created_utc: string;
  error?: string;
  rows_in?: number;
  rows_out?: number;
  columns_in?: number;
  columns_out?: number;
  rows_removed?: number;
  raw_dataset_modified: boolean;
  business_totals_changed?: boolean;
  steps?: Array<{ id: string; title: string; status: string; rows_affected: number; columns_affected: string[]; detail: string; rationale: string }>;
  output_columns?: string[];
  output_sha256?: string;
  config?: { input_sha256: string };
}

export const researchApi = {
  // Research Console v2 read models
  summary: () => researchGet<ResearchSummary>("/research/summary"),
  modelComparison: () => researchGet<ModelComparison>("/research/model-comparison"),
  mlBenchmark: () => researchGet<MlBenchmark>("/research/ml-benchmark"),
  runModelEvaluation: (modelId: string) =>
    researchPost<{ model_id: string; status: string; reason: string | null; evaluated_at: string | null }>(`/research/evaluation/models/${encodeURIComponent(modelId)}/run`),
  runPendingEvaluations: () =>
    researchPost<{ attempted: number; evaluated: number; results: { model_id: string; model: string; status: string; reason: string | null }[] }>(
      "/research/evaluation/models/run-pending",
    ),
  runModelComparison: () => researchPost<Record<string, { status: string; run_id: string | null; reason: string | null }>>("/research/model-comparison/run"),
  validationReport: () => researchGet<ValidationReport>("/research/validation"),
  architectureEvaluation: () => researchGet<ArchitectureEvaluation>("/research/architecture-evaluation"),
  causalAssessment: () => researchGet<CausalAssessment>("/research/causal-assessment"),
  riskAssessment: () => researchGet<RiskAssessment>("/research/risk-assessment"),
  llmRunDetail: (runId: string) => researchGet<LlmRunDetail>(`/research/llm-evaluation/runs/${encodeURIComponent(runId)}`),
  preprocessingPlan: (versionId: string) => researchGet<PreprocessPlan>(`/research/preprocessing/${versionId}/plan`),
  runPreprocessing: (versionId: string, steps?: string[]) => researchPost<PreprocessRun>(`/research/preprocessing/${versionId}/run`, steps ? { steps } : {}),
  preprocessingRun: (versionId: string, runId: string) => researchGet<PreprocessRun>(`/research/preprocessing/${versionId}/runs/${runId}`),
  downloadPreprocessed: async (versionId: string, runId: string): Promise<Blob> => {
    const response = await fetch(`${API_BASE_URL}/research/preprocessing/${versionId}/runs/${runId}/download`, { headers: authHeaders(), cache: "no-store" });
    if (!response.ok) throw new ResearchApiError(response.status, "DOWNLOAD_FAILED", `Download failed with status ${response.status}`);
    return response.blob();
  },
  llmEvaluation: () => researchGet<LlmEvaluationStatus>("/research/llm-evaluation"),
  externalBenchmark: () => researchGet<ExternalBenchmarkReport>("/research/external-benchmark"),
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
  validateModel: (id: string) => researchPost<ModelValidation>(`/research/models/${id}/validate`),
  promoteModel: (id: string, reason: string) => researchPost<ModelEntry>(`/research/models/${id}/promote`, { reason }),
  rollbackModel: (model_name: string, reason: string) => researchPost<ModelEntry>(`/research/models/rollback`, { model_name, reason }),
  archiveModel: (id: string, reason = "archived from the Model Registry") => researchPost<ModelEntry>(`/research/models/${id}/archive`, { reason }),

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
  // --- evaluation metrics (shared metric registry; every value is recorded by a run) ----------
  evaluation: () => researchGet<EvaluationOverview>("/research/evaluation"),
  evaluationBusiness: (businessId: string) => researchGet<BusinessValidation>(`/research/evaluation/business/${businessId}`),
  runEvaluationBusiness: (businessId: string, kind: "forecast" | "customer") =>
    researchPost<PresentedValidationRun>(`/research/evaluation/business/${businessId}/run?kind=${kind}`),
  digitalTwinEvaluation: () => researchGet<DigitalTwinEvaluation>("/research/digital-twin-evaluation"),
  digitalTwinEvaluationBackfill: () =>
    researchPost<{ evaluations_created: number }>("/research/digital-twin-evaluation/backfill"),
  causalEvaluation: () => researchGet<CausalEvaluation>("/research/causal-evaluation"),
  agentEvaluation: () => researchGet<AgentEvaluation>("/research/agent-evaluation"),
  paperResults: () => researchGet<PaperResults>("/research/paper-results"),
  verifiedResults: () => researchGet<VerifiedResearchResults>("/research/verified-results"),
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
export interface EvalMini {
  value: number | null;
  display: string | null;
  status: string;
  kind: string | null;
  reason: string | null;
}
export type EvaluationStatus = "evaluated" | "pending" | "unavailable" | "failed";
export interface EvaluationSummaryRow {
  model_id: string;
  model_name: string;
  version: string;
  model_status: string;
  dataset_version: string;
  evaluation_status: EvaluationStatus;
  evaluation_kind: string | null;
  evaluation_reason: string | null;
  evaluated_at: string | null;
  can_run: boolean;
  test_window: (string | null)[] | null;
  n_eval: number | null;
  horizon: string;
  baseline_name: string;
  method: string | null;
  is_baseline_model: boolean;
  wape: EvalMini;
  forecast_accuracy?: EvalMini;
  mae: EvalMini;
  rmse: EvalMini;
  mape: EvalMini;
  baseline_wape: EvalMini;
  baseline_forecast_accuracy?: EvalMini;
  wape_vs_baseline: EvalMini;
  mae_vs_baseline: EvalMini;
  verdict_wape: string | null;
}
export interface EvaluationSummary {
  basis: string;
  rows: EvaluationSummaryRow[];
  definitions: { key: string; name: string; abbr: string; definition: string; caveat: string | null; direction_text: string }[];
}
export interface ModelPerformance {
  evaluation_summary?: EvaluationSummary;
  summary: {
    registered_models: number;
    active_models: number;
    experimental_models: number;
    completed_training_runs: number;
    failed_training_runs: number;
    best_forecasting: BestMetric | null;
    best_forecasting_note?: string | null;
    best_churn: BestMetric | null;
    best_accuracy?: BestMetric | null;
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
  verified_research_results?: VerifiedResearchResults | null;
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
  research_status?: {
    real_llm: string;
    real_llm_blocked: boolean;
    r3_status: string;
    production: string;
    production_is_r0: boolean;
  };
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
    data_category?: string;
    export_tables: string[];
    sections: { name: string; headers: string[]; rows: (string | number | null)[][]; row_count: number }[];
    source_refs: Record<string, unknown>;
  }[];
  export_formats: string[];
}

// ---- ML benchmark (read-only stored runs, grouped by evidence class)
export interface MlBenchmarkForecastRow {
  method: string;
  kind: "baseline" | "single" | "ensemble";
  wape: number | null;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  aggregate_daily_wape: number | null;
  selected_by_validation: boolean;
  best_single_by_validation?: boolean;
}
export interface MlBenchmarkPaired {
  difference_a_minus_b: number;
  ci95: [number, number] | null;
  method: string;
}
export interface MlBenchmarkSection {
  name: string;
  n_series: number;
  n_test_points: number;
  test_window: string[];
  validation_selected_method: string | null;
  rows: MlBenchmarkForecastRow[];
  paired: Record<string, MlBenchmarkPaired>;
}
export interface MlBenchmarkClassRow {
  method: string;
  accuracy?: number | null;
  roc_auc: number | null;
  pr_auc: number | null;
  brier: number | null;
  ece: number | null;
  isotonic_ece: number | null;
  sigmoid_ece: number | null;
  selected_by_validation: boolean;
}
export interface MlBenchmarkRun {
  run_id: string;
  task: string;
  title: string;
  kind: "forecast" | "classification" | "price_identification" | "reproduction";
  evidence_class: string | null;
  created_utc: string | null;
  git_revision: string | null;
  sections?: MlBenchmarkSection[];
  rows?: MlBenchmarkClassRow[];
  paired?: Record<string, { delta_auc: number; ci95: [number, number] }>;
  prevalence?: Record<string, number>;
  rows_per_split?: Record<string, number>;
  fixed_effects?: Record<string, { coefficient_log_price?: number; ci95?: [number, number]; n_obs?: number; identified?: boolean } | null>;
  price_variation?: { share_of_item_days_with_price_change: number; items_with_any_price_change: number; n_items: number };
  model_counterfactuals?: Record<string, Record<string, { mean_change_pct_of_total: number | null }>>;
  platform?: { data?: Record<string, number> };
  reading?: string[];
  summary?: { max_abs_diff_registry_metrics?: number; max_abs_diff_model_comparison?: number };
}
export interface MlBenchmark {
  available: boolean;
  runs: MlBenchmarkRun[];
  reading_notes?: string[];
  message?: string;
}


// ---- Evaluation metrics (mirrors backend/app/services/metric_registry.py and evaluation_console_service.py) ----
export type MetricStatus = "available" | "not_available" | "not_evaluated" | "unreliable";

export interface MetricCardData {
  key: string;
  name: string;
  abbr: string;
  task: string;
  unit: string;
  direction: "lower_is_better" | "higher_is_better" | "closer_to_zero_is_better" | "closer_to_nominal_is_better" | "informational";
  direction_text: string;
  explanation: string;
  caveat: string;
  sign_note: string | null;
  context: Record<string, string | number | null | undefined>;
  status: MetricStatus;
  /** Why a value is not shown, in finer detail than `status` (absent in reports stored before it existed). */
  kind?: "available" | "not_evaluated" | "not_applicable" | "not_recorded" | "insufficient_data" | "failed" | "unreliable";
  value: number | null;
  display: string;
  reason: string | null;
}

export interface ModelSetup {
  dataset_version: string;
  feature_version: string;
  features: string[];
  dataset_sha256?: string | null;
  random_seed?: number | null;
  splits?: Record<string, { rows: number; first?: string; last?: string }> | null;
  split_scheme: string;
  code_revision?: string | null;
  training_run_id?: string | null;
  source: string;
  trained_at: string | null;
  selection_rule?: string | null;
}

export interface EvalModelIdentity {
  id: string;
  model_name: string;
  model_type: string;
  version: string;
  status: string;
  validation_status: string;
  target: string;
  setup: ModelSetup;
  test: MetricCardData[];
  validation: MetricCardData[];
}

export interface EvalForecastModel extends EvalModelIdentity {
  task: "forecasting";
  evaluation?: {
    status: EvaluationStatus;
    kind: string | null;
    reason: string | null;
    evaluated_at: string | null;
    test_window: (string | null)[] | null;
    n_eval: number | null;
    horizon: string;
    baseline_name: string;
    method: string | null;
    dataset: string;
  };
  baseline: { baseline: string; same_rows: string; test: MetricCardData[]; validation: MetricCardData[]; verdict: string | null };
  interval_coverage: MetricCardData;
  by_horizon: { status: string; reason: string };
}

export interface EvalClassificationModel extends EvalModelIdentity {
  task: "classification";
  positive_class: string;
  confusion_matrix: { tp: number; fp: number; fn: number; tn: number; n: number; positive_class: string; threshold: number | null; rows_are: string; columns_are: string } | null;
  threshold_note: string;
  class_balance: { test_positive_rate: MetricCardData; train_positive_rate: MetricCardData; shift: number | null } | null;
  score_meaning: string;
  calibrated: boolean;
  baseline: { status: string; reason: string };
}

export interface BenchmarkRowCards {
  method: string;
  kind?: string;
  selected_by_validation: boolean;
  cards: MetricCardData[];
  brier_if_always_predicting_the_positive_rate?: number | null;
}

export interface BenchmarkRun {
  run_id: string;
  task: string;
  title: string;
  kind: string;
  evidence_class: string | null;
  created_utc: string | null;
  git_revision: string | null;
  sections?: { name: string; n_series: number | null; n_test_points: number | null; test_window: string[] | null; baseline_used_for_comparison: string | null; rows: BenchmarkRowCards[] }[];
  rows?: BenchmarkRowCards[];
  rows_per_split?: Record<string, number> | null;
  prevalence?: Record<string, number> | null;
  temporal_integrity?: unknown;
  note?: string;
}

export interface EvaluationOverview {
  generated_at: string;
  sections: {
    training: { label: string; note: string; forecasting: EvalForecastModel[]; classification: EvalClassificationModel[]; empty: string | null };
    benchmark: { available: boolean; label: string; runs: BenchmarkRun[]; reason?: string; reading_notes?: string[] };
    production: { label: string; status: string; reason: string };
  };
  availability: { forecasting_models: number; classification_models: number; benchmark_runs: number };
  glossary: { key: string; name: string; abbr: string; task: string; direction_text: string; definition: string; caveat: string | null; sign_note: string | null }[];
  limitations: string[];
}

export interface PresentedHorizon {
  horizon_days: number;
  status: string;
  statement: string | null;
  origins?: number;
  holdout_origins?: number;
  selection_origins?: number;
  method?: string;
  cards: MetricCardData[];
  references?: { method: string; cards: MetricCardData[] }[];
  baseline_comparison?: { reference: string; mae_ratio: number | null; reading: string }[];
  verdict?: string;
  interval_coverage: MetricCardData;
  interval_reliable_by_policy?: boolean;
}

export interface PresentedValidationRun {
  kind: "forecast" | "customer";
  run_id: string | null;
  generated_at: string | null;
  code_revision?: string | null;
  headline: string | null;
  not_evidence_of: string[];
  // forecast
  dataset?: { first_date?: string; last_date?: string; days?: number; sha256?: string } | null;
  series?: { series_class?: string; pattern?: string; zero_share?: number; mean_units_per_day?: number; metric_guidance?: string } | null;
  data_quality?: { calendar_days?: number; days_with_sales_rows?: number; calendar_days_without_rows?: number; missing_day_treatment?: string } | null;
  config?: Record<string, unknown> | null;
  horizons?: PresentedHorizon[];
  // customer
  model?: { name?: string; version?: string; label_provenance?: string; score_meaning?: string } | null;
  target?: { kind?: string; definition?: string; limits?: string } | null;
  cutoffs?: { cutoff: string; label_window?: string[] | null; status: string; reason?: string | null; customers?: number; inactive?: number; cards?: MetricCardData[]; top_decile_lift?: number | null; top_decile_inactive_rate?: number | null }[];
  stable_across_cutoffs?: boolean | null;
  calibration?: MetricCardData;
}

export interface BusinessValidation {
  evidence: "business";
  label: string;
  forecast: PresentedValidationRun | null;
  customer: PresentedValidationRun | null;
}

// ---- Verified Research Results & Real-Data Accuracy ----

export interface VerifiedForecastModelRow {
  name: string;
  type: string;
  val_mae: number | null;
  val_rmse: number | null;
  val_mase: number | null;
  test_mae: number;
  test_rmse: number;
  test_r2: number;
  test_mase: number;
  test_bias: number;
  wape_pct: number;
  forecast_accuracy_pct: number;
  is_selected_winner: boolean;
}

export interface VerifiedChartPoint {
  date: string;
  actual: number;
  predicted: number;
  naive: number;
}

export interface TargetHorizonResult {
  target_name: string;
  horizon: string;
  description: string;
  usable_records: number;
  dev_samples: number;
  test_samples: number;
  test_date_range: [string, string];
  test_sum_volume: number;
  validation_winner: string;
  results_table: {
    model: string;
    type: string;
    val_mae: number;
    mae: number;
    rmse: number;
    r2: number;
    mase: number;
    bias: number;
    wape_pct: number;
    forecast_score_pct: number;
  }[];
}

export interface RealDataAudit {
  file_path: string;
  exact_row_count: number;
  date_range: string;
  calendar_days_spanned: number;
  missing_calendar_dates: number;
  duplicate_dates: number;
  columns: string[];
  target_column: string;
  target_summary: {
    mean: number;
    std: number;
    median: number;
    min: number;
    max: number;
    zero_sales_days: number;
    zero_sales_frequency_pct: number;
  };
  sample_count_reconciliation: Record<string, string | number>;
}

export interface RealData80PctValidation {
  target_achieved: boolean;
  best_operational_horizon: string;
  winning_model: string;
  validation_score_mae: number;
  untouched_test_score_wape_pct: number;
  untouched_test_forecast_score_pct: number;
  naive_baseline_wape_pct: number;
  naive_baseline_score_pct: number;
  relative_error_reduction_pct: number;
  test_sample_size: number;
  test_date_range: string;
  summary: string;
}

export interface VerifiedRealForecasting {
  dataset_id: string;
  dataset_name: string;
  provenance: string;
  evidence_class: string;
  sample_count: number;
  zero_sales_days: number;
  zero_sales_pct: number;
  test_period: string;
  test_samples: number;
  selected_model: string;
  selection_rule: string;
  forecast_accuracy_pct: number;
  accuracy_formula: string;
  metrics: {
    mae: number;
    rmse: number;
    r2: number;
    mase: number;
    bias: number;
    wape_pct: number;
    forecast_accuracy_pct: number;
  };
  baseline_comparison: {
    naive_name: string;
    naive_mae: number;
    naive_rmse: number;
    naive_mase: number;
    naive_r2: number;
    naive_wape_pct: number;
    naive_accuracy_pct: number;
    mae_reduction_pct: number;
    mase_reduction_pct: number;
  };
  chart_data: VerifiedChartPoint[];
  models_table: VerifiedForecastModelRow[];
  scientific_caveat: string;
  audit?: RealDataAudit;
  target_horizons?: Record<string, TargetHorizonResult>;
  real_data_80pct_validation?: RealData80PctValidation;
}

export interface VerifiedSyntheticForecasting {
  dataset_id: string;
  dataset_name: string;
  provenance: string;
  evidence_class: string;
  selected_model: string;
  test_samples: number;
  metrics: {
    mae: number;
    rmse: number;
    r2: number;
    mase: number;
    wape_pct: number;
    forecast_accuracy_pct: number;
  };
  note: string;
}

export interface VerifiedClassificationModelRow {
  name: string;
  type: string;
  val_auc: number | null;
  val_pr_auc: number | null;
  opt_threshold: number | null;
  test_acc: number;
  test_prec: number;
  test_rec: number;
  test_f1: number;
  test_auc: number;
  test_pr_auc: number;
  test_brier: number;
  test_ece: number;
}

export interface VerifiedClassification {
  dataset_id: string;
  dataset_name: string;
  provenance: string;
  evidence_class: string;
  real_data_audit: {
    has_real_labeled_churn_data: boolean;
    status: string;
    explanation: string;
  };
  selected_model: string;
  selection_rule: string;
  test_samples: number;
  selected_threshold: number;
  metrics: {
    accuracy: number;
    balanced_accuracy: number;
    precision: number;
    recall: number;
    f1: number;
    macro_f1: number;
    roc_auc: number;
    pr_auc: number;
    brier: number;
    ece: number;
  };
  confusion_matrix: {
    tn: number;
    fp: number;
    fn: number;
    tp: number;
    n: number;
    positive_class: string;
    threshold: number;
  };
  class_distribution: {
    train_positive_rate: number;
    test_positive_rate: number;
    majority_class_baseline_accuracy: number;
  };
  calibrated_model: {
    name: string;
    ece: number;
    brier: number;
    roc_auc: number;
    f1: number;
    note: string;
  };
  models_table: VerifiedClassificationModelRow[];
}

export interface VerifiedConditionRow {
  id: string;
  name: string;
  regret: number;
  sd: number;
  delta_vs_b: string;
  ci95: string;
  p_val: string;
  violations: number;
}

export interface VerifiedDecisionArchitecture {
  evidence_class: string;
  metric_distinction: string;
  conditions: VerifiedConditionRow[];
  primary_finding: string;
}

export interface VerifiedResearchResults {
  status: string;
  generated_at: string;
  real_forecasting: VerifiedRealForecasting;
  synthetic_forecasting: VerifiedSyntheticForecasting;
  classification: VerifiedClassification;
  decision_architecture: VerifiedDecisionArchitecture;
}

export interface ExternalBenchmarkSystem {
  id: string;
  name: string;
  type: string;
  description: string;
  architecture: string;
  llm_powered: boolean;
  causal_grounded: boolean;
  simulation_enabled: boolean;
}

export interface ExternalBenchmarkMetrics {
  decision_accuracy_pct: number;
  evidence_groundedness_pct: number;
  constraint_adherence_pct: number;
  risk_identification_rate_pct: number;
  hallucination_rate_pct: number;
  avg_latency_s: number;
  avg_cost_usd: number;
  reproducibility_pct: number;
  strengths: string[];
  weaknesses: string[];
}

export interface ExternalBenchmarkReport {
  benchmark_name: string;
  protocol_version: string;
  evaluation_date: string;
  systems: ExternalBenchmarkSystem[];
  tasks: Array<{ id: string; name: string; domain: string; complexity: string; ground_truth_optimal_action: string }>;
  performance_matrix: Record<string, ExternalBenchmarkMetrics>;
  summary: Record<string, string>;
  conclusions: string[];
}

