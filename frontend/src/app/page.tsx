"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";

export default function Home() {
  const { business, loading, setBusinessId } = useBusiness();
  const router = useRouter();
  const [creatingDemo, setCreatingDemo] = useState(false);
  const [demoError, setDemoError] = useState<string | null>(null);

  async function tryDemoBusiness() {
    setCreatingDemo(true);
    setDemoError(null);
    try {
      const demoBusiness = await api.createDemoBusiness();
      setBusinessId(demoBusiness.id);
      router.push("/dashboard");
    } catch (err) {
      setDemoError(err instanceof ApiError ? err.message : "Could not create the demo business right now.");
      setCreatingDemo(false);
    }
  }

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
          <>
            <Link
              href="/onboarding"
              className="inline-flex items-center justify-center rounded-full bg-accent px-6 py-3 text-sm font-medium text-accent-foreground transition hover:opacity-90"
            >
              Get started
            </Link>
            <button
              onClick={tryDemoBusiness}
              disabled={creatingDemo}
              className="inline-flex items-center justify-center rounded-full border border-border bg-surface px-6 py-3 text-sm font-medium text-foreground transition hover:bg-muted-surface disabled:opacity-50"
            >
              {creatingDemo ? "Setting up demo…" : "Try demo business"}
            </button>
          </>
        )}
      </div>
      {demoError ? <p className="mt-4 text-sm text-danger">{demoError}</p> : null}

      <p className="mt-16 text-xs text-muted">
        A decision-support system. DecisionGPT recommends and simulates —
        it never executes payments, ad spend, or price changes on its own.
      </p>
    </div>
  );
}
