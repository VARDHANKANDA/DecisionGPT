"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { platform, formatKpi, type AnswerExplanation, type KpiExplanation } from "@/lib/platform-api";
import { api, type BusinessMemoryEntry } from "@/lib/api";
import { Notice, btnPrimary, btnSecondary } from "@/components/simple";
import { LoadView, Panel, useLoad } from "@/components/agent-ui";
import { ActionError, Badge, BulletList, Details, PeriodPicker, Workspace, inputCls, useAction } from "@/components/platform-ui";
import type { Anchor } from "@/lib/platform-api";
import { timeAgo } from "@/lib/friendly";

const KPI_KEYS = [
  ["revenue", "Sales"],
  ["orders", "Orders"],
  ["customers", "Customers who bought"],
  ["average_order_value", "Average order"],
  ["profit", "Profit"],
  ["marketing_spend", "Marketing spend"],
  ["marketing_roi", "Return on marketing"],
];

function KpiExplain({ id, initialKey, initialDays, initialAnchor }: { id: string; initialKey: string; initialDays: number; initialAnchor: Anchor }) {
  const [key, setKey] = useState(initialKey);
  const [days, setDays] = useState(initialDays);
  const [anchor, setAnchor] = useState<Anchor>(initialAnchor);
  const [out, setOut] = useState<KpiExplanation | null>(null);
  const run = useAction(async () => setOut(await platform.explainKpi(id, key, days, anchor)));
  return (
    <Panel title="How a number was worked out" note="Every KPI is a plain calculation over your stored rows — no model is involved.">
      <div className="flex flex-wrap items-end gap-4">
        <label className="block text-sm font-medium text-foreground">
          Number
          <select value={key} onChange={(e) => setKey(e.target.value)} className={inputCls}>
            {KPI_KEYS.map(([k, n]) => (
              <option key={k} value={k}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <PeriodPicker days={days} anchor={anchor} onChange={(d, a) => { setDays(d); setAnchor(a); }} />
        <button className={btnPrimary} disabled={run.busy} onClick={() => run.run()}>
          Explain it
        </button>
      </div>
      <ActionError error={run.error} />
      {out ? (
        <div className="mt-5 space-y-4">
          <p className="text-lg font-medium text-foreground">{out.question}</p>
          <p className="text-3xl font-semibold text-foreground">{formatKpi(out.result.value, out.result.unit)}</p>
          <BulletList title="What it means" items={[out.definition]} />
          <BulletList title="Where it comes from" items={[out.source, `${out.rows_used.sales_rows.toLocaleString("en-IN")} sales row(s) and ${out.rows_used.marketing_rows.toLocaleString("en-IN")} marketing row(s) were used.`]} />
          <BulletList title="Filters" items={out.filters} />
          <BulletList title="Assumptions" items={out.assumptions} />
          <BulletList title="Limits" items={out.limitations} />
          <Details summary="Technical detail">
            <p>Method: {out.method}</p>
            <p>Implementation: <code>{out.technical_detail.implementation}</code></p>
            <p>Status rule: {out.technical_detail.status_rule}</p>
          </Details>
        </div>
      ) : null}
    </Panel>
  );
}

function AnswerView({ a }: { a: AnswerExplanation }) {
  return (
    <div className="mt-4 space-y-3">
      <Badge tone={a.path === "llm_analytics" ? "warn" : "neutral"}>{a.path === "llm_analytics" ? "AI-assisted analytics path" : "Fixed-rule assistant"}</Badge>
      <p className="text-base text-foreground">
        <strong>Question:</strong> {a.question}
      </p>
      <p className="text-base text-foreground">
        <strong>Answer:</strong> {a.answer}
      </p>
      <p className="text-base text-foreground">How it was produced: {a.method}</p>
      {a.checks ? <BulletList title="Checks" items={a.checks.map((c) => `${c.check}: ${c.passed ? "passed" : "failed"}`)} /> : null}
      {a.assumptions && a.assumptions.length > 0 ? <BulletList title="Assumptions" items={a.assumptions} /> : null}
      {a.sources.length > 0 ? <BulletList title="Sources" items={a.sources} /> : null}
      <BulletList title="Limits" items={a.limitations} />
      {a.structured_request || a.tool ? (
        <Details summary="Technical detail">
          {a.tool ? <p>Tool: <code>{a.tool}</code></p> : null}
          {a.structured_request ? <pre className="overflow-x-auto rounded-lg bg-muted-surface p-3 text-xs">{JSON.stringify(a.structured_request, null, 2)}</pre> : null}
        </Details>
      ) : null}
    </div>
  );
}

function AnswerExplain({ id }: { id: string }) {
  const list = useLoad(async (b) => (await api.listMemory(b, "chat")).filter((m: BusinessMemoryEntry) => m.memory_type === "chat").slice(0, 25));
  const [out, setOut] = useState<AnswerExplanation | null>(null);
  const run = useAction(async (mid: string) => setOut(await platform.explainAnswer(id, mid)));
  return (
    <Panel title="How an assistant answer was produced" note="Pick one of your earlier chat answers to see how it was worked out.">
      <LoadView load={list} label="Loading your earlier answers…">
        {(items) =>
          items.length === 0 ? (
            <p className="text-base text-muted">
              No chat answers yet. <Link href="/chat" className="font-medium text-accent underline underline-offset-4">Ask a question</Link> first.
            </p>
          ) : (
            <ul className="divide-y divide-border rounded-xl border border-border">
              {items.map((m) => {
                const q = typeof m.metadata_json?.question === "string" ? (m.metadata_json.question as string) : m.content.slice(0, 80);
                return (
                  <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3">
                    <div className="min-w-0">
                      <p className="text-base text-foreground">{q}</p>
                      <p className="text-sm text-muted">{timeAgo(m.created_at)}</p>
                    </div>
                    <button className={btnSecondary} disabled={run.busy} onClick={() => run.run(m.id)}>
                      Explain
                    </button>
                  </li>
                );
              })}
            </ul>
          )
        }
      </LoadView>
      <ActionError error={run.error} />
      {out ? <AnswerView a={out} /> : null}
    </Panel>
  );
}

function Body({ id }: { id: string }) {
  const sp = useSearchParams();
  const kpi = sp.get("kpi") ?? "revenue";
  const days = Number(sp.get("days") ?? 30);
  const anchor = (sp.get("anchor") === "latest" ? "latest" : "today") as Anchor;
  return (
    <div className="space-y-6">
      <Notice tone="info" title="What is and is not explained here">
        Numbers are explained from the exact rows and rules behind them. Answers are explained from the record stored with them. DecisionGPT does not show feature-importance charts for recommendations unless the stored analysis actually contains them — and never invents a reason after the fact.
      </Notice>
      <KpiExplain id={id} initialKey={KPI_KEYS.some(([k]) => k === kpi) ? kpi : "revenue"} initialDays={[7, 30, 90].includes(days) ? days : 30} initialAnchor={anchor} />
      <AnswerExplain id={id} />
      <Panel title="Recommendations">
        <p className="text-base text-foreground">
          Each recommendation has its own “why” — the goal, the data, the specialist reviews and the risks. Open one from{" "}
          <Link href="/history" className="font-medium text-accent underline underline-offset-4">Decision History</Link>.
        </p>
      </Panel>
    </div>
  );
}

export default function ExplainPage() {
  return (
    <Workspace title="Explainable AI" subtitle="Show your work: how each number, answer and recommendation was produced, from what, and with which limits.">
      {(id) => (
        <Suspense fallback={null}>
          <Body id={id} />
        </Suspense>
      )}
    </Workspace>
  );
}
