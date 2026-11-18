"use client";

import { useEffect, useState } from "react";
import { EvalEmptyState, Expandable, PageIntro, Panel } from "@/components/research-ui";
import { CheckStatusBadge, Definition, EvidenceTypeBadge, num } from "@/components/research-evidence";
import { researchApi, type RiskAssessment } from "@/lib/research-api";

export default function RiskCalibrationPage() {
  const [data, setData] = useState<RiskAssessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    researchApi
      .riskAssessment()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the risk assessment."));
  }, []);

  if (error) return <EvalEmptyState message={error} />;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;

  const c = data.churn_probability_calibration;
  const drs = data.decision_risk_score;
  return (
    <div className="space-y-6">
      <PageIntro
        title="Risk calibration"
        subtitle="Do stated probabilities and intervals match what actually happened? 'Risk' means three different things in DecisionGPT, and only some of them can be calibrated."
      />

      <Panel title="Three meanings of “risk”">
        <ul className="space-y-3">
          {data.definitions.map((d) => (
            <li key={d.kind} className="rounded-xl border border-border p-3">
              <p className="text-sm font-semibold text-foreground">
                {d.kind} <span className="ml-1 text-xs font-normal text-muted">{d.is_probability ? "a probability" : "not a probability"}</span>
              </p>
              <p className="mt-1 text-sm text-muted">{d.meaning}</p>
              <p className="mt-1 text-xs text-muted">Calibration: <strong className="text-foreground">{d.calibration.replace(/_/g, " ")}</strong>. {d.why}</p>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Churn probabilities on held-out customers" right={c ? <EvidenceTypeBadge type={c.evidence_type} /> : <EvidenceTypeBadge type="not_evaluated" />}>
        {c ? (
          <>
            <p className="text-sm text-muted">
              Event: {c.event}. Model: {c.model}. {c.split.test_rows.toLocaleString("en-IN")} held-out customers ({c.split.scheme}); {c.metrics.positives.toLocaleString("en-IN")} churned.
            </p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-4">
              <div><dt className="text-muted">Brier score (lower is better)</dt><dd className="font-semibold text-foreground">{num(c.metrics.brier, 3)}</dd><dd className="text-xs text-muted">baseline {num(c.metrics.brier_baseline_prevalence, 3)}; 95% CI {num(c.metrics.brier_ci95[0], 3)}–{num(c.metrics.brier_ci95[1], 3)}</dd></div>
              <div><dt className="text-muted">Log loss</dt><dd className="font-semibold text-foreground">{num(c.metrics.log_loss, 3)}</dd><dd className="text-xs text-muted">baseline {num(c.metrics.log_loss_baseline_prevalence, 3)}</dd></div>
              <div><dt className="text-muted">Expected calibration error</dt><dd className="font-semibold text-foreground">{num(c.metrics.ece, 3)}</dd><dd className="text-xs text-muted">10 equal-width bins</dd></div>
              <div><dt className="text-muted">ROC-AUC (ranking, not calibration)</dt><dd className="font-semibold text-foreground">{num(c.metrics.roc_auc, 3)}</dd></div>
            </dl>
            <h3 className="mt-5 text-sm font-semibold text-foreground">Reliability: predicted probability vs what happened</h3>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full min-w-[480px] text-sm">
                <caption className="sr-only">Reliability table by predicted-probability bin</caption>
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th scope="col" className="py-1 pr-3 font-medium">Predicted range</th>
                    <th scope="col" className="py-1 pr-3 text-right font-medium">Customers</th>
                    <th scope="col" className="py-1 pr-3 text-right font-medium">Mean predicted</th>
                    <th scope="col" className="py-1 pr-3 text-right font-medium">Observed churn</th>
                    <th scope="col" className="py-1 font-medium">Predicted vs observed</th>
                  </tr>
                </thead>
                <tbody>
                  {c.metrics.reliability_table.map((b) => (
                    <tr key={b.bin[0]} className="border-t border-border">
                      <th scope="row" className="py-1.5 pr-3 text-left font-normal">{Math.round(b.bin[0] * 100)}–{Math.round(b.bin[1] * 100)}%</th>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{b.n}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{b.mean_predicted === null ? "no data" : `${(b.mean_predicted * 100).toFixed(1)}%`}</td>
                      <td className="py-1.5 pr-3 text-right tabular-nums">{b.observed_rate === null ? "no data" : `${(b.observed_rate * 100).toFixed(1)}%`}</td>
                      <td className="py-1.5">
                        {b.mean_predicted === null || b.observed_rate === null ? (
                          <span className="text-muted">—</span>
                        ) : (
                          <span className="flex items-center gap-2" aria-label={`predicted ${(b.mean_predicted * 100).toFixed(0)} percent, observed ${(b.observed_rate * 100).toFixed(0)} percent`}>
                            <span className="relative h-2.5 w-28 rounded-full bg-muted-surface">
                              <span className="absolute inset-y-0 left-0 rounded-full bg-accent/40" style={{ width: `${b.mean_predicted * 100}%` }} />
                              <span className="absolute -top-0.5 h-3.5 w-1 rounded bg-foreground" style={{ left: `calc(${b.observed_rate * 100}% - 2px)` }} />
                            </span>
                            <span className="text-xs text-muted">bar = predicted, marker = observed</span>
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 space-y-2">
              <Expandable summary="Definitions and limitations">
                <dl className="space-y-3">
                  <Definition term="Expected calibration error">{c.metrics.ece_definition}</Definition>
                  <Definition term="Baseline">{c.baseline}</Definition>
                </dl>
                <ul className="mt-3 space-y-1">{c.limitations.map((l) => <li key={l}>• {l}</li>)}</ul>
              </Expandable>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted">Not evaluated: no stored churn-calibration run.</p>
        )}
      </Panel>

      <Panel title="Forecast intervals on held-out periods">
        {data.forecast_uncertainty.length === 0 ? (
          <p className="text-sm text-muted">Not evaluated: no model comparison has been run.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <caption className="sr-only">Forecast interval coverage on the test period</caption>
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">Dataset</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Nominal</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Actually inside</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Test points</th>
                  <th scope="col" className="py-1 font-medium">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {data.forecast_uncertainty.map((u) => (
                  <tr key={u.run_id} className="border-t border-border align-top">
                    <th scope="row" className="py-1.5 pr-3 text-left font-medium text-foreground">{u.dataset}</th>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{Math.round(u.nominal_coverage * 100)}%</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{(u.empirical_coverage * 100).toFixed(0)}%</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{u.test_points}</td>
                    <td className="py-1.5"><EvidenceTypeBadge type={u.provenance === "real" ? "measured" : "measured_on_synthetic_data"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="mt-2 text-xs text-muted">Split-conformal intervals from out-of-fold residuals. With few test points, coverage differs from nominal by chance.</p>
      </Panel>

      <Panel title="Decision risk score (Risk Manager)" right={<EvidenceTypeBadge type="not_evaluated" />}>
        <p className="text-sm text-foreground">
          Calibration is <strong>not evaluated</strong>: the score is a heuristic, not a probability, and {drs.recorded_real_outcomes === 0 ? "no real outcomes have been recorded" : `${drs.recorded_real_outcomes} outcome(s) are recorded, too few`}.
          A low error elsewhere is not evidence that this score is safe.
        </p>
        <ul className="mt-3 space-y-2">
          {drs.prerequisites.map((p) => (
            <li key={p.need} className="flex items-start gap-2 text-sm">
              <CheckStatusBadge status={p.met ? "passed" : "failed"} />
              <span className="text-muted">{p.need}{typeof p.observed === "number" ? ` (observed: ${p.observed})` : ""}</span>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-sm text-muted">Next step: {drs.next_step}</p>
      </Panel>

      <Panel title="Pre-registered risk-formula study" right={<EvidenceTypeBadge type="simulated" />}>
        <p className="text-sm text-muted">{data.synthetic_variant_study.note}</p>
        <p className="mt-2 text-sm font-medium text-foreground">{data.synthetic_variant_study.verdict}</p>
        <ul className="mt-2 grid gap-2 text-sm sm:grid-cols-3">
          {data.synthetic_variant_study.variants.map((v) => (
            <li key={v.variant} className="rounded-lg border border-border px-3 py-2">
              <span className="font-medium text-foreground">{v.variant}</span> — goal achievement {num(v.mean_goal_achievement, 3)}
              {v.verdict ? <span className="block text-xs text-muted">{v.verdict}</span> : null}
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
