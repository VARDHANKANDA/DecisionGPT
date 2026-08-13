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

export interface DatasetEntry {
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
  created_at: string;
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
  listDatasets: () => researchGet<DatasetEntry[]>("/research/datasets"),
  listModels: (modelType?: string) =>
    researchGet<ModelEntry[]>(`/research/models${modelType ? `?model_type=${modelType}` : ""}`),
  syncModels: () => researchPost<ModelEntry[]>("/research/models/sync"),

  runExperiment: (experimentType: ExperimentType, configuration: Record<string, unknown> = {}) =>
    researchPost<ExperimentRun>("/research/experiments/run", { experiment_type: experimentType, configuration }),
  listExperiments: (experimentType?: ExperimentType) =>
    researchGet<ExperimentRun[]>(`/research/experiments${experimentType ? `?experiment_type=${experimentType}` : ""}`),
  getExperiment: (id: string) => researchGet<ExperimentRun>(`/research/experiments/${id}`),

  exportTable: (table: ExportTable, format: ExportFormat, experimentId?: string) =>
    researchPostText("/research/export", { table, format, experiment_id: experimentId ?? null }),
};
