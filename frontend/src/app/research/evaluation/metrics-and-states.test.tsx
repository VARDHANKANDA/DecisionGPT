import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { BenchmarkRun, BusinessValidation, EvaluationOverview, MetricCardData } from "@/lib/research-api";

const evaluation = vi.fn();
const evaluationBusiness = vi.fn();
vi.mock("@/lib/research-api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/research-api")>();
  return {
    ...actual,
    researchApi: {
      ...actual.researchApi,
      evaluation: (...a: unknown[]) => evaluation(...a),
      evaluationBusiness: (...a: unknown[]) => evaluationBusiness(...a),
      modelPerformance: () => Promise.resolve({ training_history: [], summary: {} }),
    },
  };
});
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, myBusinesses: () => Promise.resolve([{ id: "b1", name: "Shop One" }]) } };
});

import EvaluationPage from "./page";

function card(key: string, abbr: string, display: string, over: Partial<MetricCardData> = {}): MetricCardData {
  return {
    key, name: `${abbr} full name`, abbr, task: "regression", unit: "ratio", direction: "lower_is_better", direction_text: "Lower is better",
    explanation: `Meaning of ${abbr}.`, caveat: "", sign_note: null, context: {}, status: "available", value: 1, display, reason: null, ...over,
  };
}
const na = (key: string, abbr: string, display: string, status: MetricCardData["status"], reason: string) =>
  card(key, abbr, display, { status, value: null, reason });

const forecastRun: BenchmarkRun = {
  run_id: "f1_run", task: "f1", title: "Daily unit sales, many series", kind: "forecast", evidence_class: "public_real_data", created_utc: "2026-10-15T00:00:00Z", git_revision: "d61f858",
  sections: [{
    name: "Daily unit sales", n_series: 350, n_test_points: 9800, test_window: ["2016-04-25", "2016-05-22"], baseline_used_for_comparison: "baseline:seasonal_naive_28",
    rows: [{
      method: "xgboost:depth6", kind: "single", selected_by_validation: true,
      cards: [card("mae", "MAE", "1.18 units/day"), card("rmse", "RMSE", "2.14 units/day"), card("wape", "WAPE", "70.5%"), card("relative_bias", "Rel. bias", "-3.0%"),
              card("rmsse", "RMSSE", "0.830", { caveat: "6 series with a constant training history could not be scaled and are not in this average." }),
              card("aggregate_daily_wape", "Agg. WAPE", "7.0%"), card("median_series_wape", "Median WAPE", "103.0%"), card("mae_vs_baseline", "vs baseline", "+18.7%")],
    }],
  }],
};

const singleSeriesRun: BenchmarkRun = {
  run_id: "f2_run", task: "f2", title: "One UK online retailer", kind: "forecast", evidence_class: "real_single_business_transactions", created_utc: null, git_revision: null,
  sections: [{
    name: "Total daily revenue (one series)", n_series: 1, n_test_points: 28, test_window: null, baseline_used_for_comparison: null,
    rows: [{
      method: "xgboost:depth6", kind: "single", selected_by_validation: true,
      cards: [card("mae", "MAE", "8.00 revenue/day"), card("rmse", "RMSE", "9.00 revenue/day"), card("wape", "WAPE", "24.0%"), card("relative_bias", "Rel. bias", "-1.0%"),
              na("rmsse", "RMSSE", "Not available", "not_available", "This run did not record a scale-based error for these series."),
              na("aggregate_daily_wape", "Agg. WAPE", "Not evaluated", "not_evaluated", "This is a single series, so adding series together changes nothing: see WAPE."),
              na("median_series_wape", "Median WAPE", "Not evaluated", "not_evaluated", "This is a single series, so there is no typical series to take the middle of: see WAPE."),
              na("mae_vs_baseline", "vs baseline", "Not available", "not_available", "No baseline was recorded.")],
    }],
  }],
};

const classRun: BenchmarkRun = {
  run_id: "c1_run", task: "c1", title: "Customer inactivity (proxy label)", kind: "classification", evidence_class: "real_data_proxy_label", created_utc: null, git_revision: null,
  rows_per_split: { train: 14805, validation: 4951, test: 5256 }, prevalence: { train: 0.576, validation: 0.677, test: 0.565 },
  rows: [{
    method: "random_forest", selected_by_validation: true,
    cards: [card("roc_auc", "ROC-AUC", "0.800"), card("pr_auc", "PR-AUC", "0.810"), card("brier", "Brier", "0.190"), card("brier_baseline", "Brier (constant)", "0.246"),
            card("brier_vs_baseline", "Brier vs constant", "+22.7%"), card("log_loss", "Log loss", "0.560", { caveat: "No constant-forecast reference was recorded for it." }), card("ece", "ECE", "0.090")],
  }],
};

function overview(runs: BenchmarkRun[], generatedAt = new Date().toISOString()): EvaluationOverview {
  return {
    generated_at: generatedAt,
    sections: {
      training: { label: "x", note: "y", empty: "No models are registered yet.", forecasting: [], classification: [] },
      benchmark: { available: true, label: "b", runs },
      production: { label: "Live use", status: "not_evaluated", reason: "Live accuracy is not aggregated here." },
    },
    availability: { forecasting_models: 0, classification_models: 0, benchmark_runs: runs.length },
    glossary: [], limitations: [],
  };
}

async function open(ov: EvaluationOverview) {
  evaluation.mockResolvedValue(ov);
  render(<EvaluationPage />);
  await screen.findByText("What this page shows");
}

beforeEach(() => {
  evaluation.mockReset();
  evaluationBusiness.mockReset();
});

describe("Evaluation page: additional benchmark metrics", () => {
  it("shows RMSSE, aggregate-day WAPE and median-series WAPE next to the other forecast metrics, with the sample and window it was measured on", async () => {
    await open(overview([forecastRun]));
    fireEvent.click(screen.getByRole("tab", { name: "Forecasting & Regression" }));
    const facts = await screen.findByRole("list", { name: "Evaluated on" }, { timeout: 2000 }).catch(() => screen.getByLabelText("Evaluated on"));
    expect(facts.textContent).toContain("Series:350");
    expect(facts.textContent).toContain("Test points:9,800");
    expect(facts.textContent).toContain("Test window:2016-04-25 to 2016-05-22");
    const row = screen.getByText(/xgboost:depth6/).closest("tr")!;
    for (const v of ["0.830", "7.0%", "103.0%", "-3.0%"]) expect(row.textContent).toContain(v);
    const head = within(row.closest("table")!).getAllByRole("columnheader").map((h) => h.textContent);
    expect(head).toEqual(expect.arrayContaining(["RMSSE", "Agg. WAPE", "Median WAPE", "Rel. bias"]));
  });

  it("explains every column from the cards themselves: direction, meaning and limits", async () => {
    await open(overview([forecastRun]));
    fireEvent.click(screen.getByRole("tab", { name: "Forecasting & Regression" }));
    const legend = (await screen.findByText("What these figures mean")).closest("details")!;
    expect(legend.textContent).toContain("Meaning of RMSSE.");
    expect(legend.textContent).toContain("Lower is better");
    expect(legend.textContent).toContain("6 series with a constant training history could not be scaled");
  });

  it("labels a metric a single-series run cannot give as 'Not evaluated' and one it did not record as 'Not available', never as a number", async () => {
    await open(overview([singleSeriesRun]));
    fireEvent.click(screen.getByRole("tab", { name: "Forecasting & Regression" }));
    const row = (await screen.findByText(/xgboost:depth6/)).closest("tr")!;
    expect(row.textContent).toContain("Not available");
    expect(row.textContent).toContain("Not evaluated");
    expect(row.textContent).toContain("8.00 revenue/day");
    expect(row.querySelector('[title*="single series"]')).toBeTruthy();                  // the reason is on the cell
  });

  it("shows log loss and the constant-forecast Brier reference with the rows and positive rates behind them", async () => {
    await open(overview([classRun]));
    fireEvent.click(screen.getByRole("tab", { name: "Classification" }));
    const row = (await screen.findByText(/random_forest/)).closest("tr")!;
    for (const v of ["0.560", "0.246", "+22.7%", "0.190"]) expect(row.textContent).toContain(v);
    const facts = screen.getByLabelText("Evaluated on");
    expect(facts.textContent).toContain("test 5,256");
    expect(facts.textContent).toContain("test 0.565");
    expect(screen.getByText(/No constant-forecast reference was recorded/)).toBeTruthy();
  });
});

describe("Evaluation page: states look different", () => {
  const descriptive = { horizon_days: 14, status: "descriptive_only", statement: "too few", origins: 3, cards: [], references: [], interval_coverage: na("coverage", "Coverage", "Not evaluated", "not_evaluated", "too few") };
  const refused = { horizon_days: 28, status: "refused", statement: "needs more history", cards: [], interval_coverage: na("coverage", "Coverage", "Not evaluated", "not_evaluated", "x") };
  const business = (generatedAt: string): BusinessValidation => ({
    evidence: "business", label: "x", customer: null,
    forecast: { kind: "forecast", run_id: "r1", generated_at: generatedAt, headline: "h", not_evidence_of: [], dataset: { first_date: "2026-01-01", last_date: "2026-06-01", days: 152 }, horizons: [descriptive, refused] },
  });

  async function openHorizon(b: BusinessValidation) {
    await open(overview([]));
    evaluationBusiness.mockResolvedValue(b);
    fireEvent.click(screen.getByRole("tab", { name: "Performance by Horizon" }));
    await screen.findByRole("option", { name: "Shop One" });
    fireEvent.change(screen.getByLabelText("Business"), { target: { value: "b1" } });
    await screen.findByText("14-day horizon");
  }

  it("shows 'not enough data', 'failed' and 'not evaluated' as different kinds of note, each with a word and an icon", async () => {
    await openHorizon(business(new Date().toISOString()));
    const kinds = Array.from(document.querySelectorAll("[data-state]")).map((n) => n.getAttribute("data-state"));
    expect(kinds).toEqual(expect.arrayContaining(["insufficient", "failed"]));
    expect(screen.getByText("Not enough data.")).toBeTruthy();
    expect(screen.getByText("Failed.")).toBeTruthy();
    expect(document.querySelector('[data-state="failed"]')!.getAttribute("role")).toBe("alert");     // announced; the others are polite status
    expect(document.querySelector('[data-state="insufficient"]')!.getAttribute("role")).toBe("status");
  });

  it("flags a validation that is a week or more old as possibly out of date", async () => {
    await openHorizon(business(new Date(Date.now() - 10 * 86_400_000).toISOString()));
    expect(screen.getByText("May be out of date.")).toBeTruthy();
    expect(screen.getByText(/run 10 days ago/i)).toBeTruthy();
  });

  it("does not call a fresh validation stale", async () => {
    await openHorizon(business(new Date().toISOString()));
    expect(screen.queryByText("May be out of date.")).toBeNull();
  });

  it("flags old loaded results on the page itself and offers a refresh", async () => {
    await open(overview([], new Date(Date.now() - 3 * 3600_000).toISOString()));
    expect(screen.getByText("May be out of date.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Refresh" })).toBeTruthy();
  });
});

describe("Evaluation page: customer top-decile lift", () => {
  it("shows the lift with the group it is based on and the proxy-label caveat", async () => {
    await open(overview([]));
    const lift = card("top_decile_lift", "Top-10% lift", "1.80×", { task: "classification", direction: "higher_is_better", direction_text: "Higher is better",
      caveat: "Ranking check against a proxy label, not churn.", context: { top_group: "13 highest-scored customers (10%, rounded up)" } });
    evaluationBusiness.mockResolvedValue({
      evidence: "business", label: "x", forecast: null,
      customer: { kind: "customer", run_id: "c1", generated_at: new Date().toISOString(), headline: "h", not_evidence_of: [], model: { name: "churn", version: "v1" },
                  target: { definition: "no purchase in 60 days", limits: "proxy" },
                  cutoffs: [{ cutoff: "2026-05-01", label_window: ["2026-05-02", "2026-06-30"], status: "evaluated", customers: 123, inactive: 40, cards: [lift] },
                            { cutoff: "2026-03-01", status: "insufficient_evidence", reason: "needs at least 30 customers" }] },
    } satisfies BusinessValidation);
    fireEvent.click(screen.getByRole("tab", { name: "Performance by Horizon" }));
    await screen.findByRole("option", { name: "Shop One" });
    fireEvent.change(screen.getByLabelText("Business"), { target: { value: "b1" } });
    await waitFor(() => expect(evaluationBusiness).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("tab", { name: "Classification" }));
    const c = await screen.findByLabelText("Top-10% lift full name: 1.80×");
    expect(c.textContent).toContain("Higher is better");
    expect(c.textContent).toContain("Group: 13 highest-scored customers (10%, rounded up)");
    expect(c.textContent).toContain("proxy label");
    const facts = screen.getAllByLabelText("Evaluated on").map((n) => n.textContent).join(" ");
    expect(facts).toContain("Label window:2026-05-02 to 2026-06-30");
    expect(facts).toContain("Customers:123");
    expect(screen.getByText("Not enough data.")).toBeTruthy();                             // the other cut-off is insufficient, not failed
  });
});
