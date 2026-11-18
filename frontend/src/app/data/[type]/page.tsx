"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, type CellValue, type DataLibraryEntry, type DataRow, type DataTablePage, type DataType } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { isDemoBusiness } from "@/lib/demo";
import { DATA_GROUP_NAME } from "@/lib/features";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import {
  ConfirmDialog,
  ErrorBox,
  KIND_ICON,
  Notice,
  Page,
  Spinner,
  btnPrimary,
  btnSecondary,
} from "@/components/simple";

const PAGE_SIZE = 25;
const VALID: DataType[] = ["sales", "customers", "products", "inventory", "marketing_campaigns", "finance"];

function inputType(kind: string): string {
  return kind === "date" ? "date" : kind === "number" || kind === "integer" ? "number" : "text";
}

function csvEscape(v: CellValue): string {
  const s = v === null ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export default function DataDetailPage() {
  const params = useParams<{ type: string }>();
  const type = params.type as DataType;
  const { business, loading } = useBusiness();

  const [page, setPage] = useState<DataTablePage | null>(null);
  const [meta, setMeta] = useState<DataLibraryEntry | null>(null);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, CellValue>>({});
  const [saving, setSaving] = useState(false);
  const [rowError, setRowError] = useState<FriendlyError | null>(null);
  const [deleteRow, setDeleteRow] = useState<DataRow | null>(null);
  const [clearAll, setClearAll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const bid = business?.id;

  const load = useCallback(async () => {
    if (!bid || !VALID.includes(type)) return;
    try {
      const [t, lib] = await Promise.all([api.getTable(bid, type, offset, PAGE_SIZE), api.getDataLibrary(bid)]);
      setPage(t);
      setMeta(lib.find((l) => l.type === type) ?? null);
      setError(null);
    } catch (e) {
      setError(friendlyError(e));
    }
  }, [bid, type, offset]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch-on-mount/param-change
    void load();
  }, [load, attempt]);

  if (!VALID.includes(type)) {
    return (
      <Page title="We couldn't find that">
        <Link href="/data" className={btnPrimary}>
          Back to My Data
        </Link>
      </Page>
    );
  }
  if (loading) return <Page title="My Data"><Spinner label="Opening your data…" /></Page>;
  if (!business) {
    return (
      <Page title="My Data">
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business
        </Link>
      </Page>
    );
  }

  const startEdit = (row: DataRow) => {
    setEditingId(row.id);
    setDraft({ ...row.values });
    setRowError(null);
  };

  async function saveEdit(row: DataRow) {
    if (!page) return;
    const changes: Record<string, CellValue> = {};
    for (const c of page.columns) {
      if (!c.editable) continue;
      const before = row.values[c.key] ?? null;
      const now = draft[c.key] === "" ? null : (draft[c.key] ?? null);
      if (String(before ?? "") !== String(now ?? "")) changes[c.key] = now;
    }
    if (Object.keys(changes).length === 0) {
      setEditingId(null);
      return;
    }
    setSaving(true);
    setRowError(null);
    try {
      const updated = await api.updateRow(business!.id, type, row.id, changes);
      setPage((p) => (p ? { ...p, rows: p.rows.map((r) => (r.id === row.id ? updated : r)) } : p));
      setEditingId(null);
    } catch (e) {
      setRowError(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  async function confirmDelete() {
    if (!deleteRow) return;
    setBusy(true);
    try {
      await api.deleteRow(business!.id, type, deleteRow.id);
      setDeleteRow(null);
      if (page && page.rows.length === 1 && offset > 0) setOffset(Math.max(0, offset - PAGE_SIZE));
      else setAttempt((n) => n + 1);
    } catch (e) {
      setError(friendlyError(e));
      setDeleteRow(null);
    } finally {
      setBusy(false);
    }
  }

  async function confirmClear() {
    setBusy(true);
    try {
      await api.clearTable(business!.id, type);
      setClearAll(false);
      setOffset(0);
      setAttempt((n) => n + 1);
    } catch (e) {
      setError(friendlyError(e));
      setClearAll(false);
    } finally {
      setBusy(false);
    }
  }

  async function download() {
    if (!page) return;
    setBusy(true);
    try {
      const lines = [page.columns.map((c) => csvEscape(c.label)).join(",")];
      for (let off = 0; off < page.total; off += 200) {
        const chunk = await api.getTable(business!.id, type, off, 200);
        for (const r of chunk.rows) lines.push(page.columns.map((c) => csvEscape(r.values[c.key] ?? null)).join(","));
      }
      const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `${type}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  const total = page?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);

  return (
    <Page
      title={`${KIND_ICON[type] ?? ""} ${DATA_GROUP_NAME[type] ?? page?.title ?? "My Data"}`.trim()}
      subtitle={page?.description}
      wide
      action={
        <Link href="/data" className={btnSecondary}>
          ← All my data
        </Link>
      }
    >
      {error ? <div className="mb-6"><ErrorBox error={error} onRetry={() => setAttempt((n) => n + 1)} /></div> : null}
      {!page && !error ? <Spinner label="Looking at your data…" /> : null}

      {page ? (
        <>
          <dl className="mb-6 grid grid-cols-2 gap-4 rounded-2xl border border-border bg-surface p-5 sm:grid-cols-4">
            <div><dt className="text-sm text-muted">Rows</dt><dd className="text-xl font-semibold">{total.toLocaleString("en-IN")}</dd></div>
            <div><dt className="text-sm text-muted">Columns</dt><dd className="text-xl font-semibold">{page.columns.length}</dd></div>
            <div><dt className="text-sm text-muted">Last updated</dt><dd className="text-xl font-semibold">{timeAgo(meta?.last_updated)}</dd></div>
            <div>
              <dt className="text-sm text-muted">Came from</dt>
              <dd className="break-words text-base font-medium">
                {total === 0 ? "—" : meta?.source_files.length ? meta.source_files.map((f) => f.filename).join(", ") : isDemoBusiness(business) ? "Demo data — not real" : "Entered by hand"}
              </dd>
            </div>
          </dl>

          <div className="mb-4 flex flex-wrap gap-3">
            <Link href={`/data/manual?type=${type}`} className={btnPrimary}>
              + Add rows
            </Link>
            <Link href="/data/upload/file" className={btnSecondary}>
              Add from a file
            </Link>
            <button type="button" onClick={download} disabled={busy || total === 0} className={btnSecondary}>
              Download as spreadsheet
            </button>
          </div>

          {type === "sales" ? (
            <p className="mb-4 text-sm text-muted">
              When you change the quantity, price or discount of a sale, its total is recalculated for you. The product and
              customer of an existing sale can&apos;t be changed here — delete the row and add it again instead.
            </p>
          ) : null}

          {total === 0 ? (
            <Notice title="Nothing here yet">
              Add some rows by hand or upload a file, and they&apos;ll show up here.
            </Notice>
          ) : (
            <div className="relative overflow-x-auto rounded-2xl border border-border bg-surface" tabIndex={0} aria-label={`${page.title} table, scrolls sideways`}>
              <table className="w-full text-left text-base">
                <thead>
                  <tr className="border-b border-border bg-muted-surface/60 text-muted">
                    {page.columns.map((c) => (
                      <th key={c.key} scope="col" className="whitespace-nowrap px-4 py-3 font-medium">{c.label}</th>
                    ))}
                    <th scope="col" className="px-4 py-3 font-medium"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {page.rows.map((r) => {
                    const editing = editingId === r.id;
                    return (
                      <tr key={r.id} className="border-b border-border align-top last:border-0">
                        {page.columns.map((c) => (
                          <td key={c.key} className="whitespace-nowrap px-4 py-3">
                            {editing && c.editable ? (
                              <input
                                aria-label={c.label}
                                type={inputType(c.kind)}
                                step={c.kind === "number" ? "any" : c.kind === "integer" ? 1 : undefined}
                                value={draft[c.key] ?? ""}
                                onChange={(e) => setDraft((d) => ({ ...d, [c.key]: e.target.value }))}
                                className="input min-w-[8rem]"
                              />
                            ) : r.values[c.key] === null || r.values[c.key] === undefined ? (
                              <span className="text-muted">—</span>
                            ) : (
                              String(r.values[c.key])
                            )}
                          </td>
                        ))}
                        <td className="whitespace-nowrap px-4 py-3">
                          {editing ? (
                            <div className="flex gap-2">
                              <button type="button" onClick={() => saveEdit(r)} disabled={saving} className={btnPrimary}>
                                {saving ? "Saving…" : "Save"}
                              </button>
                              <button type="button" onClick={() => setEditingId(null)} disabled={saving} className={btnSecondary}>
                                Cancel
                              </button>
                            </div>
                          ) : (
                            <div className="flex gap-2">
                              <button type="button" onClick={() => startEdit(r)} className={btnSecondary} aria-label="Edit this row">
                                Edit
                              </button>
                              <button type="button" onClick={() => setDeleteRow(r)} className={btnSecondary} aria-label="Delete this row">
                                Delete
                              </button>
                            </div>
                          )}
                          {editing && rowError ? <p role="alert" className="mt-2 max-w-xs whitespace-normal text-sm text-danger">{rowError.message}</p> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {total > 0 ? (
            <nav aria-label="Pages" className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className="text-base text-muted">
                Showing {from.toLocaleString("en-IN")}–{to.toLocaleString("en-IN")} of {total.toLocaleString("en-IN")}
              </p>
              <div className="flex gap-3">
                <button type="button" className={btnSecondary} disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                  ← Previous
                </button>
                <button type="button" className={btnSecondary} disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>
                  Next →
                </button>
              </div>
            </nav>
          ) : null}

          {total > 0 ? (
            <section id="remove-data" className="mt-12 scroll-mt-6 rounded-2xl border border-danger/30 p-5">
              <h2 className="text-lg font-semibold text-foreground">Remove data</h2>
              <p className="mt-1 text-base text-muted">This removes every row of {page.title.toLowerCase()} from your account. To replace it with something new, remove it here first, then add the new data.</p>
              <button type="button" onClick={() => setClearAll(true)} className="mt-3 inline-flex min-h-[48px] items-center rounded-full border border-danger px-6 py-3 text-base font-medium text-danger hover:bg-danger-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger">
                Remove all {page.title.toLowerCase()} data…
              </button>
            </section>
          ) : null}
        </>
      ) : null}

      <ConfirmDialog
        open={deleteRow !== null}
        title="Delete this row?"
        body="This will permanently remove this row. This can't be undone."
        confirmLabel="Delete"
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteRow(null)}
      />
      <ConfirmDialog
        open={clearAll}
        title="Remove this data?"
        body={`This will permanently remove all ${total.toLocaleString("en-IN")} rows of ${page?.title.toLowerCase() ?? "this data"}. This can't be undone.`}
        confirmLabel="Remove everything"
        busy={busy}
        onConfirm={confirmClear}
        onCancel={() => setClearAll(false)}
      />
    </Page>
  );
}
