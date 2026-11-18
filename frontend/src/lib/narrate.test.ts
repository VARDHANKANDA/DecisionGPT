import { describe, expect, it } from "vitest";
import { churnStory, describeChange, forecastStory, revenueHeadline, riskBand } from "@/lib/narrate";

const pt = (i: number, v: number) => ({
  forecast_date: `2026-10-${String(i + 1).padStart(2, "0")}`,
  predicted_value: v,
  lower_bound: 0,
  upper_bound: v * 2,
});

describe("describeChange", () => {
  it("is plain and treats tiny moves as steady", () => {
    expect(describeChange(0.14)).toBe("up 14%");
    expect(describeChange(-0.035)).toBe("down 3.5%");
    expect(describeChange(0.01)).toBe("about the same");
    expect(describeChange(null)).toMatch(/can't be compared/);
  });
});

describe("revenueHeadline", () => {
  it("doesn't invent a comparison when there is no earlier period", () => {
    const t = revenueHeadline({
      current_revenue: 1000,
      previous_revenue: 0,
      change_absolute: 1000,
      change_pct: null,
      current_orders: 3,
      previous_orders: 0,
    });
    expect(t).toMatch(/isn't an earlier period/);
  });
});

describe("forecastStory", () => {
  it("returns null when there is no forecast", () => {
    expect(forecastStory([], [])).toBeNull();
  });
  it("sums the real points and compares with real recent history", () => {
    const points = Array.from({ length: 14 }, (_, i) => pt(i, 10));
    const history = Array.from({ length: 30 }, (_, i) => ({ date: `d${i}`, units_sold: 20 }));
    const s = forecastStory(points, history)!;
    expect(s.totalUnits).toBe(140);
    expect(s.direction).toBe("steady");
    expect(s.why.join(" ")).toMatch(/50% lower than the last 14 days/);
  });
  it("flags a forecast that is far from recent real sales", () => {
    const history = Array.from({ length: 30 }, (_, i) => ({ date: `d${i}`, units_sold: 5 }));
    const huge = forecastStory(Array.from({ length: 14 }, (_, i) => pt(i, 19)), history)!;
    expect(huge.hugeShift && huge.bigShift).toBe(true);
    const mild = forecastStory(Array.from({ length: 14 }, (_, i) => pt(i, 6.9)), history)!;
    expect(mild.bigShift).toBe(true);
    expect(mild.hugeShift).toBe(false);
    const fine = forecastStory(Array.from({ length: 14 }, (_, i) => pt(i, 5.2)), history)!;
    expect(fine.bigShift).toBe(false);
  });
  it("calls a clear climb rising", () => {
    const points = Array.from({ length: 10 }, (_, i) => pt(i, 10 + i * 3));
    expect(forecastStory(points, [])!.direction).toBe("rising");
  });
});

describe("churn", () => {
  const p = (id: string, v: number) => ({ customer_id: id, external_customer_id: id, churn_probability: v });
  it("bands and counts", () => {
    expect(riskBand(0.8)).toBe("higher");
    expect(riskBand(0.5)).toBe("moderate");
    expect(riskBand(0.49)).toBe("lower");
    const s = churnStory([p("a", 0.9), p("b", 0.55), p("c", 0.1)]);
    expect(s.atRisk.map((x) => x.customer_id)).toEqual(["a", "b"]);
    expect(s.counts).toEqual({ higher: 1, moderate: 1, lower: 1 });
    expect(s.headline).toMatch(/2 of your 3 customers/);
  });
  it("says so when nobody is at risk", () => {
    expect(churnStory([p("a", 0.1)]).headline).toMatch(/None of your 1 customers/);
  });
});
