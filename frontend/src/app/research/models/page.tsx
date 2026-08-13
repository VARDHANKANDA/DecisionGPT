"use client";

import { useEffect, useState } from "react";
import { researchApi, type ModelEntry } from "@/lib/research-api";

export default function ModelsPage() {
  const [models, setModels] = useState<ModelEntry[] | null>(null);
  const [syncing, setSyncing] = useState(false);

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

  const forecasting = models?.filter((m) => m.model_type.startsWith("forecasting_")) ?? [];
  const churn = models?.filter((m) => m.model_type.startsWith("churn_")) ?? [];

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Model Registry</h1>
          <p className="mt-1 text-muted">Every metric below comes from a real training run — nothing is hand-typed.</p>
        </div>
        <button
          onClick={sync}
          disabled={syncing}
          className="rounded-full border border-border bg-surface px-4 py-2 text-sm font-medium hover:bg-muted-surface disabled:opacity-50"
        >
          {syncing ? "Syncing…" : "Sync from training manifests"}
        </button>
      </div>

      {models === null ? (
        <p className="mt-6 text-sm text-muted">Loading…</p>
      ) : (
        <>
          <Section title="Forecasting performance">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 font-medium">Model</th>
                  <th className="py-2 font-medium">Version</th>
                  <th className="py-2 text-right font-medium">MAE</th>
                  <th className="py-2 text-right font-medium">RMSE</th>
                  <th className="py-2 text-right font-medium">MAPE</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {forecasting.map((m) => (
                  <tr key={m.id} className="border-b border-border last:border-0">
                    <td className="py-2">{m.model_name}</td>
                    <td className="py-2">{m.version}</td>
                    <td className="py-2 text-right">{fmt(m.metrics_json.mae)}</td>
                    <td className="py-2 text-right">{fmt(m.metrics_json.rmse)}</td>
                    <td className="py-2 text-right">{fmt(m.metrics_json.mape)}%</td>
                    <td className="py-2 capitalize">{m.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>

          <Section title="Churn performance">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="py-2 font-medium">Model</th>
                  <th className="py-2 font-medium">Version</th>
                  <th className="py-2 text-right font-medium">Precision</th>
                  <th className="py-2 text-right font-medium">Recall</th>
                  <th className="py-2 text-right font-medium">F1</th>
                  <th className="py-2 text-right font-medium">ROC-AUC</th>
                </tr>
              </thead>
              <tbody>
                {churn.map((m) => (
                  <tr key={m.id} className="border-b border-border last:border-0">
                    <td className="py-2">{m.model_name}</td>
                    <td className="py-2">{m.version}</td>
                    <td className="py-2 text-right">{fmt(m.metrics_json.precision)}</td>
                    <td className="py-2 text-right">{fmt(m.metrics_json.recall)}</td>
                    <td className="py-2 text-right">{fmt(m.metrics_json.f1)}</td>
                    <td className="py-2 text-right">{fmt(m.metrics_json.roc_auc)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Section>
        </>
      )}
    </div>
  );
}

function fmt(value: unknown): string {
  return typeof value === "number" ? value.toFixed(3) : "—";
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-8 rounded-2xl border border-border bg-surface p-6 shadow-sm">
      <h2 className="text-sm font-medium text-foreground">{title}</h2>
      <div className="mt-4 overflow-x-auto">{children}</div>
    </div>
  );
}
