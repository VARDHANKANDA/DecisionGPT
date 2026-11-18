"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type DataLibraryEntry, type DataType } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { isDemoBusiness } from "@/lib/demo";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import { DATA_GROUP_NAME, featuresUsing } from "@/lib/features";
import { ErrorBox, KIND_ICON, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";

export default function MyDataPage() {
  const { business, loading } = useBusiness();
  const [library, setLibrary] = useState<DataLibraryEntry[] | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    api
      .getDataLibrary(business.id)
      .then((l) => !cancelled && (setLibrary(l), setError(null)))
      .catch((e) => !cancelled && setError(friendlyError(e)));
    return () => {
      cancelled = true;
    };
  }, [business, attempt]);

  if (loading) return <Page title="My Data"><Spinner label="Opening your data…" /></Page>;
  if (!business) {
    return (
      <Page title="My Data" subtitle="Set up your business first, then you can add your data here.">
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business
        </Link>
      </Page>
    );
  }

  const demo = isDemoBusiness(business);
  const withData = (library ?? []).filter((d) => d.rows > 0);
  const empty = (library ?? []).filter((d) => d.rows === 0);

  return (
    <Page
      title="My Data"
      subtitle="Your business information, grouped by what it is. DecisionGPT automatically uses the data in each group when you run an analysis."
      action={
        <Link href="/data/upload" className={btnPrimary}>
          + Add data
        </Link>
      }
    >
      {error ? <ErrorBox error={error} onRetry={() => setAttempt((n) => n + 1)} /> : null}
      {!library && !error ? <Spinner label="Looking at your data…" /> : null}

      {library && withData.length === 0 ? (
        <Notice title="No business data yet.">
          Upload a file, enter data manually, or explore sample data. Your data stays in your own account.
        </Notice>
      ) : null}

      {withData.length > 0 ? (
        <ul className="grid gap-4">
          {withData.map((d) => (
            <li key={d.type} className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="text-xl font-semibold text-foreground">
                    <span aria-hidden="true" className="mr-2">
                      {KIND_ICON[d.type]}
                    </span>
                    {DATA_GROUP_NAME[d.type as DataType] ?? d.title}
                  </h2>
                  <p className="mt-1 text-base text-muted">{d.description}</p>
                  <p className="mt-2 text-base text-foreground">
                    {d.rows.toLocaleString("en-IN")} rows · {d.columns} columns · Updated {timeAgo(d.last_updated).toLowerCase()}
                  </p>
                  {d.source_files.length > 0 ? (
                    <p className="mt-1 break-words text-sm text-muted">
                      From file: {d.source_files.map((f) => f.filename).join(", ")}
                    </p>
                  ) : (
                    <p className="mt-1 text-sm text-muted">{demo ? "Demo data — made up for demonstration, not a real business." : "Entered by hand or edited since upload."}</p>
                  )}
                </div>
              </div>
              <div className="mt-4">
                <p className="text-sm font-medium text-muted">Can be used for</p>
                <ul className="mt-1 flex flex-wrap gap-2">
                  {featuresUsing(d.type).map((f) => (
                    <li key={f.id}>
                      <Link
                        href={f.href}
                        className="inline-flex min-h-[40px] items-center gap-1 rounded-full bg-accent-soft px-4 py-1.5 text-base font-medium text-accent hover:opacity-80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                      >
                        <span aria-hidden="true">{f.icon}</span> {f.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <Link href={`/data/${d.type}`} className={btnSecondary}>
                  View &amp; edit
                </Link>
                <Link href={featuresUsing(d.type)[0]?.href ?? "/chat"} className={btnPrimary}>
                  Analyze
                </Link>
                <Link href={`/data/${d.type}#remove-data`} className={btnSecondary}>
                  Remove data
                </Link>
                <Link href={`/data/manual?type=${d.type}`} className={btnSecondary}>
                  Add rows
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {empty.length > 0 && library ? (
        <section aria-labelledby="not-added" className="mt-10">
          <h2 id="not-added" className="text-xl font-semibold text-foreground">
            You can also add
          </h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {empty.map((d) => (
              <li key={d.type}>
                <Link
                  href={`/data/manual?type=${d.type}`}
                  className="block rounded-2xl border border-dashed border-border bg-surface p-5 transition hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
                >
                  <span className="text-lg font-semibold text-foreground">
                    <span aria-hidden="true" className="mr-2">
                      {KIND_ICON[d.type]}
                    </span>
                    {DATA_GROUP_NAME[d.type as DataType] ?? d.title}
                  </span>
                  <span className="mt-1 block text-base text-muted">{d.description}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {withData.length > 0 ? (
        <details className="mt-10 rounded-2xl border border-border bg-surface">
          <summary className="min-h-[56px] cursor-pointer px-5 py-4 text-lg font-medium text-foreground">
            Want to replace data you already added?
          </summary>
          <div className="border-t border-border px-5 py-4 text-base text-muted">
            <p>New data is always added to what you already have. To replace it completely:</p>
            <ol className="mt-2 list-decimal space-y-1 pl-6 text-foreground">
              <li>Remove the old data — choose “Remove data” on that group.</li>
              <li>Add the new data — upload a file or type it in.</li>
            </ol>
          </div>
        </details>
      ) : null}

      <div className="mt-10 flex flex-wrap gap-3">
        <Link href="/data/samples" className={btnSecondary}>
          Look at sample data
        </Link>
        <Link href="/analytics" className={btnSecondary}>
          See totals &amp; charts
        </Link>
      </div>
    </Page>
  );
}
