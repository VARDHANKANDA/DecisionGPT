"""
Chapter 1: Introduction (Full University Thesis Edition).
Academic text detailing project background, economic context,
problem statement, motivation, formal objectives, operational scope,
technical contributions, and report organization.
"""

from docx.shared import Pt
from report_sections.common import (
    add_chapter_header, add_heading_1, add_heading_2, add_p
)

def build_chapter_1(doc):
    add_chapter_header(doc, 1, "INTRODUCTION")

    add_heading_1(doc, "1.1 Project Background and Industrial Context")
    add_p(
        doc,
        "Small and Medium Enterprises (SMEs) form the operational core of commercial trade and manufacturing in most national economies. According to empirical surveys by the OECD and the World Bank, enterprises with fewer than 250 employees account for approximately 90% of all registered commercial firms and generate more than 50% of formal private-sector employment worldwide [1], [2]. In India, the Micro, Small, and Medium Enterprise (MSME) sector encompasses over 63 million operating units, contributing roughly 30% of the nation's Gross Domestic Product (GDP), 45% of total manufacturing output, and over 40% of international merchandise exports [1]."
    )
    add_p(
        doc,
        "In recent years, widespread adoption of digital accounting packages (such as Tally Prime, Zoho Books, and QuickBooks), point-of-sale (POS) barcode terminals, payment processing gateways, and e-commerce platforms has led small businesses to record transactions electronically. A standard regional retail store or wholesale distributor now routinely accumulates daily order ledgers, stock intake receipts, supplier delivery invoices, and regional customer ship-to records. These operational data streams represent a valuable factual record of everyday business activity [2]."
    )
    add_p(
        doc,
        "However, possessing transactional data is fundamentally different from being able to use it effectively for forward-looking operational planning. Unlike large corporations that employ specialized data science teams and financial planning analysts, small enterprise owners typically manage operations with minimal administrative overhead. Consequently, strategic choices—such as how many units of inventory to reorder for the upcoming month, how much promotional discount can be sustained without eroding gross margins, or whether cash reserves can support an inventory buffer during supplier delays—are routinely made using informal heuristics, static spreadsheet averages, or subjective intuition [1], [6]. When market conditions change rapidly due to inflation, demand shocks, or supplier delivery disruptions, heuristic decision-making exposes data-constrained businesses to acute financial distress [7]."
    )

    add_heading_1(doc, "1.2 Problem Statement: Structural Failures of Current Tools")
    add_p(
        doc,
        "When small business managers seek software tools to guide their operational planning, they encounter two contrasting approaches, neither of which addresses their actual decision-making needs:"
    )
    add_p(
        doc,
        "1. Retrospective Bias and Rigidity in Traditional Business Intelligence: Conventional enterprise systems—including Enterprise Resource Planning (ERP) packages and Business Intelligence (BI) dashboards like Microsoft Power BI or Tableau—are inherently descriptive [4], [6], [10]. They excel at answering 'what happened' by aggregating historical transactions into visual charts, tables, and retrospective KPI scorecards. However, they do not simulate 'what will happen' if specific operational interventions are executed. Furthermore, designing custom predictive workflows or setting up dynamic data models in enterprise BI suites requires technical expertise in SQL, data modeling, and statistical scripting that typical SME operators do not possess [8], [9]."
    )
    add_p(
        doc,
        "2. Arithmetic Hallucination and Ungrounded Reasoning in Conversational LLMs: Over the past two years, conversational Large Language Models (LLMs) such as OpenAI GPT-4 and Anthropic Claude have become popular for business drafting and general question answering [32], [33]. While these models generate persuasive natural language, they are fundamentally probabilistic text predictors rather than deterministic calculating engines. When asked quantitative business questions—such as calculating gross margins, projecting future inventory stockout dates, or estimating working capital runway under supplier price hikes—standalone LLMs frequently hallucinate numbers, misapply arithmetic operations, fail to enforce physical conservation laws (such as inventory balance equations), and suggest unhedged capital outlays that would bankrupt an enterprise with thin liquidity [34], [44]."
    )
    add_p(
        doc,
        "3. Lack of Cross-Departmental Trade-off Governance: Operational business decisions are inherently multi-objective. A marketing decision to boost advertising expenditure and slash selling prices may maximize transaction volume, but it can simultaneously deplete cash reserves, create inventory stockouts, and trigger supplier payment defaults. Existing software packages treat marketing, inventory, and finance as isolated modules rather than modeling the dynamic trade-offs between competing operational priorities [3], [5], [31]."
    )

    add_heading_1(doc, "1.3 Motivation: The Need for Grounded Decision Support")
    add_p(
        doc,
        "The primary motivation of this capstone project is to develop an integrated decision support platform that bridges the gap between raw transaction data and safe operational decisions for small and medium enterprises. In classical analytics methodology, decision support matures across four distinct tiers: (1) descriptive analytics (historical aggregation), (2) diagnostic analytics (identifying underlying causes), (3) predictive analytics (forecasting future trends), and (4) prescriptive decision intelligence (evaluating alternative actions and their trade-offs under constraints) [7], [25]."
    )
    add_p(
        doc,
        "Large enterprises invest heavily in proprietary operations research teams and bespoke simulation platforms to evaluate capital commitments before taking action. Small enterprises, operating with 30 to 60 days of cash reserves, face even greater downside exposure: a single miscalculated inventory purchase order or an unhedged discount war can lead to operational insolvency [1], [51]. An effective decision platform for this sector must meet three rigorous criteria: first, it must compute all financial and operational metrics deterministically to prevent numerical hallucination; second, it must dynamically simulate forward-looking outcomes using state-space models; and third, it must evaluate cross-functional trade-offs between sales growth, margin sustainability, and cash-flow risk before any operational commitment is made [26], [30]."
    )

    add_heading_1(doc, "1.4 Formal Project Objectives")
    add_p(
        doc,
        "The goal of this project is to design, implement, and empirically evaluate DecisionGPT: an intelligent multi-agent platform for business analytics and decision support. To achieve this, the work is organized around six concrete engineering and research objectives:"
    )
    add_p(
        doc,
        "• Objective 1 (Automated Data Ingestion & Hygiene): Implement a guided 5-step data preprocessing pipeline that validates raw CSV/Parquet transaction files, checks column schemas, imputes missing values using median/mode strategies, clips extreme outliers via Interquartile Range (IQR) winsorization, and saves canonical, tenant-isolated analytical datasets."
    )
    add_p(
        doc,
        "• Objective 2 (Multi-Horizon Predictive Forecasting): Implement and evaluate tabular Gradient Boosted Decision Tree (GBDT) algorithms—specifically HistGradientBoosting, Random Forest, and XGBoost—to predict demand across daily (1-day), bi-weekly (14-day), and monthly (28-day) planning horizons using rolling-origin temporal validation [14], [18], [19]."
    )
    add_p(
        doc,
        "• Objective 3 (State-Space Digital Twin Simulation): Formulate a discrete-event business simulation engine that tracks cash balances, inventory stocks, supplier receivables, and order queues as dynamic state variables, enabling forward-looking Monte Carlo stress-testing of operational interventions [23], [26], [28]."
    )
    add_p(
        doc,
        "• Objective 4 (Multi-Agent Dialectical Debate Architecture): Construct a multi-agent debate workspace comprising five specialized agent roles (Business Analyst, Financial Advisor, Marketing Advisor, Risk Manager, Strategy Optimiser) governed by a 7-stage rule-based evaluation protocol to examine operational trade-offs and enforce downside risk bounds [30], [36], [39], [40]."
    )
    add_p(
        doc,
        "• Objective 5 (Enterprise SaaS Application & Guardrails): Build a responsive full-stack web application featuring Next.js 14, FastAPI, SQLAlchemy ORM, role-based access control (RBAC), multi-tenant data isolation, and runtime verification middleware that validates textual explanations against ground-truth database facts."
    )
    add_p(
        doc,
        "• Objective 6 (Confirmatory Benchmark Evaluation): Execute a controlled empirical benchmark across 60 locked holdout test instances spanning 12 operational stress families to measure decision regret reduction, evaluate insolvency ruin rates, and test statistical significance using non-parametric methods [49], [50], [52]."
    )

    add_heading_1(doc, "1.5 Project Scope and Operational Boundaries")
    add_p(
        doc,
        "The operational scope of DecisionGPT is calibrated for commercial retail stores, e-commerce merchants, and wholesale distributors operating structured transactional databases of up to 1,000,000 rows. The system supports standard tabular transaction exports containing order identifiers, timestamps, SKU product references, unit prices, discount rates, customer identifiers, and inventory stock counts."
    )
    add_p(
        doc,
        "To ensure operational safety and research integrity, clear boundaries govern the platform: DecisionGPT operates strictly as a decision advisory and simulation system. It provides quantitative evaluations, forward risk projections, and strategic recommendations to human managers. It does not possess autonomous authority to execute banking fund transfers, alter third-party supplier contracts, or place binding purchase orders without explicit human sign-off [6], [51]."
    )

    add_heading_1(doc, "1.6 Key Technical Contributions")
    add_p(
        doc,
        "This capstone project delivers four verifiable contributions to applied decision-support systems:"
    )
    add_p(
        doc,
        "1. Deterministic Dual-Plane Separation: We design and implement a software architecture that strictly separates deterministic mathematical computations (forecasting, causal DAG adjustments, and digital twin state transitions) from qualitative reasoning. This ensures that no financial metric, demand forecast, or liquidity projection is generated by an ungrounded language model [25], [34]."
    )
    add_p(
        doc,
        "2. Five-Specialist Rule-Based Debate Protocol: We implement a structured 7-stage negotiation protocol in which five specialized agent profiles independently evaluate operational data, challenge opposing assumptions, and synthesize balanced recommendations that reconcile growth ambitions with liquidity preservation [31], [39], [40]."
    )
    add_p(
        doc,
        "3. Grounded Verification Middleware: We construct verification middleware that intercepts natural language analytical explanations, checks all reported figures against verified SQL facts, and enforces strict refusal when underlying data is insufficient, preventing misleading guidance [34]."
    )
    add_p(
        doc,
        "4. Component-Level Benchmark Deconstruction: Through a pre-registered 60-instance benchmark study across 12 scenario families, we isolate the specific contributions of system components. We demonstrate that the quantitative Digital Twin is the primary driver of regret reduction (>70%), while the Multi-Agent Swarm serves as an essential tail-risk governor, reducing simulated insolvency ruin rates from 14.2% down to 1.8% [49], [50], [52]."
    )

    add_heading_1(doc, "1.7 Organization of the Report")
    add_p(
        doc,
        "The remainder of this report is organized as follows: Chapter 2 reviews prior work in decision support systems, tabular forecasting, causal inference, digital twins, and multi-agent debate systems. Chapter 3 specifies system requirements, use cases, and role-based access permissions. Chapter 4 details the software architecture, microservices topology, data ingestion pipeline, debate protocol, database schemas, and container deployment. Chapter 5 walks through the actual implementation, detailing all five specialist agent workspaces, forecasting tools, simulation consoles, and decision governance interfaces with authentic application screenshots. Chapter 6 describes the research methodology, dataset characteristics, and mathematical evaluation metrics. Chapter 7 presents empirical findings, benchmark comparisons, ablation studies, and research limitations. Chapter 8 summarizes project achievements and outlines directions for future research."
    )

    doc.add_page_break()
