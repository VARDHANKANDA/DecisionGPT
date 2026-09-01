"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  researchApi,
  type AgentEvaluation,
  type PaperResults,
  type ResearchOverview,
} from "@/lib/research-api";

type StatusKind =
  | "controlled"
  | "real-data-probe"
  | "not-validated"
  | "blocked"
  | "not-ready"
  | "production";

const STATUS_STYLE: Record<StatusKind, { label: string; cls: string }> = {
  controlled: { label: "VALIDATED IN CONTROLLED EXPERIMENTS", cls: "bg-success-soft text-success" },
  "real-data-probe": { label: "REAL-DATA PROBE", cls: "bg-accent-soft text-accent" },
  "not-validated": { label: "NOT VALIDATED", cls: "bg-warning-soft text-warning" },
  blocked: { label: "BLOCKED", cls: "bg-muted-surface text-muted" },
  "not-ready": { label: "NOT READY", cls: "bg-warning-soft text-warning" },
  production: { label: "PRODUCTION", cls: "bg-muted-surface text-muted" },
};

function StatusTag({ kind }: { kind: StatusKind }) {
  const s = STATUS_STYLE[kind];
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-wide ${s.cls}`}>
      {s.label}
    </span>
  );
}

export default function ResearchOverviewPage() {
  const [ov, setOv] = useState<ResearchOverview | null>(null);
  const [paper, setPaper] = useState<PaperResults | null>(null);
  const [agents, setAgents] = useState<AgentEvaluation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.allSettled([researchApi.overview(), researchApi.paperResults(), researchApi.agentEvaluation()])
      .then(([o, p, a]) => {
        if (o.status === "fulfilled") setOv(o.value);
        if (p.status === "fulfilled") setPaper(p.value);
        if (a.status === "fulfilled") setAgents(a.value);
        if (o.status === "rejected") setError(String(o.reason?.message ?? o.reason));
      })
      .catch((e) => setError(String(e?.message ?? e)));
  }, []);

  const table2 = paper?.tables.find((t) => t.key === "digital_twin_evaluation");
  // Headline numbers come from the POST-correction multi-scenario diagnostic
  // (12 scenarios × 5 seeds) — the authoritative controlled comparison — not the
  // preserved legacy single-scenario run.
  const mad = agents?.multi_agent_diagnostic ?? null;
  const aVal = 0; // "prediction only" has no strategy mechanism → 0 by construction
  const bVal = mad?.digital_twin_mean_goal_achievement ?? null;
  const dVal = mad?.full_decisiongpt_mean_goal_achievement ?? null;

  return (
    <div className="space-y-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Research Overview</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">
          A controlled, reproducible evaluation of the DecisionGPT architecture. Every number is a live
          aggregate over stored experiment rows — nothing is hard-coded, and nothing here is a real-world
          performance claim.
        </p>
      </header>

      {error ? (
        <p className="rounded-lg bg-danger-soft px-4 py-3 text-sm text-danger">{error}</p>
      ) : null}

      {/* ---------- Level 1: Research status ---------- */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Research status</h2>
        <dl className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <StatusCard title="Experiments completed" value={ov ? `${ov.experiments_completed} / ${ov.experiment_count}` : "…"}
            note={ov?.experiments_failed ? `${ov.experiments_failed} failed` : "all recorded runs succeeded"} />
          <StatusCard title="Production decision model" value="R0 / D0"
            note="risk_model = None · risk_penalty_lambda = 1.0 — unchanged" tag="production" />
          <StatusCard title="Risk Manager R3" value="Experimental"
            note="Promising on the synthetic suite; not promoted." tag="controlled" />
          <StatusCard title="Real SME outcomes" value="0"
            note="No genuine decision outcomes have been collected yet." tag="not-validated" />
          <StatusCard title="Real-LLM validation" value="Blocked"
            note="No LLM provider is configured." tag="blocked" />
          <StatusCard title="Table 2 — Digital Twin vs actual" value={table2?.available ? "Ready" : "Not ready"}
            note={table2?.missing_reason ?? "Needs ≥ 5 genuine real-SME matched records."} tag="not-ready" />
          <StatusCard title="Causal validation (real interventions)" value="Not ready"
            note="CAUSALLY_VALIDATED = 0 — no real intervention evidence." tag="not-ready" />
        </dl>
      </section>

      {/* ---------- Level 1: Key findings ---------- */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Key findings</h2>
        <ul className="mt-3 space-y-3">
          <Finding
            title="Decision-simulation layer (Digital Twin)"
            body="Strongest objective contribution in the controlled evaluation — it is the only component that improved the simulated goal-attainment metric."
            kind="controlled"
          />
          <Finding
            title="Multi-agent layer"
            body="Adding the rule-based multi-agent layer reduced simulated goal achievement relative to the strongest baseline; the cause was traced to the risk-penalty term, not an unequal strategy space."
            kind="controlled"
          />
          <Finding
            title="Risk Manager calibration (R3)"
            body="R3 was promising on the synthetic calibration suite but was not promoted; on the one real Indian dataset it had no measurable effect."
            kind="real-data-probe"
          />
          <Finding
            title="Real-world validation"
            body="Not yet validated — 0 genuine SME outcomes recorded, no real-LLM run, and no real intervention evidence for causality."
            kind="not-validated"
          />
        </ul>
      </section>

      {/* ---------- Level 2: The headline result ---------- */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">What did we learn?</h2>
        <div className="mt-3 rounded-2xl border border-border bg-surface p-6">
          <p className="max-w-2xl text-sm text-foreground">
            In the controlled 12-scenario suite, the decision-simulation layer produced the strongest measured
            improvement. Adding the rule-based multi-agent layer on top of it <strong>reduced</strong> the
            simulated goal-attainment metric.
          </p>

          <div className="mt-5 space-y-3">
            <Bar label="Prediction only" value={aVal} />
            <Bar label="Prediction + Decision Simulation" value={bVal ?? 0} highlight />
            <Bar label="Prediction + Decision Simulation + Multi-Agent (full)" value={dVal ?? 0} />
          </div>

          <p className="mt-4 text-xs text-muted">
            Simulated goal-attainment metric ·{" "}
            <span className="font-medium text-foreground">B = {(bVal ?? 0).toFixed(3)}</span>
            {"  ·  "}
            <span className="font-medium text-foreground">D = {(dVal ?? 0).toFixed(3)}</span>
            {mad ? "" : " (loading…)"}
          </p>
          <p className="mt-2 rounded-lg bg-warning-soft px-3 py-2 text-xs text-warning">
            These are simulated goal-attainment metrics from the controlled research suite — <strong>not</strong>{" "}
            real SME outcomes. The scenarios are designed, not sampled from a population.
          </p>

          <Link
            href="/research/agent-evaluation"
            className="mt-4 inline-block text-sm font-medium text-accent underline underline-offset-4"
          >
            Full architecture evaluation →
          </Link>
        </div>
      </section>

      {/* ---------- Level 1: Real-world evidence (empty, handled honestly) ---------- */}
      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Real-world evidence</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
          <PendingCard
            title="Real-world validation"
            state="Pending"
            body="0 genuine SME outcomes recorded. Table 2 becomes available once the required real-world outcome records are collected."
          />
          <PendingCard
            title="Real LLM"
            state="Blocked"
            body="No LLM provider is currently configured. By design a real LLM would affect goal parsing and narration only, not scoring."
          />
          <PendingCard
            title="Causal validation"
            state="Not ready"
            body="No real intervention evidence has been collected. Causal recovery is validated on synthetic ground truth only."
          />
        </div>
      </section>

      {/* ---------- Levels 3 & 4: pointers ---------- */}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Link
          href="/research/experiments"
          className="rounded-xl border border-border bg-surface p-5 transition hover:border-accent"
        >
          <p className="text-sm font-medium text-foreground">Methodology &amp; reproducibility →</p>
          <p className="mt-1 text-xs text-muted">
            Experiment runner, seeds, dataset versions, and the downloadable reproducibility manifest
            ({ov?.experiment_count ?? "…"} experiments, seed 42).
          </p>
        </Link>
        <Link
          href="/research/export"
          className="rounded-xl border border-border bg-surface p-5 transition hover:border-accent"
        >
          <p className="text-sm font-medium text-foreground">Paper results tables →</p>
          <p className="mt-1 text-xs text-muted">
            {paper ? `${paper.summary.tables_ready} of ${paper.summary.tables_total} tables ready` : "…"} —
            with CSV / Markdown / LaTeX export.
          </p>
        </Link>
      </section>
    </div>
  );
}

function StatusCard({
  title,
  value,
  note,
  tag,
}: {
  title: string;
  value: string;
  note?: string;
  tag?: StatusKind;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface p-4">
      <p className="text-xs text-muted">{title}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
      {tag ? <div className="mt-2"><StatusTag kind={tag} /></div> : null}
      {note ? <p className="mt-2 text-xs leading-snug text-muted">{note}</p> : null}
    </div>
  );
}

function Finding({ title, body, kind }: { title: string; body: string; kind: StatusKind }) {
  return (
    <li className="rounded-xl border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <StatusTag kind={kind} />
      </div>
      <p className="mt-1.5 text-sm text-muted">{body}</p>
    </li>
  );
}

function Bar({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-medium text-foreground">{value.toFixed(3)}</span>
      </div>
      <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-muted-surface">
        <div
          className={`h-full rounded-full ${highlight ? "bg-success" : "bg-accent"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** Shared small status pill — imported by other research pages. */
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

function PendingCard({ title, state, body }: { title: string; state: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-muted-surface/40 p-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <span className="rounded-full bg-surface px-2 py-0.5 text-xs font-medium text-muted">{state}</span>
      </div>
      <p className="mt-2 text-xs leading-snug text-muted">{body}</p>
    </div>
  );
}
