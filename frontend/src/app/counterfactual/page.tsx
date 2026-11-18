"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { platform, type Anchor, type CounterfactualResult } from "@/lib/platform-api";
import { Notice, btnPrimary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, Badge, BulletList, DataTable, PeriodPicker, Workspace, inputCls, useAction } from "@/components/platform-ui";
import { formatKpi } from "@/lib/platform-api";

type Mode = CounterfactualResult["mode"];

const MODES: { key: Mode; title: string; blurb: string; tone: "good" | "warn" | "neutral" }[] = [
  { key: "deterministic_scenario", title: "Scenario arithmetic", blurb: "“If price rose 10% and I lost 5% of units, what would sales be?” Pure arithmetic on your own recent numbers with assumptions you type. No model, no prediction.", tone: "neutral" },
  { key: "model_prediction", title: "Model prediction", blurb: "What the trained sales model projects. A statistical projection from past data — not a cause-and-effect result.", tone: "warn" },
  { key: "causal_counterfactual", title: "Causal counterfactual", blurb: "What a saved Causal AI estimate implies would have happened without your change. Only available after a valid causal estimate.", tone: "good" },
];

const inr = (n: number) => formatKpi(n, "inr");

function Result({ r }: { r: CounterfactualResult }) {
  const m = MODES.find((x) => x.key === r.mode);
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-border bg-surface p-5">
        <p className="mb-2">
          <Badge tone={m?.tone ?? "neutral"}>{r.label}</Badge>
        </p>
        <p className="text-lg font-medium text-foreground">{r.headline}</p>
        {r.reason ? <p className="mt-2 text-base text-foreground">{r.reason}</p> : null}
      </div>

      {r.baseline && r.scenario ? (
        <DataTable
          columns={["", "Sales", "Notes"]}
          rows={[
            [`Baseline (last ${r.baseline.period_days} days to ${r.baseline.end})`, inr(r.baseline.sales), `${r.baseline.orders} orders`],
            [`Scenario (${r.scenario.lever === "price_change_pct" ? "price" : "marketing"} ${r.scenario.change_pct >= 0 ? "+" : ""}${r.scenario.change_pct}%, units responding ${r.scenario.elasticity}× as much)`, inr(r.scenario.sales), `${r.scenario.difference >= 0 ? "+" : ""}${inr(r.scenario.difference)} difference`],
          ]}
          caption="Scenario result"
        />
      ) : null}

      {r.mode === "model_prediction" && r.expected_revenue !== undefined ? (
        <DataTable
          columns={["", "Sales"]}
          rows={[
            ["Without the change (model forecast for the next 14 days)", inr(r.baseline_revenue as number)],
            ["With the change (model projection, next 14 days)", inr(r.expected_revenue)],
            ["Model range", `${inr((r.interval as { lower: number } | undefined)?.lower ?? 0)} to ${inr((r.interval as { upper: number } | undefined)?.upper ?? 0)}`],
          ]}
          caption="Model projection"
        />
      ) : null}

      {r.mode === "causal_counterfactual" && r.counterfactual_after !== undefined ? (
        <DataTable
          columns={["", `Value (${r.unit})`]}
          rows={[
            ["Observed after the change", r.observed_after ?? null],
            ["Counterfactual: without the change", r.counterfactual_after],
            ["Difference", r.difference ?? null],
            ["95% interval of the difference", r.ci95 ? `${r.ci95[0].toFixed(2)} to ${r.ci95[1].toFixed(2)}` : null],
          ]}
          caption="Causal counterfactual"
        />
      ) : null}

      {r.what_it_does_not_establish ? <Notice tone="warning" title="What this does not establish">{r.what_it_does_not_establish}</Notice> : null}
      {r.uncertainty ? <p className="text-base text-foreground">Uncertainty: {r.uncertainty}</p> : null}
      {r.assumptions && r.assumptions.length > 0 ? (
        <BulletList title="Assumptions" items={r.assumptions.map((a) => (typeof a === "string" ? a : `${a.assumption} — ${a.status}`))} />
      ) : null}
    </div>
  );
}

function Form({ id, initialAnalysis }: { id: string; initialAnalysis: string | null }) {
  const [mode, setMode] = useState<Mode>(initialAnalysis ? "causal_counterfactual" : "deterministic_scenario");
  const [lever, setLever] = useState("price_change_pct");
  const [change, setChange] = useState("10");
  const [elasticity, setElasticity] = useState("0");
  const [days, setDays] = useState(30);
  const [anchor, setAnchor] = useState<Anchor>("today");
  const [analysis, setAnalysis] = useState(initialAnalysis ?? "");
  const [result, setResult] = useState<CounterfactualResult | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const causal = useLoad(async (b) => (await platform.causalRuns(b)).runs.filter((r) => r.classification === "causal_estimate"));
  const run = useAction(async () => {
    setFormError(null);
    const pct = Number(change);
    const el = Number(elasticity);
    if (mode !== "causal_counterfactual" && (!change.trim() || !Number.isFinite(pct))) {
      setFormError("Enter the size of the change as a number.");
      return undefined;
    }
    if (mode === "deterministic_scenario" && (!Number.isFinite(el) || el < -5 || el > 5)) {
      setFormError("The unit response must be a number between -5 and 5.");
      return undefined;
    }
    if (mode === "causal_counterfactual" && !analysis) {
      setFormError("Choose a saved causal analysis.");
      return undefined;
    }
    const body =
      mode === "deterministic_scenario"
        ? { mode, lever, change_pct: pct, elasticity: el, baseline_days: days, anchor }
        : mode === "model_prediction"
          ? { mode, lever, change_pct: pct }
          : { mode, analysis_id: analysis };
    const r = await platform.runCounterfactual(id, body);
    setResult(r);
    return r;
  });
  return (
    <div className="space-y-6">
      <Panel title="Choose the kind of “what if”">
        <fieldset className="space-y-3">
          <legend className="sr-only">Kind of counterfactual</legend>
          {MODES.map((m) => (
            <label key={m.key} className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 ${mode === m.key ? "border-accent bg-accent-soft/40" : "border-border"}`}>
              <input type="radio" name="mode" checked={mode === m.key} onChange={() => { setMode(m.key); setResult(null); }} className="mt-1 h-5 w-5" />
              <span>
                <span className="block text-base font-semibold text-foreground">{m.title}</span>
                <span className="block text-base text-muted">{m.blurb}</span>
              </span>
            </label>
          ))}
        </fieldset>
        <form
          className="mt-5 space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            run.run();
          }}
        >
          {mode !== "causal_counterfactual" ? (
            <div className="flex flex-wrap gap-4">
              <label className="block text-sm font-medium text-foreground">
                What changes
                <select value={lever} onChange={(e) => setLever(e.target.value)} className={inputCls}>
                  <option value="price_change_pct">Selling price</option>
                  <option value="marketing_change_pct">Marketing spend</option>
                </select>
              </label>
              <label className="block text-sm font-medium text-foreground">
                By how many percent (use a minus for a cut)
                <input value={change} onChange={(e) => setChange(e.target.value)} inputMode="decimal" className={`${inputCls} w-32`} />
              </label>
              {mode === "deterministic_scenario" ? (
                <label className="block text-sm font-medium text-foreground">
                  Units respond (−1 = 10% price rise loses 10% of units)
                  <input value={elasticity} onChange={(e) => setElasticity(e.target.value)} inputMode="decimal" className={`${inputCls} w-32`} />
                </label>
              ) : null}
            </div>
          ) : (
            <LoadView load={causal} label="Looking for your saved causal analyses…">
              {(runs) =>
                runs.length === 0 ? (
                  <Notice tone="warning" title="No causal estimate yet">
                    A causal counterfactual needs a saved Causal AI analysis that produced a causal estimate. Run one in the Causal AI Engine first.
                  </Notice>
                ) : (
                  <label className="block text-sm font-medium text-foreground">
                    Saved causal analysis
                    <select value={analysis} onChange={(e) => setAnalysis(e.target.value)} className={`${inputCls} max-w-xl`}>
                      <option value="">Choose…</option>
                      {runs.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.question}
                        </option>
                      ))}
                    </select>
                  </label>
                )
              }
            </LoadView>
          )}
          {mode === "deterministic_scenario" ? <PeriodPicker days={days} anchor={anchor} onChange={(d, a) => { setDays(d); setAnchor(a); }} /> : null}
          {formError ? <p className="text-base text-danger">{formError}</p> : null}
          <button className={btnPrimary} type="submit" disabled={run.busy}>
            {run.busy ? "Working it out…" : "Work it out"}
          </button>
          <ActionError error={run.error} />
        </form>
      </Panel>
      {result ? <Result r={result} /> : null}
    </div>
  );
}

function Body({ id }: { id: string }) {
  const analysis = useSearchParams().get("analysis");
  return <Form id={id} initialAnalysis={analysis} />;
}

export default function CounterfactualPage() {
  return (
    <Workspace title="Counterfactual Analysis" subtitle="“What if” in three clearly separated kinds. Each result carries its kind, so arithmetic is never mistaken for prediction and prediction is never mistaken for cause.">
      {(id) => (
        <Suspense fallback={null}>
          <Body id={id} />
        </Suspense>
      )}
    </Workspace>
  );
}
