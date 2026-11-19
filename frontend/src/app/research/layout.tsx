"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

interface NavItem {
  href: string;
  label: string;
}

interface NavGroup {
  group: string;
  items: NavItem[];
}

const RESEARCH_NAV_GROUPS: NavGroup[] = [
  {
    group: "Overview",
    items: [
      { href: "/research", label: "Research Overview" },
    ],
  },
  {
    group: "Models & Data",
    items: [
      { href: "/research/models", label: "Model Registry" },
      { href: "/research/datasets", label: "Dataset Registry" },
      { href: "/research/ml-benchmark", label: "ML Benchmark" },
    ],
  },
  {
    group: "Evaluation",
    items: [
      { href: "/research/model-performance", label: "Model Evaluation" },
      { href: "/research/llm-evaluation", label: "LLM Evaluation" },
      { href: "/research/agent-evaluation", label: "Agent Evaluation" },
      { href: "/research/causal-evaluation", label: "Causal Evaluation" },
      { href: "/research/risk-calibration", label: "Risk Evaluation" },
    ],
  },
  {
    group: "Experiments",
    items: [
      { href: "/research/model-comparison", label: "Model Comparison" },
      { href: "/research/validation", label: "Validation" },
    ],
  },
  {
    group: "Reports",
    items: [
      { href: "/research/limitations", label: "Research Limitations" },
      { href: "/research/export", label: "Data Export" },
    ],
  },
];

const ALL_NAV_ITEMS: NavItem[] = RESEARCH_NAV_GROUPS.flatMap((g) => g.items);

export default function ResearchLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, canAccessResearch, loading, logout } = useAuth();

  useEffect(() => {
    if (loading) return;
    // Research access requires a signed-in admin or researcher session.
    if (!user) {
      router.replace(`/login?role=admin&next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, user, pathname, router]);

  if (loading) return null;

  if (!user) return null; // redirecting to admin sign-in

  if (!canAccessResearch) {
    return (
      <div className="mx-auto flex min-h-[70vh] max-w-sm flex-col justify-center px-6 text-center">
        <h1 className="text-lg font-semibold text-foreground">Research Console</h1>
        <p className="mt-2 text-sm text-muted">
          Access denied — administrator / research access is required. Your account is a standard business account.
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
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 flex-col border-r border-border bg-muted-surface/30 lg:flex">
        <div className="border-b border-border p-4">
          <p className="text-lg font-bold tracking-tight text-foreground">Research Console</p>
          <p className="mt-0.5 text-xs font-medium text-muted">Controlled Evaluation &amp; Evidence</p>
        </div>
        <nav className="flex flex-1 flex-col gap-4 overflow-y-auto p-3" aria-label="Research Console">
          {RESEARCH_NAV_GROUPS.map((grp) => (
            <div key={grp.group} className="space-y-1">
              <span className="px-3 text-xs font-bold uppercase tracking-wider text-muted-foreground/80">
                {grp.group}
              </span>
              <div className="space-y-0.5">
                {grp.items.map((link) => {
                  const active =
                    pathname === link.href || (link.href !== "/research" && pathname.startsWith(link.href));
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      aria-current={active ? "page" : undefined}
                      className={`block rounded-lg px-3 py-2 text-sm transition ${
                        active
                          ? "bg-accent/10 font-semibold text-accent border-l-2 border-accent shadow-sm"
                          : "font-medium text-muted hover:bg-muted-surface hover:text-foreground"
                      }`}
                    >
                      {link.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
        <div className="border-t border-border p-3 text-xs text-muted">
          <div className="flex items-center justify-between px-1">
            <p className="truncate font-medium">{user.email}</p>
            <span className="ml-2 shrink-0 rounded-full bg-muted-surface px-2 py-0.5 font-medium">{user.role}</span>
          </div>
          <div className="mt-2 flex items-center justify-between">
            <Link href="/dashboard" className="font-medium underline decoration-dotted underline-offset-4 hover:text-foreground">
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

      <div className="lg:pl-64">
        {/* mobile bar */}
        <header className="sticky top-0 z-10 flex items-center gap-3 overflow-x-auto border-b border-border bg-surface px-4 py-2.5 lg:hidden">
          {ALL_NAV_ITEMS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium ${
                pathname === link.href ? "bg-accent/10 font-semibold text-accent" : "text-muted hover:text-foreground"
              }`}
            >
              {link.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={logout}
            className="ml-auto shrink-0 rounded-full border border-border px-3.5 py-1.5 text-sm font-medium text-foreground"
          >
            Sign out
          </button>
        </header>
        <main className="mx-auto max-w-5xl px-6 py-10">{children}</main>
      </div>
    </div>
  );
}
