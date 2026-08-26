"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { researchApi, type ModelPerformance } from "@/lib/research-api";
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

  useEffect(() => {
    researchApi
      .modelPerformance({
        task: task || undefined,
        dataset_version: datasetVersion || undefined,
        model_name: modelName || undefined,
      })
      .then(setData)
      .catch((e) => setError(String(e?.message ?? e)));
  }, [task, datasetVersion, modelName]);

  return (
    <div>
      <PageIntro
        title="Model Performance"
        subtitle="Aggregated from the real MLModel registry and TrainingRun history. Every metric is read from a recorded training/evaluation run — nothing is computed or hard-coded here. Forecasting and classification metrics are kept separate so incompatible metrics are never compared."
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
              label="Best forecasting (MAE)"
              value={data.summary.best_forecasting ? fmt(data.summary.best_forecasting.value) : "—"}
              hint={data.summary.best_forecasting?.model}
            />
            <Metric
              label="Best churn (ROC-AUC)"
              value={data.summary.best_churn ? fmt(data.summary.best_churn.value) : "—"}
              hint={data.summary.best_churn?.model}
            />
          </StatGrid>

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
            <Panel title="Forecasting — MAE / RMSE / MAPE">
              <MetricChart data={data.forecasting.chart} keys={["mae", "rmse", "mape"]} />
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
                    m.metrics.mape != null ? `${fmt(m.metrics.mape, 2)}%` : "—",
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
