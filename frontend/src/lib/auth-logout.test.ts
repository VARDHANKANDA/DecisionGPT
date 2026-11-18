import { describe, expect, it, vi, beforeEach } from "vitest";

describe("api.logout", () => {
  beforeEach(() => {
    window.localStorage.setItem("decisiongpt.token", "token-for-test");
  });

  it("POSTs to the server logout route with the current token, and treats 204 as success", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("@/lib/api");
    await expect(api.logout()).resolves.toBeUndefined();
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toMatch(/\/auth\/logout$/);
    expect(init.method).toBe("POST");
    expect(init.headers.Authorization).toBe("Bearer token-for-test");
    vi.unstubAllGlobals();
  });
});
