import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import fixtures from "@/components/__fixtures__/evaluation_chat.json";

// The responses below were produced by the real backend (real registered-model manifests, the real stored benchmark files and a real validation
// run on a disposable business), so the UI is tested against the actual response shape and values, not hand-written ones.
const chat = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, chat: (...a: unknown[]) => chat(...a), getDataLibrary: () => Promise.resolve([]) } };
});
vi.mock("@/lib/business-context", () => ({ useBusiness: () => ({ business: { id: "b1", name: "Shop" }, loading: false }) }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams() }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/components/voice/VoiceInput", () => ({ VoiceInput: () => null }));

import ChatPage from "./page";

type Fx = (typeof fixtures)[keyof typeof fixtures];
const fx = fixtures as Record<string, Fx>;

async function ask(response: Fx, question = "Show me all evaluation results.") {
  chat.mockResolvedValue(response);
  render(<ChatPage />);
  const box = await screen.findByRole("textbox");
  fireEvent.change(box, { target: { value: question } });
  fireEvent.click(screen.getByRole("button", { name: "Ask" }));
  return await screen.findByLabelText("DecisionGPT's answer");
}

beforeEach(() => {
  chat.mockReset();
  Element.prototype.scrollIntoView = vi.fn();
});

describe("Evaluation answers in chat", () => {
  it("says the numbers are recorded results and that no AI model was used for them", async () => {
    const card = await ask(fx.all_page1);
    expect(within(card).getByText(/Recorded evaluation results · no AI model used for the numbers/)).toBeTruthy();
    expect(within(card).getByText("Recorded evaluation results")).toBeTruthy();
    expect(card.textContent).toContain("not live accuracy against what actually happened");
    expect(card.textContent).not.toContain("Question understood by the AI model");
  });

  it("leads with the direct answer and shows the grouped results, each kind of evidence under its own heading", async () => {
    const card = await ask(fx.all_page1);
    expect(card.textContent).toContain("Here are all 57 evaluation results");
    expect(within(card).getByRole("region", { name: "Your business: backtest on its own history" })).toBeTruthy();
    expect(within(card).getByRole("region", { name: "Registered models: held-out part of their research dataset" })).toBeTruthy();
    expect(within(card).queryByRole("region", { name: "Public-data benchmark runs (as stored)" })).toBeNull();     // benchmarks are on later pages
    expect(card.textContent).toContain("57 result(s), 447 metric value(s) · page 1 of 11 · business and research results");
  });

  it("shows every metric value on the page with its unit, direction, meaning and the facts it was measured on", async () => {
    const card = await ask(fx.business_only);
    const e = (fx.business_only.details as unknown as { evaluation: { sections: { results: { groups: { cards: { display: string; name: string }[] }[] }[] }[] } }).evaluation;
    const cards = e.sections.flatMap((s) => s.results.flatMap((r) => r.groups.flatMap((g) => g.cards)));
    expect(cards.length).toBeGreaterThan(15);
    for (const c of cards) expect(within(card).getAllByLabelText(new RegExp(`^${c.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}: `)).length).toBeGreaterThan(0);
    expect(card.textContent).toContain("units/day");
    expect(card.textContent).toContain("Lower is better");
    expect(card.textContent).toContain("Horizon:7 days ahead");
    expect(card.textContent).toContain("Backtest periods");
    expect(card.textContent).toContain("Code revision");
    expect(within(card).getAllByLabelText("Evaluated on").length).toBe(3);
  });

  it("never prints NaN, Infinity or a fabricated zero, and states what it could not show", async () => {
    const card = await ask(fx.all_page1);
    expect(card.textContent).not.toMatch(/\bNaN\b|Infinity|undefined units|\bnull\b/);
    expect(card.textContent).toMatch(/Not available|Not applicable|Not evaluated/);
  });

  it("lets the person move through every page, using the prompts the service gave", async () => {
    const card = await ask(fx.all_page1);
    const nav = within(card).getByRole("navigation", { name: "More evaluation results" });
    expect(within(nav).getAllByRole("button").length).toBe(11 + 1);                      // 11 page buttons + "Show the next page"
    expect((within(nav).getByRole("button", { name: "1" }) as HTMLButtonElement).disabled).toBe(true);
    chat.mockResolvedValue(fx.all_last_page);
    fireEvent.click(within(nav).getByRole("button", { name: "Show the next page" }));
    await waitFor(() => expect(chat).toHaveBeenCalledTimes(2));
    expect(chat.mock.calls[1][1]).toBe("Show all evaluation results, page 2");
  });

  it("shows the last page's limitations and no further page button", async () => {
    const card = await ask(fx.all_last_page);
    expect(card.textContent).toContain("page 11 of 11");
    expect(within(card).queryByRole("button", { name: "Show the next page" })).toBeNull();
    expect(within(card).getByRole("region", { name: "Public-data benchmark runs (as stored)" })).toBeTruthy();
  });

  it("explains in a table which metrics are unavailable and why, using the service's own states", async () => {
    const card = await ask(fx.unavailable, "Which metrics are unavailable and why?");
    expect(within(card).getByText("What is not available, and why")).toBeTruthy();
    const table = within(card).getAllByRole("table")[0];
    expect(table.textContent).toContain("Not recorded for this run");
    expect(table.textContent).toContain("Not applicable");
    expect(table.textContent).toContain("point forecasts");
  });

  it("tells 'not applicable', 'not recorded' and 'insufficient data' apart on the cards themselves", async () => {
    const card = await ask(fx.all_last_page);
    const kinds = new Set(Array.from(card.querySelectorAll("[data-kind]")).map((n) => n.getAttribute("data-kind")));
    expect(kinds.has("available")).toBe(true);
    expect(kinds.has("not_applicable")).toBe(true);
    const na = card.querySelector('[data-kind="not_applicable"]') as HTMLElement;
    expect(within(na).getAllByText(/Not applicable/).length).toBeGreaterThan(0);          // the badge and the value both say so, in words
    expect(na.getAttribute("data-status")).not.toBe("available");
  });

  it("lists every defined metric with its unit, direction and meaning when asked what is used", async () => {
    const card = await ask(fx.definitions, "What metrics are used to evaluate the models?");
    const rows = within(card).getAllByRole("row");
    expect(rows.length).toBeGreaterThan(25);                                              // header + the whole registry
    expect(card.textContent).toContain("Mean absolute error (MAE)");
    expect(card.textContent).toContain("Closer to zero is better");
    expect(card.textContent).toContain("Positive = over-forecast");
  });

  it("tells a business owner that model and benchmark results are for administrators, and shows none", async () => {
    const card = await ask(fx.restricted, "Show the historical benchmark results");
    expect(card.textContent).toContain("administrators in the Research Console");
    expect(card.textContent).not.toMatch(/xgboost|random_forest|logistic/i);
    expect(card.textContent).toContain("your business only");
  });

  it("keeps a plain-text version available for copying and for assistive technology", async () => {
    const card = await ask(fx.business_only);
    const details = within(card).getByText("Plain-text version of this answer").closest("details")!;
    expect(details.textContent).toContain("Evaluation summary");
    expect(details.textContent).toContain("Limitations and interpretation");
  });

  it("shows a failed evaluation as a plain error with a retry, not as an answer", async () => {
    chat.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<ChatPage />);
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "Show me all evaluation results." } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/couldn't reach DecisionGPT/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("shows an evaluation that could not run as insufficient evidence, with the reason", async () => {
    const card = await ask({ ...fx.business_only, sufficient_evidence: false, answer: "Insufficient data: the validation could not be run. No sales history on file yet.",
      details: { evaluation: { ...(fx.business_only.details as unknown as { evaluation: object }).evaluation, sections: [], headline: "Insufficient data: the validation could not be run.", messages: ["No sales history on file yet."] } } } as unknown as Fx);
    expect(card.textContent).toContain("Insufficient data: the validation could not be run.");
    expect(card.textContent).toContain("No sales history on file yet.");
  });
});
