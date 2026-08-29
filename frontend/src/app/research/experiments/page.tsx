"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { researchApi, ResearchApiError, type ExperimentRun, type ExperimentType } from "@/lib/research-api";

const EXPERIMENT_TYPES: { value: ExperimentType; label: string; description: string }[] = [
  { value: "forecasting", label: "Forecasting", description: "Retrains naive/linear/XGBoost on platform data." },
  { value: "churn", label: "Churn", description: "Retrains logistic regression/random forest/XGBoost." },
  { value: "digital_twin", label: "Digital Twin Evaluation", description: "Predicted vs. real recorded outcomes, across all businesses." },
  { value: "causal", label: "Causal Evaluation", description: "Synthetic ground-truth causal recovery test." },
  { value: "decision_architecture", label: "Decision Architecture (legacy 1-scenario)", description: "A/B/C/D comparison on a single synthetic scenario. Preserved for comparison." },
  { value: "multi_agent", label: "Multi-Agent Evaluation", description: "Single agent vs. full multi-agent system." },
  { value: "ablation", label: "Ablation Study (legacy 1-scenario)", description: "Full system vs. each component removed, single scenario." },
  { value: "multi_scenario_architecture", label: "Decision Architecture — multi-scenario", description: "A/B/C/D across 12 scenarios x 5 seeds, aggregated with 95% CI + paired Wilcoxon." },
  { value: "multi_scenario_ablation", label: "Ablation — multi-scenario", description: "A-F across 12 scenarios x 5 seeds, mean delta vs Full + CI." },
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
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">History</h2>
            <button
              onClick={async () => {
                const m = await researchApi.experimentManifest();
                const blob = new Blob([JSON.stringify(m, null, 2)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "experiment_manifest.json";
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="text-xs font-medium text-accent underline underline-offset-4"
            >
              Download reproducibility manifest
            </button>
          </div>
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
  const isMulti =
    run.experiment_type === "multi_scenario_architecture" ||
    run.experiment_type === "multi_scenario_ablation";
  return (
    <div className="mt-3 rounded-xl border border-border bg-surface p-4">
      <p className="text-xs text-muted">
        {run.id} · seed {run.random_seed} · {run.status}
      </p>
      <ExperimentChart run={run} />
      {isMulti && <MultiScenarioDetail run={run} />}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs font-medium text-accent">Raw metrics JSON</summary>
        <pre className="mt-2 max-h-[28rem] overflow-auto whitespace-pre-wrap text-xs text-foreground">
          {JSON.stringify(run.metrics_json, null, 2)}
        </pre>
      </details>
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

interface MultiMetrics {
  scenario_count?: number;
  seed_count?: number;
  evaluation_count?: number;
  aggregation_method?: string;
  statistical_method?: string;
  aggregates?: Record<string, Record<string, { mean?: number; std?: number; ci95?: number[] | null; n?: number } | null> & { config_label?: string; component_removed?: string }>;
  paired?: Record<string, { comparison?: string; mean_difference?: number; median_difference?: number; full_wins?: number; ties?: number; full_losses?: number; p_value?: number | null; interpretation?: string }>;
  robustness?: Record<string, { vs_full_wins?: number; vs_full_ties?: number; vs_full_losses?: number; best?: number; worst?: number; median?: number; std?: number }>;
  failure_mode_analysis?: { scenario_id: string; seed: number; goal_objective: string; selected_strategy: string | null; goal_achievement: number; confidence: number | null; associated_factors: string[] }[];
  observations?: Record<string, unknown>[];
}

function MultiScenarioDetail({ run }: { run: ExperimentRun }) {
  const m = run.metrics_json as MultiMetrics;
  const isArch = run.experiment_type === "multi_scenario_architecture";
  const groups = isArch ? ["A", "B", "C", "D"] : ["A", "B", "C", "D", "E", "F"];
  const obs = m.observations ?? [];
  const groupKey = isArch ? "architecture" : "config";

  const scenarioOpts = Array.from(new Set(obs.map((o) => String(o.scenario_id)))).sort();
  const seedOpts = Array.from(new Set(obs.map((o) => Number(o.seed)))).sort((a, b) => a - b);
  const [fScenario, setFScenario] = useState("all");
  const [fSeed, setFSeed] = useState("all");
  const [fGroup, setFGroup] = useState("all");
  const filtered = obs.filter(
    (o) =>
      (fScenario === "all" || o.scenario_id === fScenario) &&
      (fSeed === "all" || String(o.seed) === fSeed) &&
      (fGroup === "all" || o[groupKey] === fGroup),
  );

  const num = (v: number | undefined | null) => (v === undefined || v === null ? "—" : v.toFixed(4));

  return (
    <div className="mt-4 flex flex-col gap-4">
      <div className="rounded-lg border border-border bg-muted-surface p-3 text-xs text-muted">
        <span className="font-medium text-foreground">{m.scenario_count} scenarios × {m.seed_count} seeds = {m.evaluation_count} evaluations.</span>{" "}
        {m.aggregation_method} · {m.statistical_method}
      </div>

      {/* aggregate table */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-xs">
          <thead className="bg-muted-surface text-muted">
            <tr>
              <th className="px-2 py-1 text-left">{isArch ? "Architecture" : "Config"}</th>
              <th className="px-2 py-1 text-right">Mean goal ach.</th>
              <th className="px-2 py-1 text-right">Std</th>
              <th className="px-2 py-1 text-right">95% CI</th>
              {!isArch && <th className="px-2 py-1 text-right">Mean Δ vs Full</th>}
              <th className="px-2 py-1 text-right">Mean risk-adj</th>
              <th className="px-2 py-1 text-right">Mean conf</th>
              <th className="px-2 py-1 text-right">N</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => {
              const a = m.aggregates?.[g] ?? {};
              const ga = a.goal_achievement as { mean?: number; std?: number; ci95?: number[] | null; n?: number } | null;
              const ra = a.risk_adjusted_score as { mean?: number } | null;
              const cf = a.confidence as { mean?: number } | null;
              const dg = a.delta_goal_achievement_vs_full as { mean?: number } | null;
              return (
                <tr key={g} className="border-t border-border">
                  <td className="px-2 py-1 text-foreground">{g}{a.config_label ? ` — ${a.config_label}` : ""}</td>
                  <td className="px-2 py-1 text-right">{num(ga?.mean)}</td>
                  <td className="px-2 py-1 text-right">{num(ga?.std)}</td>
                  <td className="px-2 py-1 text-right">{ga?.ci95 ? `[${ga.ci95[0].toFixed(3)}, ${ga.ci95[1].toFixed(3)}]` : "n/a"}</td>
                  {!isArch && <td className="px-2 py-1 text-right">{num(dg?.mean)}</td>}
                  <td className="px-2 py-1 text-right">{ra?.mean != null ? ra.mean.toFixed(1) : "—"}</td>
                  <td className="px-2 py-1 text-right">{cf?.mean != null ? cf.mean.toFixed(3) : "n/a"}</td>
                  <td className="px-2 py-1 text-right">{ga?.n ?? 0}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* paired comparisons */}
      {m.paired && (
        <div className="flex flex-col gap-2">
          {Object.entries(m.paired).map(([k, p]) => (
            <div key={k} className="rounded-lg border border-border bg-surface p-3 text-xs">
              <p className="font-medium text-foreground">{p.comparison ?? k}</p>
              <p className="mt-1 text-muted">
                mean diff {num(p.mean_difference)} · median {num(p.median_difference)} · wins/ties/losses{" "}
                {p.full_wins}/{p.ties}/{p.full_losses} · p={p.p_value == null ? "n/a" : p.p_value.toFixed(4)}
              </p>
              <p className="mt-1 text-muted">{p.interpretation}</p>
            </div>
          ))}
        </div>
      )}

      {/* robustness */}
      {isArch && m.robustness && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="bg-muted-surface text-muted">
              <tr>
                <th className="px-2 py-1 text-left">vs Full</th>
                <th className="px-2 py-1 text-right">wins</th>
                <th className="px-2 py-1 text-right">ties</th>
                <th className="px-2 py-1 text-right">losses</th>
              </tr>
            </thead>
            <tbody>
              {["A", "B", "C"].map((g) => {
                const r = m.robustness?.[g];
                if (!r) return null;
                return (
                  <tr key={g} className="border-t border-border">
                    <td className="px-2 py-1 text-foreground">{g}</td>
                    <td className="px-2 py-1 text-right">{r.vs_full_wins}</td>
                    <td className="px-2 py-1 text-right">{r.vs_full_ties}</td>
                    <td className="px-2 py-1 text-right">{r.vs_full_losses}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {m.robustness.D_distribution && (
            <p className="px-2 py-1 text-xs text-muted">
              Full distribution — best {num(m.robustness.D_distribution.best)} · worst {num(m.robustness.D_distribution.worst)} · median{" "}
              {num(m.robustness.D_distribution.median)} · std {num(m.robustness.D_distribution.std)}
            </p>
          )}
        </div>
      )}

      {/* failure-mode analysis */}
      {isArch && m.failure_mode_analysis && m.failure_mode_analysis.length > 0 && (
        <div className="rounded-lg border border-border bg-surface p-3 text-xs">
          <p className="font-medium text-foreground">Failure-mode analysis (Full DecisionGPT, bottom-tercile goal achievement — correlational)</p>
          <ul className="mt-1 flex flex-col gap-1 text-muted">
            {m.failure_mode_analysis.slice(0, 20).map((f, i) => (
              <li key={i}>
                {f.scenario_id}/{f.seed} · {f.goal_objective} · strat {f.selected_strategy ?? "none"} · ga {f.goal_achievement.toFixed(3)} · conf{" "}
                {f.confidence == null ? "n/a" : f.confidence.toFixed(3)} — {f.associated_factors.join("; ")}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* filterable per-observation detail */}
      <div>
        <div className="mb-2 flex flex-wrap gap-2 text-xs">
          <select value={fScenario} onChange={(e) => setFScenario(e.target.value)} className="rounded border border-border bg-surface px-2 py-1">
            <option value="all">All scenarios</option>
            {scenarioOpts.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={fSeed} onChange={(e) => setFSeed(e.target.value)} className="rounded border border-border bg-surface px-2 py-1">
            <option value="all">All seeds</option>
            {seedOpts.map((s) => <option key={s} value={String(s)}>seed {s}</option>)}
          </select>
          <select value={fGroup} onChange={(e) => setFGroup(e.target.value)} className="rounded border border-border bg-surface px-2 py-1">
            <option value="all">All {isArch ? "architectures" : "configs"}</option>
            {groups.map((g) => <option key={g} value={g}>{g}</option>)}
          </select>
          <span className="self-center text-muted">{filtered.length} of {obs.length} observations</span>
        </div>
        <div className="max-h-72 overflow-auto rounded-lg border border-border">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-muted-surface text-muted">
              <tr>
                <th className="px-2 py-1 text-left">{isArch ? "Arch" : "Cfg"}</th>
                <th className="px-2 py-1 text-left">Scenario</th>
                <th className="px-2 py-1 text-right">Seed</th>
                <th className="px-2 py-1 text-left">Strategy</th>
                <th className="px-2 py-1 text-right">Goal ach.</th>
                <th className="px-2 py-1 text-right">Risk-adj</th>
                <th className="px-2 py-1 text-right">Conf</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((o, i) => (
                <tr key={i} className="border-t border-border">
                  <td className="px-2 py-1 text-foreground">{String(o[groupKey])}</td>
                  <td className="px-2 py-1">{String(o.scenario_id)}</td>
                  <td className="px-2 py-1 text-right">{String(o.seed)}</td>
                  <td className="px-2 py-1">{o.selected_strategy ? String(o.selected_strategy) : "—"}</td>
                  <td className="px-2 py-1 text-right">{Number(o.goal_achievement).toFixed(4)}</td>
                  <td className="px-2 py-1 text-right">{Number(o.risk_adjusted_score).toFixed(1)}</td>
                  <td className="px-2 py-1 text-right">{o.confidence == null ? "n/a" : Number(o.confidence).toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function buildChartData(run: ExperimentRun): { rows: { name: string; value: number }[]; label: string } | null {
  const metrics = run.metrics_json as Record<string, unknown>;

  if (run.experiment_type === "multi_scenario_architecture") {
    const agg = (metrics.aggregates ?? {}) as Record<string, { goal_achievement?: { mean?: number } | null }>;
    const rows = ["A", "B", "C", "D"]
      .map((g) => ({ name: g, value: agg[g]?.goal_achievement?.mean ?? 0 }));
    return { rows, label: "Mean goal achievement by architecture (12 scenarios × 5 seeds)" };
  }

  if (run.experiment_type === "multi_scenario_ablation") {
    const agg = (metrics.aggregates ?? {}) as Record<string, { delta_goal_achievement_vs_full?: { mean?: number } | null }>;
    const rows = ["B", "C", "D", "E", "F"]
      .map((g) => ({ name: g, value: agg[g]?.delta_goal_achievement_vs_full?.mean ?? 0 }));
    return { rows, label: "Mean Δ goal achievement vs Full (removing each component)" };
  }

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
