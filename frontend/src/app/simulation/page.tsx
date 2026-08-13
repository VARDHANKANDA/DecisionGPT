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
      setError("Turn on at least one action to simulate.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const simulation = await api.simulate(business.id, actions, undefined, horizonDays);
      setResult(simulation);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not run this simulation right now.");
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
        title="Digital Twin"
        subtitle="Try a decision before you make it — simulated with your own registered forecasting model."
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
            <span className="text-sm font-medium text-foreground">Horizon</span>
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
            {loading ? "Simulating…" : "Run simulation"}
          </PrimaryButton>
        </div>
        {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
      </Card>

      {result ? <SimulationResults result={result} /> : null}
    </div>
  );
}

function SimulationResults({ result }: { result: SimulationResult }) {
  const { output } = result;
  const revenueGrowth =
    output.baseline_revenue > 0 ? ((output.expected_revenue - output.baseline_revenue) / output.baseline_revenue) * 100 : 0;

  return (
    <div className="mt-8 space-y-6">
      <Card>
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-foreground">Simulated outcome</h2>
          <RiskBadge level={output.risk_level} />
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MiniStat label="Baseline revenue" value={formatINR(output.baseline_revenue)} />
          <MiniStat
            label="Expected revenue"
            value={formatINR(output.expected_revenue)}
            hint={`${revenueGrowth >= 0 ? "+" : ""}${revenueGrowth.toFixed(1)}%`}
          />
          <MiniStat label="Baseline units sold" value={output.baseline_units_sold.toFixed(1)} />
          <MiniStat label="Expected units sold" value={output.expected_units_sold.toFixed(1)} />
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
          <MiniStat label="Revenue range" value={`${formatINR(output.revenue_lower_bound)} – ${formatINR(output.revenue_upper_bound)}`} />
          <MiniStat label="Risk score" value={output.risk_score.toFixed(2)} />
        </div>

        {output.inventory_constrained ? (
          <div className="mt-4 rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">
            Projected sales are capped by your available inventory.
          </div>
        ) : null}
      </Card>

      <Card>
        <h3 className="text-sm font-medium text-foreground">Assumptions</h3>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
          {output.assumptions.map((a, i) => (
            <li key={i}>{a}</li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-muted">Model: {output.model_name} v{output.model_version}</p>
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
