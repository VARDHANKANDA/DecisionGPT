import { describe, expect, it } from "vitest";
import { displayMape } from "./metric-format";

describe("displayMape", () => {
  it("passes a plausible percentage error through", () => {
    expect(displayMape(18.4)).toBe(18.4);
    expect(displayMape(0)).toBe(0);
  });

  it.each([undefined, null, "12", NaN, Infinity, -Infinity, -3, 8.7e8, 1000.01])("never shows %s as a number", (v) => {
    expect(displayMape(v)).toBeNull();
  });
});
