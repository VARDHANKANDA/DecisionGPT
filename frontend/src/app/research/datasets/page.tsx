"use client";

import { useEffect, useRef, useState } from "react";
import {
  researchApi,
  ResearchApiError,
  type DatasetsResponse,
  type UploadedDataset,
} from "@/lib/research-api";

const DOMAINS = ["forecasting", "churn", "marketing", "pricing", "inventory", "causal", "benchmarks", "other"];

export default function DatasetRegistryPage() {
  const [data, setData] = useState<DatasetsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    researchApi.listDatasets().then(setData).catch((e) => setError(String(e?.message ?? e)));
  }
  useEffect(load, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Dataset Registry</h1>
      <p className="mt-1 text-muted">
        Research/benchmark datasets only — never SME business data. Upload → validate → inspect schema →
        data-quality report → versioned automatically.
      </p>

      <UploadForm onDone={load} />

      {error ? <p className="mt-6 text-sm text-danger">{error}</p> : null}
      {!data ? (
        <p className="mt-6 text-sm text-muted">Loading…</p>
      ) : (
        <>
          <h2 className="mt-10 text-sm font-semibold uppercase tracking-wide text-muted">Uploaded datasets</h2>
          {data.uploaded.length === 0 ? (
            <p className="mt-2 text-sm text-muted">Nothing uploaded yet.</p>
          ) : (
            <div className="mt-3 flex flex-col gap-4">
              {data.uploaded.map((d) => (
                <UploadedCard key={d.id} d={d} />
              ))}
            </div>
          )}

          <h2 className="mt-10 text-sm font-semibold uppercase tracking-wide text-muted">Bundled platform datasets</h2>
          <div className="mt-3 flex flex-col gap-4">
            {data.platform.map((d) => (
              <div key={d.dataset_id} className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-foreground">{d.name}</h3>
                  <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-medium text-warning">
                    {d.evidence_level}
                  </span>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <Field label="Dataset ID" value={d.dataset_id} />
                  <Field label="Rows" value={d.row_count.toLocaleString("en-IN")} />
                  <Field label="Features" value={String(d.feature_count)} />
                  <Field label="Domain" value={d.domain} />
                  <Field label="Source" value={d.source} />
                  <Field label="License" value={d.license} />
                </dl>
                {d.limitations.length > 0 ? (
                  <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted">
                    {d.limitations.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function UploadForm({ onDone }: { onDone: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [domain, setDomain] = useState(DOMAINS[0]);
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file || !name) return;
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      const v = await researchApi.uploadDataset({ file, name, domain, source: source || undefined });
      setOk(`Registered ${name} v${v.version} (${v.row_count} rows, ${v.column_count} cols${v.validation_ok ? "" : " — quality issues flagged"}).`);
      setName("");
      setSource("");
      if (fileRef.current) fileRef.current.value = "";
      onDone();
    } catch (err) {
      setError(err instanceof ResearchApiError ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 rounded-2xl border border-border bg-surface p-6 shadow-sm">
      <p className="text-sm font-medium text-foreground">Upload a dataset (CSV / XLSX / Parquet)</p>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm sm:col-span-1">
          <span className="text-muted">Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} className="input" required />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted">Domain</span>
          <select value={domain} onChange={(e) => setDomain(e.target.value)} className="input">
            {DOMAINS.map((d) => (
              <option key={d}>{d}</option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted">Source (optional)</span>
          <input value={source} onChange={(e) => setSource(e.target.value)} className="input" />
        </label>
      </div>
      <input ref={fileRef} type="file" accept=".csv,.xlsx,.parquet" className="mt-4 block text-sm" required />
      <div className="mt-4">
        <button
          type="submit"
          disabled={busy}
          className="rounded-full bg-accent px-5 py-2.5 text-sm font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Uploading…" : "Upload & validate"}
        </button>
      </div>
      {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
      {ok ? <p className="mt-3 text-sm text-success">{ok}</p> : null}
    </form>
  );
}

function UploadedCard({ d }: { d: UploadedDataset }) {
  const latest = d.versions[0];
  return (
    <div className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-foreground">{d.name}</h3>
        <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
          {d.version_count} version{d.version_count === 1 ? "" : "s"}
        </span>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        <Field label="Dataset ID" value={d.dataset_id} />
        <Field label="Domain" value={d.domain} />
        <Field label="Latest version" value={`v${d.latest_version ?? "?"}`} />
        <Field label="Source" value={d.source ?? "—"} />
      </dl>
      {latest ? (
        <div className="mt-4 rounded-xl bg-muted-surface p-4 text-xs">
          <p className="font-medium text-foreground">
            v{latest.version}: {latest.row_count} rows · {latest.column_count} columns ·{" "}
            {latest.validation_ok ? (
              <span className="text-success">validation ok</span>
            ) : (
              <span className="text-danger">{latest.quality_report.issues?.join("; ")}</span>
            )}
          </p>
          <p className="mt-2 text-muted">
            Schema: {latest.columns.map((c) => `${c.name}:${c.dtype}`).join(", ")}
          </p>
          {Object.keys(latest.missing_summary).length > 0 ? (
            <p className="mt-1 text-warning">
              Missing values — {Object.entries(latest.missing_summary).map(([k, v]) => `${k}: ${v}`).join(", ")}
            </p>
          ) : null}
          {(latest.duplicates_summary.duplicate_row_count ?? 0) > 0 ? (
            <p className="mt-1 text-warning">{latest.duplicates_summary.duplicate_row_count} duplicate rows</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="break-words text-foreground">{value}</dd>
    </div>
  );
}
