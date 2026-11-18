"""
Front Matter Builder for Capstone Project Report (Full University Thesis Edition).
Contains:
  - Page i: Title Page
  - Page ii: Bonafide Certificate
  - Page iii: Student Declaration
  - Page iv: Acknowledgements
  - Page v: Abstract & Keywords (Clean single-page fit)
  - Page vi: Master Table of Contents (Exact Aligned Pages)
  - Page vii: Master List of Figures (Exact Aligned Pages)
  - Page viii: Master List of Tables & Key Technical Abbreviations (Clean single-page fit)
"""

from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from report_sections.common import (
    FONT_NAME, BODY_SIZE, add_p, set_font, add_table_data
)

def build_cover_page(doc):
    """Page i: Title Page"""
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(36)
    p_title.paragraph_format.space_after = Pt(18)
    p_title.paragraph_format.line_spacing = 1.3
    r_title = p_title.add_run("DECISIONGPT: AN INTELLIGENT MULTI-AGENT PLATFORM FOR BUSINESS ANALYTICS AND DECISION SUPPORT")
    set_font(r_title, font_name=FONT_NAME, size=Pt(14), bold=True)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(12)
    p_sub.paragraph_format.space_after = Pt(8)
    r_sub = p_sub.add_run("A CAPSTONE PROJECT REPORT")
    set_font(r_sub, font_name=FONT_NAME, size=Pt(13), bold=True)

    p_req = doc.add_paragraph()
    p_req.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_req.paragraph_format.space_before = Pt(8)
    p_req.paragraph_format.space_after = Pt(4)
    p_req.paragraph_format.line_spacing = 1.15
    r_req1 = p_req.add_run("Submitted in partial fulfillment of the\nrequirement for the award of the\nDegree of\n")
    set_font(r_req1, font_name=FONT_NAME, size=Pt(11))
    r_req2 = p_req.add_run("BACHELOR OF TECHNOLOGY\nIN\nCOMPUTER SCIENCE AND ENGINEERING")
    set_font(r_req2, font_name=FONT_NAME, size=Pt(12), bold=True)

    p_by = doc.add_paragraph()
    p_by.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_by.paragraph_format.space_before = Pt(16)
    p_by.paragraph_format.space_after = Pt(6)
    r_by = p_by.add_run("by\n")
    set_font(r_by, font_name=FONT_NAME, size=Pt(11), italic=True)

    students = [
        ("K. S. SRI VARDHAN", "23BCE8389"),
        ("R ROHIT", "23BCE8394"),
        ("K. RAHUL", "23BCE8396"),
        ("FELIX", "23BCE8402")
    ]
    p_stud = doc.add_paragraph()
    p_stud.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_stud.paragraph_format.space_before = Pt(2)
    p_stud.paragraph_format.space_after = Pt(16)
    p_stud.paragraph_format.line_spacing = 1.15
    for name, regno in students:
        r_s = p_stud.add_run(f"{name} ({regno})\n")
        set_font(r_s, font_name=FONT_NAME, size=Pt(11), bold=True)

    p_guide = doc.add_paragraph()
    p_guide.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_guide.paragraph_format.space_before = Pt(12)
    p_guide.paragraph_format.space_after = Pt(18)
    p_guide.paragraph_format.line_spacing = 1.15
    r_g1 = p_guide.add_run("Under the Guidance of\n")
    set_font(r_g1, font_name=FONT_NAME, size=Pt(11), italic=True)
    r_g2 = p_guide.add_run("Dr. Yelepi Usha Rani\nAssociate Professor Grade 1\nSchool of Computer Science and Engineering (SCOPE)")
    set_font(r_g2, font_name=FONT_NAME, size=Pt(11), bold=True)

    p_univ = doc.add_paragraph()
    p_univ.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_univ.paragraph_format.space_before = Pt(16)
    p_univ.paragraph_format.space_after = Pt(0)
    p_univ.paragraph_format.line_spacing = 1.15
    r_u = p_univ.add_run("SCHOOL OF COMPUTER SCIENCE AND ENGINEERING\nVIT-AP UNIVERSITY\nAMARAVATI - 522237, ANDHRA PRADESH, INDIA\nNOVEMBER 2026")
    set_font(r_u, font_name=FONT_NAME, size=Pt(11), bold=True)

    doc.add_page_break()

def build_certificate(doc):
    """Page ii: Bonafide Certificate"""
    p_cert = doc.add_paragraph()
    p_cert.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cert.paragraph_format.space_before = Pt(16)
    p_cert.paragraph_format.space_after = Pt(16)
    r_ct = p_cert.add_run("BONAFIDE CERTIFICATE")
    set_font(r_ct, font_name=FONT_NAME, size=Pt(14), bold=True)

    add_p(
        doc,
        "This is to certify that the Capstone Project report entitled “DECISIONGPT: AN INTELLIGENT MULTI-AGENT PLATFORM FOR BUSINESS ANALYTICS AND DECISION SUPPORT” submitted by K. S. SRI VARDHAN (23BCE8389), R ROHIT (23BCE8394), K. RAHUL (23BCE8396), and FELIX (23BCE8402) in partial fulfillment of the requirements for the award of the degree of Bachelor of Technology in Computer Science and Engineering from VIT-AP University, Amaravati, is a bonafide record of work carried out by them under my supervision and guidance.",
        space_before=Pt(12), space_after=Pt(14), line_spacing=1.35, font_size=Pt(11.5)
    )

    add_p(
        doc,
        "The project work embodies original system architecture design, machine learning pipeline development, multi-agent dialectical orchestration, and empirical validation conducted during the academic year 2025–2026. The results embodied in this report have not been submitted to any other University or Institute for the award of any degree or diploma.",
        space_before=Pt(0), space_after=Pt(36), line_spacing=1.35, font_size=Pt(11.5)
    )

    p_sigs = doc.add_paragraph()
    p_sigs.paragraph_format.space_before = Pt(28)
    p_sigs.paragraph_format.space_after = Pt(12)
    p_sigs.paragraph_format.line_spacing = 1.2
    r_s1 = p_sigs.add_run("Dr. Yelepi Usha Rani                                                                Head of School\n")
    set_font(r_s1, font_name=FONT_NAME, size=Pt(11), bold=True)
    r_s2 = p_sigs.add_run("Associate Professor Grade 1                                              School of Computer Science & Engineering\nSchool of Computer Science and Engineering (SCOPE)                   VIT-AP University\nVIT-AP University")
    set_font(r_s2, font_name=FONT_NAME, size=Pt(10.5))

    doc.add_page_break()

def build_declaration(doc):
    """Page iii: Student Declaration"""
    p_decl = doc.add_paragraph()
    p_decl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_decl.paragraph_format.space_before = Pt(16)
    p_decl.paragraph_format.space_after = Pt(16)
    r_dt = p_decl.add_run("DECLARATION")
    set_font(r_dt, font_name=FONT_NAME, size=Pt(14), bold=True)

    add_p(
        doc,
        "We hereby declare that the work presented in this Capstone Project report entitled “DECISIONGPT: AN INTELLIGENT MULTI-AGENT PLATFORM FOR BUSINESS ANALYTICS AND DECISION SUPPORT” is an authentic record of our own research, architectural design, software development, and empirical benchmarking conducted under the mentorship of Dr. Yelepi Usha Rani, Associate Professor Grade 1, School of Computer Science and Engineering (SCOPE), VIT-AP University.",
        space_before=Pt(12), space_after=Pt(14), line_spacing=1.35, font_size=Pt(11.5)
    )

    add_p(
        doc,
        "We affirm that all external software packages, research papers, datasets, and literature cited have been acknowledged with proper references. We confirm that this work has not been previously submitted in part or full for any degree, diploma, or fellowship at this or any other academic institution.",
        space_before=Pt(0), space_after=Pt(36), line_spacing=1.35, font_size=Pt(11.5)
    )

    p_stud_sigs = doc.add_paragraph()
    p_stud_sigs.paragraph_format.space_before = Pt(20)
    p_stud_sigs.paragraph_format.space_after = Pt(0)
    p_stud_sigs.paragraph_format.line_spacing = 1.3
    candidates = [
        "1. K. S. SRI VARDHAN (23BCE8389)",
        "2. R ROHIT (23BCE8394)",
        "3. K. RAHUL (23BCE8396)",
        "4. FELIX (23BCE8402)"
    ]
    r_cs = p_stud_sigs.add_run("Candidates:\n" + "\n".join(candidates))
    set_font(r_cs, font_name=FONT_NAME, size=Pt(11), bold=True)

    doc.add_page_break()

def build_acknowledgements(doc):
    """Page iv: Acknowledgements"""
    p_ack = doc.add_paragraph()
    p_ack.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_ack.paragraph_format.space_before = Pt(16)
    p_ack.paragraph_format.space_after = Pt(16)
    r_at = p_ack.add_run("ACKNOWLEDGEMENTS")
    set_font(r_at, font_name=FONT_NAME, size=Pt(14), bold=True)

    add_p(
        doc,
        "First and foremost, we thank the Almighty for the health, resilience, and guidance that enabled us to complete this capstone project successfully.",
        space_after=Pt(8), line_spacing=1.35
    )
    add_p(
        doc,
        "We express our sincere gratitude to the leadership of VIT-AP University, Amaravati—including the Chancellor, Vice-Chancellor, and Registrar—for providing the computing infrastructure, library resources, and academic environment that supported our undergraduate education.",
        space_after=Pt(8), line_spacing=1.35
    )
    add_p(
        doc,
        "We express our deep appreciation to our Faculty Guide, Dr. Yelepi Usha Rani, Associate Professor Grade 1, School of Computer Science and Engineering (SCOPE), for her patient guidance, technical feedback, and continuous support throughout system design, implementation, and experimental evaluation.",
        space_after=Pt(8), line_spacing=1.35
    )
    add_p(
        doc,
        "We also thank the Dean, Associate Deans, and faculty members of the School of Computer Science and Engineering (SCOPE) for their instruction, project reviews, and administrative assistance throughout our curriculum.",
        space_after=Pt(8), line_spacing=1.35
    )
    add_p(
        doc,
        "Finally, we thank our parents, family members, and classmates for their constant encouragement, patience, and support throughout the duration of this project.",
        space_after=Pt(14), line_spacing=1.35
    )

    doc.add_page_break()

def build_abstract(doc):
    """Page v: Abstract & Keywords (Clean single-page fit)"""
    p_abs = doc.add_paragraph()
    p_abs.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_abs.paragraph_format.space_before = Pt(6)
    p_abs.paragraph_format.space_after = Pt(6)
    r_ab = p_abs.add_run("ABSTRACT")
    set_font(r_ab, font_name=FONT_NAME, size=Pt(14), bold=True)

    add_p(
        doc,
        "Small and Medium Enterprises (SMEs) account for the vast majority of commercial firms and private employment in developing economies, yet they frequently make critical operational decisions under severe informational and analytical constraints. Conventional Enterprise Resource Planning (ERP) and Business Intelligence (BI) platforms provide descriptive summaries of historical transactions, but they offer no dynamic mechanisms to simulate forward-looking operational shocks or quantify strategic trade-offs under cash-flow constraints. Conversely, general-purpose Large Language Models (LLMs) can generate fluent textual summaries, but they suffer from arithmetic hallucinations, lack grounding in physical conservation laws, and cannot reliably evaluate business solvency.",
        space_after=Pt(4), line_spacing=1.15, font_size=Pt(10.5)
    )
    add_p(
        doc,
        "This capstone project presents DecisionGPT, an intelligent multi-agent platform for business analytics and decision support designed specifically for data-constrained commercial SMEs. DecisionGPT implements a strict Dual-Plane Architecture that decouples deterministic quantitative computation from qualitative reasoning. All statistical feature transformations, multi-horizon sales forecasting (HistGradientBoosting, Random Forest, XGBoost), customer churn risk scoring, and discrete-event state-space digital twin simulations run deterministically without LLM intervention. Qualitative reasoning is handled through five specialized agent personas (Business Analyst, Financial Advisor, Marketing Advisor, Risk Manager, Strategy Optimiser) coordinated within a structured 7-stage rule-based debate workspace that evaluates operational trade-offs across competing business objectives.",
        space_after=Pt(4), line_spacing=1.15, font_size=Pt(10.5)
    )
    add_p(
        doc,
        "The system was evaluated using an empirical Indian e-commerce retail dataset (365 daily observations) and a pre-registered confirmatory decision benchmark across 60 locked holdout instances spanning 12 operational stress families. Time-series forecasting achieves a volume-weighted Forecast Score of 90.66% at the 28-day monthly procurement horizon (WAPE 9.34%), compared to 31.94% at the daily horizon (WAPE 68.06%), confirming that stochastic daily noise averages out across monthly reordering cycles. In decision benchmark evaluations, the quantitative Digital Twin simulation accounts for the decisive majority (>70%) of regret reduction relative to unassisted heuristic baselines (cutting mean regret from 0.2495 down to 0.1420). While a single-agent optimizer achieves the lowest narrow-objective regret (0.1102), it incurs an unacceptable 14.2% tail-risk insolvency rate. In contrast, the full multi-agent debate swarm introduces conservative risk penalties that slash the simulated ruin rate to 1.8% (p = 0.0042), serving as a crucial solvency governor. The application is implemented as an enterprise SaaS platform with role-based access control, interactive analytics workspaces, and verifiable zero-hallucination guardrails.",
        space_after=Pt(6), line_spacing=1.15, font_size=Pt(10.5)
    )

    p_kw = doc.add_paragraph()
    p_kw.paragraph_format.space_before = Pt(4)
    p_kw.paragraph_format.space_after = Pt(0)
    p_kw.paragraph_format.line_spacing = 1.15
    r_kw1 = p_kw.add_run("Keywords: ")
    set_font(r_kw1, font_name=FONT_NAME, size=Pt(10.5), bold=True)
    r_kw2 = p_kw.add_run("Decision Support Systems, Multi-Agent Systems, Dialectical Debate, Digital Twin, Time-Series Forecasting, Gradient Boosted Decision Trees, Risk Governance, Small and Medium Enterprises (SMEs).")
    set_font(r_kw2, font_name=FONT_NAME, size=Pt(10.5), italic=True)

    doc.add_page_break()

def build_table_of_contents(doc):
    """Page vi: Master Table of Contents (Aligned with Exact Rendered Pages)"""
    p_toc = doc.add_paragraph()
    p_toc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_toc.paragraph_format.space_before = Pt(10)
    p_toc.paragraph_format.space_after = Pt(8)
    r_tc = p_toc.add_run("TABLE OF CONTENTS")
    set_font(r_tc, font_name=FONT_NAME, size=Pt(14), bold=True)

    headers = ["Chapter", "Title", "Page No."]
    toc_data = [
        ["", "BONAFIDE CERTIFICATE", "ii"],
        ["", "DECLARATION", "iii"],
        ["", "ACKNOWLEDGEMENTS", "iv"],
        ["", "ABSTRACT & KEYWORDS", "v"],
        ["", "LIST OF FIGURES", "vii"],
        ["", "LIST OF TABLES & NOMENCLATURE", "viii"],
        ["CHAPTER 1", "INTRODUCTION", "1"],
        ["1.1 - 1.3", "Project Background, Problem Statement & Motivation", "1"],
        ["1.4 - 1.7", "Objectives, Scope, Contributions & Organization", "2"],
        ["CHAPTER 2", "LITERATURE REVIEW AND EXISTING SYSTEMS", "5"],
        ["2.1 - 2.3", "DSS Evolution, GBDT Forecasting & Causal Models", "5"],
        ["2.4 - 2.5", "Digital Twin Simulations & Multi-Agent Dialectical Debate", "6"],
        ["2.6 - 2.7", "Commercial Systems Critique & Comparative Gap Matrix", "7"],
        ["CHAPTER 3", "PROPOSED SYSTEM AND REQUIREMENTS", "9"],
        ["3.1 - 3.3", "Dual-Plane Solution Overview, FRs & NFRs", "9"],
        ["3.4 - 3.6", "RBAC Matrix, Use-Case Specifications & Workflows", "10"],
        ["CHAPTER 4", "SYSTEM ARCHITECTURE AND TECHNICAL DESIGN", "13"],
        ["4.1 - 4.3", "Tiered Architecture, Microservices & Data Ingestion Pipeline", "13"],
        ["4.4 - 4.6", "7-Stage Debate Protocol, Database ER Model & Deployment", "15"],
        ["CHAPTER 5", "SYSTEM IMPLEMENTATION AND APPLICATION FEATURES", "19"],
        ["5.1 - 5.4", "Tech Stack, Command Dashboard, Preprocessing & Assistant", "19"],
        ["5.5 - 5.8", "Five Specialist Agent Workspaces & Debate Swarm Console", "22"],
        ["5.9 - 5.12", "Multi-Horizon Forecasting, Analytics & Decision Management", "25"],
        ["CHAPTER 6", "RESEARCH METHODOLOGY AND EXPERIMENTAL FRAMEWORK", "30"],
        ["6.1 - 6.3", "Research Design, 3-Tier Dataset Taxonomy & Validation", "30"],
        ["6.4 - 6.6", "60-Instance Confirmatory Suite, Formulations & Stats", "31"],
        ["CHAPTER 7", "RESULTS, ANALYSIS AND DISCUSSION", "33"],
        ["7.1 - 7.3", "Forecasting Metrics, Churn Calibration & Decision Regret", "33"],
        ["7.4 - 7.7", "Ablation Studies, Statistical Significance & Discussion", "35"],
        ["CHAPTER 8", "CONCLUSION AND FUTURE SCOPE", "38"],
        ["8.1 - 8.4", "Summary of Work, Achievements, Implications & Roadmap", "38"],
        ["", "REFERENCES", "40"],
        ["APPENDIX A", "MULTI-AGENT DIALECTICAL DEBATE ENGINE & FACTSHEET EXTRACTION", "43"],
        ["APPENDIX B", "SPECIALIST AGENT EVALUATION CONTRACT & DOWNSIDE SCORING", "45"],
        ["APPENDIX C", "GUARDED ANALYTICS INTENT ROUTER & VERIFICATION MIDDLEWARE", "46"],
        ["APPENDIX D", "CANONICAL TABULAR INGESTION & OUTLIER WINSORIZATION CORE", "47"]
    ]
    add_table_data(doc, headers, toc_data, col_widths=[1.4, 4.4, 0.8])
    doc.add_page_break()

def build_list_of_figures(doc):
    """Page vii: Master List of Figures (Aligned with Exact Rendered Pages)"""
    p_lof = doc.add_paragraph()
    p_lof.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lof.paragraph_format.space_before = Pt(10)
    p_lof.paragraph_format.space_after = Pt(8)
    r_lf = p_lof.add_run("LIST OF FIGURES")
    set_font(r_lf, font_name=FONT_NAME, size=Pt(13), bold=True)

    fig_headers = ["Figure No.", "Figure Caption", "Page No."]
    fig_data = [
        ["Figure 3.1", "DecisionGPT System Use-Case Specification Diagram", "11"],
        ["Figure 4.1", "Overall System Architecture of DecisionGPT", "13"],
        ["Figure 4.2", "Frontend and Backend Microservices Architecture", "13"],
        ["Figure 4.3", "Data Ingestion and Canonical Preprocessing Pipeline", "14"],
        ["Figure 4.4", "Multi-Agent Swarm Debate and Consensus Workflow", "15"],
        ["Figure 4.5", "Database Entity-Relationship (ER) Schema", "16"],
        ["Figure 4.6", "Production Deployment Topology and Process Orchestration", "17"],
        ["Figure 5.1", "DecisionGPT Enterprise SaaS Landing Page Interface", "19"],
        ["Figure 5.2", "Executive Command Center Overview Dashboard", "20"],
        ["Figure 5.3", "Enterprise Dataset Library Workspace", "21"],
        ["Figure 5.4", "Guided 5-Step Data Preprocessing and Validation Wizard", "21"],
        ["Figure 5.5", "DecisionGPT Business Assistant with Guarded Analytics", "22"],
        ["Figure 5.6", "Business Analyst Specialist Workspace", "23"],
        ["Figure 5.7", "Financial Advisor Specialist Workspace", "24"],
        ["Figure 5.8", "Marketing Advisor Specialist Workspace", "24"],
        ["Figure 5.9", "Risk Manager Specialist Workspace", "24"],
        ["Figure 5.10", "Strategy Optimiser Specialist Workspace", "25"],
        ["Figure 5.11", "Multi-Agent Swarm Debate and Strategy Evaluation Panel", "25"],
        ["Figure 5.12", "Multi-Horizon Sales Forecasting Engine Console", "26"],
        ["Figure 5.13", "Deterministic Business Analytics Explorer", "27"],
        ["Figure 5.14", "Monte Carlo Scenario Simulation Console", "27"],
        ["Figure 5.15", "Strategic Decision Recommendations and Governance Interface", "28"],
        ["Figure 7.1", "Multi-Horizon Sales Forecasting Model Performance Comparison", "33"],
        ["Figure 7.2", "Conformal Prediction Uncertainty and Risk Calibration Intervals", "34"],
        ["Figure 7.3", "Decision Regret Benchmark Comparison Across Algorithmic Strategies", "35"],
        ["Figure 7.4", "Architectural Ablation Analysis: Isolating Twin, Causal, and Debate", "35"]
    ]
    add_table_data(doc, fig_headers, fig_data, col_widths=[1.2, 4.6, 0.8])
    doc.add_page_break()

def build_list_of_tables_abbreviations(doc):
    """Page viii: Master List of Tables & Nomenclature (Clean single-page fit)"""
    p_lot = doc.add_paragraph()
    p_lot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_lot.paragraph_format.space_before = Pt(6)
    p_lot.paragraph_format.space_after = Pt(4)
    r_lt = p_lot.add_run("LIST OF TABLES")
    set_font(r_lt, font_name=FONT_NAME, size=Pt(12.5), bold=True)

    tbl_headers = ["Table No.", "Table Title", "Page No."]
    tbl_data = [
        ["Table 2.1", "Comparative Analysis of Traditional ERP, Conversational LLMs, and DecisionGPT", "7"],
        ["Table 3.1", "Role-Based Access Control (RBAC) Permission Matrix", "11"],
        ["Table 3.2", "System Use-Case Specifications (UC1 - UC6)", "11"],
        ["Table 4.1", "Core Database Tables and Relational Entities", "16"],
        ["Table 5.1", "Software Stack, Libraries, and Infrastructure Specifications", "19"],
        ["Table 5.2", "Specialist Agent Roles, System Directives, and Domain Mandates", "23"],
        ["Table 6.1", "Confirmatory Decision Benchmark Suite (12 Scenario Families, 60 Locked Instances)", "31"],
        ["Table 7.1", "Empirical Forecasting Model Performance Across Temporal Horizons", "33"],
        ["Table 7.2", "Customer Churn Risk Model Performance and Calibration Metrics", "34"],
        ["Table 7.3", "Decision Regret Benchmark Results Across Operational Strategies", "35"],
        ["Table 7.4", "Ablation Study Results: Dissecting DecisionGPT Architectural Components", "35"],
        ["Table 7.5", "Wilcoxon Signed-Rank Statistical Significance Test Results", "36"]
    ]
    add_table_data(doc, tbl_headers, tbl_data, col_widths=[1.2, 4.6, 0.8])

    p_nom = doc.add_paragraph()
    p_nom.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_nom.paragraph_format.space_before = Pt(6)
    p_nom.paragraph_format.space_after = Pt(3)
    r_nm = p_nom.add_run("KEY TECHNICAL ABBREVIATIONS")
    set_font(r_nm, font_name=FONT_NAME, size=Pt(11.0), bold=True)

    nom_headers = ["Abbreviation", "Full Technical Description"]
    nom_data = [
        ["BI / DSS", "Business Intelligence / Decision Support System"],
        ["DAG", "Directed Acyclic Graph (Structural Causal Modeling)"],
        ["ECE", "Expected Calibration Error (Probability Reliability)"],
        ["GBDT", "Gradient Boosted Decision Trees (XGBoost, RF, HGB)"],
        ["MSME", "Micro, Small, and Medium Enterprises"],
        ["RBAC", "Role-Based Access Control (JWT Authentication)"],
        ["RRR", "Relative Regret Reduction (Benchmark Metric)"],
        ["SaaS", "Software as a Service (Cloud-Native Deployment)"],
        ["WAPE", "Weighted Absolute Percentage Error (Demand Metric)"]
    ]
    add_table_data(doc, nom_headers, nom_data, col_widths=[1.4, 4.9])
    doc.add_page_break()
