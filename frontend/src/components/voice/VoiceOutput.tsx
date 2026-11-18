"use client";

import { useEffect, useId, useState } from "react";
import { useVoiceLanguage } from "@/lib/voice/language-context";
import { useSpeechSynthesis } from "@/lib/voice/use-speech-synthesis";

export interface VoiceOutputProps {
  /** The already-displayed text to read aloud. Sanitised before speaking. */
  text: string;
  /** Override the locale from context (mainly for testing). */
  locale?: string;
  /** Short description of what will be read, for the accessible name. */
  label?: string;
  className?: string;
}

/**
 * Opt-in "Listen" control for an important, already-visible piece of text
 * (task §3, §11). Nothing is spoken until the user presses Listen; the button
 * is the only trigger. No page is ever auto-read.
 */
export function VoiceOutput({ text, locale: localeProp, label = "the recommendation", className = "" }: VoiceOutputProps) {
  const { locale: ctxLocale } = useVoiceLanguage();
  const locale = localeProp ?? ctxLocale;
  const { status, supported, speak, pause, resume, stop } = useSpeechSynthesis();
  const statusId = useId();

  // speechSynthesis is a `window` API — absent during SSR. Render nothing until
  // mounted so the server HTML and first client render match (no hydration
  // mismatch); this control is opt-in and off-screen-until-used anyway.
  const [mounted, setMounted] = useState(false);
  // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot mount flag for SSR hydration safety (canonical isMounted pattern)
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;

  if (!supported || status === "unsupported") {
    return (
      <p className={`text-xs text-muted ${className}`} role="note">
        Text-to-speech isn&apos;t available in this browser.
      </p>
    );
  }

  const speaking = status === "speaking";
  const paused = status === "paused";
  const btn =
    "inline-flex min-h-[40px] items-center justify-center gap-2 rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium text-foreground transition hover:bg-muted-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

  return (
    <div className={`flex flex-col gap-1 ${className}`}>
      <div className="flex flex-wrap items-center gap-2">
        {!speaking && !paused ? (
          <button
            type="button"
            onClick={() => speak(text, locale)}
            aria-label={`Listen to ${label}`}
            aria-describedby={statusId}
            className={btn}
          >
            <span aria-hidden="true">🔊</span>
            <span>Listen</span>
          </button>
        ) : null}

        {speaking ? (
          <button type="button" onClick={pause} aria-label="Pause reading" className={btn}>
            <span aria-hidden="true">⏸</span>
            <span>Pause</span>
          </button>
        ) : null}

        {paused ? (
          <button type="button" onClick={resume} aria-label="Resume reading" className={btn}>
            <span aria-hidden="true">▶</span>
            <span>Resume</span>
          </button>
        ) : null}

        {speaking || paused ? (
          <button type="button" onClick={stop} aria-label="Stop reading" className={btn}>
            <span aria-hidden="true">⏹</span>
            <span>Stop</span>
          </button>
        ) : null}
      </div>
      <p id={statusId} className="sr-only" aria-live="polite">
        {speaking ? "Reading aloud" : paused ? "Reading paused" : "Not reading"}
      </p>
    </div>
  );
}
