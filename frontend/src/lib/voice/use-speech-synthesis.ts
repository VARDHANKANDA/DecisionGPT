"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { isSpeechSynthesisSupported, pickVoice, sanitizeForSpeech } from "@/lib/voice/support";

export type SpeechStatus = "unsupported" | "idle" | "speaking" | "paused" | "error";

export interface UseSpeechSynthesisValue {
  status: SpeechStatus;
  supported: boolean;
  /** Speak the given text (sanitised first). No-op if nothing to say. */
  speak: (text: string, locale: string) => void;
  pause: () => void;
  resume: () => void;
  stop: () => void;
}

/**
 * SSR-safe wrapper around window.speechSynthesis. Text is sanitised
 * (sanitizeForSpeech) before it is spoken so tokens / ids are never read
 * aloud (task §11). Output is strictly caller-initiated — nothing autoplays.
 */
export function useSpeechSynthesis(): UseSpeechSynthesisValue {
  const supported = isSpeechSynthesisSupported();
  const [status, setStatus] = useState<SpeechStatus>(supported ? "idle" : "unsupported");
  const voicesRef = useRef<SpeechSynthesisVoice[]>([]);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  useEffect(() => {
    if (!supported) return;
    const synth = window.speechSynthesis;
    const load = () => {
      voicesRef.current = synth.getVoices();
    };
    load();
    synth.addEventListener?.("voiceschanged", load);
    return () => {
      synth.removeEventListener?.("voiceschanged", load);
      synth.cancel();
    };
  }, [supported]);

  const stop = useCallback(() => {
    if (!supported) return;
    window.speechSynthesis.cancel();
    utteranceRef.current = null;
    setStatus("idle");
  }, [supported]);

  const speak = useCallback(
    (text: string, locale: string) => {
      if (!supported) {
        setStatus("unsupported");
        return;
      }
      const clean = sanitizeForSpeech(text);
      if (!clean) return;

      const synth = window.speechSynthesis;
      synth.cancel(); // never queue on top of a previous read

      const utt = new SpeechSynthesisUtterance(clean);
      utt.lang = locale;
      const voice = pickVoice(voicesRef.current, locale);
      if (voice) utt.voice = voice;
      utt.onend = () => {
        utteranceRef.current = null;
        setStatus("idle");
      };
      utt.onerror = () => {
        utteranceRef.current = null;
        setStatus("error");
      };
      utteranceRef.current = utt;
      setStatus("speaking");
      synth.speak(utt);
    },
    [supported],
  );

  const pause = useCallback(() => {
    if (!supported) return;
    window.speechSynthesis.pause();
    setStatus("paused");
  }, [supported]);

  const resume = useCallback(() => {
    if (!supported) return;
    window.speechSynthesis.resume();
    setStatus("speaking");
  }, [supported]);

  useEffect(() => {
    return () => {
      // Re-check liveness at teardown — the API can disappear (e.g. under test).
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  return { status, supported, speak, pause, resume, stop };
}
