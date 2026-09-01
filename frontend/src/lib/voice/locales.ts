// Language-aware configuration for the voice accessibility layer.
//
// This is NOT an app-wide i18n system (the app has none — see
// docs/VOICE_ACCESSIBILITY.md). It only selects the BCP-47 locale used for
// browser speech recognition and speech synthesis. App copy stays English.
//
// Recognition/synthesis quality is NOT equivalent across these languages and
// depends entirely on the user's browser/OS. Callers must surface that.

export type VoiceLangCode = "en" | "hi" | "ta";

export interface VoiceLangDef {
  code: VoiceLangCode;
  /** BCP-47 tag handed to SpeechRecognition.lang / SpeechSynthesisUtterance.lang */
  locale: string;
  /** Name in the language itself, for the language picker */
  nativeName: string;
  /** Name in English, for the accessible label */
  englishName: string;
}

export const VOICE_LANGS: readonly VoiceLangDef[] = [
  { code: "en", locale: "en-IN", nativeName: "English", englishName: "English" },
  { code: "hi", locale: "hi-IN", nativeName: "हिन्दी", englishName: "Hindi" },
  { code: "ta", locale: "ta-IN", nativeName: "தமிழ்", englishName: "Tamil" },
];

export const DEFAULT_VOICE_LANG: VoiceLangCode = "en";

export function isVoiceLangCode(value: unknown): value is VoiceLangCode {
  return value === "en" || value === "hi" || value === "ta";
}

export function langDef(code: VoiceLangCode): VoiceLangDef {
  return VOICE_LANGS.find((l) => l.code === code) ?? VOICE_LANGS[0];
}

/** BCP-47 locale for a language code (e.g. "hi" -> "hi-IN"). */
export function resolveLocale(code: VoiceLangCode): string {
  return langDef(code).locale;
}
