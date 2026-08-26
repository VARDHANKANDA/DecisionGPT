"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  api,
  ApiError,
  type Decision,
  type DecisionExplanation,
  type Goal,
} from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { OutcomeForm } from "@/components/OutcomeForm";
import { Card, EmptyState, PageHeader, PrimaryButton, RiskBadge, SecondaryLink, formatINR } from "@/components/ui";

const OBJECTIVE_LABELS: Record<string, string> = {
  increase_revenue: "Increase revenue",
  increase_profit: "Increase profit",
  increase_sales: "Increase sales",
  reduce_churn: "Reduce churn",
  improve_marketing_roi: "Improve marketing ROI",
  reduce_inventory_risk: "Reduce inventory risk",
};

const AGENT_LABELS: Record<string, string> = {
  business_analyst: "Business Analyst",
  financial_advisor: "Financial Advisor",
  risk_manager: "Risk Manager",
};

export default function DecisionPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-4xl px-6 py-16 text-muted">Loading…</div>}>
      <DecisionPageInner />
    </Suspense>
  );
}

function DecisionPageInner() {
  const { business, loading: businessLoading } = useBusiness();
  const searchParams = useSearchParams();
  const goalIdParam = searchParams.get("goal");

  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(goalIdParam);
  const [decision, setDecision] = useState<Decision | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!business) return;
    api.listGoals(business.id).then((list) => {
      setGoals(list);
      if (!selectedGoalId) {
        const active = list.find((g) => g.status === "active");
        if (active) setSelectedGoalId(active.id);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [business]);

  async function runAnalysis() {
    if (!business || !selectedGoalId) return;
    setAnalyzing(true);
    setError(null);
    setDecision(null);
    try {
      const result = await api.analyzeGoal(business.id, selectedGoalId);
      setDecision(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not analyze this goal right now.");
    } finally {
      setAnalyzing(false);
    }
  }

  if (!businessLoading && !business) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="text-muted">Set up your business first.</p>
        <div className="mt-4">
          <SecondaryLink href="/onboarding">Go to onboarding</SecondaryLink>
        </div>
      </div>
    );
  }

  const selectedGoal = goals?.find((g) => g.id === selectedGoalId) ?? null;

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <PageHeader
        title="Decision"
        subtitle="DecisionGPT simulates candidate strategies and has three specialist agents evaluate each one."
      />

      {goals === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : goals.length === 0 ? (
        <EmptyState
          title="No goals yet"
          description="Set a goal first — DecisionGPT needs one to know what to optimize for."
          action={<SecondaryLink href="/goals">Set a goal</SecondaryLink>}
        />
      ) : (
        <Card>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Goal</span>
            <select
              value={selectedGoalId ?? ""}
              onChange={(e) => {
                setSelectedGoalId(e.target.value);
                setDecision(null);
              }}
              className="input"
            >
              {goals.map((g) => (
                <option key={g.id} value={g.id}>
                  {OBJECTIVE_LABELS[g.objective] ?? g.objective} by {g.target_value}
                  {g.target_unit === "percent" ? "%" : ` ${g.target_unit}`} ({g.status})
                </option>
              ))}
            </select>
          </label>
          <div className="mt-4">
            <PrimaryButton onClick={runAnalysis} disabled={analyzing || !selectedGoalId}>
              {analyzing ? "Analysing…" : "Run analysis"}
            </PrimaryButton>
          </div>
          {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
        </Card>
      )}

      {analyzing ? (
        <div className="mt-8 space-y-2 text-sm text-muted">
          <p>✓ Building candidate strategies</p>
          <p>✓ Running Digital Twin simulations</p>
          <p>● Business Analyst, Financial Advisor and Risk Manager evaluating</p>
          <p className="text-muted/60">○ Strategy Optimizer resolving a recommendation</p>
        </div>
      ) : null}

      {decision ? <DecisionResult business_id={business!.id} decision={decision} goal={selectedGoal} /> : null}
    </div>
  );
}

function DecisionResult({
  business_id,
  decision,
  goal,
}: {
  business_id: string;
  decision: Decision;
  goal: Goal | null;
}) {
  const outcome = decision.expected_outcome;
  const unitsGrowth =
    outcome.baseline_units_sold > 0
      ? ((outcome.expected_units_sold - outcome.baseline_units_sold) / outcome.baseline_units_sold) * 100
      : 0;

  return (
    <div className="mt-8 space-y-6">
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted">
              Recommended strategy
              {goal ? ` for ${OBJECTIVE_LABELS[goal.objective] ?? goal.objective}` : ""}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">{decision.selected_strategy_name}</h2>
          </div>
          <RiskBadge level={decision.risk_level} />
        </div>
        <p className="mt-3 text-sm text-foreground">{decision.reasoning}</p>

        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <MiniStat label="Expected revenue" value={formatINR(outcome.expected_revenue)} />
          <MiniStat label="Baseline revenue" value={formatINR(outcome.baseline_revenue)} />
          <MiniStat label="Units sold change" value={`${unitsGrowth >= 0 ? "+" : ""}${unitsGrowth.toFixed(1)}%`} />
          <MiniStat label="Confidence" value={`${Math.round(decision.confidence * 100)}%`} />
        </div>
      </Card>

      {decision.memory_insights.length > 0 ? (
        <Card>
          <h3 className="text-sm font-medium text-foreground">From your business history</h3>
          <ul className="mt-2 space-y-1 text-sm text-muted">
            {decision.memory_insights.map((insight, i) => (
              <li key={i}>{insight}</li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Card>
        <h3 className="text-sm font-medium text-foreground">AI Business Review</h3>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          {Object.entries(decision.agent_reviews).map(([agent, narrative]) => (
            <div key={agent} className="rounded-xl bg-muted-surface p-4">
              <p className="text-sm font-medium text-foreground">{AGENT_LABELS[agent] ?? agent}</p>
              <p className="mt-2 text-xs text-muted">{narrative}</p>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h3 className="text-sm font-medium text-foreground">Alternative strategies considered</h3>
        <div className="overflow-x-auto">
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="py-2 font-medium">Strategy</th>
                <th className="py-2 text-right font-medium">Score</th>
                <th className="py-2 text-right font-medium">Expected revenue</th>
                <th className="py-2 text-right font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border bg-accent-soft/40">
                <td className="py-2 font-medium">{decision.selected_strategy_name} (selected)</td>
                <td className="py-2 text-right">{decision.selected_strategy_score.toFixed(3)}</td>
                <td className="py-2 text-right">{formatINR(outcome.expected_revenue)}</td>
                <td className="py-2 text-right capitalize">{decision.risk_level}</td>
              </tr>
              {decision.alternatives.map((alt) => (
                <tr key={alt.strategy_id} className="border-b border-border last:border-0">
                  <td className="py-2">{alt.strategy_name}</td>
                  <td className="py-2 text-right">{alt.strategy_score.toFixed(3)}</td>
                  <td className="py-2 text-right">{formatINR(alt.expected_revenue)}</td>
                  <td className="py-2 text-right capitalize">{alt.risk_level}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {decision.skipped_strategies.length > 0 ? (
          <p className="mt-3 text-xs text-muted">
            {decision.skipped_strategies.length} candidate strateg{decision.skipped_strategies.length === 1 ? "y" : "ies"}{" "}
            could not be simulated: {decision.skipped_strategies.join("; ")}
          </p>
        ) : null}
      </Card>

      <StrategyGenerationCard info={decision.strategy_generation} />
      <CausalEvidenceCard ctx={decision.causal_context} />
      <DebateCard debate={decision.debate} />

      {outcome.assumptions?.length > 0 ? (
        <Card>
          <h3 className="text-sm font-medium text-foreground">Assumptions</h3>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
            {outcome.assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </Card>
      ) : null}

      <ExplanationSection businessId={business_id} decisionId={decision.id} />
      <Card>
        <h3 className="text-sm font-medium text-foreground">Record what actually happened</h3>
        <p className="mt-1 text-xs text-muted">
          Once you&apos;ve acted on this and have real numbers, record them here. DecisionGPT compares them
          against the prediction (Digital Twin Evaluation) and references them next time it evaluates a
          similar strategy.
        </p>
        <OutcomeForm
          businessId={business_id}
          decisionId={decision.id}
          expectedOutcome={decision.expected_outcome}
          goalObjective={goal?.objective}
        />
      </Card>
    </div>
  );
}

function StrategyGenerationCard({ info }: { info: Decision["strategy_generation"] }) {
  if (!info) return null;
  const gp = info.goal_projection;
  return (
    <Card>
      <h3 className="text-sm font-medium text-foreground">How these strategies were chosen</h3>
      <p className="mt-2 text-sm text-muted">
        Goal-aware generation for <strong>{info.objective.replace(/_/g, " ")}</strong> produced{" "}
        {info.candidate_count} candidate{info.candidate_count === 1 ? "" : "s"}.
        {info.constraints_applied.length > 0
          ? ` Constraints applied: ${info.constraints_applied.join(", ")}.`
          : ""}
      </p>
      {gp && !gp.improves_goal ? (
        <p className="mt-2 rounded-xl bg-warning-soft px-3 py-2 text-sm text-warning">
          No strategy in the supported action space is projected to improve {info.objective.replace(/_/g, " ")}{" "}
          for this business right now — the option shown is the least-harmful of those evaluated.
        </p>
      ) : null}
      {info.excluded.length > 0 || info.notes.length > 0 ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted">
          {info.excluded.map((e, i) => (
            <li key={`e${i}`}>{e}</li>
          ))}
          {info.notes.map((n, i) => (
            <li key={`n${i}`}>{n}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

const EVIDENCE_STYLE: Record<string, string> = {
  assumed: "text-muted",
  observational: "text-accent",
  data_supported: "text-success",
  causally_validated: "text-success",
};

function CausalEvidenceCard({ ctx }: { ctx: Decision["causal_context"] }) {
  if (!ctx || !ctx.built) return null;
  return (
    <Card>
      <h3 className="text-sm font-medium text-foreground">Causal evidence</h3>
      <p className="mt-2 text-sm text-muted">{ctx.summary}</p>
      <p className="mt-1 text-xs text-muted">
        Graph {ctx.graph_version} · method {ctx.method} · strongest end-to-end evidence:{" "}
        <span className={EVIDENCE_STYLE[ctx.strongest_pathway_evidence] ?? "text-muted"}>
          {ctx.strongest_pathway_evidence.replace(/_/g, " ")}
        </span>
      </p>
      {ctx.pathways.slice(0, 4).map((p, i) => (
        <div key={i} className="mt-2 text-xs">
          <span className="font-medium text-foreground">{p.nodes.join(" → ")}</span>{" "}
          <span className={EVIDENCE_STYLE[p.weakest_evidence] ?? "text-muted"}>
            ({p.weakest_evidence.replace(/_/g, " ")})
          </span>
        </div>
      ))}
      {ctx.caveats.length > 0 ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted">
          {ctx.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

function DebateCard({ debate }: { debate: Decision["debate"] }) {
  if (!debate) return null;
  const res = debate.resolution;
  return (
    <Card>
      <h3 className="text-sm font-medium text-foreground">
        Agent {debate.multi_agent ? "debate" : "review"} ({debate.rounds} round{debate.rounds === 1 ? "" : "s"})
      </h3>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {Object.entries(debate.round1).map(([agent, ev]) => (
          <div key={agent} className="rounded-xl bg-muted-surface p-3 text-xs">
            <p className="font-medium text-foreground">{agent.replace(/_/g, " ")}</p>
            <p className="mt-1 text-muted">Round-1 score {ev.score.toFixed(3)}</p>
          </div>
        ))}
      </div>

      {res.conflicts.length > 0 ? (
        <div className="mt-3">
          <p className="text-xs font-medium text-muted">Conflicts raised in review</p>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-muted">
            {res.conflicts.map((c, i) => (
              <li key={i}>
                <span className="font-medium">{c.raised_by.replace(/_/g, " ")}:</span> {c.concern}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="mt-3 text-xs text-muted">All agents concurred — no conflicts raised.</p>
      )}

      <p className="mt-3 text-xs text-muted">{res.resolution_rationale}</p>
      <p className="mt-2 text-xs text-muted">
        Confidence {(res.confidence * 100).toFixed(0)}% ={" "}
        {Object.entries(res.confidence_basis)
          .filter(([k]) => k !== "formula")
          .map(([k, v]) => `${k.replace(/_/g, " ")} ${typeof v === "number" ? v.toFixed(2) : v}`)
          .join(" × ")}
      </p>
    </Card>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
    </div>
  );
}

function ExplanationSection({ businessId, decisionId }: { businessId: string; decisionId: string }) {
  const [explanation, setExplanation] = useState<DecisionExplanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (explanation || loading) {
      setOpen((v) => !v);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.explainDecision(businessId, decisionId);
      setExplanation(result);
      setOpen(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not load an explanation right now.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <button onClick={load} className="text-sm font-medium text-accent underline underline-offset-4">
        {loading ? "Loading…" : open ? "Hide explanation" : "How did AI reach this decision?"}
      </button>
      {error ? <p className="mt-2 text-sm text-danger">{error}</p> : null}
      {open && explanation ? (
        <div className="mt-4 space-y-4">
          {explanation.explanation.shap_available ? (
            <div>
              <p className="text-sm font-medium text-foreground">What influenced this recommendation</p>
              <ul className="mt-2 space-y-1 text-sm">
                {explanation.explanation.local_factors.map((f) => (
                  <li key={f.feature} className="flex items-center justify-between border-b border-border py-1">
                    <span className="text-muted">{f.label}</span>
                    <span className={f.direction === "increased" ? "text-success" : f.direction === "decreased" ? "text-danger" : "text-muted"}>
                      {f.direction}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-muted">{explanation.explanation.unavailable_reason}</p>
          )}
        </div>
      ) : null}
    </Card>
  );
}
