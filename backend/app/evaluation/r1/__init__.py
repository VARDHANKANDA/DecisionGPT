"""R1 — versioned RESEARCH-ONLY Decision-Simulation correction.

R1 exists because V1/V2 showed the production Digital Twin's projected units are
effectively constant in price (SHAP importance of price+marketing ≈ 2 %; a 3x
price sweep moves projected units by 0.0), so condition B degenerates to
"raise price to the candidate ceiling" regardless of the decision environment
(see docs/R1_DT_DIAGNOSTIC.md).

R1 changes EXACTLY ONE thing: the scenario-side demand response. It does not
touch production files. The corrected Digital Twin (``r1_dt``) is injected at
test time by ``r1.harness``. A/B/C/D definitions, the agents, the optimizer, the
risk manager, the candidate action space, and the exogenous objective
(``app.evaluation.ground_truth`` = "System B") are all unchanged.

Nothing here modifies R0/D0, R3, V1, or V2.
"""
R1_LAYER_VERSION = "r1_research_dt_v1"
FROZEN_MANIFEST_SHA256 = "94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff"
