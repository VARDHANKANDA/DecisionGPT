"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { EvalEmptyState, Metric, PageIntro, Panel, StatGrid } from "@/components/research-ui";
import { CheckStatusBadge, EvidenceLegend, EvidenceTypeBadge, when } from "@/components/research-evidence";
import { researchApi, type ResearchSummary } from "@/lib/research-api";

const SECTIONS = [
  { href: "/research/datasets", title: "Dataset registry", text: "What data exists, its quality, and one-click preprocessing." },
  { href: "/research/model-comparison", title: "Model comparison", text: "Five forecasting algorithms against a simple baseline on held-out time periods." },
  { href: "/research/llm-evaluation", title: "LLM evaluation", text: "How the AI question-understanding layer performed on the frozen question set." },
  { href: "/research/agent-evaluation", title: "Architecture evaluation", text: "Whether each added component improved simulated decisions." },
  { href: "/research/causal-evaluation", title: "Causal evaluation", text: "What the data can and cannot say about cause and effect." },
  { href: "/research/risk-calibration", title: "Risk calibration", text: "Whether stated probabilities and intervals match what happened." },
  { href: "/research/validation", title: "Validation", text: "Data, model and evidence-integrity checks with pass / fail / warning counts." },
];

const VALIDATION_LABEL: Record<string, string> = {
  no_checks_run: "No checks run",
  passed: "All checks passed",
  passed_with_warnings: "Passed with warnings",
  failed: "Some checks failed",
};

export default function ResearchOverview() {
  const [data, setData] = useState<ResearchSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    researchApi
      .summary()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the research summary."));
  }, []);

  if (error) return <EvalEmptyState message={error} />;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;

  const vc = data.status.validation_counts;
  return (
    <div className="space-y-8">
      <PageIntro title="Research overview" subtitle={data.objective} />

      <section aria-label="Evidence types" className="space-y-2">
        <h2 className="text-sm font-semibold text-foreground">How to read the numbers</h2>
        <EvidenceLegend />
      </section>

      <StatGrid>
        <Metric label="Experiments completed" value={data.status.experiments_completed ?? "not available"} hint={`${data.status.experiments_failed ?? 0} failed`} />
        <Metric label="Algorithms compared" value={data.n_algorithms || "none run"} hint="Four learned models plus one baseline" />
        <Metric label="Live LLM evaluation runs" value={data.status.live_llm_runs || "none run"} hint="All partial so far" />
        <Metric label="Latest verified run" value={<span className="text-base">{when(data.latest_verified_run)}</span>} />
      </StatGrid>

      <Panel title="Key findings supported by stored evidence">
        <ul className="space-y-3">
          {data.key_findings.map((f, i) => (
            <li key={i} className="rounded-xl border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <EvidenceTypeBadge type={f.evidence} />
                <span className="text-xs font-semibold uppercase tracking-wide text-muted">{f.area}</span>
              </div>
              <p className="mt-1.5 text-sm text-foreground">{f.text}</p>
              {f.source ? <p className="mt-1 break-all text-xs text-muted">Source record: {f.source}</p> : null}
            </li>
          ))}
        </ul>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Datasets and coverage">
          <ul className="space-y-3 text-sm">
            {data.datasets.map((d) => (
              <li key={d.name}>
                <p className="font-medium text-foreground">
                  {d.name} <span className="text-xs font-normal text-muted">({d.provenance})</span>
                </p>
                <p className="text-muted">
                  {d.observations === null ? "Not evaluated: no stored run" : `${d.observations.toLocaleString("en-IN")} usable observations, ${d.period}`}
                </p>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Methodology">
          <ul className="space-y-1.5 text-sm text-muted">
            {data.methodology.map((m) => (
              <li key={m}>• {m}</li>
            ))}
          </ul>
          <p className="mt-3 text-sm text-foreground">
            Algorithms: {data.algorithms.join(", ") || "none run"}.
          </p>
          <p className="mt-2 text-xs text-muted">Metrics actually measured: {data.measured_metrics.join(", ") || "none"}.</p>
        </Panel>
      </div>

      <Panel title="Validation status">
        <p className="flex flex-wrap items-center gap-3 text-sm text-foreground">
          <span className="font-medium">{VALIDATION_LABEL[data.status.validation_state] ?? data.status.validation_state}</span>
          <span className="inline-flex flex-wrap gap-2">
            <span className="inline-flex items-center gap-1"><CheckStatusBadge status="passed" /> {vc.passed}</span>
            <span className="inline-flex items-center gap-1"><CheckStatusBadge status="failed" /> {vc.failed}</span>
            <span className="inline-flex items-center gap-1"><CheckStatusBadge status="warning" /> {vc.warning}</span>
            <span className="inline-flex items-center gap-1"><CheckStatusBadge status="not_applicable" /> {vc.not_applicable}</span>
          </span>
          <Link href="/research/validation" className="text-accent underline underline-offset-4">
            Open validation
          </Link>
        </p>
      </Panel>

      <section aria-label="Evaluation sections" className="space-y-3">
        <h2 className="text-base font-semibold text-foreground">Evaluations</h2>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {SECTIONS.map((s) => (
            <li key={s.href}>
              <Link href={s.href} className="block h-full rounded-xl border border-border bg-surface p-4 transition hover:bg-muted-surface focus-visible:outline-2 focus-visible:outline-accent">
                <p className="text-sm font-semibold text-foreground">{s.title}</p>
                <p className="mt-1 text-sm text-muted">{s.text}</p>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <Panel title="Known limitations">
        <ul className="space-y-1.5 text-sm text-muted">
          {data.limitations.map((l) => (
            <li key={l}>• {l}</li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
