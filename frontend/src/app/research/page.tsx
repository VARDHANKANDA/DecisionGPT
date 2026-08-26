"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { researchApi, type ResearchOverview } from "@/lib/research-api";

export default function ResearchOverviewPage() {
  const [ov, setOv] = useState<ResearchOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    researchApi.overview().then(setOv).catch((e) => setError(String(e?.message ?? e)));
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Research Console</h1>
      <p className="mt-1 text-muted">
        Private, platform-administrator surface. Every number below is a live aggregate over real rows —
        nothing is hard-coded. Never reachable from the SME application.
      </p>

      {error ? <p className="mt-6 text-sm text-danger">{error}</p> : null}
      {!ov ? (
        <p className="mt-6 text-sm text-muted">Loading…</p>
      ) : (
        <>
          <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat href="/research/datasets" label="Uploaded datasets" value={ov.uploaded_dataset_count}
              hint={`${ov.uploaded_dataset_version_count} versions`} />
            <Stat href="/research/datasets" label="Platform datasets" value={ov.platform_dataset_count} />
            <Stat href="/research/models" label="Active models" value={ov.active_model_count}
              hint={`${ov.experimental_model_count} experimental`} />
            <Stat href="/research/training" label="Training runs" value={ov.training_run_count}
              hint={ov.training_runs_failed ? `${ov.training_runs_failed} failed` : "all ok"} />
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat href="/research/experiments" label="Experiments" value={ov.experiment_count}
              hint={`${ov.experiments_completed} done · ${ov.experiments_failed} failed`} />
            <Stat href="/research/models" label="Registered models" value={ov.model_count} />
          </div>

          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card title="Latest experiment">
              {ov.latest_experiment ? (
                <div className="text-sm">
                  <p className="text-foreground">{ov.latest_experiment.experiment_type}</p>
                  <p className="mt-1 text-muted">
                    <StatusPill status={ov.latest_experiment.status} />{" "}
                    {new Date(ov.latest_experiment.created_at).toLocaleString()}
                  </p>
                  <Link
                    href={`/research/experiments`}
                    className="mt-3 inline-block text-accent underline underline-offset-4"
                  >
                    View experiments →
                  </Link>
                </div>
              ) : (
                <p className="text-sm text-muted">No experiments recorded yet.</p>
              )}
            </Card>

            <Card title="Best recorded metrics (active models)">
              {Object.keys(ov.best_metrics).length === 0 ? (
                <p className="text-sm text-muted">No active models with metrics yet.</p>
              ) : (
                <ul className="space-y-1 text-sm">
                  {Object.entries(ov.best_metrics).map(([k, v]) => (
                    <li key={k} className="flex items-center justify-between border-b border-border py-1">
                      <span className="uppercase text-muted">{k}</span>
                      <span className="font-medium text-foreground">
                        {v.value.toFixed(3)} <span className="text-xs text-muted">· {v.model}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function Stat({
  href,
  label,
  value,
  hint,
}: {
  href: string;
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <Link href={href} className="block rounded-2xl border border-border bg-surface p-5 shadow-sm transition hover:border-accent">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
      {hint ? <p className="mt-1 text-xs text-muted">{hint}</p> : null}
    </Link>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
      <h2 className="text-sm font-medium text-foreground">{title}</h2>
      <div className="mt-3">{children}</div>
    </div>
  );
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
