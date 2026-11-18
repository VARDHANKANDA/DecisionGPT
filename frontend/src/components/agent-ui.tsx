"use client";

import Link from "next/link";
import { useEffect, useState, type ReactNode } from "react";
import { api, type DecisionSummary } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import type { Agent } from "@/lib/features";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import { ErrorBox, Spinner, btnPrimary, btnSecondary } from "@/components/simple";

/** One agent's header: icon, name, one-sentence purpose, what it uses, its REAL status and its limits. */
export function AgentHero({ agent }: { agent: Agent }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-6">
      <div className="flex flex-wrap items-start gap-4">
        <span aria-hidden="true" className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-accent-soft text-3xl">
          {agent.icon}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-lg text-foreground">{agent.purpose}</p>
          <p className="mt-2 inline-block rounded-full bg-muted-surface px-3 py-1 text-sm font-medium text-foreground">
            <span className="text-muted">Status: </span>
            {agent.status}
          </p>
        </div>
      </div>
      <dl className="mt-5 grid gap-4 sm:grid-cols-2">
        <div>
          <dt className="text-sm font-semibold text-muted">What it uses</dt>
          <dd className="mt-1 text-base text-foreground">{agent.uses}</dd>
        </div>
        <div>
          <dt className="text-sm font-semibold text-muted">What it is — and isn&apos;t</dt>
          <dd className="mt-1 text-base text-foreground">{agent.scope}</dd>
        </div>
      </dl>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <a href="#consult-workspace" className={btnPrimary}>
          Execute {agent.name} Task &darr;
        </a>
        <Link href="/agents/debate" className={btnSecondary}>
          Deliberate in Multi-Agent Debate &rarr;
        </Link>
      </div>
    </section>
  );
}

export function Panel({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border bg-surface p-6">
      <h2 className="text-xl font-semibold text-foreground">{title}</h2>
      {note ? <p className="mt-1 text-sm text-muted">{note}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Facts({ items }: { items: { label: string; value: string; hint?: string }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((i) => (
        <div key={i.label} className="min-w-0 rounded-xl bg-muted-surface/60 p-4">
          <dt className="text-sm text-muted">{i.label}</dt>
          <dd className="mt-1 break-words text-xl font-semibold text-foreground">{i.value}</dd>
          {i.hint ? <p className="mt-1 text-xs text-muted">{i.hint}</p> : null}
        </div>
      ))}
    </dl>
  );
}

/** Label for how to read a statement. Colour is never the only signal: the word is always shown. */
export function Kind({ kind }: { kind: "From your records" | "An estimate" | "A suggestion" | "Not available" }) {
  const tone =
    kind === "From your records" ? "bg-success-soft text-success" : kind === "Not available" ? "bg-muted-surface text-muted" : "bg-warning-soft text-warning";
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${tone}`}>{kind}</span>;
}

type Load<T> = { state: "loading" } | { state: "error"; error: FriendlyError } | { state: "ready"; data: T };

/** Run an async loader for the current business; handles loading and error uniformly. */
export function useLoad<T>(loader: (businessId: string) => Promise<T>): Load<T> & { retry: () => void } {
  const { business } = useBusiness();
  const [result, setResult] = useState<Load<T>>({ state: "loading" });
  const [attempt, setAttempt] = useState(0);
  const businessId = business?.id;
  useEffect(() => {
    if (!businessId) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset to loading when the business or retry counter changes
    setResult({ state: "loading" });
    loader(businessId)
      .then((data) => !cancelled && setResult({ state: "ready", data }))
      .catch((e) => !cancelled && setResult({ state: "error", error: friendlyError(e) }));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- the loader is a stable closure over api calls; re-run only on business/retry
  }, [businessId, attempt]);
  return { ...result, retry: () => setAttempt((n) => n + 1) };
}

export function LoadView<T>({ load, label, children }: { load: Load<T> & { retry: () => void }; label: string; children: (data: T) => ReactNode }) {
  if (load.state === "loading") return <Spinner label={label} />;
  if (load.state === "error") return <ErrorBox error={load.error} onRetry={load.retry} />;
  return <>{children(load.data)}</>;
}

/** The most recent recommendation (if any) with the stored output of each agent that reviewed it. Real stored data only. */
export interface AgentRunOutput {
  agent_name: string;
  output: Record<string, unknown>;
}
export interface LatestAnalysis {
  summary: DecisionSummary | null;
  runs: AgentRunOutput[];
}

export async function loadLatestAnalysis(businessId: string): Promise<LatestAnalysis> {
  const list = await api.listDecisions(businessId);
  if (list.length === 0) return { summary: null, runs: [] };
  const summary = [...list].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))[0];
  const trace = await api.decisionTrace(businessId, summary.id);
  return { summary, runs: (trace.agent_runs ?? []).map((r) => ({ agent_name: r.agent_name, output: r.output })) };
}

const strings = (v: unknown): string[] => (Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : []);

function BulletList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-sm font-semibold text-muted">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-base text-foreground">
        {items.map((t) => (<li key={t}>{t}</li>))}
      </ul>
    </div>
  );
}

/** The agent's own stored output from the latest recommendation analysis (first-round assessment plus its second-round stance). */
export function StoredReview({ reviewKey, agentName }: { reviewKey: string; agentName: string }) {
  const load = useLoad(loadLatestAnalysis);
  return (
    <Panel title={`${agentName}'s review of your latest recommendation`} note="Produced by a rule-based check that runs whenever you ask Business Decisions for suggestions.">
      <LoadView load={load} label="Looking for your latest recommendation…">
        {(a) => {
          if (!a.summary) {
            return (
              <div>
                <p className="text-base text-foreground">There is no review yet — you haven&apos;t asked for a recommendation.</p>
                <div className="mt-3"><Link href="/decisions" className={btnSecondary}>Get suggestions</Link></div>
              </div>
            );
          }
          const first = a.runs.find((r) => r.agent_name === reviewKey && r.output.round === 1);
          const second = a.runs.find((r) => r.agent_name === reviewKey && r.output.round === 2);
          if (!first) return <p className="text-base text-foreground">The latest recommendation did not include a review from this agent.</p>;
          const score = typeof first.output.score === "number" ? first.output.score : null;
          const challenges = second ? strings(second.output.challenges) : [];
          return (
            <div className="space-y-4">
              <p><Kind kind="A suggestion" /></p>
              <BulletList title="What it found" items={strings(first.output.key_points)} />
              <BulletList title="Risks it raised" items={strings(first.output.risks)} />
              <BulletList title="Assumptions it relied on" items={strings(first.output.assumptions)} />
              {second ? (
                <div>
                  <p className="text-sm font-semibold text-muted">After comparing with the other reviews</p>
                  <p className="text-base text-foreground">{second.output.concurs === true ? "It agreed with the others." : "It raised concerns."}</p>
                  {challenges.length > 0 ? <ul className="mt-1 list-disc space-y-1 pl-5 text-base text-foreground">{challenges.map((c) => (<li key={c}>{c}</li>))}</ul> : null}
                </div>
              ) : null}
              {score !== null ? <p className="text-sm text-muted">Its score: {score.toFixed(2)} on a 0–1 scale from a fixed rule. It is not a probability that the action will work.</p> : null}
              <p className="text-sm text-muted">
                From the recommendation {timeAgo(a.summary.created_at).toLowerCase()}.{" "}
                <Link href={`/decision?goal=${a.summary.goal_id}`} className="font-medium text-accent underline underline-offset-4">Open it</Link>
              </p>
            </div>
          );
        }}
      </LoadView>
    </Panel>
  );
}
