"use client";

import { useVoiceLanguage } from "@/lib/voice/language-context";
import { VOICE_LANGS, type VoiceLangCode } from "@/lib/voice/locales";

/**
 * Language picker for the voice layer. Controls the speech-recognition and
 * speech-output locale only — it does not translate the interface.
 */
export function VoiceLanguagePicker({ className = "" }: { className?: string }) {
  const { lang, setLang } = useVoiceLanguage();

  return (
    <fieldset className={`flex flex-wrap items-center gap-2 ${className}`}>
      <legend className="text-xs font-medium text-muted">Voice language</legend>
      {VOICE_LANGS.map((l) => {
        const selected = l.code === lang;
        return (
          <button
            key={l.code}
            type="button"
            aria-pressed={selected}
            onClick={() => setLang(l.code as VoiceLangCode)}
            className={`min-h-[40px] rounded-full border px-4 py-2 text-sm font-medium transition ${
              selected
                ? "border-accent bg-accent-soft text-accent"
                : "border-border text-muted hover:bg-muted-surface hover:text-foreground"
            }`}
          >
            <span lang={l.code}>{l.nativeName}</span>
            <span className="sr-only"> ({l.englishName}){selected ? ", selected" : ""}</span>
          </button>
        );
      })}
    </fieldset>
  );
}
