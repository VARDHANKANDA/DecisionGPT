"use client";

import { useEffect, useState } from "react";
import {
  api,
  type ChannelPerformance,
  type CustomerSummary,
  type DataSummary,
  type InventoryStatus,
  type ProductPerformance,
} from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, EmptyState, PageHeader, SecondaryLink, Stat, formatINR } from "@/components/ui";

const TABS = ["Overview", "Sales", "Customers", "Marketing", "Inventory"] as const;
type Tab = (typeof TABS)[number];

export default function DataAnalyticsPage() {
  const { business, loading: businessLoading } = useBusiness();
  const [tab, setTab] = useState<Tab>("Overview");
  const [summary, setSummary] = useState<DataSummary | null>(null);

  useEffect(() => {
    if (!business) return;
    api.getDataSummary(business.id).then(setSummary);
  }, [business]);

  if (!businessLoading && !business) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="text-muted">Set up your business first.</p>
        <div className="mt-4">
          <SecondaryLink href="/onboarding">Go to onboarding</SecondaryLink>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader title="Data & analytics" subtitle="Every number below comes directly from your uploaded data." />
        <SecondaryLink href="/data/upload">Upload more data</SecondaryLink>
      </div>

      <nav className="mb-8 flex gap-1 overflow-x-auto border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`shrink-0 border-b-2 px-4 py-2 text-sm font-medium transition ${
              tab === t ? "border-accent text-accent" : "border-transparent text-muted hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </nav>

      {!business ? null : tab === "Overview" ? (
        <OverviewTab summary={summary} />
      ) : tab === "Sales" ? (
        <SalesTab businessId={business.id} />
      ) : tab === "Customers" ? (
        <CustomersTab businessId={business.id} />
      ) : tab === "Marketing" ? (
        <MarketingTab businessId={business.id} />
      ) : (
        <InventoryTab businessId={business.id} />
      )}
    </div>
  );
}

function OverviewTab({ summary }: { summary: DataSummary | null }) {
  if (!summary) return <p className="text-sm text-muted">Loading…</p>;
  const hasAnyData = Object.values(summary).some((v) => v > 0);
  if (!hasAnyData) {
    return (
      <EmptyState
        title="No business data yet"
        description="Upload your sales data to unlock analytics."
        action={<SecondaryLink href="/data/upload">Upload data</SecondaryLink>}
      />
    );
  }
  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
      <Stat label="Products" value={summary.products.toLocaleString("en-IN")} />
      <Stat label="Customers" value={summary.customers.toLocaleString("en-IN")} />
      <Stat label="Sales" value={summary.sales.toLocaleString("en-IN")} />
      <Stat label="Marketing campaigns" value={summary.marketing_campaigns.toLocaleString("en-IN")} />
      <Stat label="Inventory records" value={summary.inventory_records.toLocaleString("en-IN")} />
    </div>
  );
}

function SalesTab({ businessId }: { businessId: string }) {
  const [products, setProducts] = useState<ProductPerformance[] | null>(null);

  useEffect(() => {
    api.getTopProducts(businessId, 10).then(setProducts);
  }, [businessId]);

  if (!products) return <p className="text-sm text-muted">Loading…</p>;
  if (products.length === 0) {
    return (
      <EmptyState
        title="No product sales yet"
        description="Upload products and sales data to see performance by product."
      />
    );
  }

  return (
    <Card>
      <h2 className="text-sm font-medium text-foreground">Top products by revenue</h2>
      <div className="overflow-x-auto">
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="py-2 font-medium">Product</th>
              <th className="py-2 font-medium">Units sold</th>
              <th className="py-2 text-right font-medium">Revenue</th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.product_id} className="border-b border-border last:border-0">
                <td className="py-2">{p.name}</td>
                <td className="py-2">{p.units_sold.toLocaleString("en-IN")}</td>
                <td className="py-2 text-right font-medium">{formatINR(p.revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function CustomersTab({ businessId }: { businessId: string }) {
  const [summary, setSummary] = useState<CustomerSummary | null>(null);

  useEffect(() => {
    api.getCustomerSummary(businessId).then(setSummary);
  }, [businessId]);

  if (!summary) return <p className="text-sm text-muted">Loading…</p>;
  if (summary.total_customers === 0) {
    return <EmptyState title="No customers yet" description="Upload customer data to see this breakdown." />;
  }

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      <Stat label="Total customers" value={summary.total_customers.toLocaleString("en-IN")} />
      <Stat label="New in last 30 days" value={summary.new_customers_last_30_days.toLocaleString("en-IN")} />
      <Stat
        label="Avg. lifetime value"
        value={summary.avg_monetary_value !== null ? formatINR(summary.avg_monetary_value) : "Unavailable"}
      />
      <Stat
        label="Avg. purchase frequency"
        value={summary.avg_purchase_frequency !== null ? summary.avg_purchase_frequency.toFixed(1) : "Unavailable"}
      />
    </div>
  );
}

function MarketingTab({ businessId }: { businessId: string }) {
  const [channels, setChannels] = useState<ChannelPerformance[] | null>(null);

  useEffect(() => {
    api.getMarketingChannels(businessId).then(setChannels);
  }, [businessId]);

  if (!channels) return <p className="text-sm text-muted">Loading…</p>;
  if (channels.length === 0) {
    return (
      <EmptyState
        title="No marketing campaigns yet"
        description="Upload marketing campaign data to see spend and ROI by channel."
      />
    );
  }

  return (
    <Card>
      <h2 className="text-sm font-medium text-foreground">Performance by channel</h2>
      <div className="overflow-x-auto">
        <table className="mt-4 w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="py-2 font-medium">Channel</th>
              <th className="py-2 font-medium">Campaigns</th>
              <th className="py-2 text-right font-medium">Spend</th>
              <th className="py-2 text-right font-medium">Attributed revenue</th>
              <th className="py-2 text-right font-medium">ROI</th>
            </tr>
          </thead>
          <tbody>
            {channels.map((c) => (
              <tr key={c.channel} className="border-b border-border last:border-0">
                <td className="py-2">{c.channel}</td>
                <td className="py-2">{c.campaigns}</td>
                <td className="py-2 text-right">{formatINR(c.spend)}</td>
                <td className="py-2 text-right">
                  {c.attributed_revenue !== null ? formatINR(c.attributed_revenue) : "Unavailable"}
                </td>
                <td className="py-2 text-right font-medium">
                  {c.roi !== null ? `${(c.roi * 100).toFixed(0)}%` : "Unavailable"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function InventoryTab({ businessId }: { businessId: string }) {
  const [statuses, setStatuses] = useState<InventoryStatus[] | null>(null);

  useEffect(() => {
    api.getInventoryStatus(businessId).then(setStatuses);
  }, [businessId]);

  if (!statuses) return <p className="text-sm text-muted">Loading…</p>;
  if (statuses.length === 0) {
    return (
      <EmptyState
        title="No inventory data yet"
        description="Upload inventory data to see stock levels and reorder alerts."
      />
    );
  }

  return (
    <Card>
      <h2 className="text-sm font-medium text-foreground">Current stock levels</h2>
      <div className="overflow-x-auto">
      <table className="mt-4 w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted">
            <th className="py-2 font-medium">Product</th>
            <th className="py-2 text-right font-medium">Stock</th>
            <th className="py-2 text-right font-medium">Reorder level</th>
            <th className="py-2 text-right font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {statuses.map((s) => (
            <tr key={s.product_id} className="border-b border-border last:border-0">
              <td className="py-2">{s.product_name}</td>
              <td className="py-2 text-right">{s.current_stock.toLocaleString("en-IN")}</td>
              <td className="py-2 text-right">{s.reorder_level ?? "—"}</td>
              <td className="py-2 text-right">
                {s.low_stock ? (
                  <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-medium text-warning">
                    Low stock
                  </span>
                ) : (
                  <span className="rounded-full bg-success-soft px-3 py-1 text-xs font-medium text-success">OK</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </Card>
  );
}
