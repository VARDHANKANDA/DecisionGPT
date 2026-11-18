"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { researchApi, type BusinessValidation, type EvaluationOverview } from "@/lib/research-api";
import { PageIntro } from "@/components/research-ui";
import { StateNote } from "@/components/evaluation-cards";
import {
  BaselinePanel,
  BusinessPicker,
  ClassificationPanel,
  ForecastingPanel,
  HistoryPanel,
  HorizonPanel,
  LimitationsPanel,
  OverviewPanel,
  SetupPanel,
} from "./panels";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "forecasting", label: "Forecasting & Regression" },
  { id: "classification", label: "Classification" },
  { id: "baseline", label: "Model vs Baseline" },
  { id: "horizon", label: "Performance by Horizon" },
  { id: "setup", label: "Dataset & Setup" },
  { id: "limits", label: "Validation & Limitations" },
  { id: "history", label: "History" },
] as const;
type TabId = (typeof TABS)[number]["id"];
const STALE_PAGE_MS = 30 * 60_000;

export default function EvaluationPage() {
  const [data, setData] = useState<EvaluationOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<TabId>("overview");
  const [businessId, setBusinessId] = useState("");
  const [business, setBusiness] = useState<BusinessValidation | null>(null);
  const [busy, setBusy] = useState(false);
  const [bizError, setBizError] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 60_000); // so "may be out of date" appears without a reload
    return () => window.clearInterval(id);
  }, []);
  const requestId = useRef(0); // an older answer must never replace a newer one (stale results)

  const fetchOverview = useCallback(() => {
    const mine = ++requestId.current;
    researchApi
      .evaluation()
      .then((d) => {
        if (mine === requestId.current) {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => {
        if (mine === requestId.current) setError(String((e as Error)?.message ?? e));
      })
      .finally(() => {
        if (mine === requestId.current) setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchOverview(); // state is only set when the answer arrives, never synchronously here
  }, [fetchOverview]);

  function load() {
    setLoading(true);
    setError(null);
    fetchOverview();
  }

  const bizRequest = useRef(0);
  async function selectBusiness(id: string) {
    setBusinessId(id);
    setBusiness(null);
    setBizError(null);
    const mine = ++bizRequest.current;
    if (!id) return;
    try {
      const b = await researchApi.evaluationBusiness(id);
      if (mine === bizRequest.current) setBusiness(b);
    } catch (e) {
      if (mine === bizRequest.current) setBizError(String((e as Error)?.message ?? e));
    }
  }

  async function run(kind: "forecast" | "customer") {
    if (!businessId || busy) return;
    setBusy(true);
    setBizError(null);
    try {
      await researchApi.runEvaluationBusiness(businessId, kind);
      await selectBusiness(businessId); // read back what was stored, so the page shows exactly the saved report
    } catch (e) {
      setBizError(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  function onKey(e: React.KeyboardEvent, index: number) {
    const move = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : e.key === "Home" ? -index : e.key === "End" ? TABS.length - 1 - index : 0;
    if (!move) return;
    e.preventDefault();
    const next = TABS[(index + move + TABS.length) % TABS.length].id;
    setTab(next);
    document.getElementById(`tab-${next}`)?.focus();
  }

  const picker = (
    <BusinessPicker selected={businessId} onSelect={(id) => void selectBusiness(id)} validation={business} busy={busy} error={bizError} onRun={(k) => void run(k)} />
  );

  return (
    <div>
      <PageIntro
        title="Evaluation metrics"
        subtitle="Every figure here was recorded by a training run, a stored benchmark or a validation report; this page only presents it. Training, benchmark, one-business and live evidence are kept apart."
      />
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm text-muted">
        <button type="button" onClick={load} disabled={loading} className="rounded-lg border border-border px-3 py-1.5 text-foreground hover:bg-muted-surface disabled:opacity-50">
          {loading ? "Refreshing…" : "Refresh"}
        </button>
        {data ? <span>Loaded {new Date(data.generated_at).toLocaleString()}</span> : null}
      </div>
      {data && now - new Date(data.generated_at).getTime() > STALE_PAGE_MS ? (
        <div className="mb-4">
          <StateNote kind="stale">These results were loaded more than {STALE_PAGE_MS / 60_000} minutes ago. Press Refresh to read the latest recorded values.</StateNote>
        </div>
      ) : null}

      <div role="tablist" aria-label="Evaluation sections" className="mb-5 flex flex-wrap gap-1 border-b border-border">
        {TABS.map((t, i) => (
          <button
            key={t.id}
            id={`tab-${t.id}`}
            role="tab"
            type="button"
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => setTab(t.id)}
            onKeyDown={(e) => onKey(e, i)}
            className={`rounded-t-lg px-3 py-2 text-sm transition ${tab === t.id ? "border-b-2 border-accent font-medium text-accent" : "text-muted hover:text-foreground"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} tabIndex={0}>
        {error ? (
          <div role="alert" className="rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-foreground">
            The evaluation data could not be loaded: {error}{" "}
            <button type="button" className="font-medium underline" onClick={load}>Try again</button>
          </div>
        ) : !data ? (
          <p role="status" className="text-sm text-muted">Loading evaluation data…</p>
        ) : tab === "overview" ? (
          <OverviewPanel data={data} business={business} />
        ) : tab === "forecasting" ? (
          <ForecastingPanel data={data} />
        ) : tab === "classification" ? (
          <ClassificationPanel data={data} business={business} />
        ) : tab === "baseline" ? (
          <BaselinePanel data={data} business={business} />
        ) : tab === "horizon" ? (
          <HorizonPanel business={business} businessPicker={picker} />
        ) : tab === "setup" ? (
          <SetupPanel data={data} business={business} />
        ) : tab === "limits" ? (
          <LimitationsPanel data={data} business={business} />
        ) : (
          <HistoryPanel />
        )}
      </div>
    </div>
  );
}
