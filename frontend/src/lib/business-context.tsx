"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { Business } from "@/lib/api";
import { api } from "@/lib/api";

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

  const loadFromStorage = useCallback(async (signal?: { cancelled: boolean }) => {
    const id = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
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
      window.localStorage.removeItem(STORAGE_KEY);
      if (!signal?.cancelled) setBusiness(null);
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
  }, [loadFromStorage]);

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
