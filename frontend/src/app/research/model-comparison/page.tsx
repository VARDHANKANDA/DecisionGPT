"use client";

import { useEffect, useState } from "react";
import { EvalEmptyState, PageIntro, Panel, Expandable } from "@/components/research-ui";
import { Bar, Definition, EvidenceTypeBadge, num, when } from "@/components/research-evidence";
import { researchApi, type ModelComparison, type ModelComparisonRun } from "@/lib/research-api";

const GLOSSARY = [
  ["MAE", "Mean absolute error: the average size of a miss, in the target's own unit. Lower is better."],
  ["RMSE", "Root mean squared error: like MAE but punishes large misses more. Lower is better."],
  ["R²", "Share of the variation in the test period explained. 1 is perfect; 0 is no better than predicting the test-period average; negative is worse than that. Undefined for very short or flat periods."],
  ["MAPE", "Average percentage miss. Shown only when the target is safely away from zero, otherwise suppressed because it would be misleading."],
  ["Change vs baseline", "RMSE of the model relative to the seasonal-naive baseline (same weekday last week). Negative means the model's error is smaller."],
  ["Paired interval", "A 95% bootstrap interval for the model's average error minus the baseline's. If it contains 0, the data do not show a reliable difference."],
];

function RunPanel({ run, catalogueName }: { run: ModelComparisonRun | null; catalogueName: string }) {
  if (!run) {
    return (
      <Panel title={catalogueName}>
        <p className="text-sm font-medium text-foreground">Not evaluated.</p>
        <p className="mt-1 text-sm text-muted">No comparison has been run on this dataset, so no figures are shown.</p>
      </Panel>
    );
  }
  const unit = run.dataset.unit;
  const keys = Object.keys(run.models);
  const maxRmse = Math.max(...keys.map((k) => run.models[k].test.rmse));
  const small = run.split.test.dates < 30;
  return (
    <Panel title={run.dataset.name} right={<EvidenceTypeBadge type={run.evidence_type} />}>
      <p className="text-sm text-muted">
        Target: {run.dataset.target}. One-day-ahead forecast. {run.n_usable_observations.toLocaleString("en-IN")} usable observations, {run.period.first} to {run.period.last}.
        Test period: {run.split.test.first} to {run.split.test.last} ({run.split.test.dates} dates, {run.split.test.rows.toLocaleString("en-IN")} rows), untouched until final scoring.
      </p>
      {small ? (
        <p role="note" className="mt-3 rounded-lg bg-warning-soft px-3 py-2 text-sm text-foreground">
          Only {run.split.test.dates} test dates: these errors are indicative, not precise.
        </p>
      ) : null}

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[640px] text-sm">
          <caption className="sr-only">Held-out test results per algorithm</caption>
          <thead className="text-left text-xs text-muted">
            <tr>
              <th scope="col" className="py-1 pr-3 font-medium">Algorithm</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">MAE ({unit})</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">RMSE</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">R²</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">MAPE</th>
              <th scope="col" className="py-1 pr-3 text-right font-medium">vs baseline</th>
              <th scope="col" className="py-1 font-medium">Role</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => {
              const m = run.models[k];
              const isBase = k === run.baseline.key;
              const isSel = k === run.selection.selected;
              return (
                <tr key={k} className="border-t border-border align-top">
                  <th scope="row" className="py-1.5 pr-3 text-left font-medium text-foreground">{m.label}</th>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{num(m.test.mae, 1)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">{num(m.test.rmse, 1)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums" title={m.test.r2_note ?? undefined}>{m.test.r2 === null ? "undefined" : num(m.test.r2, 2)}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums" title={m.test.mape_note ?? undefined}>{m.test.mape_pct === null ? "suppressed" : num(m.test.mape_pct, 1, "%")}</td>
                  <td className="py-1.5 pr-3 text-right tabular-nums">
                    {isBase ? "reference" : m.test.rmse_change_vs_baseline_pct === null || m.test.rmse_change_vs_baseline_pct === undefined ? "not available" : num(m.test.rmse_change_vs_baseline_pct, 1, "%")}
                  </td>
                  <td className="py-1.5 text-xs">
                    {isBase ? "Baseline" : isSel ? <strong>Selected by cross-validation</strong> : "Compared"}
                    {m.paired_vs_baseline && !isBase ? (
                      <span className="block text-muted">paired interval {num(m.paired_vs_baseline.ci95[0], 0)} to {num(m.paired_vs_baseline.ci95[1], 0)}</span>
                    ) : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-5 space-y-2">
        <p className="text-sm font-medium text-foreground">Test RMSE ({unit}; same unit and scale, lower is better)</p>
        {keys.map((k) => (
          <Bar key={k} value={run.models[k].test.rmse} max={maxRmse} label={run.models[k].label} />
        ))}
      </div>

      <div className="mt-5 rounded-xl border border-border p-3 text-sm">
        <p className="font-medium text-foreground">
          Selected: {run.selection.selected_label}{" "}
          <span className="font-normal text-muted">(chosen on cross-validated error in the training period; the test period was not used to choose)</span>
        </p>
        <p className="mt-1 text-muted">
          On the held-out test period its RMSE was {num(run.selection.test.rmse, 1)} versus {num(run.models[run.baseline.key].test.rmse, 1)} for the baseline:{" "}
          {run.selection.beats_baseline_on_test_rmse ? "lower than the baseline" : "not lower than the baseline"}. This is a descriptive comparison, not a claim of statistical superiority.
        </p>
        <p className="mt-1 text-muted">
          Forecast interval check ({Math.round(run.uncertainty.nominal_coverage * 100)}% nominal): {num(run.uncertainty.empirical_coverage_test * 100, 0, "%")} of {run.uncertainty.test_points.toLocaleString("en-IN")} test points fell inside.
        </p>
      </div>

      <div className="mt-4 space-y-2">
        <Expandable summary="Methodology and technical details">
          <dl className="space-y-3">
            <Definition term="Run">{run.run_id} — {when(run.created_utc)}</Definition>
            <Definition term="Source">{run.dataset.source}</Definition>
            <Definition term="Splits (chronological)">
              {Object.entries(run.split).map(([k, v]) => `${k}: ${v.first} to ${v.last} (${v.dates} dates)`).join("; ")}
            </Definition>
            <Definition term="Cross-validation">{run.cv.scheme}. Folds: {run.cv.folds.map((f) => `train ${f.train[0]}…${f.train[1]} → validate ${f.validate[0]}…${f.validate[1]}`).join(" | ")}</Definition>
            <Definition term="Features">{run.features.join(", ")}. Lags and rolling means use only earlier days.</Definition>
            <Definition term="Selection rule">{run.selection.rule}</Definition>
            <Definition term="Software and seed">
              {Object.entries(run.reproducibility).map(([k, v]) => `${k}: ${v}`).join("; ")}
            </Definition>
            <Definition term="Parameters (fixed, not tuned)">
              {keys.filter((k) => k !== run.baseline.key).map((k) => `${run.models[k].label}: ${JSON.stringify(run.models[k].params)}`).join(" · ")}
            </Definition>
          </dl>
        </Expandable>
        <Expandable summary="Limitations of this comparison">
          <ul className="space-y-1">
            {run.limitations.map((l) => (
              <li key={l}>• {l}</li>
            ))}
          </ul>
        </Expandable>
      </div>
    </Panel>
  );
}

export default function ModelComparisonPage() {
  const [data, setData] = useState<ModelComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const load = () =>
    researchApi
      .modelComparison()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the model comparison."));

  useEffect(() => {
    void load();
  }, []);

  async function rerun() {
    setRunning(true);
    setMessage(null);
    try {
      const r = await researchApi.runModelComparison();
      setMessage(Object.entries(r).map(([k, v]) => `${k}: ${v.status}${v.run_id ? ` (${v.run_id})` : ""}${v.reason ? ` — ${v.reason}` : ""}`).join("; "));
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "The run failed.");
    } finally {
      setRunning(false);
    }
  }

  if (error) return <EvalEmptyState message={error} />;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;

  return (
    <div className="space-y-6">
      <PageIntro
        title="Model comparison"
        subtitle="Five forecasting algorithms compared with identical features, a chronological split and a simple seasonal baseline. Each model is judged on a period it never saw."
      />
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={rerun}
          disabled={running}
          className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-foreground disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {running ? "Running… (about 1–2 minutes)" : "Re-run comparison"}
        </button>
        <p className="text-xs text-muted">Local and deterministic (seed 42); no AI provider is called. A new record is written; earlier runs are kept.</p>
      </div>
      {message ? <p role="status" className="rounded-lg bg-muted-surface px-3 py-2 text-sm text-foreground">{message}</p> : null}

      {Object.entries(data.datasets).map(([key, run]) => (
        <RunPanel key={key} run={run} catalogueName={data.dataset_catalogue[key]?.name ?? key} />
      ))}

      <Expandable summary="What the metrics mean">
        <dl className="space-y-3">
          {GLOSSARY.map(([t, d]) => (
            <Definition key={t} term={t}>{d}</Definition>
          ))}
        </dl>
      </Expandable>
    </div>
  );
}
