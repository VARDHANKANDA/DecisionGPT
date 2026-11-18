"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, TOKEN_STORAGE_KEY, type AuthUser } from "@/lib/api";
import { clearClientSession } from "@/lib/session";

interface AuthContextValue {
  user: AuthUser | null;
  /** True until the initial session check (token → /me) has resolved. */
  loading: boolean;
  isAdmin: boolean;
  isResearcher: boolean;
  canAccessResearch: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  register: (email: string, password: string, fullName?: string) => Promise<AuthUser>;
  logout: () => void;
  refreshUser: () => Promise<AuthUser | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_STORAGE_KEY) : null;
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot: no token → session check is done
      setLoading(false);
      return;
    }
    let cancelled = false;
    api
      .me()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        // token is stale/invalid — drop it so the app treats us as logged out
        clearClientSession();
      })
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
    return res.user;
  }, []);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    const res = await api.register({ email, password, full_name: fullName });
    window.localStorage.setItem(TOKEN_STORAGE_KEY, res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(() => {
    // 0: ask the server to refuse this token from now on. The request is sent (with the token) before local state is cleared and is
    // best-effort: if the network is down the local sign-out below still happens, and the token simply expires on its own.
    void api.logout().catch(() => undefined);
    // 1-3: clear the token + business id + research token from browser storage.
    clearClientSession();
    // 4: drop the in-memory user so no component keeps rendering with it.
    setUser(null);
    // 5-7: a full document navigation (not a client-side route change)
    // guarantees every provider re-initialises with no token — so refresh and
    // back-navigation both stay logged out and no protected page keeps its
    // previously-fetched data in memory. `replace` also drops the app URL from
    // history so Back can't return to it.
    if (typeof window !== "undefined") {
      window.location.replace("/login");
    }
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const u = await api.me();
      setUser(u);
      return u;
    } catch {
      return null;
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isAdmin: user?.role === "admin",
        isResearcher: user?.role === "researcher",
        canAccessResearch: user?.role === "admin" || user?.role === "researcher",
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
