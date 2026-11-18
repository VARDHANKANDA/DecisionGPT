"use client";

import Link from "next/link";
import { useState } from "react";
import { api, type ChurnResult } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import { churnStory, describeChange, goalSentence, inr, revenueHeadline } from "@/lib/narrate";
import { ErrorBox, Notice, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { Facts, Kind, LoadView, Panel, StoredReview, loadLatestAnalysis, useLoad } from "@/components/agent-ui";
import { capabilityName } from "@/lib/features";

const pct1 = (n: number) => `${(Math.round(n * 10) / 10).toLocaleString("en-IN")}%`;

/* ------------------------------------------------------------------ Business Analyst */
export function BusinessAnalystPanels() {
  const load = useLoad(async (id) => {
    const [kpis, change, top] = await Promise.all([api.getKpis(id, 30), api.getPeriodComparison(id, 30), api.getTopProducts(id, 3)]);
    return { kpis, change, top };
  });
  return (
    <>
      <Panel title="How your sales are doing" note="Last 30 days, compared with the 30 days before. Every number comes from the data you added.">
        <LoadView load={load} label="Reading your sales…">
          {({ kpis, change, top }) =>
            kpis.orders === 0 && change.previous_orders === 0 ? (
              <div>
                <p className="text-base text-foreground">There are no sales in the last 60 days to analyse.</p>
                <div className="mt-3"><Link href="/data" className={btnSecondary}>Add sales data</Link></div>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-lg text-foreground"><Kind kind="From your records" /> <span className="ml-1">{revenueHeadline(change, 30)}</span></p>
                <Facts
                  items={[
                    { label: "Sales", value: inr(kpis.revenue) },
                    { label: "Orders", value: kpis.orders.toLocaleString("en-IN") },
                    { label: "Change in sales", value: describeChange(change.change_pct) },
                    { label: "Best seller", value: top[0]?.name ?? "—", hint: top[0] ? `${inr(top[0].revenue)} in sales (all time)` : undefined },
                  ]}
                />
                <p className="text-sm text-muted">This describes what happened. It does not say why it happened.</p>
              </div>
            )
          }
        </LoadView>
      </Panel>
      <StoredReview reviewKey="business_analyst" agentName="Business Analyst" />
    </>
  );
}

/* ------------------------------------------------------------------ Financial Advisor */
export function FinancialAdvisorPanels() {
  const load = useLoad(async (id) => {
    const [kpis, library] = await Promise.all([api.getKpis(id, 30), api.getDataLibrary(id)]);
    return { kpis, finance: library.find((l) => l.type === "finance")?.rows ?? 0 };
  });
  return (
    <>
      <Panel title="Your money figures" note="Last 30 days. A figure is shown only when your data can support it.">
        <LoadView load={load} label="Reading your figures…">
          {({ kpis, finance }) => (
            <div className="space-y-4">
              <Facts
                items={[
                  { label: "Sales", value: inr(kpis.revenue) },
                  { label: "Average order", value: kpis.average_order_value !== null ? inr(kpis.average_order_value) : "Not available" },
                  { label: "Profit", value: kpis.profit !== null ? inr(kpis.profit) : "Not available", hint: kpis.profit === null ? "Needs product costs" : undefined },
                  { label: "Marketing spend", value: inr(kpis.marketing_spend) },
                ]}
              />
              {kpis.notes.length > 0 ? (
                <ul className="list-disc pl-5 text-sm text-muted">
                  {kpis.notes.map((n) => (<li key={n}>{n}</li>))}
                </ul>
              ) : null}
              {kpis.profit === null ? (
                <Notice tone="info" title="Profit can't be worked out yet">
                  Add the cost of your products and DecisionGPT can show profit. <Link href="/data/products" className="font-medium underline underline-offset-4">Open product data</Link>
                </Notice>
              ) : null}
              <Notice tone="info" title="Cash flow">
                Cash-flow forecasting is not available in DecisionGPT.{" "}
                {finance > 0 ? `Your ${finance} money & accounts record${finance === 1 ? " is" : "s are"} stored but not analysed.` : "No money & accounts data has been added."}
              </Notice>
            </div>
          )}
        </LoadView>
      </Panel>
      <StoredReview reviewKey="financial_advisor" agentName="Financial Advisor" />
    </>
  );
}

/* ------------------------------------------------------------------ Marketing Advisor */
export function MarketingAdvisorPanels() {
  const load = useLoad(async (id) => {
    const [channels, kpis] = await Promise.all([api.getMarketingChannels(id), api.getKpis(id, 30)]);
    return { channels, kpis };
  });
  return (
    <>
      <Panel title="Your marketing channels" note="Spend and results as recorded in your marketing data.">
        <LoadView load={load} label="Reading your marketing records…">
          {({ channels, kpis }) => {
            if (channels.length === 0) {
              return (
                <div>
                  <p className="text-base text-foreground">No marketing data has been added, so there is nothing to compare yet.</p>
                  <div className="mt-3 flex flex-wrap gap-3">
                    <Link href="/data/manual?type=marketing_campaigns" className={btnSecondary}>Type marketing data in</Link>
                    <Link href="/data/upload/file" className={btnSecondary}>Upload a file</Link>
                  </div>
                </div>
              );
            }
            const withResults = channels.filter((c) => c.roi !== null && c.attributed_revenue !== null && c.spend > 0);
            const best = [...withResults].sort((a, b) => (b.roi as number) - (a.roi as number))[0];
            const worst = [...withResults].sort((a, b) => (a.roi as number) - (b.roi as number))[0];
            const totalSpend = channels.reduce((s, c) => s + c.spend, 0);
            return (
              <div className="space-y-5">
                <Facts
                  items={[
                    { label: "Total spent (all time)", value: inr(totalSpend) },
                    { label: "Channels", value: String(channels.length) },
                    { label: "Spent, last 30 days", value: inr(kpis.marketing_spend) },
                    { label: "Return on spend, last 30 days", value: kpis.marketing_roi !== null ? pct1(kpis.marketing_roi * 100) : "Not available", hint: kpis.marketing_roi === null ? "Needs recorded results" : undefined },
                  ]}
                />
                <div className="relative overflow-x-auto rounded-xl border border-border">
                  <table className="w-full min-w-[480px] text-left text-base">
                    <thead className="bg-muted-surface/60 text-sm text-muted">
                      <tr>
                        <th scope="col" className="px-4 py-2 font-medium">Channel</th>
                        <th scope="col" className="px-4 py-2 font-medium">Spent</th>
                        <th scope="col" className="px-4 py-2 font-medium">Brought in</th>
                        <th scope="col" className="px-4 py-2 font-medium">Return</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {channels.map((c) => (
                        <tr key={c.channel}>
                          <th scope="row" className="px-4 py-2 font-medium text-foreground">{c.channel}</th>
                          <td className="px-4 py-2">{inr(c.spend)}</td>
                          <td className="px-4 py-2">{c.attributed_revenue !== null ? inr(c.attributed_revenue) : "Not recorded"}</td>
                          <td className="px-4 py-2">{c.roi !== null ? pct1(c.roi * 100) : "Not available"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-muted">What your records suggest looking into <Kind kind="A suggestion" /></p>
                  {best && worst && best.channel !== worst.channel ? (
                    <ul className="list-disc space-y-1 pl-5 text-base text-foreground">
                      <li>{best.channel} has the highest recorded return ({pct1((best.roi as number) * 100)}); {worst.channel} has the lowest ({pct1((worst.roi as number) * 100)}).</li>
                      {((best.roi as number) - (worst.roi as number)) * 100 < 5 ? (
                        <li>These returns are very close, so your records don&apos;t clearly favour one channel.</li>
                      ) : (
                        <li>Check whether {worst.channel} is doing a different job (for example, reaching new customers) before moving money away from it.</li>
                      )}
                    </ul>
                  ) : withResults.length <= 1 ? (
                    <p className="text-base text-foreground">There isn&apos;t enough recorded result data to compare channels. Add results for each campaign to see which channel returns most.</p>
                  ) : null}
                  <p className="text-sm text-muted">
                    This compares past records only. It does not show that spending more on a channel would give the same return, and returns recorded by a channel may include sales that would have happened anyway.
                  </p>
                </div>
              </div>
            );
          }}
        </LoadView>
      </Panel>
      <Panel title="Try a change before you make it" note="Uses the What-If Tester, which estimates the effect of a marketing budget change on your sales.">
        <p className="text-base text-foreground">Ask the assistant “Should I increase my marketing spend?” for a simulated answer, or open the tester to choose your own change.</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <Link href="/simulation" className={btnPrimary}>🧪 Open the What-If Tester</Link>
          <Link href="/data/marketing_campaigns" className={btnSecondary}>View marketing data</Link>
        </div>
      </Panel>
    </>
  );
}

/* ------------------------------------------------------------------ Risk Manager */
export function RiskManagerPanels() {
  const { business } = useBusiness();
  const load = useLoad(async (id) => {
    const [caps, inventory, trend] = await Promise.all([api.getCapabilities(id), api.getInventoryStatus(id), api.getRevenueTrend(id, 3650)]);
    const lastSale = trend.length ? trend[trend.length - 1].date : null;
    const staleDays = lastSale ? Math.floor((Date.now() - new Date(lastSale).getTime()) / 86_400_000) : null;
    return { caps, inventory, lastSale, staleDays };
  });
  const [churn, setChurn] = useState<ChurnResult | null>(null);
  const [churnBusy, setChurnBusy] = useState(false);
  const [churnError, setChurnError] = useState<FriendlyError | null>(null);

  async function runChurn() {
    if (!business) return;
    setChurnBusy(true);
    setChurnError(null);
    try {
      setChurn(await api.getChurn(business.id));
    } catch (e) {
      setChurnError(friendlyError(e));
    } finally {
      setChurnBusy(false);
    }
  }
  const story = churn ? churnStory(churn.predictions) : null;

  return (
    <>
      <Panel title="What could trip you up" note="Only things DecisionGPT can actually see in your data are listed, each with its evidence.">
        <LoadView load={load} label="Checking your data and stock…">
          {({ caps, inventory, lastSale, staleDays }) => {
            const gaps = caps.capabilities.filter((c) => !c.enabled && capabilityName(c.feature) !== null);
            const low = inventory.filter((i) => i.low_stock);
            const stale = staleDays !== null && staleDays > 30;
            const nothing = gaps.length === 0 && low.length === 0 && !stale;
            return (
              <div className="space-y-4">
                {nothing ? (
                  <p className="text-base text-foreground"><Kind kind="From your records" /> <span className="ml-1">No data gaps, low-stock items or out-of-date sales were found.</span></p>
                ) : null}
                {stale ? (
                  <div className="rounded-xl border border-warning/40 bg-warning-soft/40 p-4">
                    <p className="font-semibold text-foreground">Your latest sale is {staleDays} days old</p>
                    <p className="text-base text-foreground">The newest sales record is dated {lastSale}. Answers about “the last 30 days” will be empty or out of date until you add newer sales.</p>
                  </div>
                ) : null}
                {low.length > 0 ? (
                  <div className="rounded-xl border border-warning/40 bg-warning-soft/40 p-4">
                    <p className="font-semibold text-foreground">{low.length} item{low.length === 1 ? " is" : "s are"} at or below the reorder level</p>
                    <ul className="mt-1 list-disc pl-5 text-base text-foreground">
                      {low.slice(0, 6).map((i) => (<li key={i.product_id}>{i.product_name}: {i.current_stock} in stock (reorder at {i.reorder_level})</li>))}
                    </ul>
                  </div>
                ) : null}
                {gaps.length > 0 ? (
                  <div className="rounded-xl border border-border p-4">
                    <p className="font-semibold text-foreground">Analyses that are limited by missing data</p>
                    <ul className="mt-1 space-y-1 text-base text-foreground">
                      {gaps.map((g) => (<li key={g.feature}><strong>{capabilityName(g.feature)}:</strong> {g.reason}</li>))}
                    </ul>
                    <div className="mt-3"><Link href="/data/quality" className={btnSecondary}>Open Data Preview &amp; Quality</Link></div>
                  </div>
                ) : null}
              </div>
            );
          }}
        </LoadView>
      </Panel>

      <Panel title="Customers who may stop buying" note="An estimate from a prediction model, run only when you ask. It gives a chance for each customer, not a certainty.">
        {!churn && !churnBusy ? (
          <button type="button" onClick={runChurn} className={btnPrimary}>Check my customers</button>
        ) : null}
        {churnBusy ? <Spinner label="Checking your customers…" /> : null}
        {churnError ? <ErrorBox error={churnError} onRetry={runChurn} /> : null}
        {story ? (
          <div className="space-y-2">
            <p><Kind kind="An estimate" /></p>
            <p className="text-base text-foreground">{story.headline}</p>
            <Link href="/customers" className="text-sm font-medium text-accent underline underline-offset-4">See the customer list</Link>
          </div>
        ) : null}
      </Panel>
      <StoredReview reviewKey="risk_manager" agentName="Risk Manager" />
    </>
  );
}

/* ------------------------------------------------------------------ Strategy Optimiser */
export function StrategyOptimiserPanels() {
  const load = useLoad(async (id) => {
    const [goals, latest] = await Promise.all([api.listGoals(id), loadLatestAnalysis(id)]);
    return { goals, latest };
  });
  return (
    <>
      <Panel title="Your latest recommendation" note="The top-ranked option DecisionGPT found for your most recent goal.">
        <LoadView load={load} label="Looking for your latest recommendation…">
          {({ goals, latest }) => {
            const s = latest.summary;
            if (!s) {
              return (
                <div>
                  <p className="text-base text-foreground">You haven&apos;t asked for a recommendation yet. Tell DecisionGPT a goal and it will compare possible actions.</p>
                  <div className="mt-3"><Link href="/decisions" className={btnPrimary}>Get suggestions</Link></div>
                  {goals.length > 0 ? <p className="mt-3 text-sm text-muted">You have {goals.length} saved goal{goals.length === 1 ? "" : "s"} — see Business Goals.</p> : null}
                </div>
              );
            }
            const goal = goals.find((g) => g.id === s.goal_id);
            const out = s.expected_outcome_json as Record<string, unknown>;
            const num = (k: string) => (typeof out[k] === "number" ? (out[k] as number) : null);
            const exp = num("expected_revenue");
            const base = num("baseline_revenue");
            return (
              <div className="space-y-4">
                {goal ? <p className="text-base text-muted">For your goal: <span className="text-foreground">{goalSentence(goal)}</span></p> : null}
                <div className="rounded-xl border border-accent/40 bg-accent-soft/30 p-4">
                  <p className="text-sm font-semibold text-muted">Top-ranked option <Kind kind="A suggestion" /></p>
                  <p className="mt-1 text-base text-foreground">{s.reasoning ?? "No explanation was stored for this recommendation."}</p>
                </div>
                <Facts
                  items={[
                    { label: "Risk level", value: s.risk_level ? s.risk_level.charAt(0).toUpperCase() + s.risk_level.slice(1) : "—" },
                    { label: "Estimated sales", value: exp !== null ? inr(exp) : "—", hint: "A simulation, not a promise" },
                    { label: "If nothing changes", value: base !== null ? inr(base) : "—" },
                    { label: "Internal score", value: s.confidence !== null ? s.confidence.toFixed(2) : "—", hint: "Not a probability of success" },
                  ]}
                />
                {(() => {
                  const run = latest.runs.find((r) => r.agent_name === "strategy_optimizer");
                  const conflicts = run && Array.isArray(run.output.conflicts) ? (run.output.conflicts as { raised_by?: string; concern?: string }[]) : [];
                  const rationale = run && typeof run.output.resolution_rationale === "string" ? run.output.resolution_rationale : null;
                  if (!run) return null;
                  return (
                    <div className="space-y-2">
                      <p className="text-sm font-semibold text-muted">How the reviews were weighed</p>
                      {rationale ? <p className="text-base text-foreground">{rationale}</p> : null}
                      {conflicts.length > 0 ? (
                        <ul className="list-disc space-y-1 pl-5 text-base text-foreground">
                          {conflicts.map((c, i) => (<li key={i}>{(c.raised_by ?? "").replace(/_/g, " ")}: {c.concern}</li>))}
                        </ul>
                      ) : null}
                    </div>
                  );
                })()}
                <p className="text-sm text-muted">
                  Given {timeAgo(s.created_at).toLowerCase()}. The ranking comes from simulating each option on your sales history; the decision is yours.
                </p>
                <Link href={`/decision?goal=${s.goal_id}`} className={btnSecondary}>Open the full recommendation</Link>
              </div>
            );
          }}
        </LoadView>
      </Panel>
      <Panel title="Compare options yourself">
        <p className="text-base text-foreground">Use the What-If Tester to try one change at a time, or Business Decisions to start from a goal.</p>
        <div className="mt-3 flex flex-wrap gap-3">
          <Link href="/simulation" className={btnSecondary}>🧪 What-If Tester</Link>
          <Link href="/decisions" className={btnSecondary}>💡 Business Decisions</Link>
        </div>
      </Panel>
    </>
  );
}
