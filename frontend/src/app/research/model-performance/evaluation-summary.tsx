"use client";

import { Panel } from "@/components/research-ui";
import type { EvalMini, EvaluationStatus, EvaluationSummary, EvaluationSummaryRow } from "@/lib/research-api";

const STATUS_META: Record<EvaluationStatus, { glyph: string; label: string; cls: string }> = {
  evaluated: { glyph: "✓", label: "Evaluated", cls: "bg-success-soft text-success" },
  pending: { glyph: "○", label: "Pending", cls: "bg-muted-surface text-muted" },
  unavailable: { glyph: "–", label: "Unavailable", cls: "bg-warning-soft text-warning" },
  failed: { glyph: "✕", label: "Failed", cls: "bg-danger-soft text-danger" },
};

const SOURCE_TEXT: Record<string, string> = {
  recorded_at_training: "recorded at training",
  re_evaluated: "re-scored from the stored model",
  re_evaluation_attempted: "re-evaluation attempted",
};

/** A metric cell: the displayed value only when the evaluation produced one; otherwise a plain "Not available" (the reason is in the title and under the status). */
function Cell({ c, signed = false }: { c: EvalMini; signed?: boolean }) {
  if (c.status !== "available" || c.display === null) {
    return (
      <span className="text-muted" title={c.reason ?? undefined}>
        {c.kind === "not_applicable" ? "Not applicable" : "Not available"}
      </span>
    );
  }
  const positive = signed && typeof c.value === "number" && c.value > 0;
  const negative = signed && typeof c.value === "number" && c.value < 0;
  return <span className={positive ? "text-success" : negative ? "text-danger" : "text-foreground"}>{c.display}</span>;
}

export function StatusBadge({ status }: { status: EvaluationStatus }) {
  const m = STATUS_META[status] ?? STATUS_META.pending;
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ${m.cls}`} data-testid="evaluation-status">
      <span aria-hidden="true">{m.glyph}</span>
      {m.label}
    </span>
  );
}

function period(row: EvaluationSummaryRow): string {
  const w = row.test_window;
  return w && w[0] && w[1] ? `${w[0]} to ${w[1]}` : "not recorded";
}

export function EvaluationSummaryPanel({
  summary,
  busy,
  message,
  onRun,
  onRunPending,
}: {
  summary: EvaluationSummary;
  busy: string | null;
  message: string | null;
  onRun: (modelId: string) => void;
  onRunPending: () => void;
}) {
  const rows = summary.rows;
  const pending = rows.filter((r) => r.evaluation_status === "pending");
  return (
    <Panel
      title="Forecast accuracy on held-out test data"
      right={
        pending.length > 0 ? (
          <button
            type="button"
            className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted-surface disabled:opacity-50"
            disabled={busy !== null}
            onClick={onRunPending}
            title="Scores the stored models on their held-out test blocks. Trains nothing and calls no external service."
          >
            {busy === "all" ? "Evaluating…" : `Run evaluation for ${pending.length} pending model${pending.length === 1 ? "" : "s"}`}
          </button>
        ) : null
      }
    >
      <p className="mb-3 text-sm text-muted">{summary.basis}</p>
      <p className="mb-3 text-xs text-muted">
        Figures come only from the final test block of each model&apos;s own dataset, never from training or validation rows. Models trained on different datasets are not
        ranked against each other: their errors are in different volumes. This is accuracy on a research dataset, not on any business.
      </p>
      {message ? (
        <p role="status" className="mb-3 rounded-lg bg-muted-surface px-3 py-2 text-xs text-foreground">
          {message}
        </p>
      ) : null}
      {rows.length === 0 ? (
        <p className="text-sm text-muted">No forecasting models are registered, so there is nothing to evaluate. Train one in the Training Center.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm" aria-label="Forecast accuracy on held-out test data">
            <thead>
              <tr className="border-b border-border bg-muted-surface/50 text-left text-muted">
                {[
                  ["Model", "Registered model and version, with the dataset it was trained and scored on."],
                  ["Status", "Evaluated: a test-block result exists. Pending: not yet scored. Unavailable: the stored model or dataset is missing. Failed: verification failed, so no figure is shown."],
                  ["Forecast Accuracy (1 − WAPE)", "Established forecasting accuracy: 100 × (1 − WAPE). Higher is better. 100% means zero forecast error."],
                  ["WAPE", "Weighted absolute percentage error: sum of absolute errors ÷ sum of actual volume, as a percentage. Lower is better."],
                  ["MAE", "Mean absolute error in the units of the target (units per day). Lower is better."],
                  ["RMSE", "Root mean squared error in the units of the target; large misses count more. Lower is better."],
                  ["vs baseline", "100 × (baseline WAPE − model WAPE) ÷ baseline WAPE. Positive = lower error than the baseline on the same rows."],
                  ["Baseline", "The simple reference forecast scored on exactly the same rows."],
                  ["Test n", "Number of actual-vs-predicted pairs the metrics were computed on."],
                  ["Test period", "First and last date of the held-out test block."],
                  ["Horizon", "How far ahead each forecast looks."],
                  ["", ""],
                ].map(([h, tip]) => (
                  <th key={h || "action"} className="whitespace-nowrap px-3 py-2 font-medium" title={tip || undefined} scope="col">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const accVal =
                  r.forecast_accuracy && r.forecast_accuracy.status === "available"
                    ? r.forecast_accuracy
                    : r.wape.status === "available" && typeof r.wape.value === "number"
                    ? {
                        status: "available",
                        kind: "available",
                        value: r.wape.value <= 1.0 ? (1.0 - r.wape.value) * 100 : Math.max(0, 100 - r.wape.value),
                        display: `${(r.wape.value <= 1.0 ? (1.0 - r.wape.value) * 100 : Math.max(0, 100 - r.wape.value)).toFixed(2)}%`,
                        reason: null,
                      }
                    : r.wape;
                return (
                  <tr key={r.model_id} className="border-b border-border align-top last:border-0" data-testid={`eval-row-${r.model_name}-${r.version}`}>
                    <td className="whitespace-nowrap px-3 py-2 text-foreground">
                      <div className="font-medium">
                        {r.model_name} {r.version}
                      </div>
                      <div className="max-w-[14rem] truncate text-xs text-muted" title={r.dataset_version}>
                        {r.dataset_version}
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={r.evaluation_status} />
                      <div className="mt-1 max-w-[16rem] whitespace-normal text-xs text-muted">
                        {r.evaluation_status === "evaluated" ? SOURCE_TEXT[r.evaluation_kind ?? ""] ?? "" : r.evaluation_reason}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 font-bold text-emerald-600 dark:text-emerald-400">
                      <Cell c={accVal as EvalMini} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 font-medium">
                      <Cell c={r.wape} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <Cell c={r.mae} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <Cell c={r.rmse} />
                    </td>
                    <td className="whitespace-nowrap px-3 py-2">
                      <Cell c={r.wape_vs_baseline} signed />
                    </td>
                    <td className="px-3 py-2 text-foreground">
                      <div className="whitespace-nowrap">{r.baseline_name}</div>
                      {r.baseline_wape.status === "available" ? (
                        <div className="text-xs text-muted">
                          baseline WAPE {r.baseline_wape.display}
                          {typeof r.baseline_wape.value === "number" ? (
                            <span> · Acc {((r.baseline_wape.value <= 1.0 ? 1.0 - r.baseline_wape.value : (100 - r.baseline_wape.value) / 100) * 100).toFixed(2)}%</span>
                          ) : null}
                        </div>
                      ) : null}
                    </td>
                  <td className="whitespace-nowrap px-3 py-2">{r.evaluation_status === "evaluated" && r.n_eval !== null ? r.n_eval.toLocaleString("en-IN") : <span className="text-muted">Not available</span>}</td>
                  <td className="whitespace-nowrap px-3 py-2">{r.evaluation_status === "evaluated" ? period(r) : <span className="text-muted">Not available</span>}</td>
                  <td className="max-w-[12rem] px-3 py-2 text-xs text-foreground">{r.horizon}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    {r.can_run ? (
                      <button
                        type="button"
                        className="rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted-surface disabled:opacity-50"
                        disabled={busy !== null}
                        onClick={() => onRun(r.model_id)}
                        aria-label={`Run evaluation for ${r.model_name} ${r.version}`}
                      >
                        {busy === r.model_id ? "Evaluating…" : r.evaluation_status === "pending" ? "Run evaluation" : "Run again"}
                      </button>
                    ) : null}
                  </td>
                </tr>
              );
            })}
            </tbody>
          </table>
        </div>
      )}
      {rows.some((r) => r.evaluation_kind === "re_evaluated") ? (
        <p className="mt-3 text-xs text-muted">
          &ldquo;Re-scored from the stored model&rdquo;: the stored model was scored again on the held-out test block rebuilt with the same cleaning, features and
          chronological split as training. The result is shown only because the recomputed MAE, RMSE and MAPE reproduced the values recorded at training.
        </p>
      ) : null}
      {summary.definitions.length > 0 ? (
        <div className="mt-5">
          <h3 className="mb-2 text-sm font-semibold text-foreground">What the figures mean</h3>
          <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
            {summary.definitions.map((d) => (
              <div key={d.key}>
                <dt className="font-medium text-foreground">
                  {d.abbr} — {d.name}
                </dt>
                <dd className="text-muted">
                  {d.definition} {d.direction_text}. {d.caveat ?? ""}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ) : null}
    </Panel>
  );
}
