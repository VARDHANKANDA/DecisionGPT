"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import {
  clearResearchToken,
  getResearchToken,
  researchApi,
  setResearchToken,
} from "@/lib/research-api";

const RESEARCH_NAV = [
  { href: "/research", label: "Overview" },
  { href: "/research/agent-evaluation", label: "Architecture Evaluation" },
  { href: "/research/ablation", label: "Ablation" },
  { href: "/research/digital-twin-evaluation", label: "Digital Twin Evaluation" },
  { href: "/research/causal-evaluation", label: "Causal Graph Evaluation" },
  { href: "/research/model-performance", label: "Model Performance" },
  { href: "/research/datasets", label: "Datasets" },
  { href: "/research/experiments", label: "Experiments" },
  { href: "/research/export", label: "Paper Results" },
  { href: "/research/training", label: "Training Center" },
  { href: "/research/models", label: "Model Registry" },
];

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, isAdmin, loading } = useAuth();

  // `unlocked` = we have a working credential (admin session OR console token).
  const [unlocked, setUnlocked] = useState<boolean | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (loading) return;
    // one-shot: resolve access from the session (admin) or a stored console token
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setUnlocked(isAdmin || Boolean(getResearchToken()));
  }, [loading, isAdmin]);

  async function submitToken(e: React.FormEvent) {
    e.preventDefault();
    setChecking(true);
    setError(null);
    setResearchToken(input.trim());
    try {
      await researchApi.overview();
      setUnlocked(true);
    } catch {
      clearResearchToken();
      setError("That token was rejected. Check RESEARCH_CONSOLE_TOKEN in the backend environment.");
      setUnlocked(false);
    } finally {
      setChecking(false);
    }
  }

  if (loading || unlocked === null) return null;

  // A signed-in NON-admin user should never see a token box — they simply
  // don't have access. The backend enforces this regardless of the UI.
  if (!unlocked && user && !isAdmin) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6 text-center">
        <h1 className="text-lg font-semibold text-foreground">Research console</h1>
        <p className="mt-2 text-sm text-muted">
          This area is for platform administrators. Your account doesn&apos;t have research access.
        </p>
        <Link href="/dashboard" className="mt-6 text-sm font-medium text-accent underline underline-offset-4">
          Back to your workspace
        </Link>
      </div>
    );
  }

  if (!unlocked) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6">
        <h1 className="text-lg font-semibold text-foreground">Research console</h1>
        <p className="mt-1 text-sm text-muted">
          Sign in with an administrator account, or enter the console token (CI / scripts).
        </p>
        <form onSubmit={submitToken} className="mt-6 flex flex-col gap-3">
          <label htmlFor="research-token" className="text-sm font-medium text-foreground">
            Research console token
          </label>
          <input
            id="research-token"
            type="password"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Research console token"
            className="input"
            autoFocus
          />
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          <button
            type="submit"
            disabled={checking || !input}
            className="inline-flex items-center justify-center rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition hover:opacity-90 disabled:opacity-50"
          >
            {checking ? "Checking…" : "Enter"}
          </button>
          <Link href="/login" className="text-center text-sm text-accent underline underline-offset-4">
            Sign in instead
          </Link>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-4">
          <div className="flex min-w-0 items-center gap-6">
            <span className="shrink-0 text-sm font-semibold tracking-tight text-foreground">
              DecisionGPT Research
            </span>
            <nav className="flex items-center gap-1 overflow-x-auto" aria-label="Research console">
              {RESEARCH_NAV.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={pathname === link.href ? "page" : undefined}
                  className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    pathname === link.href
                      ? "bg-accent-soft text-accent"
                      : "text-muted hover:bg-muted-surface hover:text-foreground"
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="text-sm text-muted underline decoration-dotted underline-offset-4 hover:text-foreground">
              SME app
            </Link>
            {isAdmin ? (
              <span className="text-xs text-muted">Signed in as admin</span>
            ) : (
              <button
                onClick={() => {
                  clearResearchToken();
                  setUnlocked(false);
                }}
                className="text-sm text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
              >
                Lock
              </button>
            )}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}
