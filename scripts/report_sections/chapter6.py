"""
Chapter 6: Research Methodology and Experimental Framework (Full University Thesis Edition).
Comprehensive methodology detailing pre-registered hypotheses, 3-tier dataset taxonomy,
rolling-origin validation, 60-instance benchmark suite (Table 6.1),
mathematical formulations (WAPE, Forecast Score, Regret, Ruin Rate, ECE),
and statistical significance testing protocols.
"""

from docx.shared import Pt
from report_sections.common import (
    add_chapter_header, add_heading_1, add_heading_2, add_p,
    add_tbl_caption, add_table_data
)

def build_chapter_6(doc):
    add_chapter_header(doc, 6, "RESEARCH METHODOLOGY AND EXPERIMENTAL FRAMEWORK")

    add_heading_1(doc, "6.1 Research Design and Pre-Registered Hypotheses")
    add_p(
        doc,
        "The empirical research framework of DecisionGPT is structured as a controlled, confirmatory comparative study designed to evaluate predictive accuracy, risk calibration, decision quality, and multi-agent interaction dynamics. In accordance with open science and pre-registration principles (Nosek et al. [52]), four formal hypotheses were formulated prior to benchmark execution:"
    )
    add_p(
        doc,
        "• Hypothesis 1 (H1 — Horizon Sensitivity): Time-series demand forecasting error, measured via Weighted Absolute Percentage Error (WAPE), decreases monotonically as the aggregation horizon expands from daily (1-day) to bi-weekly (14-day) and monthly (28-day), due to the statistical cancellation of high-frequency stochastic daily noise [14], [16]."
    )
    add_p(
        doc,
        "• Hypothesis 2 (H2 — Conformal Risk Calibration): Gradient boosted customer churn models calibrated with conformal prediction achieve empirical coverage probabilities exceeding 90% with an Expected Calibration Error (ECE) below 0.05 on the standardized synthetic churn cohort [18], [19]."
    )
    add_p(
        doc,
        "• Hypothesis 3 (H3 — Primacy of Digital Twin in Regret Reduction): The quantitative state-space Digital Twin simulation accounts for the decisive majority (>70%) of total decision regret reduction relative to unassisted human heuristic baselines (p < 0.001) [26], [28]."
    )
    add_p(
        doc,
        "• Hypothesis 4 (H4 — Dialectical Tail-Risk Bounding): While multi-agent dialectical debate provides qualitative trade-off explainability and reduces catastrophic insolvency ruin rates below 2%, its reduction in narrow objective regret relative to a calibrated single-agent optimizer is modest and not statistically significant at alpha = 0.05, with the single agent achieving lower narrow regret (p = 0.0093) [46], [47], [51]."
    )

    add_heading_1(doc, "6.2 Three-Tier Dataset Taxonomy and Empirical Characteristics")
    add_p(
        doc,
        "To ensure rigorous evaluation across both empirical and stress-tested operational conditions, the research utilizes a three-tier dataset taxonomy:"
    )
    add_p(
        doc,
        "1. Primary Empirical Indian E-Commerce Dataset: A real-world transactional dataset from an Indian commercial e-commerce merchant (Benroshan dataset [48]), comprising daily order volumes from 1 April 2018 to 31 March 2019 (365 daily observations, including 58 zero-sales days). Features include order dates, unit quantities, product category references, unit selling prices, discount depths, and delivery transit times."
    )
    add_p(
        doc,
        "2. Canonical SME Enterprise Schemas: Standardized relational schemas modeling small enterprise operations, featuring normalized customer accounts, inventory stock ledgers, accounts payable/receivable, and operational expense logs [8], [9]."
    )
    add_p(
        doc,
        "3. Standardized Synthetic Customer Churn Cohort: To evaluate churn classification while respecting data privacy, a synthetic cohort of 6,000 customer accounts across five random seeds was generated. Churn probabilities were parameterized using feature distributions derived from commercial retail benchmarks. As an explicit research integrity disclosure, these synthetic labels evaluate model calibration and discrimination, but do not represent observed live-customer churn events."
    )

    add_heading_1(doc, "6.3 Feature Engineering and Rolling-Origin Temporal Validation")
    add_p(
        doc,
        "Time-series models were trained using high-dimensional feature vectors: (1) Temporal lag features: sales volumes at t-1, t-7, t-14, and t-28; (2) Rolling window statistics: moving mean, standard deviation, minimum, and maximum over 7-day and 28-day windows; (3) Calendar indicators: day of week, day of month, month, and Indian festival flags (Diwali, Holi, Eid); and (4) Exogenous drivers: promotional discount depth and delivery transit latency."
    )
    add_p(
        doc,
        "To avoid look-ahead data leakage, models were evaluated using an expanding-window rolling-origin temporal validation protocol [14]. Across the 365-day dataset, 51 evaluation origins were evaluated. Because rolling-origin windows overlap chronologically, individual forecast errors across origins are statistically dependent. To verify directionality, non-overlapping disjoint checks were also conducted: H14 achieved a score of 81.65% (N=4 disjoint windows), and H28 achieved a score of 80.31% (N=2 disjoint windows), providing consistent directional support."
    )

    add_heading_1(doc, "6.4 Confirmatory Decision Benchmark Suite (60 Locked Instances)")
    add_p(
        doc,
        "To evaluate decision quality systematically, an authoritative confirmatory benchmark suite comprising 60 locked instances across 12 operational scenario families was evaluated, detailed in Table 6.1."
    )

    add_tbl_caption(doc, "6.1", "Confirmatory Decision Benchmark Suite (12 Scenario Families, 60 Locked Instances)")

    bench_headers = ["Scenario Family", "Instance Range", "Operational Stress Shock Applied", "Primary Trade-off Tested"]
    bench_data = [
        ["1. Demand Surge", "Instances 01 - 05", "+35% to +60% demand spike over 14 days", "Stockout avoidance vs. working capital lockup"],
        ["2. Supply Disruption", "Instances 06 - 10", "+15 to +30 days supplier delivery delay", "Buffer inventory cost vs. production halt"],
        ["3. Marketing Expansion", "Instances 11 - 15", "+50% ad spend with diminishing returns", "CAC escalation vs. revenue volume growth"],
        ["4. Liquidity Squeeze", "Instances 16 - 20", "Delayed receivables (+45 days DSO shock)", "Immediate solvency vs. delayed vendor payments"],
        ["5. Price War", "Instances 21 - 25", "Competitor slashes prices by 20%", "Margin collapse vs. permanent market share loss"],
        ["6. Supplier Cost Shock", "Instances 26 - 30", "Raw material inflation (+25% COGS)", "Price hike customer churn vs. negative margin"],
        ["7. Product Obsolescence", "Instances 31 - 35", "Demand collapse on aging category (-50%)", "Liquidation discounting vs. carrying holding costs"],
        ["8. Regulatory Shock", "Instances 36 - 40", "Sudden GST tax adjustment (+5% to +10%)", "Absorbing tax hit vs. passing cost to consumer"],
        ["9. Channel Conflict", "Instances 41 - 45", "Online marketplace fees increase by 8%", "Direct-to-consumer migration vs. volume loss"],
        ["10. Seasonal Peak", "Instances 46 - 50", "Diwali festival 3x demand surge", "Pre-ordering liquidity risk vs. lost holiday sales"],
        ["11. Freight Surge", "Instances 47 - 55", "Logistics shipping rates double (+100%)", "Free shipping margin erosion vs. checkout drops"],
        ["12. Customer Churn", "Instances 56 - 60", "Customer retention drop (-15% retention)", "Aggressive loyalty discount cost vs. churn bleed"]
    ]
    add_table_data(doc, bench_headers, bench_data, col_widths=[1.3, 1.1, 2.1, 1.6])

    add_heading_1(doc, "6.5 Mathematical Formulations and Evaluation Metrics")
    add_p(
        doc,
        "To ensure clarity and prevent misinterpretation, the evaluation metrics are mathematically formulated as follows:"
    )
    add_p(
        doc,
        "1. Weighted Absolute Percentage Error (WAPE): Used for demand forecasting evaluation, weighted by actual sales volume to prevent division-by-zero on intermittent days (Hyndman and Koehler [14]):"
    )
    add_p(
        doc,
        "    WAPE = ( sum_{t=1}^T | y_t - y_hat_t | ) / ( sum_{t=1}^T y_t )",
        align=None, italic=True
    )
    add_p(
        doc,
        "2. Forecast Score: Defined as the volume-weighted predictive accuracy percentage. It must never be confused with classification accuracy:"
    )
    add_p(
        doc,
        "    Forecast Score = 100 * ( 1 - WAPE )",
        align=None, italic=True
    )
    add_p(
        doc,
        "3. Decision Regret: Quantifies the utility loss between the selected operational strategy a and the ex-post optimal strategy a* under true environment state s:"
    )
    add_p(
        doc,
        "    Regret(a, s) = max_{a' in A} U(a', s) - U(a, s)",
        align=None, italic=True
    )
    add_p(
        doc,
        "4. Relative Regret Reduction (RRR): Measures the percentage reduction in regret achieved relative to the baseline:"
    )
    add_p(
        doc,
        "    RRR = [ ( Regret_baseline - Regret_system ) / Regret_baseline ] * 100%",
        align=None, italic=True
    )
    add_p(
        doc,
        "5. Tail Risk Ruin Rate: The empirical probability that enterprise cash flow drops below zero during planning horizon T, indicating insolvency (García and Fernández [51]):"
    )
    add_p(
        doc,
        "    Ruin Rate = P( Cash_Flow_t <= 0  |  a, s )",
        align=None, italic=True
    )
    add_p(
        doc,
        "6. Expected Calibration Error (ECE): Measures the discrepancy between predicted probabilities and empirical event frequencies across M probability bins. ECE measures probability calibration, not predictive discrimination:"
    )
    add_p(
        doc,
        "    ECE = sum_{m=1}^M ( |B_m| / N ) * | acc(B_m) - conf(B_m) |",
        align=None, italic=True
    )

    add_heading_1(doc, "6.6 Statistical Significance Testing Protocols")
    add_p(
        doc,
        "Because decision regret distributions across the 60 benchmark instances violate normality (Shapiro-Wilk test, p < 0.01), statistical hypothesis testing was conducted using the non-parametric Wilcoxon signed-rank test for paired observations (Wilcoxon [50]; Demšar [49]) with Pratt tie-handling and Holm-Bonferroni correction for multiple hypothesis testing. Bootstrap confidence intervals (95% CI) were computed using 1,000 resamples."
    )

    doc.add_page_break()
