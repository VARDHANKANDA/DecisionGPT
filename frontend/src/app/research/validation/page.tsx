"use client";

import { useEffect, useState } from "react";
import { researchApi, type AgentEvaluation, type PaperResults } from "@/lib/research-api";

export default function ValidationPage() {
  const [paper, setPaper] = useState<PaperResults | null>(null);
  const [agents, setAgents] = useState<AgentEvaluation | null>(null);

  useEffect(() => {
    Promise.allSettled([researchApi.paperResults(), researchApi.agentEvaluation()]).then(([p, a]) => {
      if (p.status === "fulfilled") setPaper(p.value);
      if (a.status === "fulfilled") setAgents(a.value);
    });
  }, []);

  const t2 = paper?.tables.find((t) => t.key === "digital_twin_evaluation");
  const rmg = agents?.risk_manager_generalization ?? null;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Validation</h1>
        <p className="mt-1 text-sm text-muted">
          Real-data, real-LLM and real-intervention status. The controlled synthetic suite is not
          real-world validation.
        </p>
      </header>

      <div className="grid gap-3 md:grid-cols-3">
        <Card
          title="Real Indian SME outcomes"
          big="0"
          state="NOT READY"
          body={t2?.missing_reason ?? "Table 2 becomes available at ≥ 5 genuine matched real-SME outcome records."}
        />
        <Card title="Real LLM" big="—" state="BLOCKED" body="No LLM provider is configured. A real LLM would affect goal parsing and narration only — not agent scores or strategy selection." />
        <Card title="Causal intervention evidence" big="0" state="NOT READY" body="CAUSALLY_VALIDATED = 0. No real intervention outcomes have been collected." />
      </div>

      <section className="rounded-xl border border-border bg-surface p-5">
        <h2 className="text-sm font-medium text-foreground">Real-data probe — Risk Manager on Benroshan e-commerce</h2>
        <ul className="mt-2 space-y-1 text-sm text-muted">
          <li>
            Sub-series by price-variance regime:{" "}
            {rmg?.regime_counts
              ? Object.entries(rmg.regime_counts).map(([k, v]) => `${k.replace("_VARIANCE", "").toLowerCase()} ${v}`).join(" · ")
              : "3 low · 11 moderate · 9 high"}
          </li>
          <li>
            R0 vs R1 risk score:{" "}
            <span className="font-medium text-foreground">
              identical on {rmg?.risk_regime_overall?.n_rows ?? 184}/{rmg?.risk_regime_overall?.n_rows ?? 184} rows
            </span>
          </li>
          <li>External-validation verdict: <span className="font-medium text-foreground">{rmg?.external_validation?.verdict ?? "PROMISING BUT NOT VALIDATED"}</span></li>
        </ul>
        <p className="mt-3 text-sm text-foreground">
          The low-variance pathology R3 targets does not arise on this real implied-price data, so R3&apos;s
          benefit could not be confirmed. Nothing regressed. Production stays R0 / D0.
        </p>
      </section>

      <p className="rounded-lg border border-border bg-muted-surface/40 px-4 py-3 text-sm font-medium text-foreground">
        Overall: the evidence base supports a controlled evaluation study, not validation of DecisionGPT on
        Indian SMEs.
      </p>
    </div>
  );
}

function Card({ title, big, state, body }: { title: string; big: string; state: string; body: string }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-muted-surface/40 p-5">
      <p className="text-sm font-medium text-foreground">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-foreground tabular-nums">{big}</p>
      <span className="mt-1 inline-block rounded-full bg-surface px-2 py-0.5 text-xs font-semibold text-muted">
        {state}
      </span>
      <p className="mt-2 text-xs leading-snug text-muted">{body}</p>
    </div>
  );
}
