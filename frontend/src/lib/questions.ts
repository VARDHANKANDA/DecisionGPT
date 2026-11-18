/** Example questions. Every one maps to a question type the assistant genuinely answers from the user's data. */
export const EXAMPLE_QUESTIONS: { icon: string; topic: string; question: string }[] = [
  { icon: "💰", topic: "Sales", question: "Which products sold the most last month?" },
  { icon: "👥", topic: "Customers", question: "Which customers are likely to stop buying?" },
  { icon: "📈", topic: "Forecasting", question: "What might my sales look like next month?" },
  { icon: "📊", topic: "Business performance", question: "What is improving and what is getting worse?" },
  { icon: "💡", topic: "Decisions", question: "What should I focus on to improve my business?" },
  { icon: "🎯", topic: "How reliable is it?", question: "Show the validation results for my business." },
];

/** Plain-language description of what kind of answer this was (for "Why am I seeing this?"). */
export const INTENT_EXPLANATION: Record<string, string> = {
  evaluation_results:
    "You asked about evaluation results, so DecisionGPT read the evaluations that were actually recorded (for your business, and for the research models if you have research access) and showed their values with what each one means. Nothing was recalculated and no AI model was used for the numbers.",
  top_products: "You asked which products sold the most, so DecisionGPT added up your recent sales for each product.",
  improving_worsening:
    "You asked what is getting better or worse, so DecisionGPT compared your last 30 days of sales with the 30 days before.",
  sales_forecast:
    "You asked about future sales, so DecisionGPT used a prediction model on your past sales to estimate the next 30 days.",
  customer_churn:
    "You asked which customers may stop buying, so DecisionGPT used a prediction model on your customer records.",
  valuable_customers: "You asked about your best customers, so DecisionGPT ranked them by how much each has spent.",
  why_kpi_fell:
    "You asked why a number changed. DecisionGPT can show how much it changed compared with the 30 days before, but it can't tell you what caused the change.",
  price_change_advice: "You asked about changing your price, so DecisionGPT ran a what-if simulation on your data.",
  marketing_change_advice:
    "You asked about marketing spend, so DecisionGPT ran a what-if simulation on your data.",
  what_focus: "You asked what to focus on, so DecisionGPT looked at your recent sales and your current goal.",
  analytics_query:
    "DecisionGPT worked out what you were asking, then calculated the answer directly from your sales records. The numbers come from your data, not from a guess.",
  analytics_clarification: "Your question could mean more than one thing, so DecisionGPT is asking before it calculates anything.",
  analytics_unsupported: "DecisionGPT can only calculate things that your uploaded data contains, and this question needs something it doesn't have.",
  why_recommend: "You asked why a recommendation was made, so DecisionGPT looked up its last saved reasoning.",
};

/** What kind of statement each answer is — never present an estimate as a fact. */
export const ANSWER_TYPE_LABEL: Record<string, { label: string; note: string; tone: string }> = {
  evaluation: {
    label: "Recorded evaluation results",
    note: "These are results recorded by evaluations: backtests, held-out tests and benchmark runs. They are not live accuracy against what actually happened, and no AI model wrote or changed a number.",
    tone: "bg-accent-soft text-accent",
  },
  known: {
    label: "From your records",
    note: "Counted directly from the data you added.",
    tone: "bg-success-soft text-success",
  },
  estimate: {
    label: "An estimate",
    note: "This is a prediction or what-if, not a certain outcome.",
    tone: "bg-accent-soft text-accent",
  },
  suggestion: {
    label: "A suggestion",
    note: "This is advice to consider, not a fact about your business.",
    tone: "bg-warning-soft text-warning",
  },
  clarification: {
    label: "A quick question",
    note: "DecisionGPT needs one more detail before it can calculate this.",
    tone: "bg-accent-soft text-accent",
  },
  none: {
    label: "Not enough information",
    note: "DecisionGPT couldn't answer this reliably from the data it has.",
    tone: "bg-muted-surface text-muted",
  },
};

/** Useful next questions, only ones the assistant can answer. */
export const FOLLOW_UPS: Record<string, string[]> = {
  evaluation_results: [
    "Which metrics are unavailable and why?",
    "What metrics are used to evaluate the models?",
    "Show results for each forecast horizon.",
    "Compare the model with its baseline.",
  ],
  top_products: ["What is improving and what is getting worse?", "Which customers are most valuable?"],
  improving_worsening: ["Which products sold the most last month?", "What should I focus on to improve my business?"],
  sales_forecast: ["What is improving and what is getting worse?", "What should I focus on to improve my business?"],
  customer_churn: ["Which customers are most valuable?", "What should I focus on to improve my business?"],
  valuable_customers: ["Which customers are likely to stop buying?", "Which products sold the most last month?"],
  what_focus: ["What is improving and what is getting worse?", "What might my sales look like next month?"],
  why_kpi_fell: ["Which products sold the most last month?", "What should I focus on to improve my business?"],
  price_change_advice: ["What if I increase ad spend?", "What should I focus on to improve my business?"],
  marketing_change_advice: ["Should I increase my price?", "What should I focus on to improve my business?"],
  why_recommend: ["What should I focus on to improve my business?"],
  unrecognized: EXAMPLE_QUESTIONS.slice(0, 3).map((e) => e.question),
};
