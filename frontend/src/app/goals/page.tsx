"use client";

import Link from "next/link";
import { useBusiness } from "@/lib/business-context";
import { timeAgo } from "@/lib/friendly";
import { goalSentence } from "@/lib/narrate";
import { api } from "@/lib/api";
import { Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, useLoad } from "@/components/agent-ui";

const KPI_LABEL: Record<string, string> = {
  revenue: "Sales",
  profit: "Profit",
  orders: "Number of orders",
  churn_rate: "Customers kept",
  marketing_roi: "Return on marketing",
  inventory_risk: "Stock risk",
};

export default function GoalsPage() {
  const { business, loading } = useBusiness();
  const load = useLoad((id) => api.listGoals(id));

  if (loading) return <Page title="Business Goals"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Business Goals" subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  return (
    <Page
      title="Business Goals & KPIs"
      subtitle="What you want to improve, and the numbers you want to hold yourself to."
      action={<Link href="/decisions" className={btnPrimary}>Add a goal</Link>}
    >
      <section className="mb-6 rounded-2xl border border-border bg-surface p-5">
        <h2 className="text-lg font-semibold text-foreground">KPI targets</h2>
        <p className="mt-1 text-base text-foreground">Set a number you want a KPI to reach, and DecisionGPT shows whether you are meeting it — in KPI Monitoring, the Overview and Smart Alerts.</p>
        <div className="mt-3"><Link href="/kpis" className={btnSecondary}>Set KPI targets</Link></div>
      </section>
      <LoadView load={load} label="Loading your goals…">
        {(goals) =>
          goals.length === 0 ? (
            <section className="rounded-2xl border border-dashed border-border bg-surface/60 p-8 text-center">
              <p className="text-xl font-semibold text-foreground">No goals yet</p>
              <p className="mx-auto mt-2 max-w-xl text-base text-muted">
                Write a goal in a sentence — for example “Increase profit by 15% in 3 months.” DecisionGPT turns it into a target and suggests actions to compare.
              </p>
              <div className="mt-4"><Link href="/decisions" className={btnPrimary}>Write my first goal</Link></div>
            </section>
          ) : (
            <>
              <ul className="space-y-4">
                {goals.map((g) => (
                  <li key={g.id}>
                    <article className="rounded-2xl border border-border bg-surface p-5">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h2 className="text-lg font-semibold text-foreground">{goalSentence(g)}</h2>
                          <p className="mt-1 text-sm text-muted">
                            Measured by: <span className="text-foreground">{KPI_LABEL[g.primary_kpi] ?? g.primary_kpi.replace(/_/g, " ")}</span> · Status: <span className="text-foreground capitalize">{g.status}</span> · Added {timeAgo(g.created_at).toLowerCase()}
                          </p>
                        </div>
                        <Link href={`/decision?goal=${g.id}`} className={btnSecondary}>Get suggestions</Link>
                      </div>
                    </article>
                  </li>
                ))}
              </ul>
              <p className="mt-6 text-sm text-muted">
                A goal is used by Business Decisions: DecisionGPT simulates possible pricing, marketing and stock actions against it and ranks them. Priorities beyond the goal itself (such as ordering several metrics by importance) are not settings in DecisionGPT yet.
              </p>
            </>
          )
        }
      </LoadView>
    </Page>
  );
}
