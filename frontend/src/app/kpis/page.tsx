"use client";

import Link from "next/link";
import { useState } from "react";
import { platform, formatKpi, type Anchor, type Kpi } from "@/lib/platform-api";
import { Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, Badge, LineChart, PeriodPicker, Workspace, inputCls, useAction } from "@/components/platform-ui";

const STATUS = {
  met: { tone: "good", label: "Target met" },
  not_met: { tone: "bad", label: "Target not met" },
  no_target: { tone: "neutral", label: "No target set" },
  no_data: { tone: "neutral", label: "No data to compare" },
} as const;

const change = (c: number | null) => (c === null ? "No earlier period to compare" : `${c >= 0 ? "+" : ""}${(c * 100).toFixed(1)}% vs the previous period`);

function TargetForm({ businessId, k, days, onSaved }: { businessId: string; k: Kpi; days: number; onSaved: () => void }) {
  const [value, setValue] = useState(k.target ? String(k.target.value) : "");
  const [direction, setDirection] = useState<"higher" | "lower">(k.target?.direction ?? (k.key === "marketing_spend" ? "lower" : "higher"));
  const [err, setErr] = useState<string | null>(null);
  const save = useAction(async () => {
    const n = Number(value);
    if (!value.trim() || !Number.isFinite(n) || n < 0) {
      setErr("Enter a number that is zero or more.");
      return;
    }
    setErr(null);
    await platform.setTarget(businessId, k.key, n, direction, days);
    onSaved();
  });
  const clear = useAction(async () => {
    await platform.clearTarget(businessId, k.key);
    setValue("");
    onSaved();
  });
  return (
    <form
      className="mt-3 flex flex-wrap items-end gap-3"
      onSubmit={(e) => {
        e.preventDefault();
        save.run();
      }}
    >
      <label className="block text-sm font-medium text-foreground">
        Target for the last {days} days {k.unit === "inr" ? "(₹)" : k.unit === "percent" ? "(in percent, 20 = 20%)" : ""}
        <input value={value} onChange={(e) => setValue(e.target.value)} inputMode="decimal" className={`${inputCls} w-40`} />
      </label>
      <label className="block text-sm font-medium text-foreground">
        Goal
        <select value={direction} onChange={(e) => setDirection(e.target.value as "higher" | "lower")} className={inputCls}>
          <option value="higher">At least this much</option>
          <option value="lower">At most this much</option>
        </select>
      </label>
      <button className={btnPrimary} type="submit" disabled={save.busy}>
        Save target
      </button>
      {k.target ? (
        <button className={btnSecondary} type="button" disabled={clear.busy} onClick={() => clear.run()}>
          Remove target
        </button>
      ) : null}
      {err ? <p className="w-full text-base text-danger">{err}</p> : null}
      <div className="w-full">
        <ActionError error={save.error ?? clear.error} />
      </div>
    </form>
  );
}

function Trend({ businessId, k, anchor }: { businessId: string; k: Kpi; anchor: Anchor }) {
  const load = useLoad(() => platform.kpiTrend(businessId, k.key, 90, anchor));
  return (
    <LoadView load={load} label="Loading the trend…">
      {(t) =>
        t.points.length === 0 ? (
          <p className="text-base text-muted">No recorded days in the last 90 days.</p>
        ) : (
          <div>
            <LineChart points={t.points} label={`${t.name}, daily`} />
            <p className="mt-1 text-sm text-muted">{t.note}</p>
          </div>
        )
      }
    </LoadView>
  );
}

function Card({ businessId, k, days, anchor, onChanged }: { businessId: string; k: Kpi; days: number; anchor: Anchor; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const st = STATUS[k.status];
  return (
    <li className="min-w-0 rounded-2xl border border-border bg-surface p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-lg font-semibold text-foreground">{k.name}</h3>
        <Badge tone={st.tone}>{st.label}</Badge>
      </div>
      <p className="mt-2 break-words text-3xl font-semibold text-foreground">{formatKpi(k.value, k.unit)}</p>
      <p className="mt-1 text-sm text-muted">{change(k.change_pct)}</p>
      {k.target ? (
        <p className="mt-1 text-sm text-foreground">
          Target: {k.target.direction === "higher" ? "at least" : "at most"} {formatKpi(k.target.value, k.unit)} over {k.target.period_days} days
        </p>
      ) : null}
      {k.data_quality.status !== "ok" ? <p className="mt-2 text-sm text-warning">{k.data_quality.note}</p> : null}
      <p className="mt-2 text-xs text-muted">{k.status_rule}</p>
      <div className="mt-3 flex flex-wrap gap-3">
        <button className={btnSecondary} aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide trend and target" : "Trend and target"}
        </button>
        <Link href={`/explain?kpi=${k.key}&days=${days}&anchor=${anchor}`} className={btnSecondary}>
          How was this worked out?
        </Link>
      </div>
      {open ? (
        <div className="mt-4 space-y-4">
          <Trend businessId={businessId} k={k} anchor={anchor} />
          <TargetForm businessId={businessId} k={k} days={days} onSaved={onChanged} />
        </div>
      ) : null}
    </li>
  );
}

function Body({ id, days, anchor }: { id: string; days: number; anchor: Anchor }) {
  const load = useLoad(() => platform.kpis(id, days, anchor));
  return (
    <LoadView load={load} label="Calculating your KPIs…">
      {(d) => (
        <div className="space-y-5">
          {d.stale_days !== null && d.stale_days > 14 && anchor === "today" ? (
            <Notice tone="warning" title="Your newest sale is old">
              {d.stale_rule} Your newest sale is {d.stale_days} days old, so the last {days} days from today may be empty. Choose “Your newest sale” to look at your latest recorded period.
            </Notice>
          ) : null}
          <p className="text-base text-muted">
            {d.period.start} to {d.period.end}, compared with {d.previous_period.start} to {d.previous_period.end}.
          </p>
          <ul className="grid gap-4 md:grid-cols-2">
            {d.kpis.map((k) => (
              <Card key={`${k.key}-${k.target?.value ?? "x"}`} businessId={id} k={k} days={days} anchor={anchor} onChanged={load.retry} />
            ))}
          </ul>
          <Panel title="How status works">
            <p className="text-base text-foreground">
              A KPI shows “Target met” or “Target not met” only when you set a target, by comparing the value over the target period with it. Without a target there is no status — DecisionGPT does not guess what a good number is for your business.
            </p>
          </Panel>
        </div>
      )}
    </LoadView>
  );
}

export default function KpiPage() {
  const [days, setDays] = useState(30);
  const [anchor, setAnchor] = useState<Anchor>("today");
  return (
    <Workspace title="KPI Monitoring" subtitle="The numbers that matter, over a period you choose, with targets you set yourself.">
      {(id) => (
        <div className="space-y-6">
          <PeriodPicker days={days} anchor={anchor} onChange={(d, a) => { setDays(d); setAnchor(a); }} />
          <Body key={`${id}-${days}-${anchor}`} id={id} days={days} anchor={anchor} />
        </div>
      )}
    </Workspace>
  );
}
