"use client";

import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  researchApi,
  type AgentEvaluation,
  type MultiAgentDiagnostic,
  type RiskManagerCalibration,
  type RiskManagerDiagnostic,
  type RiskManagerGeneralization,
} from "@/lib/research-api";
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

          {data.multi_agent_diagnostic ? (
            <MultiAgentDiagnosticPanel d={data.multi_agent_diagnostic} prev={data.multi_agent_diagnostic_previous} />
          ) : null}

          {data.risk_manager_diagnostic ? (
            <RiskManagerDiagnosticPanel d={data.risk_manager_diagnostic} />
          ) : null}

          {data.risk_manager_calibration ? (
            <RiskManagerCalibrationPanel d={data.risk_manager_calibration} />
          ) : null}

          {data.risk_manager_generalization ? (
            <RiskManagerGeneralizationPanel d={data.risk_manager_generalization} />
          ) : null}

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

function MultiAgentDiagnosticPanel({ d, prev }: { d: MultiAgentDiagnostic; prev: MultiAgentDiagnostic | null }) {
  const [fScenario, setFScenario] = useState("all");
  const [fMode, setFMode] = useState("all");
  const pct = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(0)}%`);
  const isPost = (d.experiment_name ?? "").startsWith("POST_CORRECTION");
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
  const cov = d.candidate_coverage;

  return (
    <Panel
      title={`Multi-Agent degradation diagnostic${isPost ? " — POST-correction" : ""} (research-only)`}
      right={
        <span className="text-xs text-muted">
          {d.experiment_name ?? "experiment"} {d.experiment_id.slice(0, 8)} · {d.total_scenario_seed_pairs} scenario-seed pairs
        </span>
      }
    >
      <p className="mb-3 text-xs text-muted">
        Digital Twin mean goal achievement {d.digital_twin_mean_goal_achievement.toFixed(3)} vs Full
        DecisionGPT {d.full_decisiongpt_mean_goal_achievement.toFixed(3)}. Every number is read from the
        stored `multi_agent_diagnostic` experiment.
      </p>

      {/* pre vs post correction */}
      {prev && (
        <div className="mb-4 overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted-surface text-muted">
              <tr>
                <th className="px-2 py-1 text-left">Metric</th>
                <th className="px-2 py-1 text-right">{(prev.experiment_name ?? "previous").replace("multi_agent_diagnostic", "").trim() || "PRE"}</th>
                <th className="px-2 py-1 text-right">{(d.experiment_name ?? "current").replace("multi_agent_diagnostic", "").trim() || "CURRENT"}</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Candidate coverage rate", pct(prev.candidate_coverage?.candidate_coverage_rate), pct(cov?.candidate_coverage_rate)],
                ["Missing supported-strategy rate", pct(prev.candidate_coverage?.missing_supported_strategy_rate), pct(cov?.missing_supported_strategy_rate)],
                ["DT best → Final override rate", pct(prev.digital_twin_to_final.override_rate), pct(d.digital_twin_to_final.override_rate)],
                ["Override improved", `${prev.override_outcomes.improved}`, `${d.override_outcomes.improved}`],
                ["Override degraded", `${prev.override_outcomes.degraded}`, `${d.override_outcomes.degraded}`],
                ["Full mean goal achievement", prev.full_decisiongpt_mean_goal_achievement.toFixed(3), d.full_decisiongpt_mean_goal_achievement.toFixed(3)],
                ["Digital Twin mean goal achievement", prev.digital_twin_mean_goal_achievement.toFixed(3), d.digital_twin_mean_goal_achievement.toFixed(3)],
              ].map((r, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="px-2 py-1 text-foreground">{r[0]}</td>
                  <td className="px-2 py-1 text-right">{r[1]}</td>
                  <td className="px-2 py-1 text-right">{r[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* candidate-coverage check */}
      {cov && (
        <div className="mb-4 rounded-lg border border-border bg-muted-surface p-3 text-xs text-muted">
          <span className="font-medium text-foreground">Candidate coverage:</span>{" "}
          {cov.dt_best_present_in_full}/{cov.pairs_checked} pairs have the Digital-Twin-best strategy in
          Full DecisionGPT&apos;s generated set ({pct(cov.candidate_coverage_rate)}). Missing supported:{" "}
          {pct(cov.missing_supported_strategy_rate)}. Mean candidates: DT {cov.mean_dt_candidate_count} ·
          Full {cov.mean_full_candidate_count}. Invariant (DT-best present when supported):{" "}
          <span className={cov.invariant_dt_best_present_when_supported ? "text-success" : "text-danger"}>
            {cov.invariant_dt_best_present_when_supported ? "holds" : "does NOT hold"}
          </span>
          {cov.missing_pairs.length > 0 && (
            <> — missing: {cov.missing_pairs.map((p) => `${p.scenario_id}/${p.seed}`).join(", ")}</>
          )}
        </div>
      )}

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

function RiskManagerDiagnosticPanel({ d }: { d: RiskManagerDiagnostic }) {
  const [fScenario, setFScenario] = useState("all");
  const pct = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(0)}%`);
  const f3 = (x: number | null | undefined) => (x == null ? "—" : x.toFixed(3));
  const s = (v: { mean: number; ci95: [number, number] | null } | null | undefined) =>
    v == null ? "—" : `${v.mean.toFixed(3)}${v.ci95 ? ` [${v.ci95[0].toFixed(3)}, ${v.ci95[1].toFixed(3)}]` : ""}`;

  const base = d.baseline;
  const rd = d.rm_decisive;
  const mm = d.risk_score_mismatch;
  const cmp = d.d0_vs_d1;
  const paired = d.paired_d1_minus_d0;
  const interp = d.interpretation;

  const scenarios = useMemo(
    () => Array.from(new Set(d.scenario_drilldown.map((r) => r.scenario_id))).sort(),
    [d],
  );
  const rows = d.scenario_drilldown.filter((r) => fScenario === "all" || r.scenario_id === fScenario);

  return (
    <Panel
      title="Risk Manager diagnostic — risk-penalty sensitivity (research-only)"
      right={
        <span className="text-xs text-muted">
          {d.experiment_name ?? "experiment"} {d.experiment_id.slice(0, 8)} · {d.total_scenario_seed_pairs} scenario-seed pairs
        </span>
      }
    >
      <p className="mb-3 text-xs text-muted">
        <span className="font-medium text-foreground">D0</span> = Full DecisionGPT (production).{" "}
        <span className="font-medium text-foreground">D1</span> = Risk-Penalty Sensitivity Variant — the
        Risk Manager still runs and still feeds confidence; only its penalty weight in the ranking score
        is set to zero. D1 is a sensitivity analysis, <span className="font-medium text-foreground">not</span>{" "}
        the architecture. Every number is read from the stored `risk_manager_diagnostic` experiment.
      </p>

      <StatGrid>
        <Metric label="D0 Full DecisionGPT mean" value={f3(base?.full_decisiongpt_mean_goal_achievement)}
          hint="goal achievement" />
        <Metric label="D1 Risk-Penalty Sensitivity mean" value={f3(base?.d1_risk_penalty_sensitivity_mean_goal_achievement)}
          hint="goal achievement" />
        <Metric label="Digital Twin mean" value={f3(base?.digital_twin_mean_goal_achievement)}
          hint="architecture B rule" />
        <Metric label="RM disagreement rate" value={pct(d.risk_manager_disagreement?.disagreement_rate)}
          hint={`${d.risk_manager_disagreement?.disagreements_vs_dt_best ?? 0} vs DT-best`} />
      </StatGrid>

      <div className="mt-4 grid gap-3 md:grid-cols-2 text-xs">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium text-foreground">RM decisive</p>
          <p className="mt-1 text-muted">{rd?.definition}</p>
          <p className="mt-1 text-foreground">
            {rd?.count} / {d.total_scenario_seed_pairs} pairs ({rd?.percentage}%) — improved {rd?.improved} ·
            degraded {rd?.degraded} · neutral {rd?.neutral}
          </p>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium text-foreground">Risk-score mismatch</p>
          <p className="mt-1 text-muted">{mm?.definition}</p>
          <p className="mt-1 text-foreground">
            {mm?.count} / {mm?.strategy_rows_inspected} strategy rows ({mm?.percentage}%).{" "}
            RM distinguishes low vs high-risk price strategies:{" "}
            <span className="font-medium">{mm?.rm_distinguishes_low_vs_high_risk_price_strategies?.verdict ?? "—"}</span>
          </p>
        </div>
      </div>

      {/* DT risk vs RM score, per lever family */}
      {mm?.calibration_table?.length ? (
        <div className="mt-4">
          <p className="mb-1 text-xs font-medium text-foreground">DT simulated risk vs Risk Manager score</p>
          <DataTable
            headers={["Strategy", "Obs", "Mean DT risk", "Mean RM score", "RM=0 rate", "DT-risk LOW rate"]}
            rows={mm.calibration_table.map((r) => [
              r.strategy, fmtInt(r.observations),
              r.mean_digital_twin_risk != null ? r.mean_digital_twin_risk.toFixed(3) : "—",
              r.mean_risk_manager_score != null ? r.mean_risk_manager_score.toFixed(3) : "—",
              r.rm_score_zero_rate != null ? pct(r.rm_score_zero_rate) : "—",
              r.dt_risk_low_rate != null ? pct(r.dt_risk_low_rate) : "—",
            ])}
          />
        </div>
      ) : null}

      {/* D0 vs D1 comparison table */}
      {cmp ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted-surface text-muted">
              <tr>
                <th className="px-2 py-1 text-left">Metric</th>
                <th className="px-2 py-1 text-right">D0 Full</th>
                <th className="px-2 py-1 text-right">D1 No Risk Penalty</th>
              </tr>
            </thead>
            <tbody>
              {[
                ["Goal achievement (mean [95% CI])", s(cmp.goal_achievement.D0), s(cmp.goal_achievement.D1)],
                ["Risk-adjusted score (mean)", s(cmp.risk_adjusted_score.D0), s(cmp.risk_adjusted_score.D1)],
                ["Confidence (mean)", s(cmp.confidence.D0), s(cmp.confidence.D1)],
                ["DT-best agreement", pct(cmp.dt_best_agreement_rate.D0), pct(cmp.dt_best_agreement_rate.D1)],
                ["Override rate vs DT-best", pct(cmp.override_rate_vs_dt_best.D0), pct(cmp.override_rate_vs_dt_best.D1)],
              ].map((r, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="px-2 py-1 text-foreground">{r[0]}</td>
                  <td className="px-2 py-1 text-right">{r[1]}</td>
                  <td className="px-2 py-1 text-right">{r[2]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {paired ? (
        <div className="mt-3 rounded-xl border border-border p-3 text-xs">
          <p className="font-medium text-foreground">Paired difference (D1 − D0), goal achievement</p>
          <p className="mt-1 text-muted">
            mean {paired.mean_difference.toFixed(4)}
            {paired.mean_difference_ci95 ? ` (95% CI [${paired.mean_difference_ci95[0]}, ${paired.mean_difference_ci95[1]}])` : ""} ·
            median {paired.median_difference.toFixed(4)} · D1 wins {paired.d1_wins} · ties {paired.ties} · D0 wins {paired.d0_wins}
          </p>
          <p className="mt-1 text-muted">
            {paired.test ?? "Wilcoxon signed-rank"}: N={paired.n_pairs}
            {paired.p_value != null ? ` · p=${paired.p_value}` : ""}
            {paired.effect_size_r != null ? ` · r=${paired.effect_size_r}` : ""}
          </p>
          <p className="mt-1 text-foreground">{paired.interpretation}</p>
        </div>
      ) : null}

      {d.formula_verification ? (
        <p className="mt-2 text-xs text-muted">
          Formula check ({d.formula_verification.checked}): max deviation{" "}
          {d.formula_verification.max_deviation_observed} over {d.formula_verification.rows_checked} rows —{" "}
          <span className={d.formula_verification.holds_for_all_rows ? "text-success" : "text-danger"}>
            {d.formula_verification.holds_for_all_rows ? "holds for all rows" : "DOES NOT hold"}
          </span>
          .
        </p>
      ) : null}

      {interp ? (
        <div className="mt-3 rounded-xl border border-border bg-muted-surface p-3 text-xs">
          <p className="font-medium text-foreground">Interpretation — outcome {interp.outcome}</p>
          <p className="mt-1 text-muted">{interp.text}</p>
          <p className="mt-2 text-foreground">
            Removing only the RM penalty improves Full DecisionGPT:{" "}
            <span className="font-medium">{interp.removing_rm_penalty_improves_full}</span> · RM explains the
            Full-vs-Digital-Twin gap: <span className="font-medium">{interp.rm_penalty_explains_the_gap}</span>
          </p>
        </div>
      ) : null}

      {/* scenario / seed drill-down */}
      <div className="mt-4">
        <div className="mb-2 flex flex-wrap gap-2 text-xs">
          <select value={fScenario} onChange={(e) => setFScenario(e.target.value)} className="rounded border border-border bg-surface px-2 py-1">
            <option value="all">All scenarios</option>
            {scenarios.map((sc) => <option key={sc} value={sc}>{sc}</option>)}
          </select>
          <span className="self-center text-muted">{rows.length} of {d.scenario_drilldown.length}</span>
        </div>
        <div className="max-h-80 overflow-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted-surface text-muted">
              <tr>
                <th className="px-2 py-1 text-left">Scenario/seed</th>
                <th className="px-2 py-1 text-left">D0 pick</th>
                <th className="px-2 py-1 text-left">D1 pick</th>
                <th className="px-2 py-1 text-right">D0 goal ach.</th>
                <th className="px-2 py-1 text-right">D1 goal ach.</th>
                <th className="px-2 py-1 text-left">RM decisive</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-border align-top">
                  <td className="px-2 py-1 text-foreground">{r.scenario_id}/{r.seed}</td>
                  <td className="px-2 py-1">{r.d0_selected_strategy ?? "—"}</td>
                  <td className="px-2 py-1">{r.d1_selected_strategy ?? "—"}</td>
                  <td className="px-2 py-1 text-right">{r.d0_goal_achievement.toFixed(3)}</td>
                  <td className="px-2 py-1 text-right">{r.d1_goal_achievement.toFixed(3)}</td>
                  <td className="px-2 py-1">{r.rm_decisive ? (r.rm_decisive_outcome ?? "yes") : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Panel>
  );
}

function RiskManagerCalibrationPanel({ d }: { d: RiskManagerCalibration }) {
  const pct = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(0)}%`);
  const num = (x: number | null | undefined, dp = 3) => (x == null ? "—" : x.toFixed(dp));
  const variants = d.variants ?? [];
  const agg = d.aggregates ?? {};
  const crit = d.criteria_evaluation ?? {};
  const paired = d.paired_vs_r0 ?? {};
  const zv = d.zero_variance_diagnostic ?? {};
  const dtMean = d.digital_twin_mean_goal_achievement;

  const gaChart = variants.map((v) => ({ variant: v, goal: agg[v]?.goal_achievement?.mean ?? 0 }));
  const raChart = variants.map((v) => ({ variant: v, risk_adjusted: agg[v]?.risk_adjusted_score?.mean ?? 0 }));

  const verdictTone =
    d.verdict === "PROMISING" ? "text-success"
    : d.verdict === "PARTIALLY PROMISING" ? "text-foreground"
    : "text-danger";

  return (
    <Panel
      title="Risk Manager calibration (research-only — no variant promoted)"
      right={
        <span className="text-xs text-muted">
          {d.experiment_name ?? "experiment"} {d.experiment_id.slice(0, 8)} · {d.total_scenario_seed_pairs} scenario-seed pairs
        </span>
      }
    >
      <p className="mb-3 text-xs text-muted">
        R0 = production (== D0). D1 = risk penalty removed (reference). R1 = robust historical scale
        for extrapolation risk. R2-λ = R0 risk, ranking penalty weight λ. R3 = R1 + the λ chosen by a
        pre-specified criterion ({d.r3_selection ? `λ=${d.r3_selection.lambda}` : "—"}). Only risk
        estimation / contribution changes — Digital Twin predictions, candidates, agent scores,
        scenarios and seeds are identical. Every variant is EXPERIMENTAL; production stays R0 / D0.
      </p>

      <div className={`mb-4 rounded-xl border border-border bg-muted-surface p-3 text-sm font-medium ${verdictTone}`}>
        Risk Calibration Verdict: {d.verdict ?? "—"}
        <span className="ml-2 text-xs font-normal text-muted">
          (best calibration variant: {d.best_calibration_variant ?? "—"}; generated from the
          pre-specified criteria, not chosen manually)
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="bg-muted-surface text-muted">
            <tr>
              <th className="px-2 py-1 text-left">Variant</th>
              <th className="px-2 py-1 text-right">Goal achievement [95% CI]</th>
              <th className="px-2 py-1 text-right">Risk-adjusted</th>
              <th className="px-2 py-1 text-right">Confidence</th>
              <th className="px-2 py-1 text-right">DT-best agree</th>
              <th className="px-2 py-1 text-right">Spearman ρ</th>
              <th className="px-2 py-1 text-right">Mono. viol.</th>
              <th className="px-2 py-1 text-left">Verdict</th>
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-border bg-muted-surface/40">
              <td className="px-2 py-1 font-medium text-foreground">Digital Twin (B)</td>
              <td className="px-2 py-1 text-right">{num(dtMean)}</td>
              <td className="px-2 py-1 text-right">—</td>
              <td className="px-2 py-1 text-right">—</td>
              <td className="px-2 py-1 text-right">—</td>
              <td className="px-2 py-1 text-right">—</td>
              <td className="px-2 py-1 text-right">—</td>
              <td className="px-2 py-1">reference</td>
            </tr>
            {variants.map((v) => {
              const a = agg[v];
              const ga = a?.goal_achievement;
              const mono = a?.risk_monotonicity;
              return (
                <tr key={v} className="border-t border-border">
                  <td className="px-2 py-1 font-medium text-foreground">{v}</td>
                  <td className="px-2 py-1 text-right">
                    {ga ? `${ga.mean.toFixed(3)}${ga.ci95 ? ` [${ga.ci95[0].toFixed(3)}, ${ga.ci95[1].toFixed(3)}]` : ""}` : "—"}
                  </td>
                  <td className="px-2 py-1 text-right">{num(a?.risk_adjusted_score?.mean, 1)}</td>
                  <td className="px-2 py-1 text-right">{num(a?.confidence?.mean)}</td>
                  <td className="px-2 py-1 text-right">{pct(a?.dt_best_agreement_rate)}</td>
                  <td className="px-2 py-1 text-right">{num(mono?.spearman_rho_distance_vs_risk, 3)}</td>
                  <td className="px-2 py-1 text-right">{mono?.price10_safer_than_price5_violations ?? "—"}</td>
                  <td className="px-2 py-1">{v === "R0" || v === "D1" ? "reference" : (crit[v]?.verdict ?? "—")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-1 text-xs font-medium text-foreground">Variant vs goal achievement</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={gaChart}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="variant" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} domain={[0, 1]} />
              <Tooltip />
              <Bar dataKey="goal" fill="var(--chart-1, #4f46e5)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-foreground">Variant vs risk-adjusted score</p>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={raChart}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="variant" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="risk_adjusted" fill="var(--chart-2, #059669)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-1 text-xs font-medium text-foreground">
          Zero-variance diagnostic — extrapolation risk by history type (R0 → R1)
        </p>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted-surface text-muted">
              <tr>
                <th className="px-2 py-1 text-left">History</th>
                {Object.keys(zv[Object.keys(zv)[0] ?? ""] ?? {}).map((mv) => (
                  <th key={mv} className="px-2 py-1 text-right">{mv}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(zv).map(([hname, moves]) => (
                <tr key={hname} className="border-t border-border">
                  <td className="px-2 py-1 text-foreground">{hname.replace(/_/g, " ")}</td>
                  {Object.entries(moves).map(([mv, rr]) => (
                    <td key={mv} className="px-2 py-1 text-right">
                      {rr.R0.toFixed(2)} → <span className="text-success">{rr.R1.toFixed(2)}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4">
        <p className="mb-1 text-xs font-medium text-foreground">Paired vs R0 (goal achievement)</p>
        <DataTable
          headers={["Variant", "Mean diff", "95% CI", "Wins/Ties/Losses", "p", "r", "Interpretation"]}
          rows={variants.filter((v) => v !== "R0").map((v) => {
            const p = paired[v];
            if (!p) return [v, "—", "—", "—", "—", "—", "—"];
            const wins = (p[`${v}_wins`] as number | undefined) ?? 0;
            return [
              v,
              p.mean_difference.toFixed(4),
              p.mean_difference_ci95 ? `[${p.mean_difference_ci95[0]}, ${p.mean_difference_ci95[1]}]` : "—",
              `${wins}/${p.ties}/${(p.r0_wins as number | undefined) ?? 0}`,
              p.p_value != null ? String(p.p_value) : "—",
              p.effect_size_r != null ? String(p.effect_size_r) : "—",
              p.interpretation,
            ];
          })}
        />
      </div>

      <div className="mt-4 rounded-xl border border-border p-3 text-xs">
        <p className="font-medium text-foreground">Pre-specified criteria</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-muted">
          {(d.pre_specified_criteria ?? []).map((c, i) => <li key={i}>{c}</li>)}
        </ul>
        <div className="mt-2 grid gap-2 md:grid-cols-3">
          {Object.entries(crit).map(([v, c]) => (
            <div key={v} className="rounded border border-border p-2">
              <p className="font-medium text-foreground">{v} — {c.verdict} ({c.criteria_passed}/{c.criteria_total})</p>
              <ul className="mt-1 space-y-0.5">
                {Object.entries(c.checks).map(([k, ok]) => (
                  <li key={k} className={ok ? "text-success" : "text-danger"}>
                    {ok ? "✓" : "✗"} {k.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}

function RiskManagerGeneralizationPanel({ d }: { d: RiskManagerGeneralization }) {
  const num = (x: number | null | undefined, dp = 3) => (x == null ? "—" : x.toFixed(dp));
  const ev = d.external_validation;
  const ov = d.risk_regime_overall;
  const dc = d.decision_comparison_simulated ?? {};
  const hyp = d.hypotheses ?? {};
  const regimes = ["LOW_VARIANCE", "MODERATE_VARIANCE", "HIGH_VARIANCE"];

  // "VALIDATED FOR CONTROLLED PRODUCTION TEST" is an internal pre-registered
  // criteria-checklist label (all 7 core criteria + a real-LLM criterion). It is
  // NOT real-world, scientific, or production validation, so it is not styled as
  // a success. Only an explicit "NOT VALIDATED" is flagged.
  const tone = ev?.verdict === "NOT VALIDATED" ? "text-danger" : "text-foreground";

  return (
    <Panel
      title="Risk Manager — generalization / real-Indian-data validation (research-only)"
      right={
        <span className="text-xs text-muted">
          {d.experiment_name ?? "experiment"} {d.experiment_id.slice(0, 8)} · {d.dataset?.category}
        </span>
      }
    >
      <p className="mb-3 text-xs text-muted">
        Tests whether R3 (robust extrapolation-risk scale + λ = 0.25), <span className="font-medium">PROMISING</span>{" "}
        on the synthetic suite, generalizes to real Indian e-commerce data ({d.dataset?.name},{" "}
        <span className="font-medium">{d.dataset?.provenance}</span> provenance). No λ re-tuned, no
        threshold changed. Production stays {d.production_default ?? "R0"}.
      </p>

      <div className={`mb-4 rounded-xl border border-border bg-muted-surface p-3 text-sm font-medium ${tone}`}>
        External validation verdict: {ev?.verdict ?? "—"}
        <span className="ml-2 text-xs font-normal text-muted">
          (central benefit confirmed on real data: {String(ev?.central_benefit_confirmed_on_real_data ?? "—")};
          anything regressed: {String(ev?.anything_regressed_on_real_data ?? "—")})
        </span>
        <span className="mt-1 block text-xs font-normal text-muted">
          This verdict is an internal, pre-registered criteria-checklist label from the experiment —
          not real-world, scientific, or production validation. A real LLM is not configured, so the
          real-LLM criterion is unmet and the strongest reachable verdict is
          &ldquo;PROMISING BUT NOT VALIDATED&rdquo;. Production stays R0 / D0.
        </span>
      </div>

      <StatGrid>
        <Metric label="Real price sub-series" value={String((d.sub_series ?? []).length)}
          hint={regimes.map((r) => `${r.split("_")[0]} ${d.regime_counts?.[r] ?? 0}`).join(" · ")} />
        <Metric label="R0 == R1 on all real rows" value={String(ov?.r0_equals_r1_all_rows ?? "—")}
          hint="the zero-variance pathology does not occur on real data" />
        <Metric label="Spearman ρ (dist vs risk)" value={num(ov?.spearman_rho_dist_vs_r1, 3)}
          hint={`R0 ${num(ov?.spearman_rho_dist_vs_r0, 3)} · identical`} />
        <Metric label="Monotonicity violations (R1)" value={String(ov?.monotonicity_violations_r1 ?? "—")}
          hint={`extreme-probe penalised ${num(ov?.extreme_outside_range_penalised_r1, 2)}`} />
      </StatGrid>

      {/* risk by regime */}
      <div className="mt-4 overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="bg-muted-surface text-muted">
            <tr>
              <th className="px-2 py-1 text-left">Regime</th>
              <th className="px-2 py-1 text-right">sub-series</th>
              <th className="px-2 py-1 text-right">ρ R0</th>
              <th className="px-2 py-1 text-right">ρ R1</th>
              <th className="px-2 py-1 text-right">mono. viol. R1</th>
              <th className="px-2 py-1 text-right">mean legit risk R0→R1</th>
              <th className="px-2 py-1 text-right">R0==R1</th>
            </tr>
          </thead>
          <tbody>
            {regimes.map((r) => {
              const a = d.risk_regime_by_regime?.[r];
              if (!a) return null;
              return (
                <tr key={r} className="border-t border-border">
                  <td className="px-2 py-1 text-foreground">{r.replace(/_/g, " ")}</td>
                  <td className="px-2 py-1 text-right">{a.n_sub_series ?? "—"}</td>
                  <td className="px-2 py-1 text-right">{num(a.spearman_rho_dist_vs_r0, 3)}</td>
                  <td className="px-2 py-1 text-right">{num(a.spearman_rho_dist_vs_r1, 3)}</td>
                  <td className="px-2 py-1 text-right">{a.monotonicity_violations_r1}</td>
                  <td className="px-2 py-1 text-right">{num(a.mean_r0_risk_legit_moves, 3)} → {num(a.mean_r1_risk_legit_moves, 3)}</td>
                  <td className="px-2 py-1 text-right">{String(a.r0_equals_r1_all_rows ?? "—")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* SIMULATED decision comparison */}
      <div className="mt-4">
        <p className="mb-1 text-xs font-medium text-foreground">
          Decision comparison — <span className="uppercase text-muted">simulated</span> (no real intervention outcome)
        </p>
        <DataTable
          headers={["Variant", "Selected strategy", "Goal ach.", "Risk-adjusted", "Confidence", "Sel. DT-risk", "Changed vs R0"]}
          rows={Object.entries(dc).map(([v, c]) => [
            v, c.selected_strategy ?? "—", num(c.goal_achievement, 2),
            num(c.risk_adjusted_score, 1), num(c.confidence, 3), num(c.selected_dt_risk, 3),
            c.strategy_changed_vs_r0 ? "yes" : "no",
          ])}
        />
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 text-xs">
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium text-foreground">Real-LLM validation</p>
          <p className="mt-1 text-muted">
            <span className={d.real_llm?.status === "AVAILABLE" ? "text-success" : "text-danger"}>
              {d.real_llm?.status ?? "—"}
            </span>{" "}
            {d.real_llm?.reason ?? ""}
          </p>
        </div>
        <div className="rounded-lg border border-border p-3">
          <p className="font-medium text-foreground">DecisionOutcome validation</p>
          <p className="mt-1 text-muted">
            <span className={d.decision_outcome?.status === "AVAILABLE" ? "text-success" : "text-danger"}>
              {d.decision_outcome?.status ?? "—"}
            </span>{" "}
            — {d.decision_outcome?.decision_outcome_records ?? 0} records; Table 2 {d.decision_outcome?.table_2 ?? "—"}
          </p>
        </div>
      </div>

      {/* hypotheses */}
      <div className="mt-4 rounded-xl border border-border p-3 text-xs">
        <p className="font-medium text-foreground">Pre-registered hypotheses</p>
        <ul className="mt-1 space-y-0.5">
          {Object.entries(hyp).filter(([k]) => !k.startsWith("_") && !k.endsWith("_note")).map(([k, v]) => (
            <li key={k} className={String(v).startsWith("SUPPORTED") ? "text-success" : "text-muted"}>
              <span className="font-medium">{k.replace(/_/g, " ")}:</span> {v}
            </li>
          ))}
        </ul>
        {hyp["H5_note"] ? <p className="mt-2 text-muted">{hyp["H5_note"]}</p> : null}
      </div>
    </Panel>
  );
}
