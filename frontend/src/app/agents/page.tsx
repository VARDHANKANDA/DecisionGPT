"use client";

import Link from "next/link";
import { AGENTS } from "@/lib/features";
import { Notice, Page, btnSecondary } from "@/components/simple";

export default function AgentsPage() {
  return (
    <Page
      title="Agent Workspace"
      subtitle="Five specialist views of your business. Each one reads your own data and says plainly what it can and cannot do."
      wide
    >
      <div className="mb-8">
        <Notice tone="info" title="How the agents work here">
          The Business Analyst, Financial Advisor and Risk Manager are rule-based checks that review each recommendation you ask for. The Strategy Optimiser ranks the options. The Marketing Advisor is an evidence view of your marketing records. They don&apos;t run on their own, and there is no hidden coordinator acting for you.
        </Notice>
      </div>
      <ul className="grid gap-5 md:grid-cols-2">
        {AGENTS.map((a) => (
          <li key={a.id} className="min-w-0">
            <article className="flex h-full flex-col rounded-2xl border border-border bg-surface p-6">
              <div className="flex items-center gap-3">
                <span aria-hidden="true" className="flex h-12 w-12 items-center justify-center rounded-xl bg-accent-soft text-2xl">{a.icon}</span>
                <h2 className="text-xl font-semibold text-foreground">{a.name}</h2>
              </div>
              <p className="mt-3 text-base text-foreground">{a.purpose}</p>
              <dl className="mt-3 space-y-2 text-sm">
                <div><dt className="inline font-semibold text-muted">Uses: </dt><dd className="inline text-foreground">{a.uses}</dd></div>
                <div><dt className="inline font-semibold text-muted">Status: </dt><dd className="inline text-foreground">{a.status}</dd></div>
              </dl>
              <div className="mt-5 flex flex-wrap gap-3 pt-1 md:mt-auto">
                <Link href={a.href} className="inline-flex min-h-[44px] items-center rounded-full bg-accent px-5 py-2 text-base font-medium text-accent-foreground hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
                  Open {a.name}
                </Link>
                <Link href={`/chat?q=${encodeURIComponent(a.question)}`} className={btnSecondary}>Ask a question</Link>
              </div>
            </article>
          </li>
        ))}
      </ul>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/agents/debate" className="inline-flex min-h-[44px] items-center rounded-full bg-accent px-5 py-2 text-base font-medium text-accent-foreground hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
          Start a Multi-Agent Debate
        </Link>
        <span className="self-center text-base text-muted">Ask one question and see all five specialists work through it, step by step.</span>
      </div>
      <section aria-labelledby="not-built" className="mt-8 rounded-2xl border border-border bg-surface p-6">
        <h2 id="not-built" className="text-xl font-semibold text-foreground">Not built yet</h2>
        <p className="mt-1 text-base text-muted">So there is nothing here to click — and nothing that pretends to be it.</p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-base text-foreground">
          <li>A learning optimiser that improves its own choices over time (reinforcement learning).</li>
          <li>A Business Knowledge library of your own documents and policies.</li>
          <li>Connections to accounting, payment or shop systems — data comes from uploads and typed entries.</li>
          <li>Continuous monitoring in the background — checks run when you open a page or press a button.</li>
        </ul>
      </section>
    </Page>
  );
}
