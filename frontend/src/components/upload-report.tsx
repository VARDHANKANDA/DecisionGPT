"use client";

import type { IngestionJob, UploadDataset } from "@/lib/api";
import { DATA_GROUP_NAME } from "@/lib/features";
import { fieldLabel } from "@/lib/friendly";
import type { DataType } from "@/lib/api";
import { Notice } from "@/components/simple";

const nf = (n: number) => n.toLocaleString("en-IN");

const DELIMITER_NAME: Record<string, string> = { ",": "comma", ";": "semicolon", "	": "tab", "|": "pipe" };

/** "semicolon-separated text, encoding cp1252", or null for a spreadsheet (nothing to say). */
export function readAs(d: Pick<UploadDataset, "delimiter" | "encoding">): string | null {
  if (!d.delimiter && !d.encoding) return null;
  const parts = [d.delimiter ? `${DELIMITER_NAME[d.delimiter] ?? "custom"}-separated text` : null, d.encoding ? `encoding ${d.encoding}` : null];
  return parts.filter(Boolean).join(", ");
}

export function datasetTitle(type: string): string {
  return DATA_GROUP_NAME[type as DataType] ?? fieldLabel(type);
}

function Figure({ label, value, tone }: { label: string; value: number; tone?: "good" | "warn" }) {
  const mark = tone === "warn" && value > 0 ? "⚠ " : "";
  return (
    <div className="rounded-xl border border-border bg-muted-surface/40 px-4 py-3">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-xl font-semibold text-foreground">
        <span aria-hidden="true">{mark}</span>
        {nf(value)}
      </dd>
    </div>
  );
}

function DatasetReport({ d }: { d: UploadDataset }) {
  const skippedReasons = Object.entries(d.skipped_reasons ?? {});
  const heading = `${datasetTitle(d.type)}${d.source && d.source.toLowerCase() !== d.type ? ` (from “${d.source}”)` : ""}`;
  return (
    <section aria-label={`Import report: ${heading}`} className="rounded-2xl border border-border bg-surface p-5">
      <h3 className="text-lg font-semibold text-foreground">{heading}</h3>
      {readAs(d) ? <p className="mt-1 text-sm text-muted">We read this file as {readAs(d)}.</p> : null}
      <dl className="mt-3 grid gap-3 sm:grid-cols-3">
        <Figure label="Rows found in the file" value={d.rows_read} />
        <Figure label="Rows added to My Data" value={d.rows_imported} />
        <Figure label="Rows left out" value={d.rows_skipped} tone="warn" />
      </dl>

      {d.rows_skipped > 0 ? (
        <div className="mt-4">
          <p className="text-base font-medium text-foreground">Why some rows were left out</p>
          <p className="text-sm text-muted">
            These rows were not changed or guessed — they are listed here so you can fix them in your file and upload them again.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-base text-foreground">
            {skippedReasons.map(([reason, count]) => (
              <li key={reason}>
                {reason}: {nf(count)} {count === 1 ? "row" : "rows"}
              </li>
            ))}
          </ul>
          {d.skipped_examples.length > 0 ? (
            <details className="mt-2 text-sm text-muted">
              <summary className="cursor-pointer">Show examples (first {d.skipped_examples.length})</summary>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {d.skipped_examples.map((e, i) => (
                  <li key={i}>
                    {e.row !== undefined ? `Row ${nf(e.row)}: ` : ""}
                    {e.reason}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}

      {d.warnings.length > 0 ? (
        <div className="mt-4">
          <Notice tone="warning" title="Please look at this">
            <ul className="list-disc space-y-1 pl-5">
              {d.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </Notice>
        </div>
      ) : null}

      {d.actions.length > 0 ? (
        <div className="mt-4">
          <p className="text-base font-medium text-foreground">What we tidied up</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-base text-foreground">
            {d.actions.map((a, i) => (
              <li key={i}>
                {a.message}
                {a.count !== null && a.count !== undefined ? ` (${nf(a.count)})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-4 text-base text-muted">Your file needed no tidying — every value was used exactly as written.</p>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="text-base font-medium text-foreground">Columns we used</p>
          <ul className="mt-1 space-y-1 text-base text-foreground">
            {d.columns_used.map((c) => (
              <li key={c.column}>
                “{c.column}” <span className="text-muted">→</span> {fieldLabel(c.as)}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-base font-medium text-foreground">Columns we did not use</p>
          {d.columns_not_used.length > 0 ? (
            <>
              <p className="text-sm text-muted">Nothing was deleted: these stay in your original file, DecisionGPT just does not use them yet.</p>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-base text-foreground">
                {d.columns_not_used.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-base text-muted">None — every column in the file was used.</p>
          )}
          {d.columns_removed_empty.length > 0 ? (
            <p className="mt-2 text-sm text-muted">Left out because they had no values at all: {d.columns_removed_empty.join(", ")}.</p>
          ) : null}
          {d.renamed_columns.length > 0 ? (
            <p className="mt-2 text-sm text-muted">
              Renamed so no two columns share a name: {d.renamed_columns.map((r) => `“${r.from}” → “${r.to}”`).join(", ")}.
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
}

/** What happened to an uploaded file: counts, what was left out and why, what was tidied, which columns were used. All values come from the server's report. */
export function UploadReport({ job }: { job: IngestionJob }) {
  const datasets = job.summary_json?.datasets ?? [];
  const unused = job.summary_json?.sheets_not_used ?? [];
  return (
    <div className="space-y-4">
      {datasets.map((d, i) => (
        <DatasetReport key={`${d.type}-${i}`} d={d} />
      ))}
      {unused.length > 0 ? (
        <Notice tone="info" title="Parts of the file that were not imported">
          <ul className="list-disc space-y-1 pl-5">
            {unused.map((u, i) => (
              <li key={i}>
                {u.sheet}: {u.reason}
              </li>
            ))}
          </ul>
        </Notice>
      ) : null}
      {job.summary_json?.original_kept ? (
        <p className="text-sm text-muted">Your original file was kept unchanged; the tidied copy is what DecisionGPT uses.</p>
      ) : null}
    </div>
  );
}
