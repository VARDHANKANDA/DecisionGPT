import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status = 404;
  },
  api: {
    listDecisions: () => Promise.resolve([{ id: "d1", created_at: new Date().toISOString(), expected_outcome_json: { expected_revenue: 100, baseline_revenue: 80 } }]),
    getOutcome: () => Promise.resolve({ id: "o1", decision_id: "d1", actual_outcome_json: { revenue: 90 }, goal_achieved: true, goal_achievement_score: 0.5, recorded_at: "" }),
    trackingDecision: () =>
      Promise.resolve({
        current: { recorded: true, response: "accepted", action_status: "unknown" },
        expectations: [
          { expectation: { id: "e1", metric: "units_sold", unit: "units", comparable_to_actuals: false, comparability_reason: "synthetic model" }, comparison: { status: "excluded", reason: "not_comparable" } },
        ],
      }),
    trackingReport: () =>
      Promise.resolve({
        decisions: { recorded: 1, executed_confirmed: 0, partially_executed: 0, latest_response: { accepted: 1 } },
        comparisons: {
          by_status: { evaluated: 1, excluded: 1 },
          details: [
            { expectation_id: "e1", metric: "units_sold", unit: "units", source_kind: "forecast", horizon_days: 7, window: ["2026-10-07", "2026-10-13"],
              status: "evaluated", reason: "same metric", expected: 160, observed: 150, signed_error: 10, data_cutoff: "2026-10-06", model: "m" },
            { expectation_id: "e2", metric: "revenue", unit: "INR", source_kind: "decision", horizon_days: 14, window: ["2026-10-07", "2026-10-20"],
              status: "excluded", reason: "not_comparable: the figure is not on your scale", expected: 100000, observed: 90000, data_cutoff: "2026-10-06", model: "m" },
          ],
        },
        awaiting_actuals: [
          { expectation_id: "e3", source_kind: "forecast", metric: "units_sold", unit: "units", window: ["2026-10-21", "2026-10-27"],
            window_finished: false, state: "no observation yet", comparable_to_actuals: true },
        ],
        forecast_accuracy: { statement: "Accuracy cannot yet be summarised: 0 comparable case(s); at least 5 are needed (provisional engineering policy).", sample_size: 0 },
        business_impact: { status: "not_evaluable", statement: "Business impact cannot be evaluated from these records." },
        legacy_free_form_outcomes: { recorded: 1, status: "unverified comparison" },
        limitations: [],
      }),
  },
}));
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));

import OutcomesPage from "./page";

describe("Recommendation outcomes page", () => {
  it("never shows a 'share of the expected change that happened' score and says why a figure cannot be compared", async () => {
    render(<OutcomesPage />);
    expect(await screen.findByText(/Accuracy cannot yet be summarised/)).toBeTruthy();
    expect(screen.getByText(/Business impact cannot be evaluated/)).toBeTruthy();
    expect(screen.getByText("Accepted")).toBeTruthy();
    expect(screen.getByText("Not recorded")).toBeTruthy();                    // accepting is not recorded as carrying it out
    expect(screen.getByText(/not on your business's own scale/)).toBeTruthy();
    expect(screen.queryByText(/Share of the expected change/)).toBeNull();
    expect(screen.queryByText("50%")).toBeNull();                              // the legacy score is not displayed
    expect(screen.getByText(/typed in without a period, units or scope/)).toBeTruthy();
  });

  it("lists saved forecasts waiting for results and every comparison with the reason when it was withheld", async () => {
    render(<OutcomesPage />);
    expect(await screen.findByText(/Saved forecasts and figures waiting/)).toBeTruthy();
    expect(screen.getByText("2026-10-21 to 2026-10-27")).toBeTruthy();
    expect(screen.getByText("Period not finished yet")).toBeTruthy();
    expect(screen.getByText("Compared: same period, after the data cutoff")).toBeTruthy();
    expect(screen.getByText("Not compared — not comparable")).toBeTruthy();
    expect(screen.getByText(/does not show that a recommendation helped/)).toBeTruthy();
    expect(screen.queryByText(/success rate|% successful/i)).toBeNull();
  });
});

