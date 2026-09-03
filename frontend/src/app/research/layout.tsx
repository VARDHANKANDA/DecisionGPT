"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

const RESEARCH_NAV = [
  { href: "/research", label: "Overview" },
  { href: "/research/model-performance", label: "Model Performance" },
  { href: "/research/agent-evaluation", label: "Architecture Evaluation" },
  { href: "/research/ablation", label: "Ablation" },
  { href: "/research/risk-calibration", label: "Risk Calibration" },
  { href: "/research/validation", label: "Validation" },
  { href: "/research/experiments", label: "Reproducibility" },
  { href: "/research/limitations", label: "Limitations" },
];

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAdmin, loading, logout } = useAuth();

  useEffect(() => {
    if (loading) return;
    // No manual access token. Research access is the signed-in admin session.
    if (!user) {
      router.replace(`/login?role=admin&next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, user, pathname, router]);

  if (loading) return null;

  if (!user) return null; // redirecting to admin sign-in

  if (!isAdmin) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6 text-center">
        <h1 className="text-lg font-semibold text-foreground">Research Console</h1>
        <p className="mt-2 text-sm text-muted">
          Access denied — administrator / research access is required. Your account is a business
          account.
        </p>
        <Link
          href="/dashboard"
          className="mt-6 text-sm font-medium text-accent underline underline-offset-4"
        >
          Go to your workspace
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col border-r border-border bg-muted-surface/30 lg:flex">
        <div className="border-b border-border p-4">
          <p className="text-base font-semibold tracking-tight text-foreground">Research Console</p>
          <p className="mt-0.5 text-xs text-muted">Controlled Evaluation &amp; Evidence</p>
        </div>
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto p-3" aria-label="Research Console">
          {RESEARCH_NAV.map((link) => {
            const active =
              pathname === link.href || (link.href !== "/research" && pathname.startsWith(link.href));
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-2 text-sm transition ${
                  active
                    ? "bg-accent-soft font-medium text-accent"
                    : "text-muted hover:bg-muted-surface hover:text-foreground"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border p-3 text-xs text-muted">
          <div className="flex items-center justify-between px-1">
            <p className="truncate">{user.email}</p>
            <span className="ml-2 shrink-0 rounded-full bg-muted-surface px-2 py-0.5 font-medium">admin</span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <Link href="/dashboard" className="underline decoration-dotted underline-offset-4 hover:text-foreground">
              SME app
            </Link>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-border px-3 py-1.5 font-medium text-foreground transition hover:bg-muted-surface"
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <div className="lg:pl-60">
        {/* mobile bar */}
        <header className="sticky top-0 z-10 flex items-center gap-3 overflow-x-auto border-b border-border bg-surface px-4 py-2 lg:hidden">
          {RESEARCH_NAV.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`shrink-0 rounded-full px-3 py-1.5 text-xs font-medium ${
                pathname === link.href ? "bg-accent-soft text-accent" : "text-muted"
              }`}
            >
              {link.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={logout}
            className="ml-auto shrink-0 rounded-full border border-border px-3 py-1.5 text-xs font-medium text-foreground"
          >
            Sign out
          </button>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
      </div>
    </div>
  );
}
