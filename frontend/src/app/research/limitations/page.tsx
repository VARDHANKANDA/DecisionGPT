"use client";

export default function LimitationsPage() {
  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Limitations</h1>
        <p className="mt-1 text-sm text-muted">What this study does not establish.</p>
      </header>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Not established</h2>
        <ul className="mt-3 space-y-2 text-sm text-foreground">
          {[
            ["Real Indian SME performance", "0 genuine decision outcomes have been recorded; Table 2 is NOT READY."],
            ["Real-LLM behaviour", "No LLM provider is configured; the agent layer is rule-based. Real-LLM validation is BLOCKED."],
            ["Real-world causal effects", "CAUSALLY_VALIDATED = 0. Causal recovery is validated on synthetic ground truth only, with pairwise Granger and no multiple-comparison correction."],
            ["Superiority over existing systems", "No external / commercial decision-support system was compared."],
            ["R3 production superiority", "R3 is promising on the synthetic calibration suite only, inert on the one real dataset; production stays R0 / D0."],
            ["Human explainability / usability benefit", "No user study was conducted."],
          ].map(([t, b]) => (
            <li key={t} className="rounded-lg border border-border bg-surface p-4">
              <span className="font-medium">✗ {t}.</span> <span className="text-muted">{b}</span>
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Scope of the evidence</h2>
        <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-muted">
          <li>All decision-quality evidence is from designed synthetic scenarios (12 scenarios × 5 seeds). The 95% CIs describe variability <em>within</em> this suite, not a population.</li>
          <li>Agent scores are rule-based; round-2 peer review is inactive in this mode. A real LLM might behave differently.</li>
          <li>The one real dataset (Benroshan) is a single small e-commerce series with unverified provenance — a feasibility probe, not evidence of generalisation.</li>
          <li>Data categories (REAL_INDIAN_SME_OUTCOME, INDIA_REAL_BUSINESS, INDIA_PUBLIC_CONTEXT, INDIA_AGRICULTURAL_PRICE, SYNTHETIC_CONTROLLED, SYNTHETIC_INDIAN_CONTEXT, RETIRED_NON_INDIAN) are never combined into a single &ldquo;real-world performance&rdquo; number.</li>
        </ul>
      </section>
    </div>
  );
}
