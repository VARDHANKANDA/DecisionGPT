"use client";

import Link from "next/link";
import { featuresUsing } from "@/lib/features";
import { useEffect, useState } from "react";
import { api, type CellValue } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { SAMPLES, installSample, type Sample } from "@/lib/sample-data";
import { ErrorBox, Notice, Page, PreviewTable, btnPrimary, btnSecondary } from "@/components/simple";

export default function SampleDataPage() {
  const { business } = useBusiness();
  const [rowsById, setRowsById] = useState<Record<string, Record<string, CellValue>[]>>({});
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);

  useEffect(() => {
    // Dates are relative to today, so build them on the client only.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time client-only initialisation
    setRowsById(Object.fromEntries(SAMPLES.map((s) => [s.id, s.rows()])));
  }, []);

  async function use(sample: Sample) {
    if (!business) return;
    setBusy(true);
    setError(null);
    try {
      await installSample(sample, (type, rows) => api.addRows(business.id, type, rows));
      setDone(sample.id);
      setConfirming(null);
    } catch (e) {
      setError(friendlyError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Page
      title="Sample data"
      subtitle="Look at an example before you add your own. This shows what each kind of data looks like and what the columns mean."
    >
      <div className="mb-8">
        <Notice tone="warning" title="Example data — not your business data">
          Everything on this page is made up for demonstration. It is not from any real business.
        </Notice>
      </div>

      <ul className="grid gap-8">
        {SAMPLES.map((s) => {
          const rows = rowsById[s.id] ?? [];
          return (
            <li key={s.id} className="min-w-0 rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-2xl font-semibold text-foreground">SAMPLE: {s.title.toUpperCase()}</h2>
                <span className="rounded-full bg-warning-soft px-3 py-1 text-sm font-medium text-warning">Example data</span>
              </div>
              <p className="mt-2 text-lg text-muted">{s.blurb}</p>
              <p className="mt-3 text-base text-foreground">
                <span className="font-medium">Example only — this is not your business data.</span> {featuresUsing(s.type).length > 0
                  ? `Once added, you can try it with: ${featuresUsing(s.type).map((f) => f.title).join(", ")}.`
                  : "It can be stored and viewed, but none of the analysis tools use this kind of data yet."}
              </p>

              <div className="mt-4">
                {rows.length > 0 ? (
                  <PreviewTable
                    columns={s.columns.map((c) => ({ key: c.key, label: c.label }))}
                    rows={rows.slice(0, 5)}
                  />
                ) : null}
              </div>

              <details className="mt-4">
                <summary className="cursor-pointer text-lg font-medium text-accent">What do the columns mean?</summary>
                <dl className="mt-3 grid gap-2 sm:grid-cols-2">
                  {s.columns.map((c) => (
                    <div key={c.key} className="rounded-xl bg-muted-surface/60 px-4 py-3">
                      <dt className="font-semibold text-foreground">{c.label}</dt>
                      <dd className="text-base text-muted">{c.meaning}</dd>
                    </div>
                  ))}
                </dl>
              </details>

              <div className="mt-5">
                {done === s.id ? (
                  <Notice tone="success" title="Example added to My Data">
                    It&apos;s marked with “EX-” IDs so you can tell it apart.{" "}
                    <Link href={`/data/${s.type}`} className="font-medium text-accent underline underline-offset-4">
                      View it
                    </Link>
                    , or delete it any time.
                  </Notice>
                ) : confirming === s.id ? (
                  <div className="rounded-2xl border border-border bg-muted-surface/50 p-5">
                    <p className="text-base text-foreground">
                      This will add {rows.length} example row{rows.length === 1 ? "" : "s"}
                      {s.companions.length ? ` (plus the example ${s.companions.join(" and ")} they refer to)` : ""} to{" "}
                      <strong>your</strong> My Data, mixed in with anything you already have. The example IDs start with
                      “EX-”, and you can delete them whenever you like.
                    </p>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button type="button" className={btnPrimary} disabled={busy || !business} onClick={() => use(s)}>
                        {busy ? "Adding…" : "Yes, add this example"}
                      </button>
                      <button type="button" className={btnSecondary} disabled={busy} onClick={() => setConfirming(null)}>
                        No, not now
                      </button>
                    </div>
                  </div>
                ) : (
                  <button type="button" className={btnSecondary} onClick={() => { setConfirming(s.id); setError(null); }} disabled={!business}>
                    Use this example
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {error ? <div className="mt-6"><ErrorBox error={error} /></div> : null}
    </Page>
  );
}
