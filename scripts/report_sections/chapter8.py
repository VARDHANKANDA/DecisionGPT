"""
Chapter 8: Conclusion and Future Scope (Full University Thesis Edition).
Comprehensive synthesis of completed research, engineering achievements,
practical enterprise implications, and future research roadmap.
"""

from docx.shared import Pt
from report_sections.common import (
    add_chapter_header, add_heading_1, add_heading_2, add_p
)

def build_chapter_8(doc):
    add_chapter_header(doc, 8, "CONCLUSION AND FUTURE SCOPE")

    add_heading_1(doc, "8.1 Summary of Completed Research and Engineering Work")
    add_p(
        doc,
        "This capstone project presented the design, implementation, and empirical evaluation of DecisionGPT: an intelligent multi-agent platform for business analytics and decision support engineered for small and medium commercial enterprises. The project addressed the practical challenge faced by data-constrained SMEs: transforming everyday transactional records into forward-looking, risk-calibrated operational decisions without requiring dedicated data science or management consulting teams."
    )
    add_p(
        doc,
        "To resolve the limitations of descriptive BI dashboards and hallucination-prone conversational models, DecisionGPT introduced a Dual-Plane Architecture that separates deterministic quantitative calculations from qualitative reasoning. The platform integrates an automated 5-step guided data preprocessing wizard, multi-horizon GBDT sales forecasting (HistGradientBoosting, Random Forest, XGBoost), structural causal DAG adjustments, a discrete-event state-space digital twin simulation engine, and a 5-specialist rule-based debate workspace governed by factual verification middleware."
    )

    add_heading_1(doc, "8.2 Key Academic and Engineering Achievements")
    add_p(
        doc,
        "The project produced four concrete academic and technical achievements:"
    )
    add_p(
        doc,
        "1. Elimination of Numerical Hallucination via Dual-Plane Separation: We demonstrated that confining language models to qualitative interpretation and natural language classification—while running all forecasts, metrics, and state transitions through verified deterministic libraries—completely eliminates financial and numerical hallucinations from decision outputs."
    )
    add_p(
        doc,
        "2. Demonstrated Multi-Horizon Forecasting Accuracy: Evaluating time-series models on 365 days of real Indian commercial e-commerce transactions demonstrated that monthly aggregation cancels stochastic daily noise, improving volume-weighted Forecast Scores from 31.94% at the daily horizon (WAPE 68.06%) to 90.66% at the 28-day monthly procurement horizon (WAPE 9.34%)."
    )
    add_p(
        doc,
        "3. Rigorous Deconstruction of Multi-Agent Decision Value: Across a pre-registered 60-instance confirmatory benchmark suite, our evaluations established that the quantitative Digital Twin simulation is the primary driver of regret reduction (>70%), cutting mean regret from 0.2495 down to 0.1420 (p = 0.0004). Furthermore, our analysis revealed that while a single-agent optimizer achieves lower narrow regret (0.1102 vs. 0.1863, pHolm = 0.0093), it incurs an unacceptable 14.2% tail-risk insolvency rate. In contrast, the multi-agent debate swarm acts as an essential solvency governor, applying conservative risk penalties that slash the simulated ruin rate down to 1.8%."
    )
    add_p(
        doc,
        "4. Deployment of a Full-Stack Enterprise SaaS Platform: We developed and containerized a production-grade web application featuring Next.js 14, FastAPI, SQLAlchemy ORM, role-based access control, multi-tenant data isolation, and interactive visual workspaces."
    )

    add_heading_1(doc, "8.3 Practical Implications for Enterprise Decision Intelligence")
    add_p(
        doc,
        "For small and medium enterprises, the practical value of DecisionGPT lies in risk reduction. Operating on thin profit margins and limited cash buffers, small business owners cannot afford costly mistakes in inventory purchasing or aggressive discounting. By providing an automated platform that profiles data quality, forecasts multi-horizon demand, and allows managers to stress-test major operational decisions in a virtual digital twin before committing real capital, DecisionGPT brings institutional-grade decision intelligence within reach of everyday commercial enterprises."
    )

    add_heading_1(doc, "8.4 Future Research Directions and Technical Roadmap")
    add_p(
        doc,
        "The findings and implementation of this capstone project suggest four valuable avenues for future research:"
    )
    add_p(
        doc,
        "• Longitudinal Field Trials with Active SMEs: The current digital twin outcome tracking table is empty. A primary priority is conducting multi-month longitudinal field trials with active retail merchants to measure actual realized post-decision financial outcomes, inventory stockout reductions, and cash-flow stability in live commercial environments."
    )
    add_p(
        doc,
        "• Automated Causal Graph Discovery: While DecisionGPT currently uses domain-specified structural causal DAGs, future work will integrate automated constraint-based and score-based causal discovery algorithms (such as the PC algorithm or NOTEARS) to infer causal relationships directly from observational transaction time series."
    )
    add_p(
        doc,
        "• Multi-Agent Reinforcement Learning (MARL): Future iterations could explore training specialist agents using multi-agent reinforcement learning with safety constraints, allowing agents to discover adaptive hedging policies under simulated macroeconomic supply disruptions."
    )
    add_p(
        doc,
        "• Multimodal Document Ingestion and Vernacular Speech: Extending the data ingestion pipeline to support optical character recognition (OCR) for physical paper invoices and regional vernacular speech interfaces (such as Hindi or Telugu) would further reduce technical barriers for traditional small business proprietors."
    )

    doc.add_page_break()
