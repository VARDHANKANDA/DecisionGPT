"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { HeroDashboardVisual } from "@/components/HeroDashboardVisual";

const BUSINESS_CHALLENGES = [
  {
    title: "Fragmented Business Information",
    description:
      "Sales ledgers, inventory counts, and customer databases live in separate silos, obscuring the unified operational picture.",
    metric: "Data Silos",
    metricLabel: "Operating blind spots across departments",
  },
  {
    title: "Unclear Performance Trends",
    description:
      "Aggregated revenue totals often conceal underlying margin deterioration, customer churn, and shifting product demand.",
    metric: "Hidden Velocity",
    metricLabel: "Difficult to isolate product margin shifts",
  },
  {
    title: "Difficulty Forecasting Future Outcomes",
    description:
      "Relying on static spreadsheets or intuitive guesses leads to inventory overstocking, stockouts, or missed sales targets.",
    metric: "Planning Gaps",
    metricLabel: "Manual spreadsheets fail on demand swings",
  },
  {
    title: "Risky Business Decisions",
    description:
      "Major choices involving pricing changes, promotional discounts, or inventory reorders are launched without prior impact simulation.",
    metric: "Capital Risk",
    metricLabel: "Commitments made without what-if validation",
  },
  {
    title: "Lack of Coordination Between Functions",
    description:
      "Finance, sales, operations, and marketing rarely share a synchronized analytical model, resulting in conflicting priorities.",
    metric: "Misaligned Goals",
    metricLabel: "Functional friction delays strategic execution",
  },
];

const PLATFORM_CAPABILITIES = [
  {
    id: "bi",
    title: "Business Intelligence",
    summary: "Understand business performance through analytics, KPIs, and forecasting.",
    detail:
      "Inspect historical sales patterns, category velocities, gross margins, and customer retention metrics derived directly from verified records.",
    href: "/analytics",
    badge: "Core Analytics",
    icon: "📊",
  },
  {
    id: "multi-agent",
    title: "Multi-Agent Intelligence",
    summary:
      "Coordinate specialized AI agents for business analysis, financial guidance, marketing insights, risk assessment, and strategy optimization.",
    detail:
      "Specialized modules review candidate strategies from distinct operational angles to construct an objective, multi-perspective evaluation.",
    href: "/agents",
    badge: "Architecture Core",
    icon: "🤖",
  },
  {
    id: "decision-intelligence",
    title: "Decision Intelligence",
    summary: "Explore scenarios, evaluate alternatives, understand recommendations, and make informed decisions.",
    detail:
      "Simulate what-if changes to product prices, marketing allocations, or stock levels before committing capital, with ranked action choices.",
    href: "/decisions",
    badge: "Simulation & Choice",
    icon: "💡",
  },
  {
    id: "data",
    title: "Data & Datasets",
    summary: "Connect, organize, and prepare business data for analytical workflows.",
    detail:
      "Ingest sales, product catalogs, customer lists, and inventory tables with automated schema profiling, data cleaning, and readiness scoring.",
    href: "/data",
    badge: "Data Governance",
    icon: "🗄️",
  },
  {
    id: "monitoring",
    title: "Business Monitoring",
    summary: "Monitor business performance, alerts, decision history, and outcomes.",
    detail:
      "Track ongoing operational indicators, automated threshold alerts, and auditable decision logs connecting initial plans to actual outcomes.",
    href: "/alerts",
    badge: "Continuous Audit",
    icon: "📈",
  },
];

const AGENT_COLLABORATION = [
  {
    id: "business-analyst",
    role: "Business Analyst",
    icon: "📊",
    focus: "Revenue momentum, sales velocity, product margins, and transaction trends.",
    perspective:
      "Audits transaction logs to establish baselines, isolate high-velocity SKUs, and detect customer purchasing pattern changes.",
    evaluates: "Historical sales growth, category trends, transaction frequency",
  },
  {
    id: "financial-advisor",
    role: "Financial Advisor",
    icon: "💰",
    focus: "Gross margin sustainability, unit costs, and capital allocation trade-offs.",
    perspective:
      "Evaluates whether proposed strategies maintain healthy operating margin thresholds and protects working capital reserves.",
    evaluates: "Gross margin impact, expenditure rebalancing, cost structures",
  },
  {
    id: "marketing-advisor",
    role: "Marketing Advisor",
    icon: "📣",
    focus: "Campaign channel efficiency, customer acquisition, and promotional elasticity.",
    perspective:
      "Compares marketing channel returns from recorded spend and models demand sensitivity to promotional pricing shifts.",
    evaluates: "Channel ROI, promotional lift, customer response dynamics",
  },
  {
    id: "risk-manager",
    role: "Risk Manager",
    icon: "🛡️",
    focus: "Downside exposure, stockout liabilities, data coverage gaps, and churn indicators.",
    perspective:
      "Identifies supply chain delivery risks, low inventory thresholds, customer drop-off risks, and missing data points.",
    evaluates: "Stockout exposure, customer churn likelihood, operational vulnerabilities",
  },
  {
    id: "strategy-optimiser",
    role: "Strategy Optimiser",
    icon: "🎯",
    focus: "Scenario synthesis, trade-off scoring, and ranked decision formulation.",
    perspective:
      "Synthesizes the findings of all advisory agents, tests feasible actions via what-if simulation, and ranks options for executive review.",
    evaluates: "Consensus scoring, action ranking, strategic trade-offs",
  },
];

const WORKFLOW_STEPS = [
  {
    step: "01",
    title: "Connect business datasets",
    description: "Ingest sales ledgers, product catalogs, customer records, and inventory sheets with automated schema validation.",
  },
  {
    step: "02",
    title: "Analyze business performance",
    description: "Profile historical transactions to reveal core revenue patterns, product velocities, and operational margins.",
  },
  {
    step: "03",
    title: "Generate forecasts and insights",
    description: "Apply validated time-series regression models across daily, 14-day, and 28-day decision planning windows.",
  },
  {
    step: "04",
    title: "Collaborate through specialized agents",
    description: "Deploy domain-specific agents to examine performance from analytical, financial, marketing, and risk viewpoints.",
  },
  {
    step: "05",
    title: "Evaluate possible scenarios",
    description: "Simulate candidate pricing, marketing spend, and inventory adjustments in a safe digital sandbox before execution.",
  },
  {
    step: "06",
    title: "Review recommendations and make decisions",
    description: "Inspect ranked, evidence-backed options with transparent trade-offs, log executive decisions, and track real-world results.",
  },
];

const USE_CASES = [
  {
    category: "Financial Planning",
    icon: "💼",
    subtitle: "Protect margins and optimize working capital",
    points: [
      "Simulate the gross margin impact of shifting supplier costs before updating catalog prices.",
      "Reallocate operating budgets toward product categories with proven contribution margins.",
      "Monitor cash runway indicators and operational cost thresholds across multi-month horizons.",
    ],
  },
  {
    category: "Marketing Strategy",
    icon: "🎯",
    subtitle: "Evidence-based channel allocation and promotions",
    points: [
      "Compare recorded sales lift across digital, physical, and referral marketing campaigns.",
      "Test promotional discount depths against historical price elasticity curves to prevent margin erosion.",
      "Identify high-value customer acquisition channels to maximize spend efficiency.",
    ],
  },
  {
    category: "Operational Management",
    icon: "⚙️",
    subtitle: "Calibrate safety stock and eliminate bottlenecks",
    points: [
      "Align inventory reorder thresholds with multi-horizon machine learning demand forecasts.",
      "Identify slow-moving stock batches early to structure controlled inventory liquidation.",
      "Track supplier delivery variances to preempt costly production and fulfillment stockouts.",
    ],
  },
  {
    category: "Customer and Risk Analysis",
    icon: "🛡️",
    subtitle: "Identify churn risks and enforce compliance",
    points: [
      "Pinpoint customer accounts showing decelerating purchase frequency before they churn.",
      "Evaluate commercial credit and payment delays across enterprise client segments.",
      "Audit business record completeness and maintain strict business-scoped tenant isolation.",
    ],
  },
];

const WHY_DECISIONGPT = [
  {
    title: "Unified business intelligence",
    text: "Consolidate historical reporting, predictive time-series models, and strategic recommendations in a single operational platform.",
  },
  {
    title: "Multi-agent collaboration",
    text: "Gain synchronized perspectives across finance, marketing, risk, and operations to eliminate departmental decision silos.",
  },
  {
    title: "Data-driven forecasting",
    text: "Trained machine learning models calibrated on your transaction histories replace guesswork with verifiable multi-horizon projections.",
  },
  {
    title: "Scenario-based evaluation",
    text: "Test strategic decisions inside a risk-free simulation environment to evaluate probable outcomes before committing capital.",
  },
  {
    title: "Explainable recommendations",
    text: "Every suggested action is accompanied by its underlying data sources, mathematical formulas, and agent trade-off considerations.",
  },
  {
    title: "Centralized decision support",
    text: "Maintain an auditable decision history connecting pre-decision expectations with recorded post-implementation outcomes.",
  },
];

const FAQ_ITEMS = [
  {
    q: "What is DecisionGPT?",
    a: "DecisionGPT is an enterprise decision intelligence SaaS platform that brings together business analytics, validated time-series forecasting, multi-agent AI collaboration, and what-if scenario simulation. It is built to help business owners, founders, and managers make evidence-based operational and strategic decisions.",
  },
  {
    q: "Who can use the platform?",
    a: "DecisionGPT is designed for SME founders, business owners, financial controllers, operations managers, commercial leads, and enterprise business teams seeking unified, verifiable decision support across sales, inventory, marketing, and finance.",
  },
  {
    q: "What datasets can be used?",
    a: "The platform ingests standard business records including sales transactions, product catalogs with unit costs, customer purchase histories, inventory stock counts, and marketing campaign spend tables in common spreadsheet and structured formats.",
  },
  {
    q: "How does multi-agent intelligence work?",
    a: "DecisionGPT coordinates specialized algorithmic agents (Business Analyst, Financial Advisor, Marketing Advisor, Risk Manager, and Strategy Optimiser). Each agent evaluates your business state through its specialized lens, identifying trade-offs and risks. The Strategy Optimiser coordinates these perspectives into a unified, ranked recommendation.",
  },
  {
    q: "What business decisions can it support?",
    a: "DecisionGPT supports product pricing adjustments, promotional campaign strategies, marketing budget allocations, inventory reorder timing, slow-moving stock liquidation, and customer retention initiatives.",
  },
  {
    q: "How are recommendations explained?",
    a: "Every recommendation includes a complete, deterministic audit trace: the exact data records used, the calculation methodology, the individual agent reviews, the projected financial impact, and the identified downside risks.",
  },
  {
    q: "Does DecisionGPT replace human decision-makers?",
    a: "No. DecisionGPT is an advisory decision-support system. It simulates outcomes, surfaces risks, and ranks viable alternatives, while strategic judgment and final execution remain entirely in the hands of business leadership.",
  },
];

export default function Home() {
  const { user, isAdmin, loading } = useAuth();
  const router = useRouter();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeAgentTab, setActiveAgentTab] = useState(0);

  // A signed-in visitor never needs the landing page — redirect to workspace.
  useEffect(() => {
    if (loading || !user) return;
    router.replace(isAdmin ? "/research" : "/dashboard");
  }, [loading, user, isAdmin, router]);

  if (!loading && user) return null;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 antialiased selection:bg-blue-100 selection:text-blue-900">
      {/* 3. NAVIGATION BAR */}
      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/95 px-6 py-3.5 backdrop-blur-md transition-all">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          {/* Brand Logo */}
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white font-bold text-base shadow-sm ring-1 ring-slate-900/10">
              D
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-slate-900">DecisionGPT</span>
            </div>
          </Link>

          {/* Desktop Navigation Links */}
          <nav aria-label="Main Navigation" className="hidden lg:flex items-center gap-7 text-sm font-medium text-slate-600">
            <Link href="/" className="transition hover:text-slate-900">Home</Link>
            <a href="#platform" className="transition hover:text-slate-900">Platform</a>
            <a href="#multi-agent" className="transition hover:text-slate-900">Multi-Agent Intelligence</a>
            <a href="#solutions" className="transition hover:text-slate-900">Solutions</a>
            <a href="#how-it-works" className="transition hover:text-slate-900">How It Works</a>
            <a href="#about" className="transition hover:text-slate-900">About</a>
            <a href="#contact" className="transition hover:text-slate-900">Contact</a>
          </nav>

          {/* Action CTAs */}
          <div className="hidden lg:flex items-center gap-4 text-sm font-medium">
            <Link
              href="/login"
              className="text-slate-600 transition hover:text-slate-900 px-3 py-1.5 focus-visible:outline-2 focus-visible:outline-blue-600 rounded-lg"
            >
              Sign In
            </Link>
            <Link
              href="/login?mode=register"
              className="inline-flex items-center justify-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
            >
              Get Started
            </Link>
          </div>

          {/* Mobile Hamburger Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="inline-flex items-center justify-center rounded-lg border border-slate-200 p-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 lg:hidden focus-visible:outline-2 focus-visible:outline-blue-600"
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              {mobileMenuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="mt-3 border-t border-slate-200 pt-3 lg:hidden">
            <nav className="flex flex-col gap-2 pb-3 text-sm font-medium text-slate-600">
              <Link
                href="/"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg px-3 py-2 hover:bg-slate-100 hover:text-slate-900"
              >
                Home
              </Link>
              <a
                href="#platform"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg px-3 py-2 hover:bg-slate-100 hover:text-slate-900"
              >
                Platform
              </a>
              <a
                href="#multi-agent"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg px-3 py-2 hover:bg-slate-100 hover:text-slate-900"
              >
                Multi-Agent Intelligence
              </a>
              <a
                href="#solutions"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg px-3 py-2 hover:bg-slate-100 hover:text-slate-900"
              >
                Solutions
              </a>
              <a
                href="#how-it-works"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg px-3 py-2 hover:bg-slate-100 hover:text-slate-900"
              >
                How It Works
              </a>
              <a
                href="#about"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg px-3 py-2 hover:bg-slate-100 hover:text-slate-900"
              >
                About
              </a>
              <a
                href="#contact"
                onClick={() => setMobileMenuOpen(false)}
                className="rounded-lg px-3 py-2 hover:bg-slate-100 hover:text-slate-900"
              >
                Contact
              </a>
              <div className="mt-2 flex flex-col gap-2 border-t border-slate-100 pt-3">
                <Link
                  href="/login"
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-center text-slate-700 hover:bg-slate-100"
                >
                  Sign In
                </Link>
                <Link
                  href="/login?mode=register"
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded-lg bg-slate-900 px-3 py-2 text-center font-semibold text-white hover:bg-slate-800"
                >
                  Get Started
                </Link>
              </div>
            </nav>
          </div>
        )}
      </header>

      <main>
        {/* SECTION 1: HERO */}
        <section className="relative overflow-hidden border-b border-slate-200/80 bg-gradient-to-b from-white via-slate-50/50 to-slate-100/60 py-16 sm:py-24 lg:py-28">
          <div className="mx-auto max-w-7xl px-6">
            <div className="grid items-center gap-12 lg:grid-cols-12 lg:gap-8">
              {/* Left Column: Headline and CTAs */}
              <div className="lg:col-span-6 xl:col-span-6">
                <div className="inline-flex items-center gap-2 rounded-full border border-blue-200/80 bg-blue-50/90 px-3.5 py-1 text-xs font-semibold text-blue-800 shadow-xs">
                  <span className="h-2 w-2 rounded-full bg-blue-600" />
                  Verified Business Intelligence &amp; Multi-Agent Deliberation
                </div>

                <h1 className="mt-5 text-4xl font-extrabold tracking-tight text-slate-900 sm:text-5xl lg:text-5xl xl:text-6xl sm:leading-[1.12]">
                  Turn Business Data Into Better Decisions.
                </h1>

                <p className="mt-6 text-lg leading-relaxed text-slate-600 sm:text-xl">
                  DecisionGPT brings business analytics, forecasting, multi-agent intelligence, and decision support together to help businesses understand performance, evaluate opportunities, and make informed decisions.
                </p>

                <div className="mt-8 flex flex-wrap items-center gap-4">
                  <Link
                    href="/login?mode=register"
                    className="inline-flex items-center justify-center rounded-lg bg-slate-900 px-6 py-3.5 text-base font-semibold text-white shadow-md transition hover:bg-slate-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                  >
                    Get Started
                  </Link>
                  <a
                    href="#platform"
                    className="inline-flex items-center justify-center rounded-lg border border-slate-300 bg-white px-6 py-3.5 text-base font-semibold text-slate-700 shadow-xs transition hover:bg-slate-50 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                  >
                    Explore the Platform
                  </a>
                </div>

                {/* Trust Badges */}
                <div className="mt-10 grid grid-cols-2 gap-4 border-t border-slate-200/80 pt-6 text-xs text-slate-500 sm:grid-cols-3">
                  <div>
                    <p className="font-bold text-slate-900">Deterministic Engine</p>
                    <p className="mt-0.5">Calculated from verified rows</p>
                  </div>
                  <div>
                    <p className="font-bold text-slate-900">Multi-Agent Review</p>
                    <p className="mt-0.5">5 specialized domains</p>
                  </div>
                  <div>
                    <p className="font-bold text-slate-900">Tenant Isolation</p>
                    <p className="mt-0.5">Strict business_id scoping</p>
                  </div>
                </div>
              </div>

              {/* Right Column: Hero Dashboard Visual */}
              <div className="lg:col-span-6 xl:col-span-6">
                <HeroDashboardVisual />
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 2: BUSINESS CHALLENGES */}
        <section id="challenges" className="border-b border-slate-200/80 bg-white py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Operating Realities</span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                The Critical Challenges in Business Decision-Making
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
                Modern business leaders face mounting complexity across sales, inventory, finance, and marketing. Isolated data and gut-feel projections lead to avoidable strategic risks.
              </p>
            </div>

            <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {BUSINESS_CHALLENGES.map((challenge, idx) => (
                <div
                  key={challenge.title}
                  className={`rounded-2xl border border-slate-200 bg-slate-50/50 p-6 shadow-xs transition hover:border-slate-300 hover:bg-white ${idx === 4 ? "sm:col-span-2 lg:col-span-1" : ""
                    }`}
                >
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-3">
                    <span className="text-xs font-bold text-slate-400 font-mono">0{idx + 1}</span>
                    <span className="rounded bg-slate-200/60 px-2 py-0.5 text-[10px] font-bold text-slate-700 uppercase">
                      {challenge.metric}
                    </span>
                  </div>
                  <h3 className="mt-4 text-base font-bold text-slate-900">{challenge.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{challenge.description}</p>
                  <p className="mt-4 text-xs font-medium text-slate-500 border-t border-slate-100 pt-3">
                    Impact: {challenge.metricLabel}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* SECTION 3: DECISIONGPT PLATFORM */}
        <section id="platform" className="border-b border-slate-200/80 bg-slate-50/60 py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Platform Capabilities</span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                One Unified System for Business Decision Support
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
                Consolidate sales records, customer history, and stock figures into verifiable answers, automated forecasts, and coordinated decision support.
              </p>
            </div>

            <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {PLATFORM_CAPABILITIES.map((cap) => (
                <div
                  key={cap.id}
                  className="flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-xs transition hover:border-blue-300 hover:shadow-md"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-xl" aria-hidden="true">
                        {cap.icon}
                      </span>
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">
                        {cap.badge}
                      </span>
                    </div>
                    <h3 className="mt-5 text-lg font-bold text-slate-900">{cap.title}</h3>
                    <p className="mt-2 text-sm font-medium text-blue-700">{cap.summary}</p>
                    <p className="mt-3 text-xs leading-relaxed text-slate-500">{cap.detail}</p>
                  </div>

                  <div className="mt-6 border-t border-slate-100 pt-4">
                    <Link
                      href={cap.href}
                      className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-900 hover:text-blue-700 transition"
                    >
                      View Platform Capability
                      <span aria-hidden="true">→</span>
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* SECTION 4: MULTI-AGENT INTELLIGENCE (PROMINENT FEATURE) */}
        <section id="agents" className="border-b border-slate-200/80 bg-white py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Multi-Agent Intelligence
              </span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                Collaborative Intelligence Across Specialized Business Agents
              </h2>
              <p className="mx-auto mt-4 max-w-3xl text-base text-slate-600 sm:text-lg">
                Rather than relying on a single generic model, DecisionGPT orchestrates specialized, deterministic advisory agents. Each agent evaluates your records from its domain of expertise to produce a coordinated, auditable consensus.
              </p>
            </div>

            {/* Interactive Agent Matrix */}
            <div className="mt-12 grid gap-8 lg:grid-cols-12">
              {/* Agent Selector List */}
              <div className="lg:col-span-5 flex flex-col gap-2">
                {AGENT_COLLABORATION.map((agent, index) => (
                  <button
                    key={agent.id}
                    onClick={() => setActiveAgentTab(index)}
                    className={`flex items-start gap-4 rounded-xl border p-4 text-left transition ${activeAgentTab === index
                      ? "border-blue-600 bg-blue-50/50 shadow-xs"
                      : "border-slate-200 bg-slate-50/40 hover:bg-slate-100/70"
                      }`}
                  >
                    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white border border-slate-200 text-lg shadow-xs">
                      {agent.icon}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-bold text-slate-900">{agent.role}</span>
                        {activeAgentTab === index && (
                          <span className="rounded bg-blue-600 px-2 py-0.5 text-[10px] font-semibold text-white">
                            Active Lens
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-xs text-slate-500 line-clamp-1">{agent.focus}</p>
                    </div>
                  </button>
                ))}
              </div>

              {/* Agent Active Detail Card */}
              <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-slate-50/70 p-6 sm:p-8 flex flex-col justify-between shadow-xs">
                <div>
                  <div className="flex items-center justify-between border-b border-slate-200 pb-4">
                    <div className="flex items-center gap-3">
                      <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-white border border-slate-200 text-2xl shadow-xs">
                        {AGENT_COLLABORATION[activeAgentTab].icon}
                      </span>
                      <div>
                        <h3 className="text-xl font-bold text-slate-900">
                          {AGENT_COLLABORATION[activeAgentTab].role}
                        </h3>
                        <p className="text-xs text-blue-700 font-medium">Domain Specialist Lens</p>
                      </div>
                    </div>
                    <span className="rounded-full bg-slate-200/80 px-3 py-1 text-xs font-semibold text-slate-700">
                      Evaluated Deterministically
                    </span>
                  </div>

                  <div className="mt-6 space-y-4">
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Core Domain Focus</h4>
                      <p className="mt-1 text-sm font-medium text-slate-900">
                        {AGENT_COLLABORATION[activeAgentTab].focus}
                      </p>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Analytical Perspective</h4>
                      <p className="mt-1 text-sm leading-relaxed text-slate-600">
                        {AGENT_COLLABORATION[activeAgentTab].perspective}
                      </p>
                    </div>

                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">Metrics Evaluated</h4>
                      <div className="mt-1 rounded-lg bg-white border border-slate-200 p-3 text-xs font-mono text-slate-700">
                        {AGENT_COLLABORATION[activeAgentTab].evaluates}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-8 rounded-xl border border-blue-200/80 bg-blue-50/70 p-4 text-xs text-blue-900">
                  <p className="font-semibold text-blue-950">Architectural Note on Multi-Agent Reviews:</p>
                  <p className="mt-1 text-slate-600">
                    Agents in DecisionGPT are structured, rule-based analytical evaluators operating directly on verified ledger rows. They are not independent human experts, and their outputs are designed to provide transparent, multi-angle evidence for human management decisions.
                  </p>
                </div>
              </div>
            </div>

            {/* Workflow Demonstration Bar */}
            <div className="mt-12 rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-800">
                Coordinated Decision Synthesis Flow
              </h3>
              <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-4 text-xs">
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
                  <span className="font-bold text-slate-900 block">Step A: Ingest &amp; Validate</span>
                  <p className="mt-1 text-slate-500">Records profiled and scoped to authenticated business tenant.</p>
                </div>
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
                  <span className="font-bold text-slate-900 block">Step B: Parallel Audit</span>
                  <p className="mt-1 text-slate-500">Agents inspect velocity, costs, channel lift, and downside risk.</p>
                </div>
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3.5">
                  <span className="font-bold text-slate-900 block">Step C: Trade-off Scoring</span>
                  <p className="mt-1 text-slate-500">Strategy Optimiser evaluates simulations against business goals.</p>
                </div>
                <div className="rounded-xl bg-blue-50 border border-blue-200 p-3.5">
                  <span className="font-bold text-blue-900 block">Step D: Ranked Action</span>
                  <p className="mt-1 text-blue-700">Clear recommendation presented with risks and calculation audit.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* SECTION 5: BUSINESS ANALYTICS AND FORECASTING */}
        <section id="analytics" className="border-b border-slate-200/80 bg-slate-50/60 py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">
                Analytics &amp; Forecasting
              </span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                Verifiable Business Analytics and Multi-Horizon Forecasting
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
                Inspect historical trends and forecast future demand without mathematical assumptions or invented numbers.
              </p>
            </div>

            <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {/* Card 1: Revenue Trends & KPIs */}
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h3 className="text-base font-bold text-slate-900">Business KPIs &amp; Revenue Trends</h3>
                  <span className="rounded bg-emerald-50 text-emerald-700 px-2 py-0.5 text-[10px] font-semibold">
                    Deterministic
                  </span>
                </div>
                <div className="mt-4 space-y-3">
                  <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                    <span className="text-xs text-slate-500">Sample Metric — Net Sales</span>
                    <p className="text-xl font-bold text-slate-900">₹28,45,200</p>
                    <p className="text-[11px] text-emerald-600 font-medium">1,420 transactions recorded</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                    <span className="text-xs text-slate-500">Operating Gross Margin</span>
                    <p className="text-xl font-bold text-slate-900">38.6%</p>
                    <p className="text-[11px] text-slate-500">Calculated from recorded SKU unit costs</p>
                  </div>
                </div>
                <p className="mt-4 text-xs text-slate-500 border-t border-slate-100 pt-3">
                  Every figure is calculated via exact SQL aggregations over your scoped business records.
                </p>
              </div>

              {/* Card 2: Multi-Horizon Forecasting */}
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h3 className="text-base font-bold text-slate-900">Multi-Horizon Demand Forecasts</h3>
                  <span className="rounded bg-indigo-50 text-indigo-700 px-2 py-0.5 text-[10px] font-semibold">
                    Regression Models
                  </span>
                </div>
                <div className="mt-4 space-y-2 text-xs">
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
                    <div className="flex justify-between font-semibold text-slate-900">
                      <span>Daily Demand</span>
                      <span className="text-blue-700">480 units/day</span>
                    </div>
                    <span className="text-[10px] text-slate-400">HistGradientBoosting • MAE 13.85 units</span>
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
                    <div className="flex justify-between font-semibold text-slate-900">
                      <span>14-Day Cumulative</span>
                      <span className="text-blue-700">6,850 units</span>
                    </div>
                    <span className="text-[10px] text-slate-400">Random Forest Ensemble • MAE 58.64 units</span>
                  </div>
                  <div className="rounded-lg border border-slate-100 bg-slate-50/60 p-2.5">
                    <div className="flex justify-between font-semibold text-slate-900">
                      <span>28-Day Cumulative</span>
                      <span className="text-blue-700">13,920 units</span>
                    </div>
                    <span className="text-[10px] text-slate-400">XGBoost Regressor • MAE 55.70 units</span>
                  </div>
                </div>
                <p className="mt-4 text-xs text-slate-500 border-t border-slate-100 pt-3">
                  Trained time-series models evaluated across strict historical validation splits.
                </p>
              </div>

              {/* Card 3: Customer & Operational Risk */}
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs sm:col-span-2 lg:col-span-1">
                <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                  <h3 className="text-base font-bold text-slate-900">Customer &amp; Risk Indicators</h3>
                  <span className="rounded bg-amber-50 text-amber-700 px-2 py-0.5 text-[10px] font-semibold">
                    Risk Calibration
                  </span>
                </div>
                <div className="mt-4 space-y-3">
                  <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                    <span className="text-xs text-slate-500">Customer Churn Exposure</span>
                    <p className="text-xl font-bold text-slate-900">3.8%</p>
                    <p className="text-[11px] text-slate-500">12 accounts showing recency drop-off</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3 border border-slate-100">
                    <span className="text-xs text-slate-500">Inventory Turnover Index</span>
                    <p className="text-xl font-bold text-slate-900">4.8x / quarter</p>
                    <p className="text-[11px] text-slate-500">Zero critical stockouts forecasted</p>
                  </div>
                </div>
                <p className="mt-4 text-xs text-slate-500 border-t border-slate-100 pt-3">
                  Early detection signals protect cash flow before customer attrition or stock depletion occurs.
                </p>
              </div>
            </div>

            {/* Illustrative data callout */}
            <p className="mt-6 text-center text-xs text-slate-400">
              * Displayed metrics reflect sample platform visualizations. In production, every figure is calibrated exclusively on your authenticated business records.
            </p>
          </div>
        </section>

        {/* SECTION 6: FROM DATA TO DECISIONS */}
        <section id="how-it-works" className="border-b border-slate-200/80 bg-white py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Methodology</span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                From Data to Decisions
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
                A transparent, six-stage workflow connecting your business records to verified insights and executed strategy.
              </p>
            </div>

            <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {WORKFLOW_STEPS.map((s) => (
                <div key={s.step} className="rounded-2xl border border-slate-200 bg-slate-50/50 p-6 shadow-xs hover:bg-white transition">
                  <div className="flex items-center gap-3">
                    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-xs font-bold text-white">
                      {s.step}
                    </span>
                    <h3 className="text-base font-bold text-slate-900">{s.title}</h3>
                  </div>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">{s.description}</p>
                </div>
              ))}
            </div>

            <div className="mt-12 rounded-2xl border border-slate-200 bg-slate-50 p-6 sm:p-8">
              <h3 className="text-base font-bold text-slate-900">Strict AI Classification Boundary</h3>
              <p className="mt-2 text-sm text-slate-600 leading-relaxed">
                DecisionGPT uses OpenAI solely to classify natural language queries into a closed, typed JSON schema. The external AI model never calculates numbers, never accesses raw customer identities, and never generates financial outputs. The deterministic calculation engine computes results directly from your business records.
              </p>
            </div>
          </div>
        </section>

        {/* SECTION 7: BUSINESS USE CASES */}
        <section id="solutions" className="border-b border-slate-200/80 bg-slate-50/60 py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Business Solutions</span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                Business Use Cases
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
                Tailored decision support for business owners, finance heads, and operational managers navigating real-world commercial trade-offs.
              </p>
            </div>

            <div className="mt-12 grid gap-6 sm:grid-cols-2">
              {USE_CASES.map((uc) => (
                <div key={uc.category} className="rounded-2xl border border-slate-200 bg-white p-7 shadow-xs">
                  <div className="flex items-center gap-3">
                    <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-xl border border-blue-100" aria-hidden="true">
                      {uc.icon}
                    </span>
                    <div>
                      <h3 className="text-lg font-bold text-slate-900">{uc.category}</h3>
                      <p className="text-xs text-blue-700 font-medium">{uc.subtitle}</p>
                    </div>
                  </div>

                  <ul className="mt-6 space-y-3 text-sm text-slate-600">
                    {uc.points.map((pt, i) => (
                      <li key={i} className="flex items-start gap-2.5">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600" />
                        <span>{pt}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* SECTION 8: WHY DECISIONGPT */}
        <section id="about" className="border-b border-slate-200/80 bg-white py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">Why DecisionGPT</span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                Engineered for Rigor, Transparency, and Executive Trust
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
                Six architectural commitments that set DecisionGPT apart from generic startup dashboards.
              </p>
            </div>

            <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {WHY_DECISIONGPT.map((item) => (
                <div key={item.title} className="rounded-2xl border border-slate-200 bg-slate-50/40 p-6 shadow-xs">
                  <h3 className="text-base font-bold text-slate-900">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-600">{item.text}</p>
                </div>
              ))}
            </div>

            {/* Research integrity note */}
            <div className="mt-10 rounded-2xl border border-slate-200 bg-slate-100/70 p-6 text-xs text-slate-600">
              <p className="font-semibold text-slate-900">Commitment to Research Integrity:</p>
              <p className="mt-1">
                DecisionGPT avoids unverified marketing claims. The platform makes no promise of specific financial returns or automated business growth. All scenario projections represent probabilistic models and simulation hypotheses built to inform executive decisions.
              </p>
            </div>
          </div>
        </section>

        {/* SECTION 9: FAQ */}
        <section id="faq" className="border-b border-slate-200/80 bg-slate-50/60 py-16 sm:py-24">
          <div className="mx-auto max-w-7xl px-6">
            <div className="text-center">
              <span className="text-xs font-bold uppercase tracking-wider text-blue-700">FAQ</span>
              <h2 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
                Frequently Asked Questions
              </h2>
              <p className="mx-auto mt-4 max-w-2xl text-base text-slate-600 sm:text-lg">
                Practical answers to core questions about platform capabilities, data security, and multi-agent architecture.
              </p>
            </div>

            <div className="mt-12 grid gap-6 lg:grid-cols-2">
              {FAQ_ITEMS.map((item, idx) => (
                <div key={idx} className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs">
                  <h3 className="text-base font-bold text-slate-900">{item.q}</h3>
                  <p className="mt-3 text-sm leading-relaxed text-slate-600">{item.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* SECTION 10: FINAL CTA */}
        <section className="bg-slate-900 py-16 text-white sm:py-24">
          <div className="mx-auto max-w-5xl px-6 text-center">
            <h2 className="text-3xl font-extrabold tracking-tight sm:text-4xl lg:text-5xl">
              Bring Clarity to Your Next Business Decision.
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base text-slate-300 sm:text-lg">
              Explore a unified platform for business intelligence, forecasting, and intelligent decision support.
            </p>

            <div className="mt-8 flex flex-wrap justify-center gap-4">
              <Link
                href="/login?mode=register"
                className="inline-flex items-center justify-center rounded-lg bg-blue-600 px-6 py-3.5 text-base font-semibold text-white shadow-md transition hover:bg-blue-500 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-500"
              >
                Get Started
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center justify-center rounded-lg border border-slate-700 bg-slate-800/80 px-6 py-3.5 text-base font-semibold text-slate-200 shadow-xs transition hover:bg-slate-700 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-500"
              >
                Sign In
              </Link>
            </div>
          </div>
        </section>

        {/* SECTION 11: FOOTER */}
        <footer id="contact" className="border-t border-slate-200 bg-white py-12 text-sm text-slate-600 sm:py-16">
          <div className="mx-auto max-w-7xl px-6">
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-5">
              {/* Brand Summary */}
              <div className="lg:col-span-2">
                <Link href="/" className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-900 text-white font-bold text-sm">
                    D
                  </div>
                  <span className="text-base font-bold text-slate-900">DecisionGPT</span>
                </Link>
                <p className="mt-3 text-xs leading-relaxed text-slate-500 max-w-sm">
                  Enterprise business intelligence, validated time-series forecasting, multi-agent evaluation, and scenario analysis for growing companies.
                </p>
                <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
                  <span className="h-2 w-2 rounded-full bg-emerald-500" />
                  <span>Tenant isolation enforced by business_id</span>
                </div>
              </div>

              {/* Column: Platform */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">Platform</h4>
                <ul className="mt-3 space-y-2 text-xs">
                  <li>
                    <Link href="/analytics" className="hover:text-slate-900 transition">Business Analytics</Link>
                  </li>
                  <li>
                    <Link href="/forecast" className="hover:text-slate-900 transition">Sales Forecasting</Link>
                  </li>
                  <li>
                    <Link href="/simulation" className="hover:text-slate-900 transition">Scenario Analysis</Link>
                  </li>
                  <li>
                    <Link href="/agents" className="hover:text-slate-900 transition">Multi-Agent Workspace</Link>
                  </li>
                  <li>
                    <Link href="/data" className="hover:text-slate-900 transition">Data &amp; Datasets</Link>
                  </li>
                </ul>
              </div>

              {/* Column: Solutions */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">Business Solutions</h4>
                <ul className="mt-3 space-y-2 text-xs">
                  <li>
                    <a href="#solutions" className="hover:text-slate-900 transition">Financial Planning</a>
                  </li>
                  <li>
                    <a href="#solutions" className="hover:text-slate-900 transition">Marketing Strategy</a>
                  </li>
                  <li>
                    <a href="#solutions" className="hover:text-slate-900 transition">Operational Management</a>
                  </li>
                  <li>
                    <a href="#solutions" className="hover:text-slate-900 transition">Customer &amp; Risk Analysis</a>
                  </li>
                </ul>
              </div>

              {/* Column: About & Legal */}
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900">About &amp; Governance</h4>
                <ul className="mt-3 space-y-2 text-xs">
                  <li>
                    <a href="#about" className="hover:text-slate-900 transition">About DecisionGPT</a>
                  </li>
                  <li>
                    <a href="mailto:enterprise@decisiongpt.ai" className="hover:text-slate-900 transition">Contact</a>
                  </li>
                  <li>
                    <Link href="/privacy" className="hover:text-slate-900 transition">Privacy Policy</Link>
                  </li>
                  <li>
                    <Link href="/terms" className="hover:text-slate-900 transition">Terms of Service</Link>
                  </li>
                </ul>
              </div>
            </div>

            <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-slate-200/80 pt-8 sm:flex-row text-xs text-slate-400">
              <p>© 2026 DecisionGPT. All rights reserved.</p>
              <p>Deterministic calculations and research integrity guaranteed.</p>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}