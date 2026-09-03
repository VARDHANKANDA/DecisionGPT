import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

let pathname = "/dashboard";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

const logout = vi.fn();
let authState: { user: unknown; isAdmin: boolean } = { user: { email: "u@x.com", role: "sme" }, isAdmin: false };
vi.mock("@/lib/auth-context", () => ({ useAuth: () => ({ ...authState, logout }) }));
vi.mock("@/lib/business-context", () => ({
  useBusiness: () => ({ business: { name: "Acme", industry: "Retail", business_type: "D2C" }, clearBusiness: vi.fn() }),
}));

import { AppShell } from "@/components/AppShell";

beforeEach(() => {
  logout.mockClear();
  pathname = "/dashboard";
  authState = { user: { email: "u@x.com", role: "sme" }, isAdmin: false };
});

describe("AppShell", () => {
  it("renders a Sign out control for an authenticated user and it calls logout", async () => {
    const user = userEvent.setup();
    render(
      <AppShell>
        <p>dashboard body</p>
      </AppShell>,
    );
    const outs = screen.getAllByRole("button", { name: /sign out/i });
    expect(outs.length).toBeGreaterThan(0);
    await user.click(outs[0]);
    expect(logout).toHaveBeenCalledTimes(1);
  });

  it("shows the Research console link only for admins", () => {
    const { rerender } = render(
      <AppShell>
        <p>body</p>
      </AppShell>,
    );
    expect(screen.queryByRole("link", { name: /research console/i })).not.toBeInTheDocument();

    authState = { user: { email: "a@x.com", role: "admin" }, isAdmin: true };
    rerender(
      <AppShell>
        <p>body</p>
      </AppShell>,
    );
    expect(screen.getByRole("link", { name: /research console/i })).toBeInTheDocument();
  });

  it("renders children bare (no shell) for a signed-out visitor", () => {
    authState = { user: null, isAdmin: false };
    render(
      <AppShell>
        <p>public body</p>
      </AppShell>,
    );
    expect(screen.getByText("public body")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /sign out/i })).not.toBeInTheDocument();
  });
});
