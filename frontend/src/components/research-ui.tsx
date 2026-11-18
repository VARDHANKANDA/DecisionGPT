"use client";

import type { ReactNode } from "react";

export function PageIntro({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
      <p className="mt-1 max-w-3xl text-sm text-muted">{subtitle}</p>
    </div>
  );
}

export function EvalEmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-border bg-surface/60 p-10 text-center">
      <p className="mx-auto max-w-xl text-sm text-muted">{message}</p>
    </div>
  );
}

export function Panel({
  title,
  children,
  right,
  className = "",
}: {
  title?: string;
  children: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-2xl border border-border bg-surface p-6 shadow-sm ${className}`}>
      {title || right ? (
        <div className="mb-4 flex items-center justify-between">
          {title ? <h2 className="text-sm font-semibold text-foreground">{title}</h2> : <span />}
          {right}
        </div>
      ) : null}
      {children}
    </section>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{children}</div>;
}

export function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-xl font-semibold text-foreground">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

export function DataTable({
  headers,
  rows,
  empty = "No rows.",
}: {
  headers: string[];
  rows: (ReactNode | string | number | null)[][];
  empty?: string;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-muted-surface/50 text-left text-muted">
            {headers.map((h) => (
              <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={headers.length} className="px-3 py-6 text-center text-muted">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((r, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                {r.map((c, j) => (
                  <td key={j} className="whitespace-nowrap px-3 py-2 text-foreground">
                    {c === null || c === undefined ? <span className="text-muted">—</span> : c}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

const EVIDENCE_CLASS: Record<string, string> = {
  assumed: "bg-muted-surface text-muted",
  observational: "bg-accent-soft text-accent",
  data_supported: "bg-success-soft text-success",
  causally_validated: "bg-success text-white",
};

export function EvidenceBadge({ level }: { level: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${EVIDENCE_CLASS[level] ?? "bg-muted-surface text-muted"}`}>
      {level.replace(/_/g, " ")}
    </span>
  );
}

export function fmt(v: unknown, digits = 3): string {
  return typeof v === "number" ? v.toFixed(digits) : "—";
}

export function fmtInt(v: unknown): string {
  return typeof v === "number" ? v.toLocaleString("en-IN") : "—";
}

export function StatusPill({ status }: { status: string }) {
  const cls =
    status === "completed"
      ? "bg-success-soft text-success"
      : status === "failed"
        ? "bg-danger-soft text-danger"
        : status === "running"
          ? "bg-accent-soft text-accent"
          : "bg-muted-surface text-muted";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}

// ---------------------------------------------------------------------------
// Pipeline UI — Research Console redesign
//
// A pipeline stage never communicates its state by color alone: every status
// pairs a glyph with a word ("✓ Complete", "○ Not started", "⚠ Partial").
// ---------------------------------------------------------------------------

export type StageStatus = "complete" | "partial" | "not_started" | "unavailable" | "warning";

const STAGE_STATUS_META: Record<StageStatus, { glyph: string; label: string; cls: string }> = {
  complete: { glyph: "✓", label: "Complete", cls: "bg-success-soft text-success" },
  partial: { glyph: "●", label: "Partial", cls: "bg-accent-soft text-accent" },
  not_started: { glyph: "○", label: "Not started", cls: "bg-muted-surface text-muted" },
  unavailable: { glyph: "—", label: "Not available", cls: "bg-muted-surface text-muted" },
  warning: { glyph: "⚠", label: "Needs attention", cls: "bg-warning-soft text-warning" },
};

export function StageStatusBadge({ status, label }: { status: StageStatus; label?: string }) {
  const meta = STAGE_STATUS_META[status];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${meta.cls}`}>
      <span aria-hidden="true">{meta.glyph}</span>
      {label ?? meta.label}
    </span>
  );
}

/** Not-fabricated placeholder — use everywhere a number/field genuinely has no recorded value. */
export function NotAvailable({ children = "Not available" }: { children?: ReactNode }) {
  return <span className="text-muted">{children}</span>;
}

export function UnavailableNote({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-border bg-muted-surface/40 px-3 py-2 text-sm text-muted">
      {children}
    </p>
  );
}

export type StageId =
  | "dataset-files"
  | "data-inspection"
  | "data-cleaning"
  | "data-preparation"
  | "business-tasks"
  | "llm-evaluation"
  | "baselines"
  | "results"
  | "efficiency"
  | "final-results";

export const PIPELINE_STAGES: { id: StageId; short: string; number: number }[] = [
  { id: "dataset-files", short: "Data", number: 1 },
  { id: "data-inspection", short: "Inspection", number: 2 },
  { id: "data-cleaning", short: "Cleaning", number: 3 },
  { id: "data-preparation", short: "Preparation", number: 4 },
  { id: "business-tasks", short: "Tasks", number: 5 },
  { id: "llm-evaluation", short: "LLM", number: 6 },
  { id: "baselines", short: "Baselines", number: 7 },
  { id: "results", short: "Results", number: 8 },
  { id: "efficiency", short: "Efficiency", number: 9 },
  { id: "final-results", short: "Summary", number: 10 },
];

/** Sticky horizontal-scroll stage navigator; click scrolls to the matching section id. */
export function PipelineNav({ active }: { active?: StageId }) {
  function go(id: StageId) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  return (
    <nav
      aria-label="Pipeline stages"
      className="sticky top-0 z-10 -mx-6 mb-8 flex gap-1 overflow-x-auto border-b border-border bg-background/95 px-6 py-2 backdrop-blur"
    >
      {PIPELINE_STAGES.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => go(s.id)}
          aria-current={active === s.id ? "true" : undefined}
          className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium transition ${
            active === s.id
              ? "bg-accent-soft text-accent"
              : "text-muted hover:bg-muted-surface hover:text-foreground"
          }`}
        >
          {s.number}. {s.short}
        </button>
      ))}
    </nav>
  );
}

/** One pipeline stage: numbered card with a one-line explanation, status, a key metric, and
 *  an optional expandable "details" region. Stages connect visually via a vertical rule drawn
 *  by the parent (see StageConnector) so the flow reads top-to-bottom on every screen size. */
export function PipelineStage({
  id,
  number,
  title,
  blurb,
  status,
  keyMetric,
  detailsHref,
  detailsLabel = "View details",
  children,
}: {
  id: StageId;
  number: number;
  title: string;
  blurb: string;
  status: StageStatus;
  keyMetric?: ReactNode;
  detailsHref?: string;
  detailsLabel?: string;
  children?: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-heading`} className="scroll-mt-16">
      <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted-surface text-sm font-semibold text-foreground">
              {number}
            </span>
            <div>
              <h2 id={`${id}-heading`} className="text-base font-semibold text-foreground">
                {title}
              </h2>
              <p className="mt-0.5 text-sm text-muted">{blurb}</p>
            </div>
          </div>
          <StageStatusBadge status={status} />
        </div>

        {keyMetric ? <div className="mt-4 flex flex-wrap gap-3">{keyMetric}</div> : null}

        {children ? <div className="mt-4">{children}</div> : null}

        {detailsHref ? (
          <a
            href={detailsHref}
            className="mt-4 inline-block text-sm font-medium text-accent underline underline-offset-4"
          >
            {detailsLabel} →
          </a>
        ) : null}
      </div>
    </section>
  );
}

/** A short connecting rule drawn between two stage cards — purely visual, decorative. */
export function StageConnector() {
  return (
    <div aria-hidden="true" className="my-1 flex justify-center">
      <div className="h-6 w-px bg-border" />
    </div>
  );
}

/** A small "N files / N rows" chip row used in stage headers. */
export function KeyMetricChip({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-lg bg-muted-surface px-3 py-1.5 text-xs">
      <span className="text-muted">{label}: </span>
      <span className="font-semibold text-foreground">{value}</span>
    </div>
  );
}

/** Collapsible region for secondary / technical detail — progressive disclosure. */
export function Expandable({
  summary,
  children,
}: {
  summary: ReactNode;
  children: ReactNode;
}) {
  return (
    <details className="group rounded-lg border border-border bg-background">
      <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium text-foreground marker:content-none">
        <span className="inline-flex items-center gap-1.5">
          <span className="text-muted transition-transform group-open:rotate-90" aria-hidden="true">
            ›
          </span>
          {summary}
        </span>
      </summary>
      <div className="border-t border-border p-4 text-sm text-muted">{children}</div>
    </details>
  );
}

/** A horizontal bar used only when two values share a genuinely comparable metric/scale. */
export function ComparisonBar({
  label,
  value,
  max,
  display,
  tone = "accent",
}: {
  label: string;
  value: number;
  max: number;
  display: string;
  tone?: "accent" | "success" | "muted";
}) {
  const pct = max > 0 ? Math.max(2, Math.min(100, (Math.abs(value) / max) * 100)) : 0;
  const barCls = tone === "success" ? "bg-success" : tone === "muted" ? "bg-muted" : "bg-accent";
  return (
    <div className="mb-2.5">
      <div className="flex justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-medium tabular-nums text-foreground">{display}</span>
      </div>
      <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-muted-surface">
        <div className={`h-full rounded-full ${barCls}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/** A labelled fact for "file card" style summaries. */
export function FactRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-muted">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}
