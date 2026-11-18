"use client";

import type { CausalClass, CausalResult } from "@/lib/platform-api";
import { Notice } from "@/components/simple";
import { Panel } from "@/components/agent-ui";
import { Badge, BulletList, DataTable, Details } from "@/components/platform-ui";

export const CLASS_LABEL: Record<CausalClass, { label: string; tone: "good" | "warn" | "bad" | "neutral"; meaning: string }> = {
  not_enough_data: { label: "Not enough data", tone: "neutral", meaning: "Your records do not cover enough days or variation for this analysis, so no estimate is given." },
  not_configured: { label: "Not set up", tone: "neutral", meaning: "Something the analysis needs (a product, a date, a choice) was not provided." },
  assumptions_not_satisfied: { label: "Assumptions not satisfied", tone: "bad", meaning: "A check the method relies on failed, so reporting an effect would be misleading. No estimate is given." },
  exploratory_association: { label: "Exploratory association — not causal", tone: "warn", meaning: "Two things move together in your records. This does not show that one causes the other." },
  causal_estimate: { label: "Causal estimate under stated assumptions", tone: "good", meaning: "An estimate from a design that can support a causal reading — only if the assumptions listed below hold." },
  failed: { label: "Analysis failed", tone: "bad", meaning: "The calculation errored. No result is shown." },
};

const fmt = (n: number, d = 2) => n.toLocaleString("en-IN", { maximumFractionDigits: d, minimumFractionDigits: 0 });

export function CausalResultView({ r }: { r: CausalResult }) {
  const c = CLASS_LABEL[r.classification];
  const e = r.estimate;
  const value = e ? (e.effect_per_product_day ?? e.coefficient) : undefined;
  return (
    <div className="space-y-5">
      <div className="rounded-2xl border border-border bg-surface p-5">
        <p className="mb-2">
          <Badge tone={c.tone}>{c.label}</Badge>
        </p>
        <p className="text-lg font-medium text-foreground">{r.headline}</p>
        <p className="mt-1 text-base text-muted">{c.meaning}</p>
        <p className="mt-2 text-base text-foreground">Question: {r.question}</p>
        {r.reason ? <p className="mt-2 text-base text-foreground">{r.reason}</p> : null}
        {r.error ? <p className="mt-2 text-base text-danger">{r.error}</p> : null}
      </div>

      {e && value !== undefined ? (
        <Panel title="The estimate">
          <p className="text-3xl font-semibold text-foreground">
            {value >= 0 ? "+" : ""}
            {fmt(value, 3)} <span className="text-lg font-normal text-muted">{e.unit}</span>
          </p>
          <p className="mt-1 text-base text-foreground">
            95% interval: {fmt(e.ci95[0], 3)} to {fmt(e.ci95[1], 3)} · p = {e.p_value < 0.001 ? "< 0.001" : e.p_value.toFixed(3)}
          </p>
          {r.interpretation ? <p className="mt-3 text-base text-foreground">{r.interpretation}</p> : null}
        </Panel>
      ) : null}

      {r.warnings && r.warnings.length > 0 ? (
        <Notice tone="warning" title="Warnings from the checks">
          <ul className="list-disc space-y-1 pl-5">
            {r.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Notice>
      ) : null}

      {r.suitability ? (
        <Panel title="Is the data suitable?">
          <DataTable columns={["Check", "Result", "Detail"]} rows={r.suitability.map((s) => [s.check, s.passed ? "Passed" : "Not met", s.detail])} caption="Suitability checks" />
          {r.coverage ? <p className="mt-2 text-sm text-muted">Days used: {r.coverage.days_used}{r.coverage.first_day ? ` (${r.coverage.first_day} to ${r.coverage.last_day})` : ""}.</p> : null}
        </Panel>
      ) : null}

      {r.assumptions && r.assumptions.length > 0 ? (
        <Panel title="Assumptions" note="Statuses are honest: “unverified” means the data cannot check it.">
          <DataTable columns={["Assumption", "Status"]} rows={r.assumptions.map((a) => [a.assumption, a.status])} caption="Assumptions" />
        </Panel>
      ) : null}

      {r.pre_trend_test ? (
        <Panel title="Did the groups move alike before the change?">
          <p className="text-base text-foreground">
            {r.pre_trend_test.description} p = {r.pre_trend_test.p_value.toFixed(3)} (flagged below {r.pre_trend_test.threshold}). {r.pre_trend_test.rejected ? "They did not move alike, so the comparison is not trusted." : "No clear difference found — which does not prove they would have stayed alike."}
          </p>
        </Panel>
      ) : null}

      {r.robustness || r.placebo || r.feedback ? (
        <Details summary="Robustness checks">
          {r.robustness ? <DataTable columns={["Check", "Association", "p-value"]} rows={r.robustness.map((x) => [x.check, fmt(x.coef, 3), x.p < 0.001 ? "< 0.001" : x.p.toFixed(3)])} caption="Robustness" /> : null}
          {r.placebo ? <p>Placebo — {r.placebo.description}: {fmt(r.placebo.coef, 3)} (p = {r.placebo.p_value.toFixed(3)}).</p> : null}
          {r.feedback ? <p>Feedback — {r.feedback.description}: {fmt(r.feedback.coef, 3)} (p = {r.feedback.p_value.toFixed(3)}).</p> : null}
        </Details>
      ) : null}

      {r.method ? (
        <Details summary="Method">
          <p>
            <strong>{r.method.name}.</strong> {r.method.model ? <code className="text-sm">{r.method.model}</code> : null}
          </p>
          {r.method.why_chosen ? <p>Why this method: {r.method.why_chosen}</p> : null}
          {r.method.why_not_causal ? <p>Why this is not causal: {r.method.why_not_causal}</p> : null}
          <p className="text-sm text-muted">Method version {r.method_version}, run on {r.generated_on}.</p>
        </Details>
      ) : null}
      {r.limitations ? <BulletList title="Limitations" items={r.limitations} /> : null}
    </div>
  );
}
