"use client";

import { useState } from "react";
import { platform, type ValidationReport, type ValidationResult } from "@/lib/platform-api";
import { Notice, btnPrimary } from "@/components/simple";
import { Facts, Panel } from "@/components/agent-ui";
import { ActionError, Badge, BulletList, Workspace, useAction } from "@/components/platform-ui";
import { DATA_GROUP_NAME } from "@/lib/features";
import type { DataType } from "@/lib/api";

const TONE = { pass: "good", warn: "warn", fail: "bad", error: "bad" } as const;
const WORD = { pass: "Passed", warn: "Warning", fail: "Failed", error: "Could not run" } as const;
const ORDER = { fail: 0, error: 1, warn: 2, pass: 3 } as const;

function Result({ r }: { r: ValidationResult }) {
  return (
    <li className="rounded-xl border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={TONE[r.status]}>{WORD[r.status]}</Badge>
        <span className="text-base font-medium text-foreground">{r.title}</span>
        <span className="text-sm text-muted">· {DATA_GROUP_NAME[r.table as DataType] ?? r.table}</span>
      </div>
      {r.status !== "pass" ? (
        <>
          <p className="mt-1 text-base text-foreground">
            {r.explanation} {r.affected > 0 ? `(${r.affected.toLocaleString("en-IN")} row(s) affected.)` : ""}
          </p>
          {r.next_step ? <p className="mt-1 text-sm text-muted">What to do: {r.next_step}</p> : null}
        </>
      ) : null}
    </li>
  );
}

function Report({ v }: { v: ValidationReport }) {
  const sorted = [...v.results].sort((a, b) => ORDER[a.status] - ORDER[b.status]);
  const overall = v.overall === "pass" ? "good" : v.overall === "warn" ? "warn" : "bad";
  return (
    <div className="space-y-5">
      <Panel title="Result">
        <p className="mb-3">
          <Badge tone={overall}>{v.overall === "pass" ? "All checks passed" : v.overall === "warn" ? "Passed with warnings" : "Needs attention"}</Badge>
        </p>
        <Facts
          items={[
            { label: "Passed", value: String(v.pass) },
            { label: "Warnings", value: String(v.warn) },
            { label: "Failed", value: String(v.fail) },
            { label: "Could not run", value: String(v.error) },
          ]}
        />
        <p className="mt-3 text-sm text-muted">Rule: {v.rule}</p>
        {v.tables_skipped_empty.length > 0 ? (
          <p className="mt-1 text-sm text-muted">Skipped because they have no rows: {v.tables_skipped_empty.map((t) => DATA_GROUP_NAME[t as DataType] ?? t).join(", ")}.</p>
        ) : null}
      </Panel>
      <ul className="space-y-3">
        {sorted.map((r) => (
          <Result key={r.id} r={r} />
        ))}
      </ul>
    </div>
  );
}

export default function ValidatePage() {
  const [report, setReport] = useState<ValidationReport | null>(null);
  return (
    <Workspace title="Validation" subtitle="Rule checks on your stored data: missing dates, negative amounts, totals that do not add up, broken links between records and more.">
      {(id) => <Body id={id} report={report} setReport={setReport} />}
    </Workspace>
  );
}

function Body({ id, report, setReport }: { id: string; report: ValidationReport | null; setReport: (v: ValidationReport) => void }) {
  const run = useAction(() => platform.validate(id));
  return (
    <div className="space-y-5">
      <Notice tone="info">
        Validation only reads your data. A failed check does not stop other pages from working — it tells you which results may be affected. Each run is saved to Data Quality History.
      </Notice>
      <button
        className={btnPrimary}
        disabled={run.busy}
        onClick={async () => {
          const r = await run.run();
          if (r) setReport(r);
        }}
      >
        {run.busy ? "Checking…" : report ? "Run the checks again" : "Run the checks"}
      </button>
      <ActionError error={run.error} />
      {report ? <Report v={report} /> : <BulletList items={["Press the button to check every kind of data you have added."]} />}
    </div>
  );
}
