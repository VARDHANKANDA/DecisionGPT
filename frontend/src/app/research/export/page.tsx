"use client";

import { useEffect, useState } from "react";
import {
  researchApi,
  ResearchApiError,
  type ExperimentRun,
  type ExportFormat,
  type ExportTable,
} from "@/lib/research-api";

const TABLES: { value: ExportTable; label: string; needsExperiment: boolean }[] = [
  { value: "forecasting_performance", label: "Forecasting performance", needsExperiment: false },
  { value: "churn_performance", label: "Churn performance", needsExperiment: false },
  { value: "decision_architecture", label: "Decision architecture comparison", needsExperiment: true },
  { value: "ablation", label: "Ablation study", needsExperiment: true },
  { value: "causal_evaluation", label: "Causal evaluation", needsExperiment: true },
  { value: "digital_twin_evaluation", label: "Digital Twin evaluation", needsExperiment: true },
];

const FORMATS: ExportFormat[] = ["csv", "json", "markdown", "latex"];

export default function ExportPage() {
  const [table, setTable] = useState<ExportTable>("forecasting_performance");
  const [format, setFormat] = useState<ExportFormat>("markdown");
  const [experiments, setExperiments] = useState<ExperimentRun[]>([]);
  const [experimentId, setExperimentId] = useState<string>("");
  const [output, setOutput] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    researchApi.listExperiments().then(setExperiments);
  }, []);

  const tableInfo = TABLES.find((t) => t.value === table)!;
  const matchingExperiments = experiments.filter((e) => e.experiment_type === tableToExperimentType(table));

  async function generate() {
    setLoading(true);
    setError(null);
    setOutput(null);
    try {
      const result = await researchApi.exportTable(table, format, experimentId || undefined);
      setOutput(result);
    } catch (err) {
      setError(err instanceof ResearchApiError ? err.message : "Could not generate that export.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Paper-ready exports</h1>
      <p className="mt-1 text-muted">CSV, JSON, Markdown, and LaTeX — generated only from recorded data.</p>

      <div className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Table</span>
            <select value={table} onChange={(e) => setTable(e.target.value as ExportTable)} className="input">
              {TABLES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          {tableInfo.needsExperiment ? (
            <label className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-foreground">Experiment run</span>
              <select value={experimentId} onChange={(e) => setExperimentId(e.target.value)} className="input">
                <option value="">Select a run…</option>
                {matchingExperiments.map((e) => (
                  <option key={e.id} value={e.id}>
                    {new Date(e.created_at).toLocaleString("en-IN")} (seed {e.random_seed})
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <div />
          )}

          <label className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">Format</span>
            <select value={format} onChange={(e) => setFormat(e.target.value as ExportFormat)} className="input">
              {FORMATS.map((f) => (
                <option key={f} value={f}>
                  {f.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-4">
          <button
            onClick={generate}
            disabled={loading || (tableInfo.needsExperiment && !experimentId)}
            className="inline-flex items-center justify-center rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground transition hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Generating…" : "Generate"}
          </button>
        </div>
        {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
      </div>

      {output !== null ? (
        <div className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-medium text-foreground">Output</h2>
            <button
              onClick={() => navigator.clipboard.writeText(output)}
              className="text-sm font-medium text-accent underline underline-offset-4"
            >
              Copy
            </button>
          </div>
          <pre className="mt-3 max-h-[28rem] overflow-auto whitespace-pre-wrap text-xs text-foreground">{output || "(no rows)"}</pre>
        </div>
      ) : null}
    </div>
  );
}

function tableToExperimentType(table: ExportTable): string | null {
  const map: Record<ExportTable, string | null> = {
    forecasting_performance: null,
    churn_performance: null,
    decision_architecture: "decision_architecture",
    ablation: "ablation",
    causal_evaluation: "causal",
    digital_twin_evaluation: "digital_twin",
  };
  return map[table];
}
