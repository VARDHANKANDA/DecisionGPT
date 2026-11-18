"use client";

import Link from "next/link";
import { FEATURES } from "@/lib/features";
import { Page, btnPrimary, btnSecondary } from "@/components/simple";

const FAQ: { q: string; a: React.ReactNode }[] = [
  {
    q: "What is DecisionGPT?",
    a: "It reads the business data you give it and helps you understand your business, predict what may happen next, understand your customers, and decide what to do — all in plain language.",
  },
  {
    q: "Which part should I use?",
    a: (
      <ul className="space-y-2">
        {FEATURES.map((f) => (
          <li key={f.id}>
            <Link href={f.href} className="font-medium text-accent underline underline-offset-4">{f.icon} {f.title}</Link>
            {" — "}{f.summary}
          </li>
        ))}
      </ul>
    ),
  },
  {
    q: "What data does each part need?",
    a: (
      <ul className="space-y-2">
        {FEATURES.filter((f) => f.uses.length > 0).map((f) => (
          <li key={f.id}><strong>{f.title}:</strong> {f.needs}</li>
        ))}
      </ul>
    ),
  },
  {
    q: "Not sure what to upload?",
    a: (
      <>
        Start with your sales. Sales data can include columns such as Date, Product, Quantity, and Amount. If you don&apos;t
        have a file, you can{" "}
        <Link href="/data/manual" className="font-medium text-accent underline underline-offset-4">type the data in</Link>{" "}
        or{" "}
        <Link href="/data/samples" className="font-medium text-accent underline underline-offset-4">look at a sample</Link>{" "}
        first.
      </>
    ),
  },
  {
    q: "Not sure what to ask?",
    a: "Try: “Which products sold the most last month?” In Chat with Your Data you can tap any example to fill in the question, then press Ask.",
  },
  {
    q: "Is a forecast or a customer check a promise?",
    a: "No. Forecasts and “customers who may be at risk” are estimates based on patterns in your past data. They can be wrong, and the expected range shows how much they could vary. They were built and tested on DecisionGPT's example data, not on your business.",
  },
  {
    q: "Is an answer a fact or a prediction?",
    a: "Every chat answer is labelled. “From your records” means it was counted from your data. “An estimate” means it is a prediction or a what-if, so it is not certain. “A suggestion” is advice to think about.",
  },
  {
    q: "Why does it sometimes say it doesn't have enough data?",
    a: "DecisionGPT only answers when your data supports the answer. If something is missing, it says so instead of guessing. Adding more data (or older data) usually helps.",
  },
  {
    q: "Why can't I choose which data an analysis uses?",
    a: "DecisionGPT automatically uses all of your available data in each group (sales, customers, products, stock, marketing). There is nothing to pick. If you want an analysis to ignore something, remove that data from My Data.",
  },
  {
    q: "How do I replace data I already added?",
    a: "New uploads and typed-in rows are always added to what you already have — they don't replace it. To replace a group completely, first open it in My Data and choose “Remove data”, then add the new data.",
  },
  {
    q: "Are my forecasts and customer checks saved?",
    a: "No. They are shown on the page while you view them. Chat answers and business-decision suggestions are saved in Saved Answers.",
  },
  {
    q: "Can I give DecisionGPT my own options to compare?",
    a: "Not yet. In Business Decisions you tell it your goal, and it comes up with possible actions itself — pricing, marketing or stock changes — then ranks them.",
  },
  {
    q: "Can I change or delete my data?",
    a: (
      <>
        Yes. Open{" "}
        <Link href="/data" className="font-medium text-accent underline underline-offset-4">My Data</Link>, choose a kind of
        data, and you can edit a row, delete a row, or remove everything of that kind. You are always asked to confirm before
        anything is deleted.
      </>
    ),
  },
  {
    q: "What is the demo account?",
    a: "The demo account contains made-up sample business data so you can explore the whole product without uploading anything. It is clearly marked DEMO and is not a real business.",
  },
];

export default function HelpPage() {
  return (
    <Page title="Help" subtitle="Short answers to common questions.">
      <ul className="grid gap-3">
        {FAQ.map((f) => (
          <li key={f.q}>
            <details className="rounded-2xl border border-border bg-surface">
              <summary className="min-h-[56px] cursor-pointer px-5 py-4 text-lg font-medium text-foreground">{f.q}</summary>
              <div className="border-t border-border px-5 py-4 text-lg leading-relaxed text-muted">{f.a}</div>
            </details>
          </li>
        ))}
      </ul>
      <div className="mt-8 flex flex-wrap gap-3">
        <Link href="/data/upload" className={btnPrimary}>Add my data</Link>
        <Link href="/dashboard" className={btnSecondary}>Back to Home</Link>
      </div>
    </Page>
  );
}
