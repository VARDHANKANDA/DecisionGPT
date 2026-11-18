"use client";

import Link from "next/link";
import { api, ApiError, type DecisionOutcome, type DecisionSummary, type TrackingDecision, type TrackingReport } from "@/lib/api";
import { Notice, btnSecondary } from "@/components/simple";
import { LoadView, Facts, Panel, useLoad } from "@/components/agent-ui";
import { Badge, DataTable, Workspace } from "@/components/platform-ui";
import { timeAgo } from "@/lib/friendly";

interface Row {
  d: DecisionSummary;
  o: DecisionOutcome | null;
  t: TrackingDecision | null;
}

interface Loaded {
  rows: Row[];
  report: TrackingReport | null;
}

async function optional<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

async function load(businessId: string): Promise<Loaded> {
  const list = await api.listDecisions(businessId);
  const rows = await Promise.all(
    list.map(async (d) => ({
      d,
      o: await optional(api.getOutcome(businessId, d.id)),
      t: await optional(api.trackingDecision(businessId, d.id)),
    })),
  );
  return { rows, report: await optional(api.trackingReport(businessId)) };
}

const SOURCE: Record<string, string> = { forecast: "Saved forecast", decision: "Recommendation figure", owner_plan: "Your plan" };
const METRIC: Record<string, string> = { units_sold: "units sold", revenue: "sales value", orders: "orders", marketing_spend: "marketing spend" };

const RESPONSE: Record<string, string> = {
  pending: "No response recorded",
  accepted: "Accepted",
  rejected: "Rejected",
  modified: "Modified",
  deferred: "Deferred",
};
const ACTION: Record<string, string> = {
  unknown: "Not recorded",
  not_executed: "Not carried out",
  partially_executed: "Partly carried out",
  executed: "Carried out",
};

/** One plain sentence saying whether the recommendation's figure can be put next to what happened, and why not. */
function comparability(t: TrackingDecision | null): string {
  const e = t?.expectations ?? [];
  if (e.length === 0) return "Not yet set up for comparison";
  const bad = e.find((x) => !x.expectation.comparable_to_actuals);
  if (bad) return "Cannot be compared: the expected figure is not on your business's own scale";
  const ev = e.filter((x) => x.comparison.status === "evaluated" || x.comparison.status === "partial").length;
  return ev > 0 ? `${ev} comparison(s) available` : "Waiting for a measured outcome";
}

function Body() {
  const l = useLoad(load);
  return (
    <LoadView load={l} label="Looking at your recommendations and what happened…">
      {({ rows, report }) => {
        const accepted = (report?.decisions.latest_response.accepted ?? 0) + (report?.decisions.latest_response.modified ?? 0);
        return (
          <div className="space-y-6">
            <Facts
              items={[
                { label: "Recommendations given", value: String(rows.length) },
                { label: "Accepted or modified", value: String(accepted) },
                { label: "Recorded as carried out", value: String(report?.decisions.executed_confirmed ?? 0) },
                { label: "Saved figures waiting for results", value: String(report?.awaiting_actuals?.length ?? 0) },
                { label: "Comparisons with a measured outcome", value: String(report?.comparisons.by_status.evaluated ?? 0) },
              ]}
            />
            <Notice tone="info" title="What this page can and cannot tell you">
              {report?.forecast_accuracy.statement ?? "No comparisons have been recorded yet."}{" "}
              {report?.business_impact.statement ??
                "Whether a recommendation helped cannot be told from these records: other things change at the same time."}
            </Notice>
            {rows.length === 0 ? (
              <Panel title="Nothing yet">
                <p className="text-base text-foreground">You have not asked for a recommendation yet.</p>
                <div className="mt-3">
                  <Link href="/decisions" className={btnSecondary}>
                    Get suggestions
                  </Link>
                </div>
              </Panel>
            ) : (
              <Panel title="Recommendation by recommendation">
                <DataTable
                  caption="What was recommended, what you did, and whether it can be checked"
                  columns={["Given", "Your response", "Action", "Can it be compared with what happened?", "A number you typed earlier"]}
                  rows={rows.map(({ d, o, t }) => [
                    timeAgo(d.created_at),
                    RESPONSE[t?.current.response ?? "pending"] ?? "—",
                    ACTION[t?.current.action_status ?? "unknown"] ?? "—",
                    comparability(t),
                    o ? "Recorded without a period or units — not used to judge the recommendation" : "—",
                  ])}
                />
                <p className="mt-3 text-sm text-muted">
                  <Badge>Why no “did it work” score</Badge> A recommendation can be accepted without being carried out, an accurate forecast can
                  accompany a change that did not help, and sales move for many reasons. Open{" "}
                  <Link href="/history" className="font-medium text-accent underline underline-offset-4">
                    Decision History
                  </Link>{" "}
                  to see the details of each recommendation.
                </p>
              </Panel>
            )}
            {report && (report.awaiting_actuals?.length ?? 0) > 0 ? (
              <Panel title="Saved forecasts and figures waiting for what actually happened">
                <DataTable
                  caption="Saved forecasts and plans without a complete measured outcome yet"
                  columns={["What", "Period", "Where it stands", "Can it be compared?"]}
                  rows={(report.awaiting_actuals ?? []).map((a) => [
                    `${SOURCE[a.source_kind] ?? a.source_kind}: ${METRIC[a.metric] ?? a.metric}`,
                    `${a.window[0]} to ${a.window[1]}`,
                    a.window_finished ? `Period is over — ${a.state}` : "Period not finished yet",
                    a.comparable_to_actuals ? "Yes, once the period is measured" : "No — not on your own scale",
                  ])}
                />
                <p className="mt-3 text-sm text-muted">
                  When a saved period is over, upload the sales for it and DecisionGPT measures it from your own data. A day with no data is never
                  counted as zero.
                </p>
              </Panel>
            ) : null}
            {report && (report.comparisons.details?.length ?? 0) > 0 ? (
              <Panel title="Expected figure next to what was measured">
                <DataTable
                  caption="Each saved figure, the measured outcome and whether the two can be compared"
                  columns={["What", "Period", "Expected", "Measured", "Difference (expected − measured)", "Comparison"]}
                  rows={(report.comparisons.details ?? []).map((c) => [
                    `${SOURCE[c.source_kind] ?? c.source_kind}: ${METRIC[c.metric] ?? c.metric}`,
                    `${c.window[0]} to ${c.window[1]}`,
                    c.expected !== null && c.expected !== undefined ? `${Math.round(c.expected).toLocaleString("en-IN")} ${c.unit}` : "—",
                    c.observed !== undefined ? `${Math.round(c.observed).toLocaleString("en-IN")} ${c.unit}` : "Not measured",
                    c.signed_error !== undefined ? `${c.signed_error >= 0 ? "+" : ""}${Math.round(c.signed_error).toLocaleString("en-IN")}` : "—",
                    c.status === "evaluated"
                      ? "Compared: same period, after the data cutoff"
                      : c.status === "partial"
                        ? `Partly compared (${Math.round((c.coverage_fraction ?? 0) * 100)}% of the period)`
                        : `Not compared — ${c.reason.split(":")[0].replace(/_/g, " ")}`,
                  ])}
                />
                <p className="mt-3 text-sm text-muted">
                  A figure being close does not show that a recommendation helped, and a recommendation can help even when the forecast was off.
                </p>
              </Panel>
            ) : null}
            {report && report.legacy_free_form_outcomes.recorded > 0 ? (
              <Notice tone="warning" title="Earlier recorded outcomes">
                {report.legacy_free_form_outcomes.recorded} outcome(s) were typed in without a period, units or scope. They are kept, but they
                are not compared with expectations or used to judge a recommendation.
              </Notice>
            ) : null}
          </div>
        );
      }}
    </LoadView>
  );
}

export default function OutcomesPage() {
  return (
    <Workspace title="Recommendation Outcomes" subtitle="What each recommendation expected, what you did, and what can be checked afterwards.">
      {() => <Body />}
    </Workspace>
  );
}
