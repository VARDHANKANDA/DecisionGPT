import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const llmEvaluation = vi.fn();
const llmRunDetail = vi.fn();
vi.mock("@/lib/research-api", () => ({ researchApi: { llmEvaluation: () => llmEvaluation(), llmRunDetail: (id: string) => llmRunDetail(id) } }));

import LlmEvaluationPage from "./page";

function status(over: Record<string, unknown> = {}) {
  return {
    state: "ready_to_run",
    label: "Ready to run",
    evaluation: "not_run",
    evaluated: false,
    blockers: [],
    llm: { enabled: true, provider: "openai", model: "gpt-4.1-mini" },
    infrastructure: { task_spec: true, ground_truth: true, dataset_present: true, ready: true },
    tasks: { n: 27, n_primary: 23, n_supplementary: 4, repeats_per_task: 5, categories: [] },
    view_rules: "view rules",
    latest_run: null,
    limitations: ["One store, 89 days."],
    run_history: [],
    live_coverage: null,
    run_plan: { tasks: 27, repeats_per_task: 5, planned_attempts: 135, estimated_cost_usd_at_list_price: 0.0076 },
    live_verification: null,
    ...over,
  };
}

const run = (id: string, kind: string, extra: Record<string, unknown> = {}) => ({
  run_id: id, kind, status: "COMPLETED", mode: null, research_result: kind === "live_evaluation", mock: kind === "mock_validation", created_utc: "2026-10-14T05:00:00+00:00",
  finished_utc: null, planned_attempts: 2, completed_attempts: 2, n_tasks: 2, repeats: 1, provider: null, model: null, errors: 0, note: null, ...extra,
});

const attempt = (over: Record<string, unknown>) => ({
  task_id: "A01", repeat: 1, track: "primary", category: "aggregation", question: "What were my total sales in January 2025?", answer: "Your total sales were ₹14,59,083.",
  expected: 1459082.91, outcome: "correct", correct: true, path: "llm_analytics", path_class: "llm_answered", failure_category: null, excluded_from_accuracy: false,
  error: null, latency_s: 1.0, input_tokens: 1345, output_tokens: 452, cost_usd: 0.0000565, ...over,
});

const detail = (over: Record<string, unknown> = {}) => ({
  run_id: "run_live", kind: "live_evaluation", status: "PARTIALLY_COMPLETED", is_live_result: true, created_utc: "2026-10-14T05:00:00+00:00", finished_utc: null,
  provider: "openai", model_requested: "gpt-4.1-mini", models_returned: ["gpt-4.1-mini-2025-04-14"],
  summary: {
    run_type: "partial_pilot", note: null, tasks_in_spec: 27, task_ids_attempted: ["A01", "E03"], task_ids_not_attempted: [], repeats_used: 1, repeats_frozen: 5,
    primary: { attempts: 1, correct: 1, excluded: 0, errors: 0, outcomes: { correct: 1 } }, supplementary: { attempts: 1, correct: 0, excluded: 0, errors: 0, outcomes: {} },
    answer_paths: null, provider_requests: 2, attempt_errors: 0, models_returned: ["gpt-4.1-mini-2025-04-14"], input_tokens: 2700, output_tokens: 900,
    estimated_cost_usd_at_list_price: 0.00011, spec_sha256: "s", manifest_sha256: "m",
  },
  attempts: [
    attempt({}),
    attempt({ task_id: "E03", track: "supplementary", category: "gst", question: "What percentage came from 0% GST?", answer: "I don't have enough data.", expected: 54.1, outcome: "legacy_fallback", correct: false, path: "legacy_router", path_class: "legacy_fallback", failure_category: "low_confidence" }),
  ],
  technical: { spec_sha256: "s", manifest_sha256: "m", scorer_version: "score-1.0", ground_truth_version: "gt-1.0", retry_policy: "none", conditions: ["asof"], repeats: 1 },
  ...over,
});

beforeEach(() => {
  llmEvaluation.mockReset();
  llmRunDetail.mockReset();
});

describe("Research Console — LLM evaluation", () => {
  it("says 'Not evaluated' with no figures when no live run exists", async () => {
    llmEvaluation.mockResolvedValue(status({ run_history: [run("mock_a", "mock_validation")] }));
    render(<LlmEvaluationPage />);
    expect(await screen.findByText("Not evaluated")).toBeTruthy();
    expect(screen.queryByText(/Partial evaluation/)).toBeNull();
    expect(screen.queryByText("Results")).toBeNull();
    expect(screen.queryByText(/\d+(\.\d+)?\s?%/)).toBeNull();
    expect(llmRunDetail).not.toHaveBeenCalled(); // a mock record is not auto-selected as the default result
  });

  it("opens the latest live run by default and never calls a partial run complete", async () => {
    llmEvaluation.mockResolvedValue(
      status({
        run_history: [run("run_live", "live_evaluation", { run_type: "partial_pilot" })],
        live_coverage: [{
          provider: "openai", is_active_provider: true,
          runs: [{ run_id: "run_live", run_type: "partial_pilot", tasks: 2, repeats: 1, primary_correct: 1, primary_attempts: 1, provider_requests: 2, input_tokens: 2700, estimated_cost_usd_at_list_price: 0.00011 }],
          tasks_in_spec: 27, tasks_attempted_at_least_once: 27, task_ids_never_attempted: [], repeats_frozen: 5, max_repeats_any_run: 1,
          primary_correct_sum: 1, primary_attempts_sum: 1, provider_requests_sum: 2, estimated_cost_usd_sum: 0.00011, note: "Arithmetic over this provider's separate stored runs.",
        }],
      }),
    );
    llmRunDetail.mockResolvedValue(detail());
    render(<LlmEvaluationPage />);
    expect(await screen.findByText(/Partial evaluation — the five-repeat frozen benchmark is incomplete/)).toBeTruthy();
    await waitFor(() => expect(llmRunDetail).toHaveBeenCalledWith("run_live"));
    expect(await screen.findByText("What were my total sales in January 2025?")).toBeTruthy();
    expect(screen.getByText(/not a reliable accuracy estimate/)).toBeTruthy();
    expect(screen.getByText(/27 of 27 frozen tasks attempted at least once/)).toBeTruthy();
    // counts add up: 1 correct + 1 fallback
    expect(screen.getByText("Fallback (standard assistant)", { selector: "dt" }).nextElementSibling?.textContent).toBe("1");
    expect(screen.getByText("Correct", { selector: "dt" }).nextElementSibling?.textContent).toBe("1");
    // expected answer is shown next to the system answer
    expect(screen.getByText("1459082.91")).toBeTruthy();
  });

  it("filters the question table by outcome", async () => {
    llmEvaluation.mockResolvedValue(status({ run_history: [run("run_live", "live_evaluation")] }));
    llmRunDetail.mockResolvedValue(detail());
    render(<LlmEvaluationPage />);
    await screen.findByText("What were my total sales in January 2025?");
    fireEvent.change(screen.getByLabelText("Outcome"), { target: { value: "fallback" } });
    const table = screen.getByRole("table", { name: /Each question/ });
    expect(within(table).queryByText("What were my total sales in January 2025?")).toBeNull();
    expect(within(table).getByText("What percentage came from 0% GST?")).toBeTruthy();
    expect(screen.getByText("1 of 2 shown")).toBeTruthy();
  });

  it("labels a mock record as not a result when it is selected", async () => {
    llmEvaluation.mockResolvedValue(status({ run_history: [run("run_live", "live_evaluation"), run("mock_a", "mock_validation")] }));
    llmRunDetail.mockImplementation((id: string) => Promise.resolve(id === "mock_a" ? detail({ run_id: "mock_a", kind: "mock_validation", is_live_result: false }) : detail()));
    render(<LlmEvaluationPage />);
    await screen.findByText("What were my total sales in January 2025?");
    fireEvent.change(screen.getByLabelText(/Run shown/), { target: { value: "mock_a" } });
    expect(await screen.findByText(/carries no information about any model/)).toBeTruthy();
  });

  it("shows an error state instead of stale data when a run cannot be loaded", async () => {
    llmEvaluation.mockResolvedValue(status({ run_history: [run("run_live", "live_evaluation")] }));
    llmRunDetail.mockRejectedValue(new Error("boom"));
    render(<LlmEvaluationPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("boom");
    expect(screen.queryByText("Results")).toBeNull();
  });

  it("reports each provider's coverage separately and never as one combined score", async () => {
    const cov = (provider: string, correct: number) => ({
      provider, is_active_provider: provider === "openai",
      runs: [{ run_id: `run_${provider}`, run_type: "partial_pilot", tasks: 6, repeats: 1, primary_correct: correct, primary_attempts: 5, provider_requests: 6, input_tokens: 1, estimated_cost_usd_at_list_price: 0.0001 }],
      tasks_in_spec: 27, tasks_attempted_at_least_once: 6, task_ids_never_attempted: [], repeats_frozen: 5, max_repeats_any_run: 1,
      primary_correct_sum: correct, primary_attempts_sum: 5, provider_requests_sum: 6, estimated_cost_usd_sum: 0.0001, note: "never pooled",
    });
    llmEvaluation.mockResolvedValue(status({
      run_history: [run("run_openai", "live_evaluation", { provider: "openai" }), run("run_typesafe-jev", "live_evaluation", { provider: "typesafe-jev" })],
      live_coverage: [cov("openai", 4), cov("typesafe-jev", 5)],
    }));
    llmRunDetail.mockResolvedValue(detail());
    render(<LlmEvaluationPage />);
    expect(await screen.findByText(/Coverage — OpenAI \(current provider\)/)).toBeTruthy();
    expect(screen.getByText(/Coverage — TypeSafe Jev \(earlier provider\)/)).toBeTruthy();
    expect(screen.getByText(/never combined into one score/)).toBeTruthy();
    expect(screen.queryByText(/9 of 10/)).toBeNull();
  });
});
