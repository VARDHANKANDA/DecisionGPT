const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  code: string;
  details: Record<string, unknown>;
  status: number;

  constructor(status: number, code: string, message: string, details: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let code = "UNKNOWN_ERROR";
    let message = `Request failed with status ${response.status}`;
    let details: Record<string, unknown> = {};
    try {
      const body = await response.json();
      if (body?.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        details = body.error.details ?? {};
      }
    } catch {
      // response body wasn't JSON — keep the generic message
    }
    throw new ApiError(response.status, code, message, details);
  }
  return response.json() as Promise<T>;
}

async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  return handleResponse<T>(response);
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  return handleResponse<T>(response);
}

async function apiUpload<T>(path: string, file: File): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    body: formData,
    cache: "no-store",
  });
  return handleResponse<T>(response);
}

// ---- Types (mirrors backend/app/schemas/*.py) ----

export interface Business {
  id: string;
  name: string;
  industry: string;
  business_type: string;
  business_size: string;
  country: string;
  currency: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface BusinessCreateInput {
  name: string;
  industry: string;
  business_type: string;
  business_size: string;
  description?: string;
}

export interface IngestionJob {
  id: string;
  business_id: string;
  filename: string;
  status: "processing" | "needs_mapping_confirmation" | "completed" | "failed";
  detected_types_json: string[];
  mapping_json: Record<string, unknown>;
  summary_json: {
    rows_ingested?: Record<string, number>;
    quality?: Record<string, unknown>;
  };
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DataSummary {
  products: number;
  customers: number;
  sales: number;
  marketing_campaigns: number;
  inventory_records: number;
}

export interface KPISnapshot {
  period_start: string | null;
  period_end: string | null;
  revenue: number;
  orders: number;
  customers: number;
  average_order_value: number | null;
  profit: number | null;
  marketing_spend: number;
  marketing_roi: number | null;
  conversion_rate: number | null;
  notes: string[];
}

export interface RevenueTrendPoint {
  date: string;
  revenue: number;
}

export interface ForecastPoint {
  forecast_date: string;
  predicted_value: number;
  lower_bound: number;
  upper_bound: number;
}

export interface ForecastResult {
  model_name: string;
  model_version: string;
  metrics: Record<string, number>;
  points: ForecastPoint[];
}

export interface Goal {
  id: string;
  business_id: string;
  objective: string;
  target_value: number;
  target_unit: string;
  primary_kpi: string;
  time_horizon: number | null;
  constraints_json: unknown[];
  status: string;
  created_at: string;
  updated_at: string;
}

// ---- API surface ----

export const api = {
  createBusiness: (input: BusinessCreateInput) =>
    apiPost<Business>("/businesses", { country: "IN", currency: "INR", ...input }),
  getBusiness: (businessId: string) => apiGet<Business>(`/businesses/${businessId}`),

  uploadData: (businessId: string, file: File, dataType?: string) => {
    const query = dataType ? `?data_type=${encodeURIComponent(dataType)}` : "";
    return apiUpload<IngestionJob>(`/businesses/${businessId}/data/upload${query}`, file);
  },
  getIngestionJob: (businessId: string, jobId: string) =>
    apiGet<IngestionJob>(`/businesses/${businessId}/data/jobs/${jobId}`),
  getDataSummary: (businessId: string) => apiGet<DataSummary>(`/businesses/${businessId}/data/summary`),

  getKpis: (businessId: string, periodDays?: number) =>
    apiGet<KPISnapshot>(
      `/businesses/${businessId}/analytics/kpis${periodDays ? `?period_days=${periodDays}` : ""}`
    ),
  getRevenueTrend: (businessId: string, days = 90) =>
    apiGet<RevenueTrendPoint[]>(`/businesses/${businessId}/analytics/revenue-trend?days=${days}`),
  getForecast: (businessId: string, horizonDays = 14) =>
    apiPost<ForecastResult>(`/businesses/${businessId}/analytics/forecast?horizon_days=${horizonDays}`),

  createGoal: (businessId: string, text: string) =>
    apiPost<Goal>(`/businesses/${businessId}/goals`, { text }),
  listGoals: (businessId: string) => apiGet<Goal[]>(`/businesses/${businessId}/goals`),
};
