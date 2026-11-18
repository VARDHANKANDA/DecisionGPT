import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api";
import { explainIssue, friendlyError, timeAgo, tooManyAttempts } from "@/lib/friendly";

describe("friendlyError", () => {
  it("never shows a status code or error code to the person", () => {
    const f = friendlyError(new ApiError(500, "INTERNAL_SERVER_ERROR", "boom", {}));
    expect(f.message).not.toMatch(/500|INTERNAL/);
    expect(f.message).toMatch(/safe/i);
    expect(f.technical).toContain("500");
  });

  it("keeps plain-language messages the server wrote for expected problems", () => {
    const f = friendlyError(new ApiError(422, "VALIDATION_FAILED", "2 row(s) are missing “Quantity”.", {}));
    expect(f.message).toBe("2 row(s) are missing “Quantity”.");
  });

  it("explains a network failure kindly", () => {
    expect(friendlyError(new TypeError("Failed to fetch")).message).toMatch(/internet connection/i);
  });
});

describe("explainIssue", () => {
  it("rewrites technical data-quality messages", () => {
    expect(explainIssue("Required field 'sale_date' is missing after mapping.")).toBe(
      "We couldn't find a column for “Date”.",
    );
    expect(explainIssue("3 duplicate rows detected.")).toBe("3 rows appear more than once.");
    expect(explainIssue("1 rows have an unparseable date in 'sale_date'.")).toContain("a date we couldn't read");
  });
});

describe("timeAgo", () => {
  it("is human", () => {
    expect(timeAgo(new Date().toISOString())).toBe("Today");
    expect(timeAgo(new Date(Date.now() - 86_400_000 * 1.2).toISOString())).toBe("Yesterday");
    expect(timeAgo(null)).toBe("—");
  });
});


describe("tooManyAttempts", () => {
  it("turns the server's retry information into minutes, in plain words", () => {
    expect(tooManyAttempts(new ApiError(429, "RATE_LIMITED", "x", { retry_after_seconds: 600 }))).toContain("about 10 minutes");
    expect(tooManyAttempts(new ApiError(429, "RATE_LIMITED", "x", { retry_after_seconds: 20 }))).toContain("a minute");
  });
  it("still reads sensibly when the server sent no usable retry time, and never mentions status codes", () => {
    const msg = tooManyAttempts(new ApiError(429, "RATE_LIMITED", "x", {}));
    expect(msg).toContain("wait a few minutes");
    expect(msg).not.toMatch(/429|rate/i);
  });
});
