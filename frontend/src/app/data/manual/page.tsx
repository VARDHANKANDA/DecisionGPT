"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";
import { api, type CellValue, type DataType } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { ErrorBox, KIND_ICON, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";

interface FieldDef {
  key: string;
  label: string;
  kind: "text" | "number" | "integer" | "date";
  required?: boolean;
  hint?: string;
  /** shown from the start; otherwise offered under "+ Add another detail" */
  base?: boolean;
}

interface KindDef {
  title: string;
  blurb: string;
  fields: FieldDef[];
}

// Field keys are the names the backend understands; the labels are what people see.
const KINDS: Record<DataType, KindDef> = {
  sales: {
    title: "Sales",
    blurb: "Each row is one sale.",
    fields: [
      { key: "sale_date", label: "Date", kind: "date", required: true, base: true },
      { key: "product", label: "Product ID", kind: "text", base: true, hint: "The ID from your product list" },
      { key: "quantity", label: "Quantity", kind: "integer", required: true, base: true },
      { key: "unit_price", label: "Price each (₹)", kind: "number", required: true, base: true },
      { key: "customer", label: "Customer ID", kind: "text", hint: "Optional" },
      { key: "discount", label: "Discount (₹)", kind: "number", hint: "Optional" },
      { key: "revenue", label: "Total (₹)", kind: "number", hint: "Leave empty to calculate it for you" },
    ],
  },
  customers: {
    title: "Customers",
    blurb: "Each row is one customer.",
    fields: [
      { key: "external_customer_id", label: "Customer ID", kind: "text", required: true, base: true },
      { key: "first_purchase_date", label: "First purchase", kind: "date", base: true },
      { key: "last_purchase_date", label: "Last purchase", kind: "date", base: true },
      { key: "purchase_frequency", label: "Times bought", kind: "number", base: true },
      { key: "monetary_value", label: "Total spent (₹)", kind: "number", base: true },
      { key: "segment", label: "Group", kind: "text", hint: "For example New or Regular" },
    ],
  },
  products: {
    title: "Products",
    blurb: "Each row is something you sell.",
    fields: [
      { key: "external_product_id", label: "Product ID", kind: "text", required: true, base: true },
      { key: "name", label: "Name", kind: "text", required: true, base: true },
      { key: "selling_price", label: "Selling price (₹)", kind: "number", required: true, base: true },
      { key: "stock_quantity", label: "In stock", kind: "integer", base: true },
      { key: "unit_cost", label: "Cost each (₹)", kind: "number" },
      { key: "category", label: "Category", kind: "text" },
    ],
  },
  inventory: {
    title: "Stock levels",
    blurb: "Each row is a stock count for one product on one day.",
    fields: [
      { key: "date", label: "Date", kind: "date", required: true, base: true },
      { key: "product", label: "Product ID", kind: "text", required: true, base: true },
      { key: "stock_level", label: "In stock", kind: "integer", required: true, base: true },
      { key: "reorder_level", label: "Reorder at", kind: "integer" },
    ],
  },
  marketing_campaigns: {
    title: "Marketing",
    blurb: "Each row is money spent on advertising.",
    fields: [
      { key: "campaign_date", label: "Date", kind: "date", required: true, base: true },
      { key: "channel", label: "Where (e.g. Instagram)", kind: "text", required: true, base: true },
      { key: "spend", label: "Spent (₹)", kind: "number", required: true, base: true },
      { key: "campaign_name", label: "Campaign name", kind: "text" },
      { key: "clicks", label: "Clicks", kind: "integer" },
      { key: "conversions", label: "Orders", kind: "integer" },
      { key: "attributed_revenue", label: "Sales from it (₹)", kind: "number" },
      { key: "impressions", label: "Times shown", kind: "integer" },
    ],
  },
  finance: {
    title: "Money & accounts",
    blurb: "Each row is one month of money figures.",
    fields: [
      { key: "period_date", label: "Month (a date in it)", kind: "date", required: true, base: true },
      { key: "revenue", label: "Income (₹)", kind: "number", base: true },
      { key: "cogs", label: "Cost of goods (₹)", kind: "number", base: true },
      { key: "operating_expenses", label: "Running costs (₹)", kind: "number", base: true },
      { key: "net_profit", label: "Profit (₹)", kind: "number", base: true },
      { key: "cash_balance", label: "Cash in hand (₹)", kind: "number" },
    ],
  },
};

type Row = Record<string, string>;
const blankRow = (): Row => ({});
const inputType = (k: FieldDef["kind"]) => (k === "date" ? "date" : k === "number" || k === "integer" ? "number" : "text");

function ManualEntry() {
  const search = useSearchParams();
  const { business, loading } = useBusiness();
  const initial = search.get("type") as DataType | null;
  const [type, setType] = useState<DataType | null>(initial && KINDS[initial] ? initial : null);
  const [rows, setRows] = useState<Row[]>([blankRow(), blankRow(), blankRow()]);
  const [extra, setExtra] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [productIds, setProductIds] = useState<Set<string>>(new Set());

  const kind = type ? KINDS[type] : null;
  const visible = useMemo(
    () => (kind ? kind.fields.filter((f) => f.base || extra.includes(f.key)) : []),
    [kind, extra],
  );
  const optional = kind ? kind.fields.filter((f) => !f.base && !extra.includes(f.key)) : [];
  const needsProducts = type === "sales" || type === "inventory";

  useEffect(() => {
    if (!business || !needsProducts) return;
    api
      .getTable(business.id, "products", 0, 200)
      .then((t) => setProductIds(new Set(t.rows.map((r) => String(r.values.external_product_id)))))
      .catch(() => undefined);
  }, [business, needsProducts]);

  function pick(t: DataType) {
    setType(t);
    setRows([blankRow(), blankRow(), blankRow()]);
    setExtra([]);
    setSaved(null);
    setError(null);
  }

  const setCell = (ri: number, key: string, v: string) =>
    setRows((rs) => rs.map((r, i) => (i === ri ? { ...r, [key]: v } : r)));

  function onPaste(e: React.ClipboardEvent, ri: number, ci: number) {
    const text = e.clipboardData.getData("text");
    if (!/[\t\n]/.test(text)) return; // single value: let the browser paste normally
    e.preventDefault();
    const grid = text.replace(/\r/g, "").split("\n").filter((l, i, a) => l !== "" || i < a.length - 1).map((l) => l.split("\t"));
    setRows((rs) => {
      const next = rs.map((r) => ({ ...r }));
      grid.forEach((cells, gi) => {
        while (next.length <= ri + gi) next.push(blankRow());
        cells.forEach((v, gj) => {
          const f = visible[ci + gj];
          if (f) next[ri + gi][f.key] = v.trim();
        });
      });
      return next;
    });
  }

  const filled = rows.filter((r) => Object.values(r).some((v) => v.trim() !== ""));

  async function save() {
    if (!business || !type) return;
    if (filled.length === 0) {
      setError({ message: "Please fill in at least one row first.", technical: "no rows" });
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, CellValue>[] = filled.map((r) =>
        Object.fromEntries(Object.entries(r).filter(([, v]) => v.trim() !== "").map(([k, v]) => [k, v.trim()])),
      );
      const res = await api.addRows(business.id, type, payload);
      setSaved(res.added);
      setRows([blankRow(), blankRow(), blankRow()]);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <Page title="Enter data manually"><Spinner label="Opening…" /></Page>;
  if (!business) {
    return (
      <Page title="Enter data manually">
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business first
        </Link>
      </Page>
    );
  }

  if (!type || !kind) {
    return (
      <Page title="Enter data manually" subtitle="What kind of data are you entering?">
        <ul className="grid gap-4 sm:grid-cols-2">
          {(Object.keys(KINDS) as DataType[]).map((t) => (
            <li key={t}>
              <button
                type="button"
                onClick={() => pick(t)}
                className="block w-full rounded-2xl border border-border bg-surface p-6 text-left transition hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                <span aria-hidden="true" className="text-3xl">{KIND_ICON[t]}</span>
                <span className="mt-2 block text-xl font-semibold text-foreground">{KINDS[t].title}</span>
                <span className="block text-base text-muted">{KINDS[t].blurb}</span>
              </button>
            </li>
          ))}
        </ul>
      </Page>
    );
  }

  const unknownProduct = (r: Row) => needsProducts && r.product?.trim() && productIds.size > 0 && !productIds.has(r.product.trim());

  return (
    <Page
      title={`Enter ${kind.title.toLowerCase()} data`}
      subtitle="Type into the table or paste from a spreadsheet. Fields marked “required” must be filled in. These rows are added to your existing data."
      wide
      action={
        <button type="button" className={btnSecondary} onClick={() => setType(null)}>
          ← Choose another kind
        </button>
      }
    >
      {saved !== null ? (
        <div className="mb-6">
          <Notice tone="success" title={`Saved ${saved} row${saved === 1 ? "" : "s"}`}>
            They&apos;re now in My Data.{" "}
            <Link href={`/data/${type}`} className="font-medium text-accent underline underline-offset-4">
              View them
            </Link>
          </Notice>
        </div>
      ) : null}

      <div className="relative overflow-x-auto rounded-2xl border border-border bg-surface" tabIndex={0} aria-label="Data entry table, scrolls sideways">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-border bg-muted-surface/60 text-muted">
              <th scope="col" className="px-3 py-3 text-sm font-medium">#</th>
              {visible.map((f) => (
                <th key={f.key} scope="col" className="min-w-[10rem] px-3 py-3 text-sm font-medium">
                  {f.label}
                  {f.required ? <span className="ml-1 text-danger"> (required)</span> : null}
                  {f.hint ? <span className="block font-normal text-muted">{f.hint}</span> : null}
                </th>
              ))}
              <th scope="col" className="px-3 py-3"><span className="sr-only">Remove row</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} className="border-b border-border align-top last:border-0">
                <td className="px-3 py-3 text-muted">{ri + 1}</td>
                {visible.map((f, ci) => (
                  <td key={f.key} className="px-3 py-2">
                    <input
                      aria-label={`${f.label}, row ${ri + 1}`}
                      type={inputType(f.kind)}
                      step={f.kind === "number" ? "any" : f.kind === "integer" ? 1 : undefined}
                      list={f.key === "product" ? "known-products" : undefined}
                      value={r[f.key] ?? ""}
                      onChange={(e) => setCell(ri, f.key, e.target.value)}
                      onPaste={(e) => onPaste(e, ri, ci)}
                      className="input min-h-[44px]"
                    />
                    {f.key === "product" && unknownProduct(r) ? (
                      <span className="mt-1 block text-xs text-warning">Not in your product list yet — it will be added with this ID as its name.</span>
                    ) : null}
                  </td>
                ))}
                <td className="px-3 py-2">
                  <button
                    type="button"
                    aria-label={`Remove row ${ri + 1}`}
                    onClick={() => setRows((rs) => (rs.length > 1 ? rs.filter((_, i) => i !== ri) : [blankRow()]))}
                    className="min-h-[44px] min-w-[44px] rounded-full border border-border text-lg text-muted hover:bg-muted-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                  >
                    ×
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <datalist id="known-products">
          {[...productIds].map((p) => <option key={p} value={p} />)}
        </datalist>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" className={btnSecondary} onClick={() => setRows((rs) => [...rs, blankRow()])}>
          + Add row
        </button>
        {optional.length > 0 ? (
          <label className="inline-flex items-center gap-2 text-base text-muted">
            <span>+ Add another detail:</span>
            <select
              className="input min-h-[48px] w-auto"
              value=""
              onChange={(e) => e.target.value && setExtra((x) => [...x, e.target.value])}
              aria-label="Add another detail to the table"
            >
              <option value="">Pick one…</option>
              {optional.map((f) => <option key={f.key} value={f.key}>{f.label}</option>)}
            </select>
          </label>
        ) : null}
      </div>

      {error ? <div className="mt-6"><ErrorBox error={error} /></div> : null}

      <div className="mt-8 flex flex-wrap items-center gap-4">
        <button type="button" onClick={save} disabled={saving} className={btnPrimary}>
          {saving ? "Saving…" : `Save data${filled.length ? ` (${filled.length} row${filled.length === 1 ? "" : "s"})` : ""}`}
        </button>
        <p className="text-base text-muted">Nothing is saved until you press Save.</p>
      </div>
    </Page>
  );
}

export default function ManualEntryPage() {
  return (
    <Suspense fallback={<Page title="Enter data manually"><Spinner label="Opening…" /></Page>}>
      <ManualEntry />
    </Suspense>
  );
}
