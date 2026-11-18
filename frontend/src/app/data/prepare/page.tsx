"use client";

import Link from "next/link";
import { platform, type PipelineStage } from "@/lib/platform-api";
import { Notice, btnPrimary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { Badge, BulletList, Workspace } from "@/components/platform-ui";
import { timeAgo } from "@/lib/friendly";

const STATE: Record<PipelineStage["state"], { label: string; tone: "good" | "warn" | "bad" | "neutral" }> = {
  not_started: { label: "Not started", tone: "neutral" },
  in_progress: { label: "In progress", tone: "warn" },
  needs_attention: { label: "Needs attention", tone: "warn" },
  ready: { label: "Ready", tone: "good" },
  failed: { label: "Failed", tone: "bad" },
};

function Body({ id }: { id: string }) {
  const load = useLoad(() => platform.pipeline(id));
  return (
    <LoadView load={load} label="Checking each stage…">
      {(p) => (
        <div className="space-y-6">
          <Notice tone={p.ready_for_analysis ? "success" : "warning"} title={p.ready_for_analysis ? "Your data is ready for analysis" : "Your data is not fully ready yet"}>
            {p.ready_for_analysis
              ? "Source data exists and no validation check has failed."
              : "See the stage marked “Needs attention” or “Not started” below. Analyses still run, but their results may be affected."}
          </Notice>
          {p.downstream_may_need_refresh.length > 0 ? (
            <Notice tone="warning" title="Some results may be out of date">
              Your data changed after these were last produced: {p.downstream_may_need_refresh.join(", ")}. Open them to refresh.
            </Notice>
          ) : null}
          <ol className="space-y-3">
            {p.stages.map((s, i) => (
              <li key={s.key} className="flex flex-wrap items-center gap-3 rounded-2xl border border-border bg-surface p-4">
                <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted-surface text-sm font-semibold">
                  {i + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-lg font-semibold text-foreground">{s.name}</p>
                  <p className="text-base text-muted">{s.detail}</p>
                </div>
                <Badge tone={STATE[s.state].tone}>{STATE[s.state].label}</Badge>
                {s.link ? (
                  <Link href={s.link} className="font-medium text-accent underline underline-offset-4">
                    Open
                  </Link>
                ) : null}
              </li>
            ))}
          </ol>
          <Panel title="Last activity">
            <p className="text-base text-foreground">
              Data last changed: {p.last_data_change ? timeAgo(p.last_data_change) : "no changes recorded"}. Last preparation step: {p.last_prepared ? timeAgo(p.last_prepared) : "none yet"}.
            </p>
          </Panel>
          <BulletList title="Good to know" items={p.limitations} />
          <Link href="/data/validate" className={btnPrimary}>
            Run validation
          </Link>
        </div>
      )}
    </LoadView>
  );
}

export default function PreparePage() {
  return (
    <Workspace title="Preparation & Readiness" subtitle="One view of the whole path from your source data to analysis: profiling, cleaning, validation and transformation, each with its real state.">
      {(id) => <Body id={id} />}
    </Workspace>
  );
}
