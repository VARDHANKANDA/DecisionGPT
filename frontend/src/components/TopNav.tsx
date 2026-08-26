"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useBusiness } from "@/lib/business-context";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/data", label: "Data" },
  { href: "/goals", label: "Goals" },
  { href: "/decision", label: "Decision" },
  { href: "/simulation", label: "Simulation" },
  { href: "/causal-graph", label: "Causal Graph" },
  { href: "/history", label: "History" },
  { href: "/chat", label: "Chat" },
];

export function TopNav() {
  const { business, clearBusiness } = useBusiness();
  const { user, logout } = useAuth();
  const pathname = usePathname();

  // The Research Console (docs/PRD.md §8) is a separate, private surface
  // with its own layout/nav and must never appear in the SME navigation.
  if (pathname.startsWith("/research")) return null;

  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-6 py-4">
        <Link href="/" className="shrink-0 text-lg font-semibold tracking-tight text-foreground">
          DecisionGPT
        </Link>

        <div className="flex shrink-0 items-center gap-3 order-2 sm:order-3">
          {business ? (
            <>
              <span className="max-w-[10rem] truncate text-sm text-muted sm:max-w-none">{business.name}</span>
              <button
                onClick={clearBusiness}
                className="whitespace-nowrap text-sm text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
              >
                Switch business
              </button>
            </>
          ) : null}
          {user ? (
            <button
              onClick={logout}
              className="whitespace-nowrap text-sm text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
            >
              Sign out ({user.email})
            </button>
          ) : (
            <Link
              href="/login"
              className="whitespace-nowrap text-sm text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
            >
              Sign in
            </Link>
          )}
        </div>

        {business ? (
          <nav className="order-3 flex w-full items-center gap-1 overflow-x-auto sm:order-2 sm:w-auto">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`shrink-0 rounded-full px-3 py-2 text-sm font-medium transition ${
                  pathname === link.href || pathname.startsWith(`${link.href}/`)
                    ? "bg-accent-soft text-accent"
                    : "text-muted hover:bg-muted-surface hover:text-foreground"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        ) : null}
      </div>
    </header>
  );
}
