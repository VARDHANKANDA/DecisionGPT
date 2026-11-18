"use client";

import { useState } from "react";
import { api, type ActionType, type SimulationAction, type SimulationResult } from "@/lib/api";
import { Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { Panel } from "@/components/agent-ui";
import { ActionError, Badge, BulletList, DataTable, Workspace, inputCls, useAction } from "@/components/platform-ui";
import { formatKpi } from "@/lib/platform-api";

const LABEL: Record<ActionType, string> = { price_change: "Price change (%)", marketing_change: "Marketing spend change (%)", inventory_change: "Stock change (%)" };
const BOUNDS: Record<ActionType, [number, number]> = { price_change: [-50, 100], marketing_change: [-100, 500], inventory_change: [-100, 500] };

interface Draft {
  name: string;
  values: Record<ActionType, string>;
}
const blank = (name: string, values?: Partial<Record<ActionType, string>>): Draft => ({ name, values: { price_change: "", marketing_change: "", inventory_change: "", ...values } });

const inr = (n: number | null) => formatKpi(n, "inr");

export default function ComparePage() {
  const [drafts, setDrafts] = useState<Draft[]>([blank("Option A", { price_change: "5" }), blank("Option B", { marketing_change: "10" })]);
  const [results, setResults] = useState<{ name: string; actions: SimulationAction[]; sim: SimulationResult }[] | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  return (
    <Workspace
      title="Strategy Comparison"
      subtitle="Which of these available business strategies is more suitable? Compare candidate strategic options side by side to evaluate projected revenue lift, margin impact, and downside risks."
    >
      {(id) => <Body id={id} drafts={drafts} setDrafts={setDrafts} results={results} setResults={setResults} formError={formError} setFormError={setFormError} />}
    </Workspace>
  );
}

function Body({
  id,
  drafts,
  setDrafts,
  results,
  setResults,
  formError,
  setFormError,
}: {
  id: string;
  drafts: Draft[];
  setDrafts: (d: Draft[]) => void;
  results: { name: string; actions: SimulationAction[]; sim: SimulationResult }[] | null;
  setResults: (r: { name: string; actions: SimulationAction[]; sim: SimulationResult }[] | null) => void;
  formError: string | null;
  setFormError: (e: string | null) => void;
}) {
  const run = useAction(async () => {
    const plans: { name: string; actions: SimulationAction[] }[] = [];
    for (const d of drafts) {
      const actions: SimulationAction[] = [];
      for (const t of Object.keys(LABEL) as ActionType[]) {
        const raw = d.values[t].trim();
        if (!raw) continue;
        const n = Number(raw);
        const [lo, hi] = BOUNDS[t];
        if (!Number.isFinite(n) || n < lo || n > hi) {
          setFormError(`${d.name}: ${LABEL[t]} must be a number from ${lo} to ${hi}.`);
          return undefined;
        }
        actions.push({ type: t, value: n });
      }
      if (actions.length === 0) {
        setFormError(`${d.name}: enter at least one change.`);
        return undefined;
      }
      plans.push({ name: d.name, actions });
    }
    setFormError(null);
    const sims = await Promise.all(plans.map((p) => api.simulate(id, p.actions, undefined, 14)));
    const out = plans.map((p, i) => ({ ...p, sim: sims[i] }));
    setResults(out);
    return out;
  });
  // Options whose price effect is withheld have no expected sales and are never ranked.
  const rankable = results ? results.filter((r) => r.sim.output.expected_revenue !== null) : [];
  const best = rankable.length > 0 ? [...rankable].sort((a, b) => (b.sim.output.expected_revenue ?? 0) - (a.sim.output.expected_revenue ?? 0))[0] : null;
  const WITHHELD = "Withheld: price effect not identified";
  return (
    <div className="space-y-6">
      <Panel title="Describe the options" note="Leave a change blank to leave it unchanged. Each option is run through the same what-if model over 14 days.">
        <div className="grid gap-4 md:grid-cols-3">
          {drafts.map((d, i) => (
            <fieldset key={i} className="min-w-0 rounded-xl border border-border p-4">
              <legend className="px-1 text-sm font-semibold text-foreground">{d.name}</legend>
              {(Object.keys(LABEL) as ActionType[]).map((t) => (
                <label key={t} className="mt-2 block text-sm font-medium text-foreground">
                  {LABEL[t]}
                  <input
                    value={d.values[t]}
                    inputMode="decimal"
                    onChange={(e) => setDrafts(drafts.map((x, j) => (j === i ? { ...x, values: { ...x.values, [t]: e.target.value } } : x)))}
                    className={inputCls}
                  />
                </label>
              ))}
              {drafts.length > 2 ? (
                <button type="button" className={`${btnSecondary} mt-3`} onClick={() => setDrafts(drafts.filter((_, j) => j !== i))}>
                  Remove
                </button>
              ) : null}
            </fieldset>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-3">
          {drafts.length < 3 ? (
            <button className={btnSecondary} onClick={() => setDrafts([...drafts, blank(`Option ${String.fromCharCode(65 + drafts.length)}`)])}>
              Add a third option
            </button>
          ) : null}
          <button className={btnPrimary} disabled={run.busy} onClick={() => run.run()}>
            {run.busy ? "Comparing…" : "Compare"}
          </button>
        </div>
        {formError ? <p className="mt-2 text-base text-danger">{formError}</p> : null}
        <ActionError error={run.error} />
      </Panel>

      {results ? (
        <>
          <Panel title="Side by side">
            <DataTable
              caption="Strategy comparison"
              columns={["", ...results.map((r) => r.name)]}
              rows={[
                ["Changes", ...results.map((r) => r.actions.map((a) => `${LABEL[a.type].replace(" (%)", "")} ${a.value > 0 ? "+" : ""}${a.value}%`).join(", "))],
                ["Expected sales", ...results.map((r) => (r.sim.output.expected_revenue === null ? WITHHELD : inr(r.sim.output.expected_revenue)))],
                ["Compared with no change", ...results.map((r) => {
                  const e = r.sim.output.expected_revenue;
                  if (e === null) return WITHHELD;
                  const d = e - r.sim.output.baseline_revenue;
                  return `${d >= 0 ? "+" : ""}${inr(d)}`;
                })],
                ["Likely range", ...results.map((r) => (r.sim.output.revenue_lower_bound === null || r.sim.output.revenue_upper_bound === null ? "Unavailable" : `${inr(r.sim.output.revenue_lower_bound)} to ${inr(r.sim.output.revenue_upper_bound)}`))],
                ["Expected profit", ...results.map((r) => (r.sim.output.expected_profit === null ? "Not available" : inr(r.sim.output.expected_profit)))],
                ["Risk", ...results.map((r) => r.sim.output.risk_level.toLowerCase())],
              ]}
            />
            {best ? (
              <p className="mt-3 text-base text-foreground">
                Highest projected sales among the options that could be estimated: <strong>{best.name}</strong>. <Badge>Projection</Badge> That is not the same as the best choice — look at the range and the risk, and at the assumptions below.
              </p>
            ) : (
              <p className="mt-3 text-base text-foreground">
                None of these options can be ranked: each changes price, and your sales history does not contain enough price variation to estimate a price response.
              </p>
            )}
            {results.some((r) => r.sim.output.price_response?.withheld) ? (
              <p className="mt-2 text-sm text-muted">
                Needed to evaluate price changes: {(results.find((r) => r.sim.output.price_response?.withheld)?.sim.output.price_response?.needed ?? []).slice(0, 3).join("; ")}.
              </p>
            ) : null}
          </Panel>
          {results.some((r) => r.sim.output.expected_profit === null) ? <Notice tone="info">Profit is shown only when product costs are recorded.</Notice> : null}
          <Panel title="Assumptions behind each projection">
            {new Set(results.map((r) => r.sim.output.assumptions.join("|"))).size === 1 ? (
              <>
                <p className="text-xs text-muted">
                  The same for every option · {results[0].sim.output.model_name} {results[0].sim.output.model_version}
                </p>
                <BulletList items={results[0].sim.output.assumptions} />
              </>
            ) : (
              <div className="grid gap-4 md:grid-cols-3">
                {results.map((r) => (
                  <div key={r.name} className="min-w-0">
                    <p className="text-base font-semibold text-foreground">{r.name}</p>
                    <p className="text-xs text-muted">
                      {r.sim.output.model_name} {r.sim.output.model_version}
                    </p>
                    <BulletList items={r.sim.output.assumptions} />
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </>
      ) : null}
    </div>
  );
}
