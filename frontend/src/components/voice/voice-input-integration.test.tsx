import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceInput } from "@/components/voice/VoiceInput";
import {
  installMockSpeechRecognition,
  removeMockSpeechRecognition,
  type MockRecognitionController,
} from "@/lib/voice/mock-speech";

// Mirrors the shape of goals/page.tsx: VoiceInput fills the SAME textarea a
// keyboard user types into, and the SAME submit handler runs. Voice is only an
// alternative input modality — there is no voice-specific submission path.
function GoalFormHarness({ onSubmit }: { onSubmit: (text: string) => void }) {
  const [text, setText] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(text);
      }}
    >
      <VoiceInput label="your goal" onTranscript={(t) => setText(t)} locale="en-IN" showLanguagePicker={false} />
      <textarea aria-label="Goal, in plain language" value={text} onChange={(e) => setText(e.target.value)} />
      <button type="submit">Set goal</button>
    </form>
  );
}

let mock: MockRecognitionController;

beforeEach(() => {
  mock = installMockSpeechRecognition();
});
afterEach(() => {
  removeMockSpeechRecognition();
});

describe("voice → existing text submission path", () => {
  it("voice transcript lands in the existing field and submits through the same handler as typed text", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<GoalFormHarness onSubmit={onSubmit} />);

    // speak
    await user.click(screen.getByRole("button", { name: /start voice input/i }));
    mock.finish("increase revenue by 20 percent next month");
    await user.click(await screen.findByRole("button", { name: /use this text/i }));

    // the transcript is now the textarea's value — identical to typing it
    const field = screen.getByLabelText(/goal, in plain language/i) as HTMLTextAreaElement;
    expect(field.value).toBe("increase revenue by 20 percent next month");

    // the normal submit path runs unchanged
    await user.click(screen.getByRole("button", { name: /set goal/i }));
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith("increase revenue by 20 percent next month");
  });

  it("typed text still works with the voice component present", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<GoalFormHarness onSubmit={onSubmit} />);
    await user.type(screen.getByLabelText(/goal, in plain language/i), "reduce churn by 10 percent");
    await user.click(screen.getByRole("button", { name: /set goal/i }));
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith("reduce churn by 10 percent");
  });
});
