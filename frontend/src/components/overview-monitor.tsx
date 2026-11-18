"use client";

import Link from "next/link";
import { platform, formatKpi } from "@/lib/platform-api";
import { LoadView, useLoad } from "@/components/agent-ui";
import { Badge } from "@/components/platform-ui";

/**
 * The monitoring half of the Overview: health, alerts, KPI targets and data readiness, all read live from the
 * business-OS endpoints. Opening the Overview runs one on-demand alert check (there is no background monitoring).
 */
export function OverviewMonitor({ businessId }: { businessId: string }) {
  const load = useLoad(async () => {
    await platform.checkAlerts(businessId, "today").catch(() => null);
    const [health, alerts, pipeline, kpis] = await Promise.all([
      platform.health(businessId, 30, "today"),
      platform.alerts(businessId, "active"),
      platform.pipeline(businessId),
      platform.kpis(businessId, 30, "today"),
    ]);
    return { health, alerts: alerts.alerts, pipeline, kpis };
  });
  return (
    <LoadView load={load} label="Checking health, alerts and data readiness…">
      {({ health, alerts, pipeline, kpis }) => {
        const withTarget = kpis.kpis.filter((k) => k.target);
        const stage = pipeline.stages.find((s) => s.state === "failed" || s.state === "needs_attention") ?? pipeline.stages.find((s) => s.state !== "ready" && !s.optional && s.key !== "profiling") ?? null;
        return (
          <div className="grid gap-8 lg:grid-cols-3">
            <section aria-labelledby="ov-health" className="min-w-0 rounded-2xl border border-border bg-surface p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 id="ov-health" className="text-xl font-semibold text-foreground">Business health</h2>
                <Link href="/health" className="text-sm font-medium text-accent underline underline-offset-4">Details</Link>
              </div>
              {health.composite_score === null ? (
                <p className="mt-3 text-base text-foreground">No overall score yet. {health.composite_unavailable_reason}</p>
              ) : (
                <>
                  <p className="mt-3 text-4xl font-semibold text-foreground">
                    {health.composite_score.toFixed(0)}<span className="text-lg text-muted"> / 100</span>
                  </p>
                  <p className="mt-1"><Badge tone={health.composite_score >= 75 ? "good" : health.composite_score >= 50 ? "warn" : "bad"}>{health.level}</Badge></p>
                </>
              )}
              <p className="mt-3 text-xs text-muted">A simple guide built from a few of your own records, not a verdict. Last 30 days from today.</p>
            </section>

            <section aria-labelledby="ov-alerts" className="min-w-0 rounded-2xl border border-border bg-surface p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 id="ov-alerts" className="text-xl font-semibold text-foreground">Active alerts</h2>
                <Link href="/alerts" className="text-sm font-medium text-accent underline underline-offset-4">All alerts</Link>
              </div>
              {alerts.length === 0 ? (
                <p className="mt-3 text-base text-foreground">None. No enabled rule is triggered by your records right now.</p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {alerts.slice(0, 3).map((a) => (
                    <li key={a.id} className="text-base text-foreground">
                      <Badge tone={a.severity === "high" ? "bad" : a.severity === "medium" ? "warn" : "neutral"}>{a.severity}</Badge> {a.title}
                    </li>
                  ))}
                  {alerts.length > 3 ? <li className="text-sm text-muted">and {alerts.length - 3} more</li> : null}
                </ul>
              )}
              <p className="mt-3 text-xs text-muted">Checked when you open this page. DecisionGPT does not watch in the background.</p>
            </section>

            <section aria-labelledby="ov-ready" className="min-w-0 rounded-2xl border border-border bg-surface p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 id="ov-ready" className="text-xl font-semibold text-foreground">Data readiness</h2>
                <Link href="/data/prepare" className="text-sm font-medium text-accent underline underline-offset-4">Pipeline</Link>
              </div>
              <p className="mt-3 text-base text-foreground">
                {pipeline.ready_for_analysis ? "Ready for analysis." : "Not fully ready."}
                {stage ? ` ${stage.name}: ${stage.detail}` : ""}
              </p>
              {pipeline.downstream_may_need_refresh.length > 0 ? <p className="mt-2 text-sm text-warning">Your data changed after: {pipeline.downstream_may_need_refresh.join(", ")}.</p> : null}
            </section>

            <section aria-labelledby="ov-kpi" className="min-w-0 rounded-2xl border border-border bg-surface p-6 lg:col-span-3">
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 id="ov-kpi" className="text-xl font-semibold text-foreground">KPIs against your targets</h2>
                <Link href="/kpis" className="text-sm font-medium text-accent underline underline-offset-4">KPI Monitoring</Link>
              </div>
              {withTarget.length === 0 ? (
                <p className="mt-3 text-base text-foreground">
                  You have not set a target yet. Choose what “good” means for a number you care about in <Link href="/kpis" className="font-medium underline underline-offset-4">KPI Monitoring</Link>.
                </p>
              ) : (
                <ul className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {withTarget.map((k) => (
                    <li key={k.key} className="min-w-0 rounded-xl bg-muted-surface/60 p-4">
                      <p className="text-sm text-muted">{k.name}</p>
                      <p className="text-xl font-semibold text-foreground">{formatKpi(k.target_period_value, k.unit)}</p>
                      <p className="text-sm text-muted">target {k.target!.direction === "higher" ? "at least" : "at most"} {formatKpi(k.target!.value, k.unit)}</p>
                      <Badge tone={k.status === "met" ? "good" : k.status === "not_met" ? "bad" : "neutral"}>{k.status === "met" ? "Target met" : k.status === "not_met" ? "Target not met" : "No data"}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        );
      }}
    </LoadView>
  );
}
