"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { Card, PageHeader, PrimaryButton } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password, fullName || undefined);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-sm px-6 py-20">
      <PageHeader
        title={mode === "login" ? "Sign in" : "Create an account"}
        subtitle="Your business data is private to your account."
      />
      <Card>
        <form onSubmit={submit} className="flex flex-col gap-4">
          {mode === "register" ? (
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="font-medium text-foreground">Name</span>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} className="input" />
            </label>
          ) : null}
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="font-medium text-foreground">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
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
              className="input"
            />
          </label>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <PrimaryButton type="submit" disabled={busy || !email || password.length < 8}>
            {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
          </PrimaryButton>
        </form>
        <button
          onClick={() => setMode(mode === "login" ? "register" : "login")}
          className="mt-4 text-sm text-accent underline underline-offset-4"
        >
          {mode === "login" ? "Need an account? Register" : "Already have an account? Sign in"}
        </button>
      </Card>
    </div>
  );
}
