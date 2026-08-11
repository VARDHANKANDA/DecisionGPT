"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, ApiError, type ForecastResult, type KPISnapshot, type RevenueTrendPoint } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, EmptyState, PageHeader, PrimaryButton, SecondaryLink, Stat, formatINR } from "@/components/ui";

export default function DashboardPage() {
  const { business, loading: businessLoading } = useBusiness();
  const [kpis, setKpis] = useState<KPISnapshot | null>(null);
  const [trend, setTrend] = useState<RevenueTrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [forecast, setForecast] = useState<ForecastResult | null>(null);
  const [forecastError, setForecastError] = useState<string | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    Promise.all([api.getKpis(business.id), api.getRevenueTrend(business.id, 90)]).then(([k, t]) => {
      if (cancelled) return;
      setKpis(k);
      setTrend(t);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [business]);

  async function runForecast() {
    if (!business) return;
    setForecastLoading(true);
    setForecastError(null);
    try {
      const result = await api.getForecast(business.id, 14);
      setForecast(result);
    } catch (err) {
      setForecastError(
        err instanceof ApiError ? err.message : "Could not generate a forecast right now."
      );
    } finally {
      setForecastLoading(false);
    }
  }

  if (!businessLoading && !business) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="text-muted">Set up your business first.</p>
        <div className="mt-4">
          <SecondaryLink href="/onboarding">Go to onboarding</SecondaryLink>
        </div>
      </div>
    );
  }

  if (loading || !kpis) {
    return <div className="mx-auto max-w-6xl px-6 py-16 text-muted">Loading your dashboard…</div>;
  }

  const hasData = kpis.orders > 0;

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <PageHeader title={`${business?.name}`} subtitle="How your business is doing, based on your uploaded data." />

      {!hasData ? (
        <EmptyState
          title="No business data yet"
          description="Upload your sales data to unlock analytics, forecasting and strategy simulation."
          action={<SecondaryLink href="/data/upload">Upload data</SecondaryLink>}
        />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Revenue" value={formatINR(kpis.revenue)} hint={periodLabel(kpis)} />
            <Stat
              label="Profit"
              value={kpis.profit !== null ? formatINR(kpis.profit) : "Unavailable"}
              hint={kpis.profit === null ? "No product cost data on file" : undefined}
            />
            <Stat label="Orders" value={kpis.orders.toLocaleString("en-IN")} />
            <Stat label="Customers" value={kpis.customers.toLocaleString("en-IN")} />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat
              label="Avg. order value"
              value={kpis.average_order_value !== null ? formatINR(kpis.average_order_value) : "—"}
            />
            <Stat label="Marketing spend" value={formatINR(kpis.marketing_spend)} />
            <Stat
              label="Marketing ROI"
              value={kpis.marketing_roi !== null ? `${(kpis.marketing_roi * 100).toFixed(0)}%` : "Unavailable"}
            />
            <Stat
              label="Conversion rate"
              value={kpis.conversion_rate !== null ? `${(kpis.conversion_rate * 100).toFixed(1)}%` : "Unavailable"}
            />
          </div>

          {kpis.notes.length > 0 ? (
            <div className="mt-4 rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">
              {kpis.notes.join(" ")}
            </div>
          ) : null}

          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <h2 className="text-sm font-medium text-foreground">Revenue trend (last 90 days)</h2>
              <div className="mt-4 h-64">
                {trend.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={trend}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
                      <YAxis tick={{ fontSize: 11 }} width={60} />
                      <Tooltip formatter={(value) => formatINR(typeof value === "number" ? value : Number(value))} />
                      <Line type="monotone" dataKey="revenue" stroke="var(--accent)" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-sm text-muted">Not enough data for a trend chart yet.</p>
                )}
              </div>
            </Card>

            <Card>
              <h2 className="text-sm font-medium text-foreground">14-day sales forecast</h2>
              <p className="mt-1 text-xs text-muted">
                Predicted units sold per day, from the best-performing registered model.
              </p>

              {!forecast ? (
                <div className="mt-4">
                  <PrimaryButton onClick={runForecast} disabled={forecastLoading}>
                    {forecastLoading ? "Forecasting…" : "Generate forecast"}
                  </PrimaryButton>
                  {forecastError ? <p className="mt-3 text-sm text-warning">{forecastError}</p> : null}
                </div>
              ) : (
                <div className="mt-4">
                  <p className="text-xs text-muted">
                    Model: {forecast.model_name} · MAE {forecast.metrics.mae?.toFixed(1)}
                  </p>
                  <ul className="mt-3 max-h-48 space-y-1 overflow-y-auto text-sm">
                    {forecast.points.map((p) => (
                      <li key={p.forecast_date} className="flex justify-between border-b border-border py-1">
                        <span className="text-muted">{p.forecast_date}</span>
                        <span className="font-medium">
                          {p.predicted_value.toFixed(0)}{" "}
                          <span className="text-xs text-muted">
                            ({p.lower_bound.toFixed(0)}–{p.upper_bound.toFixed(0)})
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          </div>

          <div className="mt-8">
            <SecondaryLink href="/goals">Set a goal for DecisionGPT →</SecondaryLink>
          </div>
        </>
      )}
    </div>
  );
}

function periodLabel(kpis: KPISnapshot): string | undefined {
  if (!kpis.period_start || !kpis.period_end) return "All-time";
  return `${kpis.period_start} to ${kpis.period_end}`;
}
