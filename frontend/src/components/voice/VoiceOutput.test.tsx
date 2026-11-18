import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceOutput } from "@/components/voice/VoiceOutput";
import { installMockSpeechSynthesis, type MockSynthController } from "@/lib/voice/mock-speech";

let synth: MockSynthController;

beforeEach(() => {
  synth = installMockSpeechSynthesis();
});

afterEach(() => {
  // @ts-expect-error test teardown
  delete window.speechSynthesis;
});

describe("VoiceOutput", () => {
  it("renders an opt-in Listen button and does not auto-speak", () => {
    render(<VoiceOutput text="Recommended strategy: Marketing +20%." locale="en-IN" />);
    expect(screen.getByRole("button", { name: /listen to the recommendation/i })).toBeInTheDocument();
    expect(synth.spoken).toHaveLength(0);
  });

  it("speaks the provided text only after the user presses Listen", async () => {
    const user = userEvent.setup();
    render(<VoiceOutput text="Risk level: LOW." locale="en-IN" />);
    await user.click(screen.getByRole("button", { name: /listen/i }));
    expect(synth.spoken).toEqual(["Risk level: LOW."]);
  });

  it("sanitises ids / tokens before speaking", async () => {
    const user = userEvent.setup();
    render(
      <VoiceOutput
        text="Decision 3fa85f64-5717-4562-b3fc-2c963f66afa6 ready. Bearer abc.def-999"
        locale="en-IN"
      />,
    );
    await user.click(screen.getByRole("button", { name: /listen/i }));
    expect(synth.spoken[0]).not.toMatch(/3fa85f64|Bearer abc/);
    expect(synth.spoken[0]).toMatch(/Decision.*ready/);
  });

  it("can be paused, resumed and stopped", async () => {
    const user = userEvent.setup();
    render(<VoiceOutput text="A longer recommendation to read aloud." locale="en-IN" />);
    await user.click(screen.getByRole("button", { name: /listen/i }));

    await user.click(screen.getByRole("button", { name: /pause reading/i }));
    expect(synth.paused).toBe(true);

    await user.click(screen.getByRole("button", { name: /resume reading/i }));
    expect(synth.paused).toBe(false);

    await user.click(screen.getByRole("button", { name: /stop reading/i }));
    expect(synth.cancelled).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /listen/i })).toBeInTheDocument();
  });

  it("is keyboard operable", async () => {
    const user = userEvent.setup();
    render(<VoiceOutput text="Read me." locale="en-IN" />);
    await user.tab();
    expect(screen.getByRole("button", { name: /listen/i })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(synth.spoken).toEqual(["Read me."]);
  });

  it("shows a fallback when speech synthesis is unavailable", () => {
    // @ts-expect-error remove for this case
    delete window.speechSynthesis;
    render(<VoiceOutput text="anything" locale="en-IN" />);
    expect(screen.getByText(/text-to-speech isn.t available/i)).toBeInTheDocument();
  });
});
