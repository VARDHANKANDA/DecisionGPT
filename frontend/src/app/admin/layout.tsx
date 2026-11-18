"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

const ADMIN_NAV = [
  { href: "/admin", label: "System Monitoring", icon: "📊" },
  { href: "/admin#users", label: "User Management", icon: "👥" },
  { href: "/admin#security", label: "Security & Settings", icon: "🛡️" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAdmin, loading, logout } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace(`/login?role=admin&next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, user, pathname, router]);

  if (loading) return null;
  if (!user) return null;

  if (!isAdmin) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-6 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-danger-soft text-danger text-2xl">
          ⛔
        </div>
        <h1 className="mt-4 text-xl font-bold text-foreground">Administrative Access Restricted</h1>
        <p className="mt-2 text-sm text-muted">
          Your account does not possess platform administrator privileges (ROLE_ADMIN). Access to user
          management and application infrastructure controls is strictly restricted.
        </p>
        <div className="mt-6 flex justify-center gap-3">
          <Link
            href="/dashboard"
            className="rounded-full bg-accent px-5 py-2 text-sm font-medium text-accent-foreground transition hover:opacity-90"
          >
            Go to SME Workspace
          </Link>
          <Link
            href="/research"
            className="rounded-full border border-border px-5 py-2 text-sm font-medium text-foreground transition hover:bg-muted-surface"
          >
            Research Console
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar for Desktop */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-border bg-muted-surface/30 lg:flex">
        <div className="border-b border-border p-5">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-accent-foreground font-bold text-sm">
              DG
            </div>
            <div>
              <p className="text-base font-bold tracking-tight text-foreground leading-none">DecisionGPT</p>
              <p className="mt-1 text-[11px] font-semibold uppercase tracking-wider text-accent">Admin Console</p>
            </div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3" aria-label="Administrative Navigation">
          <p className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted">Platform Controls</p>
          {ADMIN_NAV.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.label}
                href={link.href}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "bg-accent-soft text-accent"
                    : "text-muted hover:bg-muted-surface hover:text-foreground"
                }`}
              >
                <span>{link.icon}</span>
                <span>{link.label}</span>
              </Link>
            );
          })}

          <div className="my-3 border-t border-border" />
          <p className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wider text-muted">Switch Workspace</p>
          <Link
            href="/research"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-muted-surface hover:text-foreground transition"
          >
            <span>🔬</span>
            <span>Research Console</span>
          </Link>
          <Link
            href="/dashboard"
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-muted hover:bg-muted-surface hover:text-foreground transition"
          >
            <span>💼</span>
            <span>SME App Workspace</span>
          </Link>
        </nav>

        <div className="border-t border-border p-4 text-xs text-muted">
          <div className="flex items-center justify-between">
            <div className="truncate">
              <p className="font-medium text-foreground truncate">{user.full_name || "Admin"}</p>
              <p className="truncate text-muted">{user.email}</p>
            </div>
            <span className="shrink-0 rounded-full bg-accent-soft px-2.5 py-0.5 font-bold text-accent">
              ADMIN
            </span>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
              Live Backend
            </span>
            <button
              type="button"
              onClick={logout}
              className="rounded-lg border border-border px-3 py-1 font-medium text-foreground hover:bg-muted-surface transition"
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* Main Container */}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-surface/90 px-6 py-3 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <span className="rounded-md bg-accent-soft px-2.5 py-1 text-xs font-bold text-accent">
              SYSTEM LEVEL
            </span>
            <span className="text-xs text-muted">Node: localhost:8000 · RBAC: Enforced</span>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/research"
              className="text-xs font-medium text-muted hover:text-foreground transition"
            >
              Research Console &rarr;
            </Link>
            <button
              onClick={logout}
              className="rounded-md border border-border px-3 py-1 text-xs font-medium text-foreground hover:bg-muted-surface"
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </div>
    </div>
  );
}
