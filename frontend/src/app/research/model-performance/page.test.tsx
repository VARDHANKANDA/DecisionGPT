import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { EvalMini, EvaluationSummary, EvaluationSummaryRow, ModelPerformance } from "@/lib/research-api";

const modelPerformance = vi.fn();
const runModelEvaluation = vi.fn();
const runPendingEvaluations = vi.fn();
vi.mock("@/lib/research-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/research-api")>();
  return {
    ...actual,
    researchApi: {
      ...actual.researchApi,
      modelPerformance: (...a: unknown[]) => modelPerformance(...a),
      runModelEvaluation: (...a: unknown[]) => runModelEvaluation(...a),
      runPendingEvaluations: (...a: unknown[]) => runPendingEvaluations(...a),
    },
  };
});
// recharts needs layout that jsdom does not have; the charts are not under test
vi.mock("recharts", () => {
  const Null = () => null;
  return { Bar: Null, BarChart: Null, CartesianGrid: Null, Legend: Null, ResponsiveContainer: ({ children }: { children?: unknown }) => children ?? null, Tooltip: Null, XAxis: Null, YAxis: Null };
});

import ModelPerformancePage from "./page";
import { EvaluationSummaryPanel } from "./evaluation-summary";

const mini = (display: string | null, value: number | null = null, over: Partial<EvalMini> = {}): EvalMini => ({
  value, display, status: value === null ? "not_available" : "available", kind: value === null ? "not_recorded" : "available", reason: value === null ? "not recorded" : null, ...over,
});

function row(over: Partial<EvaluationSummaryRow> = {}): EvaluationSummaryRow {
  return {
    model_id: "m1", model_name: "sales_forecast_xgboost", version: "v1", model_status: "active", dataset_version: "platform-forecasting-v1", evaluation_status: "evaluated",
    evaluation_kind: "re_evaluated", evaluation_reason: null, evaluated_at: "2026-10-23T10:00:00Z", can_run: false, test_window: ["2024-09-16", "2024-12-30"], n_eval: 4240,
    horizon: "1 day ahead", baseline_name: "Yesterday's value (1-day lag)", method: "Re-scored.", is_baseline_model: false,
    wape: mini("9.6%", 9.6), mae: mini("15.14 units/day", 15.14), rmse: mini("21.86 units/day", 21.86), mape: mini(null),
    baseline_wape: mini("15.6%", 15.6), wape_vs_baseline: mini("+38.6%", 38.6), mae_vs_baseline: mini(null), verdict_wape: "better_than_baseline", ...over,
  };
}

const pendingRow = (): EvaluationSummaryRow =>
  row({
    model_id: "m2", model_name: "sales_forecast_linear", version: "v2", dataset_version: "upload:abc:v1", evaluation_status: "pending", evaluation_kind: null, can_run: true, test_window: null,
    n_eval: null, wape: mini(null), baseline_wape: mini(null), wape_vs_baseline: mini(null), mae: mini("18.47 units/day", 18.47), rmse: mini("28.51 units/day", 28.51),
    evaluation_reason: "WAPE and the evaluated-row count were not recorded when this model was trained (older run).",
  });

const failedRow = (): EvaluationSummaryRow =>
  row({
    model_id: "m3", model_name: "sales_forecast_xgboost", version: "v2", evaluation_status: "failed", evaluation_kind: "re_evaluation_attempted", can_run: true, test_window: null, n_eval: null,
    wape: mini(null), baseline_wape: mini(null), wape_vs_baseline: mini(null), evaluation_reason: "Verification failed: the recomputed MAE/RMSE/MAPE do not reproduce the values recorded at training.",
  });

const unavailableRow = (): EvaluationSummaryRow =>
  row({
    model_id: "m4", model_name: "sales_forecast_naive", version: "v2", evaluation_status: "unavailable", evaluation_kind: "re_evaluation_attempted", can_run: true, test_window: null, n_eval: null,
    wape: mini(null), baseline_wape: mini(null), wape_vs_baseline: mini(null, null, { kind: "not_applicable" }), evaluation_reason: "The stored artifact file is missing.",
  });

function summary(rows: EvaluationSummaryRow[]): EvaluationSummary {
  return {
    basis: "Held-out TEST block of each model's own dataset (chronological split by date). Training and validation figures are never shown here.", rows,
    definitions: [{ key: "wape", name: "Weighted absolute percentage error", abbr: "WAPE", definition: "Total absolute error divided by total actual volume.", caveat: "Not defined when the actual total is zero.", direction_text: "Lower is better" }],
  };
}

function perf(rows: EvaluationSummaryRow[], over: Partial<ModelPerformance["summary"]> = {}): ModelPerformance {
  return {
    summary: { registered_models: rows.length, active_models: rows.length, experimental_models: 0, completed_training_runs: 0, failed_training_runs: 0, best_forecasting: null,
               best_forecasting_note: "Forecasting models here were scored on different datasets, so no model is named best; compare them only within one dataset.", best_churn: null, ...over },
    evaluation_summary: summary(rows),
    forecasting: { metrics: ["mae", "rmse", "mape"], models: [], chart: [] }, classification: { metrics: [], models: [], chart: [] }, training_history: [],
    filters: { tasks: ["forecasting"], dataset_versions: [], model_names: [] }, empty_state: null,
  };
}

beforeEach(() => {
  modelPerformance.mockReset();
  runModelEvaluation.mockReset();
  runPendingEvaluations.mockReset();
});

describe("EvaluationSummaryPanel", () => {
  const noop = () => {};

  it("shows an evaluated model's WAPE, MAE, RMSE, change vs baseline, baseline, sample size, period, horizon and dataset with consistent units", () => {
    render(<EvaluationSummaryPanel summary={summary([row()])} busy={null} message={null} onRun={noop} onRunPending={noop} />);
    const r = screen.getByTestId("eval-row-sales_forecast_xgboost-v1");
    for (const text of ["sales_forecast_xgboost v1", "platform-forecasting-v1", "Evaluated", "re-scored from the stored model", "9.6%", "15.14 units/day", "21.86 units/day", "+38.6%",
      "Yesterday's value (1-day lag)", "baseline WAPE 15.6%", "4,240", "2024-09-16 to 2024-12-30", "1 day ahead"]) {
      expect(within(r).getByText(text)).toBeInTheDocument();
    }
  });

  it("labels the evaluation as held-out test data, never training or validation", () => {
    render(<EvaluationSummaryPanel summary={summary([row()])} busy={null} message={null} onRun={noop} onRunPending={noop} />);
    expect(screen.getByText(/never from training or validation rows/i)).toBeInTheDocument();
    expect(screen.getByText(/Held-out TEST block/)).toBeInTheDocument();
    expect(screen.getByText(/not on any business/i)).toBeInTheDocument();
  });

  it("shows 'Not available' — never 0 or a made-up value — for a pending model, and offers the evaluation action", () => {
    const onRun = vi.fn();
    render(<EvaluationSummaryPanel summary={summary([pendingRow()])} busy={null} message={null} onRun={onRun} onRunPending={noop} />);
    const r = screen.getByTestId("eval-row-sales_forecast_linear-v2");
    expect(within(r).getByText("Pending")).toBeInTheDocument();
    expect(within(r).getAllByText("Not available").length).toBeGreaterThanOrEqual(4);       // WAPE, vs baseline, test n, test period
    expect(within(r).queryByText(/^0(\.0)?%$/)).toBeNull();
    expect(within(r).queryByText(/NaN|Infinity|undefined|null/)).toBeNull();
    expect(within(r).getByText("18.47 units/day")).toBeInTheDocument();                       // the recorded test MAE is still shown
    expect(within(r).getByText(/older run/)).toBeInTheDocument();
    fireEvent.click(within(r).getByRole("button", { name: /Run evaluation for sales_forecast_linear v2/ }));
    expect(onRun).toHaveBeenCalledWith("m2");
  });

  it("distinguishes pending, unavailable and failed with different words and shows the reason, with no WAPE for any of them", () => {
    render(<EvaluationSummaryPanel summary={summary([pendingRow(), unavailableRow(), failedRow()])} busy={null} message={null} onRun={noop} onRunPending={noop} />);
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getByText("Failed")).toBeInTheDocument();
    expect(screen.getByText("The stored artifact file is missing.")).toBeInTheDocument();
    expect(screen.getByText(/Verification failed/)).toBeInTheDocument();
    for (const id of ["eval-row-sales_forecast_naive-v2", "eval-row-sales_forecast_xgboost-v2"]) {
      expect(within(screen.getByTestId(id)).queryByText(/%/)).toBeNull();
    }
  });

  it("a naive baseline model shows 'Not applicable' for change vs baseline, not a made-up zero", () => {
    render(<EvaluationSummaryPanel summary={summary([unavailableRow()])} busy={null} message={null} onRun={noop} onRunPending={noop} />);
    expect(within(screen.getByTestId("eval-row-sales_forecast_naive-v2")).getByText("Not applicable")).toBeInTheDocument();
  });

  it("colours/signs a negative change vs baseline honestly (worse than the baseline is shown as negative)", () => {
    render(<EvaluationSummaryPanel summary={summary([row({ wape_vs_baseline: mini("-12.0%", -12) })])} busy={null} message={null} onRun={noop} onRunPending={noop} />);
    expect(screen.getByText("-12.0%")).toHaveClass("text-danger");
  });

  it("offers one batch action for pending models and disables the actions while a run is in progress", () => {
    const onRunPending = vi.fn();
    const { rerender } = render(<EvaluationSummaryPanel summary={summary([row(), pendingRow()])} busy={null} message={null} onRun={noop} onRunPending={onRunPending} />);
    fireEvent.click(screen.getByRole("button", { name: /Run evaluation for 1 pending model$/ }));
    expect(onRunPending).toHaveBeenCalled();
    rerender(<EvaluationSummaryPanel summary={summary([row(), pendingRow()])} busy="all" message={null} onRun={noop} onRunPending={onRunPending} />);
    expect(screen.getByRole("button", { name: "Evaluating…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Run evaluation for sales_forecast_linear v2/ })).toBeDisabled();
  });

  it("explains every column and the metrics (tooltips and a definitions section)", () => {
    render(<EvaluationSummaryPanel summary={summary([row()])} busy={null} message={null} onRun={noop} onRunPending={noop} />);
    expect(screen.getByRole("columnheader", { name: "WAPE" })).toHaveAttribute("title", expect.stringContaining("sum of absolute errors"));
    expect(screen.getByRole("columnheader", { name: "vs baseline" })).toHaveAttribute("title", expect.stringContaining("baseline WAPE − model WAPE"));
    expect(screen.getByText("What the figures mean")).toBeInTheDocument();
    expect(screen.getByText(/WAPE — Weighted absolute percentage error/)).toBeInTheDocument();
  });

  it("says plainly when no forecasting model is registered", () => {
    render(<EvaluationSummaryPanel summary={summary([])} busy={null} message={null} onRun={noop} onRunPending={noop} />);
    expect(screen.getByText(/No forecasting models are registered/)).toBeInTheDocument();
  });
});

describe("Model Performance page states", () => {
  it("shows a loading state, then the summary", async () => {
    let resolve!: (v: ModelPerformance) => void;
    modelPerformance.mockReturnValue(new Promise<ModelPerformance>((r) => (resolve = r)));
    render(<ModelPerformancePage />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
    resolve(perf([row()]));
    expect(await screen.findByText("Forecast accuracy on held-out test data")).toBeInTheDocument();
    expect(screen.queryByText("Loading…")).toBeNull();
  });

  it("shows the error and no figures when the request fails", async () => {
    modelPerformance.mockRejectedValue(new Error("Access denied — administrator access is required"));
    render(<ModelPerformancePage />);
    expect(await screen.findByText(/Access denied/)).toBeInTheDocument();
    expect(screen.queryByText("Forecast accuracy on held-out test data")).toBeNull();
  });

  it("does not name a 'best' model when the models were scored on different datasets", async () => {
    modelPerformance.mockResolvedValue(perf([row(), pendingRow()]));
    render(<ModelPerformancePage />);
    expect(await screen.findByText(/no model is named best/)).toBeInTheDocument();
    expect(screen.queryByText(/Best forecasting/)).toBeNull();
  });

  it("says so (and shows no numbers) when the server returns no evaluation summary", async () => {
    const p = perf([row()]);
    delete p.evaluation_summary;
    modelPerformance.mockResolvedValue(p);
    render(<ModelPerformancePage />);
    expect(await screen.findByText(/did not return an evaluation summary/)).toBeInTheDocument();
    expect(screen.queryByText("9.6%")).toBeNull();
  });

  it("runs the evaluation for one model, reports the outcome and reloads real data (no mock values in between)", async () => {
    modelPerformance.mockResolvedValueOnce(perf([pendingRow()])).mockResolvedValue(perf([row({ model_id: "m2", model_name: "sales_forecast_linear", version: "v2" })]));
    runModelEvaluation.mockResolvedValue({ model_id: "m2", status: "evaluated", reason: null, evaluated_at: "2026-10-23T10:00:00Z" });
    render(<ModelPerformancePage />);
    const btn = await screen.findByRole("button", { name: /Run evaluation for sales_forecast_linear v2/ });
    fireEvent.click(btn);
    expect(await screen.findByText(/Evaluation finished: the model was scored on its held-out test block/)).toBeInTheDocument();
    await waitFor(() => expect(runModelEvaluation).toHaveBeenCalledWith("m2"));
    expect(modelPerformance).toHaveBeenCalledTimes(2);
    expect(within(await screen.findByTestId("eval-row-sales_forecast_linear-v2")).getByText("9.6%")).toBeInTheDocument();
  });

  it("reports a failed evaluation request instead of silently ignoring it", async () => {
    modelPerformance.mockResolvedValue(perf([pendingRow()]));
    runModelEvaluation.mockRejectedValue(new Error("boom"));
    render(<ModelPerformancePage />);
    fireEvent.click(await screen.findByRole("button", { name: /Run evaluation for sales_forecast_linear v2/ }));
    expect(await screen.findByText(/The evaluation request failed: boom/)).toBeInTheDocument();
  });
});
