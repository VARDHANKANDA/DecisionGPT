"use client";

import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { researchApi, type ModelPerformance } from "@/lib/research-api";
import { displayMape } from "@/lib/metric-format";
import { EvaluationSummaryPanel } from "./evaluation-summary";
import { VerifiedResultsPanel } from "./verified-results-panel";
import {
  DataTable,
  EvalEmptyState,
  Metric,
  Panel,
  PageIntro,
  StatGrid,
  fmt,
  fmtInt,
} from "@/components/research-ui";

export default function ModelPerformancePage() {
  const [data, setData] = useState<ModelPerformance | null>(null);
  const [task, setTask] = useState<string>("");
  const [datasetVersion, setDatasetVersion] = useState<string>("");
  const [modelName, setModelName] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  const [busy, setBusy] = useState<string | null>(null);
  const [runMessage, setRunMessage] = useState<string | null>(null);

  const load = useCallback(() => {
    return researchApi
      .modelPerformance({
        task: task || undefined,
        dataset_version: datasetVersion || undefined,
        model_name: modelName || undefined,
      })
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(String(e?.message ?? e)));
  }, [task, datasetVersion, modelName]);

  useEffect(() => {
    void load();
  }, [load]);

  // A safe action: re-scores stored models on their held-out test blocks (trains nothing, calls no external service), then reloads the page data.
  async function runOne(modelId: string) {
    setBusy(modelId);
    setRunMessage(null);
    try {
      const r = await researchApi.runModelEvaluation(modelId);
      setRunMessage(r.status === "evaluated" ? "Evaluation finished: the model was scored on its held-out test block." : `Evaluation ${r.status}: ${r.reason ?? "no reason given"}`);
      await load();
    } catch (e) {
      setRunMessage(`The evaluation request failed: ${String((e as Error)?.message ?? e)}`);
    } finally {
      setBusy(null);
    }
  }

  async function runPending() {
    setBusy("all");
    setRunMessage(null);
    try {
      const r = await researchApi.runPendingEvaluations();
      setRunMessage(`Evaluation finished for ${r.attempted} pending model${r.attempted === 1 ? "" : "s"}: ${r.evaluated} evaluated, ${r.attempted - r.evaluated} could not be evaluated (see each row).`);
      await load();
    } catch (e) {
      setRunMessage(`The evaluation request failed: ${String((e as Error)?.message ?? e)}`);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div>
      <PageIntro
        title="Model Performance"
        subtitle="Aggregated from the real model registry and training history. Every figure is read from a recorded evaluation of a held-out test block, or from a verified re-scoring of the stored model — never from training rows and never typed in. Forecasting and classification metrics are kept separate so incompatible metrics are never compared."
      />

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {!data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : data.empty_state ? (
        <EvalEmptyState message={data.empty_state} />
      ) : (
        <div className="space-y-6">
          <StatGrid>
            <Metric label="Registered models" value={fmtInt(data.summary.registered_models)}
              hint={`${data.summary.active_models} active · ${data.summary.experimental_models} experimental`} />
            <Metric label="Completed training runs" value={fmtInt(data.summary.completed_training_runs)}
              hint={data.summary.failed_training_runs ? `${data.summary.failed_training_runs} failed` : undefined} />
            <Metric
              label="Lowest forecasting MAE (one dataset)"
              value={data.summary.best_forecasting ? fmt(data.summary.best_forecasting.value) : "—"}
              hint={data.summary.best_forecasting?.model ?? data.summary.best_forecasting_note ?? undefined}
            />
            <Metric
              label="Best churn (ROC-AUC)"
              value={data.summary.best_churn ? fmt(data.summary.best_churn.value) : "—"}
              hint={data.summary.best_churn?.model}
            />
          </StatGrid>

          {data.verified_research_results ? (
            <VerifiedResultsPanel results={data.verified_research_results} />
          ) : null}

          {data.evaluation_summary ? (
            <EvaluationSummaryPanel summary={data.evaluation_summary} busy={busy} message={runMessage} onRun={(id) => void runOne(id)} onRunPending={() => void runPending()} />
          ) : (
            <Panel title="Forecast accuracy on held-out test data">
              <p className="text-sm text-muted">The server did not return an evaluation summary, so accuracy cannot be shown. Reload the page; if this persists the backend may be out of date.</p>
            </Panel>
          )}

          <Panel title="Filters">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <label className="flex flex-col gap-1 text-xs text-muted">
                Task
                <select className="input" value={task} onChange={(e) => setTask(e.target.value)}>
                  <option value="">All</option>
                  {data.filters.tasks.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-muted">
                Dataset version
                <select className="input" value={datasetVersion} onChange={(e) => setDatasetVersion(e.target.value)}>
                  <option value="">All</option>
                  {data.filters.dataset_versions.map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-muted">
                Model
                <select className="input" value={modelName} onChange={(e) => setModelName(e.target.value)}>
                  <option value="">All</option>
                  {data.filters.model_names.map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </label>
            </div>
          </Panel>

          {data.forecasting.models.length > 0 ? (
            <Panel title="Forecasting — MAE / RMSE (full metric set: Evaluation metrics)">
              <MetricChart data={data.forecasting.chart} keys={["mae", "rmse"]} />
              <div className="mt-4">
                <DataTable
                  headers={["Model", "Version", "Status", "Dataset", "MAE", "RMSE", "MAPE"]}
                  rows={data.forecasting.models.map((m) => [
                    m.model_name,
                    m.version,
                    m.status,
                    m.dataset_version,
                    fmt(m.metrics.mae),
                    fmt(m.metrics.rmse),
                    displayMape(m.metrics.mape) !== null ? `${fmt(displayMape(m.metrics.mape), 2)}%` : "not reliable",
                  ])}
                />
              </div>
            </Panel>
          ) : null}

          {data.classification.models.length > 0 ? (
            <Panel title="Churn / Classification — Precision / Recall / F1 / ROC-AUC">
              <MetricChart data={data.classification.chart} keys={["precision", "recall", "f1", "roc_auc"]} />
              <div className="mt-4">
                <DataTable
                  headers={["Model", "Version", "Status", "Dataset", "Precision", "Recall", "F1", "ROC-AUC"]}
                  rows={data.classification.models.map((m) => [
                    m.model_name,
                    m.version,
                    m.status,
                    m.dataset_version,
                    fmt(m.metrics.precision),
                    fmt(m.metrics.recall),
                    fmt(m.metrics.f1),
                    fmt(m.metrics.roc_auc),
                  ])}
                />
              </div>
            </Panel>
          ) : null}

          <Panel title="Training history">
            <DataTable
              headers={["When", "Task / model", "Dataset", "Status", "Key metric"]}
              rows={data.training_history.map((r) => [
                r.created_at ? new Date(r.created_at).toLocaleString() : "—",
                `${r.task} / ${r.model_type}`,
                r.dataset_version_label ?? "—",
                r.error_message ? `failed — ${r.error_message}` : r.status,
                r.status === "completed"
                  ? r.task === "forecasting"
                    ? `MAE ${fmt((r.metrics as Record<string, number>).mae, 2)}`
                    : `ROC-AUC ${fmt((r.metrics as Record<string, number>).roc_auc)}`
                  : "—",
              ])}
              empty="No training runs recorded."
            />
          </Panel>
        </div>
      )}
    </div>
  );
}

function MetricChart({
  data,
  keys,
}: {
  data: Record<string, number | string | null>[];
  keys: string[];
}) {
  const colors = ["var(--accent)", "var(--success)", "var(--warning)", "#7c3aed"];
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} angle={-12} textAnchor="end" height={54} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {keys.map((k, i) => (
            <Bar key={k} dataKey={k} fill={colors[i % colors.length]} radius={[3, 3, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
