"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import type { DataType } from "@/lib/api";
import { DATA_GROUP_NAME } from "@/lib/features";
import { REFERENCE_FORMAT } from "@/lib/sample-data";
import type { FriendlyError } from "@/lib/friendly";

/** Shared building blocks for the everyday (non-technical) screens: big targets, plain words. */

export const btnPrimary =
  "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
export const btnSecondary =
  "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full border border-border bg-surface px-5 py-2.5 text-sm font-medium text-foreground transition hover:bg-muted-surface disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
export const btnDanger =
  "inline-flex min-h-[44px] items-center justify-center gap-2 rounded-full bg-danger px-5 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger";

export function Page({
  title,
  subtitle,
  action,
  children,
  wide = false,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <div className={`mx-auto px-4 py-6 sm:px-6 sm:py-8 ${wide ? "max-w-6xl" : "max-w-4xl"}`}>
      <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-[26px]">{title}</h1>
          {subtitle ? <p className="mt-1.5 max-w-2xl text-sm sm:text-base text-muted">{subtitle}</p> : null}
        </div>
        {action}
      </header>
      {children}
    </div>
  );
}

export function ActionCard({
  href,
  onClick,
  icon,
  title,
  description,
  badge,
}: {
  href?: string;
  onClick?: () => void;
  icon: string;
  title: string;
  description: string;
  badge?: string;
}) {
  const inner = (
    <>
      <span aria-hidden="true" className="text-2xl">
        {icon}
      </span>
      <span className="mt-2.5 block text-base font-semibold text-foreground">{title}</span>
      <span className="mt-1 block text-sm text-muted">{description}</span>
      {badge ? (
        <span className="mt-2.5 inline-block rounded-full bg-muted-surface px-2.5 py-0.5 text-xs text-muted">{badge}</span>
      ) : null}
    </>
  );
  const cls =
    "block w-full rounded-2xl border border-border bg-surface p-6 text-left shadow-sm transition hover:border-accent hover:shadow-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";
  return href ? (
    <Link href={href} className={cls}>
      {inner}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={cls}>
      {inner}
    </button>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "success" | "warning" | "danger";
  title?: string;
  children?: ReactNode;
}) {
  const cls = {
    info: "border-border bg-muted-surface/50 text-foreground",
    success: "border-success/30 bg-success-soft text-foreground",
    warning: "border-warning/40 bg-warning-soft text-foreground",
    danger: "border-danger/30 bg-danger-soft text-foreground",
  }[tone];
  const icon = { info: "ℹ️", success: "✓", warning: "⚠", danger: "!" }[tone];
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={`rounded-2xl border px-5 py-4 text-base ${cls}`}>
      {title ? (
        <p className="font-semibold">
          <span aria-hidden="true" className="mr-2">
            {icon}
          </span>
          {title}
        </p>
      ) : null}
      {children ? <div className={title ? "mt-1 text-muted" : ""}>{children}</div> : null}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: FriendlyError; onRetry?: () => void }) {
  return (
    <div role="alert" className="rounded-2xl border border-danger/30 bg-danger-soft px-5 py-4">
      <p className="text-base font-semibold text-foreground">{error.message}</p>
      <p className="mt-1 text-base text-muted">Your data is still safe.</p>
      <div className="mt-3 flex flex-wrap items-center gap-4">
        {onRetry ? (
          <button type="button" onClick={onRetry} className={btnSecondary}>
            Try again
          </button>
        ) : null}
        <details className="text-sm text-muted">
          <summary className="cursor-pointer">Technical details</summary>
          <p className="mt-1 break-words">{error.technical}</p>
        </details>
      </div>
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <p role="status" aria-live="polite" className="flex items-center gap-3 text-base text-muted">
      <span
        aria-hidden="true"
        className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-border border-t-accent"
      />
      {label}
    </p>
  );
}

/** Plain-language confirmation before anything destructive. Escape / Cancel always safe. */
export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  busy,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  body: ReactNode;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus(); // default focus on the SAFE choice
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onCancel]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-foreground/40 p-4 sm:items-center">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-md rounded-2xl bg-surface p-6 shadow-xl"
      >
        <h2 id="confirm-title" className="text-xl font-semibold text-foreground">
          {title}
        </h2>
        <div className="mt-2 text-base text-muted">{body}</div>
        <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button ref={cancelRef} type="button" onClick={onCancel} disabled={busy} className={btnSecondary}>
            Cancel
          </button>
          <button type="button" onClick={onConfirm} disabled={busy} className={btnDanger}>
            {busy ? "Please wait…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

/** A read-only preview table that scrolls sideways on small screens. */
export function PreviewTable({
  columns,
  rows,
}: {
  columns: { key: string; label: string }[];
  rows: Record<string, unknown>[];
}) {
  return (
    <div className="relative min-w-0 max-w-full overflow-x-auto rounded-xl border border-border" tabIndex={0} aria-label="Data table, scrolls sideways">
      <table className="w-full text-left text-base">
        <thead>
          <tr className="border-b border-border bg-muted-surface/60 text-muted">
            {columns.map((c) => (
              <th key={c.key} scope="col" className="whitespace-nowrap px-4 py-3 font-medium">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border last:border-0">
              {columns.map((c) => (
                <td key={c.key} className="whitespace-nowrap px-4 py-3 text-foreground">
                  {r[c.key] === null || r[c.key] === undefined || r[c.key] === "" ? (
                    <span className="text-muted">—</span>
                  ) : (
                    String(r[c.key])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export const KIND_ICON: Record<string, string> = {
  sales: "💰",
  customers: "👥",
  products: "📦",
  inventory: "🏬",
  marketing_campaigns: "📣",
  finance: "🧾",
};

/** A real, usable part of DecisionGPT: what it does, what it needs, what you get, and a way in. */
export function FeatureCard({
  icon,
  title,
  summary,
  needs,
  gives,
  href,
  cta,
  status,
}: {
  icon: string;
  title: string;
  summary: string;
  needs?: string;
  gives?: string;
  href: string;
  cta: string;
  /** Plain-language readiness note — shown only when we actually know. */
  status?: { ready: boolean; text: string } | null;
}) {
  return (
    <div className="flex h-full min-w-0 flex-col rounded-2xl border border-border bg-surface p-6 shadow-sm">
      <span aria-hidden="true" className="text-3xl">
        {icon}
      </span>
      <h3 className="mt-3 text-xl font-semibold text-foreground">{title}</h3>
      <p className="mt-1 text-base text-foreground/80">{summary}</p>
      {needs || gives ? (
        <dl className="mt-3 space-y-1 text-sm text-muted">
          {needs ? (
            <div>
              <dt className="inline font-medium text-foreground/80">Needs: </dt>
              <dd className="inline">{needs}</dd>
            </div>
          ) : null}
          {gives ? (
            <div>
              <dt className="inline font-medium text-foreground/80">You get: </dt>
              <dd className="inline">{gives}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}
      {status ? (
        <p className={`mt-3 text-sm font-medium ${status.ready ? "text-success" : "text-warning"}`}>
          <span aria-hidden="true">{status.ready ? "✓ " : "⚠ "}</span>
          {status.text}
        </p>
      ) : null}
      <div className="mt-auto pt-5">
        <Link href={href} className={btnPrimary}>
          {cta}
        </Link>
      </div>
    </div>
  );
}

/**
 * The shape every analysis result follows: the answer first, then why it matters, what the data
 * shows, what to watch, and a next step. Sections without content are simply left out.
 */
export function AnswerBlock({
  headline,
  why,
  shows,
  watch,
  next,
  label = "Your answer",
}: {
  label?: string;
  headline: string;
  why?: ReactNode;
  shows?: ReactNode;
  watch?: ReactNode;
  next?: ReactNode;
}) {
  const section = (label: string, body: ReactNode) =>
    body ? (
      <section className="mt-4">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</h3>
        <div className="mt-1 text-sm leading-relaxed text-foreground max-w-3xl">{body}</div>
      </section>
    ) : null;
  return (
    <div className="rounded-2xl border border-accent/30 bg-accent-soft/30 p-5 sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-wide text-accent">{label}</p>
      <p className="mt-1.5 text-base sm:text-lg font-semibold leading-snug text-foreground">{headline}</p>
      {section("Why it matters", why)}
      {section("What your data shows", shows)}
      {section("What to watch", watch)}
      {section("Possible next step", next)}
    </div>
  );
}

/** Says plainly which of the person's data a feature is using (the app uses all of a kind). */
export function DataUsed({
  library,
  types,
  action,
}: {
  library: { type: string; title: string; rows: number; last_updated: string | null }[] | null;
  types: string[];
  action?: ReactNode;
}) {
  if (!library) return null;
  const mine = library.filter((d) => types.includes(d.type));
  return (
    <section aria-labelledby="data-used" className="rounded-2xl border border-border bg-surface p-5">
      <h2 id="data-used" className="text-base font-semibold text-foreground">
        Data used
      </h2>
      <p className="mt-1 text-base text-foreground">{usingLine(mine.map((d) => d.type as DataType))}</p>
      <ul className="mt-2 space-y-1 text-base">
        {mine.map((d) => (
          <li key={d.type} className="flex flex-wrap items-baseline justify-between gap-x-4">
            <span className="text-foreground">
              <span aria-hidden="true" className="mr-2">
                {KIND_ICON[d.type]}
              </span>
              <Link href={`/data/${d.type}`} className="underline underline-offset-4">
                {DATA_GROUP_NAME[d.type as DataType] ?? d.title}
              </Link>
            </span>
            <span className={d.rows > 0 ? "text-muted" : "text-warning"}>
              {d.rows > 0 ? `${d.rows.toLocaleString("en-IN")} rows` : "none added yet"}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-sm text-muted">DecisionGPT chooses this automatically — there is nothing for you to select.</p>
      {action ? <div className="mt-3">{action}</div> : null}
    </section>
  );
}

/**
 * "What should my file look like?" — an example table per kind of data, using exactly the fields
 * DecisionGPT understands. Teaching by example instead of by schema vocabulary.
 */
export function ReferenceFormat({ value, onChange }: { value: DataType; onChange: (t: DataType) => void }) {
  const fields = REFERENCE_FORMAT[value];
  const kinds = Object.keys(REFERENCE_FORMAT) as DataType[];
  return (
    <section aria-labelledby="ref-h" className="rounded-2xl border border-border bg-surface p-5">
      <h2 id="ref-h" className="text-lg font-semibold text-foreground">What should my file look like?</h2>
      <p className="mt-1 text-base text-muted">
        DecisionGPT uses the fields it supports for each kind of data. Use these columns when preparing your file — the
        names don&apos;t have to match exactly, we&apos;ll help you match them.
      </p>
      <div role="group" aria-label="Kind of data" className="mt-3 flex flex-wrap gap-2">
        {kinds.map((k) => (
          <button
            key={k}
            type="button"
            aria-pressed={value === k}
            onClick={() => onChange(k)}
            className={`min-h-[44px] rounded-full border px-4 py-2 text-base ${
              value === k ? "border-accent bg-accent-soft font-medium text-accent" : "border-border text-foreground hover:bg-muted-surface"
            }`}
          >
            <span aria-hidden="true">{KIND_ICON[k]} </span>
            {DATA_GROUP_NAME[k]}
          </button>
        ))}
      </div>
      <p className="mt-4 text-base font-medium text-foreground">Example {DATA_GROUP_NAME[value].toLowerCase()}</p>
      <div className="relative mt-2 overflow-x-auto rounded-xl border border-border" tabIndex={0} aria-label="Example file layout, scrolls sideways">
        <table className="w-full text-base">
          <thead className="bg-muted-surface/60 text-left text-sm text-muted">
            <tr>
              {fields.map((f) => (
                <th key={f.label} className="whitespace-nowrap px-4 py-2 font-medium">
                  {f.label}
                  {f.required ? <span className="ml-1 text-foreground"> (needed)</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-t border-border">
              {fields.map((f) => (
                <td key={f.label} className="whitespace-nowrap px-4 py-2 text-foreground">{f.example}</td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-sm text-muted">Example values only — not your data. One row per {value === "finance" ? "month" : "entry"}.</p>
    </section>
  );
}

/** "Using your available sales data." — says exactly which kinds of data a feature reads. */
export function usingLine(types: DataType[]): string {
  if (types.length === 0) return "Using your available data.";
  if (types.length > 3) return "Using your available business data.";
  const names = types.map((t) => DATA_GROUP_NAME[t].replace(/ data$/, "").toLowerCase());
  const joined = names.length === 1 ? names[0] : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
  return `Using your available ${joined} data.`;
}
