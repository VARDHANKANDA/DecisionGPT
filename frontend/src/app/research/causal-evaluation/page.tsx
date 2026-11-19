"use client";

import { useEffect, useState } from "react";
import { EvalEmptyState, Expandable, PageIntro, Panel } from "@/components/research-ui";
import { CheckStatusBadge, Definition, EvidenceTypeBadge, num } from "@/components/research-evidence";
import { researchApi, type CausalAssessment } from "@/lib/research-api";

export default function CausalEvaluationPage() {
  const [data, setData] = useState<CausalAssessment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    researchApi
      .causalAssessment()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the causal assessment."));
  }, []);

  if (error) return <EvalEmptyState message={error} />;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;

  const pairs = data.assessment.pairs;
  const unsupported = pairs.filter((p) => p.status === "unsupported").length;
  const sim = data.known_truth_simulation?.known_truth_simulation;
  const ge = data.graph_evidence;
  return (
    <div className="space-y-6">
      <PageIntro
        title="Causal evaluation"
        subtitle="Can the available data support a claim that one thing caused another? A cause-and-effect number is only produced where the data make it identifiable."
      />

      <Panel title="In one sentence">
        <p className="text-sm text-foreground">
          {unsupported} of {pairs.length} candidate treatment → outcome pairs cannot be causally evaluated with the registered data. For these, no effect number is shown —
          marketing and sales moving together is not evidence that marketing caused the sales.
        </p>
      </Panel>

      <Panel title="Correlation, prediction, simulation, causal inference">
        <dl className="grid gap-3 sm:grid-cols-2">
          {data.assessment.distinguish.map((d) => (
            <Definition key={d.term} term={d.term}>{d.meaning}</Definition>
          ))}
        </dl>
      </Panel>

      <Panel title="Can each effect be identified from the data?" right={<EvidenceTypeBadge type="measured" />}>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <caption className="sr-only">Identification assessment per treatment and outcome pair</caption>
            <thead className="text-left text-xs text-muted">
              <tr>
                <th scope="col" className="py-1 pr-3 font-medium">Treatment → outcome</th>
                <th scope="col" className="py-1 pr-3 font-medium">Status</th>
                <th scope="col" className="py-1 font-medium">Why, and what would be needed</th>
              </tr>
            </thead>
            <tbody>
              {pairs.map((p) => (
                <tr key={p.pair} className="border-t border-border align-top">
                  <th scope="row" className="py-2 pr-3 text-left font-medium text-foreground">{p.pair}</th>
                  <td className="py-2 pr-3">
                    {p.status === "unsupported" ? <CheckStatusBadge status="failed" /> : <CheckStatusBadge status="passed" />}
                    <span className="mt-1 block text-xs text-muted font-medium">{p.status === "unsupported" ? "Unsupported" : (p.status_label || "Identified")}</span>
                  </td>
                  <td className="py-2 text-muted">
                    {p.reasons.length ? <ul className="space-y-0.5">{p.reasons.map((r) => <li key={r}>• {r}</li>)}</ul> : <span>{p.note}</span>}
                    {p.needs.length ? <p className="mt-1 text-xs"><span className="font-medium text-foreground">Needed:</span> {p.needs.join("; ")}</p> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Known-truth check of the estimator" right={<EvidenceTypeBadge type="simulated" />}>
        {sim ? (
          <>
            <p className="text-sm text-muted">
              In the project&apos;s synthetic data, promotion days are assigned by an independent coin flip, so their effect is identified. The generator multiplies demand by a documented
              factor, which lets the estimator be checked against the truth. <strong className="text-foreground">This validates the method; it says nothing about any real business.</strong>
            </p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
              <div><dt className="text-muted">Estimated effect of a promotion day</dt><dd className="font-semibold text-foreground">{num(sim.estimate_pct, 1, "%")}</dd><dd className="text-xs text-muted">95% interval {num(sim.ci95_pct[0], 1, "%")} to {num(sim.ci95_pct[1], 1, "%")}</dd></div>
              <div><dt className="text-muted">Documented truth</dt><dd className="font-semibold text-foreground">{num(sim.documented_truth_pct, 0, "%")}</dd><dd className="text-xs text-muted">{sim.truth_inside_ci ? "inside the interval" : "just outside the interval: a small downward bias"}</dd></div>
              <div><dt className="text-muted">Sample</dt><dd className="font-semibold text-foreground">{sim.n_rows.toLocaleString("en-IN")} series-days</dd><dd className="text-xs text-muted">{sim.n_series} series, {sim.n_treated_days.toLocaleString("en-IN")} promotion days</dd></div>
            </dl>
            <div className="mt-4">
              <Expandable summary="Estimand, estimator and balance checks">
                <dl className="space-y-3">
                  <Definition term="Estimand (fixed before fitting)">{sim.estimand}</Definition>
                  <Definition term="Estimator">{sim.estimator}. {sim.bootstrap_draws} bootstrap draws.</Definition>
                  <Definition term="Balance (standardised mean differences between promotion and non-promotion days)">
                    {Object.entries(sim.balance_standardised_mean_differences).map(([k, v]) => `${k}: ${v.toFixed(3)}`).join("; ")}
                  </Definition>
                  <Definition term="Reading">{sim.reading}</Definition>
                </dl>
              </Expandable>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted">Not evaluated: the known-truth simulation has not been run.</p>
        )}
      </Panel>

      <Panel title="Causal graph evidence in the product" right={<EvidenceTypeBadge type="estimated" />}>
        <p className="text-sm text-muted">
          Edges in business causal graphs are graded by evidence. {ge.overview.total_graph_versions} graph version(s) exist for {ge.overview.businesses_with_a_graph} business(es). Edge counts by grade:
        </p>
        <ul className="mt-2 flex flex-wrap gap-2 text-sm">
          {Object.entries(ge.overview.evidence_counts_latest_per_business).map(([k, v]) => (
            <li key={k} className="rounded-full bg-muted-surface px-3 py-1">{k.replace(/_/g, " ")}: <strong>{v}</strong></li>
          ))}
        </ul>
        <p className="mt-2 text-sm text-foreground">
          Causally validated edges: <strong>{ge.overview.evidence_counts_latest_per_business.causally_validated ?? 0}</strong>. No edge has intervention evidence, so none is presented as a proven cause.
        </p>
        {ge.method_validation ? (
          <p className="mt-2 text-xs text-muted">
            Structure-recovery check on a synthetic series with a planted structure ({ge.method_validation.label}): precision {num(ge.method_validation.precision, 2)}, recall {num(ge.method_validation.recall, 2)}, F1 {num(ge.method_validation.f1, 2)}.
          </p>
        ) : null}
      </Panel>

      <Panel title="What would make causal claims possible">
        <ul className="space-y-1.5 text-sm text-muted">
          <li>• A recorded intervention with a known assignment rule (an A/B test, a staggered roll-out or a holdout group).</li>
          <li>• Outcome and treatment measured on the same units before and after, with pre-treatment covariates.</li>
          <li>• Enough variation and overlap: periods or units with and without the treatment under comparable conditions.</li>
        </ul>
      </Panel>
    </div>
  );
}
