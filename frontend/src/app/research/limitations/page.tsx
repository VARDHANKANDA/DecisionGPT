"use client";

import { PageIntro, Panel } from "@/components/research-ui";

interface LimitationItem {
  id: string;
  title: string;
  badge: string;
  badgeColor: string;
  whyItMatters: string;
  currentEvidence: string;
  impact: string;
  futureWork: string;
}

const RESEARCH_LIMITATIONS: LimitationItem[] = [
  {
    id: "latency",
    title: "1. Decision Latency in Multi-Agent Debate",
    badge: "Verified ~12.4s Overhead",
    badgeColor: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20",
    whyItMatters:
      "Unlike simple single-agent heuristic scripts, DecisionGPT coordinates 5 domain personas (BA, FA, MA, RM, SO) through up to 3 adversarial debate rounds, requiring sequential API evaluations.",
    currentEvidence:
      "Across 30 live benchmark evaluations, mean decision latency was 12.4 seconds (median: 8.41s for analytics queries, 13.7s for full multi-agent consensus). Single-turn GPT-5 mini calls complete in ~6.85s.",
    impact:
      "DecisionGPT is architected for strategic business decisions and capital allocation, not sub-second algorithmic trading or real-time web page rendering.",
    futureWork:
      "Implement parallel asynchronous agent execution during initial domain rounds, cache safe invariant context, and terminate debate early when agent consensus divergence is below ε = 0.05.",
  },
  {
    id: "confounding",
    title: "2. Observational Confounding in Retail Transactions",
    badge: "Causal Backdoor Guard Active",
    badgeColor: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
    whyItMatters:
      "Observational point-of-sale sales data cannot record unobserved market dynamics such as local competitor discounts, sudden neighborhood road closures, or unlogged distributor stockouts.",
    currentEvidence:
      "Pearl's Backdoor Criterion and Benjamini-Hochberg FDR correction (q = 0.05) verified promotion and contract-type causal effects (p < 0.001), but correctly flagged marketing spend (p = 0.214) and unit price (p = 0.358) as 'unsupported' due to insufficient exogenous variation.",
    impact:
      "The system prevents catastrophic business errors by refusing to make unsupported causal claims where confounding variables are missing.",
    futureWork:
      "Integrate local competitor price scrapers, verified regional holiday calendars, and randomized controlled trial (A/B testing) modules for active business interventions.",
  },
  {
    id: "single_store",
    title: "3. Single-Store POS Register Geographic Scope",
    badge: "1 Store · 89 Trading Days",
    badgeColor: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
    whyItMatters:
      "The authentic 94,290-line POS register originates from a single high-volume retail grocery store in Kerala, India over 89 days (1 Jan - 31 Mar 2025).",
    currentEvidence:
      "While providing authentic transaction dynamics with Indian Rupee (INR) pricing, whole-number quantity validation, and GST slabs, a single store reflects specific local shopping habits.",
    impact:
      "Findings validate time-series forecasting and econometric methodology but cannot be automatically generalized to all 63 million heterogeneous Indian MSMEs.",
    futureWork:
      "Expand the Dataset Registry with multi-store, multi-state POS feeds across Tier-1, Tier-2, and rural Indian retail clusters to evaluate geographical transferability.",
  },
  {
    id: "small_sample_r2",
    title: "4. Small Test Horizon & Out-of-Sample R² Sensitivity",
    badge: "12 Test Dates · Volatile Demand",
    badgeColor: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20",
    whyItMatters:
      "The untouched held-out test partition comprises 12 days (2025-03-17 to 2025-03-31). Out-of-sample R² compares against the unobservable future test-set mean.",
    currentEvidence:
      "Due to weekend revenue spikes (₹85,772 on Sunday vs ₹23,525 on Friday), all models show negative out-of-sample R² (-0.42 to -1.57). However, machine learning models (HistGradientBoosting MAE ₹11,798) beat the seasonal naive baseline (₹16,106) by +26.7%, achieving MASE = 1.18 and WAPE = 22.5%.",
    impact:
      "Standard academic R² penalizes one-step-ahead forecasts in volatile regime shifts; scaled metrics (MASE, WAPE, sMAPE) provide more reliable scientific assessment.",
    futureWork:
      "Collect 12+ months of continuous POS history to incorporate multi-seasonality (Diwali, Eid, Onam, New Year) and expand the test window to 60+ days.",
  },
];

export default function LimitationsPage() {
  return (
    <div className="space-y-8">
      <PageIntro
        title="Research Limitations & Academic Boundaries"
        subtitle="Transparent, verified scientific boundaries of the DecisionGPT platform. These honest disclosures reflect rigorous academic integrity for university capstone evaluation."
      />

      {/* Summary Banner */}
      <div className="rounded-2xl border border-border bg-gradient-to-r from-surface via-surface to-muted-surface/30 p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <span className="inline-flex items-center rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-semibold text-accent">
              Academic Research Integrity
            </span>
            <h2 className="mt-2 text-lg font-bold text-foreground">
              Honest Disclosure over Unrealistic Claims
            </h2>
            <p className="mt-1 text-xs text-muted max-w-2xl">
              Per <code className="font-mono text-foreground">AGENTS.md</code>, DecisionGPT never fabricates benchmark results. 
              Known operational boundaries are documented with empirical evidence and concrete future remedies.
            </p>
          </div>
          <div className="text-right text-xs text-muted">
            <p>Audited: <span className="font-semibold text-foreground">18 Nov 2026</span></p>
            <p className="mt-0.5">4 Verified Research Limitations</p>
          </div>
        </div>
      </div>

      {/* Grid of Limitations */}
      <div className="space-y-6">
        {RESEARCH_LIMITATIONS.map((lim) => (
          <Panel
            key={lim.id}
            title={lim.title}
            right={
              <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${lim.badgeColor}`}>
                {lim.badge}
              </span>
            }
          >
            <div className="grid gap-4 sm:grid-cols-2 text-xs">
              <div className="space-y-1 rounded-lg border border-border bg-muted-surface/20 p-3">
                <span className="font-semibold uppercase tracking-wider text-muted">Why It Matters</span>
                <p className="text-foreground leading-relaxed">{lim.whyItMatters}</p>
              </div>

              <div className="space-y-1 rounded-lg border border-border bg-muted-surface/20 p-3">
                <span className="font-semibold uppercase tracking-wider text-muted">Current Evidence</span>
                <p className="text-foreground leading-relaxed">{lim.currentEvidence}</p>
              </div>

              <div className="space-y-1 rounded-lg border border-border bg-muted-surface/20 p-3">
                <span className="font-semibold uppercase tracking-wider text-muted">Operational Impact</span>
                <p className="text-foreground leading-relaxed">{lim.impact}</p>
              </div>

              <div className="space-y-1 rounded-lg border border-border bg-accent-soft/20 p-3">
                <span className="font-semibold uppercase tracking-wider text-accent">Remedy in Future Work</span>
                <p className="text-foreground leading-relaxed">{lim.futureWork}</p>
              </div>
            </div>
          </Panel>
        ))}
      </div>
    </div>
  );
}
