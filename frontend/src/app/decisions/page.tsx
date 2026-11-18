"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type DecisionSummary, type Goal } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, timeAgo, type FriendlyError } from "@/lib/friendly";
import { goalSentence, inr } from "@/lib/narrate";
import { useLibrary } from "@/lib/use-library";
import { DataUsed, ErrorBox, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { VoiceInput } from "@/components/voice/VoiceInput";

const EXAMPLES = [
  "Increase profit by 15% in 3 months.",
  "Increase revenue by 20% in 2 months.",
  "Reduce churn by 10%.",
  "Improve marketing ROI by 25% in 1 month.",
];

export default function DecisionsPage() {
  const { business, loading } = useBusiness();
  const router = useRouter();
  const library = useLibrary();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<FriendlyError | null>(null);
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [decisions, setDecisions] = useState<DecisionSummary[] | null>(null);

  useEffect(() => {
    if (!business) return;
    let cancelled = false;
    Promise.all([api.listGoals(business.id), api.listDecisions(business.id)])
      .then(([g, d]) => {
        if (cancelled) return;
        setGoals(g);
        setDecisions(d);
      })
      .catch(() => {
        if (cancelled) return;
        setGoals([]);
        setDecisions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [business]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!business || !text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const goal = await api.createGoal(business.id, text.trim());
      router.push(`/decision?goal=${goal.id}&run=1`);
    } catch (err) {
      setError(friendlyError(err, "We couldn't understand that goal. Try something like “Increase profit by 15% in 3 months.”"));
      setSubmitting(false);
    }
  }

  if (loading) return <Page title="Business Decisions"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Business Decisions" subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  return (
    <Page
      title="Recommendations & Decisions"
      subtitle="Evaluate candidate decisions and recommended actions: formulate business goals, review ranked alternatives, simulate trade-offs, and track implemented outcomes."
      wide
    >
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <form onSubmit={submit} className="min-w-0 rounded-2xl border border-border bg-surface p-6">
          <h2 className="text-xl font-semibold text-foreground">Tell DecisionGPT what you want to achieve</h2>
          <p className="mt-1 text-base text-muted">Write your goal in a sentence, the way you would say it — with a number and a time if you can.</p>
          <p className="mt-2 text-base text-foreground">DecisionGPT will suggest possible actions based on your goal and available data.</p>
          <p className="mt-2 text-base text-muted">Possible areas it may consider: <strong className="text-foreground">Pricing</strong> · <strong className="text-foreground">Marketing</strong> · <strong className="text-foreground">Stock</strong> — depending on your goal and data.</p>

          <div className="mt-4">
            <VoiceInput label="your goal" onTranscript={(t) => setText(t)} />
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            placeholder="For example: Increase profit by 15% in the next 3 months."
            className="input mt-3 min-h-[96px] w-full text-lg"
            aria-label="Your goal, in your own words"
            required
          />
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setText(ex)}
                className="min-h-[44px] rounded-full border border-border px-4 py-2 text-left text-base text-foreground hover:bg-muted-surface"
              >
                {ex}
              </button>
            ))}
          </div>
          <p className="mt-3 text-sm text-muted">Tapping an example only fills the box — nothing happens until you press the button.</p>

          {error ? <div className="mt-4"><ErrorBox error={error} /></div> : null}

          <div className="mt-5">
            <button type="submit" className={btnPrimary} disabled={submitting || !text.trim()}>
              {submitting ? "Understanding your goal…" : "Get suggestions"}
            </button>
          </div>
          <p className="mt-4 text-sm text-muted">
            DecisionGPT comes up with the actions itself and ranks them — you don&apos;t supply a list. It can&apos;t weigh other
            kinds of decisions yet.
          </p>
        </form>

        <div className="min-w-0 space-y-5">
          <DataUsed library={library} types={["sales", "products", "marketing_campaigns", "inventory"]} />
          <section className="rounded-2xl border border-border bg-surface p-5">
            <h2 className="text-base font-semibold text-foreground">Other ways to decide</h2>
            <ul className="mt-3 space-y-3">
              <li>
                <Link href="/simulation" className="block text-lg font-medium text-accent underline underline-offset-4">🧪 What-If Tester</Link>
                <span className="text-base text-muted">Try one change yourself and see what may happen.</span>
              </li>
              <li>
                <Link href="/causal-graph" className="block text-lg font-medium text-accent underline underline-offset-4">🔗 What Affects What</Link>
                <span className="text-base text-muted">See how price, marketing and stock are linked in your business.</span>
              </li>
            </ul>
          </section>
        </div>
      </div>

      <section aria-labelledby="your-goals" className="mt-10">
        <h2 id="your-goals" className="text-2xl font-semibold text-foreground">Your goals</h2>
        {goals === null ? (
          <div className="mt-3"><Spinner label="Loading your goals…" /></div>
        ) : goals.length === 0 ? (
          <p className="mt-2 text-lg text-muted">You haven&apos;t set a goal yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-border rounded-2xl border border-border bg-surface">
            {goals.map((g) => (
              <li key={g.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
                <span className="min-w-0 text-lg text-foreground">{goalSentence(g)}</span>
                <Link href={`/decision?goal=${g.id}`} className={btnSecondary}>Get suggestions</Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="past" className="mt-10">
        <h2 id="past" className="text-2xl font-semibold text-foreground">Earlier suggestions</h2>
        {decisions === null ? null : decisions.length === 0 ? (
          <div className="mt-3">
            <Notice>Your suggestions are kept here, so you can come back to them and record what happened.</Notice>
          </div>
        ) : (
          <>
            <ul className="mt-3 divide-y divide-border rounded-2xl border border-border bg-surface">
              {decisions.slice(0, 5).map((d) => (
                <li key={d.id} className="flex flex-wrap items-baseline justify-between gap-2 px-5 py-4">
                  <span className="min-w-0 text-base text-foreground">
                    {typeof d.expected_outcome_json.expected_revenue === "number"
                      ? `Suggestion: expected sales about ${inr(d.expected_outcome_json.expected_revenue)}, risk rated ${d.risk_level.toLowerCase()}`
                      : "A suggestion"}
                  </span>
                  <span className="text-sm text-muted">{timeAgo(d.created_at)}</span>
                </li>
              ))}
            </ul>
            <p className="mt-3">
              <Link href="/history" className="text-base font-medium text-accent underline underline-offset-4">See all and record what happened</Link>
            </p>
          </>
        )}
      </section>
    </Page>
  );
}
