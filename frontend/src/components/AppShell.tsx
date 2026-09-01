"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useBusiness } from "@/lib/business-context";
import { isPublicPath } from "@/lib/session";

const NAV: { href: string; label: string }[] = [
  { href: "/dashboard", label: "Home" },
  { href: "/data", label: "Business data" },
  { href: "/chat", label: "Ask a question" },
  { href: "/goals", label: "Goals" },
  { href: "/decision", label: "Analyze a decision" },
  { href: "/simulation", label: "Simulator" },
  { href: "/causal-graph", label: "Cause & effect" },
  { href: "/history", label: "Decision history" },
];

/** Full-bleed routes that render without the workspace shell. */
const BARE_PATHS = ["/onboarding"];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, isAdmin, logout } = useAuth();
  const { business, clearBusiness } = useBusiness();
  const [drawer, setDrawer] = useState(false);

  // Close the mobile drawer whenever the route changes.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot sync of an ephemeral UI flag to the current route
  useEffect(() => setDrawer(false), [pathname]);

  const bare =
    isPublicPath(pathname) || pathname.startsWith("/research") || BARE_PATHS.includes(pathname) || !user;

  if (bare) return <>{children}</>;

  const nav = (
    <nav className="flex flex-1 flex-col gap-0.5" aria-label="Workspace">
      {NAV.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
              active
                ? "bg-accent-soft text-accent"
                : "text-muted hover:bg-muted-surface hover:text-foreground"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
      {isAdmin ? (
        <Link
          href="/research"
          className={`mt-1 rounded-lg px-3 py-2 text-sm font-medium transition ${
            pathname.startsWith("/research")
              ? "bg-accent-soft text-accent"
              : "text-muted hover:bg-muted-surface hover:text-foreground"
          }`}
        >
          Research console
        </Link>
      ) : null}
    </nav>
  );

  const sidebarBody = (
    <div className="flex h-full flex-col gap-4 p-4">
      <div>
        <Link href="/dashboard" className="text-base font-semibold tracking-tight text-foreground">
          DecisionGPT
        </Link>
        <div className="mt-3 rounded-lg border border-border bg-surface px-3 py-2">
          <p className="truncate text-sm font-medium text-foreground">
            {business?.name ?? "No workspace yet"}
          </p>
          <p className="truncate text-xs text-muted">
            {business ? `${business.industry} · ${business.business_type}` : "Set up your business"}
          </p>
          {business ? (
            <Link
              href="/"
              onClick={() => clearBusiness()}
              className="mt-1 inline-block text-xs text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
            >
              Switch workspace
            </Link>
          ) : (
            <Link
              href="/onboarding"
              className="mt-1 inline-block text-xs font-medium text-accent underline underline-offset-4"
            >
              Set up now
            </Link>
          )}
        </div>
      </div>
      {nav}
      <div className="border-t border-border pt-3">
        <p className="truncate px-3 text-xs text-muted">{user?.email}</p>
        <div className="mt-1 flex items-center justify-between px-3">
          <span className="rounded-full bg-muted-surface px-2 py-0.5 text-xs font-medium capitalize text-muted">
            {isAdmin ? "Admin" : "Business user"}
          </span>
          <button
            onClick={logout}
            className="rounded-md px-2 py-1 text-xs font-medium text-muted underline decoration-dotted underline-offset-4 hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-background">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-border bg-muted-surface/40 lg:block">
        {sidebarBody}
      </aside>

      {/* Mobile drawer */}
      {drawer ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-foreground/30"
            onClick={() => setDrawer(false)}
            aria-hidden="true"
          />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-border bg-surface shadow-xl">
            {sidebarBody}
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-3 lg:hidden">
          <button
            onClick={() => setDrawer(true)}
            aria-label="Open navigation menu"
            className="inline-flex min-h-[40px] min-w-[40px] items-center justify-center rounded-lg border border-border text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
          >
            <span aria-hidden="true">☰</span>
          </button>
          <span className="truncate text-sm font-semibold text-foreground">
            {business?.name ?? "DecisionGPT"}
          </span>
        </header>

        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
