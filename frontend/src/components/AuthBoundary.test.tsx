import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

// --- mock next/navigation ------------------------------------------------
const replace = vi.fn();
let pathname = "/dashboard";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => pathname,
}));

// --- mock the auth context --------------------------------------------------
let authState: { user: unknown; isAdmin: boolean; loading: boolean } = {
  user: null,
  isAdmin: false,
  loading: false,
};
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => authState,
}));

import { AuthBoundary } from "@/components/AuthBoundary";

beforeEach(() => {
  replace.mockClear();
  pathname = "/dashboard";
  authState = { user: null, isAdmin: false, loading: false };
});
afterEach(() => vi.clearAllMocks());

describe("AuthBoundary", () => {
  it("redirects a signed-out visitor away from a protected route and hides its content", async () => {
    render(
      <AuthBoundary>
        <div>secret dashboard</div>
      </AuthBoundary>,
    );
    expect(screen.queryByText("secret dashboard")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith("/login?next=%2Fdashboard"),
    );
  });

  it("renders protected content once a user is present", () => {
    authState = { user: { id: "u1", role: "sme" }, isAdmin: false, loading: false };
    render(
      <AuthBoundary>
        <div>secret dashboard</div>
      </AuthBoundary>,
    );
    expect(screen.getByText("secret dashboard")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("shows a loading state (not the page) while the session check is pending", () => {
    authState = { user: null, isAdmin: false, loading: true };
    render(
      <AuthBoundary>
        <div>secret dashboard</div>
      </AuthBoundary>,
    );
    expect(screen.queryByText("secret dashboard")).not.toBeInTheDocument();
    expect(screen.getByText(/loading your workspace/i)).toBeInTheDocument();
  });

  it("sends a signed-in visitor off /login to their workspace", async () => {
    pathname = "/login";
    authState = { user: { id: "u1", role: "sme" }, isAdmin: false, loading: false };
    render(
      <AuthBoundary>
        <div>login form</div>
      </AuthBoundary>,
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
  });

  it("sends a signed-in admin off /login to the research console", async () => {
    pathname = "/login";
    authState = { user: { id: "a1", role: "admin" }, isAdmin: true, loading: false };
    render(
      <AuthBoundary>
        <div>login form</div>
      </AuthBoundary>,
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/research"));
  });

  it("does not guard public routes", () => {
    pathname = "/login";
    authState = { user: null, isAdmin: false, loading: false };
    render(
      <AuthBoundary>
        <div>login form</div>
      </AuthBoundary>,
    );
    expect(screen.getByText("login form")).toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });
});
