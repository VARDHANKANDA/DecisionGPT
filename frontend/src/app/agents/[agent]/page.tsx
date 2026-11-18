"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { agentById, type AgentId } from "@/lib/features";
import { useBusiness } from "@/lib/business-context";
import { api, type AgentConsultationResult } from "@/lib/api";
import { Page, Spinner, btnPrimary, btnSecondary, Notice } from "@/components/simple";
import { AgentHero } from "@/components/agent-ui";
import {
  BusinessAnalystPanels,
  FinancialAdvisorPanels,
  MarketingAdvisorPanels,
  RiskManagerPanels,
  StrategyOptimiserPanels,
} from "@/components/agent-panels";

const PANELS: Record<AgentId, () => ReactNode> = {
  "business-analyst": () => <BusinessAnalystPanels />,
  "financial-advisor": () => <FinancialAdvisorPanels />,
  "marketing-advisor": () => <MarketingAdvisorPanels />,
  "risk-manager": () => <RiskManagerPanels />,
  "strategy-optimiser": () => <StrategyOptimiserPanels />,
};

const AGENT_TASKS: Record<
  AgentId,
  { defaultTask: string; suggestions: string[]; roleBadge: string }
> = {
  "business-analyst": {
    defaultTask: "Analyze recent sales momentum, identify top revenue products, and audit demand velocity.",
    suggestions: [
      "What are our fastest-growing products?",
      "Audit monthly sales trends and revenue seasonality",
      "Identify products with declining sales velocity",
    ],
    roleBadge: "Sales Velocity & Performance Audit Specialist",
  },
  "financial-advisor": {
    defaultTask: "Evaluate gross margins across catalog, audit expense structures, and review capital allocation priorities.",
    suggestions: [
      "Assess gross margin health across categories",
      "Analyze unit economics and overhead sustainability",
      "Identify cost-reduction opportunities",
    ],
    roleBadge: "Gross Margin Sustainability & Capital Allocation Specialist",
  },
  "marketing-advisor": {
    defaultTask: "Review marketing campaign performance, channel ROI, and customer acquisition efficiency.",
    suggestions: [
      "Which marketing channels yield the highest return?",
      "Audit customer acquisition cost vs lifetime value",
      "Evaluate seasonal campaign lift",
    ],
    roleBadge: "Campaign Performance & Customer Channel Specialist",
  },
  "risk-manager": {
    defaultTask: "Audit inventory stockout liabilities, detect customer churn signals, and assess downside vulnerability.",
    suggestions: [
      "Which items are at immediate risk of stocking out?",
      "Identify high-value customer accounts showing churn signals",
      "What are our primary data quality and operational risks?",
    ],
    roleBadge: "Operational Downside & Vulnerability Specialist",
  },
  "strategy-optimiser": {
    defaultTask: "Synthesize operational signals, evaluate candidate strategic initiatives, and quantify business trade-offs.",
    suggestions: [
      "Should we prioritize price discounts or marketing expansion?",
      "Compare revenue growth vs margin protection",
      "Rank strategic alternatives based on simulated impact",
    ],
    roleBadge: "Strategic Synthesis & Trade-off Optimization Specialist",
  },
};

export default function AgentPage() {
  const params = useParams<{ agent: string }>();
  const agent = agentById(params.agent);
  const { business, loading } = useBusiness();

  const agentConfig = agent ? AGENT_TASKS[agent.id] : null;
  const [task, setTask] = useState(agentConfig?.defaultTask || "");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AgentConsultationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Sync default task when agent loads
  useEffect(() => {
    if (agentConfig) {
      setTask(agentConfig.defaultTask);
      setResult(null);
    }
  }, [params.agent]);

  if (!agent || !agentConfig) {
    return (
      <Page title="Agent Not Found" subtitle="The requested AI agent could not be found.">
        <Link href="/dashboard" className={btnSecondary}>
          Return to Dashboard
        </Link>
      </Page>
    );
  }

  if (loading) return <Page title={agent.name}><Spinner label="Opening agent workspace…" /></Page>;
  if (!business) {
    return (
      <Page title={agent.name} subtitle={agent.purpose}>
        <Link href="/onboarding" className={btnPrimary}>
          Set up my business first
        </Link>
      </Page>
    );
  }

  async function handleConsult(queryTask?: string) {
    const taskToRun = (queryTask ?? task).trim();
    if (!taskToRun || !business || !agent) return;
    setRunning(true);
    setError(null);
    try {
      const data = await api.consultAgent(business.id, agent.id, taskToRun);
      setResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to complete agent consultation.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <Page
      title={`${agent.icon} ${agent.name}`}
      subtitle={`${agentConfig.roleBadge} — dedicated domain execution grounded in your verified business data.`}
      wide
    >
      <div className="space-y-6">
        <AgentHero agent={agent} />

        {/* Dedicated Agent Consultation Workspace */}
        <section
          id="consult-workspace"
          className="rounded-2xl border border-border bg-surface p-6 shadow-sm"
        >
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 pb-4">
            <div>
              <h2 className="text-xl font-semibold text-foreground">
                Domain Consultation Workspace
              </h2>
              <p className="mt-1 text-sm text-muted">
                Assign a dedicated analytical task to the {agent.name}. Every recommendation adheres to verified records and documented scoring.
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-3 py-1 text-xs font-semibold text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent"></span> Dedicated Execution
            </span>
          </div>

          {/* Quick Prompts */}
          <div className="mt-5">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">
              Suggested Tasks for {agent.name}
            </span>
            <div className="mt-2 flex flex-wrap gap-2">
              {agentConfig.suggestions.map((sug) => (
                <button
                  key={sug}
                  type="button"
                  onClick={() => {
                    setTask(sug);
                    void handleConsult(sug);
                  }}
                  className="rounded-full border border-border bg-background px-3.5 py-1.5 text-xs text-foreground hover:border-accent hover:bg-muted-surface transition"
                >
                  {sug}
                </button>
              ))}
            </div>
          </div>

          {/* Task Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void handleConsult();
            }}
            className="mt-4 space-y-3"
          >
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              rows={2}
              placeholder={`Describe the task or question for ${agent.name}…`}
              className="w-full rounded-xl border border-border bg-background p-3.5 text-sm text-foreground focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-muted">
                Task runs specialized domain algorithms over connected tables.
              </span>
              <button
                type="submit"
                disabled={running || !task.trim()}
                className={btnPrimary}
              >
                {running ? "Analyzing Evidence…" : `Consult ${agent.name}`}
              </button>
            </div>
          </form>

          {error && (
            <div className="mt-4">
              <Notice tone="danger" title="Consultation Error">{error}</Notice>
            </div>
          )}

          {running && (
            <div className="mt-6 py-8 text-center">
              <Spinner label={`${agent.name} is inspecting records and synthesizing executive recommendations…`} />
            </div>
          )}

          {/* Standardized 6-Part Executive Structure Output */}
          {result && !running && (
            <div className="mt-8 space-y-6 border-t border-border/80 pt-6">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-lg font-semibold text-foreground">
                  Executive Consultation Brief
                </h3>
                <span className="text-xs text-muted">
                  Prepared by <strong>{result.agent_name}</strong>
                </span>
              </div>

              {/* Part 1: Executive Summary */}
              <div className="rounded-xl border border-accent/30 bg-accent/5 p-5 shadow-xs">
                <span className="text-xs font-semibold uppercase tracking-wider text-accent">
                  1. Executive Summary
                </span>
                <p className="mt-2 text-base font-medium leading-relaxed text-foreground">
                  {result.executive_summary}
                </p>
              </div>

              {/* Part 2: Key Findings */}
              <div className="rounded-xl border border-border bg-background p-5 shadow-xs">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                  2. Key Findings
                </span>
                <ul className="mt-3 space-y-2">
                  {result.key_findings.map((f, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-foreground">
                      <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-accent"></span>
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Part 3: Supporting Evidence */}
              <div className="rounded-xl border border-border bg-background p-5 shadow-xs">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                  3. Supporting Evidence
                </span>
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-border bg-muted-surface/50 text-muted uppercase">
                      <tr>
                        <th className="px-3 py-2 font-medium">Claim / Metric</th>
                        <th className="px-3 py-2 font-medium">Verified Source</th>
                        <th className="px-3 py-2 font-medium">Type</th>
                        <th className="px-3 py-2 font-medium">Confidence</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border/60">
                      {result.supporting_evidence.map((ev, i) => (
                        <tr key={i} className="hover:bg-muted-surface/30">
                          <td className="px-3 py-2 font-medium text-foreground">{ev.claim}</td>
                          <td className="px-3 py-2 font-mono text-[11px] text-muted">{ev.source}</td>
                          <td className="px-3 py-2 text-muted capitalize">{ev.evidence_type}</td>
                          <td className="px-3 py-2 text-emerald-600 dark:text-emerald-400 font-semibold">
                            {(ev.confidence * 100).toFixed(0)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Part 4: Business Implications */}
              <div className="rounded-xl border border-border bg-background p-5 shadow-xs">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                  4. Business Implications
                </span>
                <ul className="mt-3 space-y-2">
                  {result.business_implications.map((imp, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-foreground">
                      <span className="mt-1 text-accent font-bold text-xs">&rarr;</span>
                      <span>{imp}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Part 5: Recommended Actions */}
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-5 shadow-xs">
                <span className="text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                  5. Recommended Actions
                </span>
                <ol className="mt-3 space-y-2">
                  {result.recommended_actions.map((act, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-foreground">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500 text-[10px] font-bold text-white">
                        {i + 1}
                      </span>
                      <span className="font-medium">{act}</span>
                    </li>
                  ))}
                </ol>
              </div>

              {/* Part 6: Assumptions and Limitations */}
              <div className="rounded-xl border border-border/80 bg-muted-surface/30 p-5 shadow-xs">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                  6. Assumptions and Limitations
                </span>
                <ul className="mt-3 space-y-1.5 text-xs text-muted">
                  {result.assumptions_and_limitations.map((lim, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span>•</span>
                      <span>{lim}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Cross-deliberation link */}
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface p-4">
                <span className="text-xs text-muted">
                  Want to challenge this advice against other specialists?
                </span>
                <Link href="/agents/debate" className={btnSecondary}>
                  Deliberate in Multi-Agent Debate &rarr;
                </Link>
              </div>
            </div>
          )}
        </section>

        {/* Specialized Domain Metric Panels */}
        <section className="space-y-4">
          <div className="border-t border-border pt-4">
            <h3 className="text-base font-semibold text-foreground">
              Domain Data & Baseline Trends
            </h3>
            <p className="text-xs text-muted">
              Live operational metrics evaluated by {agent.name}.
            </p>
          </div>
          {PANELS[agent.id]()}
        </section>
      </div>
    </Page>
  );
}
