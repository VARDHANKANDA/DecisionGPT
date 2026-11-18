import { existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { FEATURES, INTENTS, featuresUsing } from "@/lib/features";

const appDir = path.resolve(__dirname, "../app");

describe("feature registry", () => {
  it("every feature opens a real page", () => {
    for (const f of FEATURES) {
      expect(existsSync(path.join(appDir, f.href, "page.tsx")), `${f.href} should exist`).toBe(true);
    }
  });

  it("ids are unique and every 'What are you trying to do?' choice leads to a real feature", () => {
    expect(new Set(FEATURES.map((f) => f.id)).size).toBe(FEATURES.length);
    for (const i of INTENTS) expect(FEATURES.some((f) => f.id === i.featureId)).toBe(true);
  });

  it("only lists real combinations of data and feature", () => {
    expect(featuresUsing("customers").map((f) => f.id)).toContain("customers");
    expect(featuresUsing("customers").map((f) => f.id)).not.toContain("forecast");
    expect(featuresUsing("sales").map((f) => f.id)).toContain("forecast");
    // finance records are stored but no analysis tool reads them yet — we don't pretend otherwise
    expect(featuresUsing("finance")).toHaveLength(0);
  });

  it("no feature text uses developer jargon", () => {
    const text = FEATURES.map((f) => `${f.title} ${f.summary} ${f.needs} ${f.gives} ${f.cta}`).join(" ");
    expect(text).not.toMatch(/\b(API|endpoint|inference|dataset ID|model output|XGBoost|Digital Twin)\b/i);
  });
});

import { AGENTS, NAV_ACCOUNT, NAV_GROUPS, agentById } from "@/lib/features";
import { activeHref } from "@/components/AppShell";

describe("navigation follows the updated architecture", () => {
  const entries = [...NAV_GROUPS.flatMap((g) => g.items), ...NAV_ACCOUNT];

  it("every navigation entry opens a real page", () => {
    for (const e of entries) {
      const dynamicAgent = /^\/agents\/[^/]+$/.test(e.href);
      const file = dynamicAgent ? path.join(appDir, "agents", "[agent]", "page.tsx") : path.join(appDir, e.href, "page.tsx");
      expect(existsSync(file), `${e.href} should exist`).toBe(true);
    }
  });

  it("has no duplicate destinations or labels", () => {
    expect(new Set(entries.map((e) => e.href)).size).toBe(entries.length);
    expect(new Set(entries.map((e) => e.label)).size).toBe(entries.length);
  });

  it("lists the five specialized decision agents with real definitions", () => {
    expect(AGENTS.map((a) => a.name)).toEqual(["Business Analyst", "Financial Advisor", "Marketing Advisor", "Risk Manager", "Strategy Optimiser"]);
    expect(agentById("marketing-advisor")?.href).toBe("/agents/marketing-advisor");
    expect(existsSync(path.join(appDir, "agents", "page.tsx"))).toBe(true);
    expect(existsSync(path.join(appDir, "risk", "page.tsx"))).toBe(true);
  });

  it("agent descriptions never claim autonomy, optimisation or reinforcement learning", () => {
    const text = AGENTS.map((a) => `${a.purpose} ${a.uses} ${a.status} ${a.scope}`).join(" ");
    expect(text).not.toMatch(/reinforcement|autonomous(ly)?\b(?! coordinator)|self-learning|guarantee/i);
    expect(AGENTS.every((a) => a.scope.length > 40 && a.status.length > 10)).toBe(true);
  });

  it("highlights exactly one entry, preferring the most specific route", () => {
    // deep links and integrated advanced tools highlight their parent category
    expect(activeHref("/data/preprocessing")).toBe("/data/preprocessing");
    expect(activeHref("/data")).toBe("/data");
    expect(activeHref("/data/quality")).toBe("/data/preprocessing");
    expect(activeHref("/agents/marketing-advisor")).toBe("/agents/marketing-advisor");
    expect(activeHref("/decision")).toBe("/decisions");
    expect(activeHref("/counterfactual")).toBe("/simulation");
    expect(activeHref("/causal")).toBe("/simulation");
    expect(activeHref("/causal-graph")).toBe("/simulation");
    expect(activeHref("/outcomes")).toBe("/outcomes");
    expect(activeHref("/research")).toBeNull();
  });

  it("organizes user navigation around the restored core categories", () => {
    const headings = NAV_GROUPS.map((g) => g.heading).filter(Boolean);
    expect(headings).toEqual([
      "Data & Datasets",
      "Business Intelligence",
      "Multi-Agent Intelligence",
      "Decision Intelligence",
      "Business Monitoring",
      "Business Configuration",
    ]);
    const labels = NAV_GROUPS.flatMap((g) => g.items.map((i) => i.label));
    expect(labels).toContain("Dashboard");
    expect(labels).toContain("Dataset Library");
    expect(labels).toContain("Upload Dataset");
    expect(labels).toContain("Data Preprocessing");
    expect(labels).not.toContain("Data Quality");
    expect(labels).toContain("Business Assistant");
    expect(labels).toContain("Business Analytics");
    expect(labels).toContain("Performance Monitoring");
    expect(labels).toContain("Business Forecasts");
    expect(labels).toContain("Customer Insights");
    expect(labels).not.toContain("Agent Workspace");
    expect(labels).toContain("Business Analyst");
    expect(labels).toContain("Financial Advisor");
    expect(labels).toContain("Marketing Advisor");
    expect(labels).toContain("Risk Manager");
    expect(labels).toContain("Strategy Optimiser");
    expect(labels).toContain("Multi-Agent Debate");
    expect(labels).not.toContain("Causal AI Engine");
    expect(labels).toContain("Scenario Analysis");
    expect(labels).toContain("Strategy Comparison");
    expect(labels).toContain("Decision Explanations");
    expect(labels).toContain("Recommendations & Decisions");
    expect(labels).toContain("Smart Alerts");
    expect(labels).toContain("Business Health");
    expect(labels).toContain("Reports");
    expect(labels).toContain("Decision History");
    expect(labels).toContain("Decision Outcomes");
    expect(labels).toContain("Business Profile");
    expect(labels).toContain("Goals & KPIs");
  });
});
