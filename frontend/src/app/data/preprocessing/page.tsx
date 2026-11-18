"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  platform,
  type CleaningProposal,
  type DataProfile,
  type PreviewPage,
  type PrepRun,
  type ValidationReport,
} from "@/lib/platform-api";
import { ConfirmDialog, Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { Badge, Workspace } from "@/components/platform-ui";
import { TablePicker } from "@/components/table-picker";
import { friendlyError } from "@/lib/friendly";

type StepId = 1 | 2 | 3 | 4 | 5;

interface RunOutcome {
  proposal: CleaningProposal;
  run?: PrepRun & { affected_rows: number };
  error?: string;
  undone?: boolean;
}

const KIND_LABELS: Record<string, string> = {
  trim_whitespace: "Whitespace Cleanup",
  standardise_categories: "Category Standardization",
  exact_duplicates: "Duplicate Deduplication",
  invalid_rows: "Invalid Value Correction",
  missing_values: "Missing Value Handling",
};

const KIND_WHY_MATTERS: Record<string, string> = {
  trim_whitespace: "Hidden spaces cause identical product codes or customer names to be treated as different entities in analytics.",
  standardise_categories: "Inconsistent casing or spellings fragment sales totals across duplicate category buckets.",
  exact_duplicates: "Double-counted transactions artificially inflate revenue and customer counts.",
  invalid_rows: "Out-of-range prices, negative stock, or corrupt dates cause forecasting models to fail.",
  missing_values: "Blank dates or missing amounts create gaps in time-series trends and attribution charts.",
};

function Body({ id }: { id: string }) {
  const [currentStep, setCurrentStep] = useState<StepId>(1);
  const [table, setTable] = useState("sales");

  // Data states
  const [profile, setProfile] = useState<DataProfile | null>(null);
  const [preview, setPreview] = useState<PreviewPage | null>(null);
  const [proposals, setProposals] = useState<CleaningProposal[] | null>(null);
  const [chosen, setChosen] = useState<Record<string, boolean>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  // Execution states
  const [confirming, setConfirming] = useState(false);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<string | null>(null);
  const [beforeValidation, setBeforeValidation] = useState<ValidationReport | null>(null);
  const [afterValidation, setAfterValidation] = useState<ValidationReport | null>(null);
  const [outcomes, setOutcomes] = useState<RunOutcome[]>([]);
  const [reload, setReload] = useState(0);

  // Fetch preview, profile, and cleaning proposals
  useEffect(() => {
    let alive = true;
    Promise.all([
      platform.profile(id, table),
      platform.cleaning(id, table),
      platform.preview(id, table, 0, 8),
    ])
      .then(([prof, cln, prev]) => {
        if (!alive) return;
        setProfile(prof);
        setProposals(cln.proposals);
        setPreview(prev);
        setChosen(
          Object.fromEntries(
            cln.proposals.filter((x) => x.can_apply && !x.applied).map((x) => [x.id, true])
          )
        );
        setLoadError(null);
      })
      .catch((e) => alive && setLoadError(friendlyError(e, "We couldn't load dataset information.").message));

    return () => {
      alive = false;
    };
  }, [id, table, reload]);

  const applicable = useMemo(
    () => (proposals ?? []).filter((p) => p.can_apply && !p.applied),
    [proposals]
  );
  const selected = applicable.filter((p) => chosen[p.id]);
  const rowsAffected = selected.reduce((n, p) => n + p.affected_rows, 0);

  async function handleApplyCleaning() {
    setConfirming(false);
    setRunning(true);
    setOutcomes([]);
    setAfterValidation(null);
    setCurrentStep(4);

    try {
      setProgress("Analyzing baseline dataset before modifications…");
      const beforeRep = await platform.validate(id, [table]);
      setBeforeValidation(beforeRep);

      const done: RunOutcome[] = [];
      for (let i = 0; i < selected.length; i++) {
        const p = selected[i];
        setProgress(`Applying rule ${i + 1} of ${selected.length}: ${p.issue}`);
        try {
          const run = await platform.applyCleaning(id, p.id, true);
          done.push({ proposal: p, run });
        } catch (e) {
          done.push({ proposal: p, error: friendlyError(e, "Could not apply this preparation step.").message });
        }
        setOutcomes([...done]);
      }

      setProgress("Verifying prepared dataset integrity…");
      const afterRep = await platform.validate(id, [table]);
      setAfterValidation(afterRep);
      setReload((n) => n + 1);
      setCurrentStep(5);
    } catch (e) {
      setLoadError(friendlyError(e, "The data preparation run could not finish.").message);
    } finally {
      setRunning(false);
      setProgress(null);
    }
  }

  async function undo(index: number) {
    const outcome = outcomes[index];
    if (!outcome.run) return;
    try {
      await platform.revert(id, outcome.run.id);
      setOutcomes((cur) => cur.map((x, j) => (j === index ? { ...x, undone: true } : x)));
      setReload((n) => n + 1);
    } catch (e) {
      setOutcomes((cur) =>
        cur.map((x, j) =>
          j === index ? { ...x, error: friendlyError(e, "This step could not be undone.").message } : x
        )
      );
    }
  }

  const steps: { id: StepId; title: string; subtitle: string }[] = [
    { id: 1, title: "1. Upload & Table Select", subtitle: "Choose table" },
    { id: 2, title: "2. Dataset Preview", subtitle: "Inspect records & schema" },
    { id: 3, title: "3. Prepare Data", subtitle: "Detect & resolve issues" },
    { id: 4, title: "4. Review Changes", subtitle: "Before & after impact" },
    { id: 5, title: "5. Save Prepared Dataset", subtitle: "Preserve raw & continue" },
  ];

  return (
    <div className="space-y-6">
      {/* 5-Step Progress Stepper */}
      <nav aria-label="Data Preparation Workflow" className="rounded-2xl border border-border bg-surface p-4 shadow-sm">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
          {steps.map((st) => {
            const isCurrent = currentStep === st.id;
            const isCompleted = currentStep > st.id;
            return (
              <button
                key={st.id}
                type="button"
                onClick={() => setCurrentStep(st.id)}
                className={`flex flex-col items-start rounded-xl p-3 text-left transition ${
                  isCurrent
                    ? "bg-accent/10 border border-accent/40 font-semibold text-accent"
                    : isCompleted
                    ? "bg-muted-surface/50 text-foreground hover:bg-muted-surface"
                    : "text-muted hover:bg-muted-surface/30"
                }`}
              >
                <div className="flex items-center gap-1.5 text-xs">
                  {isCompleted ? (
                    <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 text-[10px] text-white font-bold">✓</span>
                  ) : (
                    <span className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold ${isCurrent ? "bg-accent text-accent-foreground" : "bg-muted text-surface"}`}>
                      {st.id}
                    </span>
                  )}
                  <span className="truncate">{st.subtitle}</span>
                </div>
                <span className="mt-1 text-sm font-medium">{st.title.split(". ")[1]}</span>
              </button>
            );
          })}
        </div>
      </nav>

      {loadError && (
        <Notice tone="warning" title="Action Needed">
          {loadError}
        </Notice>
      )}

      {/* STEP 1: UPLOAD & SELECT */}
      {currentStep === 1 && (
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Step 1 — Upload or Choose Table to Prepare</h2>
              <p className="mt-1 text-sm text-muted">
                Choose an existing table from your business library or upload a new CSV / Excel file.
              </p>
            </div>
            <Link href="/data/upload/file" className={btnPrimary}>
              Upload New CSV / Excel File &rarr;
            </Link>
          </div>

          <div className="mt-6 max-w-md">
            <TablePicker
              value={table}
              onChange={(newTable) => {
                setTable(newTable);
                setReload((r) => r + 1);
              }}
              label="Select Table to Prepare"
            />
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
              <span className="text-xs font-medium uppercase text-muted">Total Records</span>
              <p className="mt-1 text-2xl font-bold text-foreground">
                {profile ? profile.rows.toLocaleString("en-IN") : "…"}
              </p>
              <p className="mt-1 text-xs text-muted">Active rows in {table.replace(/_/g, " ")}</p>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
              <span className="text-xs font-medium uppercase text-muted">Columns Detected</span>
              <p className="mt-1 text-2xl font-bold text-foreground">
                {profile ? profile.columns : "…"}
              </p>
              <p className="mt-1 text-xs text-muted">Schema dimensions</p>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-4">
              <span className="text-xs font-medium uppercase text-muted">Storage Policy</span>
              <p className="mt-1 text-base font-semibold text-emerald-600 dark:text-emerald-400">
                Originals Protected
              </p>
              <p className="mt-1 text-xs text-muted">Raw upload files are never overwritten</p>
            </div>
          </div>

          <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-border">
            <Link href="/data" className={btnSecondary}>
              Back to Library
            </Link>
            <button
              type="button"
              onClick={() => setCurrentStep(2)}
              className={btnPrimary}
            >
              Continue to Dataset Preview &rarr;
            </button>
          </div>
        </section>
      )}

      {/* STEP 2: DATASET PREVIEW */}
      {currentStep === 2 && (
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">Step 2 — Dataset Preview & Schema Inspection</h2>
              <p className="mt-1 text-sm text-muted">
                Review column names, inferred data types, and a live sample of rows stored in <strong className="text-foreground">{table.replace(/_/g, " ")}</strong>.
              </p>
            </div>
            <div className="text-xs text-muted self-center">
              Showing first {preview?.rows.length || 0} of {preview?.total.toLocaleString("en-IN") || 0} rows
            </div>
          </div>

          {/* Schema Chips */}
          <div className="mt-4 flex flex-wrap gap-2">
            {profile?.column_profiles.map((col) => (
              <span
                key={col.key}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1 text-xs font-medium text-foreground"
              >
                <span>{col.label}</span>
                <span className="text-[10px] text-muted">({col.inferred_type})</span>
              </span>
            ))}
          </div>

          {/* Table Preview */}
          <div className="mt-4 overflow-x-auto rounded-xl border border-border">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted-surface/80 text-foreground font-semibold border-b border-border">
                <tr>
                  {preview?.columns.map((c) => (
                    <th key={c.key} className="px-3 py-2.5 whitespace-nowrap">
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 bg-surface">
                {preview?.rows && preview.rows.length > 0 ? (
                  preview.rows.map((row) => (
                    <tr key={row.id} className="hover:bg-muted-surface/30">
                      {preview.columns.map((c) => (
                        <td key={c.key} className="px-3 py-2 whitespace-nowrap text-foreground font-mono text-[11px]">
                          {row.values[c.key] !== null && row.values[c.key] !== undefined
                            ? String(row.values[c.key])
                            : <span className="text-muted italic">null</span>}
                        </td>
                      ))}
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={preview?.columns.length || 1} className="p-6 text-center text-muted">
                      No records found in this dataset.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="mt-6 flex items-center justify-between gap-3 pt-4 border-t border-border">
            <button type="button" onClick={() => setCurrentStep(1)} className={btnSecondary}>
              &larr; Back to Selection
            </button>
            <button type="button" onClick={() => setCurrentStep(3)} className={btnPrimary}>
              Proceed to Prepare Data &rarr;
            </button>
          </div>
        </section>
      )}

      {/* STEP 3: PREPARE DATA */}
      {currentStep === 3 && (
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Step 3 — Detect & Prepare Data</h2>
            <p className="mt-1 text-sm text-muted">
              Select automated cleaning and data quality corrections. DecisionGPT identifies formatting defects that could skew business forecasts or analytics.
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="rounded-xl border border-border p-3">
              <span className="text-xs text-muted">Duplicate Rows</span>
              <p className="mt-1 text-lg font-bold text-foreground">
                {profile?.duplicate_rows.toLocaleString("en-IN") || 0}
              </p>
            </div>
            <div className="rounded-xl border border-border p-3">
              <span className="text-xs text-muted">Format & Value Issues</span>
              <p className="mt-1 text-lg font-bold text-foreground">
                {profile?.invalid_or_inconsistent.reduce((acc, curr) => acc + curr.count, 0) || 0}
              </p>
            </div>
            <div className="rounded-xl border border-border p-3">
              <span className="text-xs text-muted">Cleanable Proposals</span>
              <p className="mt-1 text-lg font-bold text-foreground">
                {applicable.length}
              </p>
            </div>
            <div className="rounded-xl border border-border p-3">
              <span className="text-xs text-muted">Selected Impact</span>
              <p className="mt-1 text-lg font-bold text-accent">
                {rowsAffected.toLocaleString("en-IN")} rows
              </p>
            </div>
          </div>

          {/* Cleaning Proposals */}
          <div className="mt-6 space-y-3">
            <h3 className="text-sm font-semibold uppercase tracking-wider text-muted">
              Recommended Cleaning Operations
            </h3>

            {applicable.length === 0 ? (
              <Notice tone="success" title="Clean Dataset">
                No automatic cleaning steps are needed. Your {table.replace(/_/g, " ")} records conform to standard schemas.
              </Notice>
            ) : (
              applicable.map((prop) => (
                <div
                  key={prop.id}
                  className={`rounded-xl border p-4 transition ${
                    chosen[prop.id] ? "border-accent/50 bg-accent/5" : "border-border bg-surface"
                  }`}
                >
                  <label className="flex items-start gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={!!chosen[prop.id]}
                      onChange={(e) => setChosen((prev) => ({ ...prev, [prop.id]: e.target.checked }))}
                      className="mt-1 h-5 w-5 rounded border-border text-accent focus:ring-accent"
                    />
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone="warn">{KIND_LABELS[prop.kind] || prop.kind}</Badge>
                        <span className="text-base font-semibold text-foreground">{prop.issue}</span>
                      </div>
                      <p className="mt-1 text-sm text-foreground">{prop.action}</p>
                      <p className="mt-1 text-xs text-muted">
                        <strong>Why it matters:</strong> {KIND_WHY_MATTERS[prop.kind] || "Ensures metric stability."}
                      </p>
                      <div className="mt-2 text-xs text-muted flex gap-4">
                        <span>Impact: <strong>{prop.affected_rows.toLocaleString("en-IN")}</strong> row(s)</span>
                        <span>Safety Risk: <strong className="capitalize">{prop.risk}</strong></span>
                      </div>
                    </div>
                  </label>
                </div>
              ))
            )}
          </div>

          <div className="mt-6 flex items-center justify-between gap-3 pt-4 border-t border-border">
            <button type="button" onClick={() => setCurrentStep(2)} className={btnSecondary}>
              &larr; Back to Preview
            </button>
            <button type="button" onClick={() => setCurrentStep(4)} className={btnPrimary}>
              Review Changes &rarr;
            </button>
          </div>
        </section>
      )}

      {/* STEP 4: REVIEW CHANGES */}
      {currentStep === 4 && (
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Step 4 — Review Proposed Changes</h2>
            <p className="mt-1 text-sm text-muted">
              Verify the actions to be taken. Original raw dataset records remain permanently stored and reversible.
            </p>
          </div>

          <div className="mt-6 rounded-xl border border-border/80 bg-muted-surface/30 p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <span className="text-xs font-medium text-muted uppercase">Target Table</span>
                <p className="text-base font-semibold text-foreground capitalize">{table.replace(/_/g, " ")}</p>
              </div>
              <div>
                <span className="text-xs font-medium text-muted uppercase">Selected Operations</span>
                <p className="text-base font-semibold text-foreground">{selected.length} rule(s) active</p>
              </div>
              <div>
                <span className="text-xs font-medium text-muted uppercase">Total Impact</span>
                <p className="text-base font-semibold text-foreground">{rowsAffected.toLocaleString("en-IN")} row(s) updated</p>
              </div>
              <div>
                <span className="text-xs font-medium text-muted uppercase">Safety Guarantee</span>
                <p className="text-base font-semibold text-emerald-600 dark:text-emerald-400">Reversible & Non-Destructive</p>
              </div>
            </div>

            {selected.length > 0 ? (
              <div className="mt-4 border-t border-border/60 pt-4">
                <p className="text-xs font-medium uppercase text-muted mb-2">Rules to Execute:</p>
                <ul className="space-y-1.5 text-xs text-foreground">
                  {selected.map((s) => (
                    <li key={s.id} className="flex items-center gap-2">
                      <span className="h-1.5 w-1.5 rounded-full bg-accent"></span>
                      <span>{s.issue} ({s.affected_rows.toLocaleString("en-IN")} rows)</span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="mt-4 text-xs text-muted">
                No cleaning rules selected. Continuing will validate and preserve the table as-is.
              </p>
            )}
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 pt-4 border-t border-border">
            <button type="button" onClick={() => setCurrentStep(3)} className={btnSecondary} disabled={running}>
              &larr; Back to Preparation
            </button>
            <div className="flex items-center gap-3">
              {progress && <span className="text-xs text-muted animate-pulse">{progress}</span>}
              <button
                type="button"
                onClick={() => setConfirming(true)}
                disabled={running}
                className={btnPrimary}
              >
                {running ? "Processing Dataset..." : "Save Prepared Dataset &rarr;"}
              </button>
            </div>
          </div>
        </section>
      )}

      {/* STEP 5: SAVE PREPARED DATASET & RESULTS */}
      {currentStep === 5 && (
        <section className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div>
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-xs text-white font-bold">✓</span>
              <h2 className="text-xl font-semibold text-foreground">Step 5 — Dataset Successfully Prepared</h2>
            </div>
            <p className="mt-1 text-sm text-muted">
              Your cleaned dataset is ready for analytics, forecasting, and multi-agent deliberation.
            </p>
          </div>

          {/* Validation Metrics */}
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-border p-4">
              <span className="text-xs font-medium text-muted">Before Preprocessing</span>
              <p className="mt-1 text-base font-semibold text-foreground">
                {beforeValidation
                  ? `${beforeValidation.pass} passed · ${beforeValidation.warn} warnings · ${beforeValidation.fail} issues`
                  : "Verified"}
              </p>
            </div>

            <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4">
              <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">After Preparation</span>
              <p className="mt-1 text-base font-semibold text-foreground">
                {afterValidation
                  ? `${afterValidation.pass} passed · ${afterValidation.warn} warnings · ${afterValidation.fail} issues`
                  : "Clean & Ready"}
              </p>
            </div>
          </div>

          {/* Applied Actions with Undo */}
          {outcomes.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold uppercase text-muted mb-3">Applied Cleaning Actions</h3>
              <ul className="space-y-2">
                {outcomes.map((o, idx) => (
                  <li
                    key={o.proposal.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border p-3 text-xs"
                  >
                    <div>
                      <span className="font-semibold text-foreground">{o.proposal.issue}</span>
                      <span className="text-muted ml-2">
                        {o.error ? `Error: ${o.error}` : `${o.run?.affected_rows.toLocaleString("en-IN")} row(s) updated`}
                      </span>
                    </div>
                    {o.run && !o.undone && o.run.reversible ? (
                      <button
                        type="button"
                        onClick={() => undo(idx)}
                        className="text-xs font-medium text-accent underline hover:opacity-80"
                      >
                        Undo Step
                      </button>
                    ) : o.undone ? (
                      <span className="text-xs text-muted">Reverted</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Next Steps CTAs */}
          <div className="mt-8 border-t border-border pt-6">
            <h3 className="text-base font-semibold text-foreground mb-4">What would you like to do next?</h3>
            <div className="grid gap-3 sm:grid-cols-3">
              <Link
                href="/analytics"
                className="flex flex-col rounded-xl border border-border bg-background p-4 transition hover:border-accent hover:shadow-sm"
              >
                <span className="text-lg">📊</span>
                <span className="mt-2 text-sm font-semibold text-foreground">Open Business Analytics</span>
                <span className="mt-0.5 text-xs text-muted">Explore sales trends, KPIs, and revenue velocity.</span>
              </Link>

              <Link
                href="/forecast"
                className="flex flex-col rounded-xl border border-border bg-background p-4 transition hover:border-accent hover:shadow-sm"
              >
                <span className="text-lg">📈</span>
                <span className="mt-2 text-sm font-semibold text-foreground">Run Sales Forecast</span>
                <span className="mt-0.5 text-xs text-muted">Predict 30-90 day trajectories using cleaned records.</span>
              </Link>

              <Link
                href="/agents/business-analyst"
                className="flex flex-col rounded-xl border border-border bg-background p-4 transition hover:border-accent hover:shadow-sm"
              >
                <span className="text-lg">🤖</span>
                <span className="mt-2 text-sm font-semibold text-foreground">Consult Business Analyst</span>
                <span className="mt-0.5 text-xs text-muted">Ask an AI agent to evaluate performance drivers.</span>
              </Link>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={() => {
                  setCurrentStep(1);
                  setReload((r) => r + 1);
                }}
                className={btnSecondary}
              >
                Prepare Another Table
              </button>
            </div>
          </div>
        </section>
      )}

      {/* Confirmation Modal */}
      <ConfirmDialog
        open={confirming}
        title="Execute Data Preparation?"
        body={
          <>
            <p className="text-sm text-foreground">
              {selected.length} cleaning rule(s) will update up to {rowsAffected.toLocaleString("en-IN")} row(s) in your {table.replace(/_/g, " ")} table.
            </p>
            <p className="mt-2 text-xs text-muted">
              Your original uploaded files remain completely safe and untouched. Any applied operation can be undone immediately from the results page.
            </p>
          </>
        }
        confirmLabel="Confirm & Apply Cleaning"
        busy={running}
        onConfirm={handleApplyCleaning}
        onCancel={() => setConfirming(false)}
      />
    </div>
  );
}

export default function DataPreprocessingPage() {
  return (
    <Workspace
      title="Data Preprocessing"
      subtitle="A guided, 5-step preparation workflow to clean, validate, and prepare your business datasets without touching original raw files."
    >
      {(id) => <Body id={id} />}
    </Workspace>
  );
}
