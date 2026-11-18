import type { ChurnPrediction, ForecastPoint, Goal, PeriodComparison, UnitsHistoryPoint } from "@/lib/api";

/**
 * Turns real model/analytics output into plain sentences. These functions only describe numbers
 * they are given — they never add or estimate anything of their own.
 */

const num = (n: number, digits = 0) => n.toLocaleString("en-IN", { maximumFractionDigits: digits });

export const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

/** "up 14%", "down 3%", "about the same" — 2% either way counts as steady. */
export function describeChange(pct: number | null): string {
  if (pct === null || !Number.isFinite(pct)) return "can't be compared (nothing to compare with)";
  const p = Math.abs(pct * 100);
  if (p < 2) return "about the same";
  return `${pct > 0 ? "up" : "down"} ${num(p, p < 10 ? 1 : 0)}%`;
}

export function revenueHeadline(c: PeriodComparison | null, days = 30): string {
  if (!c) return "";
  if (c.previous_revenue <= 0) {
    return `You sold ${inr(c.current_revenue)} in the last ${days} days. There isn't an earlier period to compare it with yet.`;
  }
  const change = describeChange(c.change_pct);
  return change === "about the same"
    ? `Your sales are about the same as the ${days} days before: ${inr(c.current_revenue)} compared with ${inr(c.previous_revenue)}.`
    : `Your sales are ${change} compared with the ${days} days before: ${inr(c.previous_revenue)} → ${inr(c.current_revenue)}.`;
}

export interface ForecastStory {
  headline: string;
  direction: "rising" | "falling" | "steady";
  avgPerDay: number;
  totalUnits: number;
  recentAvg: number | null;
  /** How many recent real days the comparison covers, and their units in total. */
  recentDays: number;
  recentTotal: number | null;
  /** True when the forecast differs from recent real sales by more than a quarter — worth a caution. */
  bigShift: boolean;
  /** True when it is more than double (or under half) of recent real sales — too far off to lean on. */
  hugeShift: boolean;
  /** Plain sentences for the "Why?" section. */
  why: string[];
}

/** Compare the forecast with what really sold over the same number of recent days. */
export function forecastStory(points: ForecastPoint[], history: UnitsHistoryPoint[]): ForecastStory | null {
  if (points.length === 0) return null;
  const n = points.length;
  const total = points.reduce((s, p) => s + p.predicted_value, 0);
  const avg = total / n;

  const half = Math.max(1, Math.floor(n / 2));
  const first = points.slice(0, half).reduce((s, p) => s + p.predicted_value, 0) / half;
  const last = points.slice(n - half).reduce((s, p) => s + p.predicted_value, 0) / half;
  const within = first > 0 ? (last - first) / first : 0;
  const direction = within > 0.05 ? "rising" : within < -0.05 ? "falling" : "steady";

  const recent = history.slice(-n);
  const recentAvg =
    recent.length >= Math.min(n, 7) ? recent.reduce((s, h) => s + h.units_sold, 0) / recent.length : null;

  let vs = "";
  if (recentAvg !== null && recentAvg > 0) {
    const diff = (avg - recentAvg) / recentAvg;
    vs =
      Math.abs(diff) < 0.03
        ? `That is about the same as the last ${recent.length} days (about ${num(recentAvg, 1)} a day).`
        : `That is ${num(Math.abs(diff) * 100)}% ${diff > 0 ? "higher" : "lower"} than the last ${recent.length} days (about ${num(recentAvg, 1)} a day).`;
  }

  const trendWords = {
    rising: "gradually rising",
    falling: "gradually falling",
    steady: "broadly steady",
  }[direction];

  return {
    headline: `Over the next ${n} days, DecisionGPT estimates you will sell about ${num(total)} units — roughly ${num(avg, 1)} a day, ${trendWords}.`,
    direction,
    avgPerDay: avg,
    totalUnits: total,
    recentAvg,
    recentDays: recent.length,
    recentTotal: recentAvg !== null ? recent.reduce((s, h) => s + h.units_sold, 0) : null,
    bigShift: recentAvg !== null && recentAvg > 0 && Math.abs(avg - recentAvg) / recentAvg > 0.25,
    hugeShift: recentAvg !== null && recentAvg > 0 && (avg > recentAvg * 2 || avg < recentAvg / 2),
    why: [
      "The forecast continues from your own sales history, using patterns such as recent sales levels and the day of the week.",
      ...(vs ? [vs] : []),
      "It assumes things carry on as they are — it does not know about upcoming festivals, offers or supply problems unless they are already in your data.",
    ],
  };
}

export type RiskBand = "higher" | "moderate" | "lower";

/** Display bands only. The model gives a score between 0 and 1 (not a probability); these cut-offs just group the list. */
export const RISK_CUTOFFS = { higher: 0.7, moderate: 0.5 } as const;

export function riskBand(p: number): RiskBand {
  return p >= RISK_CUTOFFS.higher ? "higher" : p >= RISK_CUTOFFS.moderate ? "moderate" : "lower";
}

export const RISK_LABEL: Record<RiskBand, string> = {
  higher: "Higher risk",
  moderate: "Some risk",
  lower: "Lower risk",
};

export interface ChurnStory {
  headline: string;
  total: number;
  atRisk: ChurnPrediction[];
  counts: Record<RiskBand, number>;
}

export function churnStory(predictions: ChurnPrediction[]): ChurnStory {
  const counts: Record<RiskBand, number> = { higher: 0, moderate: 0, lower: 0 };
  for (const p of predictions) counts[riskBand(p.churn_probability)] += 1;
  const atRisk = predictions
    .filter((p) => p.churn_probability >= RISK_CUTOFFS.moderate)
    .sort((a, b) => b.churn_probability - a.churn_probability);
  const total = predictions.length;
  const headline =
    atRisk.length === 0
      ? `None of your ${num(total)} customers currently scores high on the stop-buying pattern.`
      : `${num(atRisk.length)} of your ${num(total)} customers (${num((atRisk.length / total) * 100)}%) score high on the stop-buying pattern — ${num(counts.higher)} of them clearly so.`;
  return { headline, total, atRisk, counts };
}

const OBJECTIVE_LABELS: Record<string, string> = {
  increase_revenue: "Increase sales",
  increase_profit: "Increase profit",
  increase_sales: "Sell more units",
  reduce_churn: "Keep more customers",
  improve_marketing_roi: "Get more from marketing",
  reduce_inventory_risk: "Avoid running out of or overstocking items",
};

/** "Increase profit by 15% in 3 months" — a stored goal said the way a person would. */
export function goalSentence(g: Goal): string {
  const label = OBJECTIVE_LABELS[g.objective] ?? g.objective.replace(/_/g, " ");
  const unit = g.target_unit === "percent" ? "%" : ` ${g.target_unit}`;
  const months = g.time_horizon ? ` in ${g.time_horizon} month${g.time_horizon === 1 ? "" : "s"}` : "";
  return `${label} by ${g.target_value}${unit}${months}`;
}
