// Framework-free helpers for the voice layer. Pure functions only — no React,
// no side effects — so they are unit-testable without a DOM renderer.

export type VoiceErrorKind =
  | "unsupported"
  | "permission-denied"
  | "no-speech"
  | "no-microphone"
  | "network"
  | "language-not-supported"
  | "aborted"
  | "timeout"
  | "unknown";

export interface NormalizedVoiceError {
  kind: VoiceErrorKind;
  /** Plain-language message safe to show a non-technical user. */
  message: string;
}

/** The browser's SpeechRecognition constructor, or null when unsupported.
 *  Accepts an explicit window for testing; defaults to the global. */
export function getSpeechRecognition(
  win: (Window & typeof globalThis) | undefined = typeof window !== "undefined" ? window : undefined,
): SpeechRecognitionConstructor | null {
  if (!win) return null;
  return win.SpeechRecognition ?? win.webkitSpeechRecognition ?? null;
}

export function isSpeechRecognitionSupported(
  win: (Window & typeof globalThis) | undefined = typeof window !== "undefined" ? window : undefined,
): boolean {
  return getSpeechRecognition(win) !== null;
}

export function isSpeechSynthesisSupported(
  win: (Window & typeof globalThis) | undefined = typeof window !== "undefined" ? window : undefined,
): boolean {
  return !!win && "speechSynthesis" in win && typeof win.speechSynthesis?.speak === "function";
}

const MESSAGES: Record<VoiceErrorKind, string> = {
  unsupported: "Voice input isn't supported in this browser. You can type instead.",
  "permission-denied": "Microphone access is blocked. You can type instead.",
  "no-speech": "I didn't catch anything. Tap the microphone and try again, or type instead.",
  "no-microphone": "No microphone was found. You can type instead.",
  network: "Voice recognition needs a network connection and it isn't reachable right now. You can type instead.",
  "language-not-supported":
    "This browser can't recognise the selected language. Try English, another browser, or type instead.",
  aborted: "Voice input was stopped.",
  timeout: "Voice input timed out. Tap the microphone to try again, or type instead.",
  unknown: "Voice input didn't work this time. You can type instead.",
};

/** Map a raw SpeechRecognition error code (or arbitrary error) onto a
 *  user-facing, non-technical message. Never surfaces a raw exception string. */
export function normalizeRecognitionError(raw: unknown): NormalizedVoiceError {
  const code =
    typeof raw === "string"
      ? raw
      : raw && typeof raw === "object" && "error" in raw
        ? String((raw as { error: unknown }).error)
        : "";

  const kind: VoiceErrorKind =
    code === "not-allowed" || code === "service-not-allowed"
      ? "permission-denied"
      : code === "no-speech"
        ? "no-speech"
        : code === "audio-capture"
          ? "no-microphone"
          : code === "network"
            ? "network"
            : code === "language-not-supported"
              ? "language-not-supported"
              : code === "aborted"
                ? "aborted"
                : code === "timeout"
                  ? "timeout"
                  : code === "unsupported"
                    ? "unsupported"
                    : "unknown";

  return { kind, message: MESSAGES[kind] };
}

/** Choose the best installed synthesis voice for a locale.
 *  Exact match first, then language-prefix match, then null (browser default). */
export function pickVoice(
  voices: readonly SpeechSynthesisVoice[],
  locale: string,
): SpeechSynthesisVoice | null {
  if (voices.length === 0) return null;
  const target = locale.toLowerCase();
  const lang = target.split("-")[0];
  return (
    voices.find((v) => v.lang?.toLowerCase() === target) ??
    voices.find((v) => v.lang?.toLowerCase().startsWith(`${lang}-`)) ??
    voices.find((v) => v.lang?.toLowerCase() === lang) ??
    null
  );
}

// Tokens / identifiers we must never read aloud even if they somehow appear in
// a displayed string (defence-in-depth for VoiceOutput — see task §11).
const SENSITIVE_PATTERNS: RegExp[] = [
  /\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b/g, // UUID
  /\bBearer\s+[A-Za-z0-9._~+/-]+=*/gi, // bearer token
  /\beyJ[A-Za-z0-9._-]{10,}/g, // JWT-looking blob
  /\b(?:sk|pk|api|key|tok|token|secret|pwd|passwd)[-_][A-Za-z0-9][A-Za-z0-9_-]{5,}\b/gi, // key-ish
  /\b[A-Fa-f0-9]{32,}\b/g, // long hex ids / hashes
];

/** Strip anything token/key/id-shaped and collapse whitespace before speaking.
 *  Returns "" for empty / whitespace-only input. */
export function sanitizeForSpeech(text: string): string {
  let out = text ?? "";
  for (const re of SENSITIVE_PATTERNS) out = out.replace(re, " ");
  return out.replace(/\s+/g, " ").trim();
}
