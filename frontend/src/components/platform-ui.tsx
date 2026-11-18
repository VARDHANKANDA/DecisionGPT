"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useState, type ReactNode } from "react";
import type { Anchor, ReportPayload, ReportSection } from "@/lib/platform-api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { ErrorBox, Notice, Page, Spinner, btnPrimary } from "@/components/simple";
import { Facts } from "@/components/agent-ui";

const LEGACY_DATA_PAGES = ["/data/profile", "/data/clean", "/data/validate", "/data/transform", "/data/prepare", "/data/quality"];

/** Wraps a page that needs a business: handles the loading and no-business states so each page only renders real content. */
export function Workspace({
  title,
  subtitle,
  action,
  wide = true,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  wide?: boolean;
  children: (businessId: string) => ReactNode;
}) {
  const { business, loading } = useBusiness();
  const pathname = usePathname();
  if (loading) {
    return (
      <Page title={title}>
        <Spinner label="Opening your workspace…" />
      </Page>
    );
  }
  if (!business) {
    return (
      <Page title={title} subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business
        </Link>
      </Page>
    );
  }
  return (
    <Page title={title} subtitle={subtitle} action={action} wide={wide}>
      {LEGACY_DATA_PAGES.includes(pathname ?? "") ? (
        <p className="mb-4 text-base text-muted">
          This is one part of <Link href="/data/preprocessing" className="font-medium text-accent underline underline-offset-4">Data Preprocessing</Link>, which walks through
          all of these steps in one place.
        </p>
      ) : null}
      {children(business.id)}
    </Page>
  );
}

const TONES = {
  good: "bg-success-soft text-success",
  warn: "bg-warning-soft text-warning",
  bad: "bg-danger-soft text-danger",
  neutral: "bg-muted-surface text-muted",
} as const;

/** A small status label. The word is always shown; colour is never the only signal. */
export function Badge({ tone = "neutral", children }: { tone?: keyof typeof TONES; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}>{children}</span>;
}

/** Run an async action (a button press) with busy and error state. */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<FriendlyError | null>(null);
  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      setBusy(true);
      setError(null);
      try {
        return await fn(...args);
      } catch (e) {
        setError(friendlyError(e));
        return undefined;
      } finally {
        setBusy(false);
      }
    },
    [fn],
  );
  return { run, busy, error, clear: () => setError(null) };
}

export function ActionError({ error }: { error: FriendlyError | null }) {
  return error ? <ErrorBox error={error} /> : null;
}

/** Period length and "relative to" selector shared by KPI-based pages. */
export function PeriodPicker({
  days,
  anchor,
  onChange,
  options = [7, 30, 90],
}: {
  days: number;
  anchor: Anchor;
  onChange: (days: number, anchor: Anchor) => void;
  options?: number[];
}) {
  return (
    <div className="flex flex-wrap items-end gap-4">
      <label className="block text-sm font-medium text-foreground">
        Period
        <select
          value={days}
          onChange={(e) => onChange(Number(e.target.value), anchor)}
          className="mt-1 block min-h-[44px] rounded-lg border border-border bg-surface px-3 text-base"
        >
          {options.map((d) => (
            <option key={d} value={d}>
              Last {d} days
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-foreground">
        Counted back from
        <select
          value={anchor}
          onChange={(e) => onChange(days, e.target.value as Anchor)}
          className="mt-1 block min-h-[44px] rounded-lg border border-border bg-surface px-3 text-base"
        >
          <option value="today">Today</option>
          <option value="latest">Your newest sale</option>
        </select>
      </label>
    </div>
  );
}

/** Simple dependency-free line chart with a text summary for screen readers. */
export function LineChart({ points, label, unit = "" }: { points: { date: string; value: number }[]; label: string; unit?: string }) {
  if (points.length < 2) return <p className="text-base text-muted">Not enough points to draw a line yet.</p>;
  const W = 640;
  const H = 160;
  const xs = points.map((_, i) => (i / (points.length - 1)) * (W - 20) + 10);
  const vals = points.map((p) => p.value);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const ys = vals.map((v) => H - 14 - ((v - lo) / span) * (H - 28));
  const d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${ys[i].toFixed(1)}`).join(" ");
  const first = points[0];
  const last = points[points.length - 1];
  return (
    <figure className="min-w-0">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${label}: from ${first.date} to ${last.date}, low ${lo.toLocaleString("en-IN")}${unit}, high ${hi.toLocaleString("en-IN")}${unit}`} className="h-40 w-full">
        <path d={d} fill="none" stroke="currentColor" strokeWidth="2" className="text-accent" />
      </svg>
      <figcaption className="mt-1 flex justify-between text-xs text-muted">
        <span>{first.date}</span>
        <span>
          low {Math.round(lo).toLocaleString("en-IN")} · high {Math.round(hi).toLocaleString("en-IN")}
        </span>
        <span>{last.date}</span>
      </figcaption>
    </figure>
  );
}

export function DataTable({ columns, rows, caption }: { columns: string[]; rows: (string | number | null)[][]; caption?: string }) {
  return (
    <div className="relative overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[480px] text-left text-sm sm:text-base">
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <thead className="bg-muted-surface/60 text-sm text-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((cell, j) => (
                <td key={j} className="px-3 py-2 align-top">
                  {cell === null || cell === undefined ? "—" : typeof cell === "number" ? cell.toLocaleString("en-IN") : cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BulletList({ title, items, empty }: { title?: string; items: string[]; empty?: string }) {
  if (items.length === 0 && !empty) return null;
  return (
    <div>
      {title ? <p className="text-sm font-semibold text-muted">{title}</p> : null}
      {items.length === 0 ? (
        <p className="mt-1 text-base text-muted">{empty}</p>
      ) : (
        <ul className="mt-1 list-disc space-y-1 pl-5 text-base text-foreground">
          {items.map((t, i) => (
            <li key={`${i}-${t}`}>{t}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Collapsible "technical detail" so plain-language answers come first. */
export function Details({ summary, children }: { summary: string; children: ReactNode }) {
  return (
    <details className="rounded-xl border border-border bg-surface px-4 py-3">
      <summary className="cursor-pointer text-base font-medium text-foreground">{summary}</summary>
      <div className="mt-3 space-y-3 text-base text-foreground">{children}</div>
    </details>
  );
}

function Section({ s }: { s: ReportSection }) {
  switch (s.kind) {
    case "notice":
      return <Notice tone={s.tone === "danger" ? "danger" : s.tone === "warning" ? "warning" : "info"}>{s.text}</Notice>;
    case "facts":
      return (
        <div>
          {s.title ? <h3 className="mb-2 text-lg font-semibold text-foreground">{s.title}</h3> : null}
          <Facts items={s.items} />
        </div>
      );
    case "table":
      return (
        <div>
          {s.title ? <h3 className="mb-2 text-lg font-semibold text-foreground">{s.title}</h3> : null}
          <DataTable columns={s.columns} rows={s.rows} caption={s.title} />
          {s.note ? <p className="mt-1 text-sm text-muted">{s.note}</p> : null}
        </div>
      );
    case "series":
      return (
        <div>
          {s.title ? <h3 className="mb-2 text-lg font-semibold text-foreground">{s.title}</h3> : null}
          <LineChart points={s.points} label={s.title ?? "Trend"} unit={s.unit ?? ""} />
          {s.note ? <p className="mt-1 text-sm text-muted">{s.note}</p> : null}
        </div>
      );
    case "text":
      return (
        <div>
          {s.title ? <h3 className="mb-2 text-lg font-semibold text-foreground">{s.title}</h3> : null}
          {s.paragraphs.map((p, i) => (
            <p key={i} className="mb-2 text-base text-foreground">
              {p}
            </p>
          ))}
        </div>
      );
    case "list":
      return <BulletList title={s.title} items={s.items} />;
  }
}

/** Renders a saved report exactly as stored. Nothing is recomputed here. */
export function ReportView({ payload }: { payload: ReportPayload }) {
  return (
    <article className="space-y-6" aria-label={payload.title}>
      <header>
        <h2 className="text-2xl font-semibold text-foreground">{payload.title}</h2>
        <p className="mt-1 text-base text-muted">
          {payload.scope.business} · {payload.period.start} to {payload.period.end} · created {payload.created_on}
          {payload.scope.demo_data ? " · example data" : ""}
        </p>
        <p className="mt-3 text-lg text-foreground">{payload.summary}</p>
      </header>
      {payload.sections.map((s, i) => (
        <Section key={i} s={s} />
      ))}
      <BulletList title="Assumptions" items={payload.assumptions} />
      <BulletList title="Limitations" items={payload.limitations} />
    </article>
  );
}

export const inputCls = "mt-1 block min-h-[44px] w-full rounded-lg border border-border bg-surface px-3 text-base text-foreground";
