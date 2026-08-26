"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type DecisionOutcome, type DecisionSummary } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { OutcomeForm } from "@/components/OutcomeForm";
import { Card, EmptyState, PageHeader, RiskBadge, SecondaryLink, formatINR } from "@/components/ui";

export default function HistoryPage() {
  const { business, loading: businessLoading } = useBusiness();
  const [decisions, setDecisions] = useState<DecisionSummary[] | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, DecisionOutcome | null>>({});
  const [recording, setRecording] = useState<string | null>(null);

  function loadOutcomes(list: DecisionSummary[], businessId: string) {
    Promise.all(
      list.map(async (d) => {
        try {
          return [d.id, await api.getOutcome(businessId, d.id)] as const;
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) return [d.id, null] as const;
          throw err;
        }
      })
    ).then((entries) => setOutcomes(Object.fromEntries(entries)));
  }

  useEffect(() => {
    if (!business) return;
    api.listDecisions(business.id).then((list) => {
      setDecisions(list);
      loadOutcomes(list, business.id);
    });
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
    <div className="mx-auto max-w-4xl px-6 py-12">
      <PageHeader title="Decision history" subtitle="Every decision DecisionGPT has made for this business, and what actually happened." />

      {decisions === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : decisions.length === 0 ? (
        <EmptyState
          title="No decisions yet"
          description="Run a decision analysis from the Decision page to see it appear here."
          action={<SecondaryLink href="/decision">Run an analysis</SecondaryLink>}
        />
      ) : (
        <ul className="flex flex-col gap-4">
          {decisions.map((d) => {
            const outcome = outcomes[d.id];
            const outcomeJson = d.expected_outcome_json as {
              expected_revenue?: number;
              baseline_revenue?: number;
              model_name?: string;
            };
            return (
              <li key={d.id}>
                <Card>
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-xs text-muted">{new Date(d.created_at).toLocaleString("en-IN")}</p>
                      <p className="mt-1 text-sm text-muted">
                        Expected revenue{" "}
                        <span className="font-medium text-foreground">
                          {outcomeJson.expected_revenue !== undefined ? formatINR(outcomeJson.expected_revenue) : "—"}
                        </span>{" "}
                        (baseline{" "}
                        {outcomeJson.baseline_revenue !== undefined ? formatINR(outcomeJson.baseline_revenue) : "—"})
                      </p>
                      {d.reasoning ? <p className="mt-2 text-sm text-foreground">{d.reasoning}</p> : null}
                    </div>
                    <RiskBadge level={d.risk_level} />
                  </div>

                  <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
                    <div className="text-sm">
                      {outcome === undefined ? (
                        <span className="text-muted">Checking for a recorded outcome…</span>
                      ) : outcome === null ? (
                        <button
                          onClick={() => setRecording(recording === d.id ? null : d.id)}
                          className="font-medium text-accent underline underline-offset-4"
                        >
                          {recording === d.id ? "Cancel" : "Record actual outcome"}
                        </button>
                      ) : (
                        <span className="text-foreground">
                          Outcome recorded
                          {outcome.goal_achievement_score !== null
                            ? ` — achieved ${(outcome.goal_achievement_score * 100).toFixed(0)}% of the predicted change`
                            : ""}
                        </span>
                      )}
                    </div>
                    <Link
                      href={`/decision?goal=${d.goal_id}`}
                      className="text-sm font-medium text-accent underline underline-offset-4"
                    >
                      View details
                    </Link>
                  </div>

                  {recording === d.id && outcome === null ? (
                    <div className="mt-3 rounded-xl bg-muted-surface p-4">
                      <OutcomeForm
                        businessId={business!.id}
                        decisionId={d.id}
                        expectedOutcome={d.expected_outcome_json}
                        onRecorded={() => {
                          setRecording(null);
                          if (decisions) loadOutcomes(decisions, business!.id);
                        }}
                        compact
                      />
                    </div>
                  ) : null}
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
