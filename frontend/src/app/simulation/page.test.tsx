import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const simulate = vi.fn();
vi.mock("@/lib/api", () => ({
  api: { simulate: (...a: unknown[]) => simulate(...a) },
  ApiError: class extends Error {},
}));
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));

import SimulationPage from "./page";

const base = {
  baseline_units_sold: 140, baseline_revenue: 140000, expected_profit: null, baseline_profit: null, profit_note: null, customer_impact: null,
  inventory_constrained: false, risk_level: "MODERATE", risk_score: 0.3, model_name: "sales_forecast_xgboost", model_version: "v1",
  assumptions: ["The registered model was not trained for this business's daily totals."],
};

async function run(output: Record<string, unknown>) {
  simulate.mockResolvedValue({ id: "s1", business_id: "b1", goal_id: null, input_state: {}, actions: [{ type: "price_change", value: 10 }], output: { ...base, ...output } });
  render(<SimulationPage />);
  fireEvent.click(await screen.findByRole("button", { name: /See what may happen/ }));
  await waitFor(() => expect(simulate).toHaveBeenCalled());
}

beforeEach(() => simulate.mockReset());

describe("What-If price effect", () => {
  it("shows no figures for a withheld price effect and says what would be needed", async () => {
    await run({
      expected_units_sold: null, expected_revenue: null, revenue_lower_bound: null, revenue_upper_bound: null,
      price_response: { status: "not_identified", identified: false, reliable: false, withheld: true, days: 90, distinct_prices: 1, price_cv: 0,
        needed: ["at least 5 different average prices (you have 1)", "average-price variation of at least 5% (you have 0.0%)"], message: "x" },
    });
    expect(await screen.findByText("Price effect unavailable")).toBeTruthy();
    expect(screen.getByText(/at least 5 different average prices/)).toBeTruthy();
    expect(screen.queryByText("Sales with your change")).toBeNull();
    expect(screen.queryByText("Units with your change")).toBeNull();
    expect(screen.queryByText(/expected to be about/)).toBeNull();
  });

  it("explains that a missing checked model, not the history, is the reason when the history does vary", async () => {
    await run({
      expected_units_sold: null, expected_revenue: null, revenue_lower_bound: null, revenue_upper_bound: null,
      price_response: { status: "not_identified", identified: false, reliable: false, withheld: true, reason: "model", days: 120, distinct_prices: 40,
        price_cv: 0.12, needed: ["a forecasting model trained on your own business and checked against your own price changes"], message: "x" },
    });
    expect(await screen.findByText("Price effect unavailable")).toBeTruthy();
    expect(screen.getByText(/no forecasting model that has been checked against your own price changes/)).toBeTruthy();
    expect(screen.queryByText(/does not contain enough price variation/)).toBeNull();
    expect(screen.queryByText("Sales with your change")).toBeNull();
  });

  it("shows the effect, labelled an association, when the data can support one", async () => {
    await run({
      expected_units_sold: 150, expected_revenue: 150000, revenue_lower_bound: 120000, revenue_upper_bound: 180000,
      price_response: { status: "association_only", identified: true, reliable: false, withheld: false, days: 90, distinct_prices: 40, price_cv: 0.12,
        needed: [], message: "The price effect below is an association learned from your history, not a measured causal effect." },
    });
    expect(await screen.findByText("Sales with your change")).toBeTruthy();
    expect(screen.getByText(/not a measured causal effect/)).toBeTruthy();
    expect(screen.queryByText("Price effect unavailable")).toBeNull();
  });
});
