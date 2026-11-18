"use client";

import Link from "next/link";
import { useRef, useState } from "react";
import { api, type DataTablePage, type DataType, type DateOrder, type IngestionJob, type PendingMapping } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { DATA_GROUP_NAME } from "@/lib/features";
import { useLibrary } from "@/lib/use-library";
import { explainIssue, fieldLabel, friendlyError, type FriendlyError } from "@/lib/friendly";
import {
  ErrorBox,
  Notice,
  Page,
  PreviewTable,
  ReferenceFormat,
  Spinner,
  btnPrimary,
  btnSecondary,
} from "@/components/simple";
import { UploadReport } from "@/components/upload-report";

const CSV_KINDS: { value: DataType; label: string; keywords: RegExp }[] = [
  { value: "sales", label: "Sales — what was sold and when", keywords: /sale|order|transaction/i },
  { value: "customers", label: "Customers — who buys from me", keywords: /customer|client/i },
  { value: "products", label: "Products — what I sell", keywords: /product|item|catalog/i },
  { value: "inventory", label: "Stock levels — how much I have", keywords: /stock|inventory/i },
  { value: "marketing_campaigns", label: "Marketing — what I spent on ads", keywords: /market|campaign|ads?\b/i },
  { value: "finance", label: "Money & accounts — monthly figures", keywords: /financ|expense|profit|p&l|account/i },
];

const PREVIEW_BYTES = 256 * 1024; // the preview never reads more than this, however large the file is
const ACCEPTED = [".csv", ".xlsx"];

function readText(blob: Blob): Promise<string> {
  if (typeof blob.text === "function") return blob.text();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

/** The separator a CSV most likely uses (the server decides for real; this only makes the preview readable). */
function sniffDelimiter(text: string): string {
  const first = text.split(/\r?\n/, 1)[0] ?? "";
  const best = [",", ";", "\t", "|"]
    .map((d) => [d, first.split(d).length - 1] as const)
    .sort((a, b) => b[1] - a[1])[0];
  return best[1] > 0 ? best[0] : ",";
}

/** Minimal CSV reader (quotes, separators, newlines) — used only to preview a file before it is sent. */
function parseCsv(text: string, maxRows = 200, sep = ","): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;
  for (let i = 0; i < text.length && rows.length <= maxRows; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (ch === '"') inQuotes = false;
      else cell += ch;
    } else if (ch === '"') inQuotes = true;
    else if (ch === sep) {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      if (row.some((c) => c.trim() !== "")) rows.push(row);
      row = [];
      cell = "";
    } else cell += ch;
  }
  if (cell !== "" || row.length) {
    row.push(cell);
    if (row.some((c) => c.trim() !== "")) rows.push(row);
  }
  return rows;
}

export default function UploadFilePage() {
  const { business, loading } = useBusiness();
  const library = useLibrary();
  const inputRef = useRef<HTMLInputElement>(null);
  const busy = useRef(false); // a second click can arrive before React re-renders the disabled button
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ columns: string[]; rows: string[][] } | null>(null);
  const [kind, setKind] = useState<DataType | "">("sales"); // "" = let DecisionGPT decide (Excel only)
  const [guessed, setGuessed] = useState(false);
  const [phase, setPhase] = useState<"pick" | "uploading" | "done" | "problem" | "mapping">("pick");
  const [progress, setProgress] = useState<number | null>(null);
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [after, setAfter] = useState<Record<string, DataTablePage>>({});
  const [choices, setChoices] = useState<Record<string, Record<string, string>>>({});
  const [orders, setOrders] = useState<Record<string, Record<string, DateOrder>>>({});

  const lowerName = file?.name.toLowerCase() ?? "";
  const isCsv = lowerName.endsWith(".csv");
  const oldExcel = lowerName.endsWith(".xls");
  const unsupported = file !== null && !ACCEPTED.some((e) => lowerName.endsWith(e));
  const cannotSend = unsupported || oldExcel;

  async function choose(f: File | null) {
    setFile(f);
    setPreview(null);
    setError(null);
    setPhase("pick");
    setJob(null);
    setProgress(null);
    setChoices({});
    setOrders({});
    if (!f) return;
    const csv = f.name.toLowerCase().endsWith(".csv");
    const guess = CSV_KINDS.find((k) => k.keywords.test(f.name));
    if (guess) {
      setKind(guess.value);
      setGuessed(true);
    } else {
      setGuessed(false);
      setKind(csv ? "sales" : "");
    }
    if (csv) {
      try {
        const text = await readText(f.slice(0, PREVIEW_BYTES));
        const parsed = parseCsv(text, 200, sniffDelimiter(text));
        if (parsed.length > 0) setPreview({ columns: parsed[0], rows: parsed.slice(1, 9) });
      } catch {
        // the preview is a convenience; the server reads the real file
      }
    }
  }

  async function showAccountPreview(j: IngestionJob) {
    if (!business) return;
    const types = Object.keys(j.summary_json?.rows_ingested ?? {}) as DataType[];
    const entries = await Promise.all(
      types
        .filter((t) => t !== ("business_profile" as string))
        .map(async (t) => [t, await api.getTable(business.id, t, 0, 5)] as const),
    ).catch(() => []);
    setAfter(Object.fromEntries(entries));
  }

  function handleJob(j: IngestionJob) {
    setJob(j);
    if (j.status === "completed") {
      setPhase("done");
      void showAccountPreview(j);
    } else if (j.status === "needs_mapping_confirmation") {
      setPhase("mapping");
    } else {
      setPhase("problem");
    }
  }

  async function upload(allowDuplicateFile = false) {
    if (!business || !file || busy.current || cannotSend) return;
    busy.current = true;
    setPhase("uploading");
    setError(null);
    setProgress(0);
    try {
      handleJob(await api.uploadData(business.id, file, kind || undefined, { allowDuplicateFile, onProgress: setProgress }));
    } catch (e) {
      setError(friendlyError(e));
      setPhase("pick");
    } finally {
      busy.current = false;
      setProgress(null);
    }
  }

  async function confirmMapping() {
    if (!business || !job || busy.current) return;
    const pending = job.mapping_json as Record<string, PendingMapping>;
    const mappings: Record<string, Record<string, string>> = {};
    for (const [type, p] of Object.entries(pending)) {
      mappings[type] = { ...p.suggested_mapping };
      for (const [field, column] of Object.entries(choices[type] ?? {})) if (column) mappings[type][column] = field;
    }
    busy.current = true;
    setPhase("uploading");
    setError(null);
    try {
      handleJob(await api.confirmMapping(business.id, job.id, mappings, orders));
    } catch (e) {
      setError(friendlyError(e));
      setPhase("mapping");
    } finally {
      busy.current = false;
    }
  }

  if (!loading && !business) {
    return (
      <Page title="Upload a file">
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business first
        </Link>
      </Page>
    );
  }

  const pending = (job?.mapping_json ?? {}) as Record<string, PendingMapping>;
  const mappingComplete = Object.entries(pending).every(
    ([type, p]) =>
      p.unmapped_required_fields.every((f) => Boolean(choices[type]?.[f])) &&
      (p.date_questions ?? []).every((q) => Boolean(orders[type]?.[q.field])),
  );
  const duplicateOf = job?.summary_json?.duplicate_of;
  const qualityIssues = Object.entries((job?.summary_json?.quality ?? {}) as Record<string, { issues?: string[] }>).flatMap(
    ([type, q]) => (q.issues ?? []).map((i) => ({ type, text: explainIssue(i) })),
  );

  return (
    <Page
      title="Upload a file"
      subtitle="Choose a CSV or Excel (.xlsx) file from your computer. We tidy it, tell you exactly what we did, and never delete your original."
    >
      {phase !== "done" ? (
        <div className="mb-6">
          <Notice title="Adding new data">
            New uploads are added to your existing data. To replace existing data, remove the old data first
            (<Link href="/data" className="font-medium text-accent underline underline-offset-4">My Data → Remove data</Link>), then upload the new file.
          </Notice>
        </div>
      ) : null}

      {phase !== "done" ? (
        <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div
            className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-border bg-muted-surface/60 px-6 py-10 text-center"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              void choose(e.dataTransfer.files?.[0] ?? null);
            }}
          >
            <span aria-hidden="true" className="text-4xl">
              📁
            </span>
            <p className="text-lg text-foreground">
              {file ? <span className="font-semibold">{file.name}</span> : "Drag a file here, or"}
            </p>
            <button type="button" onClick={() => inputRef.current?.click()} className={btnSecondary}>
              {file ? "Choose a different file" : "Choose a file"}
            </button>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx"
              className="sr-only"
              aria-label="Choose a CSV or Excel file"
              onChange={(e) => void choose(e.target.files?.[0] ?? null)}
            />
            <p className="text-sm text-muted">CSV or Excel (.xlsx). For an old .xls file: open it in Excel and use Save As → .xlsx first.</p>
          </div>

          {file ? (
            <div className="mt-6 space-y-5">
              {cannotSend ? (
                <Notice tone="warning" title={oldExcel ? "Old Excel files (.xls) can't be read safely" : "We can't read this kind of file"}>
                  {oldExcel
                    ? "Open it in Excel (or Google Sheets) and save a copy as .xlsx or CSV, then choose that file."
                    : "Please choose a CSV (.csv) or Excel (.xlsx) file."}
                </Notice>
              ) : (
                <label className="block">
                  <span className="text-lg font-medium text-foreground">What is in this file?</span>
                  <select
                    value={kind}
                    onChange={(e) => {
                      setKind(e.target.value as DataType | "");
                      setGuessed(false);
                    }}
                    className="input mt-2 min-h-[48px] text-base"
                  >
                    {!isCsv ? <option value="">Let DecisionGPT decide (from the sheet names and columns)</option> : null}
                    {CSV_KINDS.map((k) => (
                      <option key={k.value} value={k.value}>
                        {k.label}
                      </option>
                    ))}
                  </select>
                  {guessed ? <span className="mt-1 block text-sm text-muted">We guessed this from the file name — please check it.</span> : null}
                  {!isCsv ? (
                    <span className="mt-1 block text-sm text-muted">
                      An Excel file can hold several sheets (Sales, Customers…). We recognise each sheet by its name or columns; your choice here is
                      only used when the file has a single sheet.
                    </span>
                  ) : null}
                </label>
              )}

              {(() => {
                const have = kind ? (library?.find((d) => d.type === kind)?.rows ?? 0) : 0;
                return have > 0 && kind ? (
                  <Notice tone="warning" title={`You already have ${have.toLocaleString("en-IN")} rows of ${DATA_GROUP_NAME[kind].toLowerCase()}`}>
                    DecisionGPT adds this file&apos;s rows to your existing data — it does not replace them. To replace the old data
                    completely, remove it first.{" "}
                    <Link href={`/data/${kind}#remove-data`} className="font-medium text-accent underline underline-offset-4">
                      Remove the old {DATA_GROUP_NAME[kind].toLowerCase()}
                    </Link>
                  </Notice>
                ) : null;
              })()}

              {preview ? (
                <section aria-labelledby="preview-h">
                  <h2 id="preview-h" className="text-xl font-semibold text-foreground">
                    Here&apos;s a preview
                  </h2>
                  <p className="mt-1 text-base text-muted">
                    We found {preview.columns.length} columns: {preview.columns.join(", ")}. This shows only the start of the file — nothing has been
                    saved yet.
                  </p>
                  <div className="mt-3">
                    <PreviewTable
                      columns={preview.columns.map((c, i) => ({ key: String(i), label: c }))}
                      rows={preview.rows.map((r) => Object.fromEntries(r.map((v, i) => [String(i), v])))}
                    />
                  </div>
                </section>
              ) : null}

              {error ? <ErrorBox error={error} onRetry={() => void upload()} /> : null}

              <div className="flex flex-wrap gap-3">
                <button type="button" onClick={() => void upload()} disabled={phase === "uploading" || cannotSend} className={btnPrimary}>
                  {phase === "uploading" ? "Adding your data…" : "Add this data to My Data"}
                </button>
              </div>
              {phase === "uploading" ? (
                <div className="space-y-2">
                  {progress !== null && progress < 1 ? (
                    <label className="block text-base text-muted">
                      Sending your file… {Math.round(progress * 100)}%
                      <progress className="mt-1 block h-2 w-full" max={100} value={Math.round(progress * 100)} aria-label="Upload progress" />
                    </label>
                  ) : null}
                  <Spinner label={progress !== null && progress < 1 ? "Sending your file…" : "Checking your file and saving it…"} />
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {phase === "pick" ? (
        <div className="mt-6">
          <ReferenceFormat
            value={kind || "sales"}
            onChange={(k) => {
              setKind(k);
              setGuessed(false);
            }}
          />
        </div>
      ) : null}

      {phase === "mapping" && job ? (
        <section aria-labelledby="map-h" className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <h2 id="map-h" className="text-xl font-semibold text-foreground">
            We need your help with a few things
          </h2>
          <p className="mt-1 text-base text-muted">Nothing has been added yet. We would rather ask than guess — please answer each question below.</p>
          {Object.entries(pending).map(([type, p]) => (
            <fieldset key={type} className="mt-4 space-y-4">
              <legend className="text-lg font-medium text-foreground">{DATA_GROUP_NAME[type as DataType] ?? fieldLabel(type)}</legend>
              {p.unmapped_required_fields.map((field) => (
                <label key={field} className="block">
                  <span className="text-base font-medium text-foreground">Which column is “{fieldLabel(field)}”?</span>
                  <select
                    className="input mt-1 min-h-[48px] text-base"
                    value={choices[type]?.[field] ?? ""}
                    onChange={(e) => setChoices((c) => ({ ...c, [type]: { ...c[type], [field]: e.target.value } }))}
                  >
                    <option value="">Choose a column…</option>
                    {p.available_columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </label>
              ))}
              {(p.date_questions ?? []).map((q) => (
                <div key={q.field} role="radiogroup" aria-labelledby={`dq-${type}-${q.field}`}>
                  <p id={`dq-${type}-${q.field}`} className="text-base font-medium text-foreground">
                    The dates in “{q.column}” could be read two ways. Which is right?
                  </p>
                  <p className="text-sm text-muted">For example: {q.examples.slice(0, 3).join(", ")}</p>
                  {(
                    [
                      ["day_first", "Day first — 03/04/2026 means 3 April 2026"],
                      ["month_first", "Month first — 03/04/2026 means 4 March 2026"],
                    ] as const
                  ).map(([value, label]) => (
                    <label key={value} className="mt-1 flex min-h-[44px] items-center gap-3 text-base text-foreground">
                      <input
                        type="radio"
                        name={`order-${type}-${q.field}`}
                        checked={orders[type]?.[q.field] === value}
                        onChange={() => setOrders((o) => ({ ...o, [type]: { ...o[type], [q.field]: value } }))}
                      />
                      {label}
                    </label>
                  ))}
                </div>
              ))}
            </fieldset>
          ))}
          {error ? (
            <div className="mt-4">
              <ErrorBox error={error} />
            </div>
          ) : null}
          <div className="mt-5">
            <button type="button" onClick={() => void confirmMapping()} disabled={!mappingComplete} className={btnPrimary}>
              Continue
            </button>
            {!mappingComplete ? <p className="mt-2 text-sm text-muted">Answer every question above to continue.</p> : null}
          </div>
        </section>
      ) : null}

      {phase === "problem" && job ? (
        <section className="mt-6" aria-labelledby="prob-h">
          <Notice tone="warning" title={duplicateOf ? "This file was already added" : "We couldn't add this file yet"}>
            <p id="prob-h">Nothing was saved, and your existing data is unchanged. Here&apos;s what needs attention:</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {job.error_message ? <li>{job.error_message}</li> : null}
              {qualityIssues.map((q, i) => (
                <li key={i}>{q.text}</li>
              ))}
              {!job.error_message && qualityIssues.length === 0 ? <li>The file could not be read.</li> : null}
            </ul>
            {duplicateOf ? null : <p className="mt-3">Fix the file and choose it again, or enter the data by hand instead.</p>}
          </Notice>
          {job.summary_json?.datasets?.length ? (
            <div className="mt-4">
              <UploadReport job={job} />
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            {duplicateOf ? (
              <button type="button" onClick={() => void upload(true)} className={btnSecondary}>
                Import it again anyway
              </button>
            ) : (
              <button type="button" onClick={() => void upload()} className={btnSecondary}>
                Try the same file again
              </button>
            )}
            <Link href="/data/manual" className={btnSecondary}>
              Enter data manually
            </Link>
          </div>
        </section>
      ) : null}

      {phase === "done" && job ? (
        <section aria-labelledby="done-h">
          <Notice tone="success" title="File uploaded">
            <span id="done-h">{job.filename} was added to your existing data in My Data.</span>
          </Notice>
          <ul className="mt-6 grid gap-3 sm:grid-cols-2">
            {Object.entries(job.summary_json?.rows_ingested ?? {}).map(([type, count]) => (
              <li key={type} className="min-w-0 rounded-2xl border border-border bg-surface p-5">
                <p className="text-lg font-semibold text-foreground">{after[type]?.title ?? fieldLabel(type)}</p>
                <p className="text-base text-muted">
                  {count.toLocaleString("en-IN")} rows added{after[type] ? ` — you now have ${after[type].total.toLocaleString("en-IN")} rows in total` : ""}
                </p>
                {after[type] ? (
                  <div className="mt-3">
                    <p className="mb-2 text-sm text-muted">Your latest {after[type].rows.length} rows:</p>
                    <PreviewTable
                      columns={after[type].columns.slice(0, 4).map((c) => ({ key: c.key, label: c.label }))}
                      rows={after[type].rows.map((r) => r.values)}
                    />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
          <h2 className="mt-8 text-xl font-semibold text-foreground">What we did with your file</h2>
          <div className="mt-3">
            <UploadReport job={job} />
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link href="/data/preprocessing" className={btnPrimary}>
              Proceed to Data Preprocessing &rarr;
            </Link>
            <Link href="/data" className={btnSecondary}>
              View My Data
            </Link>
            <Link href="/analytics" className={btnSecondary}>
              See my business
            </Link>
            <Link href="/dashboard" className={btnSecondary}>
              What can I do next?
            </Link>
          </div>
        </section>
      ) : null}
    </Page>
  );
}
