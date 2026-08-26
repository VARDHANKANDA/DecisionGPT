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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    cache: "no-store",
    headers: { ...authHeader() },
  });
  return handleResponse<T>(response);
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...authHeader(),
    },
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
    headers: { ...authHeader() },
  });
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

export interface SimulationOutput {
  expected_units_sold: number;
  baseline_units_sold: number;
  expected_revenue: number;
  baseline_revenue: number;
  expected_profit: number | null;
  baseline_profit: number | null;
  profit_note: string | null;
  customer_impact: number | null;
  inventory_constrained: boolean;
  risk_level: "LOW" | "MODERATE" | "HIGH";
  risk_score: number;
  revenue_lower_bound: number;
  revenue_upper_bound: number;
  model_name: string;
  model_version: string;
  assumptions: string[];
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
}

// ---- API surface ----

export const api = {
  createBusiness: (input: BusinessCreateInput) =>
    apiPost<Business>("/businesses", { country: "IN", currency: "INR", ...input }),
  createDemoBusiness: () => apiPost<Business>("/businesses/demo"),
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
  recordOutcome: (businessId: string, decisionId: string, actualOutcome: Record<string, number>) =>
    apiPost<DecisionOutcome>(`/businesses/${businessId}/decisions/${decisionId}/outcome`, {
      actual_outcome: actualOutcome,
    }),
  getOutcome: (businessId: string, decisionId: string) =>
    apiGet<DecisionOutcome>(`/businesses/${businessId}/decisions/${decisionId}/outcome`),

  listMemory: (businessId: string, memoryType?: string) =>
    apiGet<BusinessMemoryEntry[]>(
      `/businesses/${businessId}/memory${memoryType ? `?memory_type=${memoryType}` : ""}`
    ),

  chat: (businessId: string, message: string) =>
    apiPost<ChatResponse>(`/businesses/${businessId}/chat`, { message }),

  register: (input: { email: string; password: string; full_name?: string; role?: string }) =>
    apiPost<AuthToken>("/auth/register", input),
  login: (input: { email: string; password: string }) => apiPost<AuthToken>("/auth/login", input),
  me: () => apiGet<AuthUser>("/auth/me"),
};
