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
  created_at: string;
  created_by: string | null;
  version_count: number;
  latest_version: number | null;
  versions: DatasetVersion[];
}

export interface DatasetsResponse {
  platform: PlatformDatasetEntry[];
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

  exportTable: (table: ExportTable, format: ExportFormat, experimentId?: string) =>
    researchPostText("/research/export", { table, format, experiment_id: experimentId ?? null }),
};
