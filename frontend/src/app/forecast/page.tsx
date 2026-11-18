"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, ApiError, type ForecastReadiness, type ForecastResult, type ForecastSnapshot, type UnitsHistoryPoint } from "@/lib/api";
import { useBusiness } from "@/lib/business-context";
import { friendlyError, type FriendlyError } from "@/lib/friendly";
import { forecastStory } from "@/lib/narrate";
import { useLibrary } from "@/lib/use-library";
import { displayMape } from "@/lib/metric-format";
import { AnswerBlock, DataUsed, ErrorBox, Notice, Page, Spinner, btnPrimary, btnSecondary } from "@/components/simple";

const HORIZONS = [
  { days: 7, label: "Next week" },
  { days: 14, label: "Next 2 weeks" },
  { days: 30, label: "Next month" },
];

interface Run {
  result: ForecastResult;
  history: UnitsHistoryPoint[];
  days: number;
}

type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "saved"; snapshot: ForecastSnapshot }
  | { kind: "error"; message: string; changed: boolean };

/** Saves THIS forecast (the one on screen, identified by its fingerprint) so it can be compared with what actually sold. */
function SaveSnapshot({ businessId, result, days }: { businessId: string; result: ForecastResult; days: number }) {
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const missing = !result.fingerprint || !result.data_cutoff || !result.forecast_start;

  async function save() {
    if (state.kind === "saving") return;
    setState({ kind: "saving" });
    try {
      const snapshot = await api.saveForecastSnapshot(businessId, { horizon_days: days, fingerprint: result.fingerprint ?? null });
      setState({ kind: "saved", snapshot });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setState({ kind: "error", changed: true, message: e.message });
      } else {
        setState({ kind: "error", changed: false, message: friendlyError(e, "We couldn't save this forecast. Nothing was saved.").message });
      }
    }
  }

  return (
    <section aria-label="Save this forecast" className="rounded-2xl border border-border bg-surface p-5">
      <h2 className="text-base font-semibold text-foreground">Check this forecast later</h2>
      {missing ? (
        <p className="mt-1 text-base text-muted">
          This forecast cannot be saved for later checking because its data date or identity is not available. Nothing is saved.
        </p>
      ) : state.kind === "saved" ? (
        <p role="status" className="mt-1 text-base text-foreground">
          {state.snapshot.already_saved ? "This exact forecast was already saved." : "Saved."} It covers {state.snapshot.window_start} to{" "}
          {state.snapshot.window_end}, based on sales up to {state.snapshot.data_cutoff}. Once those days have passed,{" "}
          <Link href="/outcomes" className="font-medium text-accent underline underline-offset-4">
            Recommendation Outcomes
          </Link>{" "}
          shows how close it was.
        </p>
      ) : (
        <>
          <p className="mt-1 text-base text-muted">
            Save exactly this forecast so that, after the days it covers, DecisionGPT can compare it with what you actually sold. Saving does not
            change anything in your business.
          </p>
          <div className="mt-3">
            <button type="button" className={btnSecondary} onClick={save} disabled={state.kind === "saving"} aria-busy={state.kind === "saving"}>
              {state.kind === "saving" ? "Saving…" : "Save this forecast"}
            </button>
          </div>
          {state.kind === "error" ? (
            <p role="alert" className="mt-2 text-base text-danger">
              {state.message}
              {state.changed ? " Press “Get my forecast” again, then save the new one." : ""}
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}

export default function ForecastPage() {
  const { business, loading } = useBusiness();
  const library = useLibrary();
  const [days, setDays] = useState(14);
  const [running, setRunning] = useState(false);
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState<FriendlyError | null>(null);

  const [readiness, setReadiness] = useState<ForecastReadiness | null>(null);
  const businessId = business?.id;

  useEffect(() => {
    if (!businessId) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.getForecastReadiness(businessId);
        if (!cancelled) setReadiness(r);
      } catch {
        if (!cancelled) setReadiness(null); // the checks are informational; the forecast itself still reports what it needs
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [businessId]);

  const story = useMemo(() => (run ? forecastStory(run.result.points, run.history) : null), [run]);
  const salesRows = library?.find((d) => d.type === "sales")?.rows ?? null;

  async function start() {
    if (!business) return;
    setRunning(true);
    setError(null);
    setRun(null);
    try {
      const [result, history] = await Promise.all([api.getForecast(business.id, days), api.getUnitsHistory(business.id, 60)]);
      setRun({ result, history, days });
    } catch (e) {
      setError(friendlyError(e, "We couldn't create a forecast right now."));
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <Page title="Forecasting"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Forecasting" subtitle="Set up your business first.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business</Link>
      </Page>
    );
  }

  return (
    <Page title="Forecasting" subtitle="See what your future sales may look like, based on your own sales history." wide>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]">
        <div className="min-w-0 space-y-5">
          <section className="rounded-2xl border border-border bg-surface p-5">
            <h2 className="text-base font-semibold text-foreground">1. What would you like to forecast?</h2>
            <p className="mt-1 text-lg text-foreground">Sales (units sold per day)</p>
            <p className="mt-1 text-sm text-muted">This is the forecast DecisionGPT can produce today.</p>
          </section>

          <DataUsed
            library={library}
            types={["sales", "marketing_campaigns"]}
            action={
              salesRows === 0 ? (
                <Link href="/data/upload/file" className={btnSecondary}>Add sales data</Link>
              ) : null
            }
          />

          {readiness && (readiness.blockers.length > 0 || readiness.issues.length > 0 || readiness.example_data) ? (
            <Notice tone="warning" title="Checks on your sales data">
              <ul className="list-disc space-y-1 pl-5">
                {readiness.blockers.map((b) => (
                  <li key={b}>{b}</li>
                ))}
                {readiness.issues.map((i) => (
                  <li key={i.kind}>
                    {i.detail} ({i.rows.toLocaleString("en-IN")} {i.kind === "long_zero_run" ? "gap" : "rows"})
                  </li>
                ))}
                {readiness.example_data ? <li>{readiness.example_data}</li> : null}
              </ul>
            </Notice>
          ) : null}

          <fieldset className="rounded-2xl border border-border bg-surface p-5">
            <legend className="px-1 text-base font-semibold text-foreground">2. How far ahead?</legend>
            <div className="mt-2 flex flex-col gap-2">
              {HORIZONS.map((h) => (
                <label
                  key={h.days}
                  className={`flex min-h-[48px] cursor-pointer items-center gap-3 rounded-xl border px-4 py-2 text-lg ${
                    days === h.days ? "border-accent bg-accent-soft/40" : "border-border"
                  }`}
                >
                  <input type="radio" name="horizon" checked={days === h.days} onChange={() => setDays(h.days)} className="h-5 w-5 accent-[var(--accent)]" />
                  <span>{h.label}</span>
                  <span className="ml-auto text-sm text-muted">{h.days} days</span>
                </label>
              ))}
            </div>
          </fieldset>

          <button type="button" className={`${btnPrimary} w-full`} onClick={start} disabled={running || salesRows === 0}>
            {running ? "Working it out…" : "3. Get my forecast"}
          </button>
        </div>

        <div className="min-w-0" aria-live="polite">
          {running ? <Spinner label="Looking at your sales history…" /> : null}
          {error ? <ErrorBox error={error} onRetry={start} /> : null}

          {!run && !running && !error ? (
            <Notice title="No forecast yet.">
              Choose how far ahead you want to look, then press “Get my forecast”. It is made from your available sales data. If
              there isn&apos;t enough sales history yet, we&apos;ll tell you what is missing instead of guessing.
            </Notice>
          ) : null}

          {run && story ? (
            <div className="space-y-6">
              <Notice title="What this forecast is built from">
                {run.result.forecast_basis === "limited_estimate"
                  ? "A limited estimate from your own recent sales (the average of your last 28 days). There is not enough history to compare forecasting methods on your own data."
                  : run.result.forecast_basis === "business_specific_validated"
                    ? `A method chosen by testing several simple methods on your own past sales: ${run.result.validation?.method_description ?? run.result.validation?.selected ?? "see the technical note"}. It beat the plain average on held-out weeks.`
                    : "The average of your last 28 days. Simple methods that look at the day of the week were tested on your own past sales and did not beat it."}
                {run.result.data_as_of
                  ? ` Based on sales recorded up to ${new Date(`${run.result.data_as_of}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}.`
                  : ""}
                {run.result.registered_model_note ? ` ${run.result.registered_model_note}` : ""}
              </Notice>

              {run.result.warnings && run.result.warnings.length > 0 ? (
                <Notice tone="warning" title="Limits of this forecast">
                  <ul className="list-disc space-y-1 pl-5">
                    {run.result.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                </Notice>
              ) : null}

              {story.bigShift ? (
                <Notice tone="warning" title="Please review this forecast">
                  The estimated value is substantially different from your recent sales history (see the comparison below). Use this
                  result as an estimate rather than a guaranteed outcome, and check it against what you see in your business.
                </Notice>
              ) : null}

              {business ? <SaveSnapshot businessId={business.id} result={run.result} days={run.days} key={run.result.fingerprint ?? run.days} /> : null}

              <AnswerBlock
                headline={story.headline}
                why="Knowing roughly what to expect helps you decide how much stock to hold and how much to spend on marketing."
                shows={
                  <ul className="list-disc space-y-1 pl-5 text-base">
                    {story.why.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                }
                watch={`This is a model-based estimate, not a guaranteed sales figure. ${
                  run.result.interval_reliable
                    ? "The shaded band is measured from how this model's earlier forecasts compared with your own past sales: about 8 days in 10 should land inside it."
                    : "The shaded band could not be confirmed against your own past weeks (the reason is in the limits above, or there is too little history to check it), so treat it as a rough indication only."
                }`}
                next={
                  <>
                    Test a change before you make it in the{" "}
                    <Link href="/simulation" className="font-medium text-accent underline underline-offset-4">What-If Tester</Link>, or{" "}
                    <Link href="/decisions" className="font-medium text-accent underline underline-offset-4">get suggestions for a goal</Link>.
                  </>
                }
              />

              <section aria-label="Your recent sales compared with the forecast" className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-border bg-surface p-5">
                  <p className="text-sm font-semibold uppercase tracking-wide text-muted">Historical sales (from your records)</p>
                  {story.recentAvg !== null && story.recentTotal !== null ? (
                    <>
                      <p className="mt-1 text-3xl font-semibold text-foreground">{story.recentAvg.toFixed(1)} units a day</p>
                      <p className="text-base text-muted">
                        {Math.round(story.recentTotal).toLocaleString("en-IN")} units over the last {story.recentDays} days
                      </p>
                    </>
                  ) : (
                    <p className="mt-1 text-lg text-muted">Not enough recent history to compare.</p>
                  )}
                </div>
                <div className="rounded-2xl border border-accent/40 bg-accent-soft/30 p-5">
                  <p className="text-sm font-semibold uppercase tracking-wide text-accent">Forecast (an estimate)</p>
                  <p className="mt-1 text-3xl font-semibold text-foreground">{story.avgPerDay.toFixed(1)} units a day</p>
                  <p className="text-base text-muted">
                    {Math.round(story.totalUnits).toLocaleString("en-IN")} units over the next {run.days} days
                  </p>
                </div>
              </section>

              <ForecastChart run={run} />
              <p className="text-sm text-muted">This forecast is available while you view this page. Forecast history isn&apos;t currently saved.</p>

              <details className="rounded-2xl border border-border bg-surface">
                <summary className="cursor-pointer px-5 py-4 text-base font-medium text-foreground">Day-by-day numbers</summary>
                <div className="relative max-h-72 overflow-auto border-t border-border">
                  <table className="w-full text-base">
                    <thead className="sticky top-0 bg-surface text-left text-sm text-muted">
                      <tr><th className="px-4 py-2 font-medium">Day</th><th className="px-4 py-2 text-right font-medium">Expected units</th><th className="px-4 py-2 text-right font-medium">Expected range</th></tr>
                    </thead>
                    <tbody>
                      {run.result.points.map((p) => (
                        <tr key={p.forecast_date} className="border-t border-border">
                          <td className="px-4 py-2">{new Date(p.forecast_date).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })}</td>
                          <td className="px-4 py-2 text-right font-medium">{p.predicted_value.toFixed(0)}</td>
                          <td className="px-4 py-2 text-right text-muted">{p.lower_bound.toFixed(0)}–{p.upper_bound.toFixed(0)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>

              <details className="rounded-2xl border border-border bg-surface">
                <summary className="cursor-pointer px-5 py-4 text-base font-medium text-foreground">How was this calculated?</summary>
                <div className="space-y-2 border-t border-border p-5 text-sm text-muted">
                  <p>Method: {run.result.model_name} (version {run.result.model_version}), chosen automatically as the best available.</p>
                  <p>
                    Typical daily error when this method was tested: about {run.result.metrics.mae?.toFixed(1)} units
                    {displayMape(run.result.metrics.mape) !== null ? ` (around ${displayMape(run.result.metrics.mape)!.toFixed(0)}% off)` : ""}. This was measured on
                    DecisionGPT&apos;s own example data when the method was built — <strong>not on your business</strong> — so treat it as a rough guide.
                  </p>
                  <p>The expected range is a rough estimate that assumes the method&apos;s typical errors are bell-shaped and covers about 8 days in 10. It is never below zero.</p>
                </div>
              </details>
            </div>
          ) : null}
        </div>
      </div>
    </Page>
  );
}

function ForecastChart({ run }: { run: Run }) {
  const data = useMemo(() => {
    const past = run.history.slice(-30).map((h) => ({ date: h.date, actual: h.units_sold }));
    const future = run.result.points.map((p) => ({
      date: p.forecast_date,
      expected: Number(p.predicted_value.toFixed(1)),
      band: [Number(p.lower_bound.toFixed(1)), Number(p.upper_bound.toFixed(1))] as [number, number],
    }));
    return [...past, ...future];
  }, [run]);

  return (
    <section className="rounded-2xl border border-border bg-surface p-5" aria-label="Chart of recent and forecast sales">
      <h2 className="text-base font-semibold text-foreground">Recent sales and your forecast (units per day)</h2>
      <div className="mt-3 h-72">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} minTickGap={32} tickFormatter={(d: string) => d.slice(5)} />
            <YAxis tick={{ fontSize: 12 }} width={44} />
            <Tooltip />
            <Legend />
            <Area type="monotone" dataKey="band" name="Expected range" stroke="none" fill="var(--accent)" fillOpacity={0.15} />
            <Line type="monotone" dataKey="actual" name="What sold" stroke="var(--foreground)" strokeWidth={2} dot={false} connectNulls={false} />
            <Line type="monotone" dataKey="expected" name="Forecast" stroke="var(--accent)" strokeWidth={2.5} strokeDasharray="6 4" dot={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
