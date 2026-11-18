import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "@/lib/api";
import {
  BUSINESS_STORAGE_KEY,
  RESEARCH_TOKEN_STORAGE_KEY,
  VOICE_LANG_STORAGE_KEY,
  clearClientSession,
  isPublicPath,
} from "@/lib/session";

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});
afterEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("clearClientSession", () => {
  it("removes the auth token, business id and research token", () => {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, "jwt");
    window.localStorage.setItem(BUSINESS_STORAGE_KEY, "biz-1");
    window.sessionStorage.setItem(RESEARCH_TOKEN_STORAGE_KEY, "rt");

    clearClientSession();

    expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull();
    expect(window.localStorage.getItem(BUSINESS_STORAGE_KEY)).toBeNull();
    expect(window.sessionStorage.getItem(RESEARCH_TOKEN_STORAGE_KEY)).toBeNull();
  });

  it("keeps the voice-language UI preference (not account data)", () => {
    window.localStorage.setItem(VOICE_LANG_STORAGE_KEY, "hi");
    clearClientSession();
    expect(window.localStorage.getItem(VOICE_LANG_STORAGE_KEY)).toBe("hi");
  });

  it("is safe to call with nothing stored", () => {
    expect(() => clearClientSession()).not.toThrow();
  });
});

describe("isPublicPath", () => {
  it("only / and /login are public", () => {
    expect(isPublicPath("/")).toBe(true);
    expect(isPublicPath("/login")).toBe(true);
    expect(isPublicPath("/dashboard")).toBe(false);
    expect(isPublicPath("/goals")).toBe(false);
    expect(isPublicPath("/research")).toBe(false);
  });
});
