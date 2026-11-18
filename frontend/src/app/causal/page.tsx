"use client";

import Link from "next/link";
import { useState } from "react";
import { platform, type CausalResult } from "@/lib/platform-api";
import { Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, Workspace, inputCls, useAction } from "@/components/platform-ui";
import { CLASS_LABEL, CausalResultView } from "@/components/causal-view";
import { timeAgo } from "@/lib/friendly";

function ProductPicker({ label, options, value, onChange }: { label: string; options: string[]; value: string[]; onChange: (v: string[]) => void }) {
  return (
    <fieldset className="min-w-0">
      <legend className="text-sm font-medium text-foreground">{label}</legend>
      <div className="mt-1 flex flex-wrap gap-2">
        {options.length === 0 ? <span className="text-base text-muted">No products recorded.</span> : null}
        {options.map((p) => {
          const on = value.includes(p);
          return (
            <label key={p} className={`flex min-h-[44px] cursor-pointer items-center gap-2 rounded-full border px-3 text-base ${on ? "border-accent bg-accent-soft" : "border-border bg-surface"}`}>
              <input type="checkbox" checked={on} onChange={() => onChange(on ? value.filter((x) => x !== p) : [...value, p])} className="h-4 w-4" />
              {p}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

function Form({ id, onResult }: { id: string; onResult: (r: CausalResult) => void }) {
  const products = useLoad(async (b) => (await platform.preview(b, "products", 0, 200)).rows.map((r) => String(r.values.name ?? "")).filter(Boolean));
  const [method, setMethod] = useState<"association" | "did">("association");
  const [outcome, setOutcome] = useState("revenue");
  const [treatment, setTreatment] = useState("marketing_spend");
  const [treated, setTreated] = useState<string[]>([]);
  const [control, setControl] = useState<string[]>([]);
  const [date, setDate] = useState("");
  const [window, setWindow] = useState(28);
  const run = useAction(() =>
    platform.analyzeCausal(
      id,
      method === "association" ? { method, outcome, treatment } : { method, outcome, treated, control, intervention_date: date || undefined, window_days: window },
    ),
  );
  return (
    <Panel title="Choose the question">
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const r = await run.run();
          if (r) onResult(r);
        }}
      >
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-foreground">What do you want to look at?</legend>
          <label className="flex items-start gap-2 text-base text-foreground">
            <input type="radio" name="m" checked={method === "association"} onChange={() => setMethod("association")} className="mt-1 h-5 w-5" />
            <span>
              Do two things move together? <span className="text-muted">(exploratory association — never reported as cause and effect)</span>
            </span>
          </label>
          <label className="flex items-start gap-2 text-base text-foreground">
            <input type="radio" name="m" checked={method === "did"} onChange={() => setMethod("did")} className="mt-1 h-5 w-5" />
            <span>
              What did a change I made actually do? <span className="text-muted">(compares products you changed with ones you did not, before and after a date)</span>
            </span>
          </label>
        </fieldset>
        <label className="block text-sm font-medium text-foreground">
          Outcome to look at
          <select value={outcome} onChange={(e) => setOutcome(e.target.value)} className={`${inputCls} max-w-xs`}>
            <option value="revenue">Sales (₹ per day)</option>
            <option value="units">Units sold per day</option>
          </select>
        </label>
        {method === "association" ? (
          <label className="block text-sm font-medium text-foreground">
            Compared with
            <select value={treatment} onChange={(e) => setTreatment(e.target.value)} className={`${inputCls} max-w-xs`}>
              <option value="marketing_spend">Marketing spend</option>
              <option value="avg_price">Average selling price</option>
            </select>
          </label>
        ) : (
          <>
            <LoadView load={products} label="Loading your products…">
              {(names) => (
                <div className="space-y-4">
                  <ProductPicker label="Products you changed" options={names} value={treated} onChange={setTreated} />
                  <ProductPicker label="Products you did not change (the comparison)" options={names.filter((n) => !treated.includes(n))} value={control} onChange={setControl} />
                </div>
              )}
            </LoadView>
            <div className="flex flex-wrap gap-4">
              <label className="block text-sm font-medium text-foreground">
                Date the change took effect
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputCls} />
              </label>
              <label className="block text-sm font-medium text-foreground">
                Days to compare on each side
                <input type="number" min={7} max={120} value={window} onChange={(e) => setWindow(Number(e.target.value))} className={`${inputCls} w-32`} />
              </label>
            </div>
          </>
        )}
        <button className={btnPrimary} type="submit" disabled={run.busy}>
          {run.busy ? "Analysing…" : "Run the analysis"}
        </button>
        <ActionError error={run.error} />
      </form>
    </Panel>
  );
}

function Past({ id, onOpen }: { id: string; onOpen: (r: CausalResult) => void }) {
  const load = useLoad(() => platform.causalRuns(id));
  const open = useAction(async (rid: string) => {
    const r = await platform.causalRun(id, rid);
    onOpen({ ...r.result, id: r.id });
  });
  return (
    <Panel title="Earlier analyses">
      <LoadView load={load} label="Loading…">
        {({ runs }) =>
          runs.length === 0 ? (
            <p className="text-base text-muted">None yet.</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {runs.slice(0, 15).map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-base font-medium text-foreground">{r.question}</p>
                    <p className="text-sm text-muted">
                      {timeAgo(r.created_at)} · {r.classification ? CLASS_LABEL[r.classification as keyof typeof CLASS_LABEL]?.label ?? r.classification : r.status}
                    </p>
                  </div>
                  <button className={btnSecondary} disabled={open.busy} onClick={() => open.run(r.id)}>
                    Open
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </LoadView>
      <ActionError error={open.error} />
    </Panel>
  );
}

export default function CausalPage() {
  const [result, setResult] = useState<CausalResult | null>(null);
  const [version, setVersion] = useState(0);
  return (
    <Workspace title="Causal AI Engine" subtitle="Separates “these move together” from “this change caused that”, and says plainly when your data cannot tell.">
      {(id) => (
        <div className="space-y-6">
          <Notice tone="info" title="How to read the labels">
            Only a before/after comparison with a comparison group can be labelled a causal estimate — and only under assumptions that are listed for you to judge. Anything weaker is called an exploratory association, and thin data gets “not enough data”, never a guess.
          </Notice>
          <Form id={id} onResult={(r) => { setResult(r); setVersion((n) => n + 1); }} />
          {result ? (
            <>
              <CausalResultView r={result} />
              {result.classification === "causal_estimate" ? (
                <Link href={`/counterfactual?analysis=${result.id}`} className={btnSecondary}>
                  See the counterfactual this implies
                </Link>
              ) : null}
            </>
          ) : null}
          <Past key={version} id={id} onOpen={setResult} />
        </div>
      )}
    </Workspace>
  );
}

