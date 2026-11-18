"use client";

import { useState } from "react";
import { platform, type Anchor, type DebateResult } from "@/lib/platform-api";
import { Notice, Spinner, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, PeriodPicker, Workspace, inputCls, useAction } from "@/components/platform-ui";
import { DebateView } from "@/components/debate-view";
import { timeAgo } from "@/lib/friendly";

const EXAMPLES = ["Should I raise my prices?", "Is it worth spending more on marketing?", "What should I do about low stock?", "How is my business doing?"];

function Past({ id, onOpen }: { id: string; onOpen: (r: DebateResult) => void }) {
  const load = useLoad(() => platform.debateRuns(id));
  const open = useAction(async (rid: string) => {
    const r = await platform.debateRun(id, rid);
    onOpen(r.result);
  });
  return (
    <Panel title="Earlier debates" note="Saved exactly as they ran.">
      <LoadView load={load} label="Loading…">
        {({ runs }) =>
          runs.length === 0 ? (
            <p className="text-base text-muted">None yet.</p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {runs.slice(0, 15).map((r) => (
                <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                  <div className="min-w-0">
                    <p className="text-base font-medium text-foreground">{r.question}</p>
                    <p className="text-sm text-muted">
                      {timeAgo(r.created_at)} · {r.mode === "ai_model" ? "AI-model mode" : "rule-based"}
                      {r.status !== "completed" ? ` · ${r.status}` : ""}
                    </p>
                  </div>
                  <button className={btnSecondary} onClick={() => open.run(r.id)} disabled={open.busy}>
                    Open
                  </button>
                </li>
              ))}
            </ul>
          )
        }
      </LoadView>
      <ActionError error={open.error} />
    </Panel>
  );
}

function Body({ id }: { id: string }) {
  const status = useLoad(() => platform.debateStatus(id));
  const [question, setQuestion] = useState("");
  const [mode, setMode] = useState<"rule_based" | "ai_model">("rule_based");
  const [anchor, setAnchor] = useState<Anchor>("today");
  const [result, setResult] = useState<DebateResult | null>(null);
  const [version, setVersion] = useState(0);
  const run = useAction(() => platform.runDebate(id, question.trim(), mode, anchor));
  const tooLong = question.length > 500;
  return (
    <div className="space-y-6">
      <LoadView load={status} label="Checking what is available…">
        {(s) => (
          <>
            <Panel title="Ask a business question" note="Five specialists look at the same evidence from their own angle, challenge each other, and a brief is built from what survives. You decide.">
              <form
                className="space-y-4"
                onSubmit={async (e) => {
                  e.preventDefault();
                  if (!question.trim() || tooLong) return;
                  setResult(null);
                  const r = await run.run();
                  if (r) {
                    setResult(r);
                    setVersion((n) => n + 1);
                  }
                }}
              >
                <label className="block text-sm font-medium text-foreground">
                  Your question
                  <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} maxLength={600} className={inputCls} placeholder="For example: should I raise my prices?" />
                </label>
                <p className={`text-xs ${tooLong ? "text-danger" : "text-muted"}`}>{question.length}/500 characters</p>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLES.map((x) => (
                    <button key={x} type="button" className={btnSecondary} onClick={() => setQuestion(x)}>
                      {x}
                    </button>
                  ))}
                </div>
                <fieldset className="space-y-2">
                  <legend className="text-sm font-medium text-foreground">How should the specialists work?</legend>
                  <label className="flex items-start gap-2 text-base text-foreground">
                    <input type="radio" name="mode" checked={mode === "rule_based"} onChange={() => setMode("rule_based")} className="mt-1 h-5 w-5" />
                    <span>
                      Rule-based review <span className="text-muted">— fixed rules over your records. No AI model, always available.</span>
                    </span>
                  </label>
                  <label className={`flex items-start gap-2 text-base ${s.ai_model_available ? "text-foreground" : "text-muted"}`}>
                    <input type="radio" name="mode" checked={mode === "ai_model"} disabled={!s.ai_model_available} onChange={() => setMode("ai_model")} className="mt-1 h-5 w-5" />
                    <span>
                      AI-model debate <span className="text-muted">— {s.ai_model_available ? "an AI model plays each specialist, with every claim checked against the evidence." : "not available (the AI provider returns typed decisions, not written reasoning)."}</span>
                    </span>
                  </label>
                  {!s.ai_model_available ? <p className="text-sm text-muted">{s.ai_model_notice}</p> : null}
                </fieldset>
                <PeriodPicker days={30} anchor={anchor} options={[30]} onChange={(_d, a) => setAnchor(a)} />
                <button className={btnPrimary} type="submit" disabled={run.busy || !question.trim() || tooLong}>
                  {run.busy ? "Running the debate…" : "Start the debate"}
                </button>
                <ActionError error={run.error} />
              </form>
            </Panel>
            {run.busy ? <Spinner label="The specialists are working through the evidence…" /> : null}
            {result ? <DebateView r={result} /> : null}
            <Past key={version} id={id} onOpen={setResult} />
            <Notice tone="info">The stages are always the same: {s.stages.map((x) => x.replace(/_/g, " ")).join(" → ")}.</Notice>
          </>
        )}
      </LoadView>
    </div>
  );
}

export default function DebatePage() {
  return (
    <Workspace title="Multi-Agent Debate" subtitle="A structured review of one business question: shared evidence, independent specialist views, challenges, and a brief that shows what is and is not settled.">
      {(id) => <Body id={id} />}
    </Workspace>
  );
}
