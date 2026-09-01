import { beforeEach, describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VoiceLanguagePicker } from "@/components/voice/VoiceLanguagePicker";
import { VoiceLanguageProvider, useVoiceLanguage } from "@/lib/voice/language-context";

function LocaleProbe() {
  const { lang, locale } = useVoiceLanguage();
  return <output data-testid="probe">{`${lang}:${locale}`}</output>;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("VoiceLanguagePicker", () => {
  it("defaults to English and updates the shared locale on selection", async () => {
    const user = userEvent.setup();
    render(
      <VoiceLanguageProvider>
        <VoiceLanguagePicker />
        <LocaleProbe />
      </VoiceLanguageProvider>,
    );

    expect(screen.getByTestId("probe")).toHaveTextContent("en:en-IN");
    expect(screen.getByRole("button", { name: /English/i })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: /தமிழ்/ }));
    expect(screen.getByTestId("probe")).toHaveTextContent("ta:ta-IN");
    expect(screen.getByRole("button", { name: /தமிழ்/ })).toHaveAttribute("aria-pressed", "true");

    await user.click(screen.getByRole("button", { name: /हिन्दी/ }));
    expect(screen.getByTestId("probe")).toHaveTextContent("hi:hi-IN");
  });

  it("persists the choice to localStorage", async () => {
    const user = userEvent.setup();
    render(
      <VoiceLanguageProvider>
        <VoiceLanguagePicker />
      </VoiceLanguageProvider>,
    );
    await user.click(screen.getByRole("button", { name: /हिन्दी/ }));
    expect(window.localStorage.getItem("decisiongpt.voice_lang")).toBe("hi");
  });

  it("has a group label and per-option accessible names (not colour-only)", () => {
    render(
      <VoiceLanguageProvider>
        <VoiceLanguagePicker />
      </VoiceLanguageProvider>,
    );
    expect(screen.getByRole("group", { name: /voice language/i })).toBeInTheDocument();
    // English name is exposed to assistive tech even though the visible label is native script
    expect(screen.getByRole("button", { name: /Hindi/i })).toBeInTheDocument();
  });
});

describe("useVoiceLanguage without a provider", () => {
  it("falls back to the English default", () => {
    render(<LocaleProbe />);
    expect(screen.getByTestId("probe")).toHaveTextContent("en:en-IN");
  });
});
