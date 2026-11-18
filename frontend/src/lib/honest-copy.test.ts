import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The everyday (non-admin) screens must never promise something the product can't do.
 * This scans their source text for phrases that would imply an unsupported capability.
 */
const src = path.resolve(__dirname, "..");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) return name === "research" || name === "voice" ? [] : files(p);
    return /\.(tsx|ts)$/.test(name) && !/\.test\./.test(name) ? [p] : [];
  });
}

const USER_FILES = [...files(path.join(src, "app")), ...files(path.join(src, "components")), path.join(src, "lib/features.ts"), path.join(src, "lib/questions.ts"), path.join(src, "lib/narrate.ts")].filter(
  (f) => !/research/.test(f),
);

const UNSUPPORTED: [RegExp, string][] = [
  [/choose (a |your |the )?dataset/i, "there is no dataset picker"],
  [/select (a |your |the )?dataset/i, "there is no dataset picker"],
  [/replace (the |your |this )?(dataset|file|upload)/i, "uploads add to existing data; they don't replace it"],
  [/rename (the |your |this )?(dataset|column|table)/i, "datasets and columns can't be renamed"],
  [/(add|create) (a )?custom column/i, "columns are fixed"],
  [/(choose|enter|add|list) your (own )?options/i, "decision options are generated, not user-supplied"],
  [/what['’]s driving the change/i, "no product-level attribution exists"],
  // forecasts are saved only when the owner presses "Save this forecast"; nothing is saved automatically, and customer results are not saved
  [/saved customer/i, "customer results aren't saved"],
  [/automatically saved (forecast|customer)/i, "nothing is saved automatically"],
  [/(is|are|will be) guaranteed/i, "forecasts and suggestions are never guaranteed"],
  [/guaranteed (to|returns|results|growth)/i, "forecasts and suggestions are never guaranteed"],
  [/we recommend/i, "generated actions are suggestions, not firm recommendations"],
  [/you should (raise|lower|increase|decrease|change|spend|buy|cut)/i, "say 'DecisionGPT suggests considering…' instead"],
  [/saved to (my )?reports(?!.*isn)/i, "only chat answers and recommendations are saved"],
  [/(forecast|customer check)s? (is|are) (saved|stored)/i, "forecast and customer results aren't saved"],
];

describe("everyday screens only promise what the product does", () => {
  it("found the screens to scan", () => {
    expect(USER_FILES.length).toBeGreaterThan(20);
  });

  for (const [pattern, reason] of UNSUPPORTED) {
    it(`never says ${pattern} (${reason})`, () => {
      const hits = USER_FILES.filter((f) => pattern.test(readFileSync(f, "utf-8"))).map((f) => path.relative(src, f));
      expect(hits).toEqual([]);
    });
  }
});
