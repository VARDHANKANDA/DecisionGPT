const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export const TOKEN_STORAGE_KEY = "decisiongpt.token";

function authHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = window.localStorage.getItem(TOKEN_STORAGE_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

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

function errorFrom(status: number, bodyText: string): ApiError {
  let code = "UNKNOWN_ERROR";
  let message = `Request failed with status ${status}`;
  let details: Record<string, unknown> = {};
  try {
    const body = JSON.parse(bodyText);
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
      details = body.error.details ?? {};
    }
  } catch {
    // response body wasn't JSON — keep the generic message
  }
  return new ApiError(status, code, message, details);
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) throw errorFrom(response.status, await response.text().catch(() => ""));
  return response.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: { ...authHeader() },
  });
  return handleResponse<T>(response);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...authHeader(),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  return handleResponse<T>(response);
}

export interface UploadOptions {
  /** Called with 0..1 while the file is being sent (not while the server is checking it). */
  onProgress?: (fraction: number) => void;
}

async function apiUpload<T>(path: string, file: File, options: UploadOptions = {}): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  if (!options.onProgress || typeof XMLHttpRequest === "undefined") {
    const response = await fetch(`${API_BASE_URL}${path}`, { method: "POST", body: formData, cache: "no-store", headers: { ...authHeader() } });
    return handleResponse<T>(response);
  }
  // fetch cannot report upload progress, so a progress bar needs XMLHttpRequest
  const onProgress = options.onProgress;
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`);
    for (const [k, v] of Object.entries(authHeader())) xhr.setRequestHeader(k, v);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) onProgress(Math.min(1, e.loaded / e.total));
    };
    xhr.onerror = () => reject(new TypeError("Network request failed"));
    xhr.ontimeout = () => reject(new TypeError("Network request timed out"));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as T);
        } catch {
          reject(new ApiError(xhr.status, "BAD_RESPONSE", "The server's answer could not be read.", {}));
        }
      } else reject(errorFrom(xhr.status, xhr.responseText));
    };
    xhr.send(formData);
  });
}

export async function apiSend<T>(method: "PATCH" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...authHeader(),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (response.status === 204) return undefined as T;
  return handleResponse<T>(response);
}

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  user: AuthUser;
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

/** One thing the cleaning step did to the file, in plain words (nothing is changed without being listed). */
export interface UploadAction {
  code: string;
  message: string;
  count: number | null;
}

export interface UploadDataset {
  type: string;
  source: string;
  rows_read: number;
  rows_after_cleaning: number;
  rows_imported: number;
  rows_skipped: number;
  skipped_reasons: Record<string, number>;
  skipped_examples: { row?: number; reason: string }[];
  columns_in_file: string[];
  columns_used: { column: string; as: string }[];
  /** Kept in the stored original, just not used by DecisionGPT — NOT deleted. */
  columns_not_used: string[];
  columns_removed_empty: string[];
  renamed_columns: { from: string; to: string; reason: string }[];
  duplicate_rows: number;
  actions: UploadAction[];
  warnings: string[];
  encoding?: string | null;
  delimiter?: string | null;
}

export interface PendingMapping {
  sheet: string;
  type: string;
  suggested_mapping: Record<string, string>;
  unmapped_required_fields: string[];
  available_columns: string[];
  /** Dates that could be read two ways (03/04/2026): the person must say which. */
  date_questions?: { field: string; column: string; examples: string[] }[];
}

export type DateOrder = "day_first" | "month_first";

export interface IngestionJob {
  id: string;
  business_id: string;
  filename: string;
  status: "processing" | "needs_mapping_confirmation" | "completed" | "failed";
  detected_types_json: string[];
  mapping_json: Record<string, PendingMapping> | Record<string, unknown>;
  summary_json: {
    rows_ingested?: Record<string, number>;
    quality?: Record<string, unknown>;
    datasets?: UploadDataset[];
    sheets_not_used?: { sheet: string; reason: string }[];
    file?: { name?: string; size_bytes?: number | null; sha256?: string | null };
    original_kept?: boolean;
    completed_at?: string;
    duplicate_of?: { job_id: string; imported_on: string };
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
  /** Plain-language limits of this forecast (stale data, out-of-range scale, synthetic training data, uncalibrated band). */
  warnings?: string[];
  interval_method?: string;
  /** True when the band was measured against this business's own past forecast errors. */
  interval_reliable?: boolean;
  data_as_of?: string | null;
  trained_on?: string | null;
  /** business_specific_validated | business_specific_baseline | limited_estimate */
  forecast_basis?: string;
  target_unit?: string;
  data_profile?: { days?: number; sale_days?: number; first_date?: string; last_date?: string };
  validation?: { status?: string; selected?: string; method_description?: string; holdout_origins?: number };
  registered_model_note?: string | null;
  /** Identifies exactly what was forecast; send it back when saving so only a forecast that was shown can be saved. */
  fingerprint?: string | null;
  dataset_sha256?: string | null;
  generated_at?: string | null;
  horizon_requested?: number | null;
  horizon_returned?: number | null;
  forecast_start?: string | null;
  forecast_end?: string | null;
  data_cutoff?: string | null;
}

export interface ForecastSnapshot {
  id: string;
  already_saved: boolean;
  verified_against_shown: boolean | null;
  metric: string;
  unit: string;
  window_start: string;
  window_end: string;
  data_cutoff: string | null;
  horizon_days: number;
  created_at: string | null;
}

export interface UnitsHistoryPoint {
  date: string;
  units_sold: number;
}

export interface ChurnPrediction {
  customer_id: string;
  external_customer_id: string | null;
  churn_probability: number;
}

export interface ChurnResult {
  model_name: string;
  model_version: string;
  metrics: Record<string, number>;
  predictions: ChurnPrediction[];
  score_meaning?: string;
  label_provenance?: string;
  trained_on?: string | null;
  warnings?: string[];
}

export interface CapabilityStatus {
  feature: string;
  enabled: boolean;
  reason: string;
  requires: string[];
}

export interface Capabilities {
  business_id: string;
  data_summary: Record<string, number | boolean>;
  capabilities: CapabilityStatus[];
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

export interface PeriodComparison {
  current_revenue: number;
  previous_revenue: number;
  change_absolute: number;
  change_pct: number | null;
  current_orders: number;
  previous_orders: number;
}

export interface ProductPerformance {
  product_id: string;
  name: string;
  units_sold: number;
  revenue: number;
}

export interface ChannelPerformance {
  channel: string;
  spend: number;
  attributed_revenue: number | null;
  roi: number | null;
  campaigns: number;
}

export interface CustomerSummary {
  total_customers: number;
  customers_with_purchase_history: number;
  avg_monetary_value: number | null;
  avg_purchase_frequency: number | null;
  new_customers_last_30_days: number;
}

export interface InventoryStatus {
  product_id: string;
  product_name: string;
  current_stock: number;
  reorder_level: number | null;
  low_stock: boolean;
}

export type ActionType = "price_change" | "marketing_change" | "inventory_change";

export interface SimulationAction {
  type: ActionType;
  value: number;
}

export interface PriceResponse {
  status: "not_identified" | "association_only";
  identified: boolean;
  reliable: boolean;
  /** True: the price effect is withheld (the effect fields of the output are null). */
  withheld: boolean;
  /** Why it is withheld: the history lacks price variation, or no model checked against this business can supply one. */
  reason?: "history" | "model" | null;
  days: number;
  distinct_prices: number;
  price_cv: number;
  needed: string[];
  message: string;
}

export interface ForecastReadiness {
  ready_for_forecast: boolean;
  ready_for_training: boolean;
  blockers: string[];
  training_blockers?: string[];
  issues: Array<{ kind: string; rows: number; severity: "error" | "warning" | "info"; detail: string }>;
  example_data?: string | null;
}

export interface SimulationOutput {
  expected_units_sold: number | null;
  baseline_units_sold: number;
  expected_revenue: number | null;
  baseline_revenue: number;
  expected_profit: number | null;
  baseline_profit: number | null;
  profit_note: string | null;
  customer_impact: number | null;
  inventory_constrained: boolean;
  risk_level: "LOW" | "MODERATE" | "HIGH";
  risk_score: number;
  revenue_lower_bound: number | null;
  revenue_upper_bound: number | null;
  model_name: string;
  model_version: string;
  assumptions: string[];
  price_response?: PriceResponse | null;
}

export interface SimulationResult {
  id: string;
  business_id: string;
  goal_id: string | null;
  input_state: Record<string, unknown>;
  actions: SimulationAction[];
  output: SimulationOutput;
}

export interface CausalEdge {
  source_node: string;
  target_node: string;
  relationship: string;
  strength: number | null;
  confidence: number | null;
  evidence_type: "assumed" | "observational" | "data_supported" | "causally_validated";
  time_lag: number | null;
  note: string;
}

export interface CausalGraph {
  id: string;
  business_id: string;
  version: string;
  method: string;
  evidence_summary: string;
  created_at: string | null;
  edges: CausalEdge[];
}

export interface AlternativeStrategy {
  strategy_id: string;
  strategy_name: string;
  actions: SimulationAction[];
  strategy_score: number;
  risk_level: string;
  expected_revenue: number;
}

export interface Decision {
  id: string;
  business_id: string;
  goal_id: string;
  selected_strategy_id: string;
  selected_strategy_name: string;
  selected_strategy_score: number;
  expected_outcome: Record<string, unknown> & {
    expected_revenue: number;
    baseline_revenue: number;
    expected_units_sold: number;
    baseline_units_sold: number;
    expected_profit: number | null;
    baseline_profit: number | null;
    assumptions: string[];
  };
  risk_level: string;
  confidence: number;
  reasoning: string;
  causal_graph_version: string | null;
  agent_reviews: Record<string, string>;
  alternatives: AlternativeStrategy[];
  skipped_strategies: string[];
  memory_insights: string[];
  causal_context: CausalContextInfo;
  debate: DebateInfo;
  strategy_generation: StrategyGenerationInfo;
  trace: Record<string, unknown>;
}

export interface CausalContextInfo {
  built: boolean;
  graph_version: string | null;
  method: string | null;
  strongest_pathway_evidence: string;
  summary: string;
  caveats: string[];
  pathways: { nodes: string[]; weakest_evidence: string; links: CausalEdge[] }[];
}

export interface DebateInfo {
  rounds: number;
  multi_agent: boolean;
  round1: Record<string, { score: number; key_points: string[]; risks: string[] }>;
  round2_reviews: {
    agent: string;
    concurs: boolean;
    challenges: string[];
    adjusted_score: number | null;
    rationale: string;
  }[];
  resolution: {
    final_score: number;
    confidence: number;
    resolution_rationale: string;
    conflicts: { raised_by: string; concern: string }[];
    confidence_basis: Record<string, number | string>;
  };
}

export interface StrategyGenerationInfo {
  objective: string;
  candidate_count: number;
  excluded: string[];
  constraints_applied: string[];
  notes: string[];
  goal_projection: {
    primary_kpi: string;
    projected_on: string;
    baseline: number;
    projected: number;
    delta: number;
    relative_change: number;
    improves_goal: boolean;
  };
}

export interface DecisionTrace {
  decision_id: string;
  business_state_version: string | null;
  candidate_strategy_ids: string[];
  simulation_ids: string[];
  agent_run_ids: string[];
  agent_runs: { id: string; agent_name: string; input: Record<string, unknown>; output: Record<string, unknown> }[];
  model_versions: Record<string, string>;
  causal_graph_version: string | null;
  reproducible: { ok: boolean; reasons: string[] };
  prompt_version: string | null;
}

export interface DecisionSummary {
  id: string;
  business_id: string;
  goal_id: string;
  selected_strategy_id: string | null;
  expected_outcome_json: Record<string, unknown>;
  risk_level: string;
  confidence: number | null;
  reasoning: string | null;
  causal_graph_version: string | null;
  created_at: string;
}

export interface FeatureContribution {
  feature: string;
  label: string;
  contribution: number;
  direction: string;
}

export interface DecisionExplanation {
  decision_id: string;
  explanation: {
    model_name: string;
    model_version: string;
    shap_available: boolean;
    unavailable_reason: string | null;
    local_factors: FeatureContribution[];
    global_importance: FeatureContribution[];
  };
  reasoning: string;
  agent_reviews: Record<string, string>;
  counterfactual: Record<string, number | null>;
  uncertainty: Record<string, unknown>;
  assumptions: string[];
}

export interface DecisionOutcome {
  id: string;
  decision_id: string;
  actual_outcome_json: Record<string, unknown>;
  goal_achieved: boolean | null;
  goal_achievement_score: number | null;
  recorded_at: string;
}

export interface TrackingResponse {
  recorded: boolean;
  seq: number;
  response: string;
  action_status: string;
  action_taken?: Record<string, unknown> | null;
  modified_action?: Record<string, unknown> | null;
  action_start?: string | null;
  action_end?: string | null;
  known_changes?: string[];
  evaluation_design?: string;
  note?: string | null;
  recorded_by?: string | null;
  created_at?: string | null;
}

export interface TrackingDecision {
  current: TrackingResponse | { recorded: false; response: string; action_status: string; seq: number };
  history?: TrackingResponse[];
  expectations: Array<{
    expectation: { id: string; metric: string; unit: string; comparable_to_actuals: boolean; comparability_reason: string | null };
    comparison: { status: string; reason: string };
  }>;
}

export interface ResponseBody {
  response?: "pending" | "accepted" | "rejected" | "modified" | "deferred";
  action_status?: "unknown" | "not_executed" | "partially_executed" | "executed";
  action_taken?: Record<string, unknown>;
  modified_action?: Record<string, unknown>;
  action_start?: string;
  note?: string;
}

export interface TrackingComparison {
  expectation_id: string;
  metric: string;
  unit: string;
  source_kind: string;
  horizon_days: number;
  window: [string, string];
  status: string;
  reason: string;
  expected: number | null;
  observed?: number;
  signed_error?: number;
  abs_error?: number;
  abs_pct_error?: number | null;
  coverage_fraction?: number;
  data_cutoff: string | null;
  data_cutoff_provenance?: string | null;
  model: string | null;
}

export interface TrackingReport {
  decisions: { recorded: number; executed_confirmed: number; partially_executed: number; latest_response: Record<string, number> };
  expectations?: { recorded: number; comparable_to_actuals: number; not_comparable: number };
  observations?: { by_status: Record<string, number>; comparable: number; not_comparable: number; mean_coverage_fraction: number | null };
  awaiting_actuals?: Array<{
    expectation_id: string;
    source_kind: string;
    metric: string;
    unit: string;
    window: [string, string];
    window_finished: boolean;
    state: string;
    comparable_to_actuals: boolean;
  }>;
  comparisons: { by_status: Record<string, number>; excluded_reasons?: Record<string, number>; details?: TrackingComparison[] };
  forecast_accuracy: { statement: string; sample_size: number; date_range?: [string, string] | null };
  business_impact: { status: string; statement: string };
  legacy_free_form_outcomes: { recorded: number; status: string };
  limitations: string[];
}

export interface BusinessMemoryEntry {
  id: string;
  business_id: string;
  memory_type: string;
  content: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ChatResponse {
  answer: string;
  intent: string;
  sources: string[];
  sufficient_evidence: boolean;
  /** known = counted from the user's records, estimate = model projection, suggestion = advice, none = no answer */
  answer_type: "known" | "estimate" | "suggestion" | "none" | "clarification" | "evaluation";
  details: Record<string, unknown>;
  /** llm_analytics = the AI assistant interpreted the question and the data layer calculated it; legacy_router = the standard assistant answered. */
  path?: "llm_analytics" | "legacy_router" | "evaluation_service";
  /** Plain-language note, e.g. the AI assistant was unavailable and the standard assistant answered instead. */
  notice?: string | null;
}

// ---- "My Data" ----

export type DataType = "sales" | "customers" | "products" | "inventory" | "marketing_campaigns" | "finance";

export interface DataLibraryEntry {
  type: DataType;
  title: string;
  description: string;
  rows: number;
  columns: number;
  last_updated: string | null;
  source_files: { filename: string; uploaded_at: string; rows: number | null }[];
}

export interface DataColumn {
  key: string;
  label: string;
  kind: "text" | "number" | "integer" | "date";
  editable: boolean;
}

export type CellValue = string | number | null;

export interface DataRow {
  id: string;
  values: Record<string, CellValue>;
}

export interface DataTablePage {
  type: DataType;
  title: string;
  description: string;
  columns: DataColumn[];
  rows: DataRow[];
  total: number;
  offset: number;
  limit: number;
}

// ---- API surface ----

export const api = {
  createBusiness: (input: BusinessCreateInput) =>
    apiPost<Business>("/businesses", { country: "IN", currency: "INR", ...input }),
  createDemoBusiness: () => apiPost<Business>("/businesses/demo"),
  getBusiness: (businessId: string) => apiGet<Business>(`/businesses/${businessId}`),

  uploadData: (businessId: string, file: File, dataType?: string, options: UploadOptions & { allowDuplicateFile?: boolean } = {}) => {
    const params = new URLSearchParams();
    if (dataType) params.set("data_type", dataType);
    if (options.allowDuplicateFile) params.set("allow_duplicate_file", "true");
    const query = params.toString() ? `?${params.toString()}` : "";
    return apiUpload<IngestionJob>(`/businesses/${businessId}/data/upload${query}`, file, { onProgress: options.onProgress });
  },
  getIngestionJob: (businessId: string, jobId: string) =>
    apiGet<IngestionJob>(`/businesses/${businessId}/data/jobs/${jobId}`),
  getDataSummary: (businessId: string) => apiGet<DataSummary>(`/businesses/${businessId}/data/summary`),

  myBusinesses: () => apiGet<Business[]>("/businesses/mine"),
  updateBusiness: (businessId: string, input: Partial<Pick<Business, "name" | "description">>) =>
    apiSend<Business>("PATCH", `/businesses/${businessId}`, input),

  getForecastReadiness: (businessId: string) => apiGet<ForecastReadiness>(`/businesses/${businessId}/data/forecast-readiness`),
  getDataLibrary: (businessId: string) => apiGet<DataLibraryEntry[]>(`/businesses/${businessId}/data/library`),
  getUploads: (businessId: string) => apiGet<IngestionJob[]>(`/businesses/${businessId}/data/uploads`),
  getTable: (businessId: string, type: DataType, offset = 0, limit = 25) =>
    apiGet<DataTablePage>(`/businesses/${businessId}/data/tables/${type}?offset=${offset}&limit=${limit}`),
  addRows: (businessId: string, type: DataType, rows: Record<string, CellValue>[]) =>
    apiPost<{ added: number }>(`/businesses/${businessId}/data/tables/${type}/rows`, { rows }),
  updateRow: (businessId: string, type: DataType, rowId: string, changes: Record<string, CellValue>) =>
    apiSend<DataRow>("PATCH", `/businesses/${businessId}/data/tables/${type}/rows/${rowId}`, { changes }),
  deleteRow: (businessId: string, type: DataType, rowId: string) =>
    apiSend<void>("DELETE", `/businesses/${businessId}/data/tables/${type}/rows/${rowId}`),
  clearTable: (businessId: string, type: DataType) =>
    apiSend<{ deleted: number }>("DELETE", `/businesses/${businessId}/data/tables/${type}`),
  confirmMapping: (
    businessId: string,
    jobId: string,
    mappings: Record<string, Record<string, string>>,
    dateOrders: Record<string, Record<string, DateOrder>> = {},
  ) => apiPost<IngestionJob>(`/businesses/${businessId}/data/mapping?job_id=${jobId}`, { mappings, date_orders: dateOrders }),

  getKpis: (businessId: string, periodDays?: number) =>
    apiGet<KPISnapshot>(
      `/businesses/${businessId}/analytics/kpis${periodDays ? `?period_days=${periodDays}` : ""}`
    ),
  getRevenueTrend: (businessId: string, days = 90) =>
    apiGet<RevenueTrendPoint[]>(`/businesses/${businessId}/analytics/revenue-trend?days=${days}`),
  getForecast: (businessId: string, horizonDays = 14) =>
    apiPost<ForecastResult>(`/businesses/${businessId}/analytics/forecast?horizon_days=${horizonDays}`),

  getUnitsHistory: (businessId: string, days = 60) =>
    apiGet<UnitsHistoryPoint[]>(`/businesses/${businessId}/analytics/units-history?days=${days}`),
  getChurn: (businessId: string) => apiPost<ChurnResult>(`/businesses/${businessId}/analytics/churn`),
  getCapabilities: (businessId: string) => apiGet<Capabilities>(`/businesses/${businessId}/data/capabilities`),

  createGoal: (businessId: string, text: string) =>
    apiPost<Goal>(`/businesses/${businessId}/goals`, { text }),
  listGoals: (businessId: string) => apiGet<Goal[]>(`/businesses/${businessId}/goals`),
  getGoal: (businessId: string, goalId: string) => apiGet<Goal>(`/businesses/${businessId}/goals/${goalId}`),

  getPeriodComparison: (businessId: string, days = 30) =>
    apiGet<PeriodComparison>(`/businesses/${businessId}/analytics/period-comparison?days=${days}`),
  getTopProducts: (businessId: string, limit = 10) =>
    apiGet<ProductPerformance[]>(`/businesses/${businessId}/analytics/products?limit=${limit}`),
  getMarketingChannels: (businessId: string) =>
    apiGet<ChannelPerformance[]>(`/businesses/${businessId}/analytics/marketing-channels`),
  getCustomerSummary: (businessId: string) =>
    apiGet<CustomerSummary>(`/businesses/${businessId}/analytics/customers`),
  getInventoryStatus: (businessId: string) =>
    apiGet<InventoryStatus[]>(`/businesses/${businessId}/analytics/inventory`),

  simulate: (businessId: string, actions: SimulationAction[], goalId?: string, horizonDays = 14) =>
    apiPost<SimulationResult>(`/businesses/${businessId}/digital-twin/simulate`, {
      actions,
      goal_id: goalId ?? null,
      horizon_days: horizonDays,
    }),
  getSimulation: (businessId: string, simulationId: string) =>
    apiGet<SimulationResult>(`/businesses/${businessId}/digital-twin/simulations/${simulationId}`),

  buildCausalGraph: (businessId: string) =>
    apiPost<CausalGraph>(`/businesses/${businessId}/causal-graph/build`),
  getCausalGraph: (businessId: string) => apiGet<CausalGraph>(`/businesses/${businessId}/causal-graph`),

  analyzeGoal: (businessId: string, goalId: string) =>
    apiPost<Decision>(`/businesses/${businessId}/decisions/analyze`, { goal_id: goalId }),
  listDecisions: (businessId: string) => apiGet<DecisionSummary[]>(`/businesses/${businessId}/decisions`),
  getDecision: (businessId: string, decisionId: string) =>
    apiGet<DecisionSummary>(`/businesses/${businessId}/decisions/${decisionId}`),
  explainDecision: (businessId: string, decisionId: string) =>
    apiGet<DecisionExplanation>(`/businesses/${businessId}/decisions/${decisionId}/explanation`),
  decisionTrace: (businessId: string, decisionId: string) =>
    apiGet<DecisionTrace>(`/businesses/${businessId}/decisions/${decisionId}/trace`),
  recordOutcome: (businessId: string, decisionId: string, actualOutcome: Record<string, number | string>) =>
    apiPost<DecisionOutcome>(`/businesses/${businessId}/decisions/${decisionId}/outcome`, {
      actual_outcome: actualOutcome,
    }),
  getOutcome: (businessId: string, decisionId: string) =>
    apiGet<DecisionOutcome>(`/businesses/${businessId}/decisions/${decisionId}/outcome`),
  saveForecastSnapshot: (businessId: string, body: { horizon_days: number; fingerprint?: string | null; question?: string }) =>
    apiPost<ForecastSnapshot>(`/businesses/${businessId}/tracking/forecasts`, body),
  listDecisionTracking: (businessId: string) =>
    apiGet<{ decisions: Array<{ decision_id: string; current: TrackingResponse | { recorded: false; response: string; action_status: string; seq: number } }> }>(
      `/businesses/${businessId}/tracking/decisions`
    ),
  recordDecisionResponse: (businessId: string, decisionId: string, body: ResponseBody) =>
    apiPost<TrackingResponse>(`/businesses/${businessId}/tracking/decisions/${decisionId}/response`, body),
  trackingReport: (businessId: string) => apiGet<TrackingReport>(`/businesses/${businessId}/tracking/report`),
  trackingDecision: (businessId: string, decisionId: string) =>
    apiGet<TrackingDecision>(`/businesses/${businessId}/tracking/decisions/${decisionId}`),

  listMemory: (businessId: string, memoryType?: string) =>
    apiGet<BusinessMemoryEntry[]>(
      `/businesses/${businessId}/memory${memoryType ? `?memory_type=${memoryType}` : ""}`
    ),

  chat: (businessId: string, message: string) =>
    apiPost<ChatResponse>(`/businesses/${businessId}/chat`, { message }),
  consultAgent: (businessId: string, agentId: string, task: string) =>
    apiPost<AgentConsultationResult>(`/businesses/${businessId}/agents/${agentId}/consult`, { task }),

  register: (input: { email: string; password: string; full_name?: string; role?: string }) =>
    apiPost<AuthToken>("/auth/register", input),
  login: (input: { email: string; password: string }) => apiPost<AuthToken>("/auth/login", input),
  me: () => apiGet<AuthUser>("/auth/me"),
  updateProfile: (input: { full_name: string }) =>
    apiSend<AuthUser>("PATCH", "/auth/profile", input),
  /** Ends this session on the server (the token is refused from now on). Always resolves; the caller still clears local state. */
  logout: () => apiPost<void>("/auth/logout"),
  logoutAll: () => apiPost<void>("/auth/logout-all"),
  changePassword: (input: { current_password: string; new_password: string }) => apiPost<AuthToken>("/auth/change-password", input),

  // Administration endpoints (ROLE_ADMIN only)
  adminListUsers: () => apiGet<AdminUser[]>("/admin/users"),
  adminUpdateUserStatus: (userId: string, isActive: boolean) =>
    apiSend<AdminUser>("PATCH", `/admin/users/${userId}/status`, { is_active: isActive }),
  adminGetMonitoring: () => apiGet<SystemMonitoring>("/admin/monitoring"),
  adminGetSettings: () => apiGet<SystemSettings>("/admin/settings"),
};

export interface AdminUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  created_at: string;
  token_version: number;
}

export interface SystemMonitoring {
  status: string;
  timestamp: string;
  system_info: {
    python_version: string;
    platform: string;
    database_type: string;
    server_mode: string;
  };
  counts: {
    total_users: number;
    active_users: number;
    businesses: number;
    products: number;
    customers: number;
    sales_transactions: number;
    inventory_items: number;
    business_memories: number;
    registered_models: number;
    active_models: number;
  };
  users_by_role: Record<string, number>;
  configuration: {
    auth_enabled: boolean;
    research_console_enabled: boolean;
    rate_limiting_enabled: boolean;
    analytics_explain_enabled: boolean;
    cors_origins: string[];
    app_environment: string;
  };
}

export interface SystemSettings {
  environment: string;
  auth_enabled: boolean;
  research_console_enabled: boolean;
  rate_limiting_enabled: boolean;
  analytics_explain_enabled: boolean;
  cors_origins: string[];
  jwt_algorithm: string;
  access_token_expire_minutes: number;
  role_hierarchy: Record<string, string[]>;
}

export interface AgentConsultationResult {
  agent_id: string;
  agent_name: string;
  role: string;
  purpose: string;
  icon: string;
  task: string;
  executive_summary: string;
  key_findings: string[];
  supporting_evidence: Array<{
    claim: string;
    source: string;
    confidence: number;
    evidence_type: string;
  }>;
  business_implications: string[];
  recommended_actions: string[];
  assumptions_and_limitations: string[];
}


