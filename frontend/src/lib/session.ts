// Central list of every browser-storage key that holds account-scoped state,
// plus a single helper to wipe them on sign-out. Keeping this in one place
// means "log out" can never leave a stale business id / research token behind.

import { TOKEN_STORAGE_KEY } from "@/lib/api";

export const BUSINESS_STORAGE_KEY = "decisiongpt.business_id";
export const RESEARCH_TOKEN_STORAGE_KEY = "decisiongpt.research_token";
export const VOICE_LANG_STORAGE_KEY = "decisiongpt.voice_lang";

/** Remove all account-scoped client state. Safe to call anywhere. */
export function clearClientSession(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    window.localStorage.removeItem(BUSINESS_STORAGE_KEY);
    window.sessionStorage.removeItem(RESEARCH_TOKEN_STORAGE_KEY);
    // Voice language is a UI preference, not account data — keep it.
  } catch {
    // storage unavailable (private mode) — nothing to clear
  }
}

/** Public routes that never require an authenticated session. */
export const PUBLIC_PATHS: readonly string[] = ["/", "/login"];

export function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.includes(pathname);
}
