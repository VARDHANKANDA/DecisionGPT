"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, type IngestionJob } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { Card, PageHeader, PrimaryButton, SecondaryLink } from "@/components/ui";

const CSV_DATA_TYPES = [
  { value: "products", label: "Products" },
  { value: "customers", label: "Customers" },
  { value: "sales", label: "Sales" },
  { value: "marketing_campaigns", label: "Marketing" },
  { value: "inventory", label: "Inventory" },
];

export default function DataUploadPage() {
  const router = useRouter();
  const { business, loading } = useBusiness();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [csvDataType, setCsvDataType] = useState(CSV_DATA_TYPES[2].value);
  const [status, setStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [job, setJob] = useState<IngestionJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!loading && !business) {
    return (
      <div className="mx-auto max-w-xl px-6 py-24 text-center">
        <p className="text-muted">Set up your business first.</p>
        <div className="mt-4">
          <SecondaryLink href="/onboarding">Go to onboarding</SecondaryLink>
        </div>
      </div>
    );
  }

  const isCsv = selectedFile?.name.toLowerCase().endsWith(".csv");

  async function handleUpload() {
    if (!business || !selectedFile) return;
    setStatus("uploading");
    setError(null);
    try {
      const result = await api.uploadData(business.id, selectedFile, isCsv ? csvDataType : undefined);
      setJob(result);
      setStatus(result.status === "failed" ? "error" : "done");
      if (result.status === "failed") {
        setError(result.error_message ?? "Upload failed data quality validation.");
      }
    } catch (err) {
      setStatus("error");
      setError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
    }
  }

  const rowsIngested = job?.summary_json?.rows_ingested;

  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <PageHeader
        title="Upload your business data"
        subtitle="One Excel workbook with Sales / Customers / Products / Marketing / Inventory sheets, or separate CSVs."
      />

      <Card>
        <div
          className="flex flex-col items-center gap-3 rounded-xl border-2 border-dashed border-border bg-muted-surface px-6 py-12 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const file = e.dataTransfer.files?.[0];
            if (file) setSelectedFile(file);
          }}
        >
          <p className="text-sm text-muted">
            {selectedFile ? (
              <span className="font-medium text-foreground">{selectedFile.name}</span>
            ) : (
              "Drag a .xlsx or .csv file here, or"
            )}
          </p>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="text-sm font-medium text-accent underline underline-offset-4"
          >
            {selectedFile ? "Choose a different file" : "browse files"}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
          />
        </div>

        {isCsv ? (
          <label className="mt-4 flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">What does this CSV contain?</span>
            <select value={csvDataType} onChange={(e) => setCsvDataType(e.target.value)} className="input">
              {CSV_DATA_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <div className="mt-6">
          <PrimaryButton onClick={handleUpload} disabled={!selectedFile || status === "uploading"}>
            {status === "uploading" ? "Uploading and processing…" : "Upload and process"}
          </PrimaryButton>
        </div>

        {status === "error" && error ? (
          <div className="mt-6 rounded-xl bg-danger-soft px-4 py-3 text-sm text-danger">
            {error}
            {job?.status === "needs_mapping_confirmation" ? (
              <p className="mt-2 text-danger/80">
                Some columns couldn&rsquo;t be automatically matched. Rename your columns to match the
                expected fields (or contact support for guided mapping) and re-upload.
              </p>
            ) : null}
          </div>
        ) : null}

        {status === "done" && job ? (
          <div className="mt-6 rounded-xl bg-success-soft px-4 py-4">
            <p className="text-sm font-medium text-success">Your data is ready.</p>
            <ul className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-foreground">
              {rowsIngested &&
                Object.entries(rowsIngested).map(([type, count]) => (
                  <li key={type} className="flex justify-between">
                    <span className="capitalize text-muted">{type.replace("_", " ")}</span>
                    <span className="font-medium">{count}</span>
                  </li>
                ))}
            </ul>
            <div className="mt-4">
              <PrimaryButton onClick={() => router.push("/dashboard")}>Go to dashboard</PrimaryButton>
            </div>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
