"use client";

import { useState } from "react";
import { api, ApiError, type ChatResponse } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, PageHeader, PrimaryButton, SecondaryLink } from "@/components/ui";
import { VoiceInput } from "@/components/voice/VoiceInput";

const EXAMPLES = [
  "Why did my revenue fall?",
  "Should I increase my price?",
  "What if I increase ad spend?",
  "What should I focus on?",
  "Why did you recommend this?",
];

interface Turn {
  question: string;
  response: ChatResponse | null;
  error: string | null;
}

export default function ChatPage() {
  const { business, loading: businessLoading } = useBusiness();
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sending, setSending] = useState(false);

  async function send(message: string) {
    if (!business || !message.trim()) return;
    setSending(true);
    setText("");
    const turn: Turn = { question: message, response: null, error: null };
    setTurns((prev) => [...prev, turn]);
    try {
      const response = await api.chat(business.id, message);
      setTurns((prev) => prev.map((t) => (t === turn ? { ...t, response } : t)));
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong answering that.";
      setTurns((prev) => prev.map((t) => (t === turn ? { ...t, error: message } : t)));
    } finally {
      setSending(false);
    }
  }

  if (!businessLoading && !business) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="text-muted">Set up your business first.</p>
        <div className="mt-4">
          <SecondaryLink href="/onboarding">Go to onboarding</SecondaryLink>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col px-6 py-12">
      <PageHeader
        title="Ask DecisionGPT"
        subtitle="Answers are grounded in your own data — if there isn't enough evidence, it will say so."
      />

      {turns.length === 0 ? (
        <Card>
          <p className="text-sm text-muted">Try one of these:</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                onClick={() => send(ex)}
                className="rounded-full border border-border px-3 py-1.5 text-sm text-foreground hover:bg-muted-surface"
              >
                {ex}
              </button>
            ))}
          </div>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {turns.map((turn, i) => (
            <div key={i} className="flex flex-col gap-2">
              <div className="ml-auto max-w-[80%] rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-sm text-accent-foreground">
                {turn.question}
              </div>
              {turn.error ? (
                <div className="max-w-[80%] rounded-2xl rounded-bl-sm bg-danger-soft px-4 py-2.5 text-sm text-danger">
                  {turn.error}
                </div>
              ) : turn.response ? (
                <div
                  className={`max-w-[80%] rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm ${
                    turn.response.sufficient_evidence
                      ? "bg-muted-surface text-foreground"
                      : "bg-warning-soft text-warning"
                  }`}
                >
                  <p>{turn.response.answer}</p>
                  {turn.response.sources.length > 0 ? (
                    <p className="mt-2 text-xs opacity-70">Based on: {turn.response.sources.join("; ")}</p>
                  ) : null}
                </div>
              ) : (
                <div className="max-w-[80%] rounded-2xl rounded-bl-sm bg-muted-surface px-4 py-2.5 text-sm text-muted">
                  Thinking…
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-6">
        <VoiceInput
          label="your question"
          showLanguagePicker={false}
          onTranscript={(t) => setText(t)}
        />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(text);
        }}
        className="sticky bottom-6 mt-3 flex items-center gap-3 rounded-full border border-border bg-surface p-2 shadow-sm"
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask about your business…"
          aria-label="Ask about your business"
          className="flex-1 rounded-full border-none bg-transparent px-3 py-2 text-sm outline-none"
        />
        <PrimaryButton type="submit" disabled={sending || !text.trim()} className="shrink-0">
          {sending ? "…" : "Send"}
        </PrimaryButton>
      </form>
    </div>
  );
}
