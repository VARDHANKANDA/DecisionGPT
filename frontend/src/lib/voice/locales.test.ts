import { describe, expect, it } from "vitest";
import {
  DEFAULT_VOICE_LANG,
  isVoiceLangCode,
  langDef,
  resolveLocale,
  VOICE_LANGS,
} from "@/lib/voice/locales";

describe("voice locales", () => {
  it("offers English, Hindi and Tamil", () => {
    expect(VOICE_LANGS.map((l) => l.code)).toEqual(["en", "hi", "ta"]);
  });

  it("maps each language to an Indian BCP-47 locale", () => {
    expect(resolveLocale("en")).toBe("en-IN");
    expect(resolveLocale("hi")).toBe("hi-IN");
    expect(resolveLocale("ta")).toBe("ta-IN");
  });

  it("defaults to English", () => {
    expect(DEFAULT_VOICE_LANG).toBe("en");
  });

  it("validates language codes", () => {
    expect(isVoiceLangCode("hi")).toBe(true);
    expect(isVoiceLangCode("fr")).toBe(false);
    expect(isVoiceLangCode(null)).toBe(false);
    expect(isVoiceLangCode(undefined)).toBe(false);
  });

  it("falls back to English for an unknown code", () => {
    // @ts-expect-error deliberately invalid
    expect(langDef("xx").code).toBe("en");
  });

  it("exposes native and English names for the picker", () => {
    expect(langDef("hi").nativeName).toBe("हिन्दी");
    expect(langDef("ta").nativeName).toBe("தமிழ்");
    expect(langDef("hi").englishName).toBe("Hindi");
  });
});
