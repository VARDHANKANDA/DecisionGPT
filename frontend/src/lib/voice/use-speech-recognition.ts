"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  getSpeechRecognition,
  normalizeRecognitionError,
  type NormalizedVoiceError,
} from "@/lib/voice/support";

export type RecognitionStatus =
  | "unsupported"
  | "idle"
  | "listening"
  | "denied"
  | "error";

export interface UseSpeechRecognitionOptions {
  locale: string;
  /** Called once per completed recognition with the best final transcript. */
  onResult: (transcript: string) => void;
  onError?: (error: NormalizedVoiceError) => void;
  /** Auto-stop after this many ms of listening with no final result. */
  timeoutMs?: number;
}

export interface UseSpeechRecognitionValue {
  status: RecognitionStatus;
  error: NormalizedVoiceError | null;
  /** Live partial transcript while listening (may be empty). */
  interim: string;
  supported: boolean;
  start: () => void;
  stop: () => void;
}

/**
 * Thin, SSR-safe wrapper around the browser SpeechRecognition API.
 * No audio is captured, retained or uploaded by this code — the browser owns
 * the microphone and (on some browsers) the transcription service. See
 * docs/VOICE_ACCESSIBILITY.md.
 */
export function useSpeechRecognition({
  locale,
  onResult,
  onError,
  timeoutMs = 15000,
}: UseSpeechRecognitionOptions): UseSpeechRecognitionValue {
  const Ctor = getSpeechRecognition();
  const supported = Ctor !== null;

  const [status, setStatus] = useState<RecognitionStatus>(supported ? "idle" : "unsupported");
  const [error, setError] = useState<NormalizedVoiceError | null>(null);
  const [interim, setInterim] = useState("");

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const gotResultRef = useRef(false);
  const erroredRef = useRef(false);
  const userStoppedRef = useRef(false);

  // Keep the latest callbacks without re-subscribing recognition handlers.
  const onResultRef = useRef(onResult);
  const onErrorRef = useRef(onError);
  useEffect(() => {
    onResultRef.current = onResult;
    onErrorRef.current = onError;
  }, [onResult, onError]);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stop = useCallback(() => {
    clearTimer();
    const rec = recognitionRef.current;
    if (rec) {
      userStoppedRef.current = true; // a manual stop is not a "no speech" error
      try {
        rec.stop();
      } catch {
        // already stopped
      }
    }
  }, [clearTimer]);

  const emitError = useCallback((raw: unknown) => {
    if (erroredRef.current) return;
    erroredRef.current = true;
    const normalized = normalizeRecognitionError(raw);
    setError(normalized);
    setStatus(normalized.kind === "permission-denied" ? "denied" : "error");
    setInterim("");
    onErrorRef.current?.(normalized);
  }, []);

  const start = useCallback(() => {
    if (!Ctor) {
      emitError("unsupported");
      return;
    }
    // Already listening — ignore.
    if (recognitionRef.current) return;

    setError(null);
    setInterim("");
    gotResultRef.current = false;
    erroredRef.current = false;
    userStoppedRef.current = false;

    let rec: SpeechRecognition;
    try {
      rec = new Ctor();
    } catch {
      emitError("unknown");
      return;
    }
    rec.lang = locale;
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
      setStatus("listening");
    };

    rec.onresult = (event: SpeechRecognitionEvent) => {
      let finalText = "";
      let partial = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const alt = result[0];
        if (!alt) continue;
        if (result.isFinal) finalText += alt.transcript;
        else partial += alt.transcript;
      }
      if (partial) setInterim(partial.trim());
      if (finalText.trim()) {
        gotResultRef.current = true;
        setInterim("");
        onResultRef.current(finalText.trim());
      }
    };

    rec.onerror = (event: SpeechRecognitionErrorEvent) => {
      emitError(event);
    };

    rec.onend = () => {
      clearTimer();
      recognitionRef.current = null;
      setInterim("");
      if (erroredRef.current) return; // an error handler already set the state
      if (userStoppedRef.current) {
        // manual cancellation — quietly return to idle, no error message
        setStatus("idle");
        return;
      }
      if (!gotResultRef.current) {
        emitError("no-speech");
        return;
      }
      setStatus("idle");
    };

    try {
      rec.start();
    } catch {
      recognitionRef.current = null;
      emitError("unknown");
      return;
    }
    recognitionRef.current = rec;
    setStatus("listening");

    clearTimer();
    timerRef.current = setTimeout(() => {
      if (!gotResultRef.current) {
        emitError("timeout"); // set the reason before abort() triggers onend
        try {
          rec.abort();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
    }, timeoutMs);
  }, [Ctor, locale, timeoutMs, emitError, clearTimer]);

  // Tear down on unmount / navigation.
  useEffect(() => {
    return () => {
      clearTimer();
      const rec = recognitionRef.current;
      if (rec) {
        try {
          rec.abort();
        } catch {
          // ignore
        }
        recognitionRef.current = null;
      }
    };
  }, [clearTimer]);

  return { status, error, interim, supported, start, stop };
}
