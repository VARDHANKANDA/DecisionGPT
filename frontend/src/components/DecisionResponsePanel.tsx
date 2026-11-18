"use client";

import { useState } from "react";
import { api, ApiError, type ResponseBody, type TrackingResponse } from "@/lib/api";
import { friendlyError } from "@/lib/friendly";
import { btnPrimary, btnSecondary } from "@/components/simple";

type Choice = "accepted" | "rejected" | "modified" | "deferred";
type Action = "unknown" | "not_executed" | "partially_executed" | "executed";

export const RESPONSE_LABEL: Record<string, string> = {
  pending: "No response recorded yet",
  accepted: "Accepted",
  rejected: "Rejected",
  modified: "Modified",
  deferred: "Deferred",
};
export const ACTION_LABEL: Record<string, string> = {
  unknown: "Whether it was carried out is not recorded",
  not_executed: "Not carried out",
  partially_executed: "Partly carried out",
  executed: "Carried out",
};

const CHOICES: Array<{ value: Choice; label: string; help: string }> = [
  { value: "accepted", label: "Accepted", help: "You agree with this recommendation." },
  { value: "modified", label: "Modified", help: "You are doing something different from what was recommended." },
  { value: "rejected", label: "Rejected", help: "You are not going to do this." },
  { value: "deferred", label: "Deferred", help: "You will decide later." },
];

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Records what the owner did with one recommendation. Accepting is never recorded as carrying it out. */
export function DecisionResponsePanel({
  businessId,
  decisionId,
  current,
  history,
  onSaved,
}: {
  businessId: string;
  decisionId: string;
  current: { recorded: boolean; response: string; action_status: string; note?: string | null; action_start?: string | null };
  history?: TrackingResponse[];
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(!current.recorded);
  const [choice, setChoice] = useState<Choice | "">(current.recorded && current.response !== "pending" ? (current.response as Choice) : "");
  const [action, setAction] = useState<Action>(current.recorded ? ((current.action_status as Action) ?? "unknown") : "unknown");
  const [date, setDate] = useState(current.action_start ?? "");
  const [change, setChange] = useState("");
  const [note, setNote] = useState(current.note ?? "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "info" | "error"; text: string } | null>(null);

  const canExecute = choice === "accepted" || choice === "modified";
  const needsDate = canExecute && (action === "executed" || action === "partially_executed");
  const problems: string[] = [];
  if (!choice) problems.push("Choose what you decided.");
  if (choice === "modified" && !change.trim()) problems.push("Describe what you changed.");
  if (needsDate && !date) problems.push("Enter the date you started.");
  if (needsDate && date > today()) problems.push("The start date cannot be in the future.");

  async function save() {
    if (saving || problems.length > 0 || !choice) return;
    setSaving(true);
    setMessage(null);
    const body: ResponseBody = {
      response: choice,
      // rejected or deferred can never be an executed action; accepted/modified record only what the owner states
      action_status: canExecute ? action : "not_executed",
      note: note.trim() || undefined,
    };
    if (needsDate) body.action_start = date;
    if (choice === "modified") {
      body.modified_action = { description: change.trim() };
      if (needsDate) body.action_taken = { description: change.trim(), basis: "the modified action, not the original recommendation" };
    }
    try {
      await api.recordDecisionResponse(businessId, decisionId, body);
      setMessage({ kind: "ok", text: "Saved. Your earlier answers are kept in the history below." });
      setOpen(false);
      onSaved();
    } catch (e) {
      if (e instanceof ApiError && /already recorded/i.test(e.message)) {
        setMessage({ kind: "info", text: "This is already saved; nothing changed." });
        setOpen(false);
      } else {
        setMessage({ kind: "error", text: friendlyError(e, "We couldn't save that. Nothing was changed.").message });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <section aria-label="Your response to this recommendation" className="mt-3 rounded-xl bg-muted-surface p-4 text-sm">
      <p className="text-foreground">
        <span className="font-medium">Your response: </span>
        {RESPONSE_LABEL[current.response] ?? current.response}
        {current.recorded && current.response !== "pending" ? ` — ${ACTION_LABEL[current.action_status] ?? current.action_status}` : ""}
        {current.action_start && (current.action_status === "executed" || current.action_status === "partially_executed")
          ? ` (started ${current.action_start})`
          : ""}
      </p>
      {current.note ? <p className="mt-1 text-muted">Note: {current.note}</p> : null}

      <div aria-live="polite" className="mt-2">
        {message ? (
          <p className={message.kind === "error" ? "text-danger" : "text-foreground"} role={message.kind === "error" ? "alert" : "status"}>
            {message.text}
          </p>
        ) : null}
      </div>

      {!open ? (
        <button type="button" className={`${btnSecondary} mt-2`} onClick={() => setOpen(true)}>
          {current.recorded ? "Correct or update my response" : "Record my response"}
        </button>
      ) : (
        <form
          className="mt-3 space-y-4"
          onSubmit={(ev) => {
            ev.preventDefault();
            void save();
          }}
        >
          <fieldset>
            <legend className="font-medium text-foreground">What did you decide?</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {CHOICES.map((c) => (
                <label key={c.value} className="flex min-h-[44px] cursor-pointer items-start gap-2 rounded-lg border border-border bg-surface p-3">
                  <input
                    type="radio"
                    name={`resp-${decisionId}`}
                    value={c.value}
                    checked={choice === c.value}
                    onChange={() => {
                      setChoice(c.value);
                      if (c.value === "rejected" || c.value === "deferred") setAction("not_executed");
                      else if (action === "not_executed" && current.action_status !== "not_executed") setAction("unknown");
                    }}
                    className="mt-1 h-4 w-4 accent-[var(--accent)]"
                  />
                  <span>
                    <span className="font-medium text-foreground">{c.label}</span>
                    <span className="block text-muted">{c.help}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>

          {choice === "modified" ? (
            <label className="block">
              <span className="font-medium text-foreground">What did you change?</span>
              <textarea
                className="input mt-1 w-full"
                rows={2}
                maxLength={500}
                value={change}
                onChange={(e) => setChange(e.target.value)}
                aria-required="true"
              />
            </label>
          ) : null}

          {canExecute ? (
            <fieldset>
              <legend className="font-medium text-foreground">Was it carried out?</legend>
              <p className="text-muted">Accepting a recommendation is not the same as doing it, so tell us only what actually happened.</p>
              <div className="mt-2 flex flex-wrap gap-3">
                {(
                  [
                    ["unknown", "Not recorded yet"],
                    ["not_executed", "Not carried out"],
                    ["partially_executed", "Partly carried out"],
                    ["executed", "Carried out"],
                  ] as Array<[Action, string]>
                ).map(([v, label]) => (
                  <label key={v} className="flex min-h-[44px] cursor-pointer items-center gap-2">
                    <input type="radio" name={`act-${decisionId}`} checked={action === v} onChange={() => setAction(v)} className="h-4 w-4 accent-[var(--accent)]" />
                    {label}
                  </label>
                ))}
              </div>
              {needsDate ? (
                <label className="mt-2 block">
                  <span className="font-medium text-foreground">Date you started</span>
                  <input type="date" className="input mt-1 w-48" value={date} max={today()} onChange={(e) => setDate(e.target.value)} aria-required="true" />
                </label>
              ) : null}
            </fieldset>
          ) : choice ? (
            <p className="text-muted">A {choice} recommendation is recorded as not carried out.</p>
          ) : null}

          <label className="block">
            <span className="font-medium text-foreground">Note (optional)</span>
            <textarea className="input mt-1 w-full" rows={2} maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>

          {problems.length > 0 && choice !== "" ? (
            <ul className="list-disc pl-5 text-warning" aria-label="What is still needed">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          ) : null}

          <div className="flex flex-wrap gap-3">
            <button type="submit" className={btnPrimary} disabled={saving || problems.length > 0} aria-busy={saving}>
              {saving ? "Saving…" : "Save my response"}
            </button>
            {current.recorded ? (
              <button type="button" className={btnSecondary} onClick={() => setOpen(false)} disabled={saving}>
                Cancel
              </button>
            ) : null}
          </div>
        </form>
      )}

      {history && history.length > 1 ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-muted">History of this response ({history.length})</summary>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-muted">
            {history.map((h) => (
              <li key={h.seq}>
                {RESPONSE_LABEL[h.response] ?? h.response} — {ACTION_LABEL[h.action_status] ?? h.action_status}
                {h.action_start ? `, started ${h.action_start}` : ""}
                {h.created_at ? ` (recorded ${new Date(h.created_at).toLocaleDateString("en-IN")})` : ""}
              </li>
            ))}
          </ol>
        </details>
      ) : null}
    </section>
  );
}
