import type { DataType } from "@/lib/api";

/**
 * The complete list of things a business owner can do in DecisionGPT, taken from what the
 * application actually supports (each entry maps to a real page backed by a real API).
 * Navigation, the Home page, Help and the "which data feeds what" hints all read from here,
 * so a capability can't appear in one place and be missing in another.
 */
export interface Feature {
  id: string;
  /** Plain-language name. */
  title: string;
  icon: string;
  href: string;
  /** One sentence: what it does for you. */
  summary: string;
  /** What it needs from you, in plain words. */
  needs: string;
  /** What you get back. */
  gives: string;
  /** Label on the button that opens it. */
  cta: string;
  /** Which kinds of data it reads. */
  uses: DataType[];
  /** Name of the matching entry in the server's data-readiness check, if there is one. */
  readiness?: string;
}

export const FEATURES: Feature[] = [
  {
    id: "analytics",
    title: "Business Analytics",
    icon: "📊",
    href: "/analytics",
    summary: "See how your business is doing — totals, trends, best sellers and what changed.",
    needs: "Your sales (products, customers, marketing and stock make it richer).",
    gives: "Key numbers, a sales trend and a plain-language summary.",
    cta: "See my business",
    uses: ["sales", "products", "customers", "marketing_campaigns", "inventory"],
    readiness: "Sales analysis",
  },
  {
    id: "forecast",
    title: "Forecasting",
    icon: "📈",
    href: "/forecast",
    summary: "See what your future sales may look like over the coming weeks.",
    needs: "A few weeks of dated sales (at least 35 days).",
    gives: "An expected number of units sold, a chart and an expected range.",
    cta: "Start a forecast",
    uses: ["sales", "marketing_campaigns"],
    readiness: "Demand / sales forecasting",
  },
  {
    id: "customers",
    title: "Customers",
    icon: "👥",
    href: "/customers",
    summary: "Understand your customers and find the ones who may be about to stop buying.",
    needs: "Customer records with first and last purchase dates (at least 30 customers).",
    gives: "How many customers may be at risk, and a list to follow up with.",
    cta: "Look at my customers",
    uses: ["customers"],
    readiness: "Churn / retention analysis",
  },
  {
    id: "decisions",
    title: "Business Decisions",
    icon: "💡",
    href: "/decisions",
    summary: "Tell us your goal. DecisionGPT suggests possible pricing, marketing or stock actions and ranks them.",
    needs: "Your sales and, ideally, product costs.",
    gives: "A ranked list of suggested actions, with the risks and the reasons.",
    cta: "Get suggestions",
    uses: ["sales", "products", "marketing_campaigns", "inventory"],
    readiness: "Pricing simulation",
  },
  {
    id: "whatif",
    title: "What-If Tester",
    icon: "🧪",
    href: "/simulation",
    summary: "Try a change — a price, a marketing budget, a stock level — and see what may happen.",
    needs: "Your sales.",
    gives: "The expected effect on sales and revenue, with the risks.",
    cta: "Try a what-if",
    uses: ["sales", "products", "marketing_campaigns", "inventory"],
    readiness: "Pricing simulation",
  },
  {
    id: "causes",
    title: "What Affects What",
    icon: "🔗",
    href: "/causal-graph",
    summary: "See how things like price, marketing and stock are linked in your business — and how well your data backs each link.",
    needs: "Your business data — the longer the history, the stronger the evidence.",
    gives: "A map of cause-and-effect links, each labelled by how well it is supported.",
    cta: "See the links",
    uses: ["sales", "products", "marketing_campaigns", "inventory"],
  },
  {
    id: "chat",
    title: "Chat with Your Data",
    icon: "💬",
    href: "/chat",
    summary: "Ask questions about your business in everyday language.",
    needs: "Any of your data.",
    gives: "An answer in plain words, what it is based on, and the numbers behind it.",
    cta: "Ask a question",
    uses: ["sales", "products", "customers", "marketing_campaigns", "inventory"],
  },
  {
    id: "reports",
    title: "Saved Answers",
    icon: "🗂️",
    href: "/reports/answers",
    summary: "Find the answers and recommendations you got before.",
    needs: "Nothing — it fills up as you use DecisionGPT.",
    gives: "Your earlier answers and decisions, ready to open again.",
    cta: "Open saved answers",
    uses: [],
  },
];

export const featureById = (id: string): Feature => {
  const f = FEATURES.find((x) => x.id === id);
  if (!f) throw new Error(`Unknown feature ${id}`);
  return f;
};

/** Which parts of DecisionGPT can use a given kind of data (only real, supported combinations). */
export function featuresUsing(type: DataType): Feature[] {
  return FEATURES.filter((f) => f.uses.includes(type));
}

/** The "What are you trying to do?" helper. Every choice goes to a real feature. */
export const INTENTS: { label: string; featureId: string }[] = [
  { label: "I want to understand my business", featureId: "analytics" },
  { label: "I want to predict future sales", featureId: "forecast" },
  { label: "I want to understand my customers", featureId: "customers" },
  { label: "I need help making a decision", featureId: "decisions" },
  { label: "I want to ask a question", featureId: "chat" },
  { label: "I want to find an earlier answer", featureId: "reports" },
];

/** What each kind of data is called to a person ("Sales data"), matching the categories the app really supports. */
export const DATA_GROUP_NAME: Record<DataType, string> = {
  sales: "Sales data",
  customers: "Customer data",
  products: "Product data",
  inventory: "Stock data",
  marketing_campaigns: "Marketing data",
  finance: "Money & accounts data",
};

// ------------------------------------------------------------------------------------------------
// AI Agents (architecture group "Multi-Agent Decision").
//
// Honest scope: the backend has real, rule-based Business Analyst / Financial Advisor / Risk Manager
// evaluations that run inside a recommendation analysis (and a Strategy Optimiser that ranks candidate
// actions). There is NO Marketing Advisor agent in the backend and NO autonomous coordinator. Each page
// therefore shows real stored results and real analyses of the owner's data, and says plainly what it is.
// ------------------------------------------------------------------------------------------------
export type AgentId = "business-analyst" | "financial-advisor" | "marketing-advisor" | "risk-manager" | "strategy-optimiser";

export interface Agent {
  id: AgentId;
  name: string;
  icon: string;
  href: string;
  /** One sentence: what it is for. */
  purpose: string;
  /** What data or capabilities it reads. */
  uses: string;
  /** Its real implementation status, in plain words. */
  status: string;
  /** Exactly what it does and does not do. */
  scope: string;
  /** A question that opens AI Business Chat with the words filled in. */
  question: string;
  /** Key of this agent's stored review inside a recommendation (backend agent_reviews), if one exists. */
  reviewKey?: "business_analyst" | "financial_advisor" | "risk_manager";
}

export const AGENTS: Agent[] = [
  {
    id: "business-analyst",
    name: "Business Analyst",
    icon: "📊",
    href: "/agents/business-analyst",
    purpose: "Explains how your sales are doing and what changed, using only your records.",
    uses: "Your sales, products and customers.",
    status: "Working — reads your analytics and your latest recommendation review",
    scope:
      "It shows the same calculations as Business Analytics, plus the Business Analyst's review from your latest recommendation (a rule-based check of expected sales effects). It is not a separate AI model and it does not explain causes.",
    question: "What is improving and what is getting worse?",
    reviewKey: "business_analyst",
  },
  {
    id: "financial-advisor",
    name: "Financial Advisor",
    icon: "💰",
    href: "/agents/financial-advisor",
    purpose: "Looks at revenue, profit and spending — only where your data allows it.",
    uses: "Your sales, product costs and marketing spend.",
    status: "Partly available — profit needs product costs; no cash-flow forecast",
    scope:
      "It reports profit only when product costs are recorded and shows the Financial Advisor's review from your latest recommendation. Cash-flow forecasting is not available, and nothing here is financial advice.",
    question: "Why did my revenue fall?",
    reviewKey: "financial_advisor",
  },
  {
    id: "marketing-advisor",
    name: "Marketing Advisor",
    icon: "📣",
    href: "/agents/marketing-advisor",
    purpose: "Compares your marketing channels and suggests what to look into, with the evidence.",
    uses: "Your marketing campaigns (spend, and results where recorded) and sales.",
    status: "Working — an evidence view of your marketing records",
    scope:
      "It compares channels using your recorded spend and results, and links to the What-If Tester for budget changes. There is no separate marketing AI model behind it, and it cannot say whether more spend would give the same return.",
    question: "Should I increase my marketing spend?",
  },
  {
    id: "risk-manager",
    name: "Risk Manager",
    icon: "🛡️",
    href: "/agents/risk-manager",
    purpose: "Points out gaps and risks in your data and stock, and shows the evidence for each.",
    uses: "Your data coverage, stock levels and customer records.",
    status: "Working — checks your data and stock; customer risk on request",
    scope:
      "It lists missing data, low stock and out-of-date records it can actually see, plus the Risk Manager's review from your latest recommendation. Customer-leaving risk is an estimate from a prediction model, run only when you ask.",
    question: "Which customers are likely to stop buying?",
    reviewKey: "risk_manager",
  },
  {
    id: "strategy-optimiser",
    name: "Strategy Optimiser",
    icon: "🎯",
    href: "/agents/strategy-optimiser",
    purpose: "Compares candidate actions for a goal and shows the trade-offs. You decide.",
    uses: "Your goals and the what-if simulation of your sales.",
    status: "Working — through Business Decisions; suggestions, not automatic actions",
    scope:
      "It ranks candidate pricing, marketing and stock actions by simulating them on your data, and shows the risks reviewers raised. Its score is an internal ranking, not a probability that an action will work, and it never changes anything by itself.",
    question: "What should I focus on to improve my business?",
  },
];

export const agentById = (id: string): Agent | undefined => AGENTS.find((a) => a.id === id);

// ------------------------------------------------------------------------------------------------
// Sidebar navigation, grouped by what the owner is trying to do. Every entry is a real, working page.
// ------------------------------------------------------------------------------------------------
export interface NavEntry {
  href: string;
  label: string;
  icon: string;
  /** Other routes that belong to this entry (so it stays highlighted on them). */
  alsoActive?: string[];
}
export interface NavGroup {
  heading?: string;
  items: NavEntry[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    items: [{ href: "/dashboard", label: "Dashboard", icon: "🏠" }],
  },
  {
    heading: "Data & Datasets",
    items: [
      {
        href: "/data",
        label: "Dataset Library",
        icon: "📚",
        alsoActive: [
          "/data/manual",
          "/data/samples",
          "/data/profile",
          "/data/clean",
          "/data/validate",
          "/data/transform",
          "/data/prepare",
        ],
      },
      { href: "/data/upload", label: "Upload Dataset", icon: "📤" },
      { href: "/data/preprocessing", label: "Data Preprocessing", icon: "🧼", alsoActive: ["/data/quality"] },
    ],
  },
  {
    heading: "Business Intelligence",
    items: [
      { href: "/chat", label: "Business Assistant", icon: "💬" },
      { href: "/analytics", label: "Business Analytics", icon: "📊" },
      { href: "/kpis", label: "Performance Monitoring", icon: "🎯" },
      { href: "/forecast", label: "Business Forecasts", icon: "📈" },
      { href: "/customers", label: "Customer Insights", icon: "👥" },
    ],
  },
  {
    heading: "Multi-Agent Intelligence",
    items: [
      ...AGENTS.map((a) => ({ href: a.href, label: a.name, icon: a.icon })),
      { href: "/agents/debate", label: "Multi-Agent Debate", icon: "⚖️" },
    ],
  },
  {
    heading: "Decision Intelligence",
    items: [
      {
        href: "/simulation",
        label: "Scenario Analysis",
        icon: "🧪",
        alsoActive: ["/causal", "/causal-graph", "/counterfactual"],
      },
      { href: "/compare", label: "Strategy Comparison", icon: "🆚" },
      { href: "/explain", label: "Decision Explanations", icon: "💡" },
      { href: "/decisions", label: "Recommendations & Decisions", icon: "✅", alsoActive: ["/decision"] },
    ],
  },
  {
    heading: "Business Monitoring",
    items: [
      { href: "/alerts", label: "Smart Alerts", icon: "🔔" },
      { href: "/health", label: "Business Health", icon: "❤️" },
      { href: "/reports", label: "Reports", icon: "📄", alsoActive: ["/reports/view", "/reports/answers"] },
      { href: "/history", label: "Decision History", icon: "🗂️" },
      { href: "/outcomes", label: "Decision Outcomes", icon: "🏁" },
    ],
  },
  {
    heading: "Business Configuration",
    items: [
      { href: "/business-profile", label: "Business Profile", icon: "🏢" },
      { href: "/goals", label: "Goals & KPIs", icon: "⛳" },
    ],
  },
];

export const NAV_ACCOUNT: NavEntry[] = [
  { href: "/profile", label: "My Profile", icon: "👤" },
  { href: "/settings", label: "Account Settings", icon: "⚙️" },
];

/**
 * Plain-language names for the server's data-readiness checks, in terms of what the product really does.
 * `null` hides a check: those analyses (financial health, regional context) are not implemented, so a "Ready"
 * badge would overstate them.
 */
export const CAPABILITY_LABEL: Record<string, string | null> = {
  "Sales analysis": "Business Analytics",
  "Demand / sales forecasting": "Sales forecast",
  "Pricing simulation": "What-if price and budget tests",
  "Profit analysis": "Profit figures",
  "Customer analytics / segmentation": "Customer insights",
  "Churn / retention analysis": "Customers who may stop buying",
  "Marketing optimization": "Marketing channel comparison",
  "Inventory optimization": "Stock level checks",
  "Financial health analysis": null,
  "Region / industry context conditioning": null,
};

export function capabilityName(feature: string): string | null {
  return feature in CAPABILITY_LABEL ? CAPABILITY_LABEL[feature] : feature;
}
