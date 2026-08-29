"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { researchApi, type AgentEvaluation, type MultiAgentDiagnostic } from "@/lib/research-api";
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

          {data.multi_agent_diagnostic ? <MultiAgentDiagnosticPanel d={data.multi_agent_diagnostic} /> : null}

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

function MultiAgentDiagnosticPanel({ d }: { d: MultiAgentDiagnostic }) {
  const [fScenario, setFScenario] = useState("all");
  const [fMode, setFMode] = useState("all");
  const scenarios = useMemo(
    () => Array.from(new Set(d.scenario_drilldown.map((r) => r.scenario_id))).sort(),
    [d],
  );
  const modes = useMemo(
    () => Array.from(new Set(d.scenario_drilldown.map((r) => r.failure_mode))).sort(),
    [d],
  );
  const rows = d.scenario_drilldown.filter(
    (r) => (fScenario === "all" || r.scenario_id === fScenario) && (fMode === "all" || r.failure_mode === fMode),
  );
  const fig = d.failure_analysis_figure;
  const pct = (x: number) => `${(x * 100).toFixed(0)}%`;

  return (
    <Panel
      title="Multi-Agent degradation diagnostic (research-only)"
      right={
        <span className="text-xs text-muted">
          experiment {d.experiment_id.slice(0, 8)} · {d.total_scenario_seed_pairs} scenario-seed pairs
        </span>
      }
    >
      <p className="mb-3 text-xs text-muted">
        Digital Twin mean goal achievement {d.digital_twin_mean_goal_achievement.toFixed(3)} vs Full
        DecisionGPT {d.full_decisiongpt_mean_goal_achievement.toFixed(3)}. Every number is read from the
        stored `multi_agent_diagnostic` experiment.
      </p>

      <StatGrid>
        <Metric label="DT best → Final override rate" value={pct(d.digital_twin_to_final.override_rate)}
          hint={`${d.digital_twin_to_final.overridden} overridden / ${d.digital_twin_to_final.unchanged} unchanged`} />
        <Metric label="Override improved" value={fmtInt(d.override_outcomes.improved)}
          hint={pct(d.override_outcomes.override_improvement_rate)} />
        <Metric label="Override degraded" value={fmtInt(d.override_outcomes.degraded)}
          hint={pct(d.override_outcomes.override_degradation_rate)} />
        <Metric label="Override neutral" value={fmtInt(d.override_outcomes.neutral)}
          hint={pct(d.override_outcomes.override_neutral_rate)} />
      </StatGrid>

      {/* failure-analysis figure (text tree from actual counts) */}
      <div className="mt-4 rounded-xl border border-border bg-muted-surface p-3 text-xs">
        <p className="font-medium text-foreground">Failure-analysis figure (aggregate counts)</p>
        <pre className="mt-1 whitespace-pre text-muted">{
`Digital Twin best strategy  (n=${fig.digital_twin_best})
 ├─ unchanged → final strategy   ${fig.unchanged}
 └─ overridden                   ${fig.overridden}
      ├─ improved                ${fig.overridden_improved}
      ├─ degraded                ${fig.overridden_degraded}
      └─ neutral                 ${fig.overridden_neutral}`
        }</pre>
      </div>

      {/* failure modes */}
      <div className="mt-4">
        <DataTable
          headers={["Failure mode", "Count", "%", "Mean DT revenue", "Mean final goal ach."]}
          rows={Object.entries(d.failure_modes)
            .filter(([, v]) => v.count > 0 || v.note)
            .map(([k, v]) => [
              k, fmtInt(v.count), `${v.percent}%`,
              v.mean_dt_revenue != null ? fmtInt(v.mean_dt_revenue) : v.note ? "—" : "—",
              v.mean_final_goal_achievement != null ? v.mean_final_goal_achievement.toFixed(3) : "—",
            ])}
        />
      </div>

      <div className="mt-3 rounded-xl border border-border p-3 text-xs">
        <p className="font-medium text-foreground">Central hypothesis</p>
        <p className="mt-1 text-muted">{d.central_hypothesis.statement}</p>
        <p className="mt-2 text-muted">
          Agent layer changed the selection where the DT-best was in its own candidate set:{" "}
          {d.central_hypothesis.agent_layer_overrides_dt_best_in_its_own_set} (degraded{" "}
          {d.central_hypothesis.of_those_degraded} · improved {d.central_hypothesis.of_those_improved} · neutral{" "}
          {d.central_hypothesis.of_those_neutral}).
        </p>
        <p className="mt-2 font-medium text-foreground">{d.central_hypothesis.verdict}</p>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-3 text-xs">
        <div className="rounded-lg border border-border p-2">
          <p className="font-medium text-foreground">Risk Manager effect</p>
          <p className="text-muted">disagrees with DT-best {pct(d.risk_manager_effect.disagreement_rate_vs_dt_best)}
            {" "}({d.risk_manager_effect.disagreements}) · degraded {d.risk_manager_effect.of_those_degraded} · improved {d.risk_manager_effect.of_those_improved}</p>
        </div>
        <div className="rounded-lg border border-border p-2">
          <p className="font-medium text-foreground">Optimizer effect</p>
          <p className="text-muted">DT-best → final change rate {pct(d.optimizer_effect.dt_best_to_final_change_rate)};
            {" "}goal ach. unchanged {d.optimizer_effect.mean_goal_achievement_when_unchanged ?? "—"} vs changed {d.optimizer_effect.mean_goal_achievement_when_changed ?? "—"}</p>
        </div>
        <div className="rounded-lg border border-border p-2">
          <p className="font-medium text-foreground">Causal-evidence effect</p>
          <p className="text-muted">{d.causal_evidence_effect.note}</p>
        </div>
      </div>

      {/* scenario / seed drill-down */}
      <div className="mt-4">
        <div className="mb-2 flex flex-wrap gap-2 text-xs">
          <select value={fScenario} onChange={(e) => setFScenario(e.target.value)} className="rounded border border-border bg-surface px-2 py-1">
            <option value="all">All scenarios</option>
            {scenarios.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={fMode} onChange={(e) => setFMode(e.target.value)} className="rounded border border-border bg-surface px-2 py-1">
            <option value="all">All failure modes</option>
            {modes.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <span className="self-center text-muted">{rows.length} of {d.scenario_drilldown.length}</span>
        </div>
        <div className="max-h-80 overflow-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted-surface text-muted">
              <tr>
                <th className="px-2 py-1 text-left">Scenario/seed</th>
                <th className="px-2 py-1 text-left">Goal</th>
                <th className="px-2 py-1 text-left">DT best</th>
                <th className="px-2 py-1 text-left">Final</th>
                <th className="px-2 py-1 text-left">Failure mode</th>
                <th className="px-2 py-1 text-right">Δ goal ach.</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-border align-top" title={r.mechanism_evidence}>
                  <td className="px-2 py-1 text-foreground">{r.scenario_id}/{r.seed}</td>
                  <td className="px-2 py-1">{r.goal_objective}</td>
                  <td className="px-2 py-1">{r.digital_twin_best ?? "—"}</td>
                  <td className="px-2 py-1">{r.final_strategy ?? "—"}</td>
                  <td className="px-2 py-1">{r.failure_mode}</td>
                  <td className="px-2 py-1 text-right">{r.improvement.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}
