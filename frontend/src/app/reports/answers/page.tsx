"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type BusinessMemoryEntry, type DecisionSummary, type Goal } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { isDemoBusiness } from "@/lib/demo";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import { goalSentence, inr } from "@/lib/narrate";
import { ANSWER_TYPE_LABEL } from "@/lib/questions";
import { ErrorBox, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";

interface Saved {
  id: string;
  question: string;
  answer: string;
  when: string;
  type: string;
  sources: string[];
  sufficient: boolean;
}

function toSaved(m: BusinessMemoryEntry): Saved | null {
  const meta = m.metadata_json ?? {};
  const fromContent = m.content.match(/^Q:\s*(.*?)\nA:\s*([\s\S]*)$/);
  const question = typeof meta.question === "string" ? meta.question : fromContent?.[1];
  const answer = typeof meta.answer === "string" ? meta.answer : fromContent?.[2];
  if (!question || !answer) return null;
  return {
    id: m.id,
    question,
    answer,
    when: m.created_at,
    type: typeof meta.answer_type === "string" ? meta.answer_type : "known",
    sources: Array.isArray(meta.sources) ? (meta.sources as string[]) : [],
    sufficient: meta.sufficient_evidence !== false,
  };
}

type Entry =
  | { kind: "answer"; when: string; s: Saved }
  | { kind: "decision"; when: string; d: DecisionSummary; similar: DecisionSummary[] };

/** Re-running the same goal gives the same result again; show those together instead of as separate decisions. */
function groupSimilar(ds: DecisionSummary[]): Entry[] {
  const groups = new Map<string, DecisionSummary[]>();
  for (const d of [...ds].sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))) {
    const o = d.expected_outcome_json as { expected_revenue?: number; baseline_revenue?: number };
    const key = `${d.goal_id}|${o.expected_revenue ?? ""}|${o.baseline_revenue ?? ""}|${d.risk_level}`;
    groups.set(key, [...(groups.get(key) ?? []), d]);
  }
  return [...groups.values()].map((g): Entry => ({ kind: "decision", when: g[0].created_at, d: g[0], similar: g.slice(1) }));
}

const TAG = "inline-block rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide";

export default function ReportsPage() {
  const { business, loading } = useBusiness();
  const [items, setItems] = useState<Saved[] | null>(null);
  const [decisions, setDecisions] = useState<DecisionSummary[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [show, setShow] = useState<"all" | "answers" | "decisions">("all");
  const [error, setError] = useState<FriendlyError | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    Promise.all([api.listMemory(business.id, "chat"), api.listDecisions(business.id), api.listGoals(business.id)])
      .then(([list, ds, gs]) => {
        if (cancelled) return;
        setItems(list.map(toSaved).filter((x): x is Saved => x !== null));
        setDecisions(ds);
        setGoals(gs);
        setError(null);
      })
      .catch((e) => !cancelled && setError(friendlyError(e)));
    return () => {
      cancelled = true;
    };
  }, [business, attempt]);

  if (loading) return <Page title="Saved Answers"><Spinner label="Opening…" /></Page>;
  if (!business) {
    return (
      <Page title="Saved Answers">
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business
        </Link>
      </Page>
    );
  }

  const entries: Entry[] = [
    ...(show === "decisions" || !items ? [] : items.map((s): Entry => ({ kind: "answer", when: s.when, s }))),
    ...(show === "answers" ? [] : groupSimilar(decisions)),
  ].sort((a, b) => +new Date(b.when) - +new Date(a.when));

  return (
    <Page title="Saved Answers" subtitle="Your saved questions and recommendations.">
      {error ? <ErrorBox error={error} onRetry={() => setAttempt((n) => n + 1)} /> : null}
      {!items && !error ? <Spinner label="Finding your answers…" /> : null}

      {items && items.length === 0 && decisions.length === 0 ? (
        <Notice title="No saved reports yet.">
          Your saved chat answers and recommendations will appear here. Try{" "}
          <Link href="/chat" className="font-medium text-accent underline underline-offset-4">Chat with Your Data</Link> or{" "}
          <Link href="/decisions" className="font-medium text-accent underline underline-offset-4">Business Decisions</Link>.
        </Notice>
      ) : null}

      {items && (items.length > 0 || decisions.length > 0) ? (
        <>
          <div role="group" aria-label="Show" className="mb-5 flex flex-wrap gap-2">
            {(
              [
                ["all", "Everything"],
                ["answers", `Chat answers (${items.length})`],
                ["decisions", `Recommendations (${groupSimilar(decisions).length})`],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                onClick={() => setShow(k)}
                aria-pressed={show === k}
                className={`min-h-[44px] rounded-full border px-5 py-2 text-base font-medium ${
                  show === k ? "border-accent bg-accent-soft text-accent" : "border-border text-foreground hover:bg-muted-surface"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <ul className="grid gap-4">
            {entries.map((entry) => {
              if (entry.kind === "decision") {
                const d = entry.d;
                const similar = entry.similar;
                const goal = goals.find((g) => g.id === d.goal_id);
                return (
                  <li key={d.id} className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
                    <div className="mb-2 flex flex-wrap gap-2">
                      <span className={`${TAG} bg-accent-soft text-accent`}>Recommendation</span>
                      {isDemoBusiness(business) ? <span className={`${TAG} bg-warning-soft text-warning`}>Demo recommendation</span> : null}
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h2 className="min-w-0 text-xl font-semibold text-foreground">
                        <span aria-hidden="true">💡 </span>
                        Suggestion{goal ? ` for “${goalSentence(goal)}”` : ""}
                      </h2>
                      <span className="text-base text-muted">{timeAgo(d.created_at)}</span>
                    </div>
                    {typeof d.expected_outcome_json.expected_revenue === "number" ? (
                      <p className="mt-2 text-lg text-foreground/90">
                        Expected sales about {inr(d.expected_outcome_json.expected_revenue)}
                        {typeof d.expected_outcome_json.baseline_revenue === "number"
                          ? ` (${inr(d.expected_outcome_json.baseline_revenue)} if nothing changed)`
                          : ""}
                        .
                      </p>
                    ) : null}
                    <p className="mt-2 text-sm text-muted">From Business Decisions · risk rated {d.risk_level.toLowerCase()}</p>
                    {similar.length > 0 ? (
                      <details className="mt-2">
                        <summary className="min-h-[44px] cursor-pointer py-2 text-base text-muted">
                          {similar.length + 1} similar recommendations — same goal, same result
                        </summary>
                        <p className="text-sm text-muted">
                          Also created {similar.map((x) => timeAgo(x.created_at).toLowerCase()).join(", ")}. Running the same goal again
                          on the same data gives the same suggestion.
                        </p>
                      </details>
                    ) : null}
                    <div className="mt-3">
                      <Link href="/history" className={btnSecondary}>Open, and record what happened</Link>
                    </div>
                  </li>
                );
              }
              const s = entry.s;
              const meta = ANSWER_TYPE_LABEL[s.type] ?? ANSWER_TYPE_LABEL.known;
              const first = s.answer.match(/^([^]+?[.!?])(\s|$)/)?.[1] ?? s.answer;
              return (
                <li key={s.id} className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
                  <div className="mb-2"><span className={`${TAG} bg-muted-surface text-muted`}>Chat answer</span></div>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="min-w-0 text-xl font-semibold text-foreground">“{s.question}”</h2>
                    <span className="text-base text-muted">{timeAgo(s.when)}</span>
                  </div>
                  <p className="mt-2 text-lg text-foreground/90">{first}</p>
                  <p className="mt-2 text-sm text-muted">
                    From Chat with Your Data{s.sources.length > 0 ? ` · based on ${s.sources.join("; ")}` : ""}
                  </p>
                  <span className={`mt-3 inline-block rounded-full px-3 py-1 text-sm font-medium ${meta.tone}`}>{meta.label}</span>
                  <details className="mt-3">
                    <summary className="min-h-[44px] cursor-pointer py-2 text-base font-medium text-accent">View full answer</summary>
                    <p className="mt-1 text-base leading-relaxed text-foreground">{s.answer}</p>
                    <p className="mt-2 text-sm text-muted">{meta.note}</p>
                    <div className="mt-3">
                      <Link href={`/chat?q=${encodeURIComponent(s.question)}`} className={btnSecondary}>Ask this again</Link>
                    </div>
                  </details>
                </li>
              );
            })}
          </ul>
        </>
      ) : null}
    </Page>
  );
}
