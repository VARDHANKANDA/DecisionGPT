"use client";

import { useEffect, useState } from "react";
import { researchApi, ResearchApiError, type ModelEntry, type ModelValidation } from "@/lib/research-api";
import { displayMape } from "@/lib/metric-format";

const num = (v: unknown) => (typeof v === "number" ? v.toFixed(3) : "—");

export default function ModelRegistryPage() {
  const [models, setModels] = useState<ModelEntry[] | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validation, setValidation] = useState<ModelValidation | null>(null);

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

  async function validate(m: ModelEntry) {
    setBusyId(m.id);
    setError(null);
    try {
      setValidation(await researchApi.validateModel(m.id));
      load();
    } catch (e) {
      setError(e instanceof ResearchApiError ? e.message : "Validation failed to run.");
    } finally {
      setBusyId(null);
    }
  }

  async function promote(m: ModelEntry) {
    const reason = window.prompt(`Why promote ${m.model_name} ${m.version} to production? (recorded with your account)`);
    if (!reason || !reason.trim()) return;
    await act(m.id, (id) => researchApi.promoteModel(id, reason.trim()));
  }

  async function rollback(m: ModelEntry) {
    const reason = window.prompt(`Why roll ${m.model_name} back to its previous version? (recorded with your account)`);
    if (!reason || !reason.trim()) return;
    await act(m.id, () => researchApi.rollbackModel(m.model_name, reason.trim()));
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
      <p className="mt-3 text-xs text-muted">
        Lifecycle: <strong>candidate</strong> → run checks → <strong>validated</strong> → promote (needs a reason) → <strong>active</strong>.
        Training and syncing never deploy a model; only the very first version of a name is activated automatically.
      </p>
      {validation ? (
        <section className="mt-4 rounded-2xl border border-border bg-surface p-4" aria-label="Latest validation result">
          <h2 className="text-sm font-medium text-foreground">
            {validation.model_name} {validation.version}: {validation.passed ? "passed all blocking checks (validated)" : "failed a blocking check (rejected)"}
          </h2>
          <ul className="mt-2 space-y-1 text-xs">
            {validation.checks.map((c) => (
              <li key={c.name} className={c.passed ? "text-muted" : c.blocking ? "text-danger" : "text-warning"}>
                {c.passed ? "✓" : c.blocking ? "✕" : "!"} <strong>{c.name}</strong>: {c.detail}
                {!c.passed && !c.blocking ? " (warning, does not block)" : ""}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
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
                      <th className="py-2 font-medium">Validation</th>
                      <th className="py-2 font-medium">Applicability</th>
                      <th className="py-2 text-right font-medium">Metrics</th>
                      <th className="py-2 text-right font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((m) => {
                      const mk = m.metrics_json as Record<string, number>;
                      const accStr =
                        typeof mk.wape === "number"
                          ? ` · Acc ${(mk.wape <= 1 ? (1 - mk.wape) * 100 : Math.max(0, 100 - mk.wape)).toFixed(1)}% (1−WAPE)`
                          : "";
                      const metricStr = m.model_type.startsWith("forecasting_")
                        ? `MAE ${num(mk.mae)} · RMSE ${num(mk.rmse)}${accStr}${displayMape(mk.mape) !== null ? ` · MAPE ${num(displayMape(mk.mape))}` : ""}`
                        : `P ${num(mk.precision)} · R ${num(mk.recall)} · F1 ${num(mk.f1)} · AUC ${num(mk.roc_auc)}`;
                      return (
                        <tr key={m.id} className="border-b border-border last:border-0">
                          <td className="py-2">{m.version}</td>
                          <td className="py-2">
                            <StatusBadge status={m.status} />
                          </td>
                          <td className="py-2 text-muted">{m.source ?? "cli"}</td>
                          <td className="py-2 text-muted">{m.dataset_version}</td>
                          <td className="py-2 text-xs">
                            {m.validation_status === "validated" ? (
                              <span className="text-success">validated</span>
                            ) : m.validation_status === "rejected" ? (
                              <span className="text-danger">rejected</span>
                            ) : m.validation_status === "not_validated_bootstrap" ? (
                              <span className="text-warning" title="Activated automatically as the first version of this model; the automated checks were never run on it">
                                not validated (first version)
                              </span>
                            ) : (
                              <span className="text-muted">not validated</span>
                            )}
                          </td>
                          <td className="py-2 text-xs text-muted" title={(m.applicability?.reasons ?? []).join("; ")}>
                            {m.applicability?.eligible_for_production_use ? "eligible for business use" : "not eligible for business use"}
                            {m.applicability?.provenance ? ` · ${m.applicability.provenance.replace(/_/g, " ")}` : ""}
                            {m.applicability?.source === "inferred" ? " · inferred, not recorded" : ""}
                          </td>
                          <td className="py-2 text-right text-muted">{metricStr}</td>
                          <td className="py-2 text-right">
                            {["candidate", "experimental", "rejected", "registered"].includes(m.status) ? (
                              <button
                                onClick={() => validate(m)}
                                disabled={busyId === m.id}
                                className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted-surface disabled:opacity-50"
                              >
                                Run checks
                              </button>
                            ) : null}
                            {m.status === "validated" ? (
                              <button
                                onClick={() => promote(m)}
                                disabled={busyId === m.id}
                                className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted-surface disabled:opacity-50"
                              >
                                Promote…
                              </button>
                            ) : null}
                            {m.status === "active" ? (
                              <button
                                onClick={() => rollback(m)}
                                disabled={busyId === m.id}
                                className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted-surface disabled:opacity-50"
                              >
                                Roll back…
                              </button>
                            ) : null}
                            {m.status !== "archived" && m.status !== "active" ? (
                              <button
                                onClick={() => act(m.id, (id) => researchApi.archiveModel(id))}
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
      : status === "validated"
        ? "bg-accent-soft text-accent"
        : status === "rejected"
          ? "bg-danger-soft text-danger"
          : status === "candidate" || status === "experimental"
            ? "bg-warning-soft text-warning"
            : "bg-muted-surface text-muted";
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>{status}</span>;
}
