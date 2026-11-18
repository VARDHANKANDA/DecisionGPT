"""
Chapter 2: Literature Review and Existing Systems (Full University Thesis Edition).
Comprehensive academic review covering DSS evolution, GBDT forecasting,
causal inference, digital twins, multi-agent debate protocols, commercial
system evaluations, and the comparative analysis gap matrix.
"""

from docx.shared import Pt
from report_sections.common import (
    add_chapter_header, add_heading_1, add_heading_2, add_p,
    add_tbl_caption, add_table_data
)

def build_chapter_2(doc):
    add_chapter_header(doc, 2, "LITERATURE REVIEW AND EXISTING SYSTEMS")

    add_heading_1(doc, "2.1 Evolution of Decision Support Systems and Business Intelligence")
    add_p(
        doc,
        "Computer-assisted managerial decision-making began in the early 1970s. In seminal work at MIT, Michael S. Scott Morton [3] introduced 'Management Decision Systems' to describe interactive, model-driven computing environments that assist executives in confronting semi-structured and unstructured decision problems. Peter Keen and Scott Morton [5] generalized this paradigm into the field of Decision Support Systems (DSS). Ralph Sprague [4] subsequently formulated the foundational architectural framework for DSS, identifying three essential collaborating components: (1) the Data Management Subsystem, (2) the Model Management Subsystem, and (3) the Dialogue (User Interface) Subsystem."
    )
    add_p(
        doc,
        "During the 1990s and 2000s, enterprise data warehousing substantially reshaped decision support architecture. Bill Inmon [8] introduced the enterprise data warehouse as a subject-oriented, integrated, time-variant, and non-volatile repository of corporate operational records. Ralph Kimball and Margy Ross [9] developed dimensional modeling and star schema design, enabling multidimensional Online Analytical Processing (OLAP) queries across product, temporal, and geographic dimensions. These developments allowed organizations to aggregate millions of historical records efficiently."
    )
    add_p(
        doc,
        "Over the past decade, self-service Business Intelligence (BI) platforms—such as Microsoft Power BI, Tableau Software, and Qlik Sense (Eckerson [10])—have democratized data visualization. However, as noted in critical reviews by Arnott and Pervan [6] and Lepenioti et al. [7], traditional BI remains fundamentally retrospective: it provides descriptive aggregations of past events ('what happened'), but lacks simulation capabilities to model prospective operational interventions ('what will happen if action X is taken') or prescribe actions under liquidity constraints."
    )

    add_heading_1(doc, "2.2 Time-Series Forecasting: Statistical Baselines vs. Gradient Boosted Trees")
    add_p(
        doc,
        "Demand forecasting is a central component of operational planning. The classical literature has long relied on linear autoregressive models, notably the Autoregressive Integrated Moving Average (ARIMA) family introduced by Box and Jenkins [11], and Error-Trend-Seasonal (ETS) exponential smoothing frameworks. For intermittent or 'lumpy' demand patterns common in spare parts and slow-moving retail stock, Croston [12] introduced a specialized technique that separates non-zero transaction quantities from inter-arrival intervals, which was later refined by Syntetos and Boylan [13]."
    )
    add_p(
        doc,
        "Although linear statistical methods provide parsimonious parameters and interpretable theoretical baselines, empirical competitions—such as the international M4 [15] and M5 Competitions organized by Makridakis et al. [16]—demonstrated that classical linear formulations struggle on complex retail datasets with nonlinear interactions, promotion schedules, and cross-category cannibalization. In the M5 Competition, which evaluated forecasts across 42,840 hierarchical retail sales series, gradient boosted tree architectures formed the core of top-performing solutions [16]."
    )
    add_p(
        doc,
        "Three modern Gradient Boosted Decision Tree (GBDT) implementations represent the current standard for tabular regression: (1) XGBoost, developed by Chen and Guestrin [18], which introduced second-order loss approximations, sparsity-aware split finding, and cache-aware access; (2) LightGBM, developed by Ke et al. [19], which implemented Gradient-based One-Side Sampling (GOSS) and Exclusive Feature Bundling (EFB); and (3) CatBoost, developed by Prokhorenkova et al. [20], which pioneered ordered target encoding to prevent target leakage from categorical attributes. In comparative benchmarks on tabular data, GBDT models match or exceed deep neural networks (such as LSTM or DeepAR [17]) while requiring orders of magnitude less training time and zero specialized GPU hardware, making them well-suited for SME deployments [16], [18]."
    )

    add_heading_1(doc, "2.3 Causal Inference and Structural Equation Modeling")
    add_p(
        doc,
        "A recognized limitation of predictive machine learning is its reliance on observational correlation. In enterprise decision-making, correlation alone does not justify intervention. For instance, high seasonal sales often correlate with elevated delivery costs, but cutting delivery expenditure during peak seasons will not increase sales. In business operations, confounding variables—such as consumer holiday patterns or regional promotional campaigns—routinely induce non-causal statistical associations [21], [25]."
    )
    add_p(
        doc,
        "To evaluate operational interventions safely, systems must distinguish correlation from causation. In his foundational work on causal epistemology, Judea Pearl [23] established the Causal Hierarchy (the 'Ladder of Causation'), delineating three cognitive levels: (1) Association ($P(y|x)$ — observation), (2) Intervention ($P(y|do(x))$ — action), and (3) Counterfactuals ($P(y_x|x', y')$ — retrospection). Pearl formalized Structural Causal Models (SCMs) and Directed Acyclic Graph (DAG) calculus, establishing Backdoor and Frontdoor Adjustment criteria to identify invariant causal effects in the presence of observed confounders [23], [24]."
    )
    add_p(
        doc,
        "Complementing Pearl's framework, Spirtes, Glymour, and Scheines [22] formulated constraint-based causal discovery algorithms (such as the PC algorithm) to reconstruct causal graph topologies from conditional independence tests, building on Granger's econometric causality concepts [21]. In DecisionGPT, causal DAG structures are embedded within the analytics engine to ensure that simulated interventions (such as promotional price cuts) adjust for known confounders (such as seasonality and baseline brand equity) before estimating revenue impacts [7], [23]."
    )

    add_heading_1(doc, "2.4 Discrete-Event State-Space Digital Twin Simulation in Enterprise Operations")
    add_p(
        doc,
        "The concept of the 'Digital Twin'—a computational model that continuously mirrors the state, dynamics, and environmental interactions of a real-world system—originated in aerospace engineering and product lifecycle management (Grieves and Vickers [26]). In a comprehensive categorical review, Kritzinger et al. [27] categorized virtual-physical systems into three levels: (1) Digital Model (manual data exchange in both directions), (2) Digital Shadow (automated one-way data flow from physical to digital), and (3) Digital Twin (automated bidirectional data flow and synchronization)."
    )
    add_p(
        doc,
        "While digital twin applications originally focused on physical machinery, turbine diagnostics, and smart manufacturing lines (Tao et al. [28]; Jones et al. [29]), recent research has applied digital twin principles to enterprise economic systems. An enterprise Digital Twin models an organization's cash balance, inventory stock, supplier receivables, and customer order backlog as discrete-event state variables governed by conservation laws and stochastic transition functions [26], [27]."
    )
    add_p(
        doc,
        "By combining state-transition equations with Monte Carlo random draws, an enterprise Digital Twin allows managers to run risk-free stress tests [26], [51]. DecisionGPT implements a discrete-event business twin that evaluates simulated operational shocks across forward-looking multi-week horizons, computing empirical probability distributions over terminal working capital, inventory holding costs, and insolvency ruin rates without putting actual capital at risk [51]."
    )

    add_heading_1(doc, "2.5 Multi-Agent Systems, Dialectical Debate, and Recent Failure Mode Findings")
    add_p(
        doc,
        "Multi-Agent Systems (MAS) have been studied in distributed artificial intelligence for decades (Wooldridge and Jennings [30]; Bulling [31]). Traditional MAS architectures used symbolic logic, contract net protocols, and BDI (Belief-Desire-Intention) models to coordinate distributed problem solving. The rise of Transformer-based Large Language Models (Vaswani et al. [32]; Brown et al. [33]) has introduced expressive natural-language agents capable of role-playing, reasoning, and communicative planning (Park et al. [35]; Wang et al. [38])."
    )
    add_p(
        doc,
        "Open-source orchestration frameworks like Microsoft AutoGen (Wu et al. [36]) and MetaGPT (Hong et al. [37]) demonstrate that dividing tasks among specialized LLM personas can improve code generation and textual analysis. Furthermore, investigations into multi-agent debate—such as Du et al. [39] and Liang et al. [40]—show that adversarial exchanges between language models can encourage divergent thinking and identify reasoning flaws in qualitative tasks."
    )
    add_p(
        doc,
        "However, recent rigorous studies have uncovered significant limitations in multi-agent LLM systems. Tran and Kiela [46] and Fu et al. [47] demonstrated that multi-agent discussions frequently underperform well-prompted single agents on multi-step reasoning benchmarks while incurring substantial token latency and monetary costs. Furthermore, Huang et al. [44] established that LLMs cannot reliably self-correct erroneous reasoning without external verifiable feedback. In comprehensive empirical investigations, Smit and Grinsztajn [43] and Cemri et al. [45] demonstrated that unconstrained multi-agent debate often degenerates into consensus conformity or shared hallucinations, where agents reinforce each other's unsupported claims."
    )
    add_p(
        doc,
        "These empirical findings inform a core architectural choice in DecisionGPT: multi-agent debate must not be responsible for unconstrained numerical calculation. Instead, multi-agent debate in DecisionGPT is implemented as a rule-based multi-perspective review operating over deterministic facts generated by the predictive engine and digital twin [25], [34], [51]."
    )

    add_heading_1(doc, "2.6 Critical Analysis of Existing Systems")
    add_p(
        doc,
        "To clarify the specific operational capabilities addressed by DecisionGPT, Table 2.1 compares existing software approaches with our implemented system across five essential decision-support dimensions."
    )

    add_tbl_caption(doc, "2.1", "Comparative Analysis of Traditional ERP, Conversational LLMs, and DecisionGPT")

    table_headers = [
        "Capability Dimension",
        "Legacy ERP Systems\n(SAP, Oracle, Tally)",
        "Traditional BI Tools\n(Power BI, Tableau)",
        "Standalone LLMs\n(ChatGPT, Claude)",
        "DecisionGPT\n(This Project)"
    ]

    table_data = [
        [
            "Primary Analytic\nOrientation",
            "Descriptive transaction recording & historical compliance",
            "Descriptive aggregation & static visual dashboarding",
            "Linguistic generation & conversational heuristics",
            "Prescriptive decision intelligence & causal optimization"
        ],
        [
            "Predictive Forecasting\nMechanism",
            "Rudimentary moving averages or rule heuristics",
            "Basic linear trendlines or proprietary black-box add-ons",
            "Ungrounded probabilistic textual generation",
            "Multi-horizon GBDT (XGBoost, RF, HGB) with WAPE scoring"
        ],
        [
            "Causal & Digital Twin\nSimulation",
            "None; static relational database tables",
            "None; external what-if parameters without state dynamics",
            "Hallucinates non-physical trajectories without bounds",
            "Discrete-event state-space twin modeling cash & inventory"
        ],
        [
            "Multi-Agent Cross-Check\n& Governance",
            "Rigid, uncoordinated organizational silos",
            "Single-user dashboard slicing without trade-off analysis",
            "Single persona; easily swayed by leading prompts",
            "5-specialist dialectical debate swarm with quorum synthesis"
        ],
        [
            "SME Accessibility &\nDeployment",
            "Cost-prohibitive setup & complex enterprise maintenance",
            "Requires specialized data engineering & SQL modeling",
            "Accessible interface but unreliable financial accuracy",
            "Automated 5-step data wizard & turnkey cloud-native SaaS"
        ]
    ]

    add_table_data(doc, table_headers, table_data, col_widths=[1.5, 1.4, 1.4, 1.3, 1.5])
    doc.add_page_break()
