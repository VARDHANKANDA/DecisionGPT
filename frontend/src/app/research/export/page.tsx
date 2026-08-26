"use client";

import { useEffect, useState } from "react";
import {
  researchApi,
  ResearchApiError,
  type ExportFormat,
  type ExportTable,
  type PaperResults,
} from "@/lib/research-api";
import { DataTable, Metric, Panel, PageIntro, StatGrid } from "@/components/research-ui";

const FORMATS: ExportFormat[] = ["csv", "json", "markdown", "latex"];

export default function PaperResultsPage() {
  const [data, setData] = useState<PaperResults | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [format, setFormat] = useState<ExportFormat>("markdown");
  const [output, setOutput] = useState<{ title: string; text: string } | null>(null);
  const [busyTable, setBusyTable] = useState<string | null>(null);

  useEffect(() => {
    researchApi.paperResults().then(setData).catch((e) => setError(String(e?.message ?? e)));
  }, []);

  async function exportTable(exportTable: string, title: string) {
    setBusyTable(exportTable);
    setError(null);
    try {
      const text = await researchApi.exportTable(exportTable as ExportTable, format);
      setOutput({ title: `${title} (${format})`, text });
    } catch (e) {
      setError(e instanceof ResearchApiError ? e.message : "Export failed.");
    } finally {
      setBusyTable(null);
    }
  }

  return (
    <div>
      <PageIntro
        title="Paper Results"
        subtitle="Collects the five paper tables from real recorded data. Each table shows whether it is ready or which experiment still needs to run — no table is fabricated. Every exported row traces back to an experiment id, training run, model version, or decision id."
      />

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {!data ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : (
        <div className="space-y-6">
          <StatGrid>
            <Metric label="Tables ready" value={`${data.summary.tables_ready} / ${data.summary.tables_total}`} />
            <Metric label="Tables missing data" value={data.summary.tables_missing} />
            <div className="col-span-2 flex items-end">
              <label className="flex w-full flex-col gap-1 text-xs text-muted">
                Export format
                <select className="input" value={format} onChange={(e) => setFormat(e.target.value as ExportFormat)}>
                  {FORMATS.map((f) => (
                    <option key={f} value={f}>
                      {f.toUpperCase()}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </StatGrid>

          {data.tables.map((t) => (
            <Panel
              key={t.key}
              title={t.title}
              right={
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      t.available ? "bg-success-soft text-success" : "bg-warning-soft text-warning"
                    }`}
                  >
                    {t.available ? "ready" : "missing data"}
                  </span>
                  {t.export_tables.map((et) => (
                    <button
                      key={et}
                      onClick={() => exportTable(et, t.title)}
                      disabled={!t.available || busyTable === et}
                      className="rounded-full border border-border px-3 py-1 text-xs hover:bg-muted-surface disabled:opacity-40"
                    >
                      {busyTable === et ? "…" : `Export ${et}`}
                    </button>
                  ))}
                </div>
              }
            >
              {!t.available ? (
                <p className="text-sm text-muted">{t.missing_reason}</p>
              ) : (
                <div className="space-y-4">
                  {t.sections.map((s) => (
                    <div key={s.name}>
                      {t.sections.length > 1 ? (
                        <p className="mb-2 text-xs font-medium text-muted">{s.name} · {s.row_count} rows</p>
                      ) : (
                        <p className="mb-2 text-xs text-muted">{s.row_count} rows</p>
                      )}
                      <DataTable
                        headers={s.headers}
                        rows={s.rows.map((r) => r.map((c) => (typeof c === "number" ? c.toLocaleString("en-IN") : c)))}
                      />
                    </div>
                  ))}
                  <p className="text-xs text-muted">
                    Traceability:{" "}
                    {Object.entries(t.source_refs)
                      .filter(([, v]) => v != null && (!Array.isArray(v) || v.length))
                      .map(([k, v]) => `${k}=${Array.isArray(v) ? `${v.length} refs` : String(v)}`)
                      .join(" · ") || "—"}
                  </p>
                </div>
              )}
            </Panel>
          ))}

          {output ? (
            <Panel
              title={output.title}
              right={
                <button
                  onClick={() => navigator.clipboard.writeText(output.text)}
                  className="text-xs font-medium text-accent underline underline-offset-4"
                >
                  Copy
                </button>
              }
            >
              <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap text-xs text-foreground">
                {output.text || "(no rows)"}
              </pre>
            </Panel>
          ) : null}
        </div>
      )}
    </div>
  );
}
