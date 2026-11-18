import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const api = { listModels: vi.fn(), syncModels: vi.fn(), validateModel: vi.fn(), promoteModel: vi.fn(), rollbackModel: vi.fn(), archiveModel: vi.fn() };
vi.mock("@/lib/research-api", () => ({
  researchApi: new Proxy({}, { get: (_t, k: string) => (...a: unknown[]) => (api as Record<string, (...x: unknown[]) => unknown>)[k](...a) }),
  ResearchApiError: class extends Error {},
}));

import ModelRegistryPage from "./page";

const row = (id: string, version: string, status: string) => ({
  id, model_name: "sales_forecast_xgboost", model_type: "forecasting_xgboost", version, dataset_version: "platform-forecasting-v1", feature_version: "forecasting_v1",
  parameters_json: {}, metrics_json: { mae: 15.1, rmse: 21.8, mape: 10.3 }, model_path: "x", status, created_at: "2026-10-15T00:00:00Z", task: "forecasting", source: "cli", promoted_at: null,
});

beforeEach(() => Object.values(api).forEach((f) => f.mockReset()));

describe("Model registry lifecycle controls", () => {
  it("offers only the action the model's state allows and never a direct promote of an unvalidated model", async () => {
    api.listModels.mockResolvedValue([row("a", "v1", "active"), row("b", "v2", "candidate"), row("c", "v3", "validated"), row("d", "v4", "rejected")]);
    render(<ModelRegistryPage />);
    await screen.findByText("v2");
    expect(screen.getAllByRole("button", { name: "Run checks" }).length).toBe(2);   // candidate + rejected
    expect(screen.getAllByRole("button", { name: /Promote…/ }).length).toBe(1);     // only the validated one
    expect(screen.getAllByRole("button", { name: /Roll back…/ }).length).toBe(1);   // only the active one
  });

  it("shows every check with its blocking/warning status after validation", async () => {
    api.listModels.mockResolvedValue([row("b", "v2", "candidate")]);
    api.validateModel.mockResolvedValue({
      model_id: "b", model_name: "sales_forecast_xgboost", version: "v2", status: "rejected", passed: false, warnings: ["trained_on_real_business_data"],
      checks: [
        { name: "beats_naive_baseline_on_validation", passed: false, blocking: true, detail: "val_mae 25 vs naive 20" },
        { name: "trained_on_real_business_data", passed: false, blocking: false, detail: "trained on synthetic platform data only" },
      ],
    });
    render(<ModelRegistryPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Run checks" }));
    expect(await screen.findByText(/failed a blocking check \(rejected\)/)).toBeTruthy();
    expect(screen.getByText(/val_mae 25 vs naive 20/)).toBeTruthy();
    expect(screen.getByText(/warning, does not block/)).toBeTruthy();
  });

  it("never presents a bootstrap-activated or synthetic-trained model as validated or business-eligible", async () => {
    api.listModels.mockResolvedValue([{ ...row("a", "v1", "active"), validation_status: "not_validated_bootstrap",
      applicability: { eligible_for_production_use: false, provenance: "synthetic_platform", source: "inferred", reasons: ["trained on synthetic platform data only"] } }]);
    render(<ModelRegistryPage />);
    expect(await screen.findByText(/not validated \(first version\)/)).toBeTruthy();
    expect(screen.getByText(/not eligible for business use/)).toBeTruthy();
    expect(screen.getByText(/inferred, not recorded/)).toBeTruthy();
    expect(screen.queryByText("validated", { selector: "span" })).toBeNull();
  });

  it("does not promote without a reason", async () => {
    api.listModels.mockResolvedValue([row("c", "v3", "validated")]);
    vi.spyOn(window, "prompt").mockReturnValue("   ");
    render(<ModelRegistryPage />);
    fireEvent.click(await screen.findByRole("button", { name: /Promote…/ }));
    await waitFor(() => expect(window.prompt).toHaveBeenCalled());
    expect(api.promoteModel).not.toHaveBeenCalled();
  });
});
