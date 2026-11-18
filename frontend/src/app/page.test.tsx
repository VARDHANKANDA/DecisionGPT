import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const auth = { user: null as unknown, isAdmin: false, loading: false };
const replace = vi.fn();
vi.mock("@/lib/auth-context", () => ({ useAuth: () => auth }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

import Home from "./page";

describe("Redesigned Enterprise Landing Page", () => {
  it("renders the primary headline, supporting text, and core sections in order", () => {
    render(<Home />);

    // Hero headline and supporting copy
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toBe("Turn Business Data Into Better Decisions.");
    expect(
      screen.getByText(/DecisionGPT brings business analytics, forecasting, multi-agent intelligence/i)
    ).toBeTruthy();

    // Key Section Headings
    expect(screen.getByRole("heading", { name: "The Critical Challenges in Business Decision-Making" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "One Unified System for Business Decision Support" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Collaborative Intelligence Across Specialized Business Agents" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Verifiable Business Analytics and Multi-Horizon Forecasting" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "From Data to Decisions" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Business Use Cases" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Engineered for Rigor, Transparency, and Executive Trust" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Frequently Asked Questions" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Bring Clarity to Your Next Business Decision." })).toBeTruthy();
  });

  it("provides functional navigation and CTA buttons without broken links", () => {
    render(<Home />);

    // Primary CTA buttons for registration / get started
    const getStartedLinks = screen.getAllByRole("link", { name: "Get Started" });
    expect(getStartedLinks.length).toBeGreaterThanOrEqual(1);
    expect(getStartedLinks[0].getAttribute("href")).toBe("/login?mode=register");

    // Sign in links
    const signInLinks = screen.getAllByRole("link", { name: "Sign In" });
    expect(signInLinks.length).toBeGreaterThanOrEqual(1);
    expect(signInLinks[0].getAttribute("href")).toBe("/login");

    // Explore the Platform anchor
    const exploreLink = screen.getByRole("link", { name: "Explore the Platform" });
    expect(exploreLink.getAttribute("href")).toBe("#platform");
  });

  it("prominently presents all five specialized agents in the multi-agent architecture", () => {
    render(<Home />);
    expect(screen.getAllByText("Business Analyst").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Financial Advisor").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Marketing Advisor").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Risk Manager").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Strategy Optimiser").length).toBeGreaterThanOrEqual(1);
  });

  it("maintains research integrity and makes no unsubstantiated marketing claims", () => {
    const { container } = render(<Home />);
    const text = container.textContent ?? "";

    // No fake startup claims
    expect(text).not.toMatch(/trusted by \d+|customers love|\d+\+ (businesses|customers)|100% accurate/i);

    // AI boundaries and illustrative disclaimers are explicitly articulated
    expect(text).toMatch(/The external AI model never calculates numbers/i);
    expect(text).toMatch(/business_id/i);
    expect(text).toMatch(/makes no promise of specific financial returns/i);
  });

  it("redirects an authenticated visitor to their respective workspace", () => {
    auth.user = { id: "user-123" };
    auth.isAdmin = true;
    const { container } = render(<Home />);
    expect(container.textContent).toBe("");
    expect(replace).toHaveBeenCalledWith("/research");

    auth.isAdmin = false;
    render(<Home />);
    expect(replace).toHaveBeenCalledWith("/dashboard");

    auth.user = null;
    auth.isAdmin = false;
  });
});