"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { clearClientSession } from "@/lib/session";

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const roleParam = params.get("role") === "admin" ? "admin" : "user";
  const next = params.get("next") || "";
  const { login, register } = useAuth();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isAdminEntry = roleParam === "admin";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const account =
        mode === "login"
          ? await login(email.trim(), password)
          : await register(email.trim(), password, fullName.trim() || undefined);

      if (isAdminEntry && account.role !== "admin") {
        // Signed in fine, but this is not a research account. Do not proceed
        // into the admin area — the server would reject it anyway.
        clearClientSession();
        setError("Access denied — administrator / research access is required for this account.");
        setBusy(false);
        return;
      }

      const dest = isAdminEntry
        ? "/research"
        : next.startsWith("/")
          ? next
          : account.role === "admin"
            ? "/research"
            : "/dashboard";
      router.replace(dest);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : mode === "login"
            ? "Could not sign you in. Check your email and password."
            : "Could not create your account. Please try again.",
      );
      setBusy(false);
    }
  }

  const canSubmit = /\S+@\S+\.\S+/.test(email) && password.length >= 8 && !busy;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6 py-16">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="text-lg font-semibold tracking-tight text-foreground">DecisionGPT</p>
          <p className="mt-1 text-sm text-muted">
            {isAdminEntry ? "Administrator / researcher sign-in" : "Decision support for your business"}
          </p>
        </div>

        <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
          {isAdminEntry ? (
            <p className="mb-5 rounded-lg bg-muted-surface px-3 py-2 text-xs text-muted">
              Research access is verified by your account role on the server. A business account cannot
              enter this area.
            </p>
          ) : (
            <div
              className="mb-5 flex rounded-lg bg-muted-surface p-1"
              role="tablist"
              aria-label="Authentication"
            >
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  role="tab"
                  aria-selected={mode === m}
                  onClick={() => {
                    setMode(m);
                    setError(null);
                  }}
                  className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
                    mode === m ? "bg-surface text-foreground shadow-sm" : "text-muted hover:text-foreground"
                  }`}
                >
                  {m === "login" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>
          )}

          <form onSubmit={submit} className="flex flex-col gap-4">
            {mode === "register" && !isAdminEntry ? (
              <label className="flex flex-col gap-1.5 text-sm">
                <span className="font-medium text-foreground">Your name</span>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  autoComplete="name"
                  className="input"
                />
              </label>
            ) : null}

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-foreground">Work email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                className="input"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-foreground">Password</span>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                className="input"
              />
              {mode === "register" && !isAdminEntry ? (
                <span className="text-xs text-muted">At least 8 characters.</span>
              ) : null}
            </label>

            {error ? (
              <p className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">
                {error}
              </p>
            ) : null}

            <button
              type="submit"
              disabled={!canSubmit}
              className="inline-flex items-center justify-center rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              {busy
                ? "Please wait…"
                : isAdminEntry
                  ? "Sign in to Research Console"
                  : mode === "login"
                    ? "Sign in"
                    : "Create account"}
            </button>
          </form>

          {!isAdminEntry ? (
            <p className="mt-4 text-center text-xs text-muted">
              {mode === "login"
                ? "Forgot your password? Password reset isn’t available yet — contact your administrator."
                : "You’ll get a private workspace for your business data."}
            </p>
          ) : null}
        </div>

        <p className="mt-6 text-center text-xs text-muted">
          <Link href="/" className="underline underline-offset-4 hover:text-foreground">
            ← Choose a different way to continue
          </Link>
        </p>
      </div>
    </div>
  );
}
