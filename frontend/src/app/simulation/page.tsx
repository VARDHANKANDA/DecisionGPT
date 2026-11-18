"use client";

import { useState } from "react";
import {
  api,
  ApiError,
  type ActionType,
  type SimulationAction,
  type SimulationResult,
} from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, PageHeader, PrimaryButton, RiskBadge, SecondaryLink, formatINR } from "@/components/ui";

const ACTION_BOUNDS: Record<ActionType, [number, number]> = {
  price_change: [-50, 100],
  marketing_change: [-100, 500],
  inventory_change: [-100, 500],
};

const ACTION_LABELS: Record<ActionType, string> = {
  price_change: "Price change",
  marketing_change: "Marketing spend change",
  inventory_change: "Inventory change",
};

export default function SimulationPage() {
  const { business, loading: businessLoading } = useBusiness();

  const [enabled, setEnabled] = useState<Record<ActionType, boolean>>({
    price_change: false,
    marketing_change: true,
    inventory_change: false,
  });
  const [values, setValues] = useState<Record<ActionType, number>>({
    price_change: 0,
    marketing_change: 10,
    inventory_change: 0,
  });
  const [horizonDays, setHorizonDays] = useState(14);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runSimulation() {
    if (!business) return;
    const actions: SimulationAction[] = (Object.keys(enabled) as ActionType[])
      .filter((type) => enabled[type])
      .map((type) => ({ type, value: values[type] }));

    if (actions.length === 0) {
      setError("Tick at least one change to test.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const simulation = await api.simulate(business.id, actions, undefined, horizonDays);
      setResult(simulation);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "We couldn't test that right now. Please try again.");
    } finally {
      setLoading(false);
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
    <div className="mx-auto max-w-4xl px-6 py-12">
      <PageHeader
        title="Scenario Analysis"
        subtitle="What could happen if I change this business variable or assumption? Simulate price adjustments, marketing spend reallocation, and inventory shifts over verified historical data."
      />

      <Card>
        <div className="space-y-5">
          {(Object.keys(ACTION_BOUNDS) as ActionType[]).map((type) => {
            const [min, max] = ACTION_BOUNDS[type];
            return (
              <div key={type} className="flex items-center gap-4">
                <label className="flex w-56 items-center gap-2">
                  <input
                    type="checkbox"
                    checked={enabled[type]}
                    onChange={(e) => setEnabled((prev) => ({ ...prev, [type]: e.target.checked }))}
                  />
                  <span className="text-sm font-medium text-foreground">{ACTION_LABELS[type]}</span>
                </label>
                <input
                  type="range"
                  min={min}
                  max={max}
                  value={values[type]}
                  disabled={!enabled[type]}
                  onChange={(e) => setValues((prev) => ({ ...prev, [type]: Number(e.target.value) }))}
                  className="flex-1 accent-[var(--accent)] disabled:opacity-40"
                />
                <span className="w-16 text-right text-sm font-medium text-foreground">
                  {values[type] > 0 ? "+" : ""}
                  {values[type]}%
                </span>
              </div>
            );
          })}

          <label className="flex items-center gap-3">
            <span className="text-sm font-medium text-foreground">Look ahead</span>
            <select
              value={horizonDays}
              onChange={(e) => setHorizonDays(Number(e.target.value))}
              className="input w-40"
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
            </select>
          </label>
        </div>

        <div className="mt-6">
          <PrimaryButton onClick={runSimulation} disabled={loading}>
            {loading ? "Working it out…" : "See what may happen"}
          </PrimaryButton>
        </div>
        {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
      </Card>

      {result ? <SimulationResults result={result} days={horizonDays} /> : null}
    </div>
  );
}

function SimulationResults({ result, days }: { result: SimulationResult; days: number }) {
  const { output } = result;
  const pr = output.price_response;
  if (pr?.withheld || output.expected_revenue === null || output.expected_units_sold === null) {
    return (
      <div className="mt-8 space-y-6">
        <Card>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">Price effect unavailable</h2>
            <RiskBadge level={output.risk_level} />
          </div>
          <p className="mt-3 text-lg text-foreground">
            {pr?.reason === "model"
              ? "DecisionGPT cannot tell you what this price change would do to your sales. Your history shows some price variation, but there is no forecasting model that has been checked against your own price changes, so any figure would not be about your customers."
              : "DecisionGPT cannot tell you what this price change would do to your sales, because your own sales history does not contain enough price variation to measure how your customers respond to price."}
          </p>
          {pr ? (
            <div className="mt-4 rounded-xl bg-warning-soft px-4 py-3 text-base text-foreground">
              <p className="font-medium">What would be needed:</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {pr.needed.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <MiniStat label="Sales if nothing changes" value={formatINR(output.baseline_revenue)} />
            <MiniStat label="Units if nothing changes" value={output.baseline_units_sold.toFixed(1)} />
            <MiniStat label="Risk" value={output.risk_level.charAt(0) + output.risk_level.slice(1).toLowerCase()} />
          </div>
          <p className="mt-3 text-xs text-muted">No effect is shown rather than a number that could be mistaken for a measured price response.</p>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-foreground">Assumptions</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted [overflow-wrap:anywhere]">
            {output.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </Card>
      </div>
    );
  }
  const revenueGrowth =
    output.baseline_revenue > 0 ? ((output.expected_revenue - output.baseline_revenue) / output.baseline_revenue) * 100 : 0;

  return (
    <div className="mt-8 space-y-6">
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-foreground">What may happen</h2>
          <RiskBadge level={output.risk_level} />
        </div>

        <p className="mt-3 text-lg text-foreground">{summaryLine(result, days)}</p>
        {Math.abs(output.expected_units_sold - output.baseline_units_sold) < 0.05 &&
        Math.abs(output.expected_revenue - output.baseline_revenue) > 0.01 * Math.max(output.baseline_revenue, 1) ? (
          <p className="mt-3 rounded-xl bg-warning-soft px-4 py-3 text-base text-foreground">
            ⚠ The prediction found <strong>no change in the units you would sell</strong>, so the difference in sales comes only from the
            price. Real customers often buy less when prices rise — treat this as something to test carefully, not a promise.
          </p>
        ) : null}
        {Math.abs(output.expected_units_sold - output.baseline_units_sold) < 0.05 &&
        Math.abs(output.expected_revenue - output.baseline_revenue) <= 0.01 * Math.max(output.baseline_revenue, 1) ? (
          <p className="mt-3 rounded-xl bg-muted-surface px-4 py-3 text-base text-foreground">
            The prediction found <strong>no effect on your sales</strong> from this change. That may be true — or your sales history
            may not contain enough variation in it for DecisionGPT to measure an effect. Try a different change or a larger one.
          </p>
        ) : null}

        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MiniStat label="Sales if nothing changes" value={formatINR(output.baseline_revenue)} />
          <MiniStat
            label="Sales with your change"
            value={formatINR(output.expected_revenue)}
            hint={`${revenueGrowth >= 0 ? "+" : ""}${revenueGrowth.toFixed(1)}%`}
          />
          <MiniStat label="Units if nothing changes" value={output.baseline_units_sold.toFixed(1)} />
          <MiniStat label="Units with your change" value={output.expected_units_sold.toFixed(1)} />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MiniStat
            label="Profit"
            value={output.expected_profit !== null ? formatINR(output.expected_profit) : "Unavailable"}
            hint={output.profit_note ?? undefined}
          />
          <MiniStat
            label="Customer impact"
            value={output.customer_impact !== null ? `${output.customer_impact >= 0 ? "+" : ""}${output.customer_impact}` : "Unavailable"}
          />
          <MiniStat
            label="Expected range for sales"
            value={output.revenue_lower_bound !== null && output.revenue_upper_bound !== null ? `${formatINR(output.revenue_lower_bound)} – ${formatINR(output.revenue_upper_bound)}` : "Unavailable"}
          />
          <MiniStat label="Risk" value={output.risk_level.charAt(0) + output.risk_level.slice(1).toLowerCase()} />
        </div>

        {output.inventory_constrained ? (
          <div className="mt-4 rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">
            Your stock limits how much you can sell, so the sales above are capped by what you have.
          </div>
        ) : null}
      </Card>

      <Card>
        <h3 className="text-sm font-medium text-foreground">Assumptions</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted [overflow-wrap:anywhere]">
          {output.assumptions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">
          Technical: estimated with {output.model_name} (version {output.model_version}). This is an estimate, not a promise.
          {pr && !pr.withheld ? ` ${pr.message}` : ""}
        </p>
      </Card>
    </div>
  );
}

function MiniStat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
      {hint ? <p className="text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

const ACTION_PHRASE: Record<string, string> = {
  price_change: "change your price",
  marketing_change: "change your marketing spend",
  inventory_change: "change your stock",
};

/** One plain sentence built only from the simulation's own numbers. */
function summaryLine(result: SimulationResult, days: number): string {
  const { output, actions } = result;
  const what = actions
    .map((a) => `${ACTION_PHRASE[a.type] ?? a.type} by ${a.value > 0 ? "+" : ""}${a.value}%`)
    .join(" and ");
  if (output.expected_revenue === null) return `If you ${what}, the effect cannot be estimated from your data.`;
  if (output.baseline_revenue <= 0) return `If you ${what}, sales over the next ${days} days are expected to be about ${formatINR(output.expected_revenue)}.`;
  const pct = ((output.expected_revenue - output.baseline_revenue) / output.baseline_revenue) * 100;
  const move = Math.abs(pct) < 0.5 ? "barely different from" : `${Math.abs(pct).toFixed(1)}% ${pct > 0 ? "higher than" : "lower than"}`;
  return `If you ${what}, sales over the next ${days} days are expected to be about ${formatINR(output.expected_revenue)} — ${move} ${formatINR(output.baseline_revenue)} if nothing changes.`;
}
