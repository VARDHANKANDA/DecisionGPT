"use client";

import { useEffect, useState } from "react";
import { api, type Business } from "@/lib/api";
import {
  researchApi,
  type BenchmarkRun,
  type BusinessValidation,
  type EvalClassificationModel,
  type EvalForecastModel,
  type EvaluationOverview,
  type MetricCardData,
  type ModelPerformance,
  type PresentedHorizon,
  type PresentedValidationRun,
} from "@/lib/research-api";
import { Block, CardCell, EvaluatedOn, EvidenceTag, MetricCard, MetricGrid, MetricLegend, StateNote } from "@/components/evaluation-cards";
import { DataTable, EvalEmptyState, Panel, fmtInt } from "@/components/research-ui";
import { btnSecondary } from "@/components/simple";

const nf = (n: number | null | undefined) => (typeof n === "number" ? n.toLocaleString("en-IN") : "—");
const when = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleString() : "—");
const find = (cards: MetricCardData[], key: string) => cards.find((c) => c.key === key);
const byKey = (cards: MetricCardData[]) => Object.fromEntries(cards.map((c) => [c.key, c])) as Record<string, MetricCardData | undefined>;

/** Whole days between an ISO time and now (null when it cannot be read). */
function ageDays(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const t = new Date(iso).getTime();
  return Number.isNaN(t) ? null : Math.floor((Date.now() - t) / 86_400_000);
}
const STALE_AFTER_DAYS = 7;

const VERDICT_TEXT: Record<string, string> = {
  better_than_baseline: "Better than the baseline on the same rows",
  not_better_than_baseline: "Not better than the baseline on the same rows",
};

// ------------------------------------------------------------------------------------------------ Overview
export function OverviewPanel({ data, business }: { data: EvaluationOverview; business: BusinessValidation | null }) {
  const a = data.availability;
  const fm = data.sections.training.forecasting;
  const cm = data.sections.training.classification;
  const kinds = [
    { kind: "training", title: "Registered models", count: `${a.forecasting_models + a.classification_models} model(s)`, text: "Scored on the held-out part of the research dataset each was trained on. Shows how well a model learned that dataset." },
    { kind: "benchmark", title: "Public benchmarks", count: `${a.benchmark_runs} stored run(s)`, text: "Results of benchmark runs on public retail data, shown exactly as stored." },
    { kind: "business", title: "One business's history", count: "Choose a business", text: "A backtest on a single business's own sales. This is the closest to how a forecast would have done for that business." },
    { kind: "production", title: "Live use", count: "Not evaluated", text: data.sections.production.reason },
  ];
  const horizons = (business?.forecast?.horizons ?? []).filter((h) => h.status === "evaluated");
  return (
    <div className="space-y-4">
      {fm.length + cm.length > 0 ? (
        <Block title="Results at a glance" tag="training" note="Recorded values only, from each model's held-out test block. Open a tab for every metric, its meaning and its limits.">
          {fm.length > 0 ? (
            <DataTable
              headers={["Forecasting model", "Test MAE", "Baseline MAE", "Change in MAE", "Against the baseline"]}
              rows={fm.map((m) => [
                `${m.model_name} ${m.version}`,
                <CardCell key="a" card={find(m.test, "mae")} />,
                <CardCell key="b" card={find(m.baseline.test, "baseline_mae")} />,
                <CardCell key="c" card={find(m.baseline.test, "mae_vs_baseline")} />,
                m.baseline.verdict ? VERDICT_TEXT[m.baseline.verdict] : (find(m.baseline.test, "mae_vs_baseline")?.reason ?? "Not comparable"),
              ])}
            />
          ) : null}
          {cm.length > 0 ? (
            <div className={fm.length > 0 ? "mt-4" : ""}>
              <DataTable
                headers={["Customer model", "ROC-AUC", "PR-AUC", "Positive rate (test)"]}
                rows={cm.map((m) => [
                  `${m.model_name} ${m.version}`,
                  <CardCell key="a" card={find(m.test, "roc_auc")} />,
                  <CardCell key="b" card={find(m.test, "pr_auc")} />,
                  <CardCell key="c" card={m.class_balance?.test_positive_rate} />,
                ])}
              />
            </div>
          ) : null}
        </Block>
      ) : null}
      {horizons.length > 0 ? (
        <Block title="This business's forecast, by horizon" tag="business" note="From the stored backtest of the business chosen under Performance by Horizon.">
          <DataTable
            headers={["Horizon", "Method", "MAE", "Against simple references"]}
            rows={horizons.map((h) => [`${h.horizon_days} days`, h.method ?? "—", <CardCell key="a" card={find(h.cards, "mae")} />, (h.verdict ?? "").replace(/_/g, " ")])}
          />
        </Block>
      ) : null}
      <Panel title="What this page shows">
        <p className="max-w-3xl text-sm text-muted">
          Every figure on this page was recorded by a training run, a stored benchmark or a validation report; this page only formats it. Four kinds of
          evidence are kept apart and never added together. A metric that was not recorded, was not run, or would be misleading is labelled and
          explained instead of being shown as a number.
        </p>
      </Panel>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {kinds.map((k) => (
          <section key={k.kind} className="rounded-xl border border-border bg-surface p-4" aria-label={k.title}>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm font-semibold text-foreground">{k.title}</h3>
              <EvidenceTag kind={k.kind} />
            </div>
            <p className="mt-2 text-lg font-semibold text-foreground">{k.count}</p>
            <p className="mt-1 text-sm text-muted">{k.text}</p>
          </section>
        ))}
      </div>
      {a.forecasting_models + a.classification_models === 0 && a.benchmark_runs === 0 ? (
        <EvalEmptyState message="Nothing has been evaluated yet. Train a model in the Training Center, or run a validation on a business, to see metrics here." />
      ) : null}
      <Panel title="Where to look">
        <ul className="list-disc space-y-1 pl-5 text-sm text-foreground">
          <li><strong>Forecasting &amp; Regression</strong> and <strong>Classification</strong>: every metric for each model, with what it means.</li>
          <li><strong>Model vs Baseline</strong>: whether a model beats a simple reference on the same rows.</li>
          <li><strong>Performance by Horizon</strong>: how a business forecast does 7, 14 and 28 days ahead.</li>
          <li><strong>Dataset &amp; Setup</strong>: what each result was measured on.</li>
          <li><strong>Validation &amp; Limitations</strong>: what the numbers do not show, plus the glossary.</li>
        </ul>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ Forecasting
function ForecastModelBlock({ m }: { m: EvalForecastModel }) {
  const n = find(m.test, "n_eval");
  const test = m.setup.splits?.test;
  return (
    <Block title={`${m.model_name} ${m.version}`} tag="training" note={`Status: ${m.status}.`}>
      <EvaluatedOn
        facts={[
          ["Dataset", m.setup.dataset_version],
          ["Target", m.target],
          ["Test sample", n?.status === "available" ? `${n.display} points` : "not recorded for this model"],
          ["Test period", m.evaluation?.test_window?.[0] ? `${m.evaluation.test_window[0]} to ${m.evaluation.test_window[1]}` : test?.first ? `${test.first} to ${test.last}` : null],
          ["Horizon", m.evaluation?.horizon ?? "1 day ahead"],
          ["Evaluation", m.evaluation ? `${m.evaluation.status}${m.evaluation.kind ? ` (${m.evaluation.kind.replace(/_/g, " ")})` : ""}` : null],
          ["Split", m.setup.split_scheme],
        ]}
      />
      <h4 className="mb-2 text-sm font-semibold text-foreground">Against the baseline (yesterday&apos;s value, same rows)</h4>
      {m.baseline.verdict ? <p className="mb-2 text-sm font-medium text-foreground">{VERDICT_TEXT[m.baseline.verdict]}.</p> : null}
      <MetricGrid cards={m.baseline.test} />
      <h4 className="mb-2 mt-5 text-sm font-semibold text-foreground">Held-out test block</h4>
      <MetricGrid cards={m.test} />
      {m.validation.length > 0 ? (
        <>
          <h4 className="mb-2 mt-5 text-sm font-semibold text-foreground">Validation block (used to choose between models; kept separate)</h4>
          <MetricGrid cards={m.validation} />
        </>
      ) : null}
      <div className="mt-5">
        <MetricCard card={m.interval_coverage} />
      </div>
    </Block>
  );
}

const BENCH_FORECAST_COLUMNS = ["mae", "rmse", "wape", "relative_bias", "rmsse", "aggregate_daily_wape", "median_series_wape", "mae_vs_baseline"];

function BenchmarkForecast({ run }: { run: BenchmarkRun }) {
  return (
    <Block title={run.title} tag="benchmark" note="Shown as stored. Figures are comparable only between rows of the same table.">
      {(run.sections ?? []).map((s) => {
        const first = s.rows[0] ? byKey(s.rows[0].cards) : {};
        return (
          <div key={s.name} className="mb-6 last:mb-0">
            <h4 className="text-sm font-semibold text-foreground">{s.name}</h4>
            <EvaluatedOn
              facts={[
                ["Evidence class", run.evidence_class ?? "not recorded"],
                ["Series", nf(s.n_series)],
                ["Test points", nf(s.n_test_points)],
                ["Test window", s.test_window ? s.test_window.join(" to ") : null],
                ["Run", run.run_id],
                ["Code revision", run.git_revision],
              ]}
            />
            <DataTable
              headers={["Method", ...BENCH_FORECAST_COLUMNS.map((k) => first[k]?.abbr ?? k)]}
              rows={s.rows.map((r) => {
                const by = byKey(r.cards);
                return [
                  <span key="m">{r.method}{r.selected_by_validation ? " (chosen on validation)" : ""}{r.kind === "baseline" ? " (baseline)" : ""}</span>,
                  ...BENCH_FORECAST_COLUMNS.map((k) => <CardCell key={k} card={by[k]} />),
                ];
              })}
            />
            <MetricLegend cards={s.rows.flatMap((r) => r.cards).filter((c) => BENCH_FORECAST_COLUMNS.includes(c.key))} />
          </div>
        );
      })}
    </Block>
  );
}

export function ForecastingPanel({ data }: { data: EvaluationOverview }) {
  const models = data.sections.training.forecasting;
  const runs = data.sections.benchmark.runs.filter((r) => r.kind === "forecast");
  return (
    <div className="space-y-5">
      <Panel>
        <p className="max-w-3xl text-sm text-muted">
          Errors are in the units of what is forecast, so they cannot be compared between different targets. Bias is signed: positive means the forecast
          is too high, negative too low. Percentage errors are only shown when they are defined.
        </p>
      </Panel>
      {models.length === 0 ? <EvalEmptyState message={data.sections.training.empty ?? "No forecasting models are registered."} /> : models.map((m) => <ForecastModelBlock key={m.id} m={m} />)}
      {runs.map((r) => <BenchmarkForecast key={r.run_id} run={r} />)}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ Classification
function Confusion({ m }: { m: NonNullable<EvalClassificationModel["confusion_matrix"]> }) {
  return (
    <div className="overflow-x-auto">
      <table className="text-sm" aria-label="Confusion matrix">
        <caption className="mb-1 text-left text-xs text-muted">
          Customers (n = {nf(m.n)}) at threshold {m.threshold ?? "—"}. Positive class: {m.positive_class}. Rows are actual, columns are predicted.
        </caption>
        <thead>
          <tr className="text-left text-muted">
            <th className="px-3 py-1 font-medium"><span className="sr-only">Actual</span></th>
            <th className="px-3 py-1 font-medium">Predicted: stays</th>
            <th className="px-3 py-1 font-medium">Predicted: leaves</th>
          </tr>
        </thead>
        <tbody>
          <tr><th scope="row" className="px-3 py-1 text-left font-medium">Actual: stays</th><td className="border border-border px-3 py-2">{nf(m.tn)} (true negative)</td><td className="border border-border px-3 py-2">{nf(m.fp)} (false positive)</td></tr>
          <tr><th scope="row" className="px-3 py-1 text-left font-medium">Actual: left</th><td className="border border-border px-3 py-2">{nf(m.fn)} (false negative)</td><td className="border border-border px-3 py-2">{nf(m.tp)} (true positive)</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function ClassificationBlock({ m }: { m: EvalClassificationModel }) {
  return (
    <Block title={`${m.model_name} ${m.version}`} tag="training" note={`Status: ${m.status}. ${m.score_meaning}`}>
      <EvaluatedOn
        facts={[
          ["Dataset", m.setup.dataset_version],
          ["Target", m.target],
          ["Positive class", m.positive_class],
          ["Test sample", m.confusion_matrix ? `${nf(m.confusion_matrix.n)} customers` : "not recorded for this model"],
          ["Threshold", m.confusion_matrix?.threshold ?? null],
          ["Split", m.setup.split_scheme],
        ]}
      />
      <MetricGrid cards={m.test} />
      {m.threshold_note ? <p className="mt-3 text-sm text-muted">{m.threshold_note}</p> : null}
      {m.confusion_matrix ? <div className="mt-4"><Confusion m={m.confusion_matrix} /></div> : null}
      {m.class_balance ? (
        <div className="mt-5">
          <h4 className="mb-2 text-sm font-semibold text-foreground">Class balance</h4>
          <MetricGrid cards={[m.class_balance.train_positive_rate, m.class_balance.test_positive_rate]} />
        </div>
      ) : null}
      {m.validation.length > 0 ? (
        <>
          <h4 className="mb-2 mt-5 text-sm font-semibold text-foreground">Validation (kept separate from the test figures)</h4>
          <MetricGrid cards={m.validation} />
        </>
      ) : null}
    </Block>
  );
}

const BENCH_CLASS_COLUMNS = ["roc_auc", "pr_auc", "brier", "brier_baseline", "brier_vs_baseline", "log_loss", "ece"];

function BenchmarkClassification({ run }: { run: BenchmarkRun }) {
  const first = run.rows?.[0] ? byKey(run.rows[0].cards) : {};
  const split = run.rows_per_split;
  const prev = run.prevalence;
  return (
    <Block title={run.title} tag="benchmark" note="Shown as stored. Scores rank customers; they are not probabilities.">
      <EvaluatedOn
        facts={[
          ["Evidence class", run.evidence_class ?? "not recorded"],
          ["Rows", split ? `train ${nf(split.train)}, validation ${nf(split.validation)}, test ${nf(split.test)}` : null],
          ["Positive rate", prev ? `train ${prev.train?.toFixed(3)}, validation ${prev.validation?.toFixed(3)}, test ${prev.test?.toFixed(3)}` : null],
          ["Run", run.run_id],
          ["Code revision", run.git_revision],
        ]}
      />
      <DataTable
        headers={["Model", ...BENCH_CLASS_COLUMNS.map((k) => first[k]?.abbr ?? k)]}
        rows={(run.rows ?? []).map((r) => {
          const by = byKey(r.cards);
          return [`${r.method}${r.selected_by_validation ? " (chosen on validation)" : ""}`, ...BENCH_CLASS_COLUMNS.map((k) => <CardCell key={k} card={by[k]} />)];
        })}
      />
      <MetricLegend cards={(run.rows ?? []).flatMap((r) => r.cards)} />
    </Block>
  );
}

export function ClassificationPanel({ data, business }: { data: EvaluationOverview; business: BusinessValidation | null }) {
  const models = data.sections.training.classification;
  const runs = data.sections.benchmark.runs.filter((r) => r.kind === "classification");
  return (
    <div className="space-y-5">
      <Panel>
        <p className="max-w-3xl text-sm text-muted">
          These models give each customer a score and rank them. ROC-AUC and PR-AUC judge the ranking. Precision, recall, F1 and accuracy depend on one
          threshold. A score is not shown as a probability, and accuracy is easy to inflate when one outcome is rare, so read it with the positive rate.
        </p>
      </Panel>
      {models.length === 0 ? <EvalEmptyState message="No customer models are registered." /> : models.map((m) => <ClassificationBlock key={m.id} m={m} />)}
      {runs.map((r) => <BenchmarkClassification key={r.run_id} run={r} />)}
      {business?.customer ? (
        <CustomerRun run={business.customer} />
      ) : (
        <StateNote kind="not_evaluated">Choose a business under Performance by Horizon and run the customer-score check to see how the score ranks that business&apos;s own customers.</StateNote>
      )}
    </div>
  );
}

function CustomerRun({ run }: { run: PresentedValidationRun }) {
  const age = ageDays(run.generated_at);
  return (
    <Block title="Customer score checked on this business's own customers" tag="business" note={run.headline ?? undefined}>
      {age !== null && age >= STALE_AFTER_DAYS ? <div className="mb-3"><StateNote kind="stale">This check was run {age} days ago. Run it again if this business&apos;s sales have changed.</StateNote></div> : null}
      {run.target?.definition ? <p className="mb-3 text-sm text-muted">Label: {run.target.definition}. {run.target.limits}</p> : null}
      {(run.cutoffs ?? []).map((c) => (
        <div key={c.cutoff} className="mb-5 last:mb-0">
          <h4 className="mb-2 text-sm font-semibold text-foreground">Cut-off {c.cutoff}</h4>
          {c.status === "evaluated" && c.cards ? (
            <>
              <EvaluatedOn
                facts={[
                  ["Cut-off", c.cutoff],
                  ["Label window", c.label_window ? c.label_window.join(" to ") : null],
                  ["Customers", nf(c.customers)],
                  ["Inactive in the window", nf(c.inactive)],
                  ["Model", run.model?.name ? `${run.model.name} ${run.model.version ?? ""}` : null],
                ]}
              />
              <MetricGrid cards={c.cards} />
            </>
          ) : (
            <StateNote kind="insufficient">{c.reason ?? "There were not enough customers or too few of one kind."}</StateNote>
          )}
        </div>
      ))}
      {run.calibration ? <div className="mt-3"><MetricCard card={run.calibration} /></div> : null}
    </Block>
  );
}

// ------------------------------------------------------------------------------------------------ Model vs baseline
export function BaselinePanel({ data, business }: { data: EvaluationOverview; business: BusinessValidation | null }) {
  const models = data.sections.training.forecasting;
  const runs = data.sections.benchmark.runs.filter((r) => r.kind === "forecast");
  const horizons = (business?.forecast?.horizons ?? []).filter((h) => h.status === "evaluated");
  return (
    <div className="space-y-5">
      <Panel>
        <p className="max-w-3xl text-sm text-muted">
          A model is only useful if it beats a simple rule. Each comparison below is on the same rows and period for both. A positive change means the
          model&apos;s error is lower than the baseline&apos;s.
        </p>
      </Panel>
      <Block title="Registered models vs yesterday's value" tag="training">
        {models.length === 0 ? <StateNote kind="not_evaluated">No forecasting models are registered.</StateNote> : (
          <DataTable
            headers={["Model", "Model MAE", "Baseline MAE", "Change in MAE", "Result"]}
            rows={models.map((m) => {
              const imp = find(m.baseline.test, "mae_vs_baseline");
              return [
                `${m.model_name} ${m.version}`, <CardCell key="a" card={find(m.test, "mae")} />, <CardCell key="b" card={find(m.baseline.test, "baseline_mae")} />,
                <CardCell key="c" card={imp} />,
                m.baseline.verdict ? VERDICT_TEXT[m.baseline.verdict] : (imp?.reason ?? "Not comparable"),
              ];
            })}
          />
        )}
      </Block>
      {runs.map((r) => (
        <Block key={r.run_id} title={`${r.title}: change in MAE vs the best baseline`} tag="benchmark">
          {(r.sections ?? []).map((s) => (
            <div key={s.name} className="mb-4 last:mb-0">
              <EvaluatedOn facts={[["Section", s.name], ["Baseline used", s.baseline_used_for_comparison ?? "none recorded"], ["Test points", nf(s.n_test_points)], ["Test window", s.test_window ? s.test_window.join(" to ") : null]]} />
              <DataTable
                headers={["Method", "MAE", "Change vs baseline"]}
                rows={s.rows.filter((x) => x.kind !== "baseline").map((x) => {
                  const by = byKey(x.cards);
                  return [x.method, <CardCell key="a" card={by.mae} />, <CardCell key="b" card={by.mae_vs_baseline} />];
                })}
              />
            </div>
          ))}
        </Block>
      ))}
      <Block title="This business's forecast vs simple references" tag="business" note="A ratio below 1 means the selected method had the lower error on the untouched holdout.">
        {horizons.length === 0 ? <StateNote kind="not_evaluated">Choose a business under Performance by Horizon and run its validation to see this.</StateNote> : (
          <DataTable
            headers={["Horizon", "Selected method", "vs naive (last value)", "vs trailing mean", "vs seasonal naive", "Result"]}
            rows={horizons.map((h) => {
              const r = (n: string) => h.baseline_comparison?.find((c) => c.reference === n)?.mae_ratio;
              const f = (v: number | null | undefined) => (typeof v === "number" ? v.toFixed(2) : "not available");
              return [`${h.horizon_days} days`, h.method ?? "—", f(r("naive_last")), f(r("trailing_mean_28")), f(r("seasonal_naive_7")), (h.verdict ?? "").replace(/_/g, " ")];
            })}
          />
        )}
      </Block>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ Horizon / business
function HorizonBlock({ h, run }: { h: PresentedHorizon; run: PresentedValidationRun }) {
  return (
    <Block title={`${h.horizon_days}-day horizon`} tag="business" note={h.statement ?? undefined}>
      {h.status === "evaluated" ? (
        <>
          <EvaluatedOn
            facts={[
              ["Data", run.dataset?.first_date ? `${run.dataset.first_date} to ${run.dataset.last_date}` : null],
              ["Horizon", `${h.horizon_days} days ahead`],
              ["Method", h.method],
              ["Backtest periods", nf(h.origins)],
              ["Selection / holdout periods", h.selection_origins !== undefined ? `${nf(h.selection_origins)} / ${nf(h.holdout_origins)}` : null],
              ["Scored on", "the untouched holdout periods only"],
            ]}
          />
          <MetricGrid cards={h.cards} />
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3"><MetricCard card={h.interval_coverage} /></div>
        </>
      ) : h.status === "descriptive_only" ? (
        <>
          <StateNote kind="insufficient">There are too few backtest periods ({nf(h.origins)}) to keep a holdout, so these figures describe those periods only. Nothing was selected and this is not a validation.</StateNote>
          <div className="mt-3"><DataTable headers={["Reference method", "MAE", "RMSE", "WAPE"]} rows={(h.references ?? []).map((r) => [r.method, <CardCell key="a" card={r.cards[0]} />, <CardCell key="b" card={r.cards[1]} />, <CardCell key="c" card={r.cards[2]} />])} /></div>
        </>
      ) : h.status === "refused" ? (
        <StateNote kind="failed">The product declined to forecast this horizon. {h.statement}</StateNote>
      ) : <StateNote kind="insufficient">{h.statement}</StateNote>}
    </Block>
  );
}

export function HorizonPanel({ business, businessPicker }: { business: BusinessValidation | null; businessPicker: React.ReactNode }) {
  const run = business?.forecast ?? null;
  const age = ageDays(run?.generated_at);
  return (
    <div className="space-y-5">
      <Panel>
        <p className="max-w-3xl text-sm text-muted">
          Registered platform models predict one day ahead, so there is no breakdown by horizon for them. Horizon figures come from a backtest on one
          business&apos;s own sales (7, 14 and 28 days ahead).
        </p>
      </Panel>
      {businessPicker}
      {run ? (
        <>
          {age !== null && age >= STALE_AFTER_DAYS ? <StateNote kind="stale">This validation was run {age} days ago. Run it again if this business&apos;s sales have changed since.</StateNote> : null}
          <Panel title="What was tested">
            <p className="text-sm text-foreground">{run.headline}</p>
            {run.series?.metric_guidance ? <p className="mt-2 text-sm text-muted">{run.series.metric_guidance}</p> : null}
            <p className="mt-2 text-xs text-muted">Run {run.run_id} · {when(run.generated_at)}</p>
          </Panel>
          {(run.horizons ?? []).map((h) => <HorizonBlock key={h.horizon_days} h={h} run={run} />)}
        </>
      ) : null}
    </div>
  );
}

export function BusinessPicker({ selected, onSelect, validation, busy, error, onRun }: {
  selected: string;
  onSelect: (id: string) => void;
  validation: BusinessValidation | null;
  busy: boolean;
  error: string | null;
  onRun: (kind: "forecast" | "customer") => void;
}) {
  const [businesses, setBusinesses] = useState<Business[] | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    api.myBusinesses().then((b) => live && setBusinesses(b)).catch(() => live && setFailed(true));
    return () => { live = false; };
  }, []);
  return (
    <Panel title="Business validation">
      {failed ? <StateNote kind="failed">Your businesses could not be loaded.</StateNote> : null}
      {businesses && businesses.length === 0 ? <EvalEmptyState message="This account owns no business. Business validation only runs on a business you own." /> : (
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted">
            Business
            <select className="input" value={selected} onChange={(e) => onSelect(e.target.value)} disabled={!businesses || busy}>
              <option value="">Choose a business…</option>
              {(businesses ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </label>
          <button type="button" className={btnSecondary} disabled={!selected || busy} onClick={() => onRun("forecast")}>
            {busy ? "Running…" : "Run forecast validation"}
          </button>
          <button type="button" className={btnSecondary} disabled={!selected || busy} onClick={() => onRun("customer")}>
            Run customer-score check
          </button>
        </div>
      )}
      {error ? <div className="mt-3"><StateNote kind="failed">{error}</StateNote></div> : null}
      {selected && validation && !validation.forecast && !validation.customer ? (
        <div className="mt-3"><StateNote kind="not_evaluated">No validation has been run for this business yet. Running one only reads its data; it changes no model.</StateNote></div>
      ) : null}
    </Panel>
  );
}

// ------------------------------------------------------------------------------------------------ Setup
export function SetupPanel({ data, business }: { data: EvaluationOverview; business: BusinessValidation | null }) {
  const models = [...data.sections.training.forecasting, ...data.sections.training.classification];
  const runs = data.sections.benchmark.runs;
  return (
    <div className="space-y-5">
      <Panel>
        <p className="max-w-3xl text-sm text-muted">What each result was measured on. Two results are only comparable when these match.</p>
      </Panel>
      <Block title="Registered models" tag="training">
        <DataTable
          headers={["Model", "Dataset", "Split", "Seed", "Features", "Code revision", "Trained"]}
          rows={models.map((m) => [`${m.model_name} ${m.version}`, m.setup.dataset_version, m.setup.split_scheme, m.setup.random_seed ?? "not recorded", String(m.setup.features.length), m.setup.code_revision ?? "not recorded", when(m.setup.trained_at)])}
          empty="No models are registered."
        />
        {models.some((m) => m.setup.splits) ? (
          <div className="mt-4">
            <h4 className="mb-2 text-sm font-semibold text-foreground">Rows and dates per block</h4>
            <DataTable
              headers={["Model", "Train", "Validation", "Test"]}
              rows={models.filter((m) => m.setup.splits).map((m) => {
                const s = m.setup.splits!;
                const f = (b?: { rows: number; first?: string; last?: string }) => (b ? `${nf(b.rows)} rows${b.first ? `, ${b.first} to ${b.last}` : ""}` : "—");
                return [`${m.model_name} ${m.version}`, f(s.train), f(s.validation), f(s.test)];
              })}
            />
          </div>
        ) : null}
      </Block>
      <Block title="Benchmark runs" tag="benchmark">
        <DataTable headers={["Task", "Run", "Evidence class", "Code revision", "Created"]} rows={runs.map((r) => [r.title, r.run_id, r.evidence_class ?? "not recorded", r.git_revision ?? "not recorded", when(r.created_utc)])} empty="No benchmark runs are stored." />
      </Block>
      {business?.forecast ? (
        <Block title="Business validation data" tag="business">
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <div><dt className="text-muted">Data covered</dt><dd>{business.forecast.dataset?.first_date ?? "—"} to {business.forecast.dataset?.last_date ?? "—"} ({nf(business.forecast.dataset?.days)} days)</dd></div>
            <div><dt className="text-muted">Days without a sales row</dt><dd>{nf(business.forecast.data_quality?.calendar_days_without_rows)} — {business.forecast.data_quality?.missing_day_treatment}</dd></div>
            <div><dt className="text-muted">Demand pattern</dt><dd>{business.forecast.series?.series_class ?? "—"} / {business.forecast.series?.pattern ?? "—"}</dd></div>
            <div><dt className="text-muted">Code revision</dt><dd>{business.forecast.code_revision ?? "not recorded"}</dd></div>
          </dl>
        </Block>
      ) : null}
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ Limitations
export function LimitationsPanel({ data, business }: { data: EvaluationOverview; business: BusinessValidation | null }) {
  const notEvidence = business?.forecast?.not_evidence_of ?? [];
  return (
    <div className="space-y-5">
      <Panel title="What these numbers do not show">
        <ul className="list-disc space-y-2 pl-5 text-sm text-foreground">
          {data.limitations.map((l) => <li key={l}>{l}</li>)}
          {notEvidence.map((l) => <li key={l}>A business backtest is not evidence of {l}.</li>)}
        </ul>
      </Panel>
      <Panel title="Live use">
        <EvidenceTag kind="production" />
        <div className="mt-2"><StateNote kind="not_evaluated">{data.sections.production.reason}</StateNote></div>
      </Panel>
      <Panel title="Glossary">
        <dl className="space-y-4">
          {data.glossary.map((g) => (
            <div key={g.key}>
              <dt className="text-sm font-semibold text-foreground">{g.name} ({g.abbr}) <span className="font-normal text-muted">· {g.direction_text}</span></dt>
              <dd className="text-sm text-muted">{g.definition}{g.sign_note ? ` ${g.sign_note}` : ""}{g.caveat ? ` Keep in mind: ${g.caveat}` : ""}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </div>
  );
}

// ------------------------------------------------------------------------------------------------ History
export function HistoryPanel() {
  const [data, setData] = useState<ModelPerformance | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    researchApi.modelPerformance().then(setData).catch((e) => setError(String(e?.message ?? e)));
  }, []);
  if (error) return <StateNote kind="failed">{error}</StateNote>;
  if (!data) return <p role="status" className="text-sm text-muted">Loading…</p>;
  const metricText = (m: Record<string, unknown>, task: string) => {
    const v = task === "forecasting" ? m.mae : m.roc_auc;
    return typeof v === "number" && Number.isFinite(v) ? `${task === "forecasting" ? "MAE" : "ROC-AUC"} ${v.toFixed(task === "forecasting" ? 2 : 3)}` : "—";
  };
  return (
    <Panel title="Training history">
      <p className="mb-3 text-sm text-muted">Every training run on record, newest first. Only the headline figure is shown here; the model cards hold the full set.</p>
      <DataTable
        headers={["When", "Task / model", "Dataset", "Status", "Headline figure"]}
        rows={data.training_history.map((r) => [
          when(r.created_at), `${r.task} / ${r.model_type}`, r.dataset_version_label ?? "—",
          r.error_message ? `failed — ${r.error_message}` : r.status,
          r.status === "completed" ? metricText(r.metrics as Record<string, unknown>, r.task) : "—",
        ])}
        empty="No training runs recorded."
      />
      <p className="mt-3 text-xs text-muted">{fmtInt(data.training_history.length)} run(s).</p>
    </Panel>
  );
}

export type { MetricCardData };
