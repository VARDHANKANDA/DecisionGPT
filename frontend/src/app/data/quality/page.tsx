"use client";

import Link from "next/link";
import { api, type IngestionJob } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { DATA_GROUP_NAME, capabilityName } from "@/lib/features";
import { timeAgo } from "@/lib/friendly";
import { Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { platform, type PrepRun } from "@/lib/platform-api";
import { ActionError, Badge, useAction } from "@/components/platform-ui";
import { useState } from "react";

const STATUS: Record<IngestionJob["status"], { label: string; tone: string }> = {
  completed: { label: "Passed", tone: "bg-success-soft text-success" },
  failed: { label: "Failed", tone: "bg-danger-soft text-danger" },
  needs_mapping_confirmation: { label: "Needs your confirmation", tone: "bg-warning-soft text-warning" },
  processing: { label: "Checking…", tone: "bg-muted-surface text-muted" },
};

function qualityNotes(job: IngestionJob): string[] {
  // What the import report recorded for this file: rows left out (never silently), and anything worth a second look (for example repeated rows).
  const notes: string[] = [];
  for (const d of job.summary_json?.datasets ?? []) {
    if (d.rows_skipped > 0) notes.push(`${d.rows_skipped.toLocaleString("en-IN")} of ${d.rows_read.toLocaleString("en-IN")} ${d.type.replace(/_/g, " ")} rows were left out`);
    for (const w of d.warnings ?? []) notes.push(w);
  }
  return notes.slice(0, 6);
}

const STAGE_WORD: Record<string, string> = { profile: "Profile", clean: "Cleaning", validate: "Validation", transform: "Transformation" };

function PrepRuns({ businessId }: { businessId: string }) {
  const load = useLoad(() => platform.prepHistory(businessId));
  const undo = useAction((runId: string) => platform.revert(businessId, runId));
  const [undone, setUndone] = useState<Record<string, boolean>>({});
  return (
    <Panel title="Preparation history" note="Every check or change made on this page and the Data Platform pages. Changes that touched your data can be undone.">
      <LoadView load={load} label="Loading history…">
        {({ runs }) =>
          runs.length === 0 ? (
            <p className="text-base text-muted">Nothing has been profiled, cleaned, validated or transformed yet.</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {runs.slice(0, 30).map((r: PrepRun) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-base font-medium text-foreground">
                      {STAGE_WORD[r.stage] ?? r.stage}
                      {r.table ? ` · ${DATA_GROUP_NAME[r.table as keyof typeof DATA_GROUP_NAME] ?? r.table}` : ""}
                      {r.operation && r.operation !== r.stage ? ` · ${r.operation}` : ""}
                    </p>
                    <p className="text-sm text-muted">{timeAgo(r.created_at)}</p>
                    {r.error ? <p className="text-sm text-danger">{r.error}</p> : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone={r.status === "applied" || r.status === "completed" ? "good" : r.status === "reverted" ? "neutral" : "bad"}>{r.status}</Badge>
                    {r.reversible && r.status === "applied" && !undone[r.id] ? (
                      <button
                        className={btnSecondary}
                        disabled={undo.busy}
                        onClick={async () => {
                          if (await undo.run(r.id)) {
                            setUndone((u) => ({ ...u, [r.id]: true }));
                            load.retry();
                          }
                        }}
                      >
                        Undo
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )
        }
      </LoadView>
      <ActionError error={undo.error} />
    </Panel>
  );
}

export default function DataQualityPage() {
  const { business, loading } = useBusiness();
  const load = useLoad(async (id) => {
    const [library, uploads, caps] = await Promise.all([api.getDataLibrary(id), api.getUploads(id), api.getCapabilities(id)]);
    return { library, uploads, caps };
  });

  if (loading) return <Page title="Data Quality History"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Data Quality History" subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  return (
    <Page title="Data Quality History" subtitle="What data you have, whether your uploads passed their checks, every profile, cleaning, validation and transformation you have run, and what the data lets you do." wide>
      <LoadView load={load} label="Checking your data…">
        {({ library, uploads, caps }) => (
          <div className="space-y-6">
            <Panel title="What you have" note="Open any group to preview, correct or delete its rows.">
              <div className="relative overflow-x-auto rounded-xl border border-border">
                <table className="w-full min-w-[520px] text-left text-base">
                  <thead className="bg-muted-surface/60 text-sm text-muted">
                    <tr>
                      <th scope="col" className="px-4 py-2 font-medium">Data</th>
                      <th scope="col" className="px-4 py-2 font-medium">Rows</th>
                      <th scope="col" className="px-4 py-2 font-medium">Last updated</th>
                      <th scope="col" className="px-4 py-2 font-medium"><span className="sr-only">Action</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {library.map((d) => (
                      <tr key={d.type}>
                        <th scope="row" className="px-4 py-2 font-medium text-foreground">{DATA_GROUP_NAME[d.type]}</th>
                        <td className="px-4 py-2">{d.rows > 0 ? d.rows.toLocaleString("en-IN") : <span className="text-warning">Not added yet</span>}</td>
                        <td className="px-4 py-2 text-muted">{d.rows > 0 ? timeAgo(d.last_updated) : "—"}</td>
                        <td className="px-4 py-2 text-right">
                          <Link href={d.rows > 0 ? `/data/${d.type}` : `/data/manual?type=${d.type}`} className="font-medium text-accent underline underline-offset-4">
                            {d.rows > 0 ? "Preview" : "Add"}
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>

            <Panel title="Checks on your uploads" note="Each uploaded file is checked before its rows are kept.">
              {uploads.length === 0 ? (
                <div>
                  <p className="text-base text-foreground">No files have been uploaded. Data you typed in or loaded as examples isn&apos;t listed here.</p>
                  <div className="mt-3"><Link href="/data/upload/file" className={btnSecondary}>Upload a file</Link></div>
                </div>
              ) : (
                <ul className="divide-y divide-border rounded-xl border border-border">
                  {uploads.slice(0, 10).map((u) => {
                    const s = STATUS[u.status] ?? STATUS.processing;
                    const rows = Object.entries(u.summary_json?.rows_ingested ?? {});
                    const notes = qualityNotes(u);
                    return (
                      <li key={u.id} className="px-4 py-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="min-w-0 break-all text-base font-medium text-foreground">{u.filename}</span>
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${s.tone}`}>{s.label}</span>
                        </div>
                        <p className="mt-1 text-sm text-muted">
                          {timeAgo(u.created_at)}
                          {rows.length > 0 ? ` · kept ${rows.map(([k, n]) => `${n.toLocaleString("en-IN")} ${k.replace(/_/g, " ")}`).join(", ")}` : ""}
                        </p>
                        {u.error_message ? <p className="mt-1 text-sm text-danger">{u.error_message}</p> : null}
                        {notes.length > 0 ? <p className="mt-1 text-xs text-muted">{notes.join(" · ")}</p> : null}
                      </li>
                    );
                  })}
                </ul>
              )}
            </Panel>

            <PrepRuns businessId={business.id} />

            <Panel title="What your data lets you do" note="Each analysis switches on when the data it needs is present.">
              <ul className="divide-y divide-border rounded-xl border border-border">
                {caps.capabilities.filter((c) => capabilityName(c.feature) !== null).map((c) => (
                  <li key={c.feature} className="flex flex-wrap items-start justify-between gap-2 px-4 py-3">
                    <div className="min-w-0">
                      <p className="text-base font-medium text-foreground">{capabilityName(c.feature)}</p>
                      {!c.enabled ? <p className="text-sm text-muted">{c.reason}</p> : null}
                    </div>
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${c.enabled ? "bg-success-soft text-success" : "bg-muted-surface text-muted"}`}>
                      {c.enabled ? "Ready" : "Needs more data"}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted">Money &amp; accounts records can be stored, but no analysis reads them yet.</p>
            </Panel>
          </div>
        )}
      </LoadView>
    </Page>
  );
}
