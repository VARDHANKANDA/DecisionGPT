// Deterministic in-memory fakes for the Web Speech API, for tests and local
// development in environments without a microphone or a real recognition
// service. NOT used in production code paths.

export interface MockRecognitionController {
  /** Emit a final transcript as if the user finished speaking. */
  finish: (transcript: string) => void;
  /** Emit an interim (partial) transcript. */
  partial: (transcript: string) => void;
  /** Emit an error with the given SpeechRecognition error code. */
  fail: (code: string) => void;
  /** The most recent recognition instance, or null. */
  current: () => SpeechRecognition | null;
  started: number;
  stopped: number;
}

class MockSpeechRecognition extends EventTarget implements SpeechRecognition {
  lang = "";
  continuous = false;
  interimResults = false;
  maxAlternatives = 1;
  onresult: ((event: SpeechRecognitionEvent) => void) | null = null;
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null = null;
  onstart: ((event: Event) => void) | null = null;
  onend: ((event: Event) => void) | null = null;
  onspeechend: ((event: Event) => void) | null = null;
  onnomatch: ((event: Event) => void) | null = null;

  _ended = false;

  constructor(private readonly ctrl: { started: number; stopped: number; instance: MockSpeechRecognition | null }) {
    super();
  }

  start(): void {
    this.ctrl.started += 1;
    this.ctrl.instance = this;
    this._ended = false;
    this.onstart?.(new Event("start"));
  }

  stop(): void {
    this.ctrl.stopped += 1;
    this._end();
  }

  abort(): void {
    this._end();
  }

  _end(): void {
    if (this._ended) return;
    this._ended = true;
    this.onend?.(new Event("end"));
  }
}

/** Install a mock SpeechRecognition on the given window (defaults to global). */
export function installMockSpeechRecognition(
  win: Window & typeof globalThis = window as Window & typeof globalThis,
): MockRecognitionController {
  const ctrl = { started: 0, stopped: 0, instance: null as MockSpeechRecognition | null };
  const Ctor = function (this: unknown) {
    return new MockSpeechRecognition(ctrl);
  } as unknown as SpeechRecognitionConstructor;
  win.SpeechRecognition = Ctor;
  win.webkitSpeechRecognition = Ctor;

  return {
    started: 0,
    stopped: 0,
    current: () => ctrl.instance,
    finish: (transcript: string) => {
      const rec = ctrl.instance;
      if (!rec) throw new Error("no active mock recognition");
      const event = {
        resultIndex: 0,
        results: {
          length: 1,
          item: (i: number) => (i === 0 ? mkResult(transcript, true) : (undefined as never)),
          0: mkResult(transcript, true),
        },
      } as unknown as SpeechRecognitionEvent;
      rec.onresult?.(event);
      rec._end();
    },
    partial: (transcript: string) => {
      const rec = ctrl.instance;
      if (!rec) throw new Error("no active mock recognition");
      const event = {
        resultIndex: 0,
        results: {
          length: 1,
          item: (i: number) => (i === 0 ? mkResult(transcript, false) : (undefined as never)),
          0: mkResult(transcript, false),
        },
      } as unknown as SpeechRecognitionEvent;
      rec.onresult?.(event);
    },
    fail: (code: string) => {
      const rec = ctrl.instance;
      if (!rec) throw new Error("no active mock recognition");
      rec.onerror?.({ error: code, message: code } as SpeechRecognitionErrorEvent);
      rec._end();
    },
  };
}

function mkResult(transcript: string, isFinal: boolean): SpeechRecognitionResult {
  const alt: SpeechRecognitionAlternative = { transcript, confidence: 0.9 };
  return {
    isFinal,
    length: 1,
    item: () => alt,
    0: alt,
  } as unknown as SpeechRecognitionResult;
}

export function removeMockSpeechRecognition(
  win: Window & typeof globalThis = window as Window & typeof globalThis,
): void {
  delete win.SpeechRecognition;
  delete win.webkitSpeechRecognition;
}

// --- speechSynthesis -------------------------------------------------------

export interface MockSynthController {
  spoken: string[];
  paused: boolean;
  cancelled: number;
  /** Fire onend for the most recent utterance. */
  endLast: () => void;
}

export function installMockSpeechSynthesis(
  win: Window & typeof globalThis = window as Window & typeof globalThis,
): MockSynthController {
  const state: MockSynthController & { _last: SpeechSynthesisUtterance | null } = {
    spoken: [],
    paused: false,
    cancelled: 0,
    _last: null,
    endLast: () => {
      const u = state._last;
      if (u?.onend) u.onend(new Event("end") as unknown as SpeechSynthesisEvent);
    },
  };

  const synth = {
    speak: (u: SpeechSynthesisUtterance) => {
      state.spoken.push(u.text);
      state._last = u;
    },
    cancel: () => {
      state.cancelled += 1;
      state.paused = false;
    },
    pause: () => {
      state.paused = true;
    },
    resume: () => {
      state.paused = false;
    },
    getVoices: () => [] as SpeechSynthesisVoice[],
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as SpeechSynthesis;

  Object.defineProperty(win, "speechSynthesis", { value: synth, configurable: true, writable: true });
  if (typeof win.SpeechSynthesisUtterance !== "function") {
    win.SpeechSynthesisUtterance = class {
      text: string;
      lang = "";
      voice: SpeechSynthesisVoice | null = null;
      onend: ((e: SpeechSynthesisEvent) => void) | null = null;
      onerror: ((e: SpeechSynthesisErrorEvent) => void) | null = null;
      constructor(text: string) {
        this.text = text;
      }
    } as unknown as typeof SpeechSynthesisUtterance;
  }

  return state;
}
