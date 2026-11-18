"""
Chapter 4: System Architecture and Technical Design (Full University Thesis Edition).
Comprehensive technical architecture detailing conceptual tiers, microservices,
canonical data preprocessing pipeline, 7-stage multi-agent debate workflow,
relational database ER model, and production deployment topology.
"""

from docx.shared import Pt, Inches
from report_sections.common import (
    add_chapter_header, add_heading_1, add_heading_2, add_p,
    add_tbl_caption, add_table_data, add_image_safe, add_fig_caption
)

def build_chapter_4(doc):
    add_chapter_header(doc, 4, "SYSTEM ARCHITECTURE AND TECHNICAL DESIGN")

    add_heading_1(doc, "4.1 High-Level Conceptual System Architecture")
    add_p(
        doc,
        "DecisionGPT is architected as an enterprise multi-tier software system designed for modularity, data isolation, computational reproducibility, and zero-hallucination execution. The architecture decomposes operational decision support into four interacting tiers: (1) Client Presentation Tier, (2) API Gateway and Routing Tier, (3) Quantitative Intelligence and Simulation Engine Tier, and (4) Relational Persistence and Storage Tier. Figure 4.1 illustrates the conceptual architecture and data flows across these tiers."
    )

    add_image_safe(doc, "figure_overall_architecture.png", width=Inches(5.8))
    add_fig_caption(doc, "4.1", "Overall System Architecture of DecisionGPT")

    add_p(
        doc,
        "As shown in Figure 4.1, client requests originating from web browsers interact with the API Gateway over secure TLS/HTTPS connections. The Gateway validates JSON Web Tokens (JWT), verifies user role permissions, and routes requests to corresponding services. Crucially, the system enforces a strict boundary between the Quantitative Intelligence Engine and the Multi-Agent Reasoning Swarm. Numerical forecasting, causal DAG adjustments, and digital twin state transitions are computed exclusively by verified Python mathematical libraries, ensuring that no statistical metric can be altered or hallucinated by a language model."
    )

    add_heading_1(doc, "4.2 Frontend and Backend Microservices Architecture")
    add_p(
        doc,
        "The interaction between user-facing interfaces and backend analytical services follows a decoupled, asynchronous client-server model, illustrated in Figure 4.2."
    )

    add_image_safe(doc, "figure_frontend_backend_arch.png", width=Inches(5.8))
    add_fig_caption(doc, "4.2", "Frontend and Backend Microservices Architecture")

    add_p(
        doc,
        "• Frontend Subsystem: Implemented with Next.js 14 utilizing React Server Components and TypeScript. The user interface uses Tailwind CSS for responsive styling, Recharts for rendering interactive time-series forecasts and scenario distributions, and Lucide React for consistent icons. Client state is managed through React Context providers, ensuring fast local updates and clean component lifecycles."
    )
    add_p(
        doc,
        "• Backend Subsystem: Built using Python 3.11 and the FastAPI asynchronous Web framework (ASGI). Request validation, parameter serialization, and error handling are enforced using Pydantic v2 schemas. Database access is managed via SQLAlchemy 2.0 ORM with asynchronous connection pooling. Computationally intensive workflows—such as 100-episode Monte Carlo simulations and multi-agent debates—execute as asynchronous background tasks, preventing HTTP connection timeouts."
    )

    add_heading_1(doc, "4.3 Guided Data Ingestion and Canonical Preprocessing Pipeline")
    add_p(
        doc,
        "Heterogeneous transactional exports from small businesses frequently contain missing entries, malformed timestamps, unstandardized column names, and extreme numerical spikes. To convert raw tabular files into structured analytical datasets without requiring manual engineering, DecisionGPT provides an automated 5-step guided preprocessing pipeline, shown in Figure 4.3."
    )

    add_image_safe(doc, "figure_preprocessing_workflow.png", width=Inches(5.8))
    add_fig_caption(doc, "4.3", "Data Ingestion and Canonical Preprocessing Pipeline")

    add_p(
        doc,
        "The pipeline executes in five stages: (1) Schema Profiling and Detection, which infers column data types and maps them to core entity concepts (orders, products, customers); (2) Missing Value Imputation, which applies median values for numerical attributes and mode categories for missing labels; (3) Outlier Processing, which uses Interquartile Range (IQR) bounds [Q1 - 1.5*IQR, Q3 + 1.5*IQR] to clip spurious volume spikes; (4) Datetime Regularization, which normalizes disparate date strings into ISO-8601 timestamps and verifies chronological sequence; and (5) Canonical Parquet Storage, which saves cleaned records in an immutable columnar format scoped by business_id for high-performance querying."
    )

    add_heading_1(doc, "4.4 Multi-Agent Swarm Debate and Consensus Protocol")
    add_p(
        doc,
        "To evaluate complex operational decisions involving cross-functional trade-offs, DecisionGPT coordinates five specialist agents through a structured 7-stage rule-based debate workspace, depicted in Figure 4.4."
    )

    add_image_safe(doc, "figure_debate_workflow.png", width=Inches(5.8))
    add_fig_caption(doc, "4.4", "Multi-Agent Swarm Debate and Consensus Workflow")

    add_p(
        doc,
        "The 7-stage protocol operates as follows: (1) Question Ingestion: the business question or objective is parsed; (2) Shared Evidence Extraction: a deterministic FactSheet is generated from verified database records and digital twin simulation outputs; (3) Independent Specialist Analysis: each of the five specialist agents independently reviews the FactSheet from its domain perspective (e.g., Business Analyst evaluates sales velocity, Financial Advisor evaluates margins, Risk Manager checks inventory stockouts); (4) Cross-Specialist Challenges: explicit rules compare one specialist's claims against another's evidence, flagging conflicts (e.g., Marketing's growth plan vs. Risk's liquidity alert); (5) Evidence and Assumption Review: missing data or unverified assumptions are explicitly identified; (6) Synthesis with Trade-offs: balanced policy recommendations are constructed by weighing revenue growth against solvency preservation; and (7) Final Decision Brief: an executive summary is compiled for human review."
    )

    add_heading_1(doc, "4.5 Database Schema and Relational Entity Architecture")
    add_p(
        doc,
        "DecisionGPT uses a relational schema with foreign-key constraints and tenant isolation. Figure 4.5 displays the Entity-Relationship (ER) diagram, and Table 4.1 documents the core entity models."
    )

    add_image_safe(doc, "figure_database_er.png", width=Inches(5.8))
    add_fig_caption(doc, "4.5", "Database Entity-Relationship (ER) Schema")

    add_tbl_caption(doc, "4.1", "Core Database Tables and Relational Entities")

    db_headers = ["Entity / Table Name", "Primary Key", "Foreign Keys", "Core Responsibilities"]
    db_data = [
        ["businesses", "id (UUID)", "None", "Stores enterprise tenant identity, industry vertical, and base settings"],
        ["users", "id (UUID)", "business_id -> businesses.id", "User account authentication, password hashes, and RBAC roles"],
        ["datasets", "id (UUID)", "business_id -> businesses.id", "Metadata, file locations, row counts, and canonical schemas"],
        ["scenarios", "id (UUID)", "business_id -> businesses.id", "Simulation parameters, baseline states, and shock definitions"],
        ["agent_runs", "id (UUID)", "business_id -> businesses.id", "Tracks agent evaluation logs, scores, and execution traces"],
        ["decisions", "id (UUID)", "business_id -> businesses.id", "Logs committed human decisions, approval status, and rationale"]
    ]
    add_table_data(doc, db_headers, db_data, col_widths=[1.3, 1.1, 1.6, 2.1])

    add_heading_1(doc, "4.6 Production Deployment Topology")
    add_p(
        doc,
        "DecisionGPT is packaged for containerized deployment using Docker and Docker Compose, illustrated in Figure 4.6."
    )

    add_image_safe(doc, "figure_deployment_arch.png", width=Inches(5.8))
    add_fig_caption(doc, "4.6", "Production Deployment Topology and Process Orchestration")

    add_p(
        doc,
        "An Nginx reverse proxy manages inbound HTTP/HTTPS traffic, terminating TLS, serving static frontend assets, and routing /api/v1/ requests to backend FastAPI worker containers. Relational data is persisted in a PostgreSQL container with mounted host volumes, while cleaned canonical datasets are stored on isolated file volumes. This containerized design allows rapid deployment on local developer machines or standard cloud virtual private servers."
    )

    doc.add_page_break()
