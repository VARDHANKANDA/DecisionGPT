import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { CausalResult, DebateResult, ReportPayload } from "@/lib/platform-api";
import { formatKpi } from "@/lib/platform-api";

vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: null, loading: false }) }));

import { CausalResultView, CLASS_LABEL } from "@/components/causal-view";
import { DebateView } from "@/components/debate-view";
import { ReportView, Workspace } from "@/components/platform-ui";

describe("formatKpi", () => {
  it("formats rupees, counts and percentage points as the server reports them", () => {
    expect(formatKpi(626228.8, "inr")).toBe("₹6,26,229");
    expect(formatKpi(181, "count")).toBe("181");
    expect(formatKpi(140.04, "percent")).toBe("140.0%"); // already percentage points — never multiplied again
    expect(formatKpi(null, "inr")).toBe("Not available");
  });
});

describe("Causal AI labels", () => {
  const base: CausalResult = { id: "1", classification: "exploratory_association", headline: "Exploratory association only.", method_version: "causal-v1", generated_on: "2026-10-09", question: "Q?" };

  it("never presents an association as a causal estimate", () => {
    render(<CausalResultView r={{ ...base, estimate: { coefficient: 0.5, ci95: [0.1, 0.9], p_value: 0.01, unit: "₹ per day" } }} />);
    expect(screen.getByText(/exploratory association — not causal/i)).toBeInTheDocument();
    expect(screen.queryByText(/causal estimate under stated assumptions/i)).not.toBeInTheDocument();
  });

  it("shows a refusal reason and no number when data is insufficient", () => {
    render(<CausalResultView r={{ ...base, classification: "not_enough_data", headline: "Not enough data.", reason: "No marketing spend is recorded." }} />);
    expect(screen.getByText("Not enough data")).toBeInTheDocument();
    expect(screen.getByText("No marketing spend is recorded.")).toBeInTheDocument();
    expect(screen.queryByText(/The estimate/)).not.toBeInTheDocument();
  });

  it("covers every classification the server can return", () => {
    expect(Object.keys(CLASS_LABEL).sort()).toEqual(["assumptions_not_satisfied", "causal_estimate", "exploratory_association", "failed", "not_configured", "not_enough_data"]);
  });

  it("lists assumptions with their honest status", () => {
    render(<CausalResultView r={{ ...base, classification: "causal_estimate", assumptions: [{ assumption: "No other change", status: "unverified — only you can confirm this" }] }} />);
    expect(screen.getByText(/unverified — only you can confirm this/)).toBeInTheDocument();
  });
});

describe("Debate view", () => {
  it("tells the owner the AI-model mode is unavailable instead of showing a debate", () => {
    const r: DebateResult = { status: "ai_model_unavailable", mode: "ai_model", message: "The AI-model debate is not available: not written reasoning. Nothing was fabricated." };
    render(<DebateView r={r} />);
    expect(screen.getAllByText(/AI-model debate is not available/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Specialist analyses/)).not.toBeInTheDocument();
  });

  it("renders the seven stages in order for a rule-based run", () => {
    const brief = {
      question: "Q", topic: "pricing", mode: "rule_based", headline: "Hold for now.", recommended_option: null, key_facts: [], disagreements: [], settled_by_calculation: [],
      missing_information: [], unresolved_uncertainty: [], next_steps: ["Review the evidence."], automatic_actions_taken: false,
    };
    const r: DebateResult = {
      status: "completed", mode: "rule_based", label: "Rule-based specialist review (no AI model was used)",
      stages: {
        question: { text: "Should I raise prices?", topic: "pricing", topic_note: "Topic is detected from keywords." },
        shared_evidence: { facts: [{ id: "F1", text: "Sales were ₹10.", value: 10, source: "KPI" }], missing: [], period: { start: "a", end: "b", days: 30, anchor: "today" } },
        specialist_analyses: { business_analyst: { agent: "business_analyst", name: "Business Analyst", role: "r", claims: [{ id: "BA1", agent: "business_analyst", text: "Sales rose.", evidence: ["F1"], type: "observation" }], missing_information: [] } },
        challenges: [],
        evidence_review: { claims: [{ claim_id: "BA1", agent: "business_analyst", status: "supported", evidence_found: ["F1"], challenges: [] }], missing_information: [], assumptions: [] },
        synthesis: { options: [], ranked_option_ids: [], insufficient_evidence: false, insufficient_reason: null, unresolved_disagreements: [], note: "n" },
        decision_brief: brief,
      },
    };
    render(<DebateView r={r} />);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent ?? "");
    const order = ["1 · The question", "2 · Shared evidence", "3 · Specialist analyses", "4 · Challenges", "5 · Evidence review", "6 · Synthesis", "7 · Decision brief"];
    const positions = order.map((o) => headings.findIndex((h) => h.startsWith(o)));
    expect(positions.every((p) => p >= 0)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
    expect(screen.getByText(/nothing was changed automatically/i)).toBeInTheDocument();
  });
});

describe("ReportView", () => {
  it("renders a stored report as saved, with assumptions and limitations", () => {
    const payload: ReportPayload = {
      report_type: "performance", title: "Business Performance Report", period: { start: "2026-09-09", end: "2026-10-09", days: 30, anchor: "today" }, created_on: "2026-10-09",
      scope: { business: "Acme", business_id: "b", dataset: {}, demo_data: true }, summary: "Sales were ₹10.",
      sections: [{ kind: "notice", tone: "warning", text: "The newest sale is old." }, { kind: "table", title: "KPIs", columns: ["KPI", "Value"], rows: [["Sales", "₹10"]] }],
      assumptions: ["Period is 30 days."], limitations: ["Descriptive only."],
    };
    render(<ReportView payload={payload} />);
    expect(screen.getByText("Business Performance Report")).toBeInTheDocument();
    expect(screen.getByText(/example data/)).toBeInTheDocument();
    expect(screen.getByText("The newest sale is old.")).toBeInTheDocument();
    expect(screen.getByText("Descriptive only.")).toBeInTheDocument();
  });
});

describe("Workspace", () => {
  it("asks for business set-up instead of rendering page content when there is no business", () => {
    render(<Workspace title="KPI Monitoring">{() => <p>should not render</p>}</Workspace>);
    expect(screen.getByRole("link", { name: /set up my business/i })).toBeInTheDocument();
    expect(screen.queryByText("should not render")).not.toBeInTheDocument();
  });
});
