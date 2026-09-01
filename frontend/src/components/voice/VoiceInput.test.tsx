import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceInput } from "@/components/voice/VoiceInput";
import { VoiceLanguageProvider } from "@/lib/voice/language-context";
import {
  installMockSpeechRecognition,
  removeMockSpeechRecognition,
  type MockRecognitionController,
} from "@/lib/voice/mock-speech";

let mock: MockRecognitionController;

beforeEach(() => {
  window.localStorage.clear();
  mock = installMockSpeechRecognition();
});

afterEach(() => {
  removeMockSpeechRecognition();
});

describe("VoiceInput (supported browser)", () => {
  it("renders a mic button with an accessible name and a visible text label", () => {
    render(<VoiceInput label="your goal" onTranscript={() => {}} locale="en-IN" />);
    const btn = screen.getByRole("button", { name: /start voice input for your goal/i });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveTextContent("Speak"); // icon is not the only label
  });

  it("starts recognition on click and shows the listening state", async () => {
    const user = userEvent.setup();
    render(<VoiceInput onTranscript={() => {}} locale="en-IN" />);
    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    expect(mock.current()).not.toBeNull();
    expect(screen.getByText(/listening/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /stop voice input/i })).toHaveAttribute("aria-pressed", "true");
  });

  it("returns the transcript for review, allows editing, and hands the edited text to onTranscript", async () => {
    const user = userEvent.setup();
    const onTranscript = vi.fn();
    render(<VoiceInput onTranscript={onTranscript} locale="en-IN" />);

    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    mock.finish("increase my revenue next month");

    const review = await screen.findByLabelText(/you said/i);
    expect(review).toHaveValue("increase my revenue next month");

    // edit before accepting
    await user.clear(review);
    await user.type(review, "increase my revenue by 10 percent");
    await user.click(screen.getByRole("button", { name: /use this text/i }));

    expect(onTranscript).toHaveBeenCalledTimes(1);
    expect(onTranscript).toHaveBeenCalledWith("increase my revenue by 10 percent");
    // review panel closes; nothing was auto-submitted
    expect(screen.queryByLabelText(/you said/i)).not.toBeInTheDocument();
  });

  it("does not call onTranscript until the user explicitly accepts (no auto decision)", async () => {
    const user = userEvent.setup();
    const onTranscript = vi.fn();
    render(<VoiceInput onTranscript={onTranscript} locale="en-IN" />);
    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    mock.finish("delete everything");
    await screen.findByLabelText(/you said/i);
    expect(onTranscript).not.toHaveBeenCalled();
  });

  it("Stop ends recognition and returns to idle", async () => {
    const user = userEvent.setup();
    render(<VoiceInput onTranscript={() => {}} locale="en-IN" />);
    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    await user.click(screen.getByRole("button", { name: /stop voice input/i }));
    await waitFor(() => expect(screen.getByRole("button", { name: /start voice input/i })).toBeInTheDocument());
  });

  it("shows a plain-language fallback when permission is denied", async () => {
    const user = userEvent.setup();
    const onError = vi.fn();
    render(<VoiceInput onTranscript={() => {}} onError={onError} locale="en-IN" />);
    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    mock.fail("not-allowed");

    expect(await screen.findByText(/microphone access is blocked\. you can type instead\./i)).toBeInTheDocument();
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "permission-denied" }));
    // the typed interface is still there — the mic button did not disappear
    expect(screen.getByRole("button", { name: /voice input/i })).toBeInTheDocument();
  });

  it("reports 'no speech detected' when recognition ends without a result", async () => {
    const user = userEvent.setup();
    render(<VoiceInput onTranscript={() => {}} locale="en-IN" />);
    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    mock.current()!.stop();
    expect(await screen.findByText(/didn.t catch anything/i)).toBeInTheDocument();
  });

  it("is keyboard operable (Tab to focus, Enter to activate)", async () => {
    const user = userEvent.setup();
    render(<VoiceInput onTranscript={() => {}} locale="en-IN" showLanguagePicker={false} />);
    await user.tab();
    const btn = screen.getByRole("button", { name: /start voice input/i });
    expect(btn).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(mock.current()).not.toBeNull();
  });

  it("passes the selected language locale to recognition", async () => {
    const user = userEvent.setup();
    render(
      <VoiceLanguageProvider>
        <VoiceInput onTranscript={() => {}} />
      </VoiceLanguageProvider>,
    );
    await user.click(screen.getByRole("button", { name: /हिन्दी/i }));
    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    expect(mock.current()!.lang).toBe("hi-IN");
  });

  it("times out and recovers without throwing", async () => {
    vi.useFakeTimers();
    try {
      const onError = vi.fn();
      render(<VoiceInput onTranscript={() => {}} onError={onError} locale="en-IN" />);
      // click via fireEvent-free path: use the DOM directly under fake timers
      screen.getByRole("button", { name: /start voice input/i }).click();
      vi.advanceTimersByTime(15001);
      expect(onError).toHaveBeenCalledWith(expect.objectContaining({ kind: "timeout" }));
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("VoiceInput (unsupported browser)", () => {
  it("shows a type-instead fallback and no mic button", () => {
    removeMockSpeechRecognition();
    render(<VoiceInput onTranscript={() => {}} locale="en-IN" />);
    expect(screen.getByText(/voice input isn.t supported in this browser\. you can type instead\./i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /voice input/i })).not.toBeInTheDocument();
  });
});
