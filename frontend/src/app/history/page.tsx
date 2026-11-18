"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type DecisionOutcome, type DecisionSummary, type TrackingResponse } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError } from "@/lib/friendly";
import { OutcomeForm } from "@/components/OutcomeForm";
import { DecisionResponsePanel } from "@/components/DecisionResponsePanel";
import { Card, EmptyState, PageHeader, RiskBadge, SecondaryLink, formatINR } from "@/components/ui";

type Current = { recorded: boolean; response: string; action_status: string; note?: string | null; action_start?: string | null };

export default function HistoryPage() {
  const { business, loading: businessLoading } = useBusiness();
  const [decisions, setDecisions] = useState<DecisionSummary[] | null>(null);
  const [outcomes, setOutcomes] = useState<Record<string, DecisionOutcome | null>>({});
  const [tracking, setTracking] = useState<Record<string, Current>>({});
  const [histories, setHistories] = useState<Record<string, TrackingResponse[]>>({});
  const [recording, setRecording] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshTracking = useCallback((businessId: string) => {
    api
      .listDecisionTracking(businessId)
      .then(async ({ decisions: rows }) => {
        const map: Record<string, Current> = {};
        for (const r of rows) map[r.decision_id] = r.current as Current;
        const withHistory = await Promise.all(
          rows
            .filter((r) => r.current.recorded)
            .map(async (r) => [r.decision_id, (await api.trackingDecision(businessId, r.decision_id)).history ?? []] as const),
        );
        setTracking(map);
        setHistories(Object.fromEntries(withHistory));
        setError(null);
      })
      .catch((e) => setError(friendlyError(e, "We couldn't load your recorded responses.").message));
  }, []);

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
    refreshTracking(business.id);
  }, [business, refreshTracking]);

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
      <PageHeader
        title="Strategic recommendations"
        subtitle="Every recommendation DecisionGPT has given you — what you decided, whether you carried it out, and, once you tell us, what actually happened."
      />
      {error ? (
        <p role="alert" className="mb-4 text-sm text-danger">
          {error}
        </p>
      ) : null}

      {decisions === null ? (
        <p className="text-sm text-muted" role="status">
          Loading…
        </p>
      ) : decisions.length === 0 ? (
        <EmptyState
          title="No recommendations yet"
          description="When you get a recommendation from Business Decisions, it is kept here."
          action={<SecondaryLink href="/decisions">Get a recommendation</SecondaryLink>}
        />
      ) : (
        <ul className="flex flex-col gap-4">
          {decisions.map((d) => {
            const outcome = outcomes[d.id];
            const cur: Current = tracking[d.id] ?? { recorded: false, response: "pending", action_status: "unknown" };
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
                        Figure from the scenario model{" "}
                        <span className="font-medium text-foreground">
                          {outcomeJson.expected_revenue !== undefined ? formatINR(outcomeJson.expected_revenue) : "—"}
                        </span>{" "}
                        (if nothing changed:{" "}
                        {outcomeJson.baseline_revenue !== undefined ? formatINR(outcomeJson.baseline_revenue) : "—"}). It has not been checked
                        against your own sales.
                      </p>
                      {d.reasoning ? <p className="mt-2 text-sm text-foreground">{d.reasoning}</p> : null}
                    </div>
                    <RiskBadge level={d.risk_level} />
                  </div>

                  {business ? (
                    <DecisionResponsePanel
                      key={`${d.id}-${cur.recorded ? histories[d.id]?.length ?? 0 : 0}`}
                      businessId={business.id}
                      decisionId={d.id}
                      current={cur}
                      history={histories[d.id]}
                      onSaved={() => refreshTracking(business.id)}
                    />
                  ) : null}

                  <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
                    <div className="text-sm">
                      {outcome === undefined ? (
                        <span className="text-muted">Checking…</span>
                      ) : outcome === null ? (
                        <button
                          onClick={() => setRecording(recording === d.id ? null : d.id)}
                          className="font-medium text-accent underline underline-offset-4"
                        >
                          {recording === d.id ? "Cancel" : "Add a note of what happened"}
                        </button>
                      ) : (
                        <span className="text-foreground">
                          A note of what happened is saved. It has no period or units, so it is not used to judge the recommendation.
                        </span>
                      )}
                    </div>
                    <Link href={`/decision?goal=${d.goal_id}`} className="text-sm font-medium text-accent underline underline-offset-4">
                      Open
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
