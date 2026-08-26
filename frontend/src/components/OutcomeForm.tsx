"use client";

import { useMemo, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { PrimaryButton } from "@/components/ui";

interface FieldSpec {
  key: string;
  label: string;
  kind: "number" | "text";
  required?: boolean;
  hint?: string;
}

/** Build the field list from what the original decision actually predicted,
 *  so we never ask the SME for a metric the decision can't be scored on. */
function fieldsForDecision(
  expected: Record<string, unknown> | undefined,
  goalObjective?: string,
): FieldSpec[] {
  const fields: FieldSpec[] = [
    { key: "revenue", label: "Actual revenue (₹)", kind: "number", required: true },
  ];
  if (expected && expected["expected_profit"] != null) {
    fields.push({ key: "profit", label: "Actual profit (₹)", kind: "number" });
  }
  if (expected && expected["expected_units_sold"] != null) {
    fields.push({ key: "orders", label: "Actual units / orders sold", kind: "number" });
  }
  fields.push({ key: "marketing_spend", label: "Actual marketing spend (₹)", kind: "number" });
  if (goalObjective === "reduce_churn") {
    fields.push({ key: "churn", label: "Actual churn rate (0–1)", kind: "number" });
  }
  fields.push({ key: "notes", label: "Notes (optional)", kind: "text" });
  return fields;
}

export function OutcomeForm({
  businessId,
  decisionId,
  expectedOutcome,
  goalObjective,
  onRecorded,
  compact = false,
}: {
  businessId: string;
  decisionId: string;
  expectedOutcome?: Record<string, unknown>;
  goalObjective?: string;
  onRecorded?: (result: { score: number | null; achieved: boolean | null }) => void;
  compact?: boolean;
}) {
  const fields = useMemo(
    () => fieldsForDecision(expectedOutcome, goalObjective),
    [expectedOutcome, goalObjective],
  );
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ score: number | null; achieved: boolean | null } | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const payload: Record<string, number | string> = {};
    for (const f of fields) {
      const raw = values[f.key]?.trim();
      if (!raw) continue;
      payload[f.key] = f.kind === "number" ? Number(raw) : raw;
    }
    if (payload.revenue === undefined || Number.isNaN(payload.revenue as number)) {
      setError("Actual revenue is required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const outcome = await api.recordOutcome(businessId, decisionId, payload);
      const result = { score: outcome.goal_achievement_score, achieved: outcome.goal_achieved };
      setDone(result);
      onRecorded?.(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record that outcome.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <p className="text-sm text-muted">
        Outcome recorded.{" "}
        {done.score !== null
          ? `Achieved ${(done.score * 100).toFixed(0)}% of the predicted revenue change.`
          : "Saved to your business history."}
      </p>
    );
  }

  return (
    <form onSubmit={submit} className={compact ? "space-y-3" : "mt-3 space-y-3"}>
      <p className="text-sm text-foreground">What happened after implementing this strategy?</p>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {fields.map((f) => (
          <label key={f.key} className="flex flex-col gap-1 text-xs text-muted">
            {f.label}
            {f.kind === "number" ? (
              <input
                type="number"
                step="any"
                required={f.required}
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                className="input"
              />
            ) : (
              <input
                type="text"
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
                className="input"
              />
            )}
          </label>
        ))}
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <PrimaryButton type="submit" disabled={submitting}>
        {submitting ? "Saving…" : "Save outcome"}
      </PrimaryButton>
    </form>
  );
}
