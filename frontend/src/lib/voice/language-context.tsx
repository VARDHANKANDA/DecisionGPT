"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  DEFAULT_VOICE_LANG,
  isVoiceLangCode,
  resolveLocale,
  type VoiceLangCode,
} from "@/lib/voice/locales";

const STORAGE_KEY = "decisiongpt.voice_lang";

interface VoiceLanguageValue {
  lang: VoiceLangCode;
  /** BCP-47 tag for SpeechRecognition / SpeechSynthesis. */
  locale: string;
  setLang: (code: VoiceLangCode) => void;
}

const VoiceLanguageContext = createContext<VoiceLanguageValue | null>(null);

export function VoiceLanguageProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<VoiceLangCode>(DEFAULT_VOICE_LANG);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot hydrate of a stored preference on mount
    if (isVoiceLangCode(stored)) setLangState(stored);
  }, []);

  const setLang = useCallback((code: VoiceLangCode) => {
    setLangState(code);
    try {
      window.localStorage.setItem(STORAGE_KEY, code);
    } catch {
      // storage unavailable (private mode etc.) — keep the in-memory value
    }
  }, []);

  return (
    <VoiceLanguageContext.Provider value={{ lang, locale: resolveLocale(lang), setLang }}>
      {children}
    </VoiceLanguageContext.Provider>
  );
}

/** Read the preferred voice language. Falls back to the default when no
 *  provider is present, so components stay usable in isolation / tests. */
export function useVoiceLanguage(): VoiceLanguageValue {
  const ctx = useContext(VoiceLanguageContext);
  if (ctx) return ctx;
  return { lang: DEFAULT_VOICE_LANG, locale: resolveLocale(DEFAULT_VOICE_LANG), setLang: () => {} };
}
