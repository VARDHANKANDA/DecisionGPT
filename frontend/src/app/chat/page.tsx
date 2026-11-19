"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { api, type ChatResponse, type DataLibraryEntry, type DataType } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { useLibrary } from "@/lib/use-library";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { ANSWER_TYPE_LABEL, EXAMPLE_QUESTIONS, FOLLOW_UPS, INTENT_EXPLANATION } from "@/lib/questions";
import { ErrorBox, KIND_ICON, Page, PreviewTable, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { VoiceInput } from "@/components/voice/VoiceInput";
import { EvaluationAnswer, isEvalChatDetails } from "@/components/evaluation-chat";

interface Turn {
  id: number;
  question: string;
  response: ChatResponse | null;
  error: FriendlyError | null;
}

const INTENT_DATA: Record<string, DataType> = {
  top_products: "sales",
  analytics_query: "sales",
  improving_worsening: "sales",
  sales_forecast: "sales",
  why_kpi_fell: "sales",
  price_change_advice: "sales",
  what_focus: "sales",
  customer_churn: "customers",
  valuable_customers: "customers",
  marketing_change_advice: "marketing_campaigns",
};

const pretty = (k: string) => k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

/** First sentence is the direct answer; the rest is the explanation. Splits only on ". " so ₹ amounts/decimals stay intact. */
function splitAnswer(text: string): [string, string] {
  const m = text.match(/^([^]+?[.!?])(\s+)([^]+)$/);
  return m ? [m[1], m[3]] : [text, ""];
}

function AnswerCard({
  turn,
  onFollowUp,
  onAsk,
  onRetry,
}: {
  turn: Turn;
  onFollowUp: (q: string) => void;
  onAsk: (q: string) => void;
  onRetry: () => void;
}) {
  const r = turn.response;
  const [copied, setCopied] = useState(false);

  if (turn.error) return <ErrorBox error={turn.error} onRetry={onRetry} />;
  if (!r) return <Spinner label="Analyzing your business data…" />;

  const meta = ANSWER_TYPE_LABEL[r.answer_type] ?? ANSWER_TYPE_LABEL.known;
  const evalDetails = isEvalChatDetails(r.details) ? r.details.evaluation : null;
  const [splitHead, splitRest] = splitAnswer(r.answer);
  const headline = evalDetails ? (evalDetails.headline ?? r.answer.split(/\r?\n/)[0]) : splitHead;
  const rest = evalDetails ? "" : splitRest;
  const insufficient = !r.sufficient_evidence;
  const dataType = INTENT_DATA[r.intent];
  const table = Array.isArray((r.details as { table?: unknown }).table)
    ? ((r.details as { table: Record<string, unknown>[] }).table)
    : null;
  const scalars = Object.entries(r.details).filter(
    ([k, v]) => k !== "table" && (typeof v === "number" || typeof v === "string")
  );
  const hasNumbers = (table && table.length > 0) || scalars.length > 0;

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(r.answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // ignore clipboard write failure
    }
  };

  return (
    <article
      aria-label="DecisionGPT's answer"
      className={`rounded-2xl border p-6 shadow-sm transition ${
        insufficient ? "border-warning/40 bg-warning-soft/30" : "border-border bg-surface"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${meta.tone}`}>
            {meta.label}
          </span>
          {r.path === "evaluation_service" ? (
            <span
              className="inline-block rounded-full border border-border bg-background px-2.5 py-0.5 text-xs text-muted"
              title="Recorded evaluation results were read and shown as they are. No AI model was used for any number, and nothing was recalculated."
            >
              Recorded evaluation results · no AI model used for the numbers
            </span>
          ) : r.path === "llm_analytics" ? (
            <span
              className="inline-block rounded-full border border-border bg-background px-2.5 py-0.5 text-xs text-muted"
              title="The AI model (OpenAI) classified what you asked. It did not calculate any number: the figures come from your data through DecisionGPT's calculation engine."
            >
              Question understood by the AI model (OpenAI) · numbers from your data
            </span>
          ) : r.path === "legacy_router" ? (
            <span
              className="inline-block rounded-full border border-border bg-background px-2.5 py-0.5 text-xs text-muted"
              title="A fixed-rule assistant answered. The AI question-understanding step was not used for this answer."
            >
              Standard assistant (rule-based)
            </span>
          ) : null}
        </div>

        <button
          type="button"
          onClick={copyAnswer}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border/80 px-2.5 py-1 text-xs font-medium text-muted hover:bg-muted-surface hover:text-foreground transition"
          title="Copy response to clipboard"
        >
          <span>{copied ? "✓" : "📋"}</span>
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>

      {r.notice ? (
        <p role="status" className="mt-3 rounded-xl bg-muted-surface/60 px-3.5 py-2 text-xs sm:text-sm text-muted">
          {r.notice}
        </p>
      ) : null}

      <p className="mt-3 text-base font-semibold leading-snug text-foreground">{headline}</p>
      {rest ? <p className="mt-2 text-sm leading-relaxed text-foreground/90 max-w-3xl">{rest}</p> : null}

      {evalDetails ? <EvaluationAnswer details={evalDetails} onFollowUp={onAsk} /> : null}

      {r.answer_type === "estimate" || r.answer_type === "suggestion" || r.answer_type === "evaluation" ? (
        <p className="mt-2.5 text-xs text-muted">
          <strong className="font-semibold text-foreground">Note:</strong> {meta.note}
        </p>
      ) : null}

      {insufficient ? (
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/data" className={btnSecondary}>
            Check Dataset Library
          </Link>
          <Link href="/data/upload/file" className={btnSecondary}>
            Upload Dataset
          </Link>
        </div>
      ) : null}

      {r.sources.length > 0 ? (
        <div className="mt-5 rounded-xl bg-muted-surface/40 px-4 py-3 border border-border/60">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">Supporting Evidence</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-foreground space-y-0.5">
            {r.sources.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="mt-4 space-y-2">
        <details className="rounded-xl border border-border bg-background">
          <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-foreground">
            Why am I seeing this?
          </summary>
          <div className="border-t border-border px-4 py-3 text-xs sm:text-sm text-muted">
            <p>{INTENT_EXPLANATION[r.intent] ?? "DecisionGPT analyzed records matching this inquiry."}</p>
            <p className="mt-1">{meta.note}</p>
            <p className="mt-2">
              <Link href="/explain" className="font-medium text-accent underline underline-offset-4">
                Learn how decisions and answers are validated
              </Link>
            </p>
          </div>
        </details>

        {evalDetails ? (
          <details className="rounded-xl border border-border bg-background">
            <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-foreground">
              Plain-text version of this answer
            </summary>
            <pre className="max-h-96 overflow-auto whitespace-pre-wrap border-t border-border px-4 py-3 text-xs font-mono text-foreground">
              {r.answer}
            </pre>
          </details>
        ) : null}

        {hasNumbers && !evalDetails ? (
          <details className="rounded-xl border border-border bg-background">
            <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-foreground">
              Inspect Quantitative Evidence
            </summary>
            <div className="space-y-3 border-t border-border px-4 py-3">
              {scalars.length > 0 ? (
                <dl className="grid gap-2 sm:grid-cols-2">
                  {scalars.map(([k, v]) => (
                    <div key={k}>
                      <dt className="text-xs text-muted">{pretty(k)}</dt>
                      <dd className="text-sm font-medium text-foreground">
                        {typeof v === "number" ? v.toLocaleString("en-IN") : String(v)}
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : null}
              {table && table.length > 0 ? (
                <PreviewTable columns={Object.keys(table[0]).map((k) => ({ key: k, label: pretty(k) }))} rows={table} />
              ) : null}
            </div>
          </details>
        ) : null}

        {dataType && !insufficient ? (
          <Link
            href={`/data/${dataType}`}
            className="flex items-center rounded-xl border border-border bg-background px-4 py-2.5 text-xs font-medium text-accent hover:bg-muted-surface"
          >
            <span aria-hidden="true" className="mr-2">{KIND_ICON[dataType]}</span>
            Inspect {pretty(dataType)} dataset records &rarr;
          </Link>
        ) : null}
      </div>

      <div className="mt-6 border-t border-border/60 pt-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted">Related Follow-Up Inquiries</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {(FOLLOW_UPS[r.intent] ?? FOLLOW_UPS.unrecognized).map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => onFollowUp(q)}
              className="rounded-full border border-border bg-background px-3.5 py-1.5 text-xs text-foreground hover:bg-muted-surface hover:border-accent transition"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </article>
  );
}

function Ask() {
  const search = useSearchParams();
  const { business, loading } = useBusiness();
  const library = useLibrary();
  const [text, setText] = useState(search.get("q") ?? "");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sending, setSending] = useState(false);
  const [showDataDetails, setShowDataDetails] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns]);

  async function run(turn: Turn) {
    if (!business) return;
    setSending(true);
    try {
      const resp = await api.chat(business.id, turn.question);
      setTurns((ts) => ts.map((t) => (t.id === turn.id ? { ...t, response: resp, error: null } : t)));
    } catch (err) {
      setTurns((ts) =>
        ts.map((t) =>
          t.id === turn.id
            ? { ...t, response: null, error: friendlyError(err, "Could not complete this query.") }
            : t
        )
      );
    } finally {
      setSending(false);
    }
  }

  function askNow(q: string) {
    if (!business) return;
    const turn: Turn = { id: nextId.current++, question: q, response: null, error: null };
    setTurns((t) => [...t, turn]);
    void run(turn);
  }

  function send() {
    const q = text.trim();
    if (!q || sending) return;
    setText("");
    askNow(q);
  }

  const fill = (q: string) => {
    setText(q);
    inputRef.current?.focus();
    inputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  };

  if (loading) return <Page title="Business Assistant"><Spinner label="Opening…" /></Page>;
  if (!business) {
    return (
      <Page title="Business Assistant" subtitle="Set up your business workspace to begin asking natural language questions.">
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business
        </Link>
      </Page>
    );
  }

  const withData = (library ?? []).filter((d) => d.rows > 0);
  const totalRowsConnected = withData.reduce((acc, d) => acc + d.rows, 0);

  return (
    <Page
      title="Business Assistant"
      subtitle="Explore business performance, customer patterns, and product trends through natural language queries backed by verified data."
      action={
        <div className="relative flex items-center gap-2">
          {/* Compact Business Data Connected Indicator */}
          <button
            type="button"
            onClick={() => setShowDataDetails(!showDataDetails)}
            className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/20 transition"
          >
            <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
            <span>Business data connected</span>
            <span className="text-[11px] opacity-75">({withData.length} tables)</span>
          </button>

          {turns.length > 0 && (
            <button
              type="button"
              onClick={() => setTurns([])}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-3 py-1.5 text-xs font-medium text-muted hover:text-foreground transition"
              title="Clear conversation history"
            >
              <span>↺</span>
              <span>Clear</span>
            </button>
          )}

          {/* Connected Data Details Popover */}
          {showDataDetails && (
            <div className="absolute right-0 top-10 z-20 w-72 rounded-2xl border border-border bg-surface p-4 shadow-xl">
              <div className="flex items-center justify-between pb-2 border-b border-border">
                <span className="text-xs font-semibold text-foreground">Connected Tables</span>
                <span className="text-xs text-muted">{totalRowsConnected.toLocaleString("en-IN")} total rows</span>
              </div>
              <ul className="mt-2.5 space-y-1.5 max-h-48 overflow-y-auto">
                {withData.length > 0 ? (
                  withData.map((d) => (
                    <li key={d.type} className="flex items-center justify-between text-xs py-1">
                      <span className="flex items-center gap-1.5 text-foreground">
                        <span>{KIND_ICON[d.type]}</span>
                        <span>{d.title}</span>
                      </span>
                      <span className="font-mono text-muted">{d.rows.toLocaleString("en-IN")}</span>
                    </li>
                  ))
                ) : (
                  <li className="text-xs text-muted py-2">No active tables found.</li>
                )}
              </ul>
              <div className="mt-3 pt-2 border-t border-border flex justify-between">
                <Link href="/data" className="text-xs font-medium text-accent hover:underline">
                  Manage Dataset Library &rarr;
                </Link>
                <button
                  type="button"
                  onClick={() => setShowDataDetails(false)}
                  className="text-xs text-muted hover:text-foreground"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      }
    >
      {/* Welcome Banner when conversation is empty */}
      {turns.length === 0 && (
        <section className="mb-6 rounded-2xl border border-border bg-gradient-to-br from-surface to-muted-surface/30 p-6 shadow-sm">
          <div className="max-w-2xl">
            <h2 className="text-xl font-semibold text-foreground">Understand & Explore Your Business</h2>
            <p className="mt-1.5 text-sm text-muted leading-relaxed">
              Ask questions about sales performance, top revenue-generating items, customer retention, or margin trajectories. Every answer is grounded in your company&apos;s actual transaction history.
            </p>
          </div>

          <div className="mt-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted">Example Inquiries</p>
            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
              {EXAMPLE_QUESTIONS.slice(0, 4).map((e) => (
                <button
                  key={e.question}
                  type="button"
                  onClick={() => fill(e.question)}
                  className="flex items-start gap-2.5 rounded-xl border border-border bg-background p-3.5 text-left text-sm text-foreground hover:border-accent hover:shadow-xs transition"
                >
                  <span className="text-base shrink-0">{e.icon}</span>
                  <span className="font-medium">{e.question}</span>
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Message Thread */}
      {turns.length > 0 && (
        <div className="mb-6 space-y-6" aria-live="polite">
          {turns.map((t) => (
            <div key={t.id} className="space-y-3">
              <div className="flex justify-end">
                <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm font-medium text-accent-foreground shadow-xs">
                  {t.question}
                </div>
              </div>
              <AnswerCard turn={t} onFollowUp={fill} onAsk={askNow} onRetry={() => void run(t)} />
            </div>
          ))}
          <div ref={endRef} />
        </div>
      )}

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="rounded-2xl border border-border bg-surface p-4 sm:p-5 shadow-sm"
      >
        <label htmlFor="question" className="text-xs font-semibold uppercase tracking-wider text-muted block mb-1">
          Ask a business question
        </label>
        <textarea
          id="question"
          ref={inputRef}
          value={text}
          rows={2}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          placeholder="e.g. Which products generated the highest revenue this quarter?"
          className="w-full resize-none rounded-xl border border-border bg-background p-3 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <VoiceInput label="your question" showLanguagePicker={false} onTranscript={(t) => setText(t)} />
            <span className="text-xs text-muted hidden sm:inline">Press Enter to send</span>
          </div>
          <button type="submit" disabled={sending || !text.trim()} className={btnPrimary}>
            {sending ? "Analyzing..." : "Ask"}
          </button>
        </div>
      </form>
    </Page>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<Page title="Business Assistant"><Spinner label="Opening…" /></Page>}>
      <Ask />
    </Suspense>
  );
}
