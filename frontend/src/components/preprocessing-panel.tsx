"use client";

import { useEffect, useState } from "react";
import { CheckStatusBadge } from "@/components/research-evidence";
import { researchApi, type PreprocessPlan, type PreprocessRun } from "@/lib/research-api";

/**
 * One-action preprocessing for a research dataset version.
 * Flow: inspect schema and quality -> review the proposed steps -> Run preprocessing -> before/after summary -> download.
 * The raw dataset is never changed; output is a new versioned artifact.
 */
export function PreprocessingPanel({ versionId }: { versionId: string }) {
  const [plan, setPlan] = useState<PreprocessPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PreprocessRun | null>(null);

  function applyPlan(p: PreprocessPlan) {
    setPlan(p);
    setSelected(Object.fromEntries(p.steps.map((s) => [s.id, s.default_enabled])));
    setError(null);
  }

  useEffect(() => {
    let alive = true;
    researchApi
      .preprocessingPlan(versionId)
      .then((p) => alive && applyPlan(p))
      .catch((e) => alive && setError(e instanceof Error ? e.message : "Could not load the preprocessing plan."));
    return () => {
      alive = false;
    };
  }, [versionId]);

  async function run() {
    setRunning(true);
    setResult(null);
    try {
      const steps = plan?.steps.filter((s) => selected[s.id]).map((s) => s.id) ?? [];
      const r = await researchApi.runPreprocessing(versionId, steps);
      setResult(r);
      applyPlan(await researchApi.preprocessingPlan(versionId));
    } catch (e) {
      setResult({ status: "failed", run_id: "", source_version_id: versionId, created_utc: "", error: e instanceof Error ? e.message : "The run failed.", raw_dataset_modified: false });
    } finally {
      setRunning(false);
    }
  }

  async function download(runId: string) {
    const blob = await researchApi.downloadPreprocessed(versionId, runId);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${runId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (error) return <p role="alert" className="text-sm text-danger">{error}</p>;
  if (!plan) return <p className="text-sm text-muted">Loading the preprocessing plan…</p>;

  const missing = plan.schema.filter((c) => c.missing > 0);
  return (
    <div className="space-y-4 text-sm">
      <section aria-label="Current schema and quality">
        <h4 className="font-semibold text-foreground">1. Current data</h4>
        <p className="mt-1 text-muted">
          {plan.rows.toLocaleString("en-IN")} rows × {plan.columns} columns. Identical rows: {plan.duplicate_rows}. Columns with missing values:{" "}
          {missing.length ? missing.map((c) => `${c.name} (${c.missing})`).join(", ") : "none"}.
        </p>
        <details className="mt-1">
          <summary className="cursor-pointer text-accent">Schema</summary>
          <p className="mt-1 text-xs text-muted">{plan.schema.map((c) => `${c.name}: ${c.dtype}`).join(" · ")}</p>
        </details>
      </section>

      <section aria-label="Proposed steps">
        <h4 className="font-semibold text-foreground">2. Proposed steps</h4>
        <p className="mt-1 text-xs text-muted">Steps that do not apply to this dataset are not offered. Nothing is deleted, imputed or clipped; issues are flagged in new columns.</p>
        <ul className="mt-2 space-y-2">
          {plan.steps.map((s) => (
            <li key={s.id} className="rounded-lg border border-border p-2">
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={!!selected[s.id]}
                  disabled={!s.applies}
                  onChange={(e) => setSelected((cur) => ({ ...cur, [s.id]: e.target.checked }))}
                />
                <span>
                  <span className="font-medium text-foreground">{s.title}</span>{" "}
                  {s.applies ? null : <span className="text-xs text-muted">— not applicable</span>}
                  <span className="block text-xs text-muted">{s.detail}. {s.rationale}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Run">
        <h4 className="font-semibold text-foreground">3. Run</h4>
        <button
          type="button"
          onClick={run}
          disabled={running}
          className="mt-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-foreground disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        >
          {running ? "Running…" : "Run preprocessing"}
        </button>
        {result ? (
          result.status === "completed" ? (
            <div role="status" className="mt-3 rounded-lg bg-success-soft p-3">
              <p className="flex items-center gap-2 font-medium text-foreground"><CheckStatusBadge status="passed" /> Completed — {result.run_id}</p>
              <p className="mt-1 text-muted">
                Before: {result.rows_in?.toLocaleString("en-IN")} rows × {result.columns_in} columns. After: {result.rows_out?.toLocaleString("en-IN")} rows × {result.columns_out} columns.
                Rows removed: {result.rows_removed}. Source dataset modified: {result.raw_dataset_modified ? "yes" : "no"}.
              </p>
              <ul className="mt-2 space-y-1 text-xs text-muted">
                {(result.steps ?? []).filter((x) => x.status === "applied").map((x) => (
                  <li key={x.id}>• <span className="text-foreground">{x.title}:</span> {x.detail}</li>
                ))}
              </ul>
              <button type="button" onClick={() => download(result.run_id)} className="mt-2 text-accent underline underline-offset-4">
                Download processed CSV
              </button>
            </div>
          ) : (
            <p role="alert" className="mt-3 rounded-lg bg-danger-soft p-3 text-danger">
              <CheckStatusBadge status="failed" /> {result.error ?? "The run did not complete."}
            </p>
          )
        ) : null}
      </section>

      <section aria-label="History">
        <h4 className="font-semibold text-foreground">4. History</h4>
        {plan.runs.length === 0 ? (
          <p className="mt-1 text-muted">No preprocessing run yet for this version.</p>
        ) : (
          <ul className="mt-1 space-y-1 text-xs text-muted">
            {plan.runs.map((r) => (
              <li key={r.run_id} className="flex flex-wrap items-center gap-2">
                <CheckStatusBadge status={r.status === "completed" ? "passed" : "failed"} />
                <span className="font-mono">{r.run_id}</span>
                <span>{r.rows_in ?? "?"} → {r.rows_out ?? "?"} rows</span>
                {r.status === "completed" ? (
                  <button type="button" onClick={() => download(r.run_id)} className="text-accent underline underline-offset-4">Download</button>
                ) : (
                  <span>{r.error}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
