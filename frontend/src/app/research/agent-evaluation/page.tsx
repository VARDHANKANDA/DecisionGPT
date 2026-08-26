"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { researchApi, type AgentEvaluation } from "@/lib/research-api";
import { DataTable, EvalEmptyState, Metric, Panel, PageIntro, StatGrid, fmt, fmtInt } from "@/components/research-ui";

export default function AgentEvaluationPage() {
  const [data, setData] = useState<AgentEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    researchApi.agentEvaluation().then(setData).catch((e) => setError(String(e?.message ?? e)));
  }, []);

  const archRows = data?.architecture_comparison.rows ?? [];
  const chartData = archRows.map((r) => ({
    name: r.label?.replace("Prediction + ", "+ ") ?? r.architecture,
    "goal achievement": r.goal_achievement != null ? Number((r.goal_achievement * 100).toFixed(1)) : null,
    "risk-adjusted": r.risk_adjusted_score,
    "latency (s)": r.latency_seconds,
  }));

  return (
    <div>
      <PageIntro
        title="Multi-Agent Evaluation"
        subtitle="Compares the decision architectures for which a real experiment exists (Prediction only → Digital Twin → Single Agent → Full DecisionGPT), plus debate statistics aggregated from real recorded decisions. The term 'agent accuracy' is not used — there is no ground-truth decision benchmark."
      />

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {!data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : data.empty_state && archRows.length === 0 ? (
        <EvalEmptyState message={data.empty_state} />
      ) : (
        <div className="space-y-6">
          {archRows.length > 0 ? (
            <Panel
              title="Architecture comparison"
              right={
                <span className="text-xs text-muted">
                  experiment {data.architecture_comparison.experiment_id?.slice(0, 8)} · seed{" "}
                  {data.architecture_comparison.seed} · target {data.architecture_comparison.goal_target_percent}%
                </span>
              }
            >
              <div className="h-64 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={54} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Bar dataKey="goal achievement" fill="var(--accent)" radius={[3, 3, 0, 0]} />
                    <Bar dataKey="risk-adjusted" fill="var(--success)" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4">
                <DataTable
                  headers={["Architecture", "Selected strategy", "Goal achievement", "Risk-adjusted", "Expected benefit", "Latency (s)"]}
                  rows={archRows.map((r) => [
                    `${r.architecture}. ${r.label}`,
                    r.selected_strategy ?? "— none —",
                    r.goal_achievement != null ? `${(r.goal_achievement * 100).toFixed(0)}%` : "—",
                    r.risk_adjusted_score != null ? fmtInt(r.risk_adjusted_score) : "—",
                    r.expected_benefit != null ? `₹${fmtInt(r.expected_benefit)}` : "—",
                    r.latency_seconds != null ? fmt(r.latency_seconds, 3) : "—",
                  ])}
                />
              </div>
            </Panel>
          ) : (
            <EvalEmptyState message="No decision-architecture experiment yet. Run one from Experiments." />
          )}

          <Panel title="Agent debate analysis (real decisions)">
            {data.debate_analysis.decisions_with_debate === 0 ? (
              <p className="text-sm text-muted">{data.debate_analysis.message}</p>
            ) : (
              <>
                <StatGrid>
                  <Metric label="Decisions with debate" value={fmtInt(data.debate_analysis.decisions_with_debate)} />
                  <Metric label="Avg agents involved" value={fmt(data.debate_analysis.avg_agents_involved, 1)} />
                  <Metric
                    label="Conflicts raised"
                    value={fmtInt(data.debate_analysis.total_conflicts)}
                    hint={`avg ${fmt(data.debate_analysis.avg_conflicts_per_decision, 2)} / decision`}
                  />
                  <Metric
                    label="Post-review score changes"
                    value={fmtInt(data.debate_analysis.post_review_score_changes)}
                    hint={`${data.debate_analysis.decisions_with_full_agreement} full agreement`}
                  />
                </StatGrid>
                {data.debate_analysis.latest_decision ? (
                  <div className="mt-4 rounded-xl border border-border p-4 text-sm">
                    <p className="font-medium text-foreground">
                      Latest: decision {data.debate_analysis.latest_decision.decision_id.slice(0, 8)} ·{" "}
                      {data.debate_analysis.latest_decision.rounds} rounds · confidence{" "}
                      {data.debate_analysis.latest_decision.confidence != null
                        ? `${(data.debate_analysis.latest_decision.confidence * 100).toFixed(0)}%`
                        : "—"}
                    </p>
                    {data.debate_analysis.latest_decision.conflicts?.length ? (
                      <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted">
                        {data.debate_analysis.latest_decision.conflicts.map((c, i) => (
                          <li key={i}>
                            <span className="font-medium">{c.raised_by.replace(/_/g, " ")}:</span> {c.concern}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-xs text-muted">All agents concurred.</p>
                    )}
                    <p className="mt-2 text-xs text-muted">
                      {data.debate_analysis.latest_decision.resolution_rationale}
                    </p>
                  </div>
                ) : null}
              </>
            )}
          </Panel>

          {data.ablation.experiment_id ? (
            <Panel title="Single vs multi-agent (ablation)">
              <DataTable
                headers={["Config", "Selected strategy", "Goal achievement", "Risk-adjusted", "Confidence"]}
                rows={(data.ablation.configs as Record<string, unknown>[])
                  .filter((c) => ["A", "C", "D"].includes(String(c.config)))
                  .map((c) => [
                    `${c.config}. ${c.label}`,
                    (c.selected_strategy_name as string) ?? "— none —",
                    c.goal_achievement != null ? `${(Number(c.goal_achievement) * 100).toFixed(0)}%` : "—",
                    c.risk_adjusted_score != null ? fmtInt(Number(c.risk_adjusted_score)) : "—",
                    c.confidence != null ? `${(Number(c.confidence) * 100).toFixed(0)}%` : "—",
                  ])}
              />
            </Panel>
          ) : null}
        </div>
      )}
    </div>
  );
}
