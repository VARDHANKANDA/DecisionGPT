"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { researchApi, ResearchApiError, type ExperimentRun, type ExperimentType } from "@/lib/research-api";

const EXPERIMENT_TYPES: { value: ExperimentType; label: string; description: string }[] = [
  { value: "forecasting", label: "Forecasting", description: "Retrains naive/linear/XGBoost on platform data." },
  { value: "churn", label: "Churn", description: "Retrains logistic regression/random forest/XGBoost." },
  { value: "digital_twin", label: "Digital Twin Evaluation", description: "Predicted vs. real recorded outcomes, across all businesses." },
  { value: "causal", label: "Causal Evaluation", description: "Synthetic ground-truth causal recovery test." },
  { value: "decision_architecture", label: "Decision Architecture", description: "A/B/C/D comparison on a synthetic scenario." },
  { value: "multi_agent", label: "Multi-Agent Evaluation", description: "Single agent vs. full multi-agent system." },
  { value: "ablation", label: "Ablation Study", description: "Full system vs. each component removed." },
];

export default function ExperimentsPage() {
  const [experimentType, setExperimentType] = useState<ExperimentType>("causal");
  const [seed, setSeed] = useState(42);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ExperimentRun[] | null>(null);
  const [selected, setSelected] = useState<ExperimentRun | null>(null);

  function load() {
    researchApi.listExperiments().then(setRuns);
  }

  useEffect(load, []);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const result = await researchApi.runExperiment(experimentType, { seed });
      setSelected(result);
      load();
    } catch (err) {
      setError(err instanceof ResearchApiError ? err.message : "Could not run this experiment.");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Experiment Runner</h1>
      <p className="mt-1 text-muted">Every run is recorded with its dataset version, seed, and full metrics.</p>

      <div className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5 sm:col-span-2">
            <span className="text-sm font-medium text-foreground">Experiment type</span>
            <select
              value={experimentType}
              onChange={(e) => setExperimentType(e.target.value as ExperimentType)}
              className="input"
            >
              {EXPERIMENT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <span className="text-xs text-muted">
              {EXPERIMENT_TYPES.find((t) => t.value === experimentType)?.description}
            </span>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Random seed</span>
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(Number(e.target.value))}
              className="input"
            />
          </label>
        </div>
        <div className="mt-4">
          <button
            onClick={run}
            disabled={running}
            className="inline-flex items-center justify-center rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition hover:opacity-90 disabled:opacity-50"
          >
            {running ? "Running…" : "Run experiment"}
          </button>
        </div>
        {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div>
          <h2 className="text-sm font-medium text-foreground">History</h2>
          {runs === null ? (
            <p className="mt-2 text-sm text-muted">Loading…</p>
          ) : runs.length === 0 ? (
            <p className="mt-2 text-sm text-muted">No experiments recorded yet.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-2">
              {runs.map((r) => (
                <li key={r.id}>
                  <button
                    onClick={() => setSelected(r)}
                    className={`w-full rounded-xl border px-4 py-3 text-left text-sm transition ${
                      selected?.id === r.id ? "border-accent bg-accent-soft" : "border-border bg-surface hover:bg-muted-surface"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-foreground">{r.experiment_type}</span>
                      <span className="text-xs text-muted">{new Date(r.created_at).toLocaleString("en-IN")}</span>
                    </div>
                    <p className="mt-1 text-xs text-muted">
                      seed {r.random_seed} · dataset {r.dataset_version ?? "—"}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h2 className="text-sm font-medium text-foreground">Result</h2>
          {selected ? <ExperimentDetail run={selected} /> : <p className="mt-2 text-sm text-muted">Select a run to see its metrics.</p>}
        </div>
      </div>
    </div>
  );
}

function ExperimentDetail({ run }: { run: ExperimentRun }) {
  return (
    <div className="mt-3 rounded-xl border border-border bg-surface p-4">
      <p className="text-xs text-muted">
        {run.id} · seed {run.random_seed} · {run.status}
      </p>
      <ExperimentChart run={run} />
      <pre className="mt-3 max-h-[28rem] overflow-auto whitespace-pre-wrap text-xs text-foreground">
        {JSON.stringify(run.metrics_json, null, 2)}
      </pre>
    </div>
  );
}

function ExperimentChart({ run }: { run: ExperimentRun }) {
  const chartData = buildChartData(run);
  if (!chartData) return null;

  return (
    <div className="mt-3 h-56 rounded-lg border border-border bg-muted-surface p-2">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={chartData.rows}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-15} textAnchor="end" height={50} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip />
          <Bar dataKey="value" fill="var(--accent)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <p className="text-center text-xs text-muted">{chartData.label}</p>
    </div>
  );
}

function buildChartData(run: ExperimentRun): { rows: { name: string; value: number }[]; label: string } | null {
  const metrics = run.metrics_json as Record<string, unknown>;

  if (run.experiment_type === "decision_architecture") {
    const results = metrics.results as { label: string; risk_adjusted_score: number }[] | undefined;
    if (!results) return null;
    return {
      rows: results.map((r) => ({ name: r.label, value: r.risk_adjusted_score })),
      label: "Risk-adjusted score by architecture (₹)",
    };
  }

  if (run.experiment_type === "ablation") {
    const comparisons = metrics.comparisons as { component_removed: string; delta_goal_achievement: number }[] | undefined;
    if (!comparisons) return null;
    return {
      rows: comparisons.map((c) => ({ name: c.component_removed, value: c.delta_goal_achievement })),
      label: "Goal-achievement delta lost by removing each component",
    };
  }

  if (run.experiment_type === "forecasting") {
    return {
      rows: Object.entries(metrics).map(([name, m]) => ({
        name,
        value: (m as { mae: number }).mae,
      })),
      label: "MAE by model (lower is better)",
    };
  }

  if (run.experiment_type === "churn") {
    return {
      rows: Object.entries(metrics).map(([name, m]) => ({
        name,
        value: (m as { roc_auc: number }).roc_auc,
      })),
      label: "ROC-AUC by model (higher is better)",
    };
  }

  if (run.experiment_type === "causal") {
    const rows: { name: string; value: number }[] = [];
    if (typeof metrics.precision === "number") rows.push({ name: "Precision", value: metrics.precision });
    if (typeof metrics.recall === "number") rows.push({ name: "Recall", value: metrics.recall });
    if (rows.length === 0) return null;
    return { rows, label: "Causal recovery precision/recall" };
  }

  return null;
}
