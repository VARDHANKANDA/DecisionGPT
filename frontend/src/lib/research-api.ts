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
  | "ablation";

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
  | "ablation"
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
  empty_state: string | null;
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
  empty_state: string | null;
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
