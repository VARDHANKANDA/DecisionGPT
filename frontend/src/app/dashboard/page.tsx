"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  api,
  type BusinessMemoryEntry,
  type DataLibraryEntry,
  type DecisionSummary,
  type IngestionJob,
  type KPISnapshot,
  type PeriodComparison,
} from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { AGENTS } from "@/lib/features";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import { describeChange, inr, revenueHeadline } from "@/lib/narrate";
import { EXAMPLE_QUESTIONS } from "@/lib/questions";
import { ErrorBox, KIND_ICON, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { Facts } from "@/components/agent-ui";
import { OverviewMonitor } from "@/components/overview-monitor";

interface Activity {
  when: string;
  text: string;
}

interface Overview {
  library: DataLibraryEntry[];
  kpis: KPISnapshot;
  change: PeriodComparison;
  activity: Activity[];
}

export default function OverviewPage() {
  const { business, loading } = useBusiness();
  const router = useRouter();
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [question, setQuestion] = useState("");

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    Promise.all([
      api.getDataLibrary(business.id),
      api.getKpis(business.id, 30),
      api.getPeriodComparison(business.id, 30),
      api.getUploads(business.id),
      api.listMemory(business.id, "chat"),
      api.listDecisions(business.id),
    ])
      .then(([library, kpis, change, uploads, chats, decisions]) => {
        if (cancelled) return;
        setData({ library, kpis, change, activity: buildActivity(uploads, chats, decisions) });
        setError(null);
      })
      .catch((e) => !cancelled && setError(friendlyError(e)));
    return () => {
      cancelled = true;
    };
  }, [business, attempt]);

  if (loading) return <Page title="Overview"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Welcome to DecisionGPT" subtitle="Let's set up your business first. It takes about a minute.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  const withData = data ? data.library.filter((d) => d.rows > 0) : [];
  const isNew = data !== null && withData.length === 0;
  const hasSales = data ? data.kpis.orders > 0 || data.change.previous_orders > 0 : false;

  return (
    <Page title="Overview" subtitle="Your business at a glance, and the quickest ways to get answers." wide>
      {error ? <div className="mb-8"><ErrorBox error={error} onRetry={() => setAttempt((n) => n + 1)} /></div> : null}
      {!data && !error ? <Spinner label="Looking at your data…" /> : null}

      {isNew ? <GetStarted /> : null}

      {data && !isNew ? (
        <div className="space-y-8">
          <section aria-labelledby="glance" className="rounded-2xl border border-border bg-surface p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="glance" className="text-xl font-semibold text-foreground">Last 30 days</h2>
              <Link href="/analytics" className="text-sm font-medium text-accent underline underline-offset-4">Open Business Analytics</Link>
            </div>
            {hasSales ? (
              <>
                <p className="mt-2 text-base text-foreground">{revenueHeadline(data.change, 30)}</p>
                <div className="mt-4">
                  <Facts
                    items={[
                      { label: "Sales", value: inr(data.kpis.revenue) },
                      { label: "Orders", value: data.kpis.orders.toLocaleString("en-IN") },
                      { label: "Change vs. before", value: describeChange(data.change.change_pct) },
                      { label: "Customers who bought", value: data.kpis.customers.toLocaleString("en-IN") },
                    ]}
                  />
                </div>
                <p className="mt-3 text-xs text-muted">From your own records. This shows what happened, not why.</p>
              </>
            ) : (
              <p className="mt-2 text-base text-foreground">There are no sales in the last 60 days. Add recent sales to see your numbers here.</p>
            )}
          </section>

          <OverviewMonitor businessId={business.id} />

          <section aria-labelledby="ask" className="rounded-2xl border border-border bg-surface p-6">
            <h2 id="ask" className="text-xl font-semibold text-foreground">Ask a question</h2>
            <form
              className="mt-3 flex flex-col gap-3 sm:flex-row"
              onSubmit={(e) => {
                e.preventDefault();
                router.push(`/chat${question.trim() ? `?q=${encodeURIComponent(question.trim())}` : ""}`);
              }}
            >
              <label className="sr-only" htmlFor="overview-question">Your question</label>
              <input
                id="overview-question"
                className="input min-h-[48px] flex-1 text-base"
                placeholder="Which products are selling best?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
              />
              <button type="submit" className={btnPrimary}>Open in AI Business Assistant</button>
            </form>
            <ul className="mt-4 flex flex-wrap gap-2">
              {EXAMPLE_QUESTIONS.slice(0, 3).map((e) => (
                <li key={e.question}>
                  <Link
                    href={`/chat?q=${encodeURIComponent(e.question)}`}
                    className="inline-flex min-h-[40px] items-center rounded-full border border-border px-4 py-2 text-sm text-foreground hover:bg-muted-surface focus-visible:outline-2 focus-visible:outline-accent"
                  >
                    {e.question}
                  </Link>
                </li>
              ))}
            </ul>
          </section>

          <div className="grid gap-8 lg:grid-cols-2">
            <section aria-labelledby="your-data" className="min-w-0 rounded-2xl border border-border bg-surface p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 id="your-data" className="text-xl font-semibold text-foreground">Your data</h2>
                <Link href="/data/quality" className="text-sm font-medium text-accent underline underline-offset-4">Data quality</Link>
              </div>
              <ul className="mt-3 divide-y divide-border">
                {data.library.map((d) => (
                  <li key={d.type} className="flex items-center justify-between gap-3 py-2 text-base">
                    <span className="text-foreground"><span aria-hidden="true" className="mr-2">{KIND_ICON[d.type]}</span>{d.title}</span>
                    <span className={d.rows > 0 ? "text-muted" : "text-warning"}>{d.rows > 0 ? `${d.rows.toLocaleString("en-IN")} rows` : "Not added"}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap gap-3">
                <Link href="/data/upload/file" className={btnSecondary}>+ Add data</Link>
                <Link href="/data" className={btnSecondary}>Manage data</Link>
              </div>
            </section>

            <section aria-labelledby="agents" className="min-w-0 rounded-2xl border border-border bg-surface p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 id="agents" className="text-xl font-semibold text-foreground">AI agents</h2>
                <Link href="/agents" className="text-sm font-medium text-accent underline underline-offset-4">See all</Link>
              </div>
              <ul className="mt-3 divide-y divide-border">
                {AGENTS.map((a) => (
                  <li key={a.id}>
                    <Link href={a.href} className="flex items-center gap-3 py-2.5 text-base text-foreground hover:text-accent focus-visible:outline-2 focus-visible:outline-accent">
                      <span aria-hidden="true" className="w-6 text-center text-lg">{a.icon}</span>
                      <span className="min-w-0">
                        <span className="block font-medium">{a.name}</span>
                        <span className="block truncate text-sm text-muted">{a.purpose}</span>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section aria-labelledby="recent" className="rounded-2xl border border-border bg-surface p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="recent" className="text-xl font-semibold text-foreground">Recent activity</h2>
              <Link href="/reports/answers" className="text-sm font-medium text-accent underline underline-offset-4">Open saved answers</Link>
            </div>
            {data.activity.length === 0 ? (
              <p className="mt-2 text-base text-muted">Nothing yet. Your uploads, answers and recommendations will show up here.</p>
            ) : (
              <ul className="mt-3 divide-y divide-border">
                {data.activity.map((a, i) => (
                  <li key={i} className="flex flex-wrap items-baseline justify-between gap-2 py-3 text-base">
                    <span className="min-w-0 text-foreground"><span aria-hidden="true" className="mr-2 text-success">✓</span>{a.text}</span>
                    <span className="text-muted">{timeAgo(a.when)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : null}
    </Page>
  );
}

function GetStarted() {
  const steps = [
    { n: 1, title: "Add your data", body: "Upload a file, type it in, or start with example data." },
    { n: 2, title: "Choose what you want to understand", body: "Your sales, your customers, what may happen next, or a decision." },
    { n: 3, title: "Get your answer", body: "In plain words, with the numbers behind it." },
  ];
  return (
    <section aria-labelledby="start" className="rounded-2xl border border-accent/30 bg-accent-soft/30 p-6 sm:p-8">
      <h2 id="start" className="text-2xl font-semibold text-foreground">Let&apos;s get your business data ready</h2>
      <ol className="mt-4 grid gap-4 sm:grid-cols-3">
        {steps.map((s) => (
          <li key={s.n} className="rounded-xl bg-surface p-4">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-base font-semibold text-accent-foreground">{s.n}</span>
            <p className="mt-2 text-lg font-semibold text-foreground">{s.title}</p>
            <p className="text-base text-muted">{s.body}</p>
          </li>
        ))}
      </ol>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link href="/data/upload/file" className={btnPrimary}>📁 Upload a file</Link>
        <Link href="/data/manual" className={btnSecondary}>✏️ Type my data in</Link>
        <Link href="/data/samples" className={btnSecondary}>🧪 Start with example data</Link>
      </div>
    </section>
  );
}

function buildActivity(uploads: IngestionJob[], chats: BusinessMemoryEntry[], decisions: DecisionSummary[]): Activity[] {
  const items: Activity[] = [];
  for (const u of uploads) {
    if (u.status === "completed") items.push({ when: u.created_at, text: `Data uploaded: ${u.filename}` });
  }
  for (const c of chats) {
    const q = typeof c.metadata_json?.question === "string" ? c.metadata_json.question : c.content.split("\n")[0]?.replace(/^Q:\s*/, "");
    if (q) items.push({ when: c.created_at, text: `Asked “${q}”` });
  }
  for (const d of decisions) items.push({ when: d.created_at, text: "Got a business recommendation" });
  return items.sort((a, b) => +new Date(b.when) - +new Date(a.when)).slice(0, 5);
}
