"use client";

import { useEffect, useMemo, useState } from "react";
import { EvalEmptyState, Expandable, PageIntro, Panel } from "@/components/research-ui";
import { Definition, EvidenceTypeBadge, when } from "@/components/research-evidence";
import { researchApi, type LlmEvaluationStatus, type LlmRunDetail } from "@/lib/research-api";

type Attempt = LlmRunDetail["attempts"][number];

const PATH_LABEL: Record<string, string> = {
  llm_answered: "AI path: answered",
  llm_clarification: "AI path: asked a clarifying question",
  llm_unsupported: "AI path: declined as unsupported",
  legacy_fallback: "Fallback: standard assistant",
};

const KIND_LABEL: Record<string, string> = {
  live_evaluation: "Live evaluation",
  mock_validation: "Mock validation — not a result",
  plumbing_check: "Plumbing check — not a result",
  blocked: "Blocked — nothing executed",
  other: "Other record",
};

/** One outcome bucket per attempt, so the counts add up and nothing is double counted. */
function bucket(a: Attempt): "correct" | "incorrect" | "fallback" | "clarification" | "unsupported" | "error" {
  if (a.error || a.outcome === "tool_data_access_failure") return "error";
  if (a.path_class === "legacy_fallback") return "fallback";
  if (a.path_class === "llm_clarification") return "clarification";
  if (a.path_class === "llm_unsupported") return "unsupported";
  return a.correct ? "correct" : "incorrect";
}

const BUCKET_LABEL: Record<string, string> = {
  correct: "Correct",
  incorrect: "Incorrect",
  fallback: "Fallback (standard assistant)",
  clarification: "Clarifying question",
  unsupported: "Declined as unsupported",
  error: "Error",
};

const PROVIDER_LABEL: Record<string, string> = { openai: "OpenAI", "typesafe-jev": "TypeSafe Jev (earlier provider)" };
const providerName = (p: string | null | undefined) => (p ? PROVIDER_LABEL[p] ?? p : "not available");

const show = (v: unknown): string => (v === null || v === undefined ? "not available" : Array.isArray(v) ? v.join(", ") : typeof v === "object" ? JSON.stringify(v) : String(v));

export default function LlmEvaluationPage() {
  const [status, setStatus] = useState<LlmEvaluationStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [loaded, setLoaded] = useState<{ id: string; detail: LlmRunDetail | null; error: string | null } | null>(null);
  const [category, setCategory] = useState("all");
  const [outcome, setOutcome] = useState("all");

  useEffect(() => {
    researchApi
      .llmEvaluation()
      .then((s) => {
        setStatus(s);
        const live = (s.run_history ?? []).filter((r) => r.kind === "live_evaluation");
        // latest valid (live) run is the default view
        setRunId(live[0]?.run_id ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load the evaluation status."));
  }, []);

  useEffect(() => {
    if (!runId) return;
    let alive = true;
    researchApi
      .llmRunDetail(runId)
      .then((d) => alive && setLoaded({ id: runId, detail: d, error: null }))
      .catch((e) => alive && setLoaded({ id: runId, detail: null, error: e instanceof Error ? e.message : "Could not load this run." }));
    return () => {
      alive = false;
    };
  }, [runId]);

  // a result for a previously selected run is ignored, so no stale table is ever shown
  const detail = loaded && loaded.id === runId ? loaded.detail : null;
  const detailError = loaded && loaded.id === runId ? loaded.error : null;

  const attempts = useMemo(() => detail?.attempts ?? [], [detail]);
  const categories = useMemo(() => Array.from(new Set(attempts.map((a) => a.category))).sort(), [attempts]);
  const filtered = useMemo(
    () => attempts.filter((a) => (category === "all" || a.category === category) && (outcome === "all" || bucket(a) === outcome)),
    [attempts, category, outcome],
  );

  if (error) return <EvalEmptyState message={error} />;
  if (!status) return <p className="text-sm text-muted">Loading…</p>;

  const history = status.run_history ?? [];
  const liveRuns = history.filter((r) => r.kind === "live_evaluation");
  const covs = status.live_coverage ?? [];
  const sm = detail?.summary;
  const counts: Record<string, number> = { correct: 0, incorrect: 0, fallback: 0, clarification: 0, unsupported: 0, error: 0 };
  attempts.forEach((a) => (counts[bucket(a)] += 1));
  const lat = attempts.map((a) => a.latency_s).filter((v): v is number => typeof v === "number").sort((a, b) => a - b);
  const medianLat = lat.length ? lat[Math.floor(lat.length / 2)] : null;

  return (
    <div className="space-y-6">
      <PageIntro
        title="LLM evaluation"
        subtitle="Purpose: check how well the AI model turns business questions into structured requests. The model only classifies the question; the deterministic engine produces every number, which is compared with ground truth computed independently from the data."
      />

      <Panel title="Status">
        {liveRuns.length === 0 ? (
          <>
            <p className="text-base font-semibold text-foreground">Not evaluated</p>
            <p className="mt-1 text-sm text-muted">
              No live evaluation run is stored, so no accuracy, latency, token or cost figure is shown. {status.llm.enabled ? "The provider is configured; a run is an explicit command." : "The provider is not configured."}
            </p>
          </>
        ) : (
          <>
            <p className="text-base font-semibold text-foreground">Partial evaluation — the five-repeat frozen benchmark is incomplete</p>
            <ul className="mt-1 space-y-1 text-sm text-muted">
              {covs.map((c) => (
                <li key={c.provider}>
                  <span className="font-medium text-foreground">{providerName(c.provider)}:</span> {c.tasks_attempted_at_least_once} of {c.tasks_in_spec} frozen tasks attempted at least once, {c.max_repeats_any_run} of{" "}
                  {c.repeats_frozen ?? "?"} repeats.
                </li>
              ))}
            </ul>
            <p className="mt-1 text-sm text-muted">
              One attempt per task is not a reliable accuracy estimate: it shows whether the live path works on each task, not how often it is right. Results from different
              providers are shown separately and are never combined into one score.
            </p>
          </>
        )}
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
          <div><dt className="text-muted">Current provider and model</dt><dd className="font-medium text-foreground">{status.llm.enabled ? `${providerName(status.llm.provider)} / ${status.llm.model}` : "Not configured (set OPENAI_API_KEY)"}</dd></div>
          <div><dt className="text-muted">Benchmark</dt><dd className="font-medium text-foreground">{status.tasks.n} frozen tasks ({status.tasks.n_primary} scored, {status.tasks.n_supplementary} GST not scored)</dd></div>
          <div><dt className="text-muted">Dataset</dt><dd className="font-medium text-foreground">Indian POS register, 89 days, one store</dd></div>
        </dl>
      </Panel>

      {covs.map((cov) => (
        <Panel key={cov.provider} title={`Coverage — ${providerName(cov.provider)}${cov.is_active_provider ? " (current provider)" : ""}`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <caption className="sr-only">Tasks, repeats and scored results per live run for this provider</caption>
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">Run</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Tasks</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Repeats</th>
                  <th scope="col" className="py-1 pr-3 text-right font-medium">Scored correct</th>
                  <th scope="col" className="py-1 text-right font-medium">Requests</th>
                </tr>
              </thead>
              <tbody>
                {cov.runs.map((c) => (
                  <tr key={c.run_id} className="border-t border-border">
                    <th scope="row" className="py-1.5 pr-3 text-left font-mono text-xs font-normal">{c.run_id}</th>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{c.tasks}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{c.repeats ?? "n/a"}</td>
                    <td className="py-1.5 pr-3 text-right tabular-nums">{c.primary_correct} of {c.primary_attempts}</td>
                    <td className="py-1.5 text-right tabular-nums">{c.provider_requests ?? "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-muted">{cov.note}</p>
        </Panel>
      ))}

      <Panel title="Run">
        <label className="text-sm text-muted" htmlFor="run-select">Run shown (the latest live run is the default)</label>
        <select
          id="run-select"
          value={runId ?? ""}
          onChange={(e) => {
            setRunId(e.target.value || null);
            setCategory("all");
            setOutcome("all");
          }}
          className="mt-1 block w-full max-w-xl rounded-lg border border-border bg-surface px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-accent"
        >
          <option value="">No run selected</option>
          {history.map((r) => (
            <option key={r.run_id} value={r.run_id}>
              {r.run_id} — {KIND_LABEL[r.kind] ?? r.kind}{r.provider ? ` — ${providerName(r.provider)}` : ""}
            </option>
          ))}
        </select>
        {detailError ? <p role="alert" className="mt-3 text-sm text-danger">{detailError}</p> : null}
        {!runId && !detailError ? <p className="mt-3 text-sm text-muted">Select a run to see its attempts.</p> : null}
      </Panel>

      {detail ? (
        <>
          {!detail.is_live_result ? (
            <p role="note" className="rounded-xl border border-border bg-warning-soft px-4 py-3 text-sm text-foreground">
              This record is a <strong>{KIND_LABEL[detail.kind] ?? detail.kind}</strong>. It exercises the measurement code and carries no information about any model.
            </p>
          ) : sm?.run_type === "partial_pilot" ? (
            <p role="note" className="rounded-xl border border-border bg-warning-soft px-4 py-3 text-sm text-foreground">
              <strong>Partial evaluation:</strong> {sm.task_ids_attempted?.length} of {sm.tasks_in_spec} frozen tasks, {sm.repeats_used} repeat(s) each (frozen protocol: {sm.repeats_frozen}).
            </p>
          ) : null}

          <Panel title="Results" right={<EvidenceTypeBadge type={detail.is_live_result ? "measured" : "not_evaluated"} />}>
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3 lg:grid-cols-6">
              {Object.keys(counts).map((k) => (
                <div key={k} className="rounded-xl border border-border p-3">
                  <dt className="text-xs text-muted">{BUCKET_LABEL[k]}</dt>
                  <dd className="mt-1 text-xl font-semibold tabular-nums text-foreground">{counts[k]}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-sm text-muted">
              {attempts.length} attempt(s). Scored (primary) tasks: {sm ? `${sm.primary.correct} of ${sm.primary.attempts} correct` : "not available"}. GST tasks are a separate track: the production data has no GST
              field, so declining is the expected behaviour and they are not part of the accuracy count. Scoring compares the answer&apos;s number or name with ground truth computed from the data, within a
              tolerance fixed before any run.
            </p>
            <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-4">
              <div><dt className="text-muted">Provider requests</dt><dd className="font-medium text-foreground">{sm ? show(sm.provider_requests) : "not available"}</dd></div>
              <div><dt className="text-muted">Tokens (in / out)</dt><dd className="font-medium text-foreground">{sm ? `${show(sm.input_tokens)} / ${show(sm.output_tokens)}` : "not available"}</dd></div>
              <div><dt className="text-muted">Median latency</dt><dd className="font-medium text-foreground">{medianLat === null ? "not available" : `${medianLat.toFixed(2)} s`}</dd></div>
              <div><dt className="text-muted">Estimated cost (list price)</dt><dd className="font-medium text-foreground">{sm?.estimated_cost_usd_at_list_price === null || sm === undefined ? "not available" : `$${sm.estimated_cost_usd_at_list_price}`}</dd></div>
            </dl>
            <p className="mt-1 text-xs text-muted">Cost is provider-reported input tokens × the published list price: an estimate, not a billing record. The provider&apos;s credit unit is not defined, so no credit figure is given.</p>
          </Panel>

          <Panel title="Questions, answers and expected results">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label htmlFor="cat" className="block text-xs text-muted">Task category</label>
                <select id="cat" value={category} onChange={(e) => setCategory(e.target.value)} className="mt-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm">
                  <option value="all">All categories</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>{c.replace(/_/g, " ")}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="out" className="block text-xs text-muted">Outcome</label>
                <select id="out" value={outcome} onChange={(e) => setOutcome(e.target.value)} className="mt-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm">
                  <option value="all">All outcomes</option>
                  {Object.keys(BUCKET_LABEL).map((k) => (
                    <option key={k} value={k}>{BUCKET_LABEL[k]}</option>
                  ))}
                </select>
              </div>
              <p className="pb-1.5 text-sm text-muted" aria-live="polite">{filtered.length} of {attempts.length} shown</p>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <caption className="sr-only">Each question with the system answer, the expected answer and the outcome</caption>
                <thead className="text-left text-xs text-muted">
                  <tr>
                    <th scope="col" className="py-1 pr-3 font-medium">Task</th>
                    <th scope="col" className="py-1 pr-3 font-medium">Question</th>
                    <th scope="col" className="py-1 pr-3 font-medium">System answer</th>
                    <th scope="col" className="py-1 pr-3 font-medium">Expected</th>
                    <th scope="col" className="py-1 font-medium">Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((a, i) => {
                    const b = bucket(a);
                    return (
                      <tr key={`${a.task_id}-${a.repeat}-${i}`} className="border-t border-border align-top">
                        <th scope="row" className="py-2 pr-3 text-left font-mono text-xs font-normal">
                          {a.task_id}
                          <span className="block text-muted">{a.track === "supplementary" ? "GST, not scored" : a.category.replace(/_/g, " ")}</span>
                        </th>
                        <td className="py-2 pr-3">{a.question}</td>
                        <td className="max-w-xs py-2 pr-3 text-muted">{a.answer ?? "no answer"}</td>
                        <td className="py-2 pr-3 tabular-nums">{show(a.expected)}</td>
                        <td className="py-2">
                          <span className="font-medium text-foreground">{BUCKET_LABEL[b]}</span>
                          <span className="block text-xs text-muted">{PATH_LABEL[a.path_class ?? ""] ?? a.path_class ?? "not available"}{a.failure_category ? ` (${a.failure_category.replace(/_/g, " ")})` : ""}</span>
                        </td>
                      </tr>
                    );
                  })}
                  {filtered.length === 0 ? (
                    <tr><td colSpan={5} className="py-6 text-center text-muted">No attempts match these filters.</td></tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </Panel>
        </>
      ) : null}

      <Panel title="Limitations and next step">
        <ul className="space-y-1.5 text-sm text-muted">
          {status.limitations.map((l) => (
            <li key={l}>• {l}</li>
          ))}
          <li>• The reference tool-use baseline (a model writing pandas code) is not implemented for the current provider; no head-to-head comparison is shown.</li>
        </ul>
        {status.run_plan ? (
          <p className="mt-3 text-sm text-foreground">
            <span className="font-medium">Next step:</span> complete the frozen protocol ({status.run_plan.tasks} tasks × {status.run_plan.repeats_per_task} repeats = {status.run_plan.planned_attempts} attempts, up to {status.run_plan.planned_attempts * status.run_plan.provider_requests_per_attempt} provider requests, about{" "}
            {status.run_plan.estimated_cost_usd_at_list_price === null ? "an unknown cost" : `$${status.run_plan.estimated_cost_usd_at_list_price} at list price`}). A run is an explicit command; nothing starts from this page.
          </p>
        ) : null}
      </Panel>

      <div className="space-y-2">
        <Expandable summary="Run history">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead className="text-left text-xs text-muted">
                <tr>
                  <th scope="col" className="py-1 pr-3 font-medium">Run</th>
                  <th scope="col" className="py-1 pr-3 font-medium">What it is</th>
                  <th scope="col" className="py-1 pr-3 font-medium">Status</th>
                  <th scope="col" className="py-1 font-medium">Attempts</th>
                </tr>
              </thead>
              <tbody>
                {history.map((r) => (
                  <tr key={r.run_id} className="border-t border-border">
                    <td className="py-1.5 pr-3 font-mono text-xs">{r.run_id}</td>
                    <td className="py-1.5 pr-3">{KIND_LABEL[r.kind] ?? r.kind}</td>
                    <td className="py-1.5 pr-3">{r.status ?? "n/a"}</td>
                    <td className="py-1.5">{r.completed_attempts ?? "—"}/{r.planned_attempts ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs">Stored runs are never deleted or overwritten. Only “Live evaluation” records are results.</p>
        </Expandable>

        <Expandable summary="Technical details">
          <dl className="space-y-3">
            {detail ? (
              <>
                <Definition term="Selected run">{detail.run_id} — {when(detail.created_utc)}; provider {providerName(detail.provider)}, requested {show(detail.model_requested)}, served by {show(detail.models_returned)}</Definition>
                <Definition term="Frozen artefacts">
                  spec {show(detail.technical.spec_sha256)}; manifest {show(detail.technical.manifest_sha256)}; scorer {show(detail.technical.scorer_version)}; ground truth {show(detail.technical.ground_truth_version)}
                </Definition>
                <Definition term="Retry policy">{show(detail.technical.retry_policy)}</Definition>
                <Definition term="Condition and repeats">{show(detail.technical.conditions)}; repeats {show(detail.technical.repeats)}</Definition>
              </>
            ) : null}
            <Definition term={`Historical connectivity check (${providerName(status.live_verification?.provider)}; real requests, not an evaluation)`}>
              {status.live_verification
                ? `${status.live_verification.requests_total} request(s), all HTTP 200: ${status.live_verification.all_http_200 ? "yes" : "no"}. ${status.live_verification.summary ?? ""}`
                : "none recorded"}
            </Definition>
            <Definition term="Infrastructure">
              task spec {status.infrastructure.task_spec ? "present" : "missing"}; ground truth {status.infrastructure.ground_truth ? "present" : "missing"}; dataset {status.infrastructure.dataset_present ? "present" : "missing"}
            </Definition>
            <Definition term="Evaluation data view">{status.view_rules ?? "not available"}</Definition>
          </dl>
        </Expandable>
      </div>
    </div>
  );
}
