"use client";

import { Block, EvaluatedOn, MetricGrid, StateNote, type StateKind } from "@/components/evaluation-cards";
import { DataTable } from "@/components/research-ui";
import type { MetricCardData } from "@/lib/research-api";

/** What the backend's evaluation chat service returns in `details.evaluation` (backend/app/services/evaluation_chat_service.py). */
export interface EvalChatResult {
  id: string;
  evidence: "business" | "training" | "benchmark";
  category: "forecasting" | "classification";
  title: string;
  horizon?: number;
  facts: { label: string; value: string | number | boolean }[];
  groups: { title: string; cards: MetricCardData[] }[];
  extras: {
    verdict?: string | null;
    notes?: string[];
    comparisons?: { reference: string; mae_ratio: number | null; reading: string }[];
    references?: { method: string; cards: MetricCardData[] }[];
    confusion_matrix?: { tp: number; fp: number; fn: number; tn: number; n: number; positive_class: string; threshold: number | null } | null;
    threshold_note?: string;
  };
  state: { kind: string; reason: string } | null;
}

export interface EvalChatDetails {
  version: number;
  query: { mode: string; page: number };
  access: { research: boolean; scope: string };
  pagination: { page: number; pages: number; results_total: number; metric_values_total: number; results_on_page: number; next_prompt: string | null; page_prompts: string[] };
  sections: { evidence: "business" | "training" | "benchmark"; title: string; results: EvalChatResult[] }[];
  inventory?: { by_evidence: Record<string, number> };
  coverage?: { available_values: number; counts_by_state: Record<string, number>; unavailable: { result: string; evidence: string; metric: string; abbr: string; kind: string; state: string; reason: string }[] };
  definitions?: { key: string; name: string; abbr: string; applies_to: string; unit: string; direction_text: string; definition: string; caveat: string | null; sign_note: string | null }[];
  history?: { id: string; kind: string; created_at: string | null; headline: string | null }[];
  messages?: string[];
  headline?: string;
  action?: string | null;
}

export function isEvalChatDetails(d: unknown): d is { evaluation: EvalChatDetails } {
  const e = (d as { evaluation?: unknown } | null)?.evaluation as EvalChatDetails | undefined;
  return !!e && typeof e === "object" && Array.isArray(e.sections) && !!e.pagination;
}

const STATE_KIND: Record<string, StateKind> = { insufficient_data: "insufficient", failed: "failed", not_evaluated: "not_evaluated", not_applicable: "not_evaluated", not_recorded: "not_evaluated" };
const nf = (n: number) => n.toLocaleString("en-IN");

function Confusion({ m }: { m: NonNullable<EvalChatResult["extras"]["confusion_matrix"]> }) {
  return (
    <div className="mt-3 overflow-x-auto">
      <table className="text-sm" aria-label="Confusion matrix">
        <caption className="mb-1 text-left text-xs text-muted">
          Customers (n = {nf(m.n)}) at threshold {m.threshold ?? "—"}. Positive class: {m.positive_class}. Rows are actual, columns are predicted.
        </caption>
        <thead>
          <tr className="text-left text-muted">
            <th className="px-3 py-1 font-medium"><span className="sr-only">Actual</span></th>
            <th className="px-3 py-1 font-medium">Predicted: stays</th>
            <th className="px-3 py-1 font-medium">Predicted: leaves</th>
          </tr>
        </thead>
        <tbody>
          <tr><th scope="row" className="px-3 py-1 text-left font-medium">Actual: stays</th><td className="border border-border px-3 py-2">{nf(m.tn)} (true negative)</td><td className="border border-border px-3 py-2">{nf(m.fp)} (false positive)</td></tr>
          <tr><th scope="row" className="px-3 py-1 text-left font-medium">Actual: left</th><td className="border border-border px-3 py-2">{nf(m.fn)} (false negative)</td><td className="border border-border px-3 py-2">{nf(m.tp)} (true positive)</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function Result({ r, open }: { r: EvalChatResult; open: boolean }) {
  const ex = r.extras;
  return (
    <details open={open} className="rounded-xl border border-border bg-background" data-result={r.id}>
      <summary className="min-h-[44px] cursor-pointer px-4 py-3 text-base font-medium text-foreground">{r.title}</summary>
      <div className="space-y-3 border-t border-border px-4 py-3">
        <EvaluatedOn facts={r.facts.map((f) => [f.label, String(f.value)] as [string, string])} />
        {r.state ? <StateNote kind={STATE_KIND[r.state.kind] ?? "not_evaluated"}>{r.state.reason}</StateNote> : null}
        {r.groups.map((g) => (
          <div key={g.title}>
            <h4 className="mb-2 text-sm font-semibold text-foreground">{g.title}</h4>
            <MetricGrid cards={g.cards} />
          </div>
        ))}
        {ex.confusion_matrix ? <Confusion m={ex.confusion_matrix} /> : null}
        {ex.threshold_note ? <p className="text-sm text-muted">{ex.threshold_note}</p> : null}
        {ex.verdict ? <p className="text-sm font-medium text-foreground">Against the references: {ex.verdict.replace(/_/g, " ")}.</p> : null}
        {ex.comparisons && ex.comparisons.length > 0 ? (
          <DataTable
            headers={["Reference", "MAE ratio (selected ÷ reference)", "How to read it"]}
            rows={ex.comparisons.map((c) => [c.reference.replace(/_/g, " "), c.mae_ratio === null ? "Not available" : c.mae_ratio.toFixed(2), c.reading])}
          />
        ) : null}
        {ex.references && ex.references.length > 0 ? (
          <DataTable
            headers={["Reference method", ...(ex.references[0]?.cards ?? []).map((c) => c.abbr)]}
            rows={ex.references.map((ref) => [ref.method, ...ref.cards.map((c) => c.display)])}
          />
        ) : null}
        {(ex.notes ?? []).map((n) => <p key={n} className="text-sm text-muted">{n}</p>)}
      </div>
    </details>
  );
}

/** The structured evaluation answer: every result the service returned, grouped by kind of evidence, with the values exactly as recorded. */
export function EvaluationAnswer({ details, onFollowUp }: { details: EvalChatDetails; onFollowUp: (q: string) => void }) {
  const { pagination: pg } = details;
  let first = true;
  return (
    <div className="mt-4 space-y-4" data-evaluation-answer>
      <p className="text-sm text-muted">
        {pg.results_total} result(s), {nf(pg.metric_values_total)} metric value(s){pg.pages > 1 ? ` · page ${pg.page} of ${pg.pages}` : ""} ·{" "}
        {details.access.research ? "business and research results" : "your business only"}
      </p>
      {(details.messages ?? []).map((m) => <StateNote key={m} kind="not_evaluated">{m}</StateNote>)}

      {details.definitions ? (
        <DataTable
          headers={["Metric", "Applies to", "Unit", "Direction", "Meaning"]}
          rows={details.definitions.map((d) => [`${d.name} (${d.abbr})`, d.applies_to, d.unit.replace("_", " "), d.direction_text, `${d.definition}${d.sign_note ? ` ${d.sign_note}` : ""}${d.caveat ? ` Keep in mind: ${d.caveat}` : ""}`])}
        />
      ) : null}

      {details.history ? (
        <DataTable headers={["When", "Kind", "Run", "Headline"]} rows={details.history.map((h) => [h.created_at ?? "—", h.kind === "forecast_eval" ? "Forecast" : "Customer score", h.id, h.headline ?? "—"])} />
      ) : null}

      {details.query.mode === "unavailable" && details.coverage ? (
        <Block title="What is not available, and why" tag="">
          <DataTable headers={["Result", "Metric", "State", "Why"]} rows={details.coverage.unavailable.map((u) => [u.result, `${u.metric}${u.abbr !== "-" ? ` (${u.abbr})` : ""}`, u.state, u.reason])} empty="Every metric in scope has a recorded value." />
        </Block>
      ) : (
        details.sections.map((sec) => (
          <Block key={sec.evidence} title={sec.title} tag={sec.evidence}>
            <div className="space-y-3">
              {sec.results.map((r) => {
                const open = first;
                first = false;
                return <Result key={r.id} r={r} open={open} />;
              })}
            </div>
          </Block>
        ))
      )}

      {details.coverage && details.query.mode !== "unavailable" && Object.keys(details.coverage.counts_by_state).length > 0 ? (
        <p className="text-sm text-muted">
          Coverage: {Object.entries(details.coverage.counts_by_state).map(([k, v]) => `${k} ${nf(v)}`).join(" · ")}. Ask “Which metrics are unavailable and why?” for each reason.
        </p>
      ) : null}

      {pg.pages > 1 ? (
        <nav aria-label="More evaluation results" className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted">Pages:</span>
          {pg.page_prompts.map((p, i) => (
            <button
              key={p}
              type="button"
              aria-current={i + 1 === pg.page ? "page" : undefined}
              disabled={i + 1 === pg.page}
              onClick={() => onFollowUp(p)}
              className="min-h-[44px] rounded-full border border-border bg-surface px-4 py-2 text-sm text-foreground hover:bg-muted-surface disabled:border-accent disabled:text-accent"
            >
              {i + 1}
            </button>
          ))}
          {pg.next_prompt ? (
            <button type="button" onClick={() => onFollowUp(pg.next_prompt!)} className="min-h-[44px] rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-foreground hover:opacity-90">
              Show the next page
            </button>
          ) : null}
        </nav>
      ) : null}
    </div>
  );
}
