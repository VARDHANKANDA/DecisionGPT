import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const getChurn = vi.fn();
vi.mock("@/lib/api", () => ({
  api: {
    getChurn: (...a: unknown[]) => getChurn(...a),
    getCustomerSummary: () => Promise.resolve({ total_customers: 60, new_customers_last_30_days: 5, avg_monetary_value: 400, avg_purchase_frequency: 3.2 }),
    getDataLibrary: () => Promise.resolve([{ type: "customers", rows: 60 }]),
  },
}));
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));

import CustomersPage from "./page";

beforeEach(() => getChurn.mockReset());

describe("Customer churn score wording", () => {
  it("presents a model score with its provenance warnings, not a percentage chance", async () => {
    getChurn.mockResolvedValue({
      model_name: "churn_logistic_regression", model_version: "v1", metrics: {},
      predictions: Array.from({ length: 12 }, (_, i) => ({ customer_id: `c${i}`, external_customer_id: `C${i}`, churn_probability: 0.9 })),
      score_meaning: "A model score, not a verified churn probability.",
      label_provenance: "synthetic: drawn from a known generator",
      warnings: ["This model was trained on synthetic customers. Its recorded metrics describe that data, not your customers."],
    });
    render(<CustomersPage />);
    const button = await screen.findByRole("button", { name: /Find customers who may be at risk/ });
    fireEvent.click(button);
    await waitFor(() => expect(getChurn).toHaveBeenCalled());
    expect(await screen.findByText("What this score is — and is not")).toBeTruthy();
    expect(screen.getByText(/trained on synthetic customers/)).toBeTruthy();
    expect(screen.getAllByText(/score 90 \/ 100/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/about 90%/)).toBeNull();
  });
});
