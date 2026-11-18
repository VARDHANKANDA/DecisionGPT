"use client";

import { useState } from "react";
import { platform, type DataProfile } from "@/lib/platform-api";
import { Notice, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad, Facts } from "@/components/agent-ui";
import { ActionError, BulletList, DataTable, Workspace, useAction } from "@/components/platform-ui";
import { TablePicker } from "@/components/table-picker";

function Columns({ p }: { p: DataProfile }) {
  return (
    <DataTable
      caption="Column profile"
      columns={["Column", "Type found", "Missing", "Distinct values", "Range or common values"]}
      rows={p.column_profiles.map((c) => [
        c.label,
        c.inferred_type,
        `${c.missing} (${c.missing_pct.toFixed(1)}%)`,
        c.unique,
        c.date_min
          ? `${c.date_min} to ${c.date_max}${c.unparseable ? ` · ${c.unparseable} unreadable` : ""}`
          : c.min !== undefined
            ? `${c.min} to ${c.max} · mean ${c.mean !== undefined ? Number(c.mean).toFixed(2) : "—"}`
            : (c.top_values ?? []).slice(0, 3).map((t) => `${t.value} (${t.count})`).join(", ") || "—",
      ])}
    />
  );
}

function Rows({ businessId, table, page, query, onPage }: { businessId: string; table: string; page: number; query: string; onPage: (n: number) => void }) {
  const preview = useLoad(() => platform.preview(businessId, table, page * 10, 10, query));
  return (
    <LoadView load={preview} label="Loading rows…">
      {(pg) =>
        pg.rows.length === 0 ? (
          <p className="text-base text-muted">No rows to show.</p>
        ) : (
          <>
            <DataTable columns={pg.columns.map((c) => c.label)} rows={pg.rows.map((r) => pg.columns.map((c) => r.values[c.key] ?? null))} caption="Rows" />
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted">
              <button className={btnSecondary} disabled={page === 0} onClick={() => onPage(page - 1)}>
                Previous
              </button>
              <span>
                {pg.offset + 1}–{Math.min(pg.offset + pg.limit, pg.total)} of {pg.total.toLocaleString("en-IN")}
              </span>
              <button className={btnSecondary} disabled={pg.offset + pg.limit >= pg.total} onClick={() => onPage(page + 1)}>
                Next
              </button>
            </div>
          </>
        )
      }
    </LoadView>
  );
}

function Body({ businessId, table }: { businessId: string; table: string }) {
  const [version, setVersion] = useState(0);
  const load = useLoad(() => platform.profile(businessId, table));
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const save = useAction(() => platform.profile(businessId, table, true));
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-6">
      <LoadView load={load} label="Profiling your data…">
        {(p) => (
          <>
            <Facts
              items={[
                { label: "Rows", value: p.rows.toLocaleString("en-IN") },
                { label: "Columns", value: String(p.columns) },
                { label: "Exact duplicate rows", value: String(p.duplicate_rows) },
                { label: "Possible outlier columns", value: String(p.outlier_candidates.length), hint: "Unusual values to look at, not errors." },
              ]}
            />
            {p.rows === 0 ? <Notice tone="info">There are no rows of this kind yet. Add or upload data first.</Notice> : null}
            <Panel title="Columns" note="Measured on the rows currently stored, nothing estimated.">
              <Columns p={p} />
            </Panel>
            {p.invalid_or_inconsistent.length > 0 ? (
              <Panel title="Values that look wrong" note="Rule-based checks. Each shows how many rows it affects.">
                <DataTable columns={["Check", "Rows affected", "Why it matters"]} rows={p.invalid_or_inconsistent.map((i) => [i.title, i.count, i.explanation])} />
              </Panel>
            ) : null}
            {p.outlier_candidates.length > 0 ? (
              <Panel title="Unusual values" note="Flagged with the interquartile-range rule. Unusual does not mean wrong.">
                <DataTable columns={["Column", "Rows flagged", "Normal range used"]} rows={p.outlier_candidates.map((o) => [o.label, o.candidates, `${o.lower_bound} to ${o.upper_bound}`])} />
              </Panel>
            ) : null}
            <BulletList title="Limits of this profile" items={p.limitations} />
            <div className="flex flex-wrap items-center gap-3">
              <button
                className={btnSecondary}
                disabled={save.busy}
                onClick={async () => {
                  if (await save.run()) setSaved(true);
                }}
              >
                Save this profile to history
              </button>
              {saved ? <span className="text-base text-success">Saved to Data Quality History.</span> : null}
            </div>
            <ActionError error={save.error} />
          </>
        )}
      </LoadView>

      <Panel title="Look at the rows" note="Read-only preview. Edit or delete rows in Upload & Manage Data.">
        <form
          className="mb-3 flex flex-wrap items-end gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(0);
            setQuery(search.trim());
            setVersion((n) => n + 1);
          }}
        >
          <label className="block text-sm font-medium text-foreground">
            Search
            <input value={search} onChange={(e) => setSearch(e.target.value)} maxLength={100} className="mt-1 block min-h-[44px] rounded-lg border border-border bg-surface px-3 text-base" />
          </label>
          <button className={btnSecondary} type="submit">
            Search
          </button>
        </form>
        <Rows key={`${version}-${page}-${query}`} businessId={businessId} table={table} page={page} query={query} onPage={setPage} />
      </Panel>
    </div>
  );
}

export default function ProfilePage() {
  const [table, setTable] = useState("sales");
  return (
    <Workspace title="Inspection & Profiling" subtitle="See what is actually in your data: how complete each column is, what ranges it covers, duplicates and unusual values.">
      {(id) => (
        <div className="space-y-6">
          <TablePicker value={table} onChange={setTable} />
          <Body key={`${id}-${table}`} businessId={id} table={table} />
        </div>
      )}
    </Workspace>
  );
}
