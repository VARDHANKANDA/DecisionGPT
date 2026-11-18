import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const chat = vi.fn();
vi.mock("@/lib/api", () => ({ api: { chat: (...a: unknown[]) => chat(...a), getDataLibrary: () => Promise.resolve([]) } }));
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/components/voice/VoiceInput", () => ({ VoiceInput: () => null }));

import ChatPage from "./page";

const base = {
  answer: "Your total sales for February 2025 were ₹14,59,083.",
  intent: "analytics_query",
  sources: ["Your sales records for February 2025 (200 records)"],
  sufficient_evidence: true,
  answer_type: "known",
  details: {},
};

async function ask(response: Record<string, unknown>) {
  chat.mockResolvedValue({ ...base, ...response });
  render(<ChatPage />);
  const box = await screen.findByRole("textbox");
  fireEvent.change(box, { target: { value: "What were my total sales in February 2025?" } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  await waitFor(() => expect(screen.getByLabelText("DecisionGPT's answer")).toBeTruthy());
}

beforeEach(() => {
  chat.mockReset();
  Element.prototype.scrollIntoView = vi.fn(); // jsdom has no layout
});

describe("Chat answer provenance", () => {
  it("says the AI only understood the question when the AI path answered", async () => {
    await ask({ path: "llm_analytics" });
    expect(screen.getByText(/Question understood by the AI model \(OpenAI\) · numbers from your data/)).toBeTruthy();
    expect(screen.queryByText("Standard assistant (rule-based)")).toBeNull();
  });

  it("labels the standard assistant and shows the fallback notice when the AI path did not answer", async () => {
    await ask({ path: "legacy_router", notice: "Advanced question understanding is temporarily unavailable, so this answer comes from the standard assistant." });
    expect(screen.getByText("Standard assistant (rule-based)")).toBeTruthy();
    expect(screen.getByText(/temporarily unavailable, so this answer comes from the standard assistant/)).toBeTruthy();
    expect(screen.queryByText(/AI model \(OpenAI\)/)).toBeNull();
  });

  it("claims neither when the response carries no path", async () => {
    await ask({});
    expect(screen.queryByText(/AI model \(OpenAI\)/)).toBeNull();
    expect(screen.queryByText("Standard assistant (rule-based)")).toBeNull();
  });
});
