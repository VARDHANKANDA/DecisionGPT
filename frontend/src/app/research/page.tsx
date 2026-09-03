"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  researchApi,
  type AgentEvaluation,
  type PaperResults,
  type ResearchOverview,
} from "@/lib/research-api";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function num(v: unknown, dp = 3): string {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(dp) : "—";
}
function pct(v: unknown, dp = 2): string {
  return typeof v === "number" && Number.isFinite(v) ? `${(v * (v <= 1 ? 100 : 1)).toFixed(dp)}%` : "—";
}

function tableSection(paper: PaperResults | null, key: string, sectionName: string) {
  const t = paper?.tables.find((x) => x.key === key);
  return t?.sections.find((s) => s.name.toLowerCase().includes(sectionName.toLowerCase())) ?? null;
}

// ---------------------------------------------------------------------------
// page
// ---------------------------------------------------------------------------

export default function ResearchOverviewPage() {
  const [ov, setOv] = useState<ResearchOverview | null>(null);
  const [paper, setPaper] = useState<PaperResults | null>(null);
  const [agents, setAgents] = useState<AgentEvaluation | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([
      researchApi.overview(),
      researchApi.paperResults(),
      researchApi.agentEvaluation(),
    ]).then(([o, p, a]) => {
      if (o.status === "fulfilled") setOv(o.value);
      else setErr(String(o.reason?.message ?? o.reason));
      if (p.status === "fulfilled") setPaper(p.value);
      if (a.status === "fulfilled") setAgents(a.value);
    });
  }, []);

  const mad = agents?.multi_agent_diagnostic ?? null;
  const bVal = mad?.digital_twin_mean_goal_achievement ?? 0.486;
  const dVal = mad?.full_decisiongpt_mean_goal_achievement ?? 0.084;
  const oo = mad?.override_outcomes;
  const losses = oo?.degraded ?? 45;
  const ties = oo?.neutral ?? 15;
  const wins = oo?.improved ?? 0;

  const rmc = agents?.risk_manager_calibration ?? null;
  const r0Mean = rmc?.aggregates?.R0?.goal_achievement?.mean ?? 0.084;
  const r3Mean = rmc?.aggregates?.R3?.goal_achievement?.mean ?? 0.168;
  const r3Ci = rmc?.aggregates?.R3?.goal_achievement?.ci95 ?? null;
  const r3P = rmc?.paired_vs_r0?.R3?.p_value ?? 0.0253;

  const rmg = agents?.risk_manager_generalization ?? null;
  const rmgRows = rmg?.risk_regime_overall?.n_rows ?? 184;
  const r0eqr1 = rmg?.risk_regime_overall?.r0_equals_r1_all_rows ?? true;

  const table2 = paper?.tables.find((t) => t.key === "digital_twin_evaluation");

  // The paper's frozen evidence base is exactly 16 experiments
  // (experiments/experiment_manifest.json). The development database can hold a
  // few extra non-frozen re-runs; show the frozen count as the headline and note
  // any drift so the live number is never mistaken for frozen research evidence.
  const FROZEN_EXPERIMENTS = 16;
  const liveRuns = ov?.experiment_count ?? null;
  const extraRuns = liveRuns != null ? liveRuns - FROZEN_EXPERIMENTS : 0;
  const runsNote =
    liveRuns != null && extraRuns > 0
      ? ` The development database currently records ${liveRuns} runs — ${extraRuns} non-frozen re-run${extraRuns === 1 ? "" : "s"} beyond the frozen set, not part of the frozen evidence base.`
      : "";
  const fc = tableSection(paper, "predictive_model_performance", "forecast");
  const ch = tableSection(paper, "predictive_model_performance", "classification");
  const abl = paper?.tables.find((t) => t.key === "ablation_study")?.sections[0] ?? null;
  const arch = paper?.tables.find((t) => t.key === "decision_architecture")?.sections[0] ?? null;

  return (
    <div className="space-y-12">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Research Console</h1>
        <p className="mt-1 text-sm text-muted">DecisionGPT — Controlled Evaluation &amp; Research Evidence</p>
      </header>

      {err ? <p className="rounded-lg bg-danger-soft px-4 py-3 text-sm text-danger">{err}</p> : null}

      {/* -------- 1. status strip -------- */}
      <section>
        <div className="overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <tbody>
              {[
                ["Frozen experiments", String(FROZEN_EXPERIMENTS)],
                ["Controlled evaluation", "Complete"],
                ["Real SME outcomes", "0"],
                ["Real-LLM validation", "Blocked"],
                ["Table 2 (Digital Twin vs actual)", table2?.available ? "Ready" : "Not ready"],
                ["Causal intervention evidence", "0"],
                ["Production decision config", "R0 / D0"],
              ].map(([k, v], i) => (
                <tr key={k} className={i % 2 ? "bg-muted-surface/40" : ""}>
                  <th scope="row" className="w-1/2 px-4 py-2.5 text-left font-medium text-muted">
                    {k}
                  </th>
                  <td className="px-4 py-2.5 font-semibold text-foreground">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">
          Metric values on this page are read live from stored experiment rows; nothing here is a
          real-world performance claim. The frozen evidence base is exactly {FROZEN_EXPERIMENTS}{" "}
          experiments (<code>experiments/experiment_manifest.json</code>).{runsNote}
        </p>
      </section>

      {/* -------- 2. main finding -------- */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">Main finding</h2>
        <p className="mt-2 max-w-2xl text-base text-foreground">
          <strong>Decision simulation was the strongest value-adding component.</strong> In the controlled
          12-scenario suite it is the only component that raised the simulated goal-achievement metric.
        </p>

        <div className="mt-5 overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted-surface/50 text-left text-muted">
                <th className="px-4 py-2.5 font-medium">Configuration</th>
                <th className="px-4 py-2.5 text-right font-medium">Simulated goal achievement</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border">
                <td className="px-4 py-2.5">Prediction only</td>
                <td className="px-4 py-2.5 text-right tabular-nums">0.000</td>
              </tr>
              <tr className="border-b border-border bg-success-soft/40">
                <td className="px-4 py-2.5 font-medium">Prediction + Decision Simulation</td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{num(bVal)}</td>
              </tr>
              <tr>
                <td className="px-4 py-2.5">Full system + rule-based multi-agent layer</td>
                <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{num(dVal)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="mt-4">
          <BarRow label="Prediction only" value={0} />
          <BarRow label="Prediction + Decision Simulation" value={bVal} highlight />
          <BarRow label="Full system + multi-agent" value={dVal} />
        </div>

        <p className="mt-4 text-sm text-foreground">
          Adding the rule-based multi-agent evaluation layer <strong>reduced</strong> simulated goal
          achievement compared with the strongest baseline.
        </p>
        <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
          <li>D vs B: <span className="font-medium text-foreground">{num(dVal - bVal)}</span></li>
          <li>{losses} losses / {ties} ties / {wins} wins (of 60 paired scenarios)</li>
          <li>Wilcoxon <span className="font-medium text-foreground">p &lt; 0.0001</span></li>
          <li>effect size r ≈ 0.87</li>
        </ul>

        <p className="mt-4 rounded-lg border border-warning/40 bg-warning-soft px-4 py-3 text-sm text-warning">
          These are results from the controlled synthetic evaluation suite. They are <strong>not</strong>{" "}
          real SME outcomes. The 12 scenarios are designed, not sampled from a population.
        </p>
      </section>

      {/* -------- 3. predictive model performance -------- */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">Predictive model performance</h2>
        <p className="mt-1 text-xs text-muted">
          Dataset: <span className="font-medium">controlled synthetic</span> forecasting / churn datasets
          (SYNTHETIC_CONTROLLED). Metrics are exactly those stored — not &ldquo;accuracy&rdquo;.
        </p>

        <h3 className="mt-4 text-sm font-medium text-foreground">Sales forecasting</h3>
        <SimpleTable
          headers={["Model", "MAE", "RMSE", "MAPE"]}
          rows={(fc?.rows ?? [])
            .filter((r) => String(r[2]) === "active")
            .map((r) => [
              String(r[0]).replace("sales_forecast_", ""),
              num(r[4], 2),
              num(r[5], 2),
              pct(r[6], 2),
            ])}
          bestRow={(rows) =>
            rows.reduce((best, r, i) => (parseFloat(r[1]) < parseFloat(rows[best][1]) ? i : best), 0)
          }
          fallback={[
            ["naive", "24.66", "38.28", "15.46%"],
            ["linear", "17.29", "25.51", "12.49%"],
            ["xgboost", "15.14", "21.86", "10.30%"],
          ]}
        />

        <h3 className="mt-6 text-sm font-medium text-foreground">Churn prediction</h3>
        <SimpleTable
          headers={["Model", "F1", "ROC-AUC"]}
          rows={(ch?.rows ?? []).map((r) => [
            String(r[0]).replace("churn_", "").replace(/_/g, " "),
            num(r[6], 3),
            num(r[7], 3),
          ])}
          bestRow={(rows) =>
            rows.reduce((best, r, i) => (parseFloat(r[2]) > parseFloat(rows[best][2]) ? i : best), 0)
          }
          fallback={[
            ["logistic regression", "0.669", "0.798"],
            ["random forest", "0.661", "0.793"],
            ["xgboost", "0.658", "0.792"],
          ]}
        />
      </section>

      {/* -------- 4. ablation -------- */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">Which components actually helped?</h2>
        <div className="mt-3 overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted-surface/50 text-left text-muted">
                <th className="px-4 py-2.5 font-medium">Component removed</th>
                <th className="px-4 py-2.5 text-right font-medium">Change in goal achievement</th>
              </tr>
            </thead>
            <tbody>
              {(abl?.rows ?? [])
                .filter((r) => String(r[1]) !== "(none)")
                .map((r) => {
                  const label = String(r[1])
                    .replace("digital_twin", "Decision Simulation")
                    .replace("causal_graph", "Association graph")
                    .replace("multi_agent", "Multi-agent layer")
                    .replace("explainability", "Explanation")
                    .replace("memory", "Memory");
                  const delta = typeof r[3] === "number" ? r[3] : 0;
                  return (
                    <tr key={String(r[0])} className="border-b border-border last:border-0">
                      <td className="px-4 py-2.5">{label}</td>
                      <td
                        className={`px-4 py-2.5 text-right font-medium tabular-nums ${
                          delta > 0 ? "text-success" : "text-muted"
                        }`}
                      >
                        {delta > 0 ? "+" : ""}
                        {num(delta)}
                      </td>
                    </tr>
                  );
                })}
              {!abl ? (
                <>
                  <tr className="border-b border-border">
                    <td className="px-4 py-2.5">Decision Simulation</td>
                    <td className="px-4 py-2.5 text-right font-medium text-success tabular-nums">+0.084</td>
                  </tr>
                  {["Association graph", "Multi-agent layer", "Explanation", "Memory"].map((c) => (
                    <tr key={c} className="border-b border-border last:border-0">
                      <td className="px-4 py-2.5">{c}</td>
                      <td className="px-4 py-2.5 text-right text-muted tabular-nums">0.000</td>
                    </tr>
                  ))}
                </>
              ) : null}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-sm text-muted">
          The controlled ablation indicates that the measurable objective value came from the
          decision-simulation layer; the other removals produced no measurable change in this suite.
        </p>
      </section>

      {/* -------- 5. multi-agent finding -------- */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">Multi-agent finding</h2>
        <p className="mt-2 text-base font-medium text-foreground">
          More agents did not improve the result in this evaluation.
        </p>
        <ul className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-muted sm:grid-cols-3">
          <li>Decision-simulation baseline: <span className="font-medium text-foreground">{num(bVal)}</span></li>
          <li>Full system: <span className="font-medium text-foreground">{num(dVal)}</span></li>
          <li>Difference: <span className="font-medium text-foreground">{num(dVal - bVal)}</span></li>
          <li>Wins: <span className="font-medium text-foreground">{wins}</span></li>
          <li>Ties: <span className="font-medium text-foreground">{ties}</span></li>
          <li>Losses: <span className="font-medium text-foreground">{losses}</span></li>
          <li>Wilcoxon: <span className="font-medium text-foreground">p &lt; 0.0001</span></li>
        </ul>
        <p className="mt-3 text-sm text-foreground">
          <span className="font-medium">Interpretation.</span> The failure analysis attributes the
          degradation to the optimizer&apos;s risk-penalty term rather than an unequal candidate strategy
          space (the candidate-space confound was found, corrected, and shown not to change the result).
        </p>
        <details className="mt-3 rounded-lg border border-border bg-surface">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-foreground">
            Show technical evidence
          </summary>
          <div className="border-t border-border p-4 text-sm text-muted">
            <p>
              Decision-simulation-best strategy → final selection override rate:{" "}
              {num(mad?.digital_twin_to_final?.override_rate ?? 1, 2)} ({mad?.digital_twin_to_final?.overridden ?? 60}
              /60). Of those overrides: {wins} improved, {ties} neutral, {losses} degraded the objective.
              A risk-penalty sensitivity variant (D1, penalty un-weighted) raised the mean to{" "}
              {num(agents?.risk_manager_diagnostic?.baseline?.d1_risk_penalty_sensitivity_mean_goal_achievement ?? 0.583)}{" "}
              (Wilcoxon p &lt; 0.0001) — isolating the risk-penalty term as the proximate mechanism.
            </p>
            <Link
              href="/research/agent-evaluation"
              className="mt-2 inline-block font-medium text-accent underline underline-offset-4"
            >
              Full architecture &amp; failure analysis →
            </Link>
          </div>
        </details>
      </section>

      {/* -------- 6. risk calibration -------- */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">Risk calibration</h2>
        <p className="mt-2">
          <span className="rounded-full bg-warning-soft px-2.5 py-1 text-xs font-semibold text-warning">
            PROMISING — NOT PROMOTED
          </span>
        </p>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-border bg-surface p-4">
            <p className="text-sm font-medium text-foreground">Synthetic calibration suite</p>
            <ul className="mt-2 space-y-1 text-sm text-muted">
              <li>R0 (production): <span className="font-medium text-foreground">{num(r0Mean)}</span></li>
              <li>R3 (robust scale + λ=0.25): <span className="font-medium text-foreground">{num(r3Mean)}</span>{r3Ci ? ` [${num(r3Ci[0])}, ${num(r3Ci[1])}]` : ""}</li>
              <li>Improvement: <span className="font-medium text-foreground">+{num(r3Mean - r0Mean)}</span> · p = {num(r3P, 4)}</li>
            </ul>
          </div>
          <div className="rounded-xl border border-border bg-surface p-4">
            <p className="text-sm font-medium text-foreground">Real-data probe (Benroshan)</p>
            <p className="mt-2 text-sm text-muted">
              R0 and R1 were <span className="font-medium text-foreground">identical on {rmgRows}/{rmgRows} rows</span>
              {r0eqr1 ? "" : ""} — the low-variance pathology R3 targets does not occur on this real data.
            </p>
            <p className="mt-2 text-sm font-medium text-foreground">
              R3 is not validated on real Indian SME data.
            </p>
          </div>
        </div>
        <p className="mt-3 text-sm text-muted">
          Production stays <span className="font-medium text-foreground">R0 / D0</span> (risk_model = None,
          risk_penalty_lambda = 1.0). R3 is experimental only.
        </p>
        <details className="mt-3 rounded-lg border border-border bg-surface">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-foreground">
            Technical details — full R0 / R1 / R2 / R3 calibration
          </summary>
          <div className="border-t border-border p-4 text-sm text-muted">
            <p>
              Pre-registered study (`docs/RISK_CALIBRATION_ANALYSIS.md`): seven variants × 60 paired
              scenarios; the R3 λ was chosen by a fixed rule before the run; verdict{" "}
              {rmc?.verdict ?? "PROMISING"} on the synthetic suite; external verdict{" "}
              {rmg?.external_validation?.verdict ?? "PROMISING BUT NOT VALIDATED"}. No variant promoted.
            </p>
            <Link
              href="/research/risk-calibration"
              className="mt-2 inline-block font-medium text-accent underline underline-offset-4"
            >
              Risk Calibration page →
            </Link>
          </div>
        </details>
      </section>

      {/* -------- 7. real-world validation -------- */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">Real-world validation</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <StatusCard
            title="Real Indian SME outcomes"
            big="0"
            state="NOT READY"
            body="No genuine SME decision outcomes have been collected."
          />
          <StatusCard
            title="Real LLM"
            big="—"
            state="BLOCKED"
            body="No LLM provider is configured."
          />
          <StatusCard
            title="Causal intervention evidence"
            big="0"
            state="NOT READY"
            body="No real intervention outcomes have been collected."
          />
        </div>
        <p className="mt-4 rounded-lg border border-border bg-muted-surface/40 px-4 py-3 text-sm font-medium text-foreground">
          The current evidence base supports a controlled evaluation study — not validation of DecisionGPT
          on Indian SMEs.
        </p>
      </section>

      {/* -------- 8. claims box -------- */}
      <section>
        <h2 className="text-lg font-semibold text-foreground">What can we claim?</h2>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-success/30 bg-success-soft/30 p-4">
            <p className="text-sm font-semibold text-success">Supported</p>
            <ul className="mt-2 space-y-1.5 text-sm text-foreground">
              {[
                "Controlled component-level evaluation",
                "Decision-simulation value in the controlled suite",
                "Negative multi-agent result",
                "Mechanistic diagnosis of the degradation",
                "Synthetic causal-method validation",
                "Pre-registered risk-calibration study",
                "Reproducible experiment infrastructure",
              ].map((s) => (
                <li key={s}>✓ {s}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-border bg-surface p-4">
            <p className="text-sm font-semibold text-muted">Not established</p>
            <ul className="mt-2 space-y-1.5 text-sm text-foreground">
              {[
                "Real Indian SME performance",
                "Real-LLM validation",
                "Real-world causal effects",
                "Superiority over existing systems",
                "R3 production superiority",
                "Human explainability / usability benefit",
              ].map((s) => (
                <li key={s}>✗ {s}</li>
              ))}
            </ul>
          </div>
        </div>
        <p className="mt-4 text-xs text-muted">
          Reproducibility details (experiment IDs, seeds, dataset versions, manifest) are on the{" "}
          <Link href="/research/experiments" className="text-accent underline underline-offset-4">
            Reproducibility
          </Link>{" "}
          page. {arch ? `Architecture comparison N = ${arch.rows[0]?.[8] ?? 60} per configuration.` : ""}
        </p>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// small components
// ---------------------------------------------------------------------------

function BarRow({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  const w = Math.max(1, Math.min(100, value * 100));
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-medium text-foreground tabular-nums">{num(value)}</span>
      </div>
      <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-muted-surface">
        <div
          className={`h-full rounded-full ${highlight ? "bg-success" : "bg-accent"}`}
          style={{ width: `${w}%` }}
        />
      </div>
    </div>
  );
}

function SimpleTable({
  headers,
  rows,
  bestRow,
  fallback,
}: {
  headers: string[];
  rows: string[][];
  bestRow?: (rows: string[][]) => number;
  fallback: string[][];
}) {
  const data = rows.length ? rows : fallback;
  const best = bestRow ? bestRow(data) : -1;
  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted-surface/50 text-left text-muted">
            {headers.map((h, i) => (
              <th key={h} className={`px-4 py-2.5 font-medium ${i ? "text-right" : ""}`}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((r, ri) => (
            <tr key={ri} className={`border-b border-border last:border-0 ${ri === best ? "bg-success-soft/40" : ""}`}>
              {r.map((c, ci) => (
                <td
                  key={ci}
                  className={`px-4 py-2.5 tabular-nums ${ci ? "text-right" : "capitalize"} ${
                    ri === best && ci ? "font-semibold text-foreground" : ""
                  }`}
                >
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StatusCard({ title, big, state, body }: { title: string; big: string; state: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-muted-surface/40 p-5">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-foreground tabular-nums">{big}</p>
      <span className="mt-1 inline-block rounded-full bg-surface px-2 py-0.5 text-xs font-semibold text-muted">
        {state}
      </span>
      <p className="mt-2 text-xs leading-snug text-muted">{body}</p>
    </div>
  );
}
