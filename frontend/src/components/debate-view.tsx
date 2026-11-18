"use client";

import Link from "next/link";
import type { DebateBrief, DebateOption, DebateResult } from "@/lib/platform-api";
import { Notice } from "@/components/simple";
import { Panel } from "@/components/agent-ui";
import { Badge, BulletList, DataTable, Details } from "@/components/platform-ui";

const STAGE_TITLE: Record<string, string> = {
  question: "1 · The question",
  shared_evidence: "2 · Shared evidence",
  specialist_analyses: "3 · Specialist analyses (each worked alone)",
  challenges: "4 · Challenges",
  evidence_review: "5 · Evidence review",
  synthesis: "6 · Synthesis",
  decision_brief: "7 · Decision brief",
};

const STRENGTH_TONE = { strong: "good", moderate: "warn", weak: "neutral" } as const;

function Evidence({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <span className="text-xs text-muted">no evidence cited</span>;
  return (
    <span className="text-xs text-muted">
      evidence: {ids.map((i) => (<code key={i} className="mr-1 rounded bg-muted-surface px-1">{i}</code>))}
    </span>
  );
}

function Option({ o }: { o: DebateOption }) {
  return (
    <li className="rounded-xl border border-border p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-base font-semibold text-foreground">{o.title}</p>
        <Badge tone={STRENGTH_TONE[o.evidence_strength as keyof typeof STRENGTH_TONE] ?? "neutral"}>Evidence: {o.evidence_strength}</Badge>
        {o.open_challenges.length > 0 ? <Badge tone="warn">{o.open_challenges.length} open challenge(s)</Badge> : null}
      </div>
      <BulletList title="Trade-offs" items={o.trade_offs} />
      {o.simulation ? (
        <p className="mt-2 text-sm text-foreground">
          What-if simulation ({o.simulation.model}): expected sales ₹{Math.round(o.simulation.expected_revenue).toLocaleString("en-IN")} against a baseline of ₹
          {Math.round(o.simulation.baseline_revenue).toLocaleString("en-IN")} (range ₹{Math.round(o.simulation.lower).toLocaleString("en-IN")}–₹{Math.round(o.simulation.upper).toLocaleString("en-IN")}; risk {o.simulation.risk_level.toLowerCase()}). A projection from past data, not a measured effect.
        </p>
      ) : null}
    </li>
  );
}

export function Brief({ b }: { b: DebateBrief }) {
  return (
    <div className="space-y-4">
      <p className="text-lg font-medium text-foreground">{b.headline}</p>
      {b.recommended_option ? (
        <div className="rounded-xl border border-border bg-muted-surface/50 p-4">
          <p className="text-sm font-semibold text-muted">Option with the most supporting evidence</p>
          <p className="text-base font-semibold text-foreground">{b.recommended_option.title}</p>
          <BulletList items={b.recommended_option.trade_offs} />
        </div>
      ) : null}
      <BulletList title="Key facts" items={b.key_facts} />
      {b.disagreements.length > 0 ? (
        <div>
          <p className="text-sm font-semibold text-muted">Unresolved disagreements</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-base text-foreground">
            {b.disagreements.map((d) => (
              <li key={d.id}>
                <strong>{d.from}:</strong> {d.text}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {b.settled_by_calculation.length > 0 ? (
        <div>
          <p className="text-sm font-semibold text-muted">Settled by recalculating, not by voting</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-base text-foreground">
            {b.settled_by_calculation.map((d) => (
              <li key={d.id}>
                {d.text}
                {d.detail?.change_by_window_days ? (
                  <span className="text-muted">
                    {" "}
                    ({Object.entries(d.detail.change_by_window_days).map(([w, v]) => `${w}-day: ${v === null ? "n/a" : `${(v * 100).toFixed(1)}%`}`).join(", ")})
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <BulletList title="Missing information" items={b.missing_information} empty="Nothing important is missing for this question." />
      <BulletList title="Uncertainty that remains" items={b.unresolved_uncertainty} />
      <BulletList title="Sensible next steps" items={b.next_steps} />
      <p className="text-sm text-muted">Nothing was changed automatically. {b.automatic_actions_taken ? "" : "The decision is yours."}</p>
    </div>
  );
}

export function DebateView({ r }: { r: DebateResult }) {
  if (r.status === "ai_model_unavailable") {
    return (
      <Notice tone="warning" title="The AI-model debate is not available">
        {r.message}
      </Notice>
    );
  }
  if (r.status === "failed" || !r.stages) {
    return (
      <Notice tone="danger" title="The debate did not finish">
        {r.error ?? "It failed."} Nothing was made up to fill the gap.
      </Notice>
    );
  }
  const s = r.stages;
  return (
    <div className="space-y-5">
      <Notice tone="info" title={r.label}>
        {r.mode === "rule_based"
          ? "Each specialist is a fixed set of rules over your records. They do not “think” or talk — their claims, challenges and the resolution come from the code and the evidence below."
          : "Each specialist is an AI model call given only the evidence below. Every claim is checked against that evidence before it is shown; claims that cite nothing real are dropped."}
        {r.status === "partial" ? " Some steps did not return, so this result is partial." : ""}
      </Notice>

      <Panel title={STAGE_TITLE.question}>
        <p className="text-lg text-foreground">“{s.question.text}”</p>
        <p className="mt-1 text-sm text-muted">{s.question.topic_note} Topic found: {s.question.topic}.</p>
      </Panel>

      <Panel title={STAGE_TITLE.shared_evidence} note={`Every specialist sees exactly these facts, for ${s.shared_evidence.period.start} to ${s.shared_evidence.period.end}.`}>
        <DataTable columns={["ID", "Fact", "Source"]} rows={s.shared_evidence.facts.map((f) => [f.id, f.text, f.source])} caption="Shared evidence" />
        {s.shared_evidence.missing.length > 0 ? (
          <div className="mt-3">
            <BulletList title="Known gaps" items={s.shared_evidence.missing.map((m) => `${m.id}: ${m.text}`)} />
          </div>
        ) : null}
      </Panel>

      <Panel title={STAGE_TITLE.specialist_analyses} note="Written independently, before any specialist saw another's claims.">
        <div className="grid gap-4 md:grid-cols-2">
          {Object.values(s.specialist_analyses).map((a) => (
            <section key={a.agent} className="min-w-0 rounded-xl border border-border p-4">
              <h3 className="text-base font-semibold text-foreground">{a.name}</h3>
              <p className="text-sm text-muted">{a.role}</p>
              {a.ran === false ? <p className="mt-2 text-base text-warning">This specialist did not return a result.</p> : null}
              <ul className="mt-2 space-y-2">
                {a.claims.map((c) => (
                  <li key={c.id} className="text-base text-foreground">
                    <code className="mr-1 rounded bg-muted-surface px-1 text-xs">{c.id}</code>
                    {c.text} <Badge>{c.type}</Badge> <Evidence ids={c.evidence} />
                  </li>
                ))}
              </ul>
              {a.claims.length === 0 && a.ran !== false ? <p className="mt-2 text-base text-muted">Nothing to claim from the recorded data.</p> : null}
              {a.missing_information.length > 0 ? <BulletList title="Says it lacks" items={a.missing_information} /> : null}
              {a.rejected_claims && a.rejected_claims.length > 0 ? <p className="mt-2 text-xs text-muted">{a.rejected_claims.length} claim(s) were dropped because they were not supported by the evidence.</p> : null}
            </section>
          ))}
        </div>
      </Panel>

      <Panel title={STAGE_TITLE.challenges} note="One specialist questions another's claim. A numeric dispute is settled by recalculating.">
        {s.challenges.length === 0 ? (
          <p className="text-base text-muted">No challenges were raised.</p>
        ) : (
          <ul className="space-y-2">
            {s.challenges.map((c) => (
              <li key={c.id} className="rounded-xl border border-border p-3 text-base text-foreground">
                <code className="mr-1 rounded bg-muted-surface px-1 text-xs">{c.id}</code>
                <strong>{c.from.replace(/_/g, " ")}</strong> challenges <code className="rounded bg-muted-surface px-1 text-xs">{c.to_claim}</code>: {c.text}{" "}
                <Badge tone={c.resolution === "resolved_by_calculation" ? "good" : "warn"}>{c.resolution === "resolved_by_calculation" ? "Settled by recalculating" : "Still open"}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title={STAGE_TITLE.evidence_review} note="Does each claim have the evidence it cites, and was it challenged?">
        <DataTable
          columns={["Claim", "Specialist", "Status", "Challenges"]}
          rows={s.evidence_review.claims.map((c) => [c.claim_id, c.agent.replace(/_/g, " "), c.status.replace(/_/g, " "), c.challenges.join(", ") || "—"])}
          caption="Evidence review"
        />
        <BulletList title="Assumptions" items={s.evidence_review.assumptions} />
      </Panel>

      <Panel title={STAGE_TITLE.synthesis} note={s.synthesis.note}>
        {s.synthesis.insufficient_evidence ? <Notice tone="warning" title="Not enough evidence">{s.synthesis.insufficient_reason}</Notice> : null}
        <ul className="mt-2 space-y-3">{s.synthesis.options.map((o) => (<Option key={o.id} o={o} />))}</ul>
      </Panel>

      <Panel title={STAGE_TITLE.decision_brief}>
        <Brief b={s.decision_brief} />
      </Panel>

      {r.audit && r.audit.length > 0 ? (
        <Details summary="Model calls made for this debate">
          <DataTable columns={["Step", "Specialist", "Result", "Attempts", "Seconds"]} rows={r.audit.map((a) => [a.stage, a.agent ?? "—", a.ok ? "ok" : `failed: ${a.error}`, a.attempts, a.latency_s])} />
        </Details>
      ) : null}
      <p className="text-sm text-muted">
        Want to try an option? Use the{" "}
        <Link href="/simulation" className="font-medium text-accent underline underline-offset-4">
          What-If Scenarios
        </Link>{" "}
        page. DecisionGPT never acts on its own.
      </p>
    </div>
  );
}
