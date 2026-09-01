import { describe, expect, it } from "vitest";
import {
  getSpeechRecognition,
  isSpeechRecognitionSupported,
  isSpeechSynthesisSupported,
  normalizeRecognitionError,
  pickVoice,
  sanitizeForSpeech,
} from "@/lib/voice/support";

describe("speech recognition support detection", () => {
  it("reports unsupported when no constructor exists", () => {
    const win = {} as Window & typeof globalThis;
    expect(getSpeechRecognition(win)).toBeNull();
    expect(isSpeechRecognitionSupported(win)).toBe(false);
  });

  it("finds the prefixed constructor", () => {
    const Ctor = function () {} as unknown as SpeechRecognitionConstructor;
    const win = { webkitSpeechRecognition: Ctor } as unknown as Window & typeof globalThis;
    expect(getSpeechRecognition(win)).toBe(Ctor);
    expect(isSpeechRecognitionSupported(win)).toBe(true);
  });

  it("handles a missing window (SSR)", () => {
    expect(getSpeechRecognition(undefined)).toBeNull();
    expect(isSpeechSynthesisSupported(undefined)).toBe(false);
  });
});

describe("normalizeRecognitionError", () => {
  it("maps permission codes to a type-instead message", () => {
    for (const code of ["not-allowed", "service-not-allowed"]) {
      const err = normalizeRecognitionError({ error: code });
      expect(err.kind).toBe("permission-denied");
      expect(err.message).toMatch(/type instead/i);
    }
  });

  it("maps audio-capture to no-microphone", () => {
    expect(normalizeRecognitionError({ error: "audio-capture" }).kind).toBe("no-microphone");
  });

  it("maps no-speech, network, language-not-supported, timeout, unsupported", () => {
    expect(normalizeRecognitionError("no-speech").kind).toBe("no-speech");
    expect(normalizeRecognitionError("network").kind).toBe("network");
    expect(normalizeRecognitionError("language-not-supported").kind).toBe("language-not-supported");
    expect(normalizeRecognitionError("timeout").kind).toBe("timeout");
    expect(normalizeRecognitionError("unsupported").kind).toBe("unsupported");
  });

  it("never surfaces a raw exception string", () => {
    const err = normalizeRecognitionError(new Error("TypeError: cannot read x of undefined"));
    expect(err.kind).toBe("unknown");
    expect(err.message).not.toMatch(/TypeError|undefined/);
  });
});

describe("pickVoice", () => {
  const v = (lang: string): SpeechSynthesisVoice => ({ lang }) as SpeechSynthesisVoice;

  it("returns null when there are no voices", () => {
    expect(pickVoice([], "hi-IN")).toBeNull();
  });

  it("prefers an exact locale match", () => {
    const exact = v("hi-IN");
    expect(pickVoice([v("en-US"), exact, v("hi-Latn")], "hi-IN")).toBe(exact);
  });

  it("falls back to a language-prefix match", () => {
    const prefix = v("ta-LK");
    expect(pickVoice([v("en-GB"), prefix], "ta-IN")).toBe(prefix);
  });

  it("returns null (browser default) when nothing matches", () => {
    expect(pickVoice([v("en-US"), v("fr-FR")], "hi-IN")).toBeNull();
  });
});

describe("sanitizeForSpeech", () => {
  it("collapses whitespace and trims", () => {
    expect(sanitizeForSpeech("  hello   world \n")).toBe("hello world");
  });

  it("returns empty string for blank input", () => {
    expect(sanitizeForSpeech("   \n\t ")).toBe("");
  });

  it("strips UUIDs / ids", () => {
    const out = sanitizeForSpeech("Decision 3fa85f64-5717-4562-b3fc-2c963f66afa6 is ready");
    expect(out).not.toMatch(/3fa85f64/);
    expect(out).toContain("Decision");
    expect(out).toContain("is ready");
  });

  it("strips bearer tokens and JWT-like blobs", () => {
    expect(sanitizeForSpeech("token Bearer abc.def-123 done")).not.toMatch(/Bearer abc/);
    expect(sanitizeForSpeech("eyJhbGciOiJIUzI1NiIsɪnR5")).not.toMatch(/eyJhbGci/);
  });

  it("strips long hex hashes and key-shaped strings", () => {
    expect(sanitizeForSpeech("id deadbeefdeadbeefdeadbeefdeadbeef end")).not.toMatch(/deadbeef/);
    expect(sanitizeForSpeech("use sk_live_abcd1234efgh now")).not.toMatch(/sk_live_abcd1234/);
  });

  it("leaves ordinary recommendation text intact", () => {
    const text = "Recommended strategy: Marketing +20%. Risk level: LOW. Confidence 15 percent.";
    expect(sanitizeForSpeech(text)).toBe(text);
  });
});
