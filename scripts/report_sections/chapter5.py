"""
Chapter 5: System Implementation and Application Features (Full University Thesis Edition).
Comprehensive technical implementation walk-through detailing the complete software stack,
executive command dashboard, guided preprocessing wizard, conversational assistant,
all 5 specialized agent workspaces, multi-agent debate swarm console, forecasting engine,
scenario simulation, and strategic decision governance interfaces with authentic screenshots.
"""

from docx.shared import Pt, Inches
from report_sections.common import (
    add_chapter_header, add_heading_1, add_heading_2, add_heading_3, add_p,
    add_tbl_caption, add_table_data, add_image_safe, add_fig_caption
)

def build_chapter_5(doc):
    add_chapter_header(doc, 5, "SYSTEM IMPLEMENTATION AND APPLICATION FEATURES")

    add_heading_1(doc, "5.1 Technology Stack and Development Frameworks")
    add_p(
        doc,
        "DecisionGPT is implemented using modern, type-safe development frameworks. Table 5.1 summarizes the technologies, libraries, and runtime components across the frontend, backend, analytical pipelines, and database layers."
    )

    add_tbl_caption(doc, "5.1", "Software Stack, Libraries, and Infrastructure Specifications")

    tech_headers = ["Software Layer / Domain", "Technology / Framework", "Version", "Functional Role in DecisionGPT"]
    tech_data = [
        ["Frontend Framework", "Next.js (App Router)", "16.4.2", "Server and client-side rendering, routing, and layout management"],
        ["User Interface Library", "React & TypeScript", "19.0 / 5.4", "Component hierarchy, type-safe state, and UI lifecycles"],
        ["Styling & Micro-interactions", "Tailwind CSS & Lucide", "3.4 / 0.38", "Responsive utility styling, design tokens, and modern icon set"],
        ["Data Visualizations", "Recharts", "2.12.7", "Interactive SVG time-series charts, bar charts, and radar graphs"],
        ["Backend REST API", "FastAPI (ASGI)", "0.115.0", "Asynchronous HTTP endpoints, dependency injection, and OpenAPI docs"],
        ["Data Validation & Schemas", "Pydantic", "2.8.2", "Runtime schema enforcement, type validation, and serialization"],
        ["Relational ORM & DB", "SQLAlchemy / SQLite / PostgreSQL", "2.0.31", "Asynchronous relational persistence, migrations, and query isolation"],
        ["Scientific & Tabular", "NumPy & Pandas", "1.26 / 2.2", "Array mathematics, tabular dataframe manipulation, and statistics"],
        ["Machine Learning Models", "scikit-learn & XGBoost", "1.5.0 / 2.0.3", "HistGradientBoosting, Random Forest, XGBoost regression and churn models"],
        ["Container Runtime", "Docker & Docker Compose", "26.1 / 2.27", "Multi-service container orchestration, networking, and volume management"]
    ]
    add_table_data(doc, tech_headers, tech_data, col_widths=[1.3, 1.5, 0.9, 2.4])

    add_heading_1(doc, "5.2 Enterprise SaaS Landing Page and Platform Navigation")
    add_p(
        doc,
        "Figure 5.1 shows the DecisionGPT public landing page. It introduces the platform's decision-support capabilities, core workflows, and supported business verticals, providing navigation into the authenticated application."
    )

    add_image_safe(doc, "screenshot_landing_page.png", width=Inches(5.5))
    add_fig_caption(doc, "5.1", "DecisionGPT Enterprise SaaS Landing Page Interface")

    add_heading_1(doc, "5.3 Executive Command Center Overview Dashboard")
    add_p(
        doc,
        "The Executive Command Dashboard (Figure 5.2) serves as the primary home view for business managers. It aggregates high-level performance indicators—including monthly revenue momentum, gross margins, cash burn rate, working capital runway, and customer churn risk—derived deterministically from verified business records."
    )

    add_image_safe(doc, "screenshot_dashboard.png", width=Inches(5.5))
    add_fig_caption(doc, "5.2", "Executive Command Center Overview Dashboard")

    add_heading_1(doc, "5.4 Enterprise Dataset Management Library")
    add_p(
        doc,
        "The Dataset Management Library (Figure 5.3) provides an interface for uploading and managing tabular transaction files. Users can view file metadata, row counts, column types, and data health scores, with strict multi-tenant isolation enforced by business_id."
    )

    add_image_safe(doc, "screenshot_data_library.png", width=Inches(5.5))
    add_fig_caption(doc, "5.3", "Enterprise Dataset Library Workspace")

    add_heading_1(doc, "5.5 Guided Data Preprocessing and Validation Wizard")
    add_p(
        doc,
        "To ensure data quality prior to modeling, DecisionGPT includes an automated 5-step data preprocessing wizard (Figure 5.4). The wizard scans raw uploaded files, identifies missing values and column type anomalies, applies median/mode imputation, clips extreme outliers via IQR bounds, and converts records into a standardized canonical schema."
    )

    add_image_safe(doc, "screenshot_data_preprocessing.png", width=Inches(5.5))
    add_fig_caption(doc, "5.4", "Guided 5-Step Data Preprocessing and Validation Wizard")

    add_heading_1(doc, "5.6 Guarded Business Assistant: Exploratory Analysis")
    add_p(
        doc,
        "DecisionGPT provides a conversational Business Assistant (Figure 5.5) designed for natural language data exploration ('Understand and Explore'). It translates user questions into structured analytical queries, executes them against verified database records, and narrates the results. Importantly, it carries verification guardrails: every response cites the underlying data sources queried, and if the data is insufficient to answer reliably, the assistant returns an honest refusal rather than guessing."
    )

    add_image_safe(doc, "screenshot_business_assistant.png", width=Inches(5.5))
    add_fig_caption(doc, "5.5", "DecisionGPT Business Assistant with Guarded Analytics")

    add_heading_1(doc, "5.7 Specialized Autonomous Agent Workspaces")
    add_p(
        doc,
        "DecisionGPT implements five dedicated agent consultation workspaces, summarized in Table 5.2 and illustrated in Figures 5.6 through 5.10. Each workspace evaluates business data from a specific operational perspective, outputting structured advice across six consistent sections: Executive Summary, Key Findings, Supporting Evidence, Business Implications, Recommended Actions, and Assumptions."
    )

    add_tbl_caption(doc, "5.2", "Specialist Agent Roles, System Directives, and Domain Mandates")

    agent_headers = ["Specialist Agent Role", "Operational Focus", "Core Inputs & Evidence", "Primary Domain Mandate"]
    agent_data = [
        ["Business Analyst", "Sales Velocity & Trends", "Daily order volumes, product revenue, category shares", "Identify sales momentum, top-performing SKUs, and underperforming categories"],
        ["Financial Advisor", "Margins & Working Capital", "COGS, gross profit margins, operating overhead, cash reserves", "Evaluate margin sustainability, expenditure run-rates, and capital allocation"],
        ["Marketing Advisor", "Campaigns & Acquisition", "Ad expenditure, promotional discounts, channel conversion lift", "Assess campaign ROI, customer acquisition cost, and promotional effectiveness"],
        ["Risk Manager", "Vulnerabilities & Downside", "Stockout incidents, delivery lead times, churn indicators, cash runway", "Identify operational stockout liabilities, data gaps, and solvency risks"],
        ["Strategy Optimiser", "Trade-off Synthesis", "Outputs from all four specialists and digital twin simulations", "Compare alternative interventions and synthesize balanced strategic recommendations"]
    ]
    add_table_data(doc, agent_headers, agent_data, col_widths=[1.4, 1.3, 1.8, 1.6])

    add_p(doc, "• Business Analyst Workspace (Figure 5.6): Analyzes sales volume trends, SKU velocity, and seasonal demand shifts.")
    add_image_safe(doc, "screenshot_business_analyst.png", width=Inches(5.5))
    add_fig_caption(doc, "5.6", "Business Analyst Specialist Workspace")

    add_p(doc, "• Financial Advisor Workspace (Figure 5.7): Reviews product cost structures, margin health, and cash-flow implications.")
    add_image_safe(doc, "screenshot_financial_advisor.png", width=Inches(5.5))
    add_fig_caption(doc, "5.7", "Financial Advisor Specialist Workspace")

    add_p(doc, "• Marketing Advisor Workspace (Figure 5.8): Examines marketing spend efficiency, discount depth, and channel returns.")
    add_image_safe(doc, "screenshot_marketing_advisor.png", width=Inches(5.5))
    add_fig_caption(doc, "5.8", "Marketing Advisor Specialist Workspace")

    add_p(doc, "• Risk Manager Workspace (Figure 5.9): Scans for stockout risks, customer churn indicators, and liquidity exposure.")
    add_image_safe(doc, "screenshot_risk_manager.png", width=Inches(5.5))
    add_fig_caption(doc, "5.9", "Risk Manager Specialist Workspace")

    add_p(doc, "• Strategy Optimiser Workspace (Figure 5.10): Evaluates multi-objective trade-offs and ranks strategic options.")
    add_image_safe(doc, "screenshot_strategy_optimiser.png", width=Inches(5.5))
    add_fig_caption(doc, "5.10", "Strategy Optimiser Specialist Workspace")

    add_heading_1(doc, "5.8 Multi-Agent Swarm Debate Workspace")
    add_p(
        doc,
        "The Multi-Agent Swarm Debate Workspace (Figure 5.11) hosts the 7-stage dialectical evaluation process. Rather than relying on ungrounded conversational exchanges, the debate operates over a deterministic FactSheet. When specialists present conflicting priorities—such as Marketing proposing a discount expansion while the Risk Manager warns of inventory exhaustion—the system resolves differences by recomputing constraints against verified operational data."
    )

    add_image_safe(doc, "screenshot_debate.png", width=Inches(5.5))
    add_fig_caption(doc, "5.11", "Multi-Agent Swarm Debate and Strategy Evaluation Panel")

    add_heading_1(doc, "5.9 Machine Learning Predictive Forecasting Engine")
    add_p(
        doc,
        "Figure 5.12 displays the Predictive Forecasting Console. The engine trains GBDT models (HistGradientBoosting, Random Forest, XGBoost) across daily, bi-weekly, and monthly horizons, allowing managers to inspect forecast accuracy metrics (WAPE, Forecast Score) and plan procurement cycles accordingly."
    )

    add_image_safe(doc, "screenshot_forecast.png", width=Inches(5.5))
    add_fig_caption(doc, "5.12", "Multi-Horizon Sales Forecasting Engine Console")

    add_heading_1(doc, "5.10 Deterministic Business Analytics Explorer")
    add_p(
        doc,
        "The Business Analytics Explorer (Figure 5.13) provides structured analytical views of historical operations, including revenue breakdowns, category volume shares, and customer transaction distributions, all computed through direct SQL queries."
    )

    add_image_safe(doc, "screenshot_analytics.png", width=Inches(5.5))
    add_fig_caption(doc, "5.13", "Deterministic Business Analytics Explorer")

    add_heading_1(doc, "5.11 Scenario Simulation and Digital Twin Console")
    add_p(
        doc,
        "The Scenario Simulation Console (Figure 5.14) allows users to perform Scenario Analysis by applying simulated shocks (e.g., +30% demand, +20% supplier cost) to the digital twin. The state-space simulation runs 100 Monte Carlo episodes to project cash flow and inventory trajectories, computing terminal liquidity distributions and ruin probabilities."
    )

    add_image_safe(doc, "screenshot_scenario_analysis.png", width=Inches(5.5))
    add_fig_caption(doc, "5.14", "Monte Carlo Scenario Simulation Console")

    add_heading_1(doc, "5.12 Strategic Decision Recommendations and Governance")
    add_p(
        doc,
        "Figure 5.15 displays the Recommendations and Decisions interface ('Evaluate and Act'). In contrast to the exploratory Business Assistant, this module supports formal decision-making. Managers can review candidate strategies, compare projected outcomes, inspect trade-offs, and record formal approvals. All decisions are logged in an immutable database table to support post-decision auditability."
    )

    add_image_safe(doc, "screenshot_decisions.png", width=Inches(5.5))
    add_fig_caption(doc, "5.15", "Strategic Decision Recommendations and Governance Interface")

    doc.add_page_break()
