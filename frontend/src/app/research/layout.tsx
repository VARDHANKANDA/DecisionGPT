"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { clearResearchToken, getResearchToken, researchApi, setResearchToken } from "@/lib/research-api";

const RESEARCH_NAV = [
  { href: "/research", label: "Overview" },
  { href: "/research/datasets", label: "Datasets" },
  { href: "/research/models", label: "Models" },
  { href: "/research/experiments", label: "Experiments" },
  { href: "/research/export", label: "Export" },
];

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [hasToken, setHasToken] = useState<boolean | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    // sessionStorage isn't available during SSR, so this must run after
    // mount — starting from hasToken=null (which renders nothing) avoids a
    // hydration mismatch between server and client output.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHasToken(Boolean(getResearchToken()));
  }, []);

  async function submitToken(e: React.FormEvent) {
    e.preventDefault();
    setChecking(true);
    setError(null);
    setResearchToken(input.trim());
    try {
      await researchApi.listDatasets();
      setHasToken(true);
    } catch {
      clearResearchToken();
      setError("That token was rejected. Check RESEARCH_CONSOLE_TOKEN in the backend environment.");
      setHasToken(false);
    } finally {
      setChecking(false);
    }
  }

  if (hasToken === null) return null;

  if (!hasToken) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6">
        <h1 className="text-lg font-semibold text-foreground">Research Console</h1>
        <p className="mt-1 text-sm text-muted">
          Platform-administrator only. Not part of the SME application.
        </p>
        <form onSubmit={submitToken} className="mt-6 flex flex-col gap-3">
          <input
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
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-6 py-4">
          <div className="flex min-w-0 items-center gap-6">
            <span className="shrink-0 text-sm font-semibold tracking-tight text-foreground">DecisionGPT Research</span>
            <nav className="flex items-center gap-1 overflow-x-auto">
              {RESEARCH_NAV.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
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
          <button
            onClick={() => {
              clearResearchToken();
              setHasToken(false);
            }}
            className="text-sm text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
          >
            Lock
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
    </div>
  );
}
