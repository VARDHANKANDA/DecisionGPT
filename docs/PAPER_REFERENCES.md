# DecisionGPT Paper — Reference Verification Log

Companion to `docs/PAPER_DRAFT.md` §20. This log records how each reference was
checked and flags anything an author must confirm under the target venue's style.
It does not change any research result.

**Verification method.** Entries were located against the publisher page, the ACL
Anthology, arXiv, or a DOI/JSTOR registry page. DOIs shown resolve. Page ranges
and editions should be re-checked once a venue citation style is chosen.

## Status summary

| Bucket | Count | Notes |
|---|---|---|
| Verified (publisher / ACL / arXiv / DOI page located) | 39 | refs 1–39 in the draft |
| Previously flagged, re-checked this pass | 3 | Shmueli & Koppius 2011; Granger 1969; Wilcoxon 1945 — all confirmed |
| Added this pass (India MSME motivation) | 1 | Buteau 2021 (ref 39) — verified via Springer / PMC |
| Optional candidates for the authors to confirm | 4 | a *second* India MSME source; Runge 2019; Makridakis 2020; Huber & Ronchetti 2009 — cited only as "candidate additions", not in the numbered list |
| Fabricated / unverifiable | 0 | — |

## Re-checked this pass

| # | Reference | Field checked | Result |
|---|---|---|---|
| 3 | Shmueli, G., & Koppius, O. R. (2011). *Predictive Analytics in Information Systems Research.* MIS Quarterly, 35(3), 553–572. | authors, title, venue, vol/iss, pages, DOI | **Confirmed.** DOI 10.2307/23042796; publisher page misq.umn.edu/misq/article/35/3/553 (published 1 Sep 2011); AIS eLibrary aisel.aisnet.org/misq/vol35/iss3/5. |
| 19 | Granger, C. W. J. (1969). *Investigating Causal Relations by Econometric Models and Cross-spectral Methods.* Econometrica, 37(3), 424–438. | authors, title, venue, vol/iss, pages, DOI | **Confirmed.** Econometric Society; RePEc `ecm:emetrp:v:37:y:1969:i:3:p:424-38`; JSTOR stable 1912791; DOI 10.2307/1912791. |
| 32 | Wilcoxon, F. (1945). *Individual Comparisons by Ranking Methods.* Biometrics Bulletin, 1(6), 80–83. | author, title, venue, vol/iss, pages, DOI | **Confirmed.** International Biometric Society; JSTOR stable 3001968; December 1945; DOI 10.2307/3001968 resolves via CrossRef (302 → jstor.org/stable/10.2307/3001968?origin=crossref). |

## Added this pass — India MSME motivation (Section 1)

| # | Reference | Field checked | Result | Claim it supports |
|---|---|---|---|---|
| 39 | Buteau, S. (2021). *Roadmap for digital technology to foster India's MSME ecosystem — opportunities and challenges.* CSI Transactions on ICT, 9(4), 233–244. DOI 10.1007/s40012-021-00345-4. | author, title, venue, vol/iss, pages, DOI, access | **Confirmed.** Springer Nature; open access via PMC (PMC8662980). | Section 1: "a large share of activity [in the Indian MSME sector] is informal, with limited financial records and little credit history, which impedes formal data integration and digital adoption." The article states informal micro-enterprises account for ~80% of employment / ~20% of output and that limited financial records and lack of credit history impede formal lending access and digital integration — the cited claim is within scope. Used as **motivation only**, not as evidence about DecisionGPT. |

## Candidate additions (not in the numbered list; authors to confirm before use)

- A peer-reviewed Indian MSME digital-adoption study as a *second* India source —
  e.g. *Information Technology for Development* 31(4) (2025), "Fostering
  competitiveness of Indian MSMEs through IT and digitalization",
  doi:10.1080/02681102.2025.2453211 (mixed-methods: 14 interviews + 321 MSMEs;
  TOE framework; barriers include infrastructure, skills, awareness). Publisher
  abstract page returned HTTP 403 during preparation; author list and pages were
  not fully confirmed — **verify before citing**.
- Runge, J., et al. (2019). *Detecting and quantifying causal associations in
  large nonlinear time series datasets.* Science Advances, 5(11), eaau4996 —
  optional, for time-series causal-discovery limitations. *Verify.*
- Makridakis, S., et al. (2020). *The M4 Competition.* International Journal of
  Forecasting, 36(1), 54–74 — optional, statistical vs ML forecasting baselines.
  *Verify.*
- Huber, P. J., & Ronchetti, E. M. (2009). *Robust Statistics* (2nd ed.). Wiley
  — optional, for the 1.4826 MAD consistency factor. *Verify.*

## Claim–citation spot audit (higher-risk statements)

| Draft statement | Cited as | Verdict |
|---|---|---|
| "a single agent with a strong prompt can match multi-agent discussion" | Wang et al. 2024 | Supported — this is the paper's stated finding. |
| "multi-agent debate is hyperparameter-fragile and does not reliably beat self-consistency" | Smit et al. 2024 ("Should we be going MAD?") | Supported. |
| "language models do not reliably self-correct without an external signal" | Huang et al. 2024 | Supported. Used only as context in Related Work, not to prove the project's own round-2 observation. |
| "multi-agent systems exhibit characteristic failure taxonomies with often-minimal benchmark gains" | Cemri et al. 2025 | Supported. |
| "multi-agent debate has been reported to improve reasoning and factuality" | Du et al. 2023; Liang et al. 2024; Li et al. 2024 | Supported — the pro-side literature the paper qualifies (not endorses). |
| Digital *model* vs *twin* by automatic bidirectional data flow | Kritzinger et al. 2018 (+ Grieves & Vickers 2017) | Supported — this is the Kritzinger taxonomy. |
| "pairwise Granger … originator warned apparent causality can reflect omitted variables or slow sampling" | Granger 1969 | Supported — Granger's own stated caveat. |
| "difficulty of distinguishing direct from indirect (transitive) effects" | Spirtes et al. 2000 | Supported — attributed to Spirtes, not Granger (tightened this pass). |
| "observational association is not an interventional effect" | Pearl 2009 | Supported. |
| "multiple hypothesis tests without correction inflate false positives" | Benjamini & Hochberg 1995 | Supported. |
| "MAPE is degenerate near zero actuals" | Hyndman & Koehler 2006 | Supported. |
| "AI explanations do not, in general, raise complementary human–AI team performance" | Bansal et al. 2021 | Supported. |
| "r = Z/√N is a standard non-parametric effect size" | Fritz et al. 2012 | Supported; the draft also flags that this is a p-derived quantity and adds the rank-biserial (Kerby 2014). |
| "small p-values do not imply large or important effects" | Wasserstein & Lazar 2016 | Supported (ASA statement). |
| "designed studies give within-suite, not population, estimates" | Shadish, Cook & Campbell 2002 | Supported (external/ecological validity). |
| "pre-registration separates hypothesis generation from testing" | Nosek et al. 2018 | Supported; the risk study genuinely fixed its criteria before running. |
| "publication bias suppresses null results" | Rosenthal 1979 | Supported. |
| "SME digital-adoption barriers: cost, skills, data scarcity, uncertain ROI" | OECD 2021 | Supported; used as motivation only. |
| Indian MSME informality / limited records / credit-history gap | Buteau 2021 | Supported; motivation only. |
| Additive risk term in the objective is a recognised family; weighting is a design choice | García & Fernández 2015 | Supported (safe-RL taxonomy). |
| "1.4826·MAD is a robust scale with low Gaussian efficiency and a symmetry assumption" | Rousseeuw & Croux 1993 | Supported. |
| "extrapolation beyond observed inputs is an OOD-reliability concern" | Yang et al. 2024 | Supported (OOD-detection survey); the draft notes the implemented heuristic is a range-overshoot term, not a learned detector. |
| "LLM evaluators carry position/verbosity/self-enhancement bias" | Zheng et al. 2023 | Supported; used only for a *future* real-LLM arm. |

No citation in the draft is used to support a claim stronger than its source
permits. No project-specific frozen result is attributed to external literature
(see `docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md` §I / `docs/PAPER_LITERATURE_FOUNDATION.md` §I).
