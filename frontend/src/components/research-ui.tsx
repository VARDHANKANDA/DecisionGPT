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
