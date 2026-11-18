"use client";

import { useEffect, useState } from "react";
import { platform, type AlertRow, type AlertRule, type Anchor } from "@/lib/platform-api";
import { Notice, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { Panel } from "@/components/agent-ui";
import { ActionError, Badge, PeriodPicker, Workspace, inputCls, useAction } from "@/components/platform-ui";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import { ErrorBox } from "@/components/simple";

const SEV = { high: { tone: "bad", label: "High" }, medium: { tone: "warn", label: "Medium" }, low: { tone: "neutral", label: "Low" } } as const;

function AlertCard({ businessId, a, onChanged }: { businessId: string; a: AlertRow; onChanged: () => void }) {
  const set = useAction((status: "read" | "resolved") => platform.setAlertStatus(businessId, a.id, status));
  return (
    <li className="rounded-2xl border border-border bg-surface p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={SEV[a.severity].tone}>{SEV[a.severity].label} severity</Badge>
        <Badge>{a.status === "open" ? "New" : a.status === "read" ? "Seen" : a.status}</Badge>
        <span className="text-sm text-muted">first seen {timeAgo(a.first_seen)}</span>
      </div>
      <h3 className="mt-2 text-lg font-semibold text-foreground">{a.title}</h3>
      <p className="mt-1 text-base text-foreground">{a.message}</p>
      {a.suggested_action ? <p className="mt-2 text-base text-foreground">What you could do: {a.suggested_action}</p> : null}
      <p className="mt-2 text-xs text-muted">
        Rule: {a.rule_name}. {a.severity_rule}
        {a.metric_value !== null && a.threshold !== null ? ` Measured ${a.metric_value}; threshold ${a.threshold}.` : ""}
      </p>
      {a.status === "open" || a.status === "read" ? (
        <div className="mt-3 flex flex-wrap gap-3">
          {a.status === "open" ? (
            <button className={btnSecondary} disabled={set.busy} onClick={async () => { if (await set.run("read")) onChanged(); }}>
              Mark as seen
            </button>
          ) : null}
          <button className={btnSecondary} disabled={set.busy} onClick={async () => { if (await set.run("resolved")) onChanged(); }}>
            Mark as resolved
          </button>
        </div>
      ) : null}
      <ActionError error={set.error} />
    </li>
  );
}

function RuleRow({ businessId, r, onChanged }: { businessId: string; r: AlertRule; onChanged: () => void }) {
  const [enabled, setEnabled] = useState(r.enabled);
  const [threshold, setThreshold] = useState(r.threshold === null ? "" : String(r.threshold));
  const [err, setErr] = useState<string | null>(null);
  const save = useAction(async () => {
    let t: number | null = null;
    if (r.threshold !== null || r.default_threshold !== null) {
      t = Number(threshold);
      if (!threshold.trim() || !Number.isFinite(t) || t <= 0) {
        setErr("Enter a number above zero.");
        return;
      }
    }
    setErr(null);
    await platform.setAlertRule(businessId, r.rule_key, enabled, t);
    onChanged();
  });
  const hasThreshold = r.default_threshold !== null;
  return (
    <li className="rounded-xl border border-border p-4">
      <p className="text-base font-semibold text-foreground">{r.name}</p>
      <p className="text-sm text-muted">{r.description}</p>
      <p className="text-xs text-muted">{r.severity_rule}</p>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <label className="flex min-h-[44px] items-center gap-2 text-base text-foreground">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} className="h-5 w-5" /> On
        </label>
        {hasThreshold ? (
          <label className="block text-sm font-medium text-foreground">
            Threshold {r.unit === "fraction" ? "(0.15 = 15%)" : r.unit === "days" ? "(days)" : ""}
            <input value={threshold} onChange={(e) => setThreshold(e.target.value)} inputMode="decimal" className={`${inputCls} w-32`} />
          </label>
        ) : null}
        <button className={btnPrimary} disabled={save.busy} onClick={() => save.run()}>
          Save
        </button>
        {r.is_default ? <span className="text-sm text-muted">Using the default.</span> : null}
      </div>
      {err ? <p className="mt-1 text-base text-danger">{err}</p> : null}
      <ActionError error={save.error} />
    </li>
  );
}

function Body({ id }: { id: string }) {
  const [anchor, setAnchor] = useState<Anchor>("today");
  const [state, setState] = useState<{ phase: "loading" } | { phase: "error"; error: FriendlyError } | { phase: "ready"; alerts: AlertRow[]; check: Awaited<ReturnType<typeof platform.checkAlerts>> | null }>({ phase: "loading" });
  const [rules, setRules] = useState<{ rules: AlertRule[]; cooldown_hours: number; monitoring_note: string } | null>(null);
  const [filter, setFilter] = useState<"active" | "resolved" | "cleared">("active");

  async function refresh(check: boolean, a: Anchor = anchor, f = filter) {
    try {
      const c = check ? await platform.checkAlerts(id, a) : null;
      const [list, r] = await Promise.all([platform.alerts(id, f), platform.alertRules(id)]);
      setState({ phase: "ready", alerts: list.alerts, check: c });
      setRules(r);
    } catch (e) {
      setState({ phase: "error", error: friendlyError(e) });
    }
  }
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- opening the page runs one on-demand check, as disclosed
    void refresh(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (state.phase === "loading") return <Spinner label="Checking your data against the alert rules…" />;
  if (state.phase === "error") return <ErrorBox error={state.error} onRetry={() => refresh(true)} />;
  const { alerts, check } = state;
  return (
    <div className="space-y-6">
      <Notice tone="info" title="Checked when you look, not around the clock">
        {rules?.monitoring_note} The same alert is not repeated within {rules?.cooldown_hours} hours.
      </Notice>
      {check ? (
        <p className="text-base text-muted">
          Just checked: {check.created} new, {check.refreshed} still true, {check.cleared} cleared, {check.suppressed_by_cooldown} held back by the cooldown.
        </p>
      ) : null}
      <div className="flex flex-wrap items-end gap-4">
        <PeriodPicker days={30} anchor={anchor} options={[30]} onChange={(_d, a) => setAnchor(a)} />
        <button className={btnPrimary} onClick={() => { setState({ phase: "loading" }); void refresh(true, anchor); }}>
          Check now
        </button>
        <label className="block text-sm font-medium text-foreground">
          Show
          <select
            value={filter}
            onChange={(e) => {
              const f = e.target.value as typeof filter;
              setFilter(f);
              void refresh(false, anchor, f);
            }}
            className={inputCls}
          >
            <option value="active">Active alerts</option>
            <option value="resolved">Resolved</option>
            <option value="cleared">Cleared (no longer true)</option>
          </select>
        </label>
      </div>
      {alerts.length === 0 ? (
        <Notice tone="success" title={filter === "active" ? "No active alerts" : "Nothing here"}>
          {filter === "active"
            ? check && check.suppressed_by_cooldown > 0
              ? `Nothing new to show. ${check.suppressed_by_cooldown} condition(s) you resolved are still true but are not raised again for ${rules?.cooldown_hours} hours.`
              : "None of the enabled rules is triggered by your recorded data right now."
            : "No alerts with this status."}
        </Notice>
      ) : (
        <ul className="space-y-4">
          {alerts.map((a) => (
            <AlertCard key={a.id} businessId={id} a={a} onChanged={() => refresh(false)} />
          ))}
        </ul>
      )}
      <Panel title="Alert rules" note="Change what counts as worth flagging. Turning a rule off clears its alerts the next time you check.">
        <ul className="space-y-3">
          {rules?.rules.map((r) => (
            <RuleRow key={`${r.rule_key}-${r.enabled}-${r.threshold}`} businessId={id} r={r} onChanged={() => refresh(true)} />
          ))}
        </ul>
      </Panel>
    </div>
  );
}

export default function AlertsPage() {
  return (
    <Workspace title="Smart Alerts" subtitle="Things in your records that deserve a look, each with the rule that raised it and the evidence.">
      {(id) => <Body id={id} />}
    </Workspace>
  );
}
