import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const getForecast = vi.fn();
const getForecastReadiness = vi.fn();
const saveSnapshot = vi.fn();
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status: number;
    code: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.code = code;
    }
  },
  api: {
    saveForecastSnapshot: (...a: unknown[]) => saveSnapshot(...a),
    getForecast: (...a: unknown[]) => getForecast(...a),
    getForecastReadiness: (...a: unknown[]) => getForecastReadiness(...a),
    getUnitsHistory: () => Promise.resolve(Array.from({ length: 30 }, (_, i) => ({ date: `2026-09-${String(i + 1).padStart(2, "0")}`, units_sold: 10 }))),
    getDataLibrary: () => Promise.resolve([{ type: "sales", rows: 100 }]),
  },
}));
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("recharts", () => {
  const Stub = ({ children }: { children?: React.ReactNode }) => <div>{children}</div>;
  return { Area: Stub, CartesianGrid: Stub, ComposedChart: Stub, Legend: Stub, Line: Stub, ResponsiveContainer: Stub, Tooltip: Stub, XAxis: Stub, YAxis: Stub };
});

import { ApiError } from "@/lib/api";
import ForecastPage from "./page";

const points = Array.from({ length: 14 }, (_, i) => ({ forecast_date: `2026-10-${String(i + 7).padStart(2, "0")}`, predicted_value: 10, lower_bound: 6, upper_bound: 14 }));

async function run(extra: Record<string, unknown>) {
  getForecast.mockResolvedValue({ model_name: "sales_forecast_xgboost", model_version: "v1", metrics: {}, points, ...extra });
  render(<ForecastPage />);
  fireEvent.click(await screen.findByRole("button", { name: /Get my forecast/ }));
  await waitFor(() => expect(getForecast).toHaveBeenCalled());
}

beforeEach(() => {
  saveSnapshot.mockReset();
  getForecast.mockReset();
  getForecastReadiness.mockReset();
  getForecastReadiness.mockResolvedValue({ ready_for_forecast: true, ready_for_training: false, blockers: [], issues: [], example_data: null });
});

describe("Forecast page limits", () => {
  it("shows the limits the service reported and says the band is not calibrated when it is not", async () => {
    await run({ warnings: ["Your latest recorded sales are from 2026-08-01 (75 days ago). The forecast continues from that point, not from today."],
                interval_reliable: false });
    expect(await screen.findByText("Limits of this forecast")).toBeTruthy();
    expect(screen.getByText(/75 days ago/)).toBeTruthy();
    expect(screen.getByText(/could not be confirmed against your own past weeks/)).toBeTruthy();
  });

  it("describes the band as measured when it was back-tested, and shows no limits box without warnings", async () => {
    await run({ warnings: [], interval_reliable: true });
    await screen.findByText(/measured from how this model's earlier forecasts compared/);
    expect(screen.queryByText("Limits of this forecast")).toBeNull();
  });

  it("lists the data issues the readiness report found, in plain language, before the forecast is run", async () => {
    getForecastReadiness.mockResolvedValue({
      ready_for_forecast: true, ready_for_training: false, blockers: [],
      issues: [{ kind: "non_positive_price", rows: 3, severity: "error", detail: "Rows with a zero or negative unit price." }],
      example_data: "Some rows in this business are DecisionGPT example data, not records of a real business.",
    });
    render(<ForecastPage />);
    expect(await screen.findByText("Checks on your sales data")).toBeTruthy();
    expect(screen.getByText(/Rows with a zero or negative unit price\. \(3 rows\)/)).toBeTruthy();
    expect(screen.getByText(/example data, not records of a real business/)).toBeTruthy();
  });

  it("states the date the forecast is based on", async () => {
    await run({ warnings: [], interval_reliable: true, forecast_basis: "business_specific_baseline", data_as_of: "2026-10-06" });
    expect(await screen.findByText(/Based on sales recorded up to 6 Oct 2026/)).toBeTruthy();
  });

  const FP = "a".repeat(64);
  const provenance = { fingerprint: FP, data_cutoff: "2026-10-06", forecast_start: "2026-10-07", forecast_end: "2026-10-20" };

  it("saves exactly the forecast on screen by sending its fingerprint and horizon", async () => {
    saveSnapshot.mockResolvedValue({ id: "s1", already_saved: false, verified_against_shown: true, metric: "units_sold", unit: "units",
      window_start: "2026-10-07", window_end: "2026-10-20", data_cutoff: "2026-10-06", horizon_days: 14, created_at: "" });
    await run({ warnings: [], interval_reliable: true, ...provenance });
    fireEvent.click(await screen.findByRole("button", { name: /Save this forecast/ }));
    await waitFor(() => expect(saveSnapshot).toHaveBeenCalledTimes(1));
    expect(saveSnapshot.mock.calls[0][0]).toBe("b1");
    expect(saveSnapshot.mock.calls[0][1]).toEqual({ horizon_days: 14, fingerprint: FP });
    expect(await screen.findByText(/It covers 2026-10-07 to 2026-10-20, based on sales up to 2026-10-06/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Save this forecast/ })).toBeNull();
  });

  it("does not save twice on a double click", async () => {
    let release: (v: unknown) => void = () => undefined;
    saveSnapshot.mockImplementation(() => new Promise((r) => (release = r)));
    await run({ warnings: [], interval_reliable: true, ...provenance });
    const button = await screen.findByRole("button", { name: /Save this forecast/ });
    fireEvent.click(button);
    fireEvent.click(button);
    expect(saveSnapshot).toHaveBeenCalledTimes(1);
    release({ id: "s1", already_saved: true, window_start: "a", window_end: "b", data_cutoff: "c" });
    expect(await screen.findByText(/This exact forecast was already saved/)).toBeTruthy();
  });

  it("explains that a forecast which changed since it was shown was not saved", async () => {
    saveSnapshot.mockRejectedValue(new ApiError(409, "CONFLICT", "The forecast has changed since it was shown. Nothing was saved.", {}));
    await run({ warnings: [], interval_reliable: true, ...provenance });
    fireEvent.click(await screen.findByRole("button", { name: /Save this forecast/ }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/changed since it was shown/);
    expect(alert.textContent).toMatch(/Press “Get my forecast” again/);
  });

  it("will not offer to save a forecast whose data date or identity is unknown", async () => {
    await run({ warnings: [], interval_reliable: true });          // no fingerprint, no cutoff
    expect(await screen.findByText(/cannot be saved for later checking/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Save this forecast/ })).toBeNull();
    expect(saveSnapshot).not.toHaveBeenCalled();
  });
});

