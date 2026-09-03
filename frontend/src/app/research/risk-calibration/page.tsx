"use client";

import { useEffect, useState } from "react";
import { researchApi, type AgentEvaluation } from "@/lib/research-api";

function n(v: unknown, dp = 3) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(dp) : "—";
}

export default function RiskCalibrationPage() {
  const [agents, setAgents] = useState<AgentEvaluation | null>(null);
  useEffect(() => {
    researchApi.agentEvaluation().then(setAgents).catch(() => {});
  }, []);

  const rmc = agents?.risk_manager_calibration ?? null;
  const rmg = agents?.risk_manager_generalization ?? null;
  const ag = rmc?.aggregates ?? null;
  const variants = ["R0", "R1", "R2-0.25", "R2-0.50", "R2-0.75", "R3"];

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Risk Calibration</h1>
        <p className="mt-1 text-sm text-muted">
          Does the extrapolation-risk term need recalibrating? Pre-registered study on the synthetic
          suite, then a probe on real data.
        </p>
      </header>

      <p>
        <span className="rounded-full bg-warning-soft px-2.5 py-1 text-xs font-semibold text-warning">
          R3: PROMISING — NOT PROMOTED
        </span>{" "}
        <span className="ml-2 text-sm text-muted">
          Production stays <strong className="text-foreground">R0 / D0</strong> (risk_model = None,
          risk_penalty_lambda = 1.0).
        </span>
      </p>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Synthetic calibration suite (12 scenarios × 5 seeds)
        </h2>
        <div className="mt-3 overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted-surface/50 text-left text-muted">
                <th className="px-4 py-2.5 font-medium">Variant</th>
                <th className="px-4 py-2.5 text-right font-medium">Goal achievement</th>
                <th className="px-4 py-2.5 text-right font-medium">Risk-adjusted</th>
                <th className="px-4 py-2.5 text-right font-medium">Internal confidence</th>
                <th className="px-4 py-2.5 text-right font-medium">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {variants.map((v) => {
                const a = ag?.[v];
                const verdict = rmc?.verdict_by_variant?.[v] ?? (v === "R0" ? "baseline" : "");
                return (
                  <tr key={v} className={`border-b border-border last:border-0 ${v === "R3" ? "bg-success-soft/40" : ""}`}>
                    <td className="px-4 py-2.5 font-medium">{v === "R0" ? "R0 (production)" : v}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{n(a?.goal_achievement?.mean)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{n(a?.risk_adjusted_score?.mean, 1)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums">{n(a?.confidence?.mean)}</td>
                    <td className="px-4 py-2.5 text-right text-xs text-muted">{verdict}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-muted">
          R3 = robust extrapolation scale + bounded penalty weight λ = 0.25. Digital-Twin reference mean
          goal achievement {n(rmc?.digital_twin_mean_goal_achievement ?? 0.486)}. Paired Wilcoxon (R3 − R0):
          p = {n(rmc?.paired_vs_r0?.R3?.p_value, 4)}.
        </p>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Real-data probe (Benroshan)</h2>
        <p className="mt-2 text-sm text-foreground">
          R0 and R1 produced <strong>identical</strong> risk scores on{" "}
          {rmg?.risk_regime_overall?.n_rows ?? 184}/{rmg?.risk_regime_overall?.n_rows ?? 184} rows across{" "}
          {rmg?.regime_counts ? Object.values(rmg.regime_counts).reduce((a, b) => a + b, 0) : 23} sub-series.
          The zero/low-variance denominator collapse that R3 fixes does not occur on real implied-price
          data. Verdict: <strong>{rmg?.external_validation?.verdict ?? "PROMISING BUT NOT VALIDATED"}</strong>.
        </p>
      </section>

      <p className="rounded-lg border border-border bg-muted-surface/40 px-4 py-3 text-sm text-muted">
        Pre-registration: `docs/RISK_CALIBRATION_ANALYSIS.md` (formula, variants, λ rule and 7 acceptance
        criteria fixed before running). No variant was promoted.
      </p>
    </div>
  );
}
