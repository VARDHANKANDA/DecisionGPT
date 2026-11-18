"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Business } from "@/lib/api";
import { api, TOKEN_STORAGE_KEY } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

const STORAGE_KEY = "decisiongpt.business_id";

interface BusinessContextValue {
  business: Business | null;
  loading: boolean;
  setBusinessId: (id: string) => void;
  clearBusiness: () => void;
  refresh: () => Promise<void>;
}

const BusinessContext = createContext<BusinessContextValue | null>(null);

export function BusinessProvider({ children }: { children: React.ReactNode }) {
  const [business, setBusiness] = useState<Business | null>(null);
  const [loading, setLoading] = useState(true);
  const { user } = useAuth();
  const userId = user?.id ?? null;

  const loadFromStorage = useCallback(async (signal?: { cancelled: boolean }) => {
    let id = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    const signedIn = typeof window !== "undefined" && !!window.localStorage.getItem(TOKEN_STORAGE_KEY);
    if (!id && signedIn) {
      // A returning user on a new browser: find the business they own.
      try {
        const mine = await api.myBusinesses();
        if (mine.length > 0) {
          id = mine[0].id;
          window.localStorage.setItem(STORAGE_KEY, id);
        }
      } catch {
        // fall through to the "set up your business" state
      }
    }
    if (!id) {
      if (!signal?.cancelled) {
        setBusiness(null);
        setLoading(false);
      }
      return;
    }
    try {
      const fetched = await api.getBusiness(id);
      if (!signal?.cancelled) setBusiness(fetched);
    } catch {
      // The remembered business isn't reachable (e.g. it belongs to someone who used this browser before).
      window.localStorage.removeItem(STORAGE_KEY);
      let own: Business | null = null;
      if (signedIn) {
        try {
          own = (await api.myBusinesses())[0] ?? null;
          if (own) window.localStorage.setItem(STORAGE_KEY, own.id);
        } catch {
          own = null;
        }
      }
      if (!signal?.cancelled) setBusiness(own);
    } finally {
      if (!signal?.cancelled) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const signal = { cancelled: false };
    // react-hooks/set-state-in-effect can't statically see the cancellation
    // guard inside loadFromStorage; this is the standard cancelled-flag
    // fetch-on-mount pattern, not an uncontrolled cascading render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadFromStorage(signal);
    return () => {
      signal.cancelled = true;
    };
    // Re-run when the signed-in user changes, so a fresh sign-in finds that user's own business.
  }, [loadFromStorage, userId]);

  const setBusinessId = useCallback((id: string) => {
    window.localStorage.setItem(STORAGE_KEY, id);
    setLoading(true);
    api
      .getBusiness(id)
      .then(setBusiness)
      .finally(() => setLoading(false));
  }, []);

  const clearBusiness = useCallback(() => {
    window.localStorage.removeItem(STORAGE_KEY);
    setBusiness(null);
  }, []);

  return (
    <BusinessContext.Provider value={{ business, loading, setBusinessId, clearBusiness, refresh: loadFromStorage }}>
      {children}
    </BusinessContext.Provider>
  );
}

export function useBusiness() {
  const ctx = useContext(BusinessContext);
  if (!ctx) throw new Error("useBusiness must be used within a BusinessProvider");
  return ctx;
}
