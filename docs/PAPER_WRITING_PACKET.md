# DecisionGPT — Paper Writing Packet

**Purpose.** A single authoritative brief for the paper author. It fixes the
framing, the title, the story order, the exact numbers, the required statistical
disclosures, and the exact scoped wording for each claim. It does **not** write
the paper and it introduces **no** new results.

**Companion documents (read alongside this):**

- `docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md` — evidence matrices, claim matrix,
  forbidden-claims list, table/figure plans, reviewer attack surface.
- `docs/PAPER_LITERATURE_FOUNDATION.md` — the ~36 verified references and the
  citation map (the related-work section must still be written from these).
- `docs/STATISTICAL_ANALYSIS.md` — the exact aggregation / test definitions.
- `experiments/experiment_manifest.json` (16 experiments, sha256 `94aa419c…`) and
  `experiments/paper_results_snapshot.json` — the frozen source of every number.

**Immutable during paper writing.** 16 frozen experiments and their IDs; the
manifest and paper-results snapshot; all datasets and category assignments; the 6
active v1 / 3 archived v2 models; every existing metric; production **R0 / D0**
(`risk_model = None`, `risk_penalty_lambda = 1.0`); **R3 = PROMISING / NOT
PROMOTED**; real Indian SME outcomes **= 0**; `PredictionEvaluation` **= 0**;
Table 2 **= NOT READY**; real LLM **= BLOCKED** (`llm_enabled = False`);
`CAUSALLY_VALIDATED = 0`; Alembic head **0007**.

---

## 1. Framing (fixed)

**Central research question.**

> Does adding a multi-agent evaluation layer improve decision quality beyond a
> deterministic business decision-simulation layer?

Investigated through **controlled component-level evaluation**.

**Central finding (state exactly this).**

> In the tested configuration, the deterministic business decision-simulation
> layer was the only component that produced measurable objective value, while
> adding the implemented rule-based multi-agent evaluation layer substantially
> reduced simulated goal achievement.

**The finding applies only to:** the implemented architecture; deterministic
rule-based agents; the tested scoring configuration; the tested optimizer; the
tested 12-scenario suite.

**Do NOT generalize to:** multi-agent systems in general; LLM agents in general;
agent debate as a research paradigm; real-world SME decision making.

**Contribution category.** Primary: negative-result / controlled-evaluation.
Secondary: reproducibility; methodological (component isolation + confound
correction). It is **not** a methodological-novelty, empirical-real-world, or
systems/SOTA paper.

---

## 2. Title (fixed)

> **Does a Multi-Agent Layer Help? A Controlled Component-Level Evaluation of an
> Integrated Decision-Support Architecture for Data-Constrained SMEs**

Keep this title **only if** the abstract's first two sentences make the synthetic
evaluation scope unmistakable. Do not return to any title implying Indian-SME
validation, explainability validation, business improvement, real-world
superiority, or real-world decision effectiveness.

---

## 3. Research story (write in this order)

1. Integrated decision-support architecture.
2. Motivation: component complexity can obscure marginal value.
3. Controlled component-level evaluation.
4. 12 designed scenarios × 5 seeds.
5. Architecture comparison.
6. Decision simulation identified as the value-adding component.
7. Multi-agent layer produces a negative result.
8. Candidate-space confound discovered.
9. Correction performed.
10. Result reproduced byte-identically.
11. Mechanism diagnosis identifies the risk-penalty interaction.
12. Pre-registered R3 calibration study.
13. R3 promising on synthetic data but inert on the real Benroshan probe.
14. R3 not promoted.
15. Explicit lack of real SME outcomes / real LLM / human study.
16. Controlled-evaluation conclusion.
17. Reproducibility and future validation.

The story must **not** become "DecisionGPT successfully improves SMEs." That
thesis is not supported.

---

## 4. Primary result — exact numbers

Source: `experiments/paper_results_snapshot.json` Table 4 (experiment
`0e1bd8dc`, POST-correction; PRE-correction `675cf17e` is byte-identical),
seeds 42–46, 12 scenarios × 5 seeds = 60 paired `(scenario, seed)` observations
per arm.

| Architecture | Mean simulated goal achievement | 95% CI (Student-t) |
|---|---:|---|
| A — Prediction only | 0.0000 | [0.0000, 0.0000] |
| B — Prediction + Digital Twin (decision simulation) | **0.4856** | [0.4045, 0.5666] |
| C — Prediction + Digital Twin + Single Agent | 0.0025 | [0.0010, 0.0040] |
| D — Full DecisionGPT (adds multi-agent layer) | **0.0844** | [0.0125, 0.1564] |

**Primary comparison — D vs B (paired):**

- paired mean difference = **−0.4011**
- wins / ties / losses = **0 / 15 / 45**
- N_nonzero = **45** (all 45 favour B)
- Wilcoxon signed-rank, two-sided, `zero_method="wilcox"`: **p ≈ 4.8 × 10⁻⁹**
  (the snapshot stores `p_value = 0.0`; the value above is recomputed from the
  stored non-zero paired differences and is the number to print)
- reproduced **byte-identically** before and after the candidate-space correction

**Metric name.** Always "**simulated goal achievement**". Never "business
success", "business performance", "ROI", "real-world improvement", or "actual
outcome". State that it is an internally computed objective (attainment of each
scenario's own primary KPI from a simulated strategy output) on procedurally
generated scenarios.

**Secondary comparison — D vs A (paired), for completeness only:**
paired mean difference +0.0844; wins / ties / losses = 10 / 50 / 0;
**N_nonzero = 10**; p = 0.0045. Report N_nonzero next to it; do not headline it.

---

## 5. Robustness result (from stored observations — NOT a new experiment)

Recomputed from the stored `0e1bd8dc` `metrics_json` observations by excluding
the two scenarios (S04 `inventory_risk`, S07 `marketing_roi`) that use a
documented revenue proxy for a non-simulated KPI:

| D vs B | n pairs | wins / ties / losses | mean paired difference | Wilcoxon p |
|---|---:|---|---:|---:|
| All 12 scenarios | 60 | 0 / 15 / 45 | **−0.4011** | 4.8 × 10⁻⁹ |
| Excluding S04 & S07 | 50 | 0 / 15 / 35 | **−0.3904** | 2.2 × 10⁻⁷ |

Per-scenario mean goal achievement (B / D): S01 .42/.00, S02 .63/.00,
S03 .00/.00, S04 .50/.00, S05 .67/.00, S06 .25/.01, S07 .41/.00, S08 1.00/.00,
S09 .00/.00, S10 1.00/1.00, S11 .33/.00, S12 .63/.00. D < B in 9 of 12
scenarios; the 3 ties are S03/S09 (both 0) and S10 (both 1).

Present this as a **robustness analysis of already-stored observations**. Do not
re-run the pipeline.

---

## 6. Statistical presentation (required disclosures)

For **every** Wilcoxon comparison report: the test statistic where appropriate,
the p-value, **N_nonzero**, wins / ties / losses where useful, and the **paired
mean difference as the primary magnitude**.

Include, verbatim or close:

> "The 60 paired observations per arm derive from 12 designed scenario generators
> crossed with 5 seeds; observations within a generator are not independent. We
> therefore report paired comparisons on `(scenario, seed)` differences and do
> not interpret the confidence intervals as population estimates."

> "`goal_achievement` is bounded in [0, 1] and has substantial mass at the
> endpoints. The reported Student-t interval is a confidence interval for the
> sample mean within the evaluation suite, not a population or tolerance
> interval."

Also state: the scenarios are designed, not population-sampled; the paired
Wilcoxon is applied to `(scenario, seed)` differences; where all paired
differences are zero, "statistical significance not assessed" is reported
(never manufactured).

---

## 7. Effect-size correction (required)

The stored `effect_size_r` is computed as `|Z| / sqrt(N_nonzero)` with
`Z = Φ⁻¹(p/2)` — a transform of the p-value, **not** an independent effect-size
estimator.

- Keep the stored value only where traceability requires it, and state exactly
  how it was calculated.
- Add a proper **matched-pairs rank-biserial correlation** where feasible from
  stored data.
- **Lead with the paired mean difference** as the primary magnitude everywhere.

| Comparison | N_nonzero | Note |
|---|---:|---|
| D vs B | 45 | all 45 favour B; matched-pairs rank-biserial ≈ −1 in the direction D−B; stored `effect_size_r` = 0.8726 (p-derived, conservative here) |
| D vs A | 10 | stored `effect_size_r` = 0.8987 — do **not** call this a large practical effect |
| R3 vs R0 | 5 | stored `effect_size_r` = 1.00 — do **not** call this a large practical effect |

Use language such as:

> "Only 10 and 5 of 60 paired observations differ in these secondary
> comparisons; sign consistency should not be interpreted as a large practical
> effect. Mean paired differences provide the more interpretable magnitude."

**R3 vs R0 must be reported as:** mean paired difference **+0.083**,
CI **[0.019, 0.148]**, **p = 0.0253**, **5 / 55 / 0** (wins / ties / losses),
**5 of 60 non-zero pairs**. Do **not** round the paired mean difference to
+0.084.

---

## 8. Ablation section — exact numbers and wording

Source: `paper_results_snapshot.json` Table 5 (experiment `db58455b`), N = 60.

| Configuration | Mean simulated goal achievement | Δ vs Full |
|---|---:|---:|
| Full DecisionGPT | 0.0844 | — |
| Without Decision Simulation (Digital Twin) | 0.0000 | +0.0844 (95% CI [+0.0125, +0.1564]) |
| Without Causal Graph | 0.0844 | 0.0000 |
| Without Multi-Agent | 0.0844 | 0.0000 |
| Without Explainability | 0.0844 | 0.0000 |
| Without Memory | 0.0844 | 0.0000 |

State plainly:

> "Removing the decision-simulation layer collapses simulated goal achievement to
> zero; removing the other evaluated components leaves the objective unchanged
> under the tested deterministic configuration."

Explain the exact zeros so they are not mistaken for a null harness:

- The business-analyst and financial-advisor scores are near-constant across
  candidates in deterministic mode.
- Those components only feed those scores (or post-selection narration), so
  removing them cannot change which strategy the optimizer selects.
- Explanation and memory affect downstream or narrative signals, not the
  selected strategy.
- Removing the Causal Graph changes the internal confidence value
  (≈ 0.139 → 0.251) **without** changing the selected strategy or the objective.

Do **not** say the other components are useless in general.

---

## 9. Multi-agent result — exact wording

> "In the tested configuration—three rule-based agents with a two-round debate,
> deterministic scoring, and a fixed optimizer formula—adding the multi-agent
> evaluation layer on top of the Digital-Twin simulator did not improve mean
> simulated goal achievement and significantly reduced it (0.486 → 0.084; paired
> Wilcoxon p < 0.0001; 45 of 60 paired observations worse, none better). Trace
> analysis attributes the reduction to the optimizer's unbounded risk-penalty
> term operating over near-flat agent scores, rather than to an unequal
> candidate-strategy space, which was identified, corrected, and shown not to
> change the result."

Then, in the Discussion, explicitly:

> "We do not claim that multi-agent debate is unhelpful in general or that an
> LLM-based implementation would behave the same way."

---

## 10. Mechanism (risk) diagnosis — classification and numbers

**Classification: mechanism / diagnostic evidence inside the deterministic
pipeline.** NOT real-world causal evidence, causal proof, or a validated business
mechanism.

Source: experiment `ba56e42b` (`risk_manager_diagnostic`), N = 60 pairs / 390
strategy rows.

- Un-weighting the optimizer risk-penalty term (variant D1): mean simulated goal
  achievement **0.084 → 0.583**, paired Wilcoxon **p < 0.0001**.
- Risk Manager decisive on **75%** of pairs.
- **0 / 390** `RISK_SCORE_MISMATCH` (the Risk Manager transmits the Digital
  Twin's extrapolation-risk score without error).
- Optimizer formula `(BA+FA)/2 − λ·(1−RM)` verified on **390 / 390** rows.
- D1 **collapses confidence 0.139 → 0.018** and leaves risk-adjusted score
  negative — **D1 is not a production fix**.

Use the distinction:

> "The intervention isolates the proximate mechanism within the deterministic
> architecture, but does not establish a real-world causal mechanism."

---

## 11. R3 calibration — supplementary only

Source: experiment `b8516eef` (`risk_manager_calibration`), 7 variants × 60
pairs; pre-registration `docs/RISK_CALIBRATION_ANALYSIS.md` (formula, variants,
λ rule and 7 acceptance criteria fixed before the run).

- R0 mean simulated goal achievement = **0.084**; R3 = **0.168**.
- Paired difference (R3 − R0) = **+0.083**, CI **[0.019, 0.148]**, **p = 0.0253**.
- **5 / 60** non-zero pairs; wins / ties / losses = **5 / 55 / 0**.
- R3 risk-adjusted score −2614.8 → **+40.5**; confidence ≈ 0.109.
- R3 closes only **≈ 21%** of the D → B gap.
- Real-data probe (experiment `70617412`, Benroshan): **R0 = R1 on 184 / 184
  rows** — the low-variance pathology R3 targets does not occur; **R3 is inert**.
- Verdict: **PROMISING — NOT PROMOTED**; production stays **R0 / D0**; R3 remains
  **experimental**.

State:

> "R3 improves the synthetic objective on a small minority of pairs, but the
> effect is not validated on real Indian SME data and the variant is not promoted
> to production."

Do **not** call R3 an improved production model. Present it in an appendix or a
boxed supplementary sub-section.

---

## 12. Predictive model section — exact stored metrics (supporting evidence)

Label: **synthetic controlled evaluation** (`SYNTHETIC_CONTROLLED`,
`platform-forecasting-v1` / `platform-churn-v1`, seed 42, single-seed point
estimates — no CIs, no significance). Do **not** use the word "accuracy".
These tables are supporting evidence, not the primary contribution.

### Forecasting

| Model | MAE | RMSE | MAPE |
|---|---:|---:|---:|
| Naive | 24.66 | 38.28 | 15.46% |
| Linear | 17.29 | 25.51 | 12.49% |
| XGBoost | 15.14 | 21.86 | 10.30% |

### Churn / classification

| Model | F1 | ROC-AUC |
|---|---:|---:|
| Logistic Regression | 0.669 | 0.798 |
| Random Forest | 0.661 | 0.793 |
| XGBoost | 0.658 | 0.792 |

The separate Benroshan (`INDIA_REAL_BUSINESS`, archived v2) forecasting rows must
be reported with **MAPE omitted** (zero-actual days → 110–276%), labelled a
single small series, descriptive only, no significance.

---

## 13. Synthetic causal-method validation — exact numbers

Source: experiment `36d0d404` (`paper_causal`), synthetic ground-truth DAG
(A→B→C lag 1; D noise), seed 42.

- Precision = **0.40**, Recall = **1.00**, SHD = **3** (2 true positives
  {A→B, B→C}; 3 false positives {A→C transitive, B→A, D→B}; 0 false negatives).

Call this **synthetic causal-method validation**. Caption: pairwise Granger,
`max_lag = 3`, no multiple-comparison correction. State explicitly
`CAUSALLY_VALIDATED = 0`. This does **not** establish any real-world causal
effect.

---

## 14. Evidence Boundaries and Real-World Validation Status (dedicated section)

Section heading: **Evidence Not Yet Available** (or equivalent). Report:

- Real Indian SME outcomes = **0**
- `PredictionEvaluation` = **0**
- Table 2 (Digital Twin predicted vs actual) = **NOT READY**
- Real-LLM validation = **BLOCKED** (`llm_enabled = False`)
- Human study = **ABSENT**
- Real causal intervention evidence = **0**
- `CAUSALLY_VALIDATED` = **0**

State explicitly, and repeat in the abstract and conclusion:

> "The current study is a controlled component-level evaluation. It does not
> establish real-world Indian SME effectiveness, real LLM behaviour, human
> usability or explainability benefit, or real-world causal effects."

**Table 2** stays an explicit placeholder: "NOT READY — no real matched SME
outcomes are currently available." Never fill it with synthetic data, demo data,
Benroshan forecasts presented as outcomes, simulated actuals, or fabricated
business results. Never hide it — its absence is a finding.

---

## 15. Contributions section (restrained — use exactly this list)

1. A controlled component-level evaluation of an integrated decision-support
   architecture.
2. A reproduced negative result showing that the implemented multi-agent layer
   reduced simulated goal achievement under the tested deterministic
   configuration.
3. Quantification of marginal component contributions through paired ablation.
4. A documented confound-discovery and correction process whose corrected result
   reproduced the original finding.
5. A mechanism diagnosis linking the regression to the optimizer's risk-penalty
   interaction.
6. A reproducible evidence-traceability framework separating synthetic, real,
   blocked, and not-ready evidence.

Explicitly state what is **not** claimed: no new multi-agent algorithm; no new
causal-discovery algorithm; no new risk-calibration algorithm; no SOTA result;
no real SME validation; no LLM validation.

---

## 16. Abstract requirements

The abstract must state early: the evaluation is controlled; the scenarios are
synthetic / designed; real SME outcomes are unavailable; the main result is
**negative** for the implemented multi-agent configuration; decision simulation
provides the measurable objective contribution; **no real-world effectiveness
claim is made**.

Do not write an abstract implying successful SME deployment. Do not use
"accuracy" for the decision objective. Do not use "business success", "ROI", or
"validated for SMEs".

---

## 17. Paper structure

1. Abstract
2. Introduction
3. Research Question and Contributions
4. Related Work  *(write from `docs/PAPER_LITERATURE_FOUNDATION.md`; every
   citation real and verifiable; do not cite on title alone)*
5. System Architecture
6. Experimental Design
7. Predictive Model Evaluation
8. Controlled Architecture Evaluation
9. Component Ablation
10. Mechanism Diagnosis
11. Risk Calibration
12. Synthetic Causal-Method Validation
13. Evidence Boundaries and Real-World Validation Status
14. Discussion
15. Threats to Validity  *(from `docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md` §L)*
16. Reproducibility  *(commit, Python 3.12.0, corrected `requirements.txt`,
    seed 42, 16-experiment manifest; note the point-in-time doc-count staleness
    is cosmetic)*
17. Limitations
18. Future Work  *(real SME outcome collection — workflow ready; real-LLM arm —
    protocol frozen; AGMARKNET; repeated-seed CIs; a real intervention study; a
    human explainability study)*
19. Conclusion
20. References

---

## 18. Figures (≈ 4 primary; no decoration, no misleading axes)

1. Architecture comparison (mean simulated goal achievement per architecture with
   95% CI; overlay wins / ties / losses vs Full) — experiment `0e1bd8dc`.
2. Predictive performance (forecasting real and synthetic blocks side by side but
   separately scaled and labelled; no combined bar) — Table 1.
3. Component ablation (Δ vs Full per removed component, bars near zero except
   Decision Simulation, with CI on that bar; a second panel for the confidence
   effect of removing the Causal Graph) — experiment `db58455b`.
4. Risk calibration (R0 vs R1 risk score vs price-move size for constant /
   low-variance / normal-variance histories; and variant vs goal achievement /
   risk-adjusted) — experiment `b8516eef`; supplementary.

Do not create a figure of Digital-Twin predicted vs actual (0 real outcomes).
Never visually imply that synthetic results are real-world results.

---

## 19. Conference readiness (honest)

The evidence is sufficient for an international-conference submission **when
framed as a controlled component-level evaluation / negative-result /
reproducibility paper**.

- Evaluation / reproducibility track: **suitable**.
- Applied-AI / decision-support venue: **suitable**.
- Strong conference workshop: **plausible**.
- Top-tier main track: **substantially harder** without an external baseline or
  real-world validation.

No claim of guaranteed acceptance.

---

## 20. Remaining tasks for the paper author (not done here)

1. Write the paper prose to the structure in §17 and the story in §3.
2. Write Related Work from `docs/PAPER_LITERATURE_FOUNDATION.md` — every citation
   real and verifiable; no citation on title alone; add an India-MSME
   data-landscape source (still TODO).
3. Add the matched-pairs rank-biserial values (§7) alongside the stored
   `effect_size_r` where cited.
4. Produce the ≈ 4 figures in §18 from the frozen experiment data.
5. Draft the abstract to the §16 constraints.
6. Final read-through against the forbidden-claims list
   (`docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md` §M).
