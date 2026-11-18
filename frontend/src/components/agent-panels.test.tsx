import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const api = vi.hoisted(() => ({ getMarketingChannels: vi.fn(), getKpis: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api,
  ApiError: class ApiError extends Error {
    status = 0;
  },
}));
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Acme" } }) }));

import { MarketingAdvisorPanels } from "@/components/agent-panels";

const kpis = { revenue: 0, orders: 0, customers: 0, average_order_value: null, profit: null, marketing_spend: 1000, marketing_roi: null, conversion_rate: null, notes: [] };

beforeEach(() => {
  api.getMarketingChannels.mockReset();
  api.getKpis.mockReset();
});

describe("Marketing Advisor", () => {
  it("compares channels using only recorded values and says what it cannot show", async () => {
    api.getKpis.mockResolvedValue({ ...kpis, marketing_roi: 1.4 });
    api.getMarketingChannels.mockResolvedValue([
      { channel: "Alpha", spend: 1000, attributed_revenue: 3000, roi: 2, campaigns: 2 },
      { channel: "Beta", spend: 500, attributed_revenue: 600, roi: 0.2, campaigns: 1 },
    ]);
    render(<MarketingAdvisorPanels />);
    expect(await screen.findByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText(/Alpha has the highest recorded return \(200%\); Beta has the lowest \(20%\)/)).toBeInTheDocument();
    expect(screen.getByText(/does not show that spending more on a channel would give the same return/)).toBeInTheDocument();
    expect(screen.queryByText(/optimi[sz]/i)).not.toBeInTheDocument();
  });

  it("shows an honest empty state, with no invented channels, when there is no marketing data", async () => {
    api.getKpis.mockResolvedValue(kpis);
    api.getMarketingChannels.mockResolvedValue([]);
    render(<MarketingAdvisorPanels />);
    expect(await screen.findByText(/No marketing data has been added/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("does not compute a return when results are not recorded", async () => {
    api.getKpis.mockResolvedValue(kpis);
    api.getMarketingChannels.mockResolvedValue([{ channel: "Alpha", spend: 1000, attributed_revenue: null, roi: null, campaigns: 1 }]);
    render(<MarketingAdvisorPanels />);
    expect(await screen.findByText("Alpha")).toBeInTheDocument();
    expect(screen.getAllByText("Not recorded").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
    expect(screen.getByText(/isn.t enough recorded result data/)).toBeInTheDocument();
  });
});
