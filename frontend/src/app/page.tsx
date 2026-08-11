"use client";

import Link from "next/link";
import { useBusiness } from "@/lib/business-context";

export default function Home() {
  const { business, loading } = useBusiness();

  return (
    <div className="mx-auto flex max-w-3xl flex-col items-center px-6 py-32 text-center">
      <p className="mb-4 text-sm font-medium uppercase tracking-widest text-accent">
        AI decision support for Indian SMEs
      </p>
      <h1 className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
        Know what to do next — not just what happened.
      </h1>
      <p className="mt-6 max-w-xl text-lg text-muted">
        DecisionGPT turns your sales, customer and marketing data into a clear,
        explainable recommendation — grounded in your own numbers, never
        fabricated.
      </p>

      <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
        {!loading && business ? (
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center rounded-full bg-accent px-6 py-3 text-sm font-medium text-accent-foreground transition hover:opacity-90"
          >
            Go to {business.name}&rsquo;s dashboard
          </Link>
        ) : (
          <Link
            href="/onboarding"
            className="inline-flex items-center justify-center rounded-full bg-accent px-6 py-3 text-sm font-medium text-accent-foreground transition hover:opacity-90"
          >
            Get started
          </Link>
        )}
      </div>

      <p className="mt-16 text-xs text-muted">
        A decision-support system. DecisionGPT recommends and simulates —
        it never executes payments, ad spend, or price changes on its own.
      </p>
    </div>
  );
}
