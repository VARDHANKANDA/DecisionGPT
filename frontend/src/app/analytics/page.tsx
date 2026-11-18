"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  api,
  type ChannelPerformance,
  type CustomerSummary,
  type InventoryStatus,
  type KPISnapshot,
  type PeriodComparison,
  type ProductPerformance,
  type RevenueTrendPoint,
} from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { inr, revenueHeadline } from "@/lib/narrate";
import { useLibrary } from "@/lib/use-library";
import { AnswerBlock, DataUsed, ErrorBox, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";

interface Loaded {
  kpis: KPISnapshot;
  comparison: PeriodComparison;
  trend: RevenueTrendPoint[];
  products: ProductPerformance[];
  customers: CustomerSummary;
  channels: ChannelPerformance[];
  stock: InventoryStatus[];
}

export default function AnalyticsPage() {
  const { business, loading } = useBusiness();
  const library = useLibrary();
  const [data, setData] = useState<Loaded | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    Promise.all([
      api.getKpis(business.id, 30),
      api.getPeriodComparison(business.id, 30),
      api.getRevenueTrend(business.id, 90),
      api.getTopProducts(business.id, 10),
      api.getCustomerSummary(business.id),
      api.getMarketingChannels(business.id),
      api.getInventoryStatus(business.id),
    ])
      .then(([kpis, comparison, trend, products, customers, channels, stock]) => {
        if (cancelled) return;
        setData({ kpis, comparison, trend, products, customers, channels, stock });
        setError(null);
      })
      .catch((e) => !cancelled && setError(friendlyError(e, "We couldn't load your business numbers right now.")));
    return () => {
      cancelled = true;
    };
  }, [business, attempt]);

  if (loading) return <Page title="Business Analytics"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Business Analytics" subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  const subtitle = "Understand what is happening in your business. Every number comes from the data you added.";
  if (error) {
    return (
      <Page title="Business Analytics" subtitle={subtitle}>
        <ErrorBox error={error} onRetry={() => setAttempt((n) => n + 1)} />
      </Page>
    );
  }
  if (!data) return <Page title="Business Analytics" subtitle={subtitle}><Spinner label="Adding up your numbers…" /></Page>;

  const { kpis, comparison, trend, products, customers, channels, stock } = data;

  if (kpis.orders === 0 && comparison.current_revenue === 0 && comparison.previous_revenue === 0) {
    return (
      <Page title="Business Analytics" subtitle={subtitle}>
        <DataUsed library={library} types={["sales", "products", "customers", "marketing_campaigns", "inventory"]} />
        <div className="mt-6">
          <Notice title="No sales in the last 30 days">
            Add your sales and we&apos;ll show your totals, trends and best sellers here.
          </Notice>
          <div className="mt-4 flex flex-wrap gap-3">
            <Link href="/data/upload/file" className={btnPrimary}>Add my data</Link>
            <Link href="/data/samples" className={btnSecondary}>Look at example data first</Link>
          </div>
        </div>
      </Page>
    );
  }

  const lowStock = stock.filter((s) => s.low_stock);
  const best = products[0];
  const marketingTotal = channels.reduce((s, c) => s + c.spend, 0);

  return (
    <Page title="Business Analytics" subtitle={subtitle} wide>
      <div className="space-y-8">
        <AnswerBlock
          label="What changed?"
          headline={revenueHeadline(comparison, 30)}
          why="Seeing the direction of your sales early lets you act while there is still time to change it."
          shows={
            <ul className="list-disc space-y-1 pl-5 text-base">
              <li>
                {comparison.current_orders.toLocaleString("en-IN")} orders in the last 30 days, compared with{" "}
                {comparison.previous_orders.toLocaleString("en-IN")} in the 30 days before.
              </li>
              {best ? <li>Your best seller so far is {best.name}, with {inr(best.revenue)} in sales.</li> : null}
              {lowStock.length > 0 ? (
                <li>{lowStock.length} product{lowStock.length === 1 ? " is" : "s are"} running low on stock: {lowStock.slice(0, 3).map((s) => s.product_name).join(", ")}.</li>
              ) : null}
            </ul>
          }
          watch={kpis.notes.length > 0 ? kpis.notes.join(" ") : undefined}
          next={
            <>
              To see which products went up or down, ask{" "}
              <Link href={`/chat?q=${encodeURIComponent("What is improving and what is getting worse?")}`} className="font-medium text-accent underline underline-offset-4">Chat with Your Data</Link>.
              {" "}Or see what may come next in{" "}
              <Link href="/forecast" className="font-medium text-accent underline underline-offset-4">Forecasting</Link>.
            </>
          }
        />

        <section aria-labelledby="key-numbers">
          <h2 id="key-numbers" className="text-2xl font-semibold text-foreground">Key numbers — last 30 days</h2>
          <dl className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Figure label="Sales" value={inr(kpis.revenue)} />
            <Figure label="Orders" value={kpis.orders.toLocaleString("en-IN")} />
            <Figure label="Customers who bought" value={kpis.customers.toLocaleString("en-IN")} />
            <Figure label="Average order" value={kpis.average_order_value !== null ? inr(kpis.average_order_value) : "Not available"} />
            <Figure
              label="Profit"
              value={kpis.profit !== null ? inr(kpis.profit) : "Not available"}
              hint={kpis.profit === null ? "Add what your products cost you to see this." : undefined}
            />
            <Figure label="Spent on marketing" value={inr(kpis.marketing_spend)} />
            <Figure
              label="Return on marketing"
              value={kpis.marketing_roi !== null ? `${(kpis.marketing_roi * 100).toFixed(0)}%` : "Not available"}
              hint={kpis.marketing_roi === null ? "Needs marketing spend and results." : undefined}
            />
            <Figure
              label="Visitors who bought"
              value={kpis.conversion_rate !== null ? `${(kpis.conversion_rate * 100).toFixed(1)}%` : "Not available"}
              hint={kpis.conversion_rate === null ? "Needs visitor numbers from your marketing data." : undefined}
            />
          </dl>
        </section>

        <section className="rounded-2xl border border-border bg-surface p-5" aria-label="Sales over the last 90 days">
          <h2 className="text-lg font-semibold text-foreground">Sales over the last 90 days (₹ per day)</h2>
          <div className="mt-3 h-64">
            {trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} minTickGap={32} tickFormatter={(d: string) => d.slice(5)} />
                  <YAxis tick={{ fontSize: 12 }} width={52} />
                  <Tooltip formatter={(v) => inr(Number(v))} />
                  <Line type="monotone" dataKey="revenue" name="Sales" stroke="var(--accent)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-base text-muted">There isn&apos;t enough history for a chart yet.</p>
            )}
          </div>
        </section>

        <div className="grid gap-6 lg:grid-cols-2">
          <Section title="Best sellers" empty={products.length === 0} emptyText="Add products and sales to see which sell best." link="/data/products" linkText="Your products">
            <Table
              head={["Product", "Sold", "Sales"]}
              rows={products.map((p) => [p.name, p.units_sold.toLocaleString("en-IN"), inr(p.revenue)])}
            />
          </Section>

          <Section title="Your customers" empty={customers.total_customers === 0} emptyText="Add customers to see who they are." link="/customers" linkText="Customer analysis">
            <dl className="grid grid-cols-2 gap-4 p-5">
              <Figure label="Customers" value={customers.total_customers.toLocaleString("en-IN")} />
              <Figure label="New in 30 days" value={customers.new_customers_last_30_days.toLocaleString("en-IN")} />
              <Figure label="Average spent each" value={customers.avg_monetary_value !== null ? inr(customers.avg_monetary_value) : "Not available"} />
              <Figure label="Average times bought" value={customers.avg_purchase_frequency !== null ? customers.avg_purchase_frequency.toFixed(1) : "Not available"} />
            </dl>
          </Section>

          <Section
            title="Marketing"
            empty={channels.length === 0}
            emptyText="Add your marketing spending to see which channels pay off."
            link="/data/marketing_campaigns"
            linkText="Your marketing data"
          >
            <Table
              head={["Channel", "Spent", "Return"]}
              rows={channels.map((c) => [c.channel, inr(c.spend), c.roi !== null ? `${(c.roi * 100).toFixed(0)}%` : "Not available"])}
            />
            {marketingTotal > 0 ? <p className="px-5 pb-4 text-sm text-muted">Total spent: {inr(marketingTotal)}</p> : null}
          </Section>

          <Section title="Stock" empty={stock.length === 0} emptyText="Add your stock levels to get low-stock warnings." link="/data/inventory" linkText="Your stock data">
            <Table
              head={["Product", "In stock", "Status"]}
              rows={stock.map((s) => [
                s.product_name,
                s.current_stock.toLocaleString("en-IN"),
                s.low_stock ? "⚠ Running low" : "✓ OK",
              ])}
            />
          </Section>
        </div>

        <DataUsed library={library} types={["sales", "products", "customers", "marketing_campaigns", "inventory"]} />
      </div>
    </Page>
  );
}

function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="min-w-0 rounded-2xl border border-border bg-surface p-4">
      <dt className="text-sm text-muted">{label}</dt>
      <dd className="mt-1 break-words text-2xl font-semibold text-foreground">{value}</dd>
      {hint ? <p className="mt-1 text-sm text-muted">{hint}</p> : null}
    </div>
  );
}

function Section({
  title,
  empty,
  emptyText,
  link,
  linkText,
  children,
}: {
  title: string;
  empty: boolean;
  emptyText: string;
  link: string;
  linkText: string;
  children: React.ReactNode;
}) {
  return (
    <section className="min-w-0 rounded-2xl border border-border bg-surface">
      <h2 className="px-5 pt-5 text-lg font-semibold text-foreground">{title}</h2>
      {empty ? <p className="px-5 py-4 text-base text-muted">{emptyText}</p> : children}
      <p className="px-5 pb-4 pt-1">
        <Link href={link} className="text-base font-medium text-accent underline underline-offset-4">{linkText}</Link>
      </p>
    </section>
  );
}

function Table({ head, rows }: { head: string[]; rows: string[][] }) {
  return (
    <div className="relative overflow-x-auto" tabIndex={0} aria-label="Table, scrolls sideways">
      <table className="mt-2 w-full text-base">
        <thead className="text-left text-sm text-muted">
          <tr>
            {head.map((h, i) => (
              <th key={h} className={`px-5 py-2 font-medium ${i > 0 ? "text-right" : ""}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-t border-border">
              {r.map((c, j) => (
                <td key={j} className={`px-5 py-2 ${j > 0 ? "whitespace-nowrap text-right" : "font-medium text-foreground"}`}>{c}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
