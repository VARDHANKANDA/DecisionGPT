"use client";

import { useState } from "react";
import { platform, type Anchor, type Health } from "@/lib/platform-api";
import { Notice, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, Badge, BulletList, DataTable, Details, LineChart, PeriodPicker, Workspace, useAction } from "@/components/platform-ui";
import { timeAgo } from "@/lib/friendly";

function Score({ h }: { h: Health }) {
  if (h.composite_score === null) {
    return (
      <Notice tone="warning" title="No overall score — not enough data">
        {h.composite_unavailable_reason} The components below are still shown for whatever can be calculated.
      </Notice>
    );
  }
  const tone = h.composite_score >= 75 ? "good" : h.composite_score >= 50 ? "warn" : "bad";
  return (
    <div className="rounded-2xl border border-border bg-surface p-6">
      <p className="text-sm font-semibold text-muted">Business health ({h.version})</p>
      <p className="mt-1 text-5xl font-semibold text-foreground">
        {h.composite_score.toFixed(1)}
        <span className="text-xl text-muted"> / 100</span>
      </p>
      <p className="mt-2">
        <Badge tone={tone}>{h.level}</Badge>
      </p>
      <p className="mt-3 text-sm text-muted">
        Based on {Math.round(h.available_weight_share * 100)}% of the full weight. Levels: {h.level_thresholds.map((t) => `${t.label} from ${t.min}`).join(", ")}.
      </p>
    </div>
  );
}

function History({ id }: { id: string }) {
  const load = useLoad(() => platform.healthHistory(id));
  return (
    <Panel title="Saved scores" note="Only scores you saved are listed. Nothing is saved in the background.">
      <LoadView load={load} label="Loading saved scores…">
        {({ snapshots }) =>
          snapshots.length === 0 ? (
            <p className="text-base text-muted">No saved scores yet.</p>
          ) : (
            <>
              {snapshots.filter((s) => s.score !== null).length >= 2 ? (
                <LineChart
                  label="Saved health scores"
                  points={[...snapshots].filter((s) => s.score !== null).reverse().map((s) => ({ date: s.created_at.slice(0, 10), value: s.score as number }))}
                />
              ) : null}
              <DataTable
                columns={["Saved", "Score", "Period", "Version"]}
                rows={snapshots.slice(0, 15).map((s) => [timeAgo(s.created_at), s.score === null ? "No score" : s.score.toFixed(1), `${s.period_days} days`, s.version])}
              />
            </>
          )
        }
      </LoadView>
    </Panel>
  );
}

function Body({ id, days, anchor }: { id: string; days: number; anchor: Anchor }) {
  const load = useLoad(() => platform.health(id, days, anchor));
  const [version, setVersion] = useState(0);
  const save = useAction(() => platform.health(id, days, anchor, true));
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-6">
      <LoadView load={load} label="Working out your health score…">
        {(h) => (
          <>
            <Score h={h} />
            <Panel title="What it is made of" note={`Period ending ${h.period.end}. A component that cannot be calculated is left out and the others are re-weighted — missing data is never counted as bad performance.`}>
              <ul className="space-y-3">
                {h.components.map((c) => (
                  <li key={c.key} className="rounded-xl border border-border p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-base font-semibold text-foreground">{c.name}</p>
                      {c.available ? <Badge tone={(c.score ?? 0) >= 75 ? "good" : (c.score ?? 0) >= 50 ? "warn" : "bad"}>{c.score} / 100</Badge> : <Badge>Not available</Badge>}
                    </div>
                    <p className="mt-1 text-base text-foreground">{c.available ? c.detail : c.unavailable_reason}</p>
                    <p className="mt-1 text-sm text-muted">
                      Weight {Math.round(c.weight * 100)}%{c.effective_weight !== null ? ` (counts for ${Math.round(c.effective_weight * 100)}% after leaving out missing parts)` : ""}. Rule: {c.rule}
                    </p>
                  </li>
                ))}
              </ul>
            </Panel>
            <Details summary="Limits of this score">
              <BulletList items={h.limitations} />
            </Details>
            <div className="flex flex-wrap items-center gap-3">
              <button
                className={btnSecondary}
                disabled={save.busy}
                onClick={async () => {
                  if (await save.run()) {
                    setSaved(true);
                    setVersion((n) => n + 1);
                  }
                }}
              >
                Save this score to history
              </button>
              {saved ? <span className="text-base text-success">Saved.</span> : null}
            </div>
            <ActionError error={save.error} />
          </>
        )}
      </LoadView>
      <History key={version} id={id} />
    </div>
  );
}

export default function HealthPage() {
  const [days, setDays] = useState(30);
  const [anchor, setAnchor] = useState<Anchor>("today");
  return (
    <Workspace title="Business Health Score" subtitle="A simple, fully explained indicator built from a few things in your own records. It is a guide, not a verdict.">
      {(id) => (
        <div className="space-y-6">
          <PeriodPicker days={days} anchor={anchor} onChange={(d, a) => { setDays(d); setAnchor(a); }} />
          <Body key={`${id}-${days}-${anchor}`} id={id} days={days} anchor={anchor} />
        </div>
      )}
    </Workspace>
  );
}
