"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { api, type ChurnResult, type CustomerSummary } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { churnStory, inr, RISK_CUTOFFS, RISK_LABEL, riskBand, type RiskBand } from "@/lib/narrate";
import { useLibrary } from "@/lib/use-library";
import { AnswerBlock, DataUsed, ErrorBox, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";

const BAND_STYLE: Record<RiskBand, string> = {
  higher: "bg-danger-soft text-danger",
  moderate: "bg-warning-soft text-warning",
  lower: "bg-success-soft text-success",
};
const BAND_GLYPH: Record<RiskBand, string> = { higher: "▲", moderate: "◆", lower: "●" };

export default function CustomersPage() {
  const { business, loading } = useBusiness();
  const library = useLibrary();
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [result, setResult] = useState<ChurnResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    api.getCustomerSummary(business.id).then((s) => !cancelled && setSummary(s)).catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [business]);

  const story = useMemo(() => (result ? churnStory(result.predictions) : null), [result]);
  const customerRows = library?.find((d) => d.type === "customers")?.rows ?? null;

  async function start() {
    if (!business) return;
    setRunning(true);
    setError(null);
    setResult(null);
    setShowAll(false);
    try {
      setResult(await api.getChurn(business.id));
    } catch (e) {
      setError(friendlyError(e, "We couldn't check your customers right now."));
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <Page title="Customers"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Customers" subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  const listed = story ? (showAll ? story.atRisk : story.atRisk.slice(0, 10)) : [];

  return (
    <Page title="Customers" subtitle="Understand your customers and find the ones who may be about to stop buying." wide>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-5">
          <section className="rounded-2xl border border-border bg-surface p-5">
            <h2 className="text-base font-semibold text-foreground">Your customers</h2>
            {!summary ? (
              <p className="mt-2 text-muted">Loading…</p>
            ) : summary.total_customers === 0 ? (
              <p className="mt-2 text-lg text-foreground">You haven&apos;t added any customers yet.</p>
            ) : (
              <dl className="mt-3 grid grid-cols-2 gap-4">
                <Fact label="Customers" value={summary.total_customers.toLocaleString("en-IN")} />
                <Fact label="New in last 30 days" value={summary.new_customers_last_30_days.toLocaleString("en-IN")} />
                <Fact label="Average spent each" value={summary.avg_monetary_value !== null ? inr(summary.avg_monetary_value) : "Not available"} />
                <Fact label="Average times bought" value={summary.avg_purchase_frequency !== null ? summary.avg_purchase_frequency.toFixed(1) : "Not available"} />
              </dl>
            )}
          </section>

          <DataUsed
            library={library}
            types={["customers"]}
            action={customerRows === 0 ? <Link href="/data/upload/file" className={btnSecondary}>Add customer data</Link> : null}
          />

          <button type="button" className={`${btnPrimary} w-full`} onClick={start} disabled={running || customerRows === 0}>
            {running ? "Checking your customers…" : "Find customers who may be at risk"}
          </button>
        </div>

        <div className="min-w-0" aria-live="polite">
          {running ? <Spinner label="Looking at how recently, how often and how much each customer buys…" /> : null}
          {error ? <ErrorBox error={error} onRetry={start} /> : null}

          {!result && !running && !error ? (
            <Notice title="Customers who may be at risk will appear here">
              We look at when each customer first and last bought, how often, and how much they spend. If there isn&apos;t
              enough customer history yet, we&apos;ll tell you what to add instead of guessing.
            </Notice>
          ) : null}

          {result && story ? (
            <div className="space-y-6">
              <AnswerBlock
                headline={story.headline}
                why="It usually costs less to keep a customer who is drifting away than to win a new one."
                shows={
                  <div className="flex flex-wrap gap-3">
                    {(["higher", "moderate", "lower"] as RiskBand[]).map((b) => (
                      <span key={b} className={`rounded-full px-4 py-2 text-base font-medium ${BAND_STYLE[b]}`}>
                        <span aria-hidden="true">{BAND_GLYPH[b]} </span>
                        {story.counts[b].toLocaleString("en-IN")} · {RISK_LABEL[b]}
                      </span>
                    ))}
                  </div>
                }
                watch="These are estimates from patterns in past buying, not facts about any one person. Some flagged customers will carry on buying."
                next="Consider a personal message or a small offer to the customers at the top of the list."
              />

              {result && result.warnings && result.warnings.length > 0 ? (
                <Notice tone="warning" title="What this score is — and is not">
                  <ul className="list-disc space-y-1 pl-5">
                    {result.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </Notice>
              ) : null}

              {story.atRisk.length > 0 ? (
                <section className="rounded-2xl border border-border bg-surface">
                  <h2 className="px-5 pt-5 text-lg font-semibold text-foreground">
                    Customers to look at first ({story.atRisk.length.toLocaleString("en-IN")})
                  </h2>
                  <div className="relative overflow-x-auto" tabIndex={0} aria-label="Customers at risk, scrolls sideways">
                    <table className="mt-3 w-full text-base">
                      <thead className="text-left text-sm text-muted">
                        <tr>
                          <th className="px-5 py-2 font-medium">Customer</th>
                          <th className="px-5 py-2 font-medium">Model score (higher = more like customers who stopped)</th>
                          <th className="px-5 py-2 text-right font-medium">Risk</th>
                        </tr>
                      </thead>
                      <tbody>
                        {listed.map((p) => {
                          const b = riskBand(p.churn_probability);
                          return (
                            <tr key={p.customer_id} className="border-t border-border">
                              <td className="px-5 py-3 font-medium text-foreground">{p.external_customer_id ?? "A customer"}</td>
                              <td className="px-5 py-3" title={result?.score_meaning ?? "Model score, not a verified probability"}>score {Math.round(p.churn_probability * 100)} / 100</td>
                              <td className="px-5 py-3 text-right">
                                <span className={`inline-block whitespace-nowrap rounded-full px-3 py-1 text-sm font-medium ${BAND_STYLE[b]}`}>
                                  <span aria-hidden="true">{BAND_GLYPH[b]} </span>
                                  {RISK_LABEL[b]}
                                </span>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 px-5 py-4">
                    {story.atRisk.length > 10 ? (
                      <button type="button" className={btnSecondary} onClick={() => setShowAll((v) => !v)}>
                        {showAll ? "Show fewer" : `Show all ${story.atRisk.length.toLocaleString("en-IN")}`}
                      </button>
                    ) : null}
                    <Link href="/data/customers" className="text-base font-medium text-accent underline underline-offset-4">
                      See everything we know about your customers
                    </Link>
                  </div>
                </section>
              ) : null}

              <p className="text-sm text-muted">This customer analysis is available while you view this page. It isn&apos;t currently saved to Reports.</p>

              <details className="rounded-2xl border border-border bg-surface">
                <summary className="cursor-pointer px-5 py-4 text-base font-medium text-foreground">How we worked this out</summary>
                <div className="space-y-2 border-t border-border p-5 text-base text-muted">
                  <p>
                    For each customer we looked at how long they have been buying, how recently they last bought, how often they
                    buy and how much they spend. We can&apos;t yet tell you <em>why</em> an individual customer was flagged.
                  </p>
                  <p>
                    Groups: “{RISK_LABEL.higher}” is a score of {Math.round(RISK_CUTOFFS.higher * 100)} or more out of 100, “{RISK_LABEL.moderate}” is{" "}
                    {Math.round(RISK_CUTOFFS.moderate * 100)}–{Math.round(RISK_CUTOFFS.higher * 100)}. These groups just help you sort the list; a score is not a percentage chance.
                  </p>
                  <p className="text-sm">
                    Method: {result.model_name} (version {result.model_version}). When it was built and tested on DecisionGPT&apos;s example data
                    (not your business), it found{" "}
                    {result.metrics.precision !== undefined ? `${Math.round(result.metrics.precision * 100)}% of its “will leave” flags were right and ` : ""}
                    {result.metrics.recall !== undefined ? `${Math.round(result.metrics.recall * 100)}% of customers who did leave were flagged.` : ""}{" "}
                    Your results may differ.
                  </p>
                </div>
              </details>
            </div>
          ) : null}
        </div>
      </div>
    </Page>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="text-xl font-semibold text-foreground">{value}</dd>
    </div>
  );
}
