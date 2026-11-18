"use client";

import { useEffect, useMemo, useState } from "react";
import { EvalEmptyState, Expandable, PageIntro, Panel } from "@/components/research-ui";
import { CheckStatusBadge, when } from "@/components/research-evidence";
import { researchApi, type ValidationReport } from "@/lib/research-api";

const STATE: Record<string, { title: string; text: string }> = {
  no_checks_run: { title: "No checks were run", text: "Nothing could be checked, so this is not a pass." },
  passed: { title: "All checks passed", text: "Every check that could be run passed." },
  passed_with_warnings: { title: "Passed with warnings", text: "No check failed, but some need attention before results are relied on." },
  failed: { title: "Validation failed", text: "At least one check failed; see the remedies below." },
};

const GROUP: Record<string, string> = { data: "Data", model: "Model runs", evidence: "Evidence integrity" };

export default function ValidationPage() {
  const [data, setData] = useState<ValidationReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("attention");

  useEffect(() => {
    researchApi
      .validationReport()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load validation."));
  }, []);

  const shown = useMemo(() => {
    if (!data) return [];
    if (filter === "all") return data.checks;
    if (filter === "attention") return data.checks.filter((c) => c.status === "failed" || c.status === "warning");
    return data.checks.filter((c) => c.status === filter);
  }, [data, filter]);

  if (error) return <EvalEmptyState message={error} />;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;

  const st = STATE[data.state] ?? STATE.no_checks_run;
  const groups = Array.from(new Set(shown.map((c) => c.group)));
  return (
    <div className="space-y-6">
      <PageIntro
        title="Validation"
        subtitle="Real checks on the datasets, the stored model runs and the frozen evidence. Passed, failed, warning and not-applicable are counted separately, and every check says what it looked at."
      />

      <Panel title={st.title}>
        <p className="text-sm text-muted">{st.text}</p>
        <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(["passed", "failed", "warning", "not_applicable"] as const).map((k) => (
            <div key={k} className="rounded-xl border border-border p-3">
              <dt><CheckStatusBadge status={k} /></dt>
              <dd className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{data.counts[k]}</dd>
            </div>
          ))}
        </dl>
        <p className="mt-3 text-xs text-muted">
          {data.checks_run} of {data.total_checks} checks were run (the rest are not applicable). Generated {when(data.generated_utc)}. Datasets checked:{" "}
          {data.datasets.map((d) => `${d.label} (${d.rows === null ? "unreadable" : `${d.rows.toLocaleString("en-IN")} rows`})`).join("; ")}.
        </p>
      </Panel>

      <div role="group" aria-label="Filter checks" className="flex flex-wrap gap-2">
        {[
          ["attention", "Needs attention"],
          ["all", "All checks"],
          ["failed", "Failed"],
          ["warning", "Warnings"],
          ["passed", "Passed"],
          ["not_applicable", "Not applicable"],
        ].map(([k, label]) => (
          <button
            key={k}
            type="button"
            aria-pressed={filter === k}
            onClick={() => setFilter(k)}
            className={`rounded-full border px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${filter === k ? "border-accent bg-accent-soft font-medium text-accent" : "border-border text-muted"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {shown.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted">No checks in this view.</p>
      ) : (
        groups.map((g) => (
          <section key={g} aria-label={GROUP[g] ?? g}>
            <h2 className="mb-2 text-sm font-semibold text-foreground">{GROUP[g] ?? g}</h2>
            <ul className="space-y-2">
              {shown.filter((c) => c.group === g).map((c, i) => (
                <li key={`${c.subject}-${c.id}-${i}`} className="rounded-xl border border-border bg-surface p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <CheckStatusBadge status={c.status} />
                    <span className="text-sm font-medium text-foreground">{c.rule}</span>
                  </div>
                  <p className="mt-1 text-xs text-muted">{c.subject}</p>
                  <p className="mt-1 text-sm text-muted">{c.explanation}</p>
                  {c.remedy ? <p className="mt-1 text-sm text-foreground"><span className="font-medium">Remedy:</span> {c.remedy}</p> : null}
                  {c.observed !== null && c.observed !== undefined ? (
                    <div className="mt-2">
                      <Expandable summary="Observed values">
                        <pre className="overflow-x-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(c.observed, null, 2)}</pre>
                      </Expandable>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
