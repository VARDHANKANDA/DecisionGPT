import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const record = vi.fn();
vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    status = 404;
  }
  return {
  ApiError,
  api: {
    listDecisions: () =>
      Promise.resolve([
        { id: "d1", goal_id: "g1", created_at: "2026-10-10T10:00:00Z", risk_level: "medium", reasoning: "Raise marketing spend.",
          expected_outcome_json: { expected_revenue: 120000, baseline_revenue: 100000 } },
        { id: "d2", goal_id: "g1", created_at: "2026-10-11T10:00:00Z", risk_level: "low", reasoning: "Hold steady.",
          expected_outcome_json: { expected_revenue: 100000, baseline_revenue: 100000 } },
      ]),
    getOutcome: (_b: string, id: string) =>
      id === "d1"
        ? Promise.resolve({ id: "o1", decision_id: "d1", actual_outcome_json: { revenue: 110000 }, goal_achieved: true, goal_achievement_score: 0.5, recorded_at: "" })
        : Promise.reject(new ApiError("none")),
    listDecisionTracking: () =>
      Promise.resolve({
        decisions: [
          { decision_id: "d1", current: { recorded: true, seq: 2, response: "accepted", action_status: "executed", action_start: "2026-10-12" } },
          { decision_id: "d2", current: { recorded: false, seq: 0, response: "pending", action_status: "unknown" } },
        ],
      }),
    trackingDecision: () =>
      Promise.resolve({
        current: { recorded: true, seq: 2, response: "accepted", action_status: "executed" },
        history: [
          { seq: 1, response: "accepted", action_status: "unknown", recorded: true },
          { seq: 2, response: "accepted", action_status: "executed", action_start: "2026-10-12", recorded: true },
        ],
        expectations: [],
      }),
    recordDecisionResponse: (...a: unknown[]) => record(...a),
  },
  };
});
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));

import HistoryPage from "./page";

describe("Decision History", () => {
  it("shows what was decided and whether it was carried out, without a 'share of the expected change' score", async () => {
    render(<HistoryPage />);
    await waitFor(() => expect(screen.getAllByText(/Your response:/).length).toBe(2));
    const texts = screen.getAllByText(/Your response:/).map((n) => n.parentElement?.textContent ?? "");
    expect(texts.some((t) => /Accepted — Carried out \(started 2026-10-12\)/.test(t))).toBe(true);
    expect(texts.some((t) => /No response recorded yet/.test(t))).toBe(true);
    expect(screen.queryByText(/of the expected change happened/)).toBeNull();
    expect(await screen.findByText(/not used to judge the recommendation/)).toBeTruthy();
    expect(screen.getAllByText(/has not been checked against your own sales/).length).toBe(2);
  });

  it("records a response for a pending recommendation through the tracking API", async () => {
    record.mockResolvedValue({ recorded: true });
    render(<HistoryPage />);
    // the recommendation with no response yet opens its form; the recorded one offers a correction instead
    expect(await screen.findByRole("button", { name: /Correct or update my response/ })).toBeTruthy();
    fireEvent.click(await screen.findByRole("radio", { name: /Deferred/ }));
    fireEvent.click(screen.getByRole("button", { name: /Save my response/ }));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    expect(record.mock.calls[0][0]).toBe("b1");
    expect(record.mock.calls[0][1]).toBe("d2");
    expect(record.mock.calls[0][2]).toMatchObject({ response: "deferred", action_status: "not_executed" });
  });
});
