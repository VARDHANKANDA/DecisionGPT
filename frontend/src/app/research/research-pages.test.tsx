import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const api = {
  summary: vi.fn(),
  validationReport: vi.fn(),
  architectureEvaluation: vi.fn(),
  externalBenchmark: vi.fn(),
  causalAssessment: vi.fn(),
  riskAssessment: vi.fn(),
  modelComparison: vi.fn(),
  preprocessingPlan: vi.fn(),
  runPreprocessing: vi.fn(),
  downloadPreprocessed: vi.fn(),
  listExperiments: vi.fn(),
  experimentManifest: vi.fn(),
  runExperiment: vi.fn(),
  mlBenchmark: vi.fn(),
  modelPerformance: vi.fn(),
  llmEvaluation: vi.fn(),
};
vi.mock("@/lib/research-api", () => ({
  researchApi: new Proxy(
    {},
    {
      get: (_t, k: string) => (...a: unknown[]) =>
        (api as Record<string, (...x: unknown[]) => unknown>)[k]?.(...a) ?? Promise.resolve(null),
    }
  ),
}));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));

import Overview from "./page";
import Validation from "./validation/page";
import Architecture from "./agent-evaluation/page";
import Causal from "./causal-evaluation/page";
import Risk from "./risk-calibration/page";
import ModelComparison from "./model-comparison/page";
import { PreprocessingPanel } from "@/components/preprocessing-panel";
import DigitalTwinMoved from "./digital-twin-evaluation/page";
import Experiments from "./experiments/page";
import MlBenchmark from "./ml-benchmark/page";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }), usePathname: () => "/research" }));

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset());
  replace.mockReset();
});

describe("Research overview", () => {
  it("labels every finding with its evidence type and shows the latest verified date", async () => {
    api.summary.mockResolvedValue({
      objective: "Evaluate components.", datasets: [{ name: "POS", provenance: "real", observations: 80, period: "2025-01-08 to 2025-03-31", status: "measured" },
        { name: "Other", provenance: "synthetic", observations: null, period: null, status: "not_evaluated" }],
      algorithms: ["Ridge Regression"], n_algorithms: 5, methodology: ["Chronological split"], measured_metrics: ["MAE"],
      status: { experiments_completed: 18, experiments_failed: 0, model_comparison_runs: 2, live_llm_runs: 2, validation_state: "passed_with_warnings", validation_counts: { passed: 40, failed: 0, warning: 3, not_applicable: 2 } },
      key_findings: [{ evidence: "simulated", area: "Architecture evaluation", text: "Full system had higher regret.", source: "experiments/r1" }],
      limitations: ["One store."], latest_verified_run: "2026-10-14T07:09:50+00:00",
      evidence_legend: [], generated_utc: "2026-10-14T08:00:00+00:00",
    });
    render(<Overview />);
    expect(await screen.findByText("Full system had higher regret.")).toBeTruthy();
    expect(screen.getAllByText("Simulated").length).toBeGreaterThan(0);
    expect(screen.getByText("Total Models Registered")).toBeTruthy();
    expect(screen.getByText("Datasets in Registry")).toBeTruthy();
  });
});

describe("Validation", () => {
  const base = { datasets: [{ key: "a", label: "A", rows: 10 }], generated_utc: "2026-10-14T08:00:00+00:00" };

  it("never presents zero checks as a pass", async () => {
    api.validationReport.mockResolvedValue({ ...base, state: "no_checks_run", counts: { passed: 0, failed: 0, warning: 0, not_applicable: 1 }, checks_run: 0, total_checks: 1,
      checks: [{ id: "drift", group: "data", subject: "x", rule: "Drift", status: "not_applicable", observed: null, explanation: "No pair.", remedy: null }] });
    render(<Validation />);
    expect(await screen.findByText("No checks were run")).toBeTruthy();
    expect(screen.getByText(/this is not a pass/)).toBeTruthy();
    expect(screen.queryByText("All checks passed")).toBeNull();
  });

  it("separates passed, failed, warning and not applicable and shows remedies for failures", async () => {
    api.validationReport.mockResolvedValue({ ...base, state: "failed", counts: { passed: 5, failed: 1, warning: 2, not_applicable: 3 }, checks_run: 8, total_checks: 11,
      checks: [
        { id: "required_columns", group: "data", subject: "POS", rule: "All required columns are present", status: "failed", observed: { missing: ["price"] }, explanation: "Required column(s) missing: price.", remedy: "Add or map the missing columns." },
        { id: "date_continuity", group: "data", subject: "POS", rule: "No missing dates", status: "warning", observed: { n_missing: 1 }, explanation: "1 date missing.", remedy: "Confirm the gap." },
        { id: "ok", group: "data", subject: "POS", rule: "Non-empty", status: "passed", observed: 10, explanation: "Rows present.", remedy: null },
      ] });
    render(<Validation />);
    expect(await screen.findByText("Validation failed")).toBeTruthy();
    expect(screen.getByText(/Add or map the missing columns/)).toBeTruthy();
    expect(screen.getByText("All required columns are present")).toBeTruthy();
    expect(screen.queryByText("Non-empty")).toBeNull(); // default view = needs attention
    fireEvent.click(screen.getByRole("button", { name: "Passed" }));
    expect(screen.getByText("Non-empty")).toBeTruthy();
  });
});

describe("Architecture evaluation", () => {
  it("shows an architecture that produced no decision as not applicable, not as zero", async () => {
    api.architectureEvaluation.mockResolvedValue({
      headline: "Simulated headline.", architectures: [{ key: "A", name: "Prediction only", includes: ["forecast"], produces: "A forecast." }],
      metric_definitions: [{ metric: "Latency", unit: "seconds", better: "lower", definition: "Wall-clock." }],
      primary_evidence: null, frozen_suite: null, comparability: ["same scenarios"], limitations: ["simulated"],
      single_decision: { n_decisions_per_architecture: 1, goal_target_percent: 15, caveats: ["One decision only."], rows: [
        { key: "A", label: "Prediction only", status: "not_applicable", selected_strategy: null, goal_achievement: null, expected_benefit: null, risk_adjusted_score: null, latency_seconds: 1.03, note: "No decision was produced." },
        { key: "B", label: "B", status: "evaluated", selected_strategy: "Price +5%", goal_achievement: 0.33, expected_benefit: 5653.75, risk_adjusted_score: 2826.88, latency_seconds: 1.6, note: null }] },
    });
    render(<Architecture />);
    expect(await screen.findByText(/Not applicable — no decision was produced/)).toBeTruthy();
    expect(screen.getByText(/n = 1/)).toBeTruthy();
    expect(screen.getByText("Not evaluated.")).toBeTruthy(); // main result panel has no stored evidence
  });
});

describe("Causal evaluation", () => {
  it("states unsupported pairs without an effect number", async () => {
    api.causalAssessment.mockResolvedValue({
      assessment: { distinguish: [{ term: "Correlation", meaning: "Move together." }], pairs: [
        { pair: "Real: marketing -> units", treatment: "marketing_spend", outcome: "units", status: "unsupported", reasons: ["no variation"], needs: ["an experiment"] }] },
      known_truth_simulation: null,
      graph_evidence: { overview: { total_graph_versions: 3, businesses_with_a_graph: 3, evidence_counts_latest_per_business: { assumed: 30, causally_validated: 0 } }, method_validation: null },
    });
    render(<Causal />);
    expect(await screen.findByText(/1 of 1 candidate treatment/)).toBeTruthy();
    expect(screen.getByText("Unsupported")).toBeTruthy();
    expect(screen.getByText(/Not evaluated: the known-truth simulation has not been run/)).toBeTruthy();
    expect(screen.getByText(/Causally validated edges:/).textContent).toMatch(/Causally validated edges:\s*0/);
  });
});

describe("Risk calibration", () => {
  it("does not calibrate the decision risk score and lists unmet prerequisites", async () => {
    api.riskAssessment.mockResolvedValue({
      definitions: [{ kind: "Decision risk score", is_probability: false, meaning: "Heuristic.", calibration: "not_applicable", why: "Not a probability." }],
      churn_probability_calibration: null, forecast_uncertainty: [],
      decision_risk_score: { status: "not_evaluated", recorded_real_outcomes: 0, prerequisites: [{ need: "Observed outcomes recorded", met: false, observed: 0 }], next_step: "Record outcomes." },
      synthetic_variant_study: { evidence_type: "simulated", note: "Study.", verdict: "R3: not promoted", variants: [] },
    });
    render(<Risk />);
    expect(await screen.findByText(/Calibration is/)).toBeTruthy();
    expect(screen.getByText("Observed outcomes recorded (observed: 0)")).toBeTruthy();
    expect(screen.getByText(/no stored churn-calibration run/)).toBeTruthy();
    expect(screen.getByText(/no model comparison has been run/)).toBeTruthy();
  });
});

describe("Model comparison", () => {
  it("shows 'Not evaluated' for a dataset with no run instead of empty numbers", async () => {
    api.modelComparison.mockResolvedValue({ datasets: { pos: null }, available: [], not_run: ["pos"], dataset_catalogue: { pos: { name: "POS revenue", provenance: "real", source: "s", target: "t", unit: "INR" } } });
    render(<ModelComparison />);
    expect(await screen.findByText("Not evaluated.")).toBeTruthy();
    expect(screen.getByText("POS revenue")).toBeTruthy();
  });
});

describe("Preprocessing panel", () => {
  const plan = {
    version_id: "v1", rows: 60, columns: 3, duplicate_rows: 0, schema: [{ name: "Order Date", dtype: "str", missing: 0 }, { name: "Revenue", dtype: "float64", missing: 2 }], runs: [],
    steps: [
      { id: "normalize_names", title: "Normalise column names", rationale: "r", applies: true, default_enabled: true, affected_rows: null, affected_columns: ["Order Date"], detail: "1 column name would change", status: "proposed" },
      { id: "parse_dates", title: "Parse date columns", rationale: "r", applies: false, default_enabled: false, affected_rows: 0, affected_columns: [], detail: "none", status: "not_applicable" },
    ],
  };

  it("proposes only applicable steps, runs the selected ones and reports before/after", async () => {
    api.preprocessingPlan.mockResolvedValue(plan);
    api.runPreprocessing.mockResolvedValue({ status: "completed", run_id: "pp_20261014T000000Z_abcd1234", source_version_id: "v1", created_utc: "x", rows_in: 60, rows_out: 60,
      columns_in: 3, columns_out: 4, rows_removed: 0, raw_dataset_modified: false,
      steps: [{ id: "normalize_names", title: "Normalise column names", status: "applied", rows_affected: 0, columns_affected: ["order_date"], detail: "1 column(s) renamed", rationale: "r" }] });
    render(<PreprocessingPanel versionId="v1" />);
    expect(await screen.findByText("Normalise column names")).toBeTruthy();
    expect((screen.getByLabelText(/Parse date columns/) as HTMLInputElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Run preprocessing" }));
    await waitFor(() => expect(api.runPreprocessing).toHaveBeenCalledWith("v1", ["normalize_names"]));
    expect(await screen.findByText(/Completed — pp_20261014T000000Z_abcd1234/)).toBeTruthy();
    expect(screen.getByText(/Source dataset modified: no/)).toBeTruthy();
    expect(screen.getByText(/Rows removed: 0/)).toBeTruthy();
  });

  it("reports a failed run as a failure", async () => {
    api.preprocessingPlan.mockResolvedValue(plan);
    api.runPreprocessing.mockRejectedValue(new Error("Another run is in progress"));
    render(<PreprocessingPanel versionId="v1" />);
    await screen.findByText("Normalise column names");
    fireEvent.click(screen.getByRole("button", { name: "Run preprocessing" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Another run is in progress");
  });
});

describe("Removed Digital Twin section", () => {
  it("only forwards old bookmarks to the overview", async () => {
    render(<DigitalTwinMoved />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/research"));
  });
});

describe("Removed Reproducibility section", () => {
  it("forwards old bookmarks to the overview", async () => {
    render(<Experiments />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/research"));
  });
});

describe("ML benchmark", () => {
  const run = {
    run_id: "f1_x", task: "f1", title: "Daily unit sales, many series", kind: "forecast", evidence_class: "public_benchmark_real_data",
    created_utc: "2026-10-15T00:00:00Z", git_revision: "abc1234",
    sections: [{
      name: "Daily unit sales", n_series: 350, n_test_points: 9800, test_window: ["2016-04-25", "2016-05-22"], validation_selected_method: "single:catboost:depth6", paired: {},
      rows: [
        { method: "catboost:depth6", kind: "single", wape: 0.698, mae: 1.166, rmse: 2.117, bias: -0.05, aggregate_daily_wape: 0.077, selected_by_validation: true },
        { method: "baseline:seasonal_naive_28", kind: "baseline", wape: 0.869, mae: 1.45, rmse: 2.94, bias: -0.02, aggregate_daily_wape: 0.109, selected_by_validation: false },
      ],
    }],
  };
  const churn = {
    run_id: "c2_x", task: "c2", title: "Customer churn on the synthetic platform file", kind: "classification",
    evidence_class: "SYNTHETIC label drawn from a known logistic mechanism", created_utc: null, git_revision: null,
    rows: [{ method: "logistic_regression", roc_auc: 0.7963, pr_auc: 0.7626, brier: 0.1834, ece: 0.03, isotonic_ece: 0.055, sigmoid_ece: 0.044, selected_by_validation: true }],
  };

  it("labels every result by evidence class and shows baselines next to models", async () => {
    api.mlBenchmark.mockResolvedValue({ available: true, runs: [run, churn], reading_notes: ["Public benchmark results describe those datasets, not Indian SMEs."] });
    render(<MlBenchmark />);
    expect(await screen.findByText("Public benchmark · real data")).toBeTruthy();
    expect(screen.getByText("Synthetic")).toBeTruthy();
    expect(screen.getByText("catboost:depth6")).toBeTruthy();
    expect(screen.getByText("baseline:seasonal_naive_28")).toBeTruthy();
    expect(screen.getByText(/method selected on validation/)).toBeTruthy();
    expect(screen.getByText(/Public benchmark results describe those datasets/)).toBeTruthy();
  });

  it("shows an explicit empty state, never zeros, when no run is stored", async () => {
    api.mlBenchmark.mockResolvedValue({ available: false, runs: [], message: "No benchmark runs are stored yet." });
    render(<MlBenchmark />);
    expect(await screen.findByText("No benchmark runs are stored yet.")).toBeTruthy();
  });

  it("does not render a missing value as 0", async () => {
    api.mlBenchmark.mockResolvedValue({ available: true, runs: [{ ...run, sections: [{ ...run.sections[0], rows: [{ ...run.sections[0].rows[0], wape: null }] }] }] });
    render(<MlBenchmark />);
    await screen.findByText("catboost:depth6");
    expect(screen.getAllByText("not available").length).toBeGreaterThan(0);
  });
});
