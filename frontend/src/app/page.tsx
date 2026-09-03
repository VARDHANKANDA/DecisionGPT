"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

export default function Home() {
  const { user, isAdmin, loading } = useAuth();
  const router = useRouter();

  // A signed-in visitor never needs the chooser — send them to their workspace.
  useEffect(() => {
    if (loading || !user) return;
    router.replace(isAdmin ? "/research" : "/dashboard");
  }, [loading, user, isAdmin, router]);

  if (!loading && user) return null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-6 py-16">
      <div className="w-full max-w-2xl">
        <div className="mb-10 text-center">
          <p className="text-lg font-semibold tracking-tight text-foreground">DecisionGPT</p>
          <p className="mt-1 text-sm text-muted">
            Decision support for small &amp; medium businesses
          </p>
        </div>

        <h1 className="text-center text-xl font-semibold text-foreground">
          How would you like to continue?
        </h1>

        <div className="mt-8 grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col rounded-2xl border border-border bg-surface p-6">
            <h2 className="text-base font-semibold text-foreground">Business user</h2>
            <p className="mt-1 flex-1 text-sm text-muted">
              For SME owners and managers. Upload your data, set a goal, and get a clear, explainable
              recommendation.
            </p>
            <Link
              href="/login?role=user"
              className="mt-5 inline-flex items-center justify-center rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Continue as User
            </Link>
          </div>

          <div className="flex flex-col rounded-2xl border border-border bg-surface p-6">
            <h2 className="text-base font-semibold text-foreground">Admin / Researcher</h2>
            <p className="mt-1 flex-1 text-sm text-muted">
              For platform administrators and paper authors. Opens the Research Console — the controlled
              evaluation and research evidence.
            </p>
            <Link
              href="/login?role=admin"
              className="mt-5 inline-flex items-center justify-center rounded-full border border-border bg-surface px-5 py-2.5 text-sm font-medium text-foreground transition hover:bg-muted-surface focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            >
              Continue as Admin
            </Link>
          </div>
        </div>

        <p className="mt-8 text-center text-xs text-muted">
          Choosing “Admin” only routes you to the admin sign-in. Research access is granted by your
          account&apos;s role on the server — not by this choice.
        </p>

        <p className="mt-10 text-center text-xs text-muted">
          DecisionGPT recommends and simulates — it never executes payments, ad spend, or price changes
          on its own.
        </p>
      </div>
    </div>
  );
}
