"use client";

import { useEffect, useState } from "react";
import {
  researchApi,
  ResearchApiError,
  type DatasetsResponse,
  type TrainingRun,
} from "@/lib/research-api";
import { StatusPill } from "@/app/research/page";

export default function TrainingCenterPage() {
  const [tasks, setTasks] = useState<Record<string, { model_types: string[]; metrics: string[] }> | null>(null);
  const [datasets, setDatasets] = useState<DatasetsResponse | null>(null);
  const [runs, setRuns] = useState<TrainingRun[] | null>(null);

  const [task, setTask] = useState("forecasting");
  const [modelType, setModelType] = useState("xgboost");
  const [datasetVersionId, setDatasetVersionId] = useState<string>("");
  const [seed, setSeed] = useState(42);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastRun, setLastRun] = useState<TrainingRun | null>(null);

  function loadRuns() {
    researchApi.listTrainingRuns().then(setRuns);
  }

  useEffect(() => {
    researchApi.trainingTasks().then(setTasks);
    researchApi.listDatasets().then(setDatasets);
    loadRuns();
  }, []);

  useEffect(() => {
    // Keep model_type valid for the selected task.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (tasks && tasks[task]) setModelType(tasks[task].model_types[0]);
  }, [task, tasks]);

  const compatibleVersions =
    datasets?.uploaded
      .filter((d) => d.domain === task || d.domain === "other")
      .flatMap((d) => d.versions.map((v) => ({ ...v, datasetName: d.name }))) ?? [];

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setLastRun(null);
    try {
      const r = await researchApi.runTraining({
        task,
        model_type: modelType,
        dataset_version_id: datasetVersionId || undefined,
        seed,
      });
      setLastRun(r);
      loadRuns();
    } catch (err) {
      setError(err instanceof ResearchApiError ? err.message : "Training failed.");
      loadRuns();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Training Center</h1>
      <p className="mt-1 text-muted">
        Trains a real model on a registered dataset (or the bundled platform dataset) using the exact
        ml/training code. New models are registered as <strong>experimental</strong> and do not affect the
        production pipeline until promoted in the Model Registry.
      </p>

      <form onSubmit={run} className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Task</span>
            <select value={task} onChange={(e) => setTask(e.target.value)} className="input">
              {tasks &&
                Object.keys(tasks).map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Model type</span>
            <select value={modelType} onChange={(e) => setModelType(e.target.value)} className="input">
              {tasks?.[task]?.model_types.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm sm:col-span-1">
            <span className="text-muted">Dataset</span>
            <select
              value={datasetVersionId}
              onChange={(e) => setDatasetVersionId(e.target.value)}
              className="input"
            >
              <option value="">Bundled platform dataset</option>
              {compatibleVersions.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.datasetName} v{v.version} ({v.row_count} rows)
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted">Seed</span>
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
            type="submit"
            disabled={busy}
            className="rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Training…" : "Start training"}
          </button>
        </div>
        {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
        {lastRun ? (
          <div className="mt-4 rounded-xl bg-muted-surface p-4 text-sm">
            <p className="font-medium text-foreground">
              {lastRun.model_name} {lastRun.model_version} — <StatusPill status={lastRun.status} />
            </p>
            <p className="mt-1 text-muted">
              {Object.entries(lastRun.metrics_json)
                .filter(([k]) => !k.endsWith("_rows"))
                .map(([k, v]) => `${k}: ${typeof v === "number" ? v.toFixed(3) : v}`)
                .join("  ·  ")}
            </p>
          </div>
        ) : null}
      </form>

      <h2 className="mt-10 text-sm font-medium text-foreground">Training runs</h2>
      <div className="mt-3 overflow-x-auto rounded-2xl border border-border bg-surface shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="px-4 py-2 font-medium">When</th>
              <th className="px-4 py-2 font-medium">Task / model</th>
              <th className="px-4 py-2 font-medium">Dataset</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Key metric</th>
            </tr>
          </thead>
          <tbody>
            {(runs ?? []).map((r) => (
              <tr key={r.id} className="border-b border-border last:border-0">
                <td className="px-4 py-2 text-muted">{new Date(r.created_at).toLocaleString()}</td>
                <td className="px-4 py-2">
                  {r.task} / {r.model_type}
                </td>
                <td className="px-4 py-2 text-muted">{r.dataset_version_label ?? "—"}</td>
                <td className="px-4 py-2">
                  <StatusPill status={r.status} />
                  {r.error_message ? (
                    <span className="ml-2 text-xs text-danger">{r.error_message}</span>
                  ) : null}
                </td>
                <td className="px-4 py-2">
                  {r.status === "completed"
                    ? r.task === "forecasting"
                      ? `MAE ${Number(r.metrics_json.mae).toFixed(2)}`
                      : `ROC-AUC ${Number(r.metrics_json.roc_auc).toFixed(3)}`
                    : "—"}
                </td>
              </tr>
            ))}
            {runs && runs.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-muted">
                  No training runs yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
