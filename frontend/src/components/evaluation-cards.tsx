"use client";

import type { ReactNode } from "react";
import type { MetricCardData, MetricStatus } from "@/lib/research-api";

// A metric is never shown as a bare number. Status is stated in words and an icon (not by colour alone), and a metric that was not
// recorded, not run, or would mislead says so and why instead of showing a value.
const STATUS_LABEL: Record<MetricStatus, { label: string; icon: string; cls: string }> = {
  available: { label: "Recorded", icon: "✓", cls: "bg-success-soft text-foreground" },
  not_available: { label: "Not available", icon: "–", cls: "bg-muted-surface text-foreground" },
  not_evaluated: { label: "Not evaluated", icon: "○", cls: "bg-muted-surface text-foreground" },
  unreliable: { label: "Not reliable", icon: "⚠", cls: "bg-warning-soft text-foreground" },
};

const KIND_LABEL: Record<string, { label: string; icon: string; cls: string }> = {
  not_applicable: { label: "Not applicable", icon: "∅", cls: "bg-muted-surface text-foreground" },
  not_recorded: { label: "Not available", icon: "–", cls: "bg-muted-surface text-foreground" },
  not_evaluated: { label: "Not evaluated", icon: "○", cls: "bg-muted-surface text-foreground" },
  insufficient_data: { label: "Insufficient data", icon: "◐", cls: "bg-warning-soft text-foreground" },
  failed: { label: "Failed", icon: "✕", cls: "bg-danger-soft text-foreground" },
  unreliable: { label: "Not reliable", icon: "⚠", cls: "bg-warning-soft text-foreground" },
};

const CONTEXT_LABEL: Record<string, string> = {
  block: "Data",
  target: "Target",
  n: "Sample",
  dataset: "Dataset",
  threshold: "Threshold",
  threshold_source: "Threshold from",
  positive_class: "Positive class",
  horizon_days: "Horizon (days)",
  method: "Method",
  origins: "Test periods",
  test_window: "Window",
  series: "Series",
  promised: "Promised level",
  points: "Points",
  reference: "Reference",
  positive_rate: "Positive rate",
  series_with_a_defined_wape: "Series with a WAPE",
  top_group: "Group",
};

export function contextText(context: MetricCardData["context"]): string[] {
  return Object.entries(context ?? {})
    .filter(([, v]) => v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `${CONTEXT_LABEL[k] ?? k}: ${Array.isArray(v) ? v.join(" to ") : typeof v === "number" ? v.toLocaleString("en-IN") : String(v)}`);
}

export function MetricCard({ card }: { card: MetricCardData }) {
  const st = (card.kind && KIND_LABEL[card.kind]) || STATUS_LABEL[card.status];
  const ctx = contextText(card.context);
  const shown = card.status === "available";
  return (
    <article
      aria-label={`${card.name}: ${shown ? card.display : st.label}`}
      className="flex flex-col rounded-xl border border-border bg-surface p-4"
      data-metric={card.key}
      data-status={card.status}
      data-kind={card.kind}
    >
      <header className="flex items-start justify-between gap-2">
        <h4 className="text-sm font-medium text-foreground">
          {card.name} <span className="text-muted">({card.abbr})</span>
        </h4>
        {shown ? null : (
          <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${st.cls}`}>
            <span aria-hidden="true">{st.icon} </span>
            {st.label}
          </span>
        )}
      </header>
      <p className={`mt-2 text-2xl font-semibold ${shown ? "text-foreground" : "text-muted"}`}>{card.display}</p>
      {!shown && card.reason ? <p className="mt-1 text-sm text-foreground">{card.reason}</p> : null}
      {shown ? <p className="mt-1 text-xs font-medium text-muted">{card.direction_text}</p> : null}
      {card.sign_note ? <p className="mt-1 text-xs text-muted">{card.sign_note}</p> : null}
      <p className="mt-2 text-sm text-muted">{card.explanation}</p>
      {ctx.length > 0 ? (
        <p className="mt-2 text-xs text-muted">{ctx.join(" · ")}</p>
      ) : null}
      {card.caveat ? (
        <p className="mt-2 border-t border-border pt-2 text-xs text-muted">
          <span className="font-medium text-foreground">Keep in mind: </span>
          {card.caveat}
        </p>
      ) : null}
    </article>
  );
}

export function MetricGrid({ cards, empty }: { cards: MetricCardData[]; empty?: string }) {
  if (cards.length === 0) return empty ? <p className="text-sm text-muted">{empty}</p> : null;
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map((c, i) => (
        <MetricCard key={`${c.key}-${i}`} card={c} />
      ))}
    </div>
  );
}

const EVIDENCE: Record<string, { label: string; cls: string }> = {
  training: { label: "Research dataset · held-out", cls: "border-border bg-muted-surface/60" },
  benchmark: { label: "Public benchmark · as stored", cls: "border-border bg-muted-surface/60" },
  business: { label: "One business · backtest", cls: "border-border bg-muted-surface/60" },
  production: { label: "Live use", cls: "border-border bg-muted-surface/60" },
};

/** Says which kind of evidence a block is. Kinds are never merged, so each block names its own. */
export function EvidenceTag({ kind }: { kind: keyof typeof EVIDENCE | string }) {
  const e = EVIDENCE[kind] ?? { label: kind, cls: "border-border" };
  return <span className={`inline-block rounded-full border px-2.5 py-0.5 text-xs font-medium text-foreground ${e.cls}`}>{e.label}</span>;
}

export function Block({ title, tag, children, note }: { title: string; tag?: string; children: ReactNode; note?: string }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-5 shadow-sm" aria-label={title}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {tag ? <EvidenceTag kind={tag} /> : null}
      </div>
      {note ? <p className="mb-3 max-w-3xl text-sm text-muted">{note}</p> : null}
      {children}
    </section>
  );
}

// ---- "Evaluated on": the facts a result depends on, shown once above its cards -------------------------------------------------------------
export function EvaluatedOn({ facts }: { facts: [string, ReactNode | null | undefined][] }) {
  const shown = facts.filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (shown.length === 0) return null;
  return (
    <dl aria-label="Evaluated on" className="mb-4 grid grid-cols-1 gap-x-6 gap-y-1 rounded-xl border border-border bg-muted-surface/40 px-4 py-3 text-sm sm:grid-cols-2">
      {shown.map(([k, v]) => (
        <div key={k} className="flex flex-wrap gap-x-2">
          <dt className="text-muted">{k}:</dt>
          <dd className="font-medium text-foreground">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

// ---- states that look different on purpose: not evaluated, not enough data, failed, possibly out of date --------------------------------------
export type StateKind = "not_evaluated" | "insufficient" | "failed" | "stale";
const STATE: Record<StateKind, { label: string; icon: string; cls: string; role: "status" | "alert" }> = {
  not_evaluated: { label: "Not evaluated", icon: "○", cls: "border-dashed border-border bg-muted-surface/40", role: "status" },
  insufficient: { label: "Not enough data", icon: "◐", cls: "border-warning/40 bg-warning-soft", role: "status" },
  failed: { label: "Failed", icon: "✕", cls: "border-danger/40 bg-danger-soft", role: "alert" },
  stale: { label: "May be out of date", icon: "⏱", cls: "border-warning/40 bg-warning-soft", role: "status" },
};

export function StateNote({ kind, children }: { kind: StateKind; children: ReactNode }) {
  const st = STATE[kind];
  return (
    <div role={st.role} data-state={kind} className={`rounded-lg border px-3 py-2 text-sm text-foreground ${st.cls}`}>
      <span className="font-semibold">
        <span aria-hidden="true">{st.icon} </span>
        {st.label}.
      </span>{" "}
      {children}
    </div>
  );
}

/** What each column or card means, taken from the cards themselves (the backend registry), so the page carries no definitions of its own. */
export function MetricLegend({ cards, title = "What these figures mean" }: { cards: MetricCardData[]; title?: string }) {
  const seen = new Set<string>();
  const unique = cards.filter((c) => (seen.has(c.key) ? false : (seen.add(c.key), true)));
  if (unique.length === 0) return null;
  return (
    <details className="mt-3 rounded-lg border border-border px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium text-foreground">{title}</summary>
      <dl className="mt-2 space-y-3">
        {unique.map((c) => (
          <div key={c.key}>
            <dt className="font-medium text-foreground">
              {c.name} ({c.abbr}) <span className="font-normal text-muted">· {c.direction_text}</span>
            </dt>
            <dd className="text-muted">
              {c.explanation}
              {c.sign_note ? ` ${c.sign_note}` : ""}
              {c.caveat ? ` Keep in mind: ${c.caveat}` : ""}
            </dd>
          </div>
        ))}
      </dl>
    </details>
  );
}

/** One table cell for a card: the recorded value, or the state in words (the reason is in the tooltip). Never a bare dash. */
export function CardCell({ card }: { card: MetricCardData | undefined }) {
  if (!card) return <span className="text-muted">Not available</span>;
  return (
    <span title={card.reason ?? undefined} className={card.status === "available" ? "" : "text-muted"}>
      {card.display}
    </span>
  );
}
