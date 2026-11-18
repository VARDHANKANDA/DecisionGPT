"use client";

import Link from "next/link";
import { agentById } from "@/lib/features";
import { useBusiness } from "@/lib/business-context";
import { Page, Spinner, btnPrimary } from "@/components/simple";
import { AgentHero } from "@/components/agent-ui";
import { RiskManagerPanels } from "@/components/agent-panels";

export default function RiskAnalysisPage() {
  const agent = agentById("risk-manager");
  const { business, loading } = useBusiness();

  if (loading) return <Page title="Risk Analysis"><Spinner label="Opening your workspace…" /></Page>;
  if (!business) {
    return (
      <Page title="Risk Analysis" subtitle="Evaluate operational vulnerabilities, customer churn risks, and stock gaps.">
        <Link href="/onboarding" className={btnPrimary}>Set up my business first</Link>
      </Page>
    );
  }
  return (
    <Page title="🛡️ Risk Analysis" subtitle="Operational risk assessment, missing data inspection, and customer retention risks." wide>
      <div className="space-y-6">
        {agent ? <AgentHero agent={agent} /> : null}
        <RiskManagerPanels />
      </div>
    </Page>
  );
}
