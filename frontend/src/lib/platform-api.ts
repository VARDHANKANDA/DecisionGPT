import { apiGet, apiPost, apiSend } from "@/lib/api";

/**
 * Typed client for the business-OS endpoints (data platform, KPI monitoring, health, alerts, reports, causal /
 * counterfactual analysis, debate, explainability). Shapes mirror what the backend actually returns; optional
 * fields are the ones the backend omits when it has nothing honest to say.
 */

export type Anchor = "today" | "latest";

/** Data kinds the data platform can inspect, in display order (matches the server's table registry). */
export const DATA_TABLES: { key: string; label: string }[] = [
  { key: "sales", label: "Sales data" },
  { key: "customers", label: "Customer data" },
  { key: "products", label: "Product data" },
  { key: "inventory", label: "Stock data" },
  { key: "marketing_campaigns", label: "Marketing data" },
  { key: "finance", label: "Money & accounts data" },
];

// ---- data platform ------------------------------------------------------------------------------
export interface ColumnProfile {
  key: string;
  label: string;
  declared_type: string;
  inferred_type: string;
  missing: number;
  missing_pct: number;
  unique: number;
  date_min?: string;
  date_max?: string;
  unparseable?: number;
  min?: number;
  max?: number;
  mean?: number;
  median?: number;
  top_values?: { value: string; count: number }[];
}
export interface DataProfile {
  table: string;
  title: string;
  rows: number;
  columns: number;
  column_profiles: ColumnProfile[];
  duplicate_rows: number;
  invalid_or_inconsistent: { rule: string; title: string; severity: string; count: number; explanation: string; sample_ids: string[] }[];
  outlier_candidates: { column: string; label: string; candidates: number; lower_bound: number; upper_bound: number; note: string }[];
  limitations: string[];
  profiled_at: string;
}
export interface PreviewPage {
  type: string;
  title: string;
  columns: { key: string; label: string; kind: string; editable: boolean }[];
  rows: { id: string; values: Record<string, string | number | null> }[];
  total: number;
  offset: number;
  limit: number;
}
export interface CleaningProposal {
  id: string;
  table: string;
  kind: string;
  column: string | null;
  issue: string;
  action: string;
  affected_rows: number;
  affected_cells: number;
  preview: Record<string, unknown>[];
  risk: string;
  can_apply: boolean;
  applied: boolean;
}
export interface PrepRun {
  id: string;
  stage: string;
  table: string | null;
  operation: string | null;
  status: string;
  summary: Record<string, unknown>;
  reversible: boolean;
  error: string | null;
  created_at: string;
}
export interface ValidationResult {
  id: string;
  table: string;
  title: string;
  severity: string;
  status: "pass" | "warn" | "fail" | "error";
  affected: number;
  explanation: string;
  next_step: string;
  sample?: unknown[];
}
export interface ValidationReport {
  overall: "pass" | "warn" | "fail" | "not_run";
  pass: number;
  warn: number;
  fail: number;
  error: number;
  tables_checked: string[];
  tables_skipped_empty: string[];
  results: ValidationResult[];
  rule: string;
  validated_at: string;
  run_id?: string;
}
export interface TransformOption {
  id: string;
  kind: "standardise_style" | "map_values" | "recalculate_totals" | "aggregate_preview";
  table: string;
  column?: string;
  title: string;
  styles?: string[];
  needs?: string;
  [k: string]: unknown;
}
export interface TransformPreview {
  id?: string;
  affected_rows?: number;
  preview?: { id?: string; before: unknown; after: unknown }[];
  risk?: string;
  can_apply?: boolean;
  by?: string;
  rows?: { period: string; sales: number; units: number; records: number }[];
  note?: string;
}
export interface PipelineStage {
  key: string;
  name: string;
  state: "not_started" | "in_progress" | "needs_attention" | "ready" | "failed";
  detail: string;
  link?: string;
  optional?: boolean;
}
export interface Pipeline {
  stages: PipelineStage[];
  current_stage: string;
  ready_for_analysis: boolean;
  last_data_change: string | null;
  last_prepared: string | null;
  downstream_may_need_refresh: string[];
  limitations: string[];
}

// ---- KPIs / health / alerts / reports ------------------------------------------------------------
export interface Kpi {
  key: string;
  name: string;
  unit: "inr" | "count" | "percent" | "ratio" | string;
  definition: string;
  source: string;
  value: number | null;
  previous_value: number | null;
  change_pct: number | null;
  target: { value: number; direction: "higher" | "lower"; period_days: number } | null;
  target_period_value: number | null;
  status: "met" | "not_met" | "no_target" | "no_data";
  status_rule: string;
  data_quality: { status: string; note: string };
}
export interface KpiList {
  period: { start: string; end: string; days: number; anchor: Anchor };
  previous_period: { start: string; end: string };
  latest_sale_date: string | null;
  stale_days: number | null;
  stale_rule: string;
  calculated_at: string;
  kpis: Kpi[];
}
export interface KpiTrend {
  key: string;
  name: string;
  unit: string;
  period: { start: string; end: string };
  points: { date: string; value: number }[];
  n_points: number;
  target: Kpi["target"];
  note: string;
}
export interface HealthComponent {
  key: string;
  name: string;
  weight: number;
  rule: string;
  available: boolean;
  score: number | null;
  detail: string;
  evidence: Record<string, unknown>;
  unavailable_reason: string | null;
  effective_weight: number | null;
  contribution: number | null;
}
export interface Health {
  version: string;
  period: { days: number; end: string; anchor: Anchor };
  calculated_at: string;
  composite_score: number | null;
  level: string | null;
  level_thresholds: { min: number; label: string }[];
  composite_unavailable_reason: string | null;
  available_weight_share: number;
  components: HealthComponent[];
  limitations: string[];
}
export interface HealthSnapshotRow {
  id: string;
  version: string;
  score: number | null;
  period_days: number;
  available_weight: number;
  created_at: string;
}
export interface AlertRow {
  id: string;
  rule_key: string;
  rule_name: string;
  severity: "low" | "medium" | "high";
  status: "open" | "read" | "resolved" | "cleared";
  title: string;
  message: string;
  metric_value: number | null;
  threshold: number | null;
  period_start: string | null;
  period_end: string | null;
  evidence: Record<string, unknown>;
  suggested_action: string | null;
  severity_rule: string;
  first_seen: string;
  last_seen: string;
  resolved_at: string | null;
}
export interface AlertCheck {
  evaluated_at: string;
  anchor: Anchor;
  created: number;
  refreshed: number;
  cleared: number;
  suppressed_by_cooldown: number;
  monitoring_note: string;
  cooldown_hours: number;
}
export interface AlertRule {
  rule_key: string;
  name: string;
  description: string;
  severity_rule: string;
  unit: string;
  enabled: boolean;
  threshold: number | null;
  default_threshold: number | null;
  is_default: boolean;
}
export type ReportSection =
  | { kind: "notice"; tone: "info" | "warning" | "danger"; text: string }
  | { kind: "facts"; title?: string; items: { label: string; value: string; hint?: string }[] }
  | { kind: "table"; title?: string; columns: string[]; rows: (string | number | null)[][]; note?: string }
  | { kind: "series"; title?: string; points: { date: string; value: number }[]; unit?: string; note?: string }
  | { kind: "text"; title?: string; paragraphs: string[] }
  | { kind: "list"; title?: string; items: string[] };
export interface ReportPayload {
  report_type: string;
  title: string;
  period: { start: string; end: string; days: number; anchor: Anchor };
  created_on: string;
  scope: { business: string; business_id: string; dataset: Record<string, unknown>; demo_data: boolean };
  summary: string;
  sections: ReportSection[];
  assumptions: string[];
  limitations: string[];
}
export interface SavedReportMeta {
  id: string;
  report_type: string;
  title: string;
  period_start: string | null;
  period_end: string | null;
  created_at: string;
  summary: string;
}
export interface SavedReport extends SavedReportMeta {
  payload: ReportPayload;
}

// ---- causal / counterfactual / debate ------------------------------------------------------------
export type CausalClass = "not_enough_data" | "not_configured" | "assumptions_not_satisfied" | "exploratory_association" | "causal_estimate" | "failed";
export interface CausalResult {
  id: string;
  classification: CausalClass;
  headline: string;
  method_version: string;
  generated_on: string;
  question: string;
  causal_question?: string;
  reason?: string;
  error?: string;
  coverage?: { first_day: string | null; last_day: string | null; days_used: number; days_in_sales_range?: number };
  suitability?: { check: string; passed: boolean; detail: string }[];
  method?: { name?: string; model?: string; why_chosen?: string; why_not_causal?: string; window_days_each_side?: number };
  estimate?: { coefficient?: number; effect_per_product_day?: number; se?: number; ci95: [number, number]; p_value: number; unit?: string; n_days?: number; n_observations?: number };
  group_means?: Record<string, number>;
  products?: { changed: string[]; comparison: string[] };
  intervention_date?: string;
  interpretation?: string;
  assumptions?: { assumption: string; status: string; p_value?: number }[];
  robustness?: { check: string; coef: number; p: number }[];
  placebo?: { description: string; coef: number; p_value: number };
  feedback?: { description: string; coef: number; p_value: number };
  pre_trend_test?: { description: string; p_value: number; threshold: number; rejected: boolean };
  warnings?: string[];
  limitations?: string[];
}
export interface RunMeta {
  id: string;
  kind: string;
  status: string;
  mode: string | null;
  question: string | null;
  created_at: string;
  classification: string | null;
  headline: string | null;
}
export interface CounterfactualResult {
  id?: string;
  mode: "deterministic_scenario" | "model_prediction" | "causal_counterfactual";
  label: string;
  headline?: string;
  classification: string;
  reason?: string;
  what_it_does_not_establish?: string;
  generated_on?: string;
  baseline?: { period_days: number; end: string; sales: number; orders: number };
  scenario?: { lever: string; change_pct: number; elasticity: number; sales: number; difference: number };
  assumptions?: (string | { assumption: string; status: string })[];
  uncertainty?: string;
  source_analysis?: string;
  observed_after?: number;
  counterfactual_after?: number;
  difference?: number;
  ci95?: [number, number];
  unit?: string;
  products?: { changed: string[]; comparison: string[] };
  intervention_date?: string;
  expected_revenue?: number;
  baseline_revenue?: number;
  revenue_lower_bound?: number;
  revenue_upper_bound?: number;
  model?: string;
  risk_level?: string;
  [k: string]: unknown;
}
export interface Claim {
  id: string;
  agent: string;
  text: string;
  evidence: string[];
  type: string;
}
export interface DebateOption {
  id: string;
  title: string;
  evidence_strength: string;
  supporting_facts?: string[];
  supporting_claims?: string[];
  open_challenges: string[];
  trade_offs: string[];
  simulation: { expected_revenue: number; baseline_revenue: number; difference: number; lower: number; upper: number; risk_level: string; model: string } | null;
  claim_id?: string;
}
export interface DebateBrief {
  question: string;
  topic: string;
  mode: string;
  headline: string;
  recommended_option: DebateOption | null;
  key_facts: string[];
  disagreements: { id: string; from: string; text: string }[];
  settled_by_calculation: { id: string; text: string; detail?: { change_by_window_days?: Record<string, number | null> } | null }[];
  missing_information: string[];
  unresolved_uncertainty: string[];
  next_steps: string[];
  automatic_actions_taken: boolean;
}
export interface DebateResult {
  id?: string;
  status: "completed" | "partial" | "failed" | "ai_model_unavailable";
  mode: "rule_based" | "ai_model";
  label?: string;
  message?: string;
  error?: string;
  version?: string;
  generated_on?: string;
  stage_order?: string[];
  no_automatic_action?: boolean;
  audit?: { stage: string; agent?: string; ok: boolean; error: string | null; latency_s: number; attempts: number | null }[];
  stages?: {
    question: { text: string; topic: string; topic_note: string };
    shared_evidence: { facts: { id: string; text: string; value: unknown; source: string }[]; missing: { id: string; text: string }[]; period: KpiList["period"] };
    specialist_analyses: Record<string, { agent: string; name: string; role: string; claims: Claim[]; missing_information: string[]; options?: DebateOption[]; rejected_claims?: { reason: string }[]; ran?: boolean }>;
    challenges: { id: string; from: string; to_claim: string; text: string; basis: string[]; resolution: string; detail?: Record<string, unknown> }[];
    evidence_review: { claims: { claim_id: string; agent: string; status: string; evidence_found: string[]; challenges: string[] }[]; missing_information: { id: string; text: string }[]; assumptions: string[] };
    synthesis: { options: DebateOption[]; ranked_option_ids: string[]; insufficient_evidence: boolean; insufficient_reason: string | null; unresolved_disagreements: string[]; note: string };
    decision_brief: DebateBrief;
  };
}
export interface DebateStatus {
  rule_based_available: boolean;
  ai_model_available: boolean;
  ai_model_notice: string | null;
  stages: string[];
  agents: { key: string; name: string }[];
}
export interface KpiExplanation {
  kind: "kpi";
  method: string;
  question: string;
  definition: string;
  source: string;
  period: KpiList["period"];
  rows_used: { sales_rows: number; marketing_rows: number };
  filters: string[];
  result: { value: number | null; unit: string; previous_period_value: number | null; change: number | null };
  assumptions: string[];
  limitations: string[];
  technical_detail: { implementation: string; status_rule: string };
}
export interface AnswerExplanation {
  kind: "chat_answer";
  question: string | null;
  answer: string | null;
  path: string;
  method: string;
  sources: string[];
  limitations: string[];
  structured_request?: unknown;
  resolved_period?: unknown;
  assumptions?: string[];
  tool?: string;
  checks?: { check: string; passed: boolean }[];
  intent?: string;
}

const b = (id: string) => `/businesses/${id}`;
const q = (params: Record<string, string | number | boolean | undefined>) => {
  const e = Object.entries(params).filter(([, v]) => v !== undefined);
  return e.length ? `?${e.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&")}` : "";
};

export const platform = {
  // data platform
  profile: (id: string, table: string, record = false) => apiGet<DataProfile>(`${b(id)}/data/profile/${table}${q({ record })}`),
  preview: (id: string, table: string, offset = 0, limit = 25, search?: string) =>
    apiGet<PreviewPage>(`${b(id)}/data/preview/${table}${q({ offset, limit, search: search || undefined })}`),
  cleaning: (id: string, table: string) => apiGet<{ table: string; proposals: CleaningProposal[] }>(`${b(id)}/data/cleaning/${table}`),
  applyCleaning: (id: string, proposalId: string, confirm: boolean) =>
    apiPost<PrepRun & { affected_rows: number }>(`${b(id)}/data/cleaning/apply`, { proposal_id: proposalId, confirm }),
  revert: (id: string, runId: string) => apiPost<PrepRun & { restored_rows: number }>(`${b(id)}/data/runs/${runId}/revert`),
  validate: (id: string, tables?: string[]) => apiPost<ValidationReport>(`${b(id)}/data/validation/run`, { tables: tables ?? null }),
  validationLatest: (id: string) => apiGet<{ run: PrepRun | null }>(`${b(id)}/data/validation/latest`),
  transformOptions: (id: string) => apiGet<{ options: TransformOption[]; not_available: string[] }>(`${b(id)}/data/transform/options`),
  transformPreview: (id: string, body: Record<string, unknown>) => apiPost<TransformPreview>(`${b(id)}/data/transform/preview`, body),
  transformApply: (id: string, body: Record<string, unknown>, confirm: boolean) =>
    apiPost<PrepRun & { affected_rows: number }>(`${b(id)}/data/transform/apply`, { ...body, confirm }),
  pipeline: (id: string) => apiGet<Pipeline>(`${b(id)}/data/pipeline`),
  prepHistory: (id: string, stage?: string) => apiGet<{ runs: PrepRun[] }>(`${b(id)}/data/prep-history${q({ stage })}`),

  // KPIs, health, alerts
  kpis: (id: string, periodDays = 30, anchor: Anchor = "today") => apiGet<KpiList>(`${b(id)}/kpis${q({ period_days: periodDays, anchor })}`),
  kpiTrend: (id: string, key: string, days = 90, anchor: Anchor = "today") => apiGet<KpiTrend>(`${b(id)}/kpis/${key}/trend${q({ period_days: days, anchor })}`),
  setTarget: (id: string, key: string, value: number, direction: "higher" | "lower", periodDays: number) =>
    apiSend<{ key: string }>("PUT", `${b(id)}/kpis/${key}/target`, { value, direction, period_days: periodDays }),
  clearTarget: (id: string, key: string) => apiSend<void>("DELETE", `${b(id)}/kpis/${key}/target`),
  health: (id: string, periodDays = 30, anchor: Anchor = "today", save = false) =>
    apiGet<Health>(`${b(id)}/health-score${q({ period_days: periodDays, anchor, save })}`),
  healthHistory: (id: string) => apiGet<{ snapshots: HealthSnapshotRow[] }>(`${b(id)}/health-score/history`),
  alerts: (id: string, status: "active" | "open" | "read" | "resolved" | "cleared" = "active") => apiGet<{ alerts: AlertRow[] }>(`${b(id)}/alerts${q({ status })}`),
  checkAlerts: (id: string, anchor: Anchor = "today") => apiPost<AlertCheck>(`${b(id)}/alerts/evaluate${q({ anchor })}`),
  setAlertStatus: (id: string, alertId: string, status: "read" | "resolved") => apiPost<AlertRow>(`${b(id)}/alerts/${alertId}/status`, { status }),
  alertRules: (id: string) => apiGet<{ rules: AlertRule[]; cooldown_hours: number; monitoring_note: string }>(`${b(id)}/alerts/rules`),
  setAlertRule: (id: string, key: string, enabled: boolean, threshold: number | null) =>
    apiSend<AlertRule>("PUT", `${b(id)}/alerts/rules/${key}`, { enabled, threshold }),

  // reports
  reportTypes: (id: string) => apiGet<{ types: { key: string; title: string }[] }>(`${b(id)}/reports/types`),
  createReport: (id: string, reportType: string, periodDays: number, anchor: Anchor) =>
    apiPost<SavedReport>(`${b(id)}/reports`, { report_type: reportType, period_days: periodDays, anchor }),
  reports: (id: string) => apiGet<{ reports: SavedReportMeta[] }>(`${b(id)}/reports`),
  report: (id: string, reportId: string) => apiGet<SavedReport>(`${b(id)}/reports/${reportId}`),
  deleteReport: (id: string, reportId: string) => apiSend<void>("DELETE", `${b(id)}/reports/${reportId}`),

  // causal / counterfactual
  analyzeCausal: (id: string, body: Record<string, unknown>) => apiPost<CausalResult>(`${b(id)}/causal/analyze`, body),
  causalRuns: (id: string) => apiGet<{ runs: RunMeta[] }>(`${b(id)}/causal/runs`),
  causalRun: (id: string, runId: string) => apiGet<{ id: string; result: CausalResult; params: Record<string, unknown> }>(`${b(id)}/causal/runs/${runId}`),
  runCounterfactual: (id: string, body: Record<string, unknown>) => apiPost<CounterfactualResult>(`${b(id)}/counterfactual/run`, body),
  counterfactualRuns: (id: string) => apiGet<{ runs: RunMeta[] }>(`${b(id)}/counterfactual/runs`),

  // debate
  debateStatus: (id: string) => apiGet<DebateStatus>(`${b(id)}/debate/status`),
  runDebate: (id: string, question: string, mode: "rule_based" | "ai_model", anchor: Anchor) =>
    apiPost<DebateResult>(`${b(id)}/debate/run`, { question, mode, anchor }),
  debateRuns: (id: string) => apiGet<{ runs: RunMeta[] }>(`${b(id)}/debate/runs`),
  debateRun: (id: string, runId: string) => apiGet<{ id: string; result: DebateResult }>(`${b(id)}/debate/runs/${runId}`),

  // explainability
  explainKpi: (id: string, key: string, periodDays = 30, anchor: Anchor = "today") =>
    apiGet<KpiExplanation>(`${b(id)}/explain/kpi/${key}${q({ period_days: periodDays, anchor })}`),
  explainAnswer: (id: string, memoryId: string) => apiGet<AnswerExplanation>(`${b(id)}/explain/answer/${memoryId}`),
};

/** Format a KPI value in the unit the backend reports. */
export function formatKpi(value: number | null, unit: string): string {
  if (value === null || value === undefined) return "Not available";
  if (unit === "inr") return `₹${Math.round(value).toLocaleString("en-IN")}`;
  if (unit === "percent") return `${value.toFixed(1)}%`; // the server already reports percentage points
  if (unit === "ratio") return `${value.toFixed(2)}×`;
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
