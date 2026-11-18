"use client";

import { useEffect, useState } from "react";
import { researchApi, ResearchApiError, type ExperimentRun } from "@/lib/research-api";
import { StatusPill } from "@/components/research-ui";

interface AblationComparison {
  component_removed: string;
  config: string;
  full_goal_achievement: number;
  ablated_goal_achievement: number;
  delta_goal_achievement: number;
  full_risk_adjusted_score: number;
  ablated_risk_adjusted_score: number;
  delta_risk_adjusted_score: number;
  full_confidence: number | null;
  ablated_confidence: number | null;
  delta_confidence: number | null;
  note: string;
}

interface AblationConfig {
  config: string;
  label: string;
  components_removed: string[];
  selected_strategy_name: string | null;
  expected_benefit: number;
  risk_adjusted_score: number;
  goal_achievement: number;
  confidence: number | null;
  note: string;
}

export default function AblationPage() {
  const [seed, setSeed] = useState(42);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ExperimentRun[] | null>(null);
  const [selected, setSelected] = useState<ExperimentRun | null>(null);

  function load() {
    researchApi.listExperiments("ablation").then(setRuns);
  }
  useEffect(load, []);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const r = await researchApi.runExperiment("ablation", { seed });
      setSelected(r);
      load();
    } catch (e) {
      setError(e instanceof ResearchApiError ? e.message : "Ablation run failed.");
      load();
    } finally {
      setRunning(false);
    }
  }

  const metrics = (selected?.metrics_json ?? {}) as {
    configs?: AblationConfig[];
    comparisons?: AblationComparison[];
    goal_target_percent?: number;
    model_versions?: Record<string, string>;
  };

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Ablation Studies</h1>
      <p className="mt-1 text-muted">
        Runs the <strong>real</strong> decision pipeline on one controlled synthetic scenario, once at full
        strength (A) and once with each component switched off (B–F). Every delta is measured, not fabricated.
      </p>

      <div className="mt-6 flex items-end gap-3 rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted">Random seed</span>
          <input
            type="number"
            value={seed}
            onChange={(e) => setSeed(Number(e.target.value))}
            className="input w-32"
          />
        </label>
        <button
          onClick={run}
          disabled={running}
          className="rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
        >
          {running ? "Running A–F…" : "Run ablation study"}
        </button>
      </div>
      {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}

      {runs && runs.length > 0 ? (
        <div className="mt-6">
          <p className="text-xs text-muted">Recorded runs</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {runs.map((r) => (
              <button
                key={r.id}
                onClick={() => researchApi.getExperiment(r.id).then(setSelected)}
                className={`rounded-full border px-3 py-1 text-xs ${
                  selected?.id === r.id ? "border-accent text-accent" : "border-border text-muted"
                }`}
              >
                seed {r.random_seed} · {new Date(r.created_at).toLocaleDateString()} · <StatusPill status={r.status} />
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {selected && metrics.configs ? (
        <>
          <h2 className="mt-8 text-sm font-medium text-foreground">
            Configurations (goal target {metrics.goal_target_percent}% revenue)
          </h2>
          <div className="mt-3 overflow-x-auto rounded-2xl border border-border bg-surface shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="px-4 py-2 font-medium">Config</th>
                  <th className="px-4 py-2 font-medium">Selected strategy</th>
                  <th className="px-4 py-2 text-right font-medium">Expected benefit</th>
                  <th className="px-4 py-2 text-right font-medium">Risk-adjusted</th>
                  <th className="px-4 py-2 text-right font-medium">Goal achievement</th>
                  <th className="px-4 py-2 text-right font-medium">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {metrics.configs.map((c) => (
                  <tr key={c.config} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 font-medium">
                      {c.config}. {c.label}
                    </td>
                    <td className="px-4 py-2 text-muted">{c.selected_strategy_name ?? "— none —"}</td>
                    <td className="px-4 py-2 text-right">₹{c.expected_benefit.toLocaleString("en-IN")}</td>
                    <td className="px-4 py-2 text-right">{c.risk_adjusted_score.toLocaleString("en-IN")}</td>
                    <td className="px-4 py-2 text-right">{(c.goal_achievement * 100).toFixed(0)}%</td>
                    <td className="px-4 py-2 text-right">
                      {c.confidence !== null ? `${(c.confidence * 100).toFixed(0)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="mt-8 text-sm font-medium text-foreground">Δ vs Full DecisionGPT</h2>
          <div className="mt-3 flex flex-col gap-3">
            {(metrics.comparisons ?? []).map((cmp) => (
              <div key={cmp.config} className="rounded-2xl border border-border bg-surface p-4 text-sm shadow-sm">
                <p className="font-medium text-foreground">
                  {cmp.config}. {cmp.component_removed}
                </p>
                <p className="mt-1 text-muted">
                  Δ goal achievement {(cmp.delta_goal_achievement * 100).toFixed(1)}pp · Δ risk-adjusted{" "}
                  {cmp.delta_risk_adjusted_score.toLocaleString("en-IN")} ·{" "}
                  {cmp.delta_confidence !== null
                    ? `Δ confidence ${(cmp.delta_confidence * 100).toFixed(1)}pp`
                    : "confidence n/a"}
                </p>
                <p className="mt-1 text-xs text-muted">{cmp.note}</p>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
