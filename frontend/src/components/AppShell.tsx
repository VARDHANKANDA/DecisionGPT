"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useBusiness } from "@/lib/business-context";
import { isDemoBusiness } from "@/lib/demo";
import { NAV_ACCOUNT, NAV_GROUPS, type NavEntry } from "@/lib/features";
import { isPublicPath } from "@/lib/session";

/** Full-bleed routes that render without the workspace shell. */
const BARE_PATHS = ["/onboarding"];

/** The single nav entry that owns this route: the longest matching href (so /data/quality wins over /data). */
export function activeHref(pathname: string): string | null {
  const all: NavEntry[] = [...NAV_GROUPS.flatMap((g) => g.items), ...NAV_ACCOUNT];
  let best: { href: string; len: number } | null = null;
  for (const item of all) {
    for (const h of [item.href, ...(item.alsoActive ?? [])]) {
      if ((pathname === h || pathname.startsWith(`${h}/`)) && (!best || h.length > best.len)) best = { href: item.href, len: h.length };
    }
  }
  return best?.href ?? null;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, isAdmin, isResearcher, canAccessResearch, logout } = useAuth();
  const { business, clearBusiness } = useBusiness();
  const [drawer, setDrawer] = useState(false);
  const [closed, setClosed] = useState<Record<string, boolean>>({});

  // Close the mobile drawer whenever the route changes.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot sync of an ephemeral UI flag to the current route
  useEffect(() => setDrawer(false), [pathname]);

  const bare = isPublicPath(pathname) || pathname.startsWith("/research") || pathname.startsWith("/admin") || BARE_PATHS.includes(pathname) || !user;
  if (bare) return <>{children}</>;

  const demo = isDemoBusiness(business);
  const current = activeHref(pathname);

  const navLink = (item: NavEntry) => {
    const active = item.href === current;
    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={active ? "page" : undefined}
        className={`flex min-h-[36px] items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-sm transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent ${
          active ? "bg-accent-soft font-medium text-accent" : "text-foreground/80 hover:bg-muted-surface hover:text-foreground"
        }`}
      >
        <span aria-hidden="true" className="w-4 text-center text-sm">
          {item.icon}
        </span>
        <span className="min-w-0 truncate text-[13.5px]">{item.label}</span>
      </Link>
    );
  };

  const sidebarBody = (
    <div className="flex h-full flex-col">
      <div className="border-b border-border px-4 py-3.5">
        <Link href="/dashboard" className="text-base font-semibold tracking-tight text-foreground">
          DecisionGPT
        </Link>
        <p className="text-[11px] text-muted">AI business operating system</p>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto px-2.5 py-2" aria-label="Workspace">
        {NAV_GROUPS.map((g, gi) => {
          const holdsActive = g.items.some((i) => i.href === current);
          const isOpen = !g.heading || holdsActive || !closed[g.heading];
          return (
            <div key={gi} className={gi > 0 ? "mt-1.5" : undefined}>
              {g.heading ? (
                <button
                  type="button"
                  aria-expanded={isOpen}
                  onClick={() => setClosed((c) => ({ ...c, [g.heading!]: isOpen && !holdsActive }))}
                  className="flex w-full items-center justify-between rounded-md px-2.5 py-1 text-left text-[11px] font-semibold uppercase tracking-wider text-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"
                >
                  {g.heading}
                  <span aria-hidden="true" className="text-[10px]">{isOpen ? "▾" : "▸"}</span>
                </button>
              ) : null}
              {isOpen ? <div className="mt-0.5 flex flex-col gap-0.5">{g.items.map(navLink)}</div> : null}
            </div>
          );
        })}

        <div className="my-2 border-t border-border" />
        <p className="px-3 pb-1 text-xs font-semibold uppercase tracking-wide text-muted">Account</p>
        {NAV_ACCOUNT.map(navLink)}
        {isAdmin ? (
          <>
            <div className="my-2 border-t border-border" />
            <Link
              href="/admin"
              className="flex min-h-[40px] items-center gap-3 rounded-lg px-3 py-2 text-[15px] text-foreground/80 hover:bg-muted-surface hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"
            >
              <span aria-hidden="true" className="w-5 text-center">⚙️</span>
              Admin dashboard
            </Link>
          </>
        ) : null}
        {canAccessResearch || isAdmin ? (
          <>
            {!isAdmin ? <div className="my-2 border-t border-border" /> : null}
            <Link
              href="/research"
              className="flex min-h-[40px] items-center gap-3 rounded-lg px-3 py-2 text-[15px] text-foreground/80 hover:bg-muted-surface hover:text-foreground focus-visible:outline-2 focus-visible:outline-accent"
            >
              <span aria-hidden="true" className="w-5 text-center">🔬</span>
              Research console
            </Link>
          </>
        ) : null}
      </nav>
    </div>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop sidebar — fixed, full height, own scroll */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-border bg-muted-surface/30 lg:block">{sidebarBody}</aside>

      {/* Mobile drawer */}
      {drawer ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button className="absolute inset-0 h-full w-full bg-foreground/30" onClick={() => setDrawer(false)} aria-label="Close navigation menu" />
          <div className="absolute inset-y-0 left-0 w-72 max-w-[85vw] border-r border-border bg-surface shadow-xl">{sidebarBody}</div>
        </div>
      ) : null}

      <div className="flex min-h-screen flex-col lg:pl-64">
        {/* Top bar: workspace on the left, account on the right (desktop and mobile) */}
        <header className="sticky top-0 z-10 flex items-center gap-3 border-b border-border bg-surface px-4 py-2.5 sm:px-6">
          <button
            onClick={() => setDrawer(true)}
            aria-label="Open navigation menu"
            className="inline-flex min-h-[40px] min-w-[40px] items-center justify-center rounded-lg border border-border text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent lg:hidden"
          >
            <span aria-hidden="true">☰</span>
          </button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-foreground">{business?.name ?? "No workspace yet"}</p>
            <p className="hidden truncate text-xs text-muted sm:block">
              {business ? (
                <>
                  {business.industry} · {business.business_type} ·{" "}
                  <Link href="/" onClick={() => clearBusiness()} className="underline decoration-dotted underline-offset-4 hover:text-foreground">
                    Switch workspace
                  </Link>
                </>
              ) : (
                <Link href="/onboarding" className="font-medium text-accent underline underline-offset-4">Set up your business</Link>
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right sm:block">
              <p className="max-w-[16rem] truncate text-xs text-muted">{user?.email}</p>
              <p className="text-xs font-medium text-foreground">{isAdmin ? "Admin" : isResearcher ? "Researcher" : demo ? "Demo account" : "Business user"}</p>
            </div>
            <button
              onClick={logout}
              className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-muted-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Sign out
            </button>
          </div>
        </header>

        {demo ? (
          <div role="note" className="border-b border-border bg-muted-surface px-4 py-2 text-center text-sm text-foreground">
            <span className="mr-2 rounded-full bg-warning px-2 py-0.5 text-xs font-bold tracking-wide text-white">DEMO DATA</span>
            You&apos;re exploring DecisionGPT with example data — not a real business.
          </div>
        ) : null}
        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
