"use client";

import Link from "next/link";
import { useState } from "react";
import { platform, type Anchor, type SavedReportMeta } from "@/lib/platform-api";
import { ConfirmDialog, Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, PeriodPicker, Workspace, inputCls, useAction } from "@/components/platform-ui";
import { timeAgo } from "@/lib/friendly";

function Generate({ id, onCreated }: { id: string; onCreated: (r: SavedReportMeta) => void }) {
  const types = useLoad(() => platform.reportTypes(id));
  const [type, setType] = useState("performance");
  const [days, setDays] = useState(30);
  const [anchor, setAnchor] = useState<Anchor>("today");
  const make = useAction(() => platform.createReport(id, type, days, anchor));
  return (
    <Panel title="Create a report" note="A report is a snapshot: it is saved exactly as generated and does not change when your data does.">
      <LoadView load={types} label="Loading report types…">
        {({ types: list }) => (
          <div className="space-y-4">
            <label className="block text-sm font-medium text-foreground">
              Report
              <select value={type} onChange={(e) => setType(e.target.value)} className={`${inputCls} max-w-md`}>
                {list.map((t) => (
                  <option key={t.key} value={t.key}>
                    {t.title}
                  </option>
                ))}
              </select>
            </label>
            <PeriodPicker days={days} anchor={anchor} onChange={(d, a) => { setDays(d); setAnchor(a); }} options={[7, 30, 90]} />
            <button
              className={btnPrimary}
              disabled={make.busy}
              onClick={async () => {
                const r = await make.run();
                if (r) onCreated(r);
              }}
            >
              {make.busy ? "Creating…" : "Create and save report"}
            </button>
            <ActionError error={make.error} />
          </div>
        )}
      </LoadView>
    </Panel>
  );
}

function Saved({ id }: { id: string }) {
  const load = useLoad(() => platform.reports(id));
  const [del, setDel] = useState<SavedReportMeta | null>(null);
  const rm = useAction((rid: string) => platform.deleteReport(id, rid));
  return (
    <Panel title="Saved reports">
      <LoadView load={load} label="Loading your reports…">
        {({ reports }) =>
          reports.length === 0 ? (
            <p className="text-base text-muted">No reports yet. Create one above.</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {reports.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-base font-medium text-foreground">{r.title}</p>
                    <p className="text-sm text-muted">
                      {r.period_start} to {r.period_end} · saved {timeAgo(r.created_at)}
                    </p>
                    <p className="text-sm text-foreground">{r.summary}</p>
                  </div>
                  <div className="flex gap-2">
                    <Link href={`/reports/view?id=${r.id}`} className={btnSecondary}>
                      Open
                    </Link>
                    <button className={btnSecondary} onClick={() => setDel(r)}>
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )
        }
      </LoadView>
      <ActionError error={rm.error} />
      <ConfirmDialog
        open={del !== null}
        title="Delete this report?"
        body={<p>“{del?.title}” will be removed permanently. Your data is not affected.</p>}
        confirmLabel="Delete report"
        busy={rm.busy}
        onCancel={() => setDel(null)}
        onConfirm={async () => {
          if (del) {
            await rm.run(del.id);
            setDel(null);
            load.retry();
          }
        }}
      />
    </Panel>
  );
}

export default function ReportsPage() {
  const [version, setVersion] = useState(0);
  return (
    <Workspace title="Reports" subtitle="Generate a report from your data, keep it, and open it again later exactly as it was.">
      {(id) => (
        <div className="space-y-6">
          <Notice tone="info">
            Reports describe what your records show. They can be printed or saved as PDF from the browser&apos;s print dialog when you open one. Your earlier chat answers and recommendations are in{" "}
            <Link href="/reports/answers" className="font-medium underline underline-offset-4">
              Saved Answers
            </Link>
            .
          </Notice>
          <Generate id={id} onCreated={() => setVersion((n) => n + 1)} />
          <Saved key={version} id={id} />
        </div>
      )}
    </Workspace>
  );
}
