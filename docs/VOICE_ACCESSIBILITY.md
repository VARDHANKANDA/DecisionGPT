# Voice Accessibility Layer

## Purpose

An optional voice **input** and voice **output** modality for the DecisionGPT
SME app, so a user can speak a request instead of typing and can hear an
important recommendation read aloud.

Voice is an **alternative input/output modality only**. It is **not** a new
feature of the decision engine, **not** a new experiment, and **not** research
evidence. Every voice interaction resolves to the *same text* and the *same API
calls* a keyboard user would produce.

```
typed text ─┐
            ├─▶ existing goal parsing ─▶ existing DecisionGPT pipeline (R0 / D0)
voice text ─┘
```

## Scope of change

| Layer | Change |
|---|---|
| **Backend** | **NONE.** No endpoint, schema, migration, service, model, dataset, experiment, or config was touched. `risk_model = None`, `risk_penalty_lambda = 1.0`, `R0 / D0` unchanged. `DecisionOutcome` count remains 0. |
| **Frontend** | New reusable components + a small language-preference context, wired into the existing goal / chat / decision screens. |

## Architecture

All speech processing is **client-side, browser-native**. No audio and no
transcript is sent to the DecisionGPT backend by this feature; the transcript
enters the app exactly where typed text already does.

| Concern | Implementation |
|---|---|
| Speech-to-text | Web Speech API `SpeechRecognition` / `webkitSpeechRecognition` (browser-native). |
| Text-to-speech | Web Speech API `speechSynthesis` (browser-native). |
| Language preference | `VoiceLanguageProvider` (`src/lib/voice/language-context.tsx`) — a `localStorage`-backed React context (`decisiongpt.voice_lang`), default `en`. Controls the recognition/synthesis **locale only**; it does not translate the interface (the app has no i18n system). |
| Reusable UI | `VoiceInput`, `VoiceOutput`, `VoiceLanguagePicker` in `src/components/voice/`. |
| Framework-free logic | `src/lib/voice/{locales,support}.ts` + the `use-speech-recognition` / `use-speech-synthesis` hooks. Pure helpers are unit-tested without a DOM renderer. |

### Files

Created:
- `frontend/src/lib/voice/locales.ts` — language ↔ BCP-47 locale map (`en-IN`, `hi-IN`, `ta-IN`).
- `frontend/src/lib/voice/support.ts` — support detection, error normalization, voice selection, `sanitizeForSpeech`.
- `frontend/src/lib/voice/speech-recognition.d.ts` — minimal ambient types for the non-standard `SpeechRecognition` API.
- `frontend/src/lib/voice/language-context.tsx` — `VoiceLanguageProvider` / `useVoiceLanguage`.
- `frontend/src/lib/voice/use-speech-recognition.ts` — SSR-safe recognition hook (lifecycle, timeout, teardown).
- `frontend/src/lib/voice/use-speech-synthesis.ts` — SSR-safe synthesis hook (play / pause / resume / stop, sanitisation).
- `frontend/src/lib/voice/mock-speech.ts` — deterministic fakes for tests / mic-less environments (not used in production paths).
- `frontend/src/components/voice/VoiceInput.tsx` — push-to-talk + transcript review.
- `frontend/src/components/voice/VoiceOutput.tsx` — opt-in "Listen" control.
- `frontend/src/components/voice/VoiceLanguagePicker.tsx` — English / हिन्दी / தமிழ் selector.
- Tests: `frontend/src/lib/voice/*.test.ts`, `frontend/src/components/voice/*.test.tsx`.
- `frontend/vitest.config.ts`, `frontend/vitest.setup.ts`.

Modified:
- `frontend/src/app/layout.tsx` — wraps the tree in `VoiceLanguageProvider`.
- `frontend/src/app/goals/page.tsx` — `VoiceInput` above the goal textarea.
- `frontend/src/app/chat/page.tsx` — `VoiceInput` above the question box.
- `frontend/src/app/decision/page.tsx` — `VoiceOutput` on the recommendation and the AI Business Review.
- `frontend/package.json` / `frontend/package-lock.json` — dev-only test tooling (`vitest`, `@testing-library/*`, `jsdom`, `@vitejs/plugin-react`) + a `test` script. No runtime dependency added.

## Supported languages

| Language | Code | Locale | Notes |
|---|---|---|---|
| English | `en` | `en-IN` | Best-supported across browsers. |
| Hindi | `hi` | `hi-IN` | Recognition/synthesis quality and voice availability vary by OS/browser. |
| Tamil | `ta` | `ta-IN` | As above; some desktop browsers lack a `ta-IN` synthesis voice and fall back to the browser default or stay silent. |

**Recognition and synthesis quality are not equivalent across these
languages.** They depend entirely on the user's browser and operating system.
The UI surfaces the active recognition language and degrades to typing when a
language is unsupported.

## Browser support

| Capability | Supported | Unsupported |
|---|---|---|
| `SpeechRecognition` (voice input) | Chrome, Edge, Chrome-on-Android, Safari (recent) | Firefox; older Safari; hardened/embedded webviews. |
| `speechSynthesis` (voice output) | Broadly supported | Rare; some Linux browsers without a TTS engine. |

On Chrome/Edge/Chrome-Android, `SpeechRecognition` sends the captured audio to
the **browser vendor's** cloud speech service for transcription. This is a
property of the browser, not of DecisionGPT. **We do not claim audio never
leaves the device.** Safari performs on-device recognition for some locales.

### Tested environments

| Environment | What was tested | How |
|---|---|---|
| CI / jsdom (Vitest) | Component behaviour, states, permission/unsupported fallbacks, transcript review + edit, language→locale wiring, keyboard operation, TTS start/pause/resume/stop, sanitisation. | Deterministic `mock-speech.ts` fakes. **No real microphone or speech service was exercised.** |
| `next build` / `tsc` / ESLint | Type safety, production build, lint. | Standard toolchain. |
| Real browsers | Not automated here. | Manual verification is required on Chrome desktop + Chrome Android for `en-IN` at minimum before relying on it in production. |

## Permission behaviour

| State | UI |
|---|---|
| Not yet requested | Mic button reads **"🎤 Speak"**. The browser prompts on first press. |
| Granted | Press → **"⏹ Stop / Listening…"**, live partial transcript, then a review box. |
| Denied (`not-allowed` / `service-not-allowed`) | **"Microphone access is blocked. You can type instead."** The text field stays fully usable. |
| No microphone (`audio-capture`) | **"No microphone was found. You can type instead."** |
| Browser unsupported | **"Voice input isn't supported in this browser. You can type instead."** (mic button not rendered) |

The app never crashes when the microphone or the API is unavailable — voice
always degrades to the existing text interface.

## Confirmation before analysis (safety)

Speech recognition can mis-transcribe. The flow is deliberately:

```
press mic ─▶ speak ─▶ transcript shown in an editable box ─▶ user presses "Use this text"
          ─▶ text lands in the normal input ─▶ user presses the normal Set goal / Send button
```

There is **no path from speech to an automatic or irreversible decision**.
`VoiceInput` calls its `onTranscript` callback only after the user explicitly
accepts the (optionally edited) text, and the page's existing submit button is
still required to run anything.

## Privacy considerations

- The microphone starts **only** after an explicit button press, and a visible
  "Listening…" state is shown while it is active.
- App code never accesses `MediaRecorder` / raw audio, never stores audio,
  never uploads audio, and never persists a recording anywhere — no database
  row, no `DecisionOutcome`, no experiment artifact.
- The transcript is treated as ordinary user text input. It is subject to the
  same handling as anything typed into the same field.
- With `SpeechRecognition` on Chromium browsers, the **browser** transmits
  audio to its vendor's speech service. Users who need on-device-only
  processing should use a browser that does that (e.g. Safari for supported
  locales) or type instead. This is documented, not hidden.
- Voice output (`speechSynthesis`) reads only text already displayed on screen,
  after passing it through `sanitizeForSpeech`, which strips UUIDs, bearer
  tokens, JWT-shaped blobs, long hex ids and key-shaped strings before speaking
  (defence in depth — the app does not render such values in these strings).

## Security

Voice adds **no** new request path. A voice request is byte-for-byte a typed
request from the same authenticated user:

- The transcript is placed into the same field and submitted with the same
  `api.*` call, the same bearer token (`localStorage` `decisiongpt.token`), and
  the same `{business_id}` path parameter.
- All server-side checks are unchanged: `require_user`, `require_business_access`
  (business ownership), capability gating, and research-console gating all run
  exactly as before. `scripts/audit_e2e.py` still passes, including
  **cross-business access blocked (403)**.
- A voice transcript cannot reach another business's data, cannot bypass
  authentication, and cannot call an endpoint a typed request could not.

## Accessibility behaviour

- Semantic `<button>` elements with explicit `aria-label`s; the mic button also
  carries `aria-pressed` for its on/off state.
- Every control has a **visible text label** next to the icon; the icon is
  `aria-hidden`. State is never signalled by colour alone (text + `aria-live`
  status line).
- Recording / reading state is announced via `aria-live="polite"` regions.
- Keyboard operable: Tab to focus, Enter/Space to activate; visible
  `focus-visible` outline on every control.
- Touch targets: the primary mic button is ≥ 44×44 px; secondary controls
  ≥ 40 px, laid out with wrap for narrow screens (mobile-first).
- The language picker is a labelled `fieldset`/`group`; each option exposes its
  English name to assistive tech even though the visible label is in native
  script.
- Nothing is voice-only: the typed interface is always present and is the
  fallback for every failure mode.

## Fallback behaviour

Every failure (unsupported browser, denied permission, missing mic, network
error, no speech, timeout, recognition error, user cancellation, interruption)
resolves to a short, non-technical message and the unchanged text input. Raw
browser exception strings are never shown — `normalizeRecognitionError` maps
them to plain language.

## Testing

Frontend (`cd frontend && npm run test`) — Vitest + Testing Library, jsdom, with
a deterministic Web Speech mock:

- `VoiceInput`: renders; accessible name; starts recognition on click; shows the
  listening state; returns the transcript for review; user can edit the
  transcript; edited text is handed to the existing submission path; **no**
  `onTranscript` before explicit accept; Stop ends recognition; permission
  denial shows the fallback; unsupported browser shows the fallback; keyboard
  operable; selected language sets the recognition locale (`hi-IN`); timeout
  recovers without throwing.
- `VoiceOutput`: renders an opt-in Listen button and does not auto-speak; speaks
  only after the button press; sanitises ids/tokens; pause / resume / stop;
  keyboard operable; fallback when synthesis is unavailable.
- `VoiceLanguagePicker`: defaults to English; selection updates the shared
  locale (`en-IN` / `hi-IN` / `ta-IN`); choice persists to `localStorage`;
  group + per-option accessible names.
- Integration harness: a transcript accepted in `VoiceInput` lands in the same
  textarea and submits through the same handler as typed text; typed text still
  works with the voice component present.
- `support.ts` / `locales.ts`: locale resolution, support detection, SSR
  safety, error normalization (never leaks a raw exception), voice selection,
  `sanitizeForSpeech`.

Result: **46 passed / 0 failed** (`vitest run`).

Backend: **Backend voice changes = NONE.** No backend test was added or changed.
`scripts/audit_e2e.py` passes unchanged.

## Known limitations

- Automated tests use mocks; real speech accuracy has not been measured and is
  out of scope. Manual browser verification is required before production use.
- `hi-IN` / `ta-IN` recognition and synthesis depend on the user's platform;
  some browsers have no Tamil TTS voice.
- Firefox has no `SpeechRecognition`; those users get the typed interface only.
- Recognition on Chromium browsers is cloud-backed (vendor service), so voice
  input needs a network connection there.
- The language selector affects speech only — the interface text stays English
  (the app has no translation system; adding one is out of scope for this
  accessibility task).
- Voice output reads the recommendation summary and the AI Business Review; it
  is not wired to every screen by design (task requirement: user-controlled,
  not page-wide).

## Research note (how the paper should describe this)

Voice access is an accessibility / input-modality feature and **was not
evaluated as a scientific treatment** in any of the 16 frozen experiments. It
does not appear in the experiment manifest, changes no metric, and produces no
`DecisionOutcome`.

The paper **must not** claim:
- "Voice access improves SME decision quality."
- "Voice access benefits rural / low-literacy users." (no user study exists)

The paper **may** state only, if it mentions the feature at all:

> "The system also provides an optional voice interaction modality (speech input
> that feeds the existing text pipeline, and opt-in text-to-speech for
> recommendations) intended to reduce typing effort. Its usability and
> speech-recognition performance were not evaluated in the present study."

Frozen scientific status is unchanged:
`REAL SME EVIDENCE = PENDING` · `REAL LLM VALIDATION = BLOCKED` ·
`TABLE 2 = NOT READY` · `CAUSALLY_VALIDATED = 0` ·
`R3 = EXPERIMENTAL / NOT PROMOTED` · production `R0 / D0`.
