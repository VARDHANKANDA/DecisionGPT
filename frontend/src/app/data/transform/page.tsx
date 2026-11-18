"use client";

import { useState } from "react";
import { DATA_GROUP_NAME } from "@/lib/features";
import type { DataType } from "@/lib/api";
import { platform, type TransformOption, type TransformPreview } from "@/lib/platform-api";
import { ConfirmDialog, Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, Badge, BulletList, DataTable, Workspace, inputCls, useAction } from "@/components/platform-ui";

function parseMapping(text: string): Record<string, string> | null {
  const out: Record<string, string> = {};
  for (const line of text.split("\n")) {
    if (!line.trim()) continue;
    const m = line.split("=>");
    if (m.length !== 2 || !m[0].trim() || !m[1].trim()) return null;
    out[m[0].trim()] = m[1].trim();
  }
  return Object.keys(out).length ? out : null;
}

function Option({ businessId, o }: { businessId: string; o: TransformOption }) {
  const [style, setStyle] = useState(o.styles?.[0] ?? "title");
  const [mapText, setMapText] = useState("");
  const [by, setBy] = useState("month");
  const [preview, setPreview] = useState<TransformPreview | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [done, setDone] = useState<{ id: string; rows: number } | null>(null);
  const [undone, setUndone] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const body = (): Record<string, unknown> | null => {
    const base: Record<string, unknown> = { id: o.id, kind: o.kind, table: o.table };
    if (o.column) base.column = o.column;
    if (o.kind === "standardise_style") base.style = style;
    if (o.kind === "aggregate_preview") base.by = by;
    if (o.kind === "map_values") {
      const m = parseMapping(mapText);
      if (!m) {
        setFormError("Write one rename per line in the form  old value => new value.");
        return null;
      }
      base.mapping = m;
    }
    setFormError(null);
    return base;
  };
  const prev = useAction(async () => {
    const b = body();
    if (!b) return undefined;
    setDone(null);
    setUndone(false);
    const r = await platform.transformPreview(businessId, b);
    setPreview(r);
    return r;
  });
  const apply = useAction(async () => {
    const b = body();
    if (!b) return undefined;
    return platform.transformApply(businessId, b, true);
  });
  const undo = useAction((runId: string) => platform.revert(businessId, runId));

  return (
    <li className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={o.kind === "aggregate_preview" ? "neutral" : "warn"}>{o.kind === "aggregate_preview" ? "Read-only" : "Changes data"}</Badge>
        <h3 className="text-lg font-semibold text-foreground">{o.title}</h3>
        <span className="text-sm text-muted">in {DATA_GROUP_NAME[o.table as DataType] ?? o.table}</span>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-3">
        {o.kind === "standardise_style" ? (
          <label className="block text-sm font-medium text-foreground">
            Style
            <select value={style} onChange={(e) => setStyle(e.target.value)} className={inputCls}>
              {(o.styles ?? []).map((s) => (
                <option key={s} value={s}>
                  {s === "title" ? "Title Case" : s === "upper" ? "UPPER CASE" : "lower case"}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {o.kind === "aggregate_preview" ? (
          <label className="block text-sm font-medium text-foreground">
            Group by
            <select value={by} onChange={(e) => setBy(e.target.value)} className={inputCls}>
              <option value="day">Day</option>
              <option value="week">Week</option>
              <option value="month">Month</option>
            </select>
          </label>
        ) : null}
        {o.kind === "map_values" ? (
          <label className="block w-full text-sm font-medium text-foreground">
            Renames (one per line, <code>old =&gt; new</code>)
            <textarea value={mapText} onChange={(e) => setMapText(e.target.value)} rows={3} maxLength={2000} className={inputCls} />
          </label>
        ) : null}
        <button className={btnSecondary} disabled={prev.busy} onClick={() => prev.run()}>
          Preview
        </button>
      </div>
      {formError ? <p className="mt-2 text-base text-danger">{formError}</p> : null}
      <div className="mt-2">
        <ActionError error={prev.error ?? apply.error ?? undo.error} />
      </div>

      {preview && o.kind === "aggregate_preview" && preview.rows ? (
        <div className="mt-3">
          {preview.rows.length === 0 ? (
            <p className="text-base text-muted">{preview.note ?? "No sales to total."}</p>
          ) : (
            <DataTable caption="Totals" columns={["Period", "Sales", "Units", "Records"]} rows={preview.rows.map((r) => [r.period, `₹${Math.round(r.sales).toLocaleString("en-IN")}`, r.units, r.records])} />
          )}
          <p className="mt-1 text-sm text-muted">A view only. Nothing is stored or changed.</p>
        </div>
      ) : null}

      {preview && o.kind !== "aggregate_preview" ? (
        <div className="mt-3 space-y-2">
          <p className="text-base text-foreground">
            {preview.affected_rows ? `${preview.affected_rows.toLocaleString("en-IN")} row(s) would change.` : "Nothing would change."}
          </p>
          {preview.preview && preview.preview.length > 0 ? (
            <DataTable caption="Preview of the change" columns={["Before", "After"]} rows={preview.preview.map((r) => [String(r.before ?? ""), String(r.after ?? "")])} />
          ) : null}
          {preview.risk ? <p className="text-sm text-muted">{preview.risk}</p> : null}
          <div className="flex flex-wrap items-center gap-3">
            {preview.can_apply && !done ? (
              <button className={btnPrimary} disabled={apply.busy} onClick={() => setConfirming(true)}>
                Apply…
              </button>
            ) : null}
            {done && !undone ? (
              <>
                <Badge tone="good">Applied to {done.rows} row(s)</Badge>
                <button
                  className={btnSecondary}
                  disabled={undo.busy}
                  onClick={async () => {
                    if (await undo.run(done.id)) setUndone(true);
                  }}
                >
                  Undo this change
                </button>
              </>
            ) : null}
            {undone ? <Badge tone="neutral">Undone</Badge> : null}
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirming}
        title="Change your stored data?"
        body={<p>{o.title}. {preview?.affected_rows ?? 0} row(s) will change. A validation runs afterwards; if it finds new failed checks the change is undone automatically. You can also undo it later.</p>}
        confirmLabel="Yes, apply it"
        busy={apply.busy}
        onCancel={() => setConfirming(false)}
        onConfirm={async () => {
          const r = await apply.run();
          setConfirming(false);
          if (r) setDone({ id: r.id, rows: r.affected_rows });
        }}
      />
    </li>
  );
}

function Body({ id }: { id: string }) {
  const load = useLoad(() => platform.transformOptions(id));
  return (
    <LoadView load={load} label="Loading transformations…">
      {({ options, not_available }) => (
        <div className="space-y-6">
          {options.length === 0 ? <Notice tone="info">No transformation applies to your data yet.</Notice> : null}
          <ul className="space-y-4">
            {options.map((o) => (
              <Option key={o.id} businessId={id} o={o} />
            ))}
          </ul>
          <Panel title="What is not available" note="These are deliberately left out. Free-form code or SQL is never run.">
            <BulletList items={not_available} />
          </Panel>
        </div>
      )}
    </LoadView>
  );
}

export default function TransformPage() {
  return (
    <Workspace title="Transformation" subtitle="Fixed, safe changes to prepare data for analysis: consistent capitalisation, renamed categories, recalculated totals and read-only summaries.">
      {(id) => <Body id={id} />}
    </Workspace>
  );
}
