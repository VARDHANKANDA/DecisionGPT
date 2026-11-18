import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const record = vi.fn();
vi.mock("@/lib/api", () => ({
  ApiError: class extends Error {
    status: number;
    code: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.code = code;
    }
  },
  api: { recordDecisionResponse: (...a: unknown[]) => record(...a) },
}));

import { ApiError } from "@/lib/api";
import { DecisionResponsePanel } from "./DecisionResponsePanel";

const fresh = { recorded: false, response: "pending", action_status: "unknown" };

function setup(current = fresh, history?: never[]) {
  const onSaved = vi.fn();
  render(<DecisionResponsePanel businessId="b1" decisionId="d1" current={current} history={history} onSaved={onSaved} />);
  return onSaved;
}

beforeEach(() => {
  record.mockReset();
});

describe("Decision response panel", () => {
  it("is a labelled group of keyboard-reachable radio buttons and a submit button", () => {
    setup();
    expect(screen.getByRole("group", { name: /What did you decide/ })).toBeTruthy();
    expect(screen.getAllByRole("radio").length).toBe(4);
    expect(screen.getByRole("button", { name: /Save my response/ }).getAttribute("type")).toBe("submit");
  });

  it("will not save until something is chosen, and says what is missing", () => {
    setup();
    expect((screen.getByRole("button", { name: /Save my response/ }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: /Modified/ }));
    expect(screen.getByText("Describe what you changed.")).toBeTruthy();
  });

  it("accepting does not record the action as carried out", async () => {
    record.mockResolvedValue({ recorded: true });
    const onSaved = setup();
    fireEvent.click(screen.getByRole("radio", { name: /Accepted/ }));
    expect(screen.getByText(/Accepting a recommendation is not the same as doing it/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Save my response/ }));
    await waitFor(() => expect(record).toHaveBeenCalledTimes(1));
    const body = record.mock.calls[0][2];
    expect(body.response).toBe("accepted");
    expect(body.action_status).toBe("unknown");          // not 'executed', and not claimed as 'not carried out' either
    expect(body.action_start).toBeUndefined();
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(await screen.findByText(/Saved\. Your earlier answers are kept/)).toBeTruthy();
  });

  it("recording that it was carried out needs a date and sends it", async () => {
    record.mockResolvedValue({ recorded: true });
    setup();
    fireEvent.click(screen.getByRole("radio", { name: /Accepted/ }));
    fireEvent.click(screen.getByRole("radio", { name: /^Carried out$/ }));
    expect(screen.getByText("Enter the date you started.")).toBeTruthy();
    expect((screen.getByRole("button", { name: /Save my response/ }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/Date you started/), { target: { value: "2026-10-10" } });
    fireEvent.click(screen.getByRole("button", { name: /Save my response/ }));
    await waitFor(() => expect(record).toHaveBeenCalled());
    expect(record.mock.calls[0][2]).toMatchObject({ response: "accepted", action_status: "executed", action_start: "2026-10-10" });
  });

  it("rejecting or deferring never offers or sends an executed action", async () => {
    record.mockResolvedValue({ recorded: true });
    setup();
    fireEvent.click(screen.getByRole("radio", { name: /Rejected/ }));
    expect(screen.queryByRole("radio", { name: /^Carried out$/ })).toBeNull();
    expect(screen.getByText(/recorded as not carried out/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Save my response/ }));
    await waitFor(() => expect(record).toHaveBeenCalled());
    expect(record.mock.calls[0][2]).toMatchObject({ response: "rejected", action_status: "not_executed" });
    expect(record.mock.calls[0][2].action_start).toBeUndefined();
  });

  it("a modified decision records what was changed and is never executed-as-original", async () => {
    record.mockResolvedValue({ recorded: true });
    setup();
    fireEvent.click(screen.getByRole("radio", { name: /Modified/ }));
    fireEvent.change(screen.getByLabelText(/What did you change/), { target: { value: "Raised price 3% instead of 5%" } });
    fireEvent.click(screen.getByRole("radio", { name: /^Carried out$/ }));
    fireEvent.change(screen.getByLabelText(/Date you started/), { target: { value: "2026-10-12" } });
    fireEvent.click(screen.getByRole("button", { name: /Save my response/ }));
    await waitFor(() => expect(record).toHaveBeenCalled());
    const b = record.mock.calls[0][2];
    expect(b.response).toBe("modified");
    expect(b.modified_action).toEqual({ description: "Raised price 3% instead of 5%" });
    expect(b.action_taken.description).toBe("Raised price 3% instead of 5%");
    expect(b.action_taken.basis).toMatch(/the modified action, not the original/);
  });

  it("a double click sends one request", async () => {
    let release: (v: unknown) => void = () => undefined;
    record.mockImplementation(() => new Promise((r) => (release = r)));
    const onSaved = setup();
    fireEvent.click(screen.getByRole("radio", { name: /Deferred/ }));
    const button = screen.getByRole("button", { name: /Save my response/ });
    fireEvent.click(button);
    fireEvent.click(button);
    fireEvent.click(button);
    expect(record).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: /Saving/ }).getAttribute("aria-busy")).toBe("true");
    release({ recorded: true });
    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1));
    expect(record).toHaveBeenCalledTimes(1);
  });

  it("shows a calm error with nothing changed, and treats 'already recorded' as saved", async () => {
    record.mockRejectedValueOnce(new ApiError(409, "CONFLICT", "Another update to this recommendation was saved at the same moment.", {}));
    setup();
    fireEvent.click(screen.getByRole("radio", { name: /Rejected/ }));
    fireEvent.click(screen.getByRole("button", { name: /Save my response/ }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/same moment/);
    record.mockRejectedValueOnce(new ApiError(422, "VALIDATION_FAILED", "This response is already recorded; nothing changed.", {}));
    fireEvent.click(screen.getByRole("button", { name: /Save my response/ }));
    expect(await screen.findByText(/already saved; nothing changed/)).toBeTruthy();
  });

  it("shows a recorded response, offers a correction and lists the history", () => {
    setup(
      { recorded: true, response: "accepted", action_status: "executed", action_start: "2026-10-10", note: "did it" } as never,
      [
        { seq: 1, response: "accepted", action_status: "unknown", recorded: true },
        { seq: 2, response: "accepted", action_status: "executed", action_start: "2026-10-10", recorded: true },
      ] as never,
    );
    expect(screen.getByText(/Your response:/).parentElement?.textContent).toMatch(/Accepted — Carried out/);
    expect(screen.getByRole("button", { name: /Correct or update my response/ })).toBeTruthy();
    expect(screen.getByText(/History of this response \(2\)/)).toBeTruthy();
  });

  it("does not show a start date for a response that was not carried out", () => {
    setup({ recorded: true, response: "rejected", action_status: "not_executed", action_start: "2026-10-10" } as never);
    const t = screen.getByText(/Your response:/).parentElement?.textContent ?? "";
    expect(t).toMatch(/Rejected — Not carried out/);
    expect(t).not.toMatch(/started/);
  });
});

