"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type Goal } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, EmptyState, PageHeader, PrimaryButton, SecondaryLink } from "@/components/ui";

const EXAMPLES = [
  "Increase profit by 15% in 3 months.",
  "Increase revenue by 20% in 2 months.",
  "Reduce churn by 10%.",
  "Improve marketing ROI by 25% in 1 month.",
];

const OBJECTIVE_LABELS: Record<string, string> = {
  increase_revenue: "Increase revenue",
  increase_profit: "Increase profit",
  increase_sales: "Increase sales",
  reduce_churn: "Reduce churn",
  improve_marketing_roi: "Improve marketing ROI",
  reduce_inventory_risk: "Reduce inventory risk",
};

export default function GoalsPage() {
  const { business, loading: businessLoading } = useBusiness();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [loading, setLoading] = useState(true);
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!business) return;
    api
      .listGoals(business.id)
      .then(setGoals)
      .finally(() => setLoading(false));
  }, [business]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!business) return;
    setSubmitting(true);
    setError(null);
    try {
      const goal = await api.createGoal(business.id, text);
      setGoals((prev) => [goal, ...prev]);
      setText("");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Could not create that goal. Please try again."
      );
    } finally {
      setSubmitting(false);
    }
  }

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
    <div className="mx-auto max-w-3xl px-6 py-12">
      <PageHeader
        title="Goals"
        subtitle="Tell DecisionGPT what you want to achieve, in plain language."
      />

      <Card>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g. Increase profit by 15% in the next 3 months."
            rows={2}
            className="input resize-none"
            required
          />
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                type="button"
                key={ex}
                onClick={() => setText(ex)}
                className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:bg-muted-surface"
              >
                {ex}
              </button>
            ))}
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <div>
            <PrimaryButton type="submit" disabled={submitting || !text}>
              {submitting ? "Checking…" : "Set goal"}
            </PrimaryButton>
          </div>
        </form>
      </Card>

      <div className="mt-8">
        {loading ? (
          <p className="text-sm text-muted">Loading goals…</p>
        ) : goals.length === 0 ? (
          <EmptyState
            title="No goals yet"
            description="Once you set a goal, DecisionGPT will use your real data to check it's achievable before tracking it."
          />
        ) : (
          <ul className="flex flex-col gap-3">
            {goals.map((goal) => (
              <li key={goal.id}>
                <Card className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-foreground">
                      {OBJECTIVE_LABELS[goal.objective] ?? goal.objective} by {goal.target_value}
                      {goal.target_unit === "percent" ? "%" : ` ${goal.target_unit}`}
                    </p>
                    <p className="mt-1 text-sm text-muted">
                      {goal.time_horizon ? `Over ${goal.time_horizon} month(s) · ` : ""}
                      Tracking: {goal.primary_kpi}
                    </p>
                  </div>
                  <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
                    {goal.status}
                  </span>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
