"use client";

import { useEffect, useState } from "react";
import { researchApi, type DatasetEntry } from "@/lib/research-api";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetEntry[] | null>(null);

  useEffect(() => {
    researchApi.listDatasets().then(setDatasets);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Dataset Registry</h1>
      <p className="mt-1 text-muted">Platform/research datasets only — never business data.</p>

      {datasets === null ? (
        <p className="mt-6 text-sm text-muted">Loading…</p>
      ) : datasets.length === 0 ? (
        <p className="mt-6 text-sm text-muted">No datasets registered yet.</p>
      ) : (
        <div className="mt-6 flex flex-col gap-4">
          {datasets.map((d) => (
            <div key={d.dataset_id} className="rounded-2xl border border-border bg-surface p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="font-medium text-foreground">{d.name}</h2>
                <span className="rounded-full bg-warning-soft px-3 py-1 text-xs font-medium text-warning">
                  {d.evidence_level}
                </span>
              </div>
              <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <Field label="Dataset ID" value={d.dataset_id} />
                <Field label="Version" value={d.version} />
                <Field label="Rows" value={d.row_count.toLocaleString("en-IN")} />
                <Field label="Features" value={String(d.feature_count)} />
                <Field label="Source" value={d.source} />
                <Field label="License" value={d.license} />
                <Field
                  label="Date range"
                  value={d.date_range ? `${d.date_range[0]} – ${d.date_range[1]}` : "N/A"}
                />
                <Field label="Domain" value={d.domain} />
              </dl>
              {d.limitations.length > 0 ? (
                <div className="mt-4">
                  <p className="text-xs font-medium text-muted">Limitations</p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-xs text-muted">
                    {d.limitations.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-foreground">{value}</dd>
    </div>
  );
}
