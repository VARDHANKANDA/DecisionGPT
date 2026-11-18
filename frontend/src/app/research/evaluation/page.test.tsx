import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { BusinessValidation, EvaluationOverview, MetricCardData } from "@/lib/research-api";

const evaluation = vi.fn();
const evaluationBusiness = vi.fn();
const runEvaluationBusiness = vi.fn();
vi.mock("@/lib/research-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/research-api")>();
  return {
    ...actual,
    researchApi: {
      ...actual.researchApi,
      evaluation: (...a: unknown[]) => evaluation(...a),
      evaluationBusiness: (...a: unknown[]) => evaluationBusiness(...a),
      runEvaluationBusiness: (...a: unknown[]) => runEvaluationBusiness(...a),
      modelPerformance: () => Promise.resolve({ training_history: [], summary: {} }),
    },
  };
});
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, myBusinesses: () => Promise.resolve([{ id: "b1", name: "Shop One" }]) } };
});

import EvaluationPage from "./page";

function card(key: string, over: Partial<MetricCardData> = {}): MetricCardData {
  return {
    key, name: key.toUpperCase(), abbr: key.toUpperCase(), task: "regression", unit: "units/day", direction: "lower_is_better", direction_text: "Lower is better",
    explanation: `What ${key} means.`, caveat: "", sign_note: null, context: {}, status: "available", value: 1, display: "1.00 units/day", reason: null, ...over,
  };
}
const unavailable = (key: string, reason: string, status: MetricCardData["status"] = "not_available"): MetricCardData =>
  card(key, { status, value: null, display: status === "unreliable" ? "Not reliable" : status === "not_evaluated" ? "Not evaluated" : "Not available", reason });

const setup = { dataset_version: "platform_v1", feature_version: "f1", features: ["a", "b"], split_scheme: "chronological", source: "cli", trained_at: null, random_seed: 42, code_revision: "abc1234" };

function overview(over: Partial<EvaluationOverview["sections"]["training"]> = {}): EvaluationOverview {
  return {
    generated_at: "2026-10-21T10:00:00Z",
    sections: {
      training: {
        label: "x", note: "y", empty: null,
        forecasting: [{
          id: "m1", model_name: "sales_forecast_xgboost", model_type: "forecasting_xgboost", version: "v3", status: "active", validation_status: "validated",
          task: "forecasting", target: "units_sold per series per day", setup,
          test: [card("mae", { value: 4, display: "4.00 units/day", caveat: "Depends on the scale of what is forecast." }),
                 unavailable("mape", "4 of 100 actual values are zero, so a percentage error is undefined. Use WAPE instead.", "unreliable"),
                 unavailable("bias", "This model was trained before this value was recorded. Retrain it to record it.")],
          validation: [],
          baseline: { baseline: "Yesterday's value", same_rows: "Same rows.", test: [card("baseline_mae", { display: "5.00 units/day" }), card("mae_vs_baseline", { unit: "percent", display: "+20.0%" })], validation: [], verdict: "better_than_baseline" },
          interval_coverage: unavailable("coverage", "Registered platform models produce point forecasts only.", "not_evaluated"),
          by_horizon: { status: "not_evaluated", reason: "one day ahead" },
        }],
        classification: [{
          id: "m2", model_name: "churn_logistic_regression", model_type: "churn_logistic_regression", version: "v1", status: "active", validation_status: "validated",
          task: "classification", target: "churned (1 = customer left)", positive_class: "churned = 1", setup: { ...setup, split_scheme: "stratified random 80/20" },
          test: [card("roc_auc", { task: "classification", display: "0.800", direction: "higher_is_better", direction_text: "Higher is better" }), card("accuracy", { task: "classification", display: "0.850" })],
          validation: [],
          confusion_matrix: { tp: 30, fp: 10, fn: 20, tn: 140, n: 200, positive_class: "churned = 1", threshold: 0.4, rows_are: "actual", columns_are: "predicted at the threshold" },
          threshold_note: "All at one threshold.", class_balance: null, score_meaning: "A ranking score. It is not a calibrated probability.", calibrated: false,
          baseline: { status: "not_evaluated", reason: "none" },
        }],
        ...over,
      },
      benchmark: { available: false, label: "b", runs: [], reason: "No benchmark runs are stored yet." },
      production: { label: "Live use", status: "not_evaluated", reason: "Live accuracy is not aggregated here." },
    },
    availability: { forecasting_models: 1, classification_models: 1, benchmark_runs: 0 },
    glossary: [{ key: "mae", name: "Mean absolute error", abbr: "MAE", task: "regression", direction_text: "Lower is better", definition: "The average size of the miss.", caveat: null, sign_note: null }],
    limitations: ["Registered platform models are scored on their own research dataset."],
  };
}

const horizonRun: BusinessValidation = {
  evidence: "business", label: "x", customer: null,
  forecast: {
    kind: "forecast", run_id: "r1", generated_at: "2026-10-21T10:00:00Z", headline: "Backtested on this business's own history only.", not_evidence_of: ["business impact"],
    horizons: [{
      horizon_days: 7, status: "evaluated", statement: "7-day horizon statement.", origins: 12, method: "weekday_mean_4w", verdict: "beats_references",
      cards: [card("mae", { display: "3.20 units/day", value: 3.2 })],
      baseline_comparison: [{ reference: "naive_last", mae_ratio: 0.8, reading: "" }, { reference: "trailing_mean_28", mae_ratio: 0.9, reading: "" }, { reference: "seasonal_naive_7", mae_ratio: null, reading: "" }],
      interval_coverage: card("coverage", { unit: "percent", display: "78.0%", value: 78, context: { promised: "80%" } }),
    }],
  },
};

beforeEach(() => {
  evaluation.mockReset();
  evaluationBusiness.mockReset();
  runEvaluationBusiness.mockReset();
});

async function open(over?: Partial<EvaluationOverview["sections"]["training"]>) {
  evaluation.mockResolvedValue(overview(over));
  render(<EvaluationPage />);
  await screen.findByText("What this page shows");
}

describe("Evaluation metrics page: shell", () => {
  it("shows a loading state, then the sections as accessible tabs", async () => {
    evaluation.mockResolvedValue(overview());
    render(<EvaluationPage />);
    expect(screen.getByText("Loading evaluation data…")).toBeTruthy();
    await screen.findByText("What this page shows");
    const tabs = screen.getAllByRole("tab");
    expect(tabs.map((t) => t.textContent)).toEqual([
      "Overview", "Forecasting & Regression", "Classification", "Model vs Baseline", "Performance by Horizon", "Dataset & Setup", "Validation & Limitations", "History",
    ]);
    expect(screen.getByRole("tablist", { name: "Evaluation sections" })).toBeTruthy();
    expect(tabs[0].getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel")).toBeTruthy();
  });

  it("moves between tabs with the arrow keys", async () => {
    await open();
    const first = screen.getByRole("tab", { name: "Overview" });
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Forecasting & Regression" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(screen.getByRole("tab", { name: "Forecasting & Regression" }), { key: "End" });
    expect(screen.getByRole("tab", { name: "History" }).getAttribute("aria-selected")).toBe("true");
  });

  it("shows an error with a retry, and recovers", async () => {
    evaluation.mockRejectedValueOnce(new Error("Request failed with status 500")).mockResolvedValueOnce(overview());
    render(<EvaluationPage />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByText(/could not be loaded/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await screen.findByText("What this page shows");
    expect(evaluation).toHaveBeenCalledTimes(2);
  });

  it("says nothing has been evaluated yet instead of showing placeholders", async () => {
    const empty = overview({ forecasting: [], classification: [], empty: "No models are registered yet." });
    empty.availability = { forecasting_models: 0, classification_models: 0, benchmark_runs: 0 };
    evaluation.mockResolvedValue(empty);
    render(<EvaluationPage />);
    expect(await screen.findByText(/Nothing has been evaluated yet/)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Forecasting & Regression" }));
    expect(await screen.findByText("No models are registered yet.")).toBeTruthy();
  });

  it("keeps the four evidence kinds apart and says live use was not evaluated", async () => {
    await open();
    expect(screen.getByRole("region", { name: "Live use" }).textContent).toContain("Not evaluated");
    expect(screen.getByRole("region", { name: "Registered models" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Public benchmarks" })).toBeTruthy();
  });
});

describe("Evaluation metrics page: metric cards", () => {
  it("shows a recorded value with its direction, explanation and caveat", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Forecasting & Regression" }));
    const mae = (await screen.findAllByLabelText(/^MAE: 4.00 units\/day/))[0];
    expect(within(mae).getByText("Lower is better")).toBeTruthy();
    expect(within(mae).getByText("What mae means.")).toBeTruthy();
    expect(within(mae).getByText(/Depends on the scale/)).toBeTruthy();
  });

  it("explains an unreliable or unavailable metric in words and shows no number for it", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Forecasting & Regression" }));
    const mape = await screen.findByLabelText("MAPE: Not reliable");
    expect(mape.getAttribute("data-status")).toBe("unreliable");
    expect(within(mape).getByText(/percentage error is undefined/)).toBeTruthy();
    expect(within(mape).getByText(/Not reliable/, { selector: "span" })).toBeTruthy();    // stated in words, not colour alone
    const bias = screen.getByLabelText("BIAS: Not available");
    expect(within(bias).getByText(/Retrain it to record it/)).toBeTruthy();
    expect(screen.getByLabelText("COVERAGE: Not evaluated")).toBeTruthy();
  });

  it("never prints NaN or Infinity anywhere on any tab", async () => {
    await open();
    for (const t of screen.getAllByRole("tab")) {
      fireEvent.click(t);
      await waitFor(() => expect(t.getAttribute("aria-selected")).toBe("true"));
      expect(document.body.textContent).not.toMatch(/NaN|Infinity|\[object Object\]|undefined (units|%)/);
    }
  });
});

describe("Evaluation metrics page: classification", () => {
  it("shows the confusion matrix with its threshold and positive class, and does not call the score a probability", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Classification" }));
    const table = await screen.findByRole("table", { name: "Confusion matrix" });
    expect(within(table).getByText(/140 \(true negative\)/)).toBeTruthy();
    expect(within(table).getByText(/30 \(true positive\)/)).toBeTruthy();
    expect(table.textContent).toContain("Positive class: churned = 1");
    expect(table.textContent).toContain("threshold 0.4");
    expect(screen.getByText(/not a calibrated probability/)).toBeTruthy();
    expect(screen.getByLabelText("ACCURACY: 0.850")).toBeTruthy();
  });
});

describe("Evaluation metrics page: baseline comparison", () => {
  it("states whether the model beat the baseline on the same rows", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Model vs Baseline" }));
    const row = (await screen.findByText("sales_forecast_xgboost v3")).closest("tr")!;
    expect(row.textContent).toContain("5.00 units/day");
    expect(row.textContent).toContain("+20.0%");
    expect(row.textContent).toContain("Better than the baseline");
  });
});

describe("Evaluation metrics page: business validation by horizon", () => {
  it("lets the owner pick a business, run a validation and then reads back what was stored", async () => {
    await open();
    evaluationBusiness.mockResolvedValueOnce({ evidence: "business", label: "x", forecast: null, customer: null }).mockResolvedValue(horizonRun);
    runEvaluationBusiness.mockResolvedValue({});
    fireEvent.click(screen.getByRole("tab", { name: "Performance by Horizon" }));
    const select = await screen.findByLabelText("Business");
    await screen.findByRole("option", { name: "Shop One" });
    const runButton = screen.getByRole("button", { name: "Run forecast validation" }) as HTMLButtonElement;
    expect(runButton.disabled).toBe(true);                                       // nothing selected: nothing to run
    fireEvent.change(select, { target: { value: "b1" } });
    expect(await screen.findByText(/No validation has been run for this business yet/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Run forecast validation" }));
    await screen.findByText("7-day horizon");
    expect(runEvaluationBusiness).toHaveBeenCalledWith("b1", "forecast");
    expect(screen.getByLabelText("MAE: 3.20 units/day")).toBeTruthy();
    expect(screen.getByLabelText("COVERAGE: 78.0%").textContent).toContain("Promised level: 80%");
  });

  it("shows the failure of a run in words and leaves the page usable", async () => {
    await open();
    evaluationBusiness.mockResolvedValue({ evidence: "business", label: "x", forecast: null, customer: null });
    runEvaluationBusiness.mockRejectedValue(new Error("No sales history on file yet, so there is nothing to validate a forecast against."));
    fireEvent.click(screen.getByRole("tab", { name: "Performance by Horizon" }));
    await screen.findByRole("option", { name: "Shop One" });
    fireEvent.change(screen.getByLabelText("Business"), { target: { value: "b1" } });
    await screen.findByText(/No validation has been run/);
    fireEvent.click(screen.getByRole("button", { name: "Run forecast validation" }));
    expect((await screen.findByRole("alert")).textContent).toContain("No sales history on file yet");
    expect((screen.getByRole("button", { name: "Run forecast validation" }) as HTMLButtonElement).disabled).toBe(false);
  });
});

describe("Evaluation metrics page: limitations", () => {
  it("lists what the numbers do not show and the glossary from the server", async () => {
    await open();
    fireEvent.click(screen.getByRole("tab", { name: "Validation & Limitations" }));
    expect(await screen.findByText(/scored on their own research dataset/)).toBeTruthy();
    expect(screen.getByText(/The average size of the miss/)).toBeTruthy();
    expect(screen.getByText("Live accuracy is not aggregated here.")).toBeTruthy();
  });
});
