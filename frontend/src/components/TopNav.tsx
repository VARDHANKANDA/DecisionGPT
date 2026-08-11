"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useBusiness } from "@/lib/business-context";

const NAV_LINKS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/data/upload", label: "Data" },
  { href: "/goals", label: "Goals" },
];

export function TopNav() {
  const { business, clearBusiness } = useBusiness();
  const pathname = usePathname();

  return (
    <header className="border-b border-border bg-surface/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-foreground">
          DecisionGPT
        </Link>

        {business ? (
          <nav className="flex items-center gap-1">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  pathname === link.href
                    ? "bg-accent-soft text-accent"
                    : "text-muted hover:bg-muted-surface hover:text-foreground"
                }`}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        ) : null}

        {business ? (
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted">{business.name}</span>
            <button
              onClick={clearBusiness}
              className="text-sm text-muted underline decoration-dotted underline-offset-4 hover:text-foreground"
            >
              Switch business
            </button>
          </div>
        ) : (
          <div className="w-24" />
        )}
      </div>
    </header>
  );
}
