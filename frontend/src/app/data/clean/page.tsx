"use client";

import { useState } from "react";
import { platform, type CleaningProposal } from "@/lib/platform-api";
import { ConfirmDialog, Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, Badge, DataTable, Workspace, useAction } from "@/components/platform-ui";
import { TablePicker } from "@/components/table-picker";

const KIND: Record<string, string> = {
  trim_whitespace: "Extra spaces",
  standardise_categories: "Inconsistent spelling",
  exact_duplicates: "Exact duplicates",
  invalid_rows: "Invalid values",
  missing_values: "Missing values",
};

const cell = (v: unknown) => (v === null || v === undefined ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

function PreviewBlock({ p }: { p: CleaningProposal }) {
  const beforeAfter = p.preview.every((r) => "before" in r && "after" in r);
  const removes = p.kind === "exact_duplicates";
  const keys = beforeAfter ? [] : Object.keys(p.preview[0]).filter((k) => !k.startsWith("_"));
  return (
    <div className="mt-3">
      <p className="mb-1 text-sm font-semibold text-muted">
        {beforeAfter ? `Preview of the change (first ${p.preview.length})` : removes ? `Rows that would be removed (first ${p.preview.length}); the first copy of each stays` : `Rows affected (first ${p.preview.length})`}
      </p>
      {beforeAfter ? (
        <DataTable caption="Preview of the change" columns={["Before", "After"]} rows={p.preview.map((r) => [cell(r.before), cell(r.after)])} />
      ) : (
        <DataTable caption="Rows affected" columns={keys} rows={p.preview.map((r) => keys.map((k) => cell(r[k])))} />
      )}
    </div>
  );
}

function Proposal({ businessId, p, onChanged }: { businessId: string; p: CleaningProposal; onChanged: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<{ runId: string; rows: number } | null>(null);
  const [undone, setUndone] = useState(false);
  const apply = useAction(() => platform.applyCleaning(businessId, p.id, true));
  const undo = useAction((runId: string) => platform.revert(businessId, runId));
  return (
    <li className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={p.can_apply ? "warn" : "neutral"}>{KIND[p.kind] ?? p.kind}</Badge>
        <h3 className="text-lg font-semibold text-foreground">{p.issue}</h3>
      </div>
      <p className="mt-2 text-base text-foreground">{p.action}</p>
      <p className="mt-1 text-sm text-muted">
        Would touch {p.affected_rows.toLocaleString("en-IN")} row(s), {p.affected_cells.toLocaleString("en-IN")} value(s). Risk: {p.risk}
      </p>
      {p.preview.length > 0 ? <PreviewBlock p={p} /> : null}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {p.can_apply && !done && !p.applied ? (
          <button className={btnPrimary} disabled={apply.busy} onClick={() => setConfirming(true)}>
            Review and apply…
          </button>
        ) : null}
        {!p.can_apply ? <span className="text-sm text-muted">This needs your judgement, so it is not applied automatically.</span> : null}
        {p.applied && !done ? <Badge tone="good">Already applied</Badge> : null}
        {done && !undone ? (
          <>
            <Badge tone="good">Applied to {done.rows} row(s)</Badge>
            <button
              className={btnSecondary}
              disabled={undo.busy}
              onClick={async () => {
                if (await undo.run(done.runId)) {
                  setUndone(true);
                  onChanged();
                }
              }}
            >
              Undo this change
            </button>
          </>
        ) : null}
        {undone ? <Badge tone="neutral">Undone — your data is back as it was</Badge> : null}
      </div>
      <div className="mt-2">
        <ActionError error={apply.error ?? undo.error} />
      </div>
      <ConfirmDialog
        open={confirming}
        title="Change your stored data?"
        body={
          <p>
            This will change {p.affected_rows.toLocaleString("en-IN")} row(s) in your stored data: {p.action} The change is recorded and can be undone from this page or from Data Quality History.
          </p>
        }
        confirmLabel="Yes, apply the change"
        busy={apply.busy}
        onCancel={() => setConfirming(false)}
        onConfirm={async () => {
          const r = await apply.run();
          setConfirming(false);
          if (r) {
            setDone({ runId: r.id, rows: r.affected_rows });
            onChanged();
          }
        }}
      />
    </li>
  );
}

function Body({ businessId, table }: { businessId: string; table: string }) {
  const load = useLoad(() => platform.cleaning(businessId, table));
  return (
    <LoadView load={load} label="Looking for things to clean…">
      {({ proposals }) =>
        proposals.length === 0 ? (
          <Notice tone="success" title="Nothing to clean here">
            No extra spaces, exact duplicates, invalid values or capitalisation differences were found in this data.
          </Notice>
        ) : (
          <ul className="space-y-4">
            {proposals.map((p) => (
              <Proposal key={p.id} businessId={businessId} p={p} onChanged={() => undefined} />
            ))}
          </ul>
        )
      }
    </LoadView>
  );
}

export default function CleanPage() {
  const [table, setTable] = useState("sales");
  return (
    <Workspace title="Cleaning" subtitle="DecisionGPT finds problems and shows exactly what a fix would change. Nothing changes until you confirm, and every change can be undone.">
      {(id) => (
        <div className="space-y-6">
          <Notice tone="info">
            Missing values are never filled in automatically — a guess would look like data you recorded. Customers and products are not changed here because other records point to them.
          </Notice>
          <Panel title="What to clean">
            <TablePicker value={table} onChange={setTable} />
          </Panel>
          <Body key={`${id}-${table}`} businessId={id} table={table} />
        </div>
      )}
    </Workspace>
  );
}

