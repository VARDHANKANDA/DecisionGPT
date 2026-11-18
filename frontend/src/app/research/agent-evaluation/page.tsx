"use client";

import { useEffect, useState } from "react";
import { EvalEmptyState, Expandable, PageIntro, Panel } from "@/components/research-ui";
import { Bar, Definition, EvidenceTypeBadge, num } from "@/components/research-evidence";
import { researchApi, type ArchitectureEvaluation } from "@/lib/research-api";

const signed = (v: number | null | undefined, dp = 3) => (v === null || v === undefined ? "not available" : `${v >= 0 ? "+" : ""}${v.toFixed(dp)}`);

export default function ArchitectureEvaluationPage() {
  const [data, setData] = useState<ArchitectureEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    researchApi
      .architectureEvaluation()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the architecture evaluation."));
  }, []);

  if (error) return <EvalEmptyState message={error} />;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;

  const ev = data.primary_evidence;
  const maxRegret = ev ? Math.max(...ev.architectures.map((a) => a.mean_regret), ...Object.values(ev.reference_points)) : 1;
  return (
    <div className="space-y-6">
      <PageIntro
        title="Architecture evaluation"
        subtitle="Does each added component — simulation, one agent, several agents — make decisions better? Every architecture is run on the same simulated scenarios."
      />

      <Panel title="In one sentence">
        <p className="text-sm text-foreground">{data.headline}</p>
        <p className="mt-1 text-xs text-muted">Simulated evidence only. It describes the tested configuration and simulated environments, not real businesses.</p>
      </Panel>

      <Panel title="What each architecture contains">
        <ol className="grid gap-3 sm:grid-cols-2">
          {data.architectures.map((a) => (
            <li key={a.key} className="rounded-xl border border-border p-3">
              <p className="text-sm font-semibold text-foreground">
                {a.key}. {a.name}
              </p>
              <p className="mt-1 text-xs text-muted">Includes: {a.includes.join(", ")}</p>
              <p className="mt-1 text-sm text-muted">Produces: {a.produces}</p>
            </li>
          ))}
        </ol>
      </Panel>

      {ev ? (
        <Panel title="Main result: decision quality over thousands of simulated decisions" right={<EvidenceTypeBadge type={ev.evidence_type} />}>
          <p className="text-sm text-muted">
            {ev.design.scenarios} scenarios × {ev.design.seeds} seeds = {ev.design.decisions_per_architecture.toLocaleString("en-IN")} decisions per architecture, identical for all four.
            Measure: <strong className="text-foreground">normalised regret</strong> — 0 means the oracle&apos;s choice, 1 the worst feasible choice. Lower is better. Dimensionless, so
            the four values share one honest scale.
          </p>
          <div className="mt-4 space-y-2" role="img" aria-label="Mean regret by architecture; lower is better">
            {ev.architectures.map((a) => (
              <Bar key={a.key} value={a.mean_regret} max={maxRegret} label={`${a.key}. ${a.name}`} note={`95% CI ${a.ci95[0].toFixed(3)}–${a.ci95[1].toFixed(3)}`} />
            ))}
            {Object.entries(ev.reference_points).map(([k, v]) => (
              <Bar key={k} value={v} max={maxRegret} label={`Reference: ${k.replace(/_/g, " ")}`} />
            ))}
          </div>

          <h3 className="mt-6 text-sm font-semibold text-foreground">Pairwise comparisons (regret difference; negative = the first is better)</h3>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <caption className="sr-only">Paired regret differences between architectures</caption>
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">Comparison</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Mean difference</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">95% interval</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Wins / ties / losses</th>
                  <th scope="col" className="py-1 text-right font-medium">Holm p</th>
                </tr>
              </thead>
              <tbody>
                {ev.comparisons.map((c) => (
                  <tr key={c.contrast} className="border-t border-border">
                    <th scope="row" className="py-1.5 pr-3 text-left font-medium text-foreground">{c.label}</th>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{signed(c.mean_difference)}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{signed(c.ci95[0])} to {signed(c.ci95[1])}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{c.wins} / {c.ties} / {c.losses}</td>
                    <td className="py-1.5 text-right tabular-nums">{c.p_holm === null ? "not available" : c.p_holm < 0.0001 ? "< 0.0001" : c.p_holm.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-muted">Unit of analysis: the scenario ({ev.design.scenarios} per comparison). Multiplicity: {ev.design.multiplicity}.</p>

          {ev.mechanism ? (
            <p className="mt-3 text-sm text-muted">
              Mechanism (associational): the full system changed the simulation-alone choice in {ev.mechanism.changed.toLocaleString("en-IN")} of {ev.mechanism.n.toLocaleString("en-IN")} decisions;
              {" "}{ev.mechanism.worsened.toLocaleString("en-IN")} got worse and {ev.mechanism.improved.toLocaleString("en-IN")} improved.
            </p>
          ) : null}
          <div className="mt-4">
            <Expandable summary="Difference by scenario family (full system minus simulation alone)">
              <ul className="space-y-1">
                {ev.family_effects_D_minus_B.map((f) => (
                  <li key={f.family} className="flex flex-wrap justify-between gap-2">
                    <span>{f.family.replace(/_/g, " ")} (n = {f.n_scenarios})</span>
                    <span className="tabular-nums text-foreground">
                      {signed(f.mean_D_minus_B)} [{signed(f.ci95[0])}, {signed(f.ci95[1])}] — {f.direction === "D_worse" ? "full system worse" : "full system better"}
                    </span>
                  </li>
                ))}
              </ul>
            </Expandable>
          </div>
        </Panel>
      ) : (
        <Panel title="Main result">
          <p className="text-sm font-medium text-foreground">Not evaluated.</p>
          <p className="text-sm text-muted">The multi-decision evidence file is not present, so no architecture ranking is shown.</p>
        </Panel>
      )}

      {data.improved_multiagent_study ? (
        <Panel
          title="Confirmatory Evaluation: Improved Multi-Agent Architectures (Untouched Scenarios)"
          right={<EvidenceTypeBadge type={data.improved_multiagent_study.evidence_type} />}
        >
          <div className="space-y-4">
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-4">
              <h3 className="text-sm font-semibold text-foreground">Pre-Registered Confirmatory Test Finding</h3>
              <p className="mt-1 text-sm text-foreground">{data.improved_multiagent_study.key_takeaway}</p>
              <p className="mt-2 text-xs text-muted">
                Evaluated on {data.improved_multiagent_study.n_instances} matched instances across {data.improved_multiagent_study.n_families} structurally distinct scenario families strictly in the untouched <code className="rounded bg-muted/20 px-1">{data.improved_multiagent_study.partition}</code> partition. Hyperparameters were tuned exclusively on development scenarios (zero test snooping).
              </p>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <caption className="sr-only">Confirmatory comparison of improved multi-agent architectures</caption>
                <thead className="text-left text-xs text-muted">
                  <tr className="border-b border-border">
                    <th scope="col" className="py-2 pr-3 font-medium">Architecture / Decision Mechanism</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">Mean Regret</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">SD</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">95% CI</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">Δ vs DT (B)</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">Holm p (B)</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">Δ vs Legacy (D)</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">Holm p (D)</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">Goal %</th>
                    <th scope="col" className="py-2 pr-3 text-right font-medium">Lat (s)</th>
                    <th scope="col" className="py-2 text-right font-medium">Cost ($)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.improved_multiagent_study.rows.map((r) => {
                    const isWinner = r.key === "C_single_agent" || r.key === "Cand_D_proposal_verification";
                    return (
                      <tr
                        key={r.key}
                        className={`border-t border-border ${isWinner ? "bg-primary/5 font-semibold" : ""}`}
                      >
                        <th scope="row" className="py-2 pr-3 text-left font-medium text-foreground">
                          {r.label}
                        </th>
                        <td className="py-2 pr-3 text-right tabular-nums text-foreground">{r.mean_regret.toFixed(4)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums text-muted">{r.sd_regret.toFixed(4)}</td>
                        <td className="py-2 pr-3 text-right tabular-nums text-muted text-xs">
                          [{r.ci95_regret[0].toFixed(3)}, {r.ci95_regret[1].toFixed(3)}]
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {r.key === "B_simulation_alone" ? "—" : signed(r.delta_vs_B, 4)}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums text-muted">
                          {r.key === "B_simulation_alone" ? "—" : r.p_holm_vs_B < 0.0001 ? "< 0.0001" : r.p_holm_vs_B.toFixed(4)}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">
                          {r.key === "D_legacy_multi_agent" ? "—" : signed(r.delta_vs_D, 4)}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums text-muted">
                          {r.key === "D_legacy_multi_agent" ? "—" : r.p_holm_vs_D < 0.0001 ? "< 0.0001" : r.p_holm_vs_D.toFixed(4)}
                        </td>
                        <td className="py-2 pr-3 text-right tabular-nums">{r.goal_achievement_pct.toFixed(1)}%</td>
                        <td className="py-2 pr-3 text-right tabular-nums text-muted">{r.mean_latency_sec < 0.001 ? "< 1ms" : `${(r.mean_latency_sec * 1000).toFixed(1)}ms`}</td>
                        <td className="py-2 text-right tabular-nums text-muted">${r.mean_cost_usd.toFixed(5)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="rounded-lg border border-border bg-card p-3 text-xs text-muted space-y-1">
              <p>• <strong>Primary Metric:</strong> Normalised regret against exogenous ground truth (0 = oracle, lower is better).</p>
              <p>• <strong>Key Failure Mode Solved:</strong> Legacy Multi-Agent suffered from subtractive penalty clamping (goal benefit minus risk penalty) and negative review ratchets. Candidate D (Proposal &amp; Verification) eliminates this degradation, matching the Digital Twin alone.</p>
              <p>• <strong>Production Architecture Recommendation:</strong> Retain Single Agent / Constrained Optimization as the default execution engine; deploy Multi-Agent Deliberation in an Adaptive Escalation mode when risk triggers fire.</p>
            </div>
          </div>
        </Panel>
      ) : null}

      {data.frozen_suite ? (
        <Panel title="Second source: synthetic suite, goal achievement" right={<EvidenceTypeBadge type="simulated" />}>
          <p className="text-sm text-muted">
            Mean goal achievement over {data.frozen_suite.pairs} scenario-seed pairs (a 0–1 fraction; higher is better). {data.frozen_suite.note}
          </p>
          <div className="mt-3 space-y-2">
            {data.frozen_suite.rows.map((r) => (
              <Bar key={r.key} value={r.mean_goal_achievement} max={1} label={`${r.key}. ${r.label}`} />
            ))}
          </div>
        </Panel>
      ) : null}

      {data.single_decision ? (
        <Panel title="Illustration: one recorded decision per architecture" right={<EvidenceTypeBadge type="simulated" />}>
          <p role="note" className="rounded-lg bg-warning-soft px-3 py-2 text-sm text-foreground">
            n = {data.single_decision.n_decisions_per_architecture}. This shows the units and the pipeline; it cannot rank the architectures.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <caption className="sr-only">One decision per architecture, in different units</caption>
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">Architecture</th>
                  <th scope="col" className="py-1 pr-3 font-medium">Chosen action</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Goal achievement (0–1)</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Expected benefit (currency)</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Risk-adjusted (currency)</th>
                  <th scope="col" className="py-1 text-right font-medium">Latency (s)</th>
                </tr>
              </thead>
              <tbody>
                {data.single_decision.rows.map((r) => (
                  <tr key={r.key} className="border-t border-border align-top">
                    <th scope="row" className="py-1.5 pr-3 text-left font-medium text-foreground">{r.key}. {r.label}</th>
                    {r.status === "not_applicable" ? (
                      <td colSpan={4} className="py-1.5 pr-3 text-muted">Not applicable — no decision was produced. {r.note}</td>
                    ) : (
                      <>
                        <td className="py-1.5 pr-3">{r.selected_strategy}</td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{num(r.goal_achievement, 2)}</td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{num(r.expected_benefit, 2)}</td>
                        <td className="py-1.5 pr-3 text-right tabular-nums">{num(r.risk_adjusted_score, 2)}</td>
                      </>
                    )}
                    <td className="py-1.5 text-right tabular-nums">{num(r.latency_seconds, 2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="mt-3 space-y-1 text-xs text-muted">
            {data.single_decision.caveats.map((c) => (
              <li key={c}>• {c}</li>
            ))}
          </ul>
        </Panel>
      ) : null}

      <Expandable summary="How each metric is defined">
        <dl className="space-y-3">
          {data.metric_definitions.map((m) => (
            <Definition key={m.metric} term={`${m.metric} — ${m.unit}; ${m.better} is better`}>
              {m.definition}
            </Definition>
          ))}
        </dl>
      </Expandable>

      <div className="grid gap-6 md:grid-cols-2">
        <Panel title="Comparability">
          <ul className="space-y-1.5 text-sm text-muted">
            {data.comparability.map((c) => (
              <li key={c}>• {c}</li>
            ))}
          </ul>
        </Panel>
        <Panel title="Limitations">
          <ul className="space-y-1.5 text-sm text-muted">
            {data.limitations.map((c) => (
              <li key={c}>• {c}</li>
            ))}
          </ul>
        </Panel>
      </div>
    </div>
  );
}
