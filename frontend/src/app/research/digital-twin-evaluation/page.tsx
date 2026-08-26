"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { researchApi, type DigitalTwinEvaluation } from "@/lib/research-api";
import { DataTable, EvalEmptyState, Metric, Panel, PageIntro, StatGrid, fmt, fmtInt } from "@/components/research-ui";

export default function DigitalTwinEvaluationPage() {
  const [data, setData] = useState<DigitalTwinEvaluation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function load() {
    researchApi.digitalTwinEvaluation().then(setData).catch((e) => setError(String(e?.message ?? e)));
  }
  useEffect(load, []);

  async function backfill() {
    setBusy(true);
    try {
      await researchApi.digitalTwinEvaluationBackfill();
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageIntro
        title="Digital Twin Evaluation"
        subtitle="Compares what the Digital Twin predicted for each chosen strategy against the actual outcome an SME later recorded. Every row is a real Decision → DigitalTwinSimulation → DecisionOutcome triple; errors are computed only where both the prediction and the recorded outcome support the metric. MAPE is omitted where the actual change is zero."
      />

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {!data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <StatGrid>
            <Metric label="Evaluated predictions" value={fmtInt(data.summary.evaluated_predictions)} />
            <Metric label="Outcomes recorded" value={fmtInt(data.summary.outcomes_recorded)} />
            <Metric label="Decisions awaiting outcome" value={fmtInt(data.summary.decisions_awaiting_outcome)} />
            <Metric
              label="Revenue-change MAE"
              value={data.summary.revenue_mae != null ? `₹${fmtInt(data.summary.revenue_mae)}` : "—"}
              hint={data.summary.revenue_mape != null ? `MAPE ${fmt(data.summary.revenue_mape, 1)}%` : undefined}
            />
          </StatGrid>

          {data.empty_state ? (
            <EvalEmptyState message={data.empty_state} />
          ) : (
            <>
              <Panel
                title="Error metrics (revenue change)"
                right={
                  <button
                    onClick={backfill}
                    disabled={busy}
                    className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted-surface disabled:opacity-50"
                  >
                    {busy ? "Backfilling…" : "Backfill missing evaluations"}
                  </button>
                }
              >
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <MetricBlock label="Revenue" agg={data.metrics.revenue} />
                  <MetricBlock label="Profit" agg={data.metrics.profit} />
                </div>
                <p className="mt-3 text-xs text-muted">Method: {data.method}</p>
              </Panel>

              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Panel title="Predicted vs actual revenue change (₹)">
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <ScatterChart>
                        <CartesianGrid stroke="var(--border)" />
                        <XAxis type="number" dataKey="predicted" name="Predicted" tick={{ fontSize: 10 }} />
                        <YAxis type="number" dataKey="actual" name="Actual" tick={{ fontSize: 10 }} />
                        <ZAxis range={[60, 60]} />
                        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
                        <Scatter data={data.charts.predicted_vs_actual} fill="var(--accent)" />
                      </ScatterChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="mt-1 text-center text-xs text-muted">Points on the diagonal = perfect prediction.</p>
                </Panel>

                <Panel title="Prediction error distribution">
                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.charts.error_distribution}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="range" tick={{ fontSize: 9 }} interval={0} angle={-20} textAnchor="end" height={54} />
                        <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Bar dataKey="count" fill="var(--accent)" radius={[3, 3, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              </div>

              {data.charts.error_over_time.length > 1 ? (
                <Panel title="Error over time">
                  <div className="h-56 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart
                        data={data.charts.error_over_time.map((p) => ({
                          date: p.recorded_at ? new Date(p.recorded_at).toLocaleDateString() : "",
                          error: p.error,
                        }))}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} />
                        <Tooltip />
                        <Line type="monotone" dataKey="error" stroke="var(--accent)" strokeWidth={2} dot />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>
              ) : null}

              <Panel title="Evaluation detail">
                <DataTable
                  headers={[
                    "Decision",
                    "Strategy",
                    "Predicted baseline",
                    "Predicted",
                    "Actual",
                    "Error",
                    "% error",
                    "Graph ver.",
                    "Date",
                  ]}
                  rows={data.rows.map((r) => [
                    r.decision_id.slice(0, 8),
                    r.strategy_name ?? "—",
                    r.predicted_baseline != null ? `₹${fmtInt(r.predicted_baseline)}` : "—",
                    r.predicted != null ? `₹${fmtInt(r.predicted)}` : "—",
                    r.actual != null ? `₹${fmtInt(r.actual)}` : "—",
                    r.error != null ? `₹${fmtInt(r.error)}` : "—",
                    r.abs_pct_error != null ? `${fmt(r.abs_pct_error, 1)}%` : "—",
                    r.causal_graph_version ?? "—",
                    r.recorded_at ? new Date(r.recorded_at).toLocaleDateString() : "—",
                  ])}
                />
              </Panel>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function MetricBlock({ label, agg }: { label: string; agg: { mae: number | null; rmse: number | null; sample_size: number; mape?: number | null } }) {
  return (
    <div className="rounded-xl border border-border p-4">
      <p className="text-sm font-medium text-foreground">{label}</p>
      {agg.sample_size === 0 ? (
        <p className="mt-1 text-xs text-muted">No matched outcomes for this metric yet.</p>
      ) : (
        <p className="mt-1 text-sm text-muted">
          MAE {fmtInt(agg.mae)} · RMSE {fmtInt(agg.rmse)}
          {agg.mape != null ? ` · MAPE ${fmt(agg.mape, 1)}%` : ""} · n={agg.sample_size}
        </p>
      )}
    </div>
  );
}
