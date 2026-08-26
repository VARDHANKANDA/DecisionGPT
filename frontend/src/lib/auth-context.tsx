"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, TOKEN_STORAGE_KEY, type AuthUser } from "@/lib/api";

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Standard fetch-on-mount: hydrate the session from a stored token.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_STORAGE_KEY) : null;
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setLoading(false);
      return;
    }
    let cancelled = false;
    api
      .me()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => window.localStorage.removeItem(TOKEN_STORAGE_KEY))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.login({ email, password });
    window.localStorage.setItem(TOKEN_STORAGE_KEY, res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    const res = await api.register({ email, password, full_name: fullName });
    window.localStorage.setItem(TOKEN_STORAGE_KEY, res.access_token);
    setUser(res.user);
  }, []);

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
