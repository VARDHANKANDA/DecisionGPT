"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { researchApi, type DatasetEntry, type ExperimentRun, type ModelEntry } from "@/lib/research-api";

export default function ResearchOverviewPage() {
  const [datasets, setDatasets] = useState<DatasetEntry[] | null>(null);
  const [models, setModels] = useState<ModelEntry[] | null>(null);
  const [experiments, setExperiments] = useState<ExperimentRun[] | null>(null);

  useEffect(() => {
    researchApi.listDatasets().then(setDatasets);
    researchApi.listModels().then(setModels);
    researchApi.listExperiments().then(setExperiments);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold text-foreground">Research Console</h1>
      <p className="mt-1 text-muted">
        Private, platform-administrator surface for datasets, model performance, experiments, and paper exports.
        Never reachable from the SME application.
      </p>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryCard
          href="/research/datasets"
          label="Platform datasets"
          value={datasets?.length ?? "…"}
          description="Registered training datasets"
        />
        <SummaryCard
          href="/research/models"
          label="Registered models"
          value={models?.length ?? "…"}
          description="Forecasting and churn models"
        />
        <SummaryCard
          href="/research/experiments"
          label="Recorded experiments"
          value={experiments?.length ?? "…"}
          description="Every run, with reproducibility metadata"
        />
      </div>
    </div>
  );
}

function SummaryCard({
  href,
  label,
  value,
  description,
}: {
  href: string;
  label: string;
  value: number | string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="block rounded-2xl border border-border bg-surface p-6 shadow-sm transition hover:border-accent"
    >
      <p className="text-sm text-muted">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-foreground">{value}</p>
      <p className="mt-1 text-xs text-muted">{description}</p>
    </Link>
  );
}
