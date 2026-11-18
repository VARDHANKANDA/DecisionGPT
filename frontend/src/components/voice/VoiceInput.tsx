"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useVoiceLanguage } from "@/lib/voice/language-context";
import { langDef } from "@/lib/voice/locales";
import { useSpeechRecognition } from "@/lib/voice/use-speech-recognition";
import type { NormalizedVoiceError } from "@/lib/voice/support";
import { VoiceLanguagePicker } from "@/components/voice/VoiceLanguagePicker";

export interface VoiceInputProps {
  /** Receives the transcript the user reviewed and accepted. This is the SAME
   *  string a keyboard user would have typed — the caller feeds it into its
   *  existing text field / submit path. No decision is triggered here. */
  onTranscript: (text: string) => void;
  onError?: (error: NormalizedVoiceError) => void;
  disabled?: boolean;
  /** Short description of what the user is dictating, e.g. "your goal". */
  label?: string;
  /** Override the locale from context (mainly for testing). */
  locale?: string;
  showLanguagePicker?: boolean;
  className?: string;
}

/**
 * Accessible push-to-talk voice input. Flow (task §6):
 *   press mic -> speak -> transcript shown -> user edits/accepts -> caller
 *   submits via the existing typed path.
 * Always degrades to "type instead" — it never blocks the text interface.
 */
export function VoiceInput({
  onTranscript,
  onError,
  disabled = false,
  label = "your request",
  locale: localeProp,
  showLanguagePicker = true,
  className = "",
}: VoiceInputProps) {
  const { locale: ctxLocale, lang } = useVoiceLanguage();
  const locale = localeProp ?? ctxLocale;

  // Voice support depends on `window` APIs, which do not exist during SSR.
  // Render a stable placeholder until mounted so the server HTML and the first
  // client render match (no hydration mismatch); the real control appears after.
  const [mounted, setMounted] = useState(false);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot mount flag for SSR hydration safety (canonical isMounted pattern)
  useEffect(() => setMounted(true), []);

  const [draft, setDraft] = useState("");
  const [showReview, setShowReview] = useState(false);
  const reviewRef = useRef<HTMLTextAreaElement | null>(null);
  const statusId = useId();
  const reviewId = useId();

  const handleResult = useCallback((text: string) => {
    setDraft(text);
    setShowReview(true);
  }, []);

  const { status, error, interim, supported, start, stop } = useSpeechRecognition({
    locale,
    onResult: handleResult,
    onError,
  });

  useEffect(() => {
    if (showReview) reviewRef.current?.focus();
  }, [showReview]);

  const listening = status === "listening";

  function toggle() {
    if (disabled) return;
    if (listening) stop();
    else {
      setShowReview(false);
      setDraft("");
      start();
    }
  }

  function accept() {
    const text = draft.trim();
    if (!text) return;
    onTranscript(text);
    setShowReview(false);
    setDraft("");
  }

  function discard() {
    setShowReview(false);
    setDraft("");
  }

  // --- Pre-hydration placeholder (matches server + first client render) ---
  if (!mounted) {
    return (
      <div className={`flex min-h-[44px] items-center ${className}`} aria-hidden="true">
        <span className="inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 rounded-full border border-border bg-surface px-4 py-2.5 text-sm font-medium text-muted opacity-60">
          <span>🎤</span>
          <span>Speak</span>
        </span>
      </div>
    );
  }

  // --- Unsupported / blocked: show the fallback, keep the component inert ---
  if (!supported || status === "unsupported") {
    return (
      <p className={`text-xs text-muted ${className}`} role="note">
        Voice input isn&apos;t supported in this browser. You can type instead.
      </p>
    );
  }

  const micLabel = listening ? "Stop voice input" : `Start voice input for ${label}`;

  return (
    <div className={`flex flex-col gap-2 ${className}`}>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={toggle}
          disabled={disabled}
          aria-label={micLabel}
          aria-pressed={listening}
          aria-describedby={statusId}
          className={`inline-flex min-h-[44px] min-w-[44px] items-center justify-center gap-2 rounded-full border px-4 py-2.5 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:cursor-not-allowed disabled:opacity-50 ${
            listening
              ? "border-danger bg-danger-soft text-danger"
              : "border-border bg-surface text-foreground hover:bg-muted-surface"
          }`}
        >
          <span aria-hidden="true">{listening ? "⏹" : "🎤"}</span>
          <span>{listening ? "Stop" : "Speak"}</span>
        </button>

        {showLanguagePicker ? <VoiceLanguagePicker /> : null}
      </div>

      {/* Live status for screen readers and sighted users (not colour-only). */}
      <p id={statusId} className="min-h-[1.25rem] text-xs text-muted" aria-live="polite">
        {listening
          ? interim
            ? `Listening… “${interim}”`
            : "Listening…"
          : error
            ? error.message
            : showReview
              ? "Voice captured. Review the text below before you use it."
              : `Voice input is off. Recognition language: ${langDef(lang).englishName}.`}
      </p>

      {showReview ? (
        <div className="rounded-xl border border-border bg-muted-surface p-3">
          <label htmlFor={reviewId} className="text-xs font-medium text-foreground">
            You said (edit if needed):
          </label>
          <textarea
            id={reviewId}
            ref={reviewRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            className="input mt-1 resize-none bg-surface"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={accept}
              disabled={!draft.trim()}
              className="min-h-[40px] rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-foreground transition hover:opacity-90 disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Use this text
            </button>
            <button
              type="button"
              onClick={discard}
              className="min-h-[40px] rounded-full border border-border px-4 py-2 text-sm font-medium text-muted transition hover:bg-muted-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Discard
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
