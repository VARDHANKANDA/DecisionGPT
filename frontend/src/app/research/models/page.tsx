"use client";

import { useEffect, useState } from "react";
import { researchApi, ResearchApiError, type ModelEntry } from "@/lib/research-api";

const num = (v: unknown) => (typeof v === "number" ? v.toFixed(3) : "—");

export default function ModelRegistryPage() {
  const [models, setModels] = useState<ModelEntry[] | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    researchApi.listModels().then(setModels);
  }
  useEffect(load, []);

  async function sync() {
    setSyncing(true);
    try {
      await researchApi.syncModels();
      load();
    } finally {
      setSyncing(false);
    }
  }

  async function act(id: string, fn: (id: string) => Promise<unknown>) {
    setBusyId(id);
    setError(null);
    try {
      await fn(id);
      load();
    } catch (e) {
      setError(e instanceof ResearchApiError ? e.message : "Action failed.");
    } finally {
      setBusyId(null);
    }
  }

  const byName = new Map<string, ModelEntry[]>();
  for (const m of models ?? []) {
    if (!byName.has(m.model_name)) byName.set(m.model_name, []);
    byName.get(m.model_name)!.push(m);
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Model Registry</h1>
          <p className="mt-1 text-muted">
            Every metric is from a real evaluation run. Only <strong>active</strong> models are used by the
            production DecisionGPT pipeline.
          </p>
        </div>
        <button
          onClick={sync}
          disabled={syncing}
          className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium hover:bg-muted-surface disabled:opacity-50"
        >
          {syncing ? "Syncing…" : "Sync CLI manifests"}
        </button>
      </div>

      {error ? <p className="mt-4 text-sm text-danger">{error}</p> : null}
      {models === null ? (
        <p className="mt-6 text-sm text-muted">Loading…</p>
      ) : (
        <div className="mt-6 flex flex-col gap-6">
          {[...byName.entries()].map(([name, rows]) => (
            <div key={name} className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <h2 className="text-sm font-medium text-foreground">{name}</h2>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-muted">
                      <th className="py-2 font-medium">Version</th>
                      <th className="py-2 font-medium">Status</th>
                      <th className="py-2 font-medium">Source</th>
                      <th className="py-2 font-medium">Dataset</th>
                      <th className="py-2 text-right font-medium">Metrics</th>
                      <th className="py-2 text-right font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((m) => {
                      const mk = m.metrics_json as Record<string, number>;
                      const metricStr = m.model_type.startsWith("forecasting_")
                        ? `MAE ${num(mk.mae)} · RMSE ${num(mk.rmse)} · MAPE ${num(mk.mape)}`
                        : `P ${num(mk.precision)} · R ${num(mk.recall)} · F1 ${num(mk.f1)} · AUC ${num(mk.roc_auc)}`;
                      return (
                        <tr key={m.id} className="border-b border-border last:border-0">
                          <td className="py-2">{m.version}</td>
                          <td className="py-2">
                            <StatusBadge status={m.status} />
                          </td>
                          <td className="py-2 text-muted">{m.source ?? "cli"}</td>
                          <td className="py-2 text-muted">{m.dataset_version}</td>
                          <td className="py-2 text-right text-muted">{metricStr}</td>
                          <td className="py-2 text-right">
                            {m.status !== "active" ? (
                              <button
                                onClick={() => act(m.id, researchApi.promoteModel)}
                                disabled={busyId === m.id}
                                className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted-surface disabled:opacity-50"
                              >
                                Promote
                              </button>
                            ) : null}
                            {m.status !== "archived" ? (
                              <button
                                onClick={() => act(m.id, researchApi.archiveModel)}
                                disabled={busyId === m.id}
                                className="ml-2 rounded-full border border-border px-3 py-1 text-xs hover:bg-muted-surface disabled:opacity-50"
                              >
                                Archive
                              </button>
                            ) : null}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "active"
      ? "bg-success-soft text-success"
      : status === "experimental"
        ? "bg-accent-soft text-accent"
        : "bg-muted-surface text-muted";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}
