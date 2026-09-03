# Does a Multi-Agent Layer Help? A Controlled Component-Level Evaluation of an Integrated Decision-Support Architecture for Data-Constrained SMEs

**Draft manuscript — venue formatting pending.** All quantitative results are
read from the frozen DecisionGPT experiment manifest
(`experiments/experiment_manifest.json`, `experiment_count = 16`, SHA-256
`94aa419c…`) and snapshot (`experiments/paper_results_snapshot.json`). No
experiment was run, re-run, or modified for this manuscript. Numbers that a
frozen record does not contain are marked *not available*.

---

## Abstract

This paper reports a **controlled, synthetic-scenario evaluation** of an
integrated decision-support architecture; it does **not** evaluate the system on
real businesses, and no real small- or medium-enterprise (SME) decision outcomes
were available at any point in the study. Within that scope, we ask which
components of a goal-to-strategy decision-support pipeline carry measurable
value, and whether adding a rule-based multi-agent evaluation layer improves
simulated decision quality beyond a deterministic business decision-simulation
layer. Using a pre-registered design of 12 deliberately constructed scenarios
crossed with 5 random seeds (60 paired observations per configuration), we find
that the decision-simulation layer is the only component that raises a simulated
goal-attainment metric (from a mean of 0.000 for a prediction-only pipeline to
0.486 with the simulation layer), and that adding the implemented three-agent
rule-based evaluation layer on top of it **reduces** the metric to 0.084 (paired
Wilcoxon signed-rank p < 10⁻⁴; 45 of 60 paired observations worse, none better;
mean shift −0.401, 95% CI [−0.478, −0.324]). A component ablation attributes the
entire measurable objective effect to the simulation layer; removing the
association-graph, multi-agent, explanation, or memory components changes the
objective by exactly 0.000. Trace analysis localises the degradation to the
optimizer's unbounded risk-penalty term acting on a mis-scaled
extrapolation-risk heuristic: neutralising that single term recovers the metric
to 0.583, and the term is decisive in 75% of paired cases (0/390 risk-score
transmission errors). A pre-registered recalibration of the risk heuristic
improves the synthetic metric to 0.168 (mean shift +0.083, p = 0.025, 5 of 60
non-zero pairs) but is inert on the one real Indian price dataset available and
is **not adopted**; production retains the original configuration. Predictive
sub-components (forecasting, churn) and a synthetic causal-recovery method
validation behave as expected on their datasets. We make no claim of real-world
effectiveness, no real-LLM evaluation was performed, and no causal effect is
established (`CAUSALLY_VALIDATED = 0`). The contribution is a reproducible
component-level evaluation protocol, a mechanism-diagnosed negative result for
the tested multi-agent configuration, and an evidence-boundary framework that
separates controlled synthetic evidence from the real-world validation that
remains future work. The full manifest, data-category separation, and clean-room
reproduction are released.

**Keywords:** decision-support systems; prescriptive analytics; controlled
evaluation; component ablation; multi-agent systems; negative results;
simulation-based decision support; risk-aware optimization; reproducibility;
pre-registration

---

## 1. Introduction

Small and medium enterprises (SMEs) operate under acute data constraints —
limited historical records, no analytics staff, and uncertain returns on
analytics investment [OECD 2021]. Business-intelligence and predictive-analytics
tools describe what happened and forecast what may happen, but stop short of
recommending an action toward a stated goal; prescriptive analytics names this
gap and its reviews note a persistent shortage of controlled empirical
evaluation of end-to-end pipelines [Lepenioti et al. 2020; Arnott & Pervan 2014;
Shmueli & Koppius 2011].

A common response is to compose more capability into one architecture:
forecasting, what-if simulation, risk scoring, contextual or causal information,
memory, explanation, and — increasingly — multiple reasoning agents that debate
a recommendation. Multi-agent debate has been reported to improve reasoning and
factuality on question-answering and reasoning benchmarks [Du et al. 2023; Liang
et al. 2024; Li et al. 2024]. A growing counter-literature, however, finds that
added agents do not reliably help: a single agent with a strong prompt can match
multi-agent discussion [Wang et al. 2024], multi-agent debate is
hyperparameter-fragile and does not reliably beat self-consistency [Smit et al.
2024], language models do not reliably self-correct without an external signal
[Huang et al. 2024], and multi-agent systems exhibit characteristic failure
modes with often-minimal benchmark gains [Cemri et al. 2025]. This debate has
been conducted almost entirely on reasoning benchmarks, not on a
decision-selection task with a simulator in the loop.

This paper takes that setting as its object of study. We do **not** claim that
the integrated system improves outcomes. We ask, under controlled conditions,
**where the value inside such an architecture comes from**, and specifically
whether a multi-agent evaluation layer adds value beyond a deterministic
decision-simulation layer. All decision-quality evidence in this paper is from
designed synthetic scenarios; there are zero real SME decision outcomes; the
real-LLM configuration was unavailable and is reported as *blocked*; and no
human study was conducted. These boundaries are stated here, repeated in
Section 15, and treated as first-class results rather than caveats.

**Positioning.** The contribution is a controlled component-level evaluation, a
reproduced and mechanism-diagnosed negative result for the tested deterministic
multi-agent configuration, and a reproducibility / evidence-boundary framework.
It is consistent with the negative multi-agent literature above and is offered
in that spirit — as evidence about architectural value, not as a validated
system.

---

## 2. Research Questions and Contributions

### 2.1 Research questions

- **RQ1.** Under controlled evaluation, what is the component-level contribution
  of each layer of an integrated goal-to-strategy decision-support architecture
  to a simulated goal-attainment metric?
- **RQ2.** Does adding a rule-based multi-agent evaluation layer improve
  simulated decision outcomes beyond a deterministic business
  decision-simulation layer?
- **RQ3 (supporting).** What mechanism within the implemented architecture
  explains any observed change when the multi-agent layer is introduced?

We deliberately introduce no research question that would require evidence not
already in the frozen record (e.g. real-world effectiveness, real-LLM behaviour,
human comprehension).

### 2.2 Contributions

1. **A controlled component-level evaluation protocol** for an integrated
   decision-support architecture: 12 designed scenarios × 5 seeds, paired per
   (scenario, seed), with pre-registered aggregation and paired non-parametric
   testing, a documented key-performance-indicator (KPI) proxy rule, and a
   candidate-space fairness control.
2. **A negative-result finding**: within this architecture and under the tested
   deterministic configuration, adding the multi-agent evaluation layer *reduced*
   the simulated goal-attainment metric relative to the prediction +
   decision-simulation configuration, across the paired evaluation (45 of 60
   paired observations worse, none better).
3. **A mechanism-level diagnosis** linking that degradation to the optimizer's
   unbounded risk-penalty term operating on a mis-scaled extrapolation-risk
   heuristic, rather than to an unequal strategy space (a candidate-space
   confound that we identified, corrected, and showed leaves the result
   unchanged to the recorded precision).
4. **A reproducibility and evidence-boundary framework** that separates
   controlled synthetic evaluation from unavailable real-world validation, with
   a 16-experiment manifest, a five-category data-governance rule, and explicit
   *NOT READY* / *BLOCKED* markers for real-outcome, real-LLM, and causal
   evidence.

We claim no new multi-agent algorithm, no new causal-discovery algorithm, no new
risk-calibration algorithm, no state-of-the-art result, no real-SME validation,
and no LLM validation.

---

## 3. Related Work

**Prescriptive analytics and decision-support systems.** Lepenioti et al. [2020]
define prescriptive analytics as goal-to-action support beyond descriptive and
predictive analytics and document a shortage of evaluation rigor. Arnott &
Pervan [2014], reviewing a large decision-support-systems literature, note
method-quality problems and the rise of design science. Shmueli & Koppius [2011]
distinguish explanatory from predictive modelling; we use this distinction to
keep method validation (forecasting error, causal recovery on synthetic ground
truth) separate from any causal or real-world claim.

**Simulation-based decision support and digital twins.** Grieves & Vickers
[2017] give the canonical digital-twin concept; Tao et al. [2019] survey the
field. Kritzinger et al. [2018] classify implementations by the degree of
*automatic* data integration: a *digital model* has no automatic data exchange,
a *digital shadow* has automatic one-way flow, and a *digital twin* has
automatic bidirectional flow. Jones et al. [2020] catalogue thirteen
characteristics and open problems including fidelity and validation. The
simulation component evaluated here runs on manually uploaded business data,
produces offline what-if projections, and has no automatic or return data path;
on the Kritzinger taxonomy it is a **digital model**. We therefore call it a
*business decision-simulation layer* throughout and reserve "twin" for the
system name only.

**Multi-agent and agent-debate systems.** The positive case: multi-agent debate
improving reasoning and factuality [Du et al. 2023]; judge-arbitrated debate
countering degeneration-of-thought [Liang et al. 2024]; sampling-and-voting
scaling with agent count [Li et al. 2024]. The critical case, which our result
joins: single strong-prompt agents matching multi-agent discussion [Wang et al.
2024]; fragility and non-dominance of multi-agent debate over self-consistency
[Smit et al. 2024]; unreliable intrinsic self-correction [Huang et al. 2024];
characteristic failure taxonomies and minimal gains [Cemri et al. 2025]. LLM
evaluators additionally carry position, verbosity, and self-enhancement bias
[Zheng et al. 2023], which is relevant to any future real-LLM arm. Our
architecture's agents are deterministic rule-based scorers with a fixed
two-round exchange arbitrated by an optimizer, structurally closest to the
arbitrated-debate pattern of Liang et al. [2024]; the decision-selection +
simulator setting is not covered by the benchmark-centred prior work.

**Risk-aware optimization.** The optimizer's additive risk term places it in the
"modify the optimality criterion" family of the safe-reinforcement-learning
taxonomy [García & Fernández 2015]; how heavily to weight such a term is a
recognised design axis. The recalibration study's robust scale uses a
median-absolute-deviation construction [Rousseeuw & Croux 1993], whose low
Gaussian efficiency and symmetry assumption we note as limitations. Penalising
inputs outside the observed range is an out-of-distribution-reliability concern
[Yang et al. 2024]; the implemented heuristic is a simple range-overshoot term,
not a learned detector.

**Causal discovery from observational data.** The association graph uses
pairwise Granger tests [Granger 1969], which cannot separate direct from
transitive effects and whose author warned that apparent causality can reflect
omitted variables or slow sampling. Constraint-based discovery and the
direct-versus-indirect problem are treated by Spirtes et al. [2000]; the
distinction between observational association and interventional effect by Pearl
[2009]; multiple-comparison inflation by Benjamini & Hochberg [1995]. We report
the graph as *evidence-labelled association*, validate the recovery method
against a known synthetic structure only, and record `CAUSALLY_VALIDATED = 0`.

**Forecasting methodology.** The naive / linear / gradient-boosted ladder and
the omission of the mean-absolute-percentage error on a series with zero-sales
days follow standard guidance [Hyndman & Koehler 2006; Chen & Guestrin 2016].

**Explainability.** Bansal et al. [2021] find that AI explanations do not, in
general, raise complementary human–AI team performance beyond the model signal;
Jacovi & Goldberg [2020] separate explanation faithfulness from plausibility.
The system generates a post-hoc narration that is not a decision input; we make
no explainability-benefit claim and ran no human study.

**Reproducibility, pre-registration, negative results.** The methodological
spine — a reproducibility crisis [Baker 2016], community reproducibility norms
[Pineau et al. 2021], pre-registration to separate hypothesis generation from
testing [Nosek et al. 2018], and the file-drawer bias against nulls [Rosenthal
1979] — motivates the manifest, the pre-registered recalibration study, and the
decision to report the negative result.

**Statistical method and validity.** We use the paired signed-rank test
[Wilcoxon 1945], report the r = Z/√N non-parametric effect size [Fritz et al.
2012] alongside the matched-pairs rank-biserial correlation [Kerby 2014], and
foreground effect magnitude over significance [Wasserstein & Lazar 2016]. The
four-way validity taxonomy and the external-validity limits of designed studies
follow Shadish, Cook & Campbell [2002].

**Novelty.** The integration of prediction, simulation, agents, and explanation
into one pipeline is not itself novel [Lepenioti et al. 2020], nor is any
individual component. The empirical contribution is a reproduced,
mechanism-diagnosed negative result for a multi-agent debate layer on a
decision-selection task with a simulator in the loop — a setting the existing
negative literature does not cover — together with a clean component-isolation
measurement and a controlled demonstration that a plausible alternative
explanation (an unequal strategy space) is not responsible.

---

## 4. System Architecture

DecisionGPT is a capability-gated pipeline. Given a natural-language goal and an
uploaded dataset, it produces a ranked recommendation with an internal
confidence value and a post-hoc explanation. The stages are:

1. **Goal specification.** A goal sentence is parsed into an objective
   (e.g. increase revenue, increase profit, increase sales), a primary KPI, a
   target percentage, and constraints. When an LLM is configured it performs
   this parse and the final narration only; every parsed field is re-validated
   against the data. All results in this paper were produced with no LLM
   configured (Section 15).
2. **Capability detection.** The system checks whether the uploaded data
   supports the requested objective. If required data is absent it returns an
   explicit insufficient-evidence result rather than a fabricated value.
3. **Strategy generation.** Goal-templated candidate strategies (pricing,
   marketing, inventory levers) are generated, gated by detected capabilities.
4. **Business decision-simulation layer.** For each candidate, a recursive
   forecast projects the KPI forward and an extrapolation-risk heuristic scores
   how far the candidate's input values lie outside the historically observed
   range. This layer is a *digital model* in the sense of Kritzinger et al.
   [2018]: it consumes manually loaded data and produces offline projections
   with no automatic or bidirectional data flow.
5. **Evidence-labelled association graph.** Pairwise Granger tests over the
   uploaded series build a directed graph whose edges carry heuristic evidence
   labels (assumed / observational / data-supported / causally-validated). Edge
   promotion is never automatic; in every experiment reported here the
   causally-validated count is zero.
6. **Rule-based multi-agent evaluation.** Three deterministic agents — a
   business analyst, a financial advisor, and a risk manager — score each
   candidate in [0, 1]. A fixed two-round structured exchange allows agents to
   revise scores. Agent scores are computed by rules, not by an LLM.
7. **Strategy optimizer.** Candidates are ranked by

   > **s = (BA + FA) / 2 − λ · (1 − RM)**   (Eq. 1)

   where BA, FA, RM ∈ [0, 1] are the business-analyst, financial-advisor, and
   risk-manager scores and λ is the risk-penalty weight. The production
   configuration (denoted **D0**) uses λ = 1 and no learned risk model
   (`risk_model = None`), abbreviated **R0/D0**.
8. **Explanation and memory.** A post-hoc narration is generated from the stored
   components; the decision and any later outcome are written to a memory store.
   Neither stage feeds back into the selection in Eq. 1.

The confidence value is a fixed product of internal factors (inter-agent
agreement, a risk factor, an evidence factor, and an uncertainty penalty). It is
reproducible from stored components but is **not** calibrated against any human
or outcome notion of confidence; we call it the *internal confidence*.

---

## 5. Experimental Design

**Configurations.** The architecture comparison evaluates four cumulative
configurations on identical inputs:

| Label | Configuration |
|---|---|
| A | Prediction only (forecast, no strategy mechanism) |
| B | Prediction + business decision-simulation layer |
| C | B + a single evaluation agent |
| D | B + the full three-agent rule-based evaluation layer (the production architecture) |

**Scenario–seed design.** Twelve scenarios (Section 6) are each instantiated
with five random seeds (42–46), producing a procedurally generated business per
(scenario, seed). Every configuration is evaluated on the identical generated
business, so observations are **paired** per (scenario, seed): 12 × 5 = 60
paired observations per configuration. The ablation (Section 12) uses the same
60-pair design across six configurations (full, and full minus each of five
components).

**Pre-registration.** The risk-recalibration study (Section 13) fixed its
formula, its variant set, its λ-selection rule, and seven acceptance criteria
before any recalibration run, following registered-report discipline [Nosek et
al. 2018]. The primary architecture comparison and ablation use the aggregation
and testing procedure specified in Section 10.

**Candidate-space fairness control.** An initial version of the strategy
generator omitted a price-increase lever for revenue and sales objectives, so
the simulation layer's preferred candidate was sometimes unavailable to the
agent layer. We added the lever, verified that the fraction of (scenario, seed)
pairs whose simulation-preferred strategy is present in the agent layer's
candidate set rose from 0.333 to 0.833 (missing-when-supported rate 0.500 →
0.000), and re-ran the architecture comparison, ablation, and diagnostic. The
corrected runs are byte-identical in every aggregate, confidence interval, and
p-value to the pre-correction runs (Section 11.4). All results in this paper use
the corrected runs.

**Determinism and provenance.** Every experiment uses seed 42 for its
non-scenario randomness, is recorded as a completed run in the manifest with an
identifier, dataset version, and model versions, and asserts that the active
model set is unchanged before and after.

---

## 6. Data and Scenario Construction

### 6.1 Designed scenarios (primary evidence)

The twelve scenarios are **deliberately constructed, not sampled** from a
population of businesses. Each fixes an industry label, a primary decision lever,
an objective, a primary KPI, and a target. They span pricing, marketing,
inventory, and conservative levers across apparel, electronics, grocery,
furniture, e-commerce, consumer-goods, regional-retail, and small-manufacturing
labels.

| ID | Label | Lever | Objective | Primary KPI | Target |
|---|---|---|---|---|---|
| S01 | Clothing retail — revenue via pricing | pricing | increase revenue | revenue | 12% |
| S02 | Clothing retail — profit via pricing | pricing | increase profit | profit | 12% |
| S03 | Electronics retail — sales via marketing | marketing | increase sales | orders | 15% |
| S04 | Grocery retail — inventory risk | inventory | reduce inventory risk | inventory risk (revenue proxy) | 10% |
| S05 | Furniture retail — high-ticket profit | pricing | increase profit | profit | 15% |
| S06 | E-commerce — revenue via marketing | marketing | increase revenue | revenue | 20% |
| S07 | Apparel e-commerce — marketing ROI | marketing | improve marketing ROI | marketing ROI (revenue proxy) | 15% |
| S08 | Consumer goods — thin-margin profit | inventory | increase profit | profit | 10% |
| S09 | Regional retail — price-sensitive sales | pricing | increase sales | orders | 12% |
| S10 | Small manufacturing — cost / profit | inventory | increase profit | profit | 8% |
| S11 | Mixed retail — revenue via marketing | marketing | increase revenue | revenue | 15% |
| S12 | Small e-commerce — conservative revenue | conservative | increase revenue | revenue | 8% |

**KPI proxy (S04, S07).** Two objectives — `reduce_inventory_risk` (S04) and
`improve_marketing_roi` (S07) — have no directly simulated KPI pair. For these,
attainment of the scenario's revenue movement is used as a documented proxy for
`goal_achievement`. These two scenarios are flagged in every trace and are
excluded in a robustness analysis (Section 11.3). Their `goal_achievement`
values are **not** genuine revenue-outcome observations.

### 6.2 Supporting datasets

| Dataset | Category | Real / synthetic | Use | Not used for |
|---|---|---|---|---|
| Platform forecasting (`platform-forecasting-v1`) | synthetic-controlled | synthetic | Forecasting sub-component evaluation (265 test rows, 1 seed) | Any real-world forecasting claim |
| Platform churn (`platform-churn-v1`) | synthetic-controlled | synthetic | Classification sub-component evaluation | Any real-world churn claim |
| Synthetic causal ground truth | synthetic-controlled | synthetic | Method validation of Granger recovery against a known graph | Any real causal claim |
| India e-commerce orders (Benroshan, `external-india-ecommerce-v1`) | real, **provenance unverified** | real | Descriptive analytics; a small forecasting reference (51 test days); a real-data risk-ordering probe (23 derived price sub-series, 184 rows) | Table 2 evidence; any representativeness or population claim; unit-price/elasticity analysis (price is derived as revenue ÷ units) |
| India festival calendar; policy repo-rate series | public context | real | Optional exogenous covariates | Targets; causal evidence |
| AGMARKNET agricultural wholesale prices | agricultural price | real | *Data pending* (not retrieved); integration present | Not SME retail data; not used in any result here |
| Real Indian SME decision outcomes | own category | real | Table 2 (when ≥ 5 matched records exist) | **0 records — nothing now** |

Categories are never averaged. The Benroshan raw file (which contains customer
first names) is excluded from every committed processed artifact.

---

## 7. Evaluation Metrics

- **Simulated goal achievement** — attainment of a scenario's own primary KPI
  computed from a simulated strategy output, in [0, 1]. For revenue/profit/orders
  objectives it is the realised fraction of the target movement; for S04 and S07
  it uses the revenue proxy above. It is a model-internal construct on a
  procedurally generated business, **not** realised business value.
- **Simulated risk-discounted benefit** — the projected benefit multiplied by
  one minus the simulation layer's extrapolation-risk score. It is dominated by
  the extrapolation-risk heuristic and can be negative even when the raw KPI
  movement is positive.
- **Internal confidence** — the fixed product of internal factors described in
  Section 4; reproducible from stored components, not human-calibrated.
- **Latency** — wall-clock seconds per decision.
- **Forecasting** — mean absolute error (MAE), root-mean-square error (RMSE),
  and, where actuals are non-degenerate, mean absolute percentage error (MAPE).
- **Classification (churn)** — precision, recall, F1, and area under the ROC
  curve (ROC-AUC). We do not report or refer to "accuracy" for these models.
- **Causal recovery** — precision, recall, F1, and structural Hamming distance
  (SHD) against a known synthetic graph.

---

## 8. Statistical Analysis

**Descriptive aggregation.** For each configuration and metric we report the
sample mean, median, and standard deviation (Bessel-corrected), and a Student-t
95% interval on the mean, `mean ± t_{0.975, n−1} · s/√n`. Because the scenarios
are *designed rather than sampled*, this interval describes sampling variability
**within the designed scenario suite**, not a population [Shadish et al. 2002;
Wasserstein & Lazar 2016].

**Paired comparison.** For each primary contrast we take per-(scenario, seed)
differences `d_i = x_i − y_i` and report: the paired sample size `n`; the number
of non-zero differences `N_nonzero` (tolerance 10⁻⁹); the mean and median paired
difference; the count of pairs favouring each side (wins / ties / losses); the
Wilcoxon signed-rank statistic and two-sided p-value (`zero_method = "wilcox"`,
no continuity correction); the r = Z/√N_nonzero effect size with `Z = Φ⁻¹(p/2)`
[Fritz et al. 2012]; and the matched-pairs rank-biserial correlation as the
proportion of favourable minus unfavourable non-tied pairs [Kerby 2014]. **We
lead with the mean paired difference as the interpretable magnitude** and never
report r alone [Wasserstein & Lazar 2016]. When all paired differences are
exactly zero the test is not defined and we state "significance not assessed"
rather than reporting a p-value.

**On the effect size r = Z/√N_nonzero.** This quantity is a monotone transform
of the p-value and `N_nonzero`; it is retained for traceability with the frozen
records but is **not** an independent effect-size estimate. Where `N_nonzero` is
small (Sections 11.2, 13) it saturates near 1 merely because the few non-tied
pairs agree in sign; we therefore also give the rank-biserial correlation and,
for the primary contrast, a bootstrap interval.

**Clustering.** The 60 paired observations per configuration derive from 12
scenario generators crossed with 5 seeds; observations within a generator are
**not independent**. We therefore also report a scenario-level analysis that
treats each scenario's mean as one unit (n = 12) for the primary contrast
(Section 11.3), and we do not interpret any interval as population inference.

**Bootstrap interval (primary contrast only).** From the 60 stored
per-(scenario, seed) differences for D − B we draw 20,000 paired bootstrap
resamples (seed 42) and report the 2.5–97.5 percentile interval of the resampled
mean. This is a re-analysis of frozen observations, not a new experiment.

---

## 9. Primary Results

### 9.1 Architecture comparison (experiment `0e1bd8dc`, N = 60 per configuration)

**Table 3 — Architecture comparison (simulated goal achievement).** Primary,
confirmatory. Synthetic. Student-t 95% intervals describe within-suite
variability.

| Config. | Mean | Median | SD | 95% CI | Mean simulated risk-discounted benefit | Internal confidence | Mean latency (s) |
|---|---:|---:|---:|---|---:|---:|---:|
| A — Prediction only | 0.0000 | 0.000 | 0.0000 | [0.0000, 0.0000] | 0.00 | n/a | 0.151 |
| B — + Decision Simulation | **0.4856** | 0.4584 | 0.3138 | [0.4045, 0.5666] | 2508.40 | n/a | 1.408 |
| C — + single agent | 0.0025 | 0.000 | 0.0057 | [0.0010, 0.0040] | 190.94 | n/a | 1.392 |
| D — Full (+ multi-agent) | **0.0844** | 0.000 | 0.2784 | [0.0125, 0.1564] | −2614.83 | 0.139 | 1.680 |

**Table 3b — Paired contrasts.** Primary, confirmatory.

| Contrast | n | N_nonzero | Mean paired diff | 95% CI (Student-t) | Wins/Ties/Losses | Wilcoxon p (two-sided) | r = Z/√N_nonzero | Rank-biserial |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| D − A | 60 | 10 | **+0.0844** | [0.0125, 0.1564] | 10 / 50 / 0 | 0.0045 | 0.899 | +1.00 |
| D − B | 60 | 45 | **−0.4011** | [−0.4783, −0.3239] | 0 / 15 / 45 | < 10⁻⁴ (recomputed 4.8 × 10⁻⁹) | 0.873 | −1.00 |

For D − B, a 20,000-sample paired bootstrap of the mean (seed 42) gives 95%
interval [−0.477, −0.327], in close agreement with the Student-t interval. The
simulation-only configuration B beats the full architecture on 45 of 60 paired
observations and is beaten on none. The full architecture's per-(scenario, seed)
distribution has best 1.000, worst 0.000, median 0.000, SD 0.278: it attains a
non-zero simulated goal achievement in only two of twelve scenarios.

### 9.2 Interpretation of the effect sizes

The D − B rank-biserial correlation of −1.00 means only that all 45 non-tied
pairs point the same way (B better); it is a boundary value driven by
sign-consistency, not a statement of practical size. The **interpretable
magnitude is the mean shift of −0.401 on a [0, 1] metric**, with a 95% interval
excluding zero by a wide margin under both the Student-t and bootstrap methods.
For D − A only 10 of 60 pairs differ, so the r = 0.90 there should likewise be
read as "the few non-tied pairs agree", with the +0.084 mean shift as the
magnitude; D is above A only because A has no strategy mechanism at all.

### 9.3 Scenario-level analysis and robustness (RQ1, RQ2)

Treating each scenario's mean as one unit (n = 12), the D − B difference is
negative in 9 scenarios, zero in 3 (S03, S09, S10 — configurations tie because
both score 0 in S03/S09 and both score 1 in S10), and positive in none; the mean
scenario-level difference is −0.401 with a 20,000-sample bootstrap 95% interval
of [−0.571, −0.235].

**Excluding the two KPI-proxy scenarios (S04, S07)** — a secondary analysis of
the frozen observations, not a new experiment — leaves n = 50 paired
observations, wins/ties/losses 0 / 15 / 35, mean paired difference −0.3904, and
Wilcoxon two-sided p ≈ 2.2 × 10⁻⁷. The headline degradation is therefore not an
artefact of the revenue-proxy scenarios.

### 9.4 Candidate-space correction

The pre-correction architecture run (`675cf17e`) and the post-correction run
(`0e1bd8dc`) are byte-identical in every reported aggregate, interval, and
p-value, despite the candidate-coverage rate rising from 0.333 to 0.833. The
negative D − B result is thus a scoring-rule effect, not a consequence of the
agent layer being unable to see the simulation layer's preferred strategy.

**Answering RQ1 and RQ2.** Within this controlled evaluation, the
decision-simulation layer is the component that carries the measurable objective
value (A → B raises the mean from 0.000 to 0.486); adding the implemented
rule-based multi-agent evaluation layer on top of it does not add value and
significantly reduces the simulated goal-achievement metric.

---

## 10. Component Ablation (experiment `db58455b`, N = 60 per configuration)

**Table 4 — Component ablation.** Primary, confirmatory. Synthetic.

| Configuration | Component removed | Mean simulated goal achievement | Δ vs Full | 95% CI of Δ | Internal confidence |
|---|---|---:|---:|---|---:|
| Full | — | 0.0844 | — | — | 0.139 |
| − Decision Simulation | decision-simulation layer | **0.0000** | +0.0844 | [0.0125, 0.1564] | n/a |
| − Association Graph | evidence-labelled association graph | 0.0844 | 0.0000 | — | 0.2512 |
| − Multi-Agent | rule-based multi-agent evaluation | 0.0844 | 0.0000 | — | 0.1321 |
| − Explanation | post-hoc explanation | 0.0844 | 0.0000 | — | 0.139 |
| − Memory | decision/outcome memory | 0.0844 | 0.0000 | — | 0.139 |

For the decision-simulation removal, the paired contrast has N_nonzero = 10,
wins/ties/losses 10 / 50 / 0, Wilcoxon two-sided p = 0.0045. For the other four
removals **every one of the 60 paired differences is exactly zero**, so
significance is not assessed.

**Why the exact zeros are credible, not a null harness.** In the deterministic
configuration the business-analyst and financial-advisor scores are near-constant
across candidates, so the strategy selected by Eq. 1 is governed by the single
risk term. The association-graph, multi-agent, explanation, and memory components
feed only those near-flat scores, the confidence value, or the post-hoc
narration; none of them changes which strategy Eq. 1 selects, so the objective is
unchanged to the recorded precision. The one measurable non-simulation effect is
that **removing the association graph raises the internal confidence value from
0.139 to 0.251** without changing the selected strategy or the objective;
removing the multi-agent layer moves the internal confidence slightly to 0.132.

We do not conclude that these components are without value in general — only that,
on this suite, under this deterministic configuration, they produce no measurable
change in the simulated goal-achievement metric.

---

## 11. Mechanism / Risk Diagnosis (experiment `ba56e42b`, 60 pairs / 390 strategy rows)

This section is **controlled mechanism / diagnostic evidence within the
implemented deterministic architecture**. It is not causal inference and not
real-world evidence. We distinguish three things: a *component ablation* removes
a module; a *mechanism diagnosis* toggles one term inside a module and measures
the change on the same inputs; *causal inference* would require interventions in
the world.

**Isolating the risk-penalty term.** Let D1 denote the full architecture with the
risk-penalty term in Eq. 1 un-weighted (λ = 0) while the risk manager still runs
and still feeds the confidence value. On the identical 60 (scenario, seed) pairs:

| Metric | D0 (Full, λ = 1) | D1 (λ = 0) |
|---|---:|---:|
| Simulated goal achievement (mean) | 0.0844 [0.0125, 0.1564] | **0.5834** [0.4692, 0.6976] |
| Median | 0.000 | 0.7582 |
| Internal confidence (mean) | 0.139 | **0.0184** |
| Simulated risk-discounted benefit (mean) | −2614.83 | −2521.95 |

Paired D1 − D0 on simulated goal achievement: n = 60, N_nonzero = 35,
wins/ties/losses 35 / 25 / 0, mean paired difference **+0.4989** (95% CI
[0.3827, 0.6152]), Wilcoxon two-sided p < 10⁻⁴, rank-biserial +1.00.

**Supporting checks.** (i) Equation 1 is verified to hold exactly on all 390
recorded strategy rows (maximum deviation 0.0). (ii) The risk manager disagrees
with the simulation layer's preferred strategy on all 60 pairs. (iii) Removing
only the risk-penalty term changes the selected strategy on 45 of 60 pairs
(75.0%): 35 of those changes improve the metric, 0 degrade it, 10 are neutral.
(iv) There are 0 risk-score transmission errors in 390 rows — the risk manager
faithfully passes through the simulation layer's extrapolation-risk score; it is
not independently mis-scoring.

**Reading.** The intervention isolates the proximate mechanism *within the
deterministic architecture*: the unbounded `−λ(1 − RM)` term, acting on an
extrapolation-risk heuristic that is large for modest price moves because the
generated histories hold price nearly constant, drives the optimizer away from
the simulation layer's preferred strategy. It does **not** establish a real-world
mechanism, and D1 is **not** a usable configuration: it removes risk management
entirely, collapses the internal confidence value to 0.018, and leaves the
simulated risk-discounted benefit negative. **Answering RQ3:** the degradation is
a scoring-rule interaction between near-flat agent scores and an unbounded,
mis-scaled risk penalty.

---

## 12. Risk-Heuristic Recalibration (experiment `b8516eef`) — supplementary

This is a **pre-registered** study (formula, seven variants, λ-selection rule,
and seven acceptance criteria fixed before running). It is **supplementary**;
production is unchanged.

**Table 6 — Risk-heuristic recalibration variants.** Supplementary, pre-registered.
Synthetic. `R0` is the production configuration.

| Variant | Definition | Mean simulated goal achievement | 95% CI | Simulated risk-discounted benefit | Internal confidence | Pre-registered verdict |
|---|---|---:|---|---:|---:|---|
| R0 | production (`extrapolation_range` scale, λ = 1) | 0.0844 | [0.0125, 0.1564] | −2614.83 | 0.139 | baseline |
| R1 | robust (MAD-based) scale only | 0.0844 | [0.0125, 0.1564] | −2263.03 | 0.1414 | no satisfactory calibration |
| R2-0.25 | bounded penalty weight λ = 0.25 only | 0.1678 | [0.0708, 0.2647] | −2614.83 | 0.1087 | promising |
| R2-0.50 | λ = 0.50 only | 0.0844 | [0.0125, 0.1564] | −2614.83 | 0.139 | no satisfactory calibration |
| R2-0.75 | λ = 0.75 only | 0.0844 | [0.0125, 0.1564] | −2614.83 | 0.139 | no satisfactory calibration |
| **R3** | robust scale + λ = 0.25 | **0.1678** | [0.0708, 0.2647] | **+40.50** | 0.1087 | **promising — not promoted** |

Paired **R3 − R0** on simulated goal achievement: n = 60, **N_nonzero = 5**,
wins/ties/losses **5 / 55 / 0**, mean paired difference **+0.083** (95% CI
[0.0113, 0.1553]), Wilcoxon two-sided p = **0.0253**, r = Z/√N_nonzero = 1.00,
rank-biserial +1.00. Only 5 of 60 pairs change; the r = 1.00 reflects that those
five agree in sign, and the interpretable magnitude is the +0.083 mean shift. R3
closes approximately 21% of the D0 → B gap in simulated goal achievement
[(0.1678 − 0.0844) / (0.4856 − 0.0844)].

**Real-data probe (experiment `70617412`).** On the Benroshan implied-price data
(23 derived sub-series, 184 rows, price-variance regimes: 3 low / 11 moderate /
9 high), the production scale (R0) and the robust scale (R1) produce **identical**
extrapolation-risk scores on all 184 rows; Spearman ρ between move-distance and
risk is 0.9892 for both; there are 0 monotonicity violations for both; and 82.2%
of the 45 extreme out-of-range probes remain penalised at or above the 0.15
threshold under R1. The low-variance degeneracy that R3 targets **does not occur**
on this real series (a real implied-price series spans a wide min–max, so the R0
denominator never collapses), so R3's central benefit could not be assessed
there. A single materialised business (307 daily observations, treated as one
unit — no inferential test) selects the same strategy under every variant.

**Verdict.** R3 improves the synthetic metric on a small minority of pairs; the
effect is **not validated on real Indian SME data**; R3 is **not promoted**; the
production configuration remains R0/D0. This is a pre-registered diagnosis, not a
validated improvement.

---

## 13. Predictive Supporting Results

These are **supporting predictive benchmarks on synthetic evaluation data**,
single-seed point estimates with no confidence intervals and no significance
tests. They are not the contribution and imply nothing about business
performance. We do not use the term "accuracy".

**Table 5 — Predictive sub-component metrics.** Supporting. Point estimates (seed 42).

*Forecasting — synthetic-controlled (`platform-forecasting-v1`, 265 test rows):*

| Model | MAE | RMSE | MAPE |
|---|---:|---:|---:|
| Naive | 24.6597 | 38.2751 | 15.4647% |
| Linear | 17.2913 | 25.5112 | 12.4894% |
| XGBoost | 15.1389 | 21.8631 | 10.2969% |

*Forecasting — real, provenance-unverified (Benroshan, 51 test days):* Naive
MAE 19.92 / RMSE 31.25; Linear 18.47 / 28.51; XGBoost 15.27 / 23.89. **MAPE is
omitted**: the series has zero-sales days, on which MAPE is degenerate (observed
110–276%) [Hyndman & Koehler 2006]. This is a single small series, reported
descriptively, with no significance and no representativeness claim.

*Classification (churn) — synthetic-controlled (`platform-churn-v1`):*

| Model | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|
| Logistic regression | 0.7076 | 0.6337 | 0.6686 | 0.7978 |
| Random forest | 0.7125 | 0.6172 | 0.6614 | 0.7928 |
| XGBoost | 0.6990 | 0.6209 | 0.6576 | 0.7922 |

**Causal-recovery method validation (experiment `36d0d404`).** Against a known
synthetic graph (A→B→C at lag 1; D an independent noise series), pairwise Granger
recovery with maximum lag 3 and **no multiple-comparison correction** gives
precision 0.40, recall 1.00, F1 0.571, SHD 3 (true positives A→B, B→C; false
positives A→C, B→A, D→B; no false negatives). This validates the *recovery
method* against a known structure only. It does not establish any real-world
causal relationship; the false positives are the expected transitive and reverse
edges of a weak pairwise method [Spirtes et al. 2000; Benjamini & Hochberg 1995;
Granger 1969], and the deployed system's causally-validated edge count is 0.

---

## 14. Evidence Boundaries and Real-World Readiness

The following are reported as **results**, not caveats.

| Evidence | Status |
|---|---|
| Real SME decision outcomes | **0** records |
| Matched prediction evaluations | **0** records |
| Table 2 — real-world decision-outcome validation | **NOT READY** |
| Real-LLM evaluation | **BLOCKED** |
| Human / user study | **not conducted** |
| Real interventional causal evidence | **0**; `CAUSALLY_VALIDATED = 0` |
| Business ROI / financial-impact evidence | **none** |
| External / commercial system baseline | **none** |

**Table 2 — Real-world decision-outcome validation: NOT READY.** No real SME
decision outcomes or matched post-decision observations were available at the
time of evaluation (the readiness threshold is ≥ 5 genuine matched records;
current count 0). Consequently no real-world validation result is reported, and
no synthetic or simulated observation is substituted. Collection of these
records is future work (Section 18).

**Real LLM.** No LLM provider was configured (`llm_enabled = false`, provider and
model both empty). The implemented multi-agent result is a **rule-based
deterministic evaluation**, not an LLM experiment. We do not report LLM outputs,
prompts, token counts, latency, or judge scores, and we make no claim about how a
real LLM would behave. A frozen real-LLM evaluation protocol exists as future
validation infrastructure; the LLM, when configured, affects goal parsing and
final narration only, not the agent scores or the selection in Eq. 1.

---

## 15. Discussion

**What the study establishes.** Under a controlled, paired, pre-registered
evaluation on 12 designed scenarios and 5 seeds, the business decision-simulation
layer is the only component that raises the simulated goal-achievement metric,
and adding the implemented rule-based multi-agent evaluation layer on top of it
reduces that metric — across the paired evaluation, with 45 of 60 paired
observations worse and none better, robust to excluding the two KPI-proxy
scenarios and to a scenario-level analysis, and unchanged by a candidate-space
correction. The proximate mechanism, within the deterministic architecture, is
the optimizer's unbounded risk-penalty term operating on near-flat agent scores
and a mis-scaled extrapolation-risk heuristic.

**What the study does not establish.** It does not establish that multi-agent
reasoning or debate is generally harmful; that an LLM-based agent implementation
would behave the same way; that DecisionGPT is ineffective for real SMEs; that
the architecture would fail in production; that the findings generalise to
arbitrary businesses; or that real business outcomes would decline. All decision
evidence is synthetic and scenario-based, the agents are deterministic
rule-based scorers, the second exchange round is inert in this mode, and there
are zero real outcomes.

**Why the negative result is useful.** Component-level evaluation surfaces a
concrete, reproducible interaction — near-flat agent scores, the fixed optimizer
rule, and an unbounded risk-penalty term — that an aggregate "does the system
work" evaluation would hide. The result is consistent with a broader literature
finding that added agent layers do not reliably help [Wang et al. 2024; Smit et
al. 2024; Huang et al. 2024; Cemri et al. 2025] and extends that literature to a
decision-selection task with a simulator in the loop. It also has a constructive
reading for builders of such systems: a deterministic simulation layer can be
the load-bearing component, and a risk term added on top of it should be bounded
and scale-calibrated before more reasoning machinery is layered on. Reporting the
result, rather than filing it away, follows the norm against publication bias
toward positive findings [Rosenthal 1979].

**Terminology.** Consistent with Kritzinger et al. [2018], the simulation
component is a digital *model*, not a data-integrated digital twin; the graph
component is an *evidence-labelled association graph*, and we reserve "causal" for
the synthetic method validation; the agents are *rule-based* scorers; and
"validated" is used only where a frozen record supports it (nowhere for real SMEs,
R3, causality, or the LLM).

---

## 16. Limitations

We state what each limitation constrains rather than apologise for it.

- **Synthetic-only decision evaluation.** Every simulated-goal-achievement number
  is from a procedurally generated business. Constrains: external validity; no
  statement about real decision quality follows.
- **Designed, not sampled, scenarios (n = 12).** Constrains: no population
  inference; the Student-t and bootstrap intervals describe within-suite
  variability only.
- **Five seeds per scenario; clustered observations.** Constrains: the 60 paired
  observations are not independent; the scenario-level analysis (n = 12) is the
  conservative reading.
- **Deterministic template-mode agents; inert second round.** Constrains: the
  multi-agent finding is scoped to this configuration; an LLM-based
  implementation is untested and could differ.
- **No external system baseline.** Constrains: no superiority or comparative
  claim; the contribution is component isolation within one architecture.
- **Two revenue-proxy scenarios (S04, S07).** Constrains: their
  `goal_achievement` values are not genuine revenue outcomes; the robustness
  analysis excluding them is provided.
- **Bounded, endpoint-heavy objective.** Constrains: `goal_achievement` has mass
  at 0 and 1; the median of the full architecture's distribution is 0; t-based
  intervals are supplemented with a bootstrap for the primary contrast.
- **Low statistical power in secondary comparisons.** D − A and R3 − R0 have
  only 10 and 5 non-zero pairs; their r values are near-boundary and the mean
  shift is the interpretable quantity.
- **Zero real SME outcomes; Table 2 NOT READY.** Constrains: no real-world
  predictive-accuracy or effectiveness result exists.
- **Real-LLM evaluation BLOCKED.** Constrains: no claim about LLM-agent behaviour.
- **No human evaluation.** Constrains: no explainability, comprehension, or
  usability claim.
- **No real interventional causal evidence (`CAUSALLY_VALIDATED = 0`).**
  Constrains: the causal component is method validation on synthetic ground
  truth only.
- **Single real dataset, provenance unverified, n_businesses = 1.** Constrains:
  the real-data risk probe is descriptive with no inferential test.
- **Robust-scale limitations.** The MAD-based scale in R1/R3 has low Gaussian
  efficiency and assumes symmetry [Rousseeuw & Croux 1993]; the λ grid
  ({0.25, 0.50, 0.75}) is motivated but not exhaustively searched, by design.

---

## 17. Reproducibility and Research Integrity

- **Manifest.** 16 completed experiments, each with an identifier, seed 42,
  dataset version, and model versions; `experiments/experiment_manifest.json`,
  SHA-256 `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff`.
  The primary results table is machine-readable in
  `experiments/paper_results_snapshot.json` (four of five paper tables ready;
  Table 2 not ready).
- **Environment.** Python 3.12.0; the dependency set was corrected once during
  preparation because the previously pinned stack was uninstallable (a
  dependency required `numpy ≥ 2`); a clean-room rebuild reproduced the
  forecasting, churn, and causal-recovery numbers exactly.
- **Determinism.** `_summ` and `_paired` are pure functions of the stored
  observation arrays; re-running the aggregation on the same manifest yields
  identical numbers. A unit test checks `_summ` against a hand-computed
  mean/SD/interval and checks that the same (scenario, seed) reproduces the same
  generated business.
- **Production/research isolation.** The production decision path uses the
  default configuration (Eq. 1 with λ = 1, `risk_model = None`, i.e. R0/D0).
  Every non-default configuration (D1, R1, R2-λ, R3) is a research variant; no
  experiment promotes a model or changes the production configuration.
- **Data governance.** Five data categories (real, synthetic-controlled,
  synthetic-context, public-context, agricultural-price) are never averaged;
  real-SME-outcome material is admitted to Table 2 only at ≥ 5 genuine matched
  records; the real-LLM and causal-validation states are held at *BLOCKED* and
  `CAUSALLY_VALIDATED = 0`.
- **Historical documentation.** Some earlier internal reports carry
  point-in-time counts (e.g. "7 experiments", an earlier migration head, earlier
  test totals) from when they were written. The authoritative current state — 16
  experiments, the current schema head, and the current test total — is recorded
  in the manifest and the preparation report; the historical documents are
  preserved rather than rewritten. No experiment value was changed to reconcile
  them.

**Integrity statement.** No experiment was invented, re-run, re-seeded, or
modified for this manuscript; no scenario or score was changed; no real SME,
customer, human-subject, or LLM result was fabricated; Table 2 was not filled;
R3 was not promoted; and synthetic evidence was not relabelled as real. Where
evidence is unavailable, the paper says so.

---

## 18. Future Work

- **Real SME decision-outcome collection.** A consent-gated,
  provenance-checked, leakage-guarded import workflow exists; populating it to
  ≥ 5 matched records enables Table 2 and a real predictive-accuracy evaluation.
- **Real-LLM arm.** Run the frozen real-LLM protocol (identical inputs, LLM
  agent scoring and narration only) and compare against the rule-based
  configuration; account for LLM-evaluator bias [Zheng et al. 2023].
- **Repeated-seed intervals for the predictive sub-components** so forecasting
  and churn can be reported with confidence intervals rather than point
  estimates.
- **A real interventional study** for any causal claim; until then the graph
  remains an evidence-labelled association graph.
- **A human study** of the explanation component (comprehension, trust,
  decision quality).
- **Broader and sampled scenarios**, including generators with realistic price
  variation, to test whether the risk pathology is specific to
  near-constant-price histories.
- **An external-system comparison** to move beyond within-architecture
  component isolation.

---

## 19. Conclusion

On a pre-registered, controlled evaluation of 12 designed scenarios and 5 seeds,
a deterministic business decision-simulation layer is the only component of an
integrated decision-support architecture that raises a simulated
goal-achievement metric, and adding a rule-based multi-agent evaluation layer on
top of it reduces that metric (mean shift −0.401; 45 of 60 paired observations
worse, none better; p < 10⁻⁴), through an identified scoring-rule interaction
rather than an unequal strategy space. A pre-registered recalibration of the
risk heuristic is promising on the synthetic suite but inert on the one real
dataset and is not adopted. No real SME outcomes, real-LLM evaluation, human
study, or real causal evidence exists, and the paper makes no real-world
effectiveness, superiority, or generalisation claim. The contribution is a
reproducible component-level evaluation, a mechanism-diagnosed negative result
for the tested multi-agent configuration, and an evidence-boundary framework
that keeps controlled synthetic evidence separate from the real-world validation
that remains future work.

---

## 20. References

*Verified against publisher / ACL Anthology / arXiv / DOI-registry pages during
preparation. Authors should run a final bibliographic check (title, year, pages)
before submission, and must add and verify at least one India MSME
digitalization source for the motivation in Section 1 (currently a gap).*

1. Lepenioti, K., Bousdekis, A., Apostolou, D., & Mentzas, G. (2020).
   Prescriptive analytics: Literature review and research challenges.
   *International Journal of Information Management*, 50, 57–70.
   doi:10.1016/j.ijinfomgt.2019.04.003
2. Arnott, D., & Pervan, G. (2014). A critical analysis of decision support
   systems research revisited: the rise of design science. *Journal of
   Information Technology*, 29(4), 269–293. doi:10.1057/jit.2014.16
3. Shmueli, G., & Koppius, O. R. (2011). Predictive Analytics in Information
   Systems Research. *MIS Quarterly*, 35(3), 553–572. doi:10.2307/23042796
   *(verify)*
4. Grieves, M., & Vickers, J. (2017). Digital Twin: Mitigating Unpredictable,
   Undesirable Emergent Behavior in Complex Systems. In *Transdisciplinary
   Perspectives on Complex Systems*, Springer, 85–113.
   doi:10.1007/978-3-319-38756-7_4
5. Tao, F., Zhang, H., Liu, A., & Nee, A. Y. C. (2019). Digital Twin in Industry:
   State-of-the-Art. *IEEE Transactions on Industrial Informatics*, 15(4),
   2405–2415. doi:10.1109/TII.2018.2873186
6. Kritzinger, W., Karner, M., Traar, G., Henjes, J., & Sihn, W. (2018). Digital
   Twin in manufacturing: A categorical literature review and classification.
   *IFAC-PapersOnLine*, 51(11), 1016–1022. doi:10.1016/j.ifacol.2018.08.474
7. Jones, D., Snider, C., Nassehi, A., Yon, J., & Hicks, B. (2020).
   Characterising the Digital Twin: A systematic literature review. *CIRP
   Journal of Manufacturing Science and Technology*, 29, 36–52.
   doi:10.1016/j.cirpj.2020.02.002 *(verify page range)*
8. Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2023).
   Improving Factuality and Reasoning in Language Models through Multiagent
   Debate. arXiv:2305.14325. (ICML 2024.)
9. Liang, T., He, Z., Jiao, W., et al. (2024). Encouraging Divergent Thinking in
   Large Language Models through Multi-Agent Debate. *EMNLP 2024*, 17889–17904.
   ACL Anthology 2024.emnlp-main.992. arXiv:2305.19118
10. Li, J., Zhang, Q., Yu, Y., Fu, Q., & Ye, D. (2024). More Agents Is All You
    Need. *Transactions on Machine Learning Research*. arXiv:2402.05120
11. Wang, Q., Wang, Z., Su, Y., Tong, H., & Song, Y. (2024). Rethinking the
    Bounds of LLM Reasoning: Are Multi-Agent Discussions the Key? *ACL 2024
    (Long)*. ACL Anthology 2024.acl-long.331. arXiv:2402.18272
12. Smit, A. P., Grinsztajn, N., Duckworth, P., Barrett, T. D., & Pretorius, A.
    (2024). Should we be going MAD? A Look at Multi-Agent Debate Strategies for
    LLMs. *ICML 2024*, PMLR 235. arXiv:2311.17371
13. Huang, J., Chen, X., Mishra, S., et al. (2024). Large Language Models Cannot
    Self-Correct Reasoning Yet. *ICLR 2024*. arXiv:2310.01798
14. Cemri, M., Pan, M. Z., Yang, S., et al. (2025). Why Do Multi-Agent LLM
    Systems Fail? arXiv:2503.13657
15. Zheng, L., Chiang, W.-L., Sheng, Y., et al. (2023). Judging LLM-as-a-Judge
    with MT-Bench and Chatbot Arena. *NeurIPS 2023 Datasets & Benchmarks*.
    arXiv:2306.05685
16. García, J., & Fernández, F. (2015). A Comprehensive Survey on Safe
    Reinforcement Learning. *Journal of Machine Learning Research*, 16,
    1437–1480.
17. Rousseeuw, P. J., & Croux, C. (1993). Alternatives to the Median Absolute
    Deviation. *Journal of the American Statistical Association*, 88(424),
    1273–1283. doi:10.1080/01621459.1993.10476408
18. Yang, J., Zhou, K., Li, Y., & Liu, Z. (2024). Generalized Out-of-Distribution
    Detection: A Survey. *International Journal of Computer Vision*, 132(12),
    5635–5662. doi:10.1007/s11263-024-02117-4
19. Granger, C. W. J. (1969). Investigating Causal Relations by Econometric
    Models and Cross-spectral Methods. *Econometrica*, 37(3), 424–438.
    doi:10.2307/1912791 *(verify)*
20. Spirtes, P., Glymour, C., & Scheines, R. (2000). *Causation, Prediction, and
    Search* (2nd ed.). MIT Press. ISBN 978-0-262-19440-2
21. Pearl, J. (2009). Causal inference in statistics: An overview. *Statistics
    Surveys*, 3, 96–146. doi:10.1214/09-SS057
22. Benjamini, Y., & Hochberg, Y. (1995). Controlling the False Discovery Rate:
    A Practical and Powerful Approach to Multiple Testing. *Journal of the Royal
    Statistical Society: Series B*, 57(1), 289–300.
    doi:10.1111/j.2517-6161.1995.tb02031.x
23. Hyndman, R. J., & Koehler, A. B. (2006). Another look at measures of forecast
    accuracy. *International Journal of Forecasting*, 22(4), 679–688.
    doi:10.1016/j.ijforecast.2006.03.001
24. Chen, T., & Guestrin, C. (2016). XGBoost: A Scalable Tree Boosting System.
    *KDD '16*, 785–794. doi:10.1145/2939672.2939785. arXiv:1603.02754
25. OECD (2021). *The Digital Transformation of SMEs.* OECD Studies on SMEs and
    Entrepreneurship, OECD Publishing, Paris. doi:10.1787/bdb9256a-en
26. Bansal, G., Wu, T., Zhou, J., et al. (2021). Does the Whole Exceed its Parts?
    The Effect of AI Explanations on Complementary Team Performance. *CHI '21*.
    doi:10.1145/3411764.3445717
27. Jacovi, A., & Goldberg, Y. (2020). Towards Faithfully Interpretable NLP
    Systems: How Should We Define and Evaluate Faithfulness? *ACL 2020*,
    4198–4205. ACL Anthology 2020.acl-main.386
28. Baker, M. (2016). 1,500 scientists lift the lid on reproducibility. *Nature*,
    533(7604), 452–454. doi:10.1038/533452a
29. Pineau, J., Vincent-Lamarre, P., Sinha, K., et al. (2021). Improving
    Reproducibility in Machine Learning Research (A Report from the NeurIPS 2019
    Reproducibility Program). *JMLR*, 22(164), 1–20. arXiv:2003.12206
30. Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018). The
    preregistration revolution. *PNAS*, 115(11), 2600–2606.
    doi:10.1073/pnas.1708274114
31. Rosenthal, R. (1979). The file drawer problem and tolerance for null results.
    *Psychological Bulletin*, 86(3), 638–641. doi:10.1037/0033-2909.86.3.638
32. Wilcoxon, F. (1945). Individual comparisons by ranking methods. *Biometrics
    Bulletin*, 1(6), 80–83. doi:10.2307/3001968 *(verify)*
33. Fritz, C. O., Morris, P. E., & Richler, J. J. (2012). Effect size estimates:
    Current use, calculations, and interpretation. *Journal of Experimental
    Psychology: General*, 141(1), 2–18. doi:10.1037/a0024338
34. Kerby, D. S. (2014). The simple difference formula: An approach to teaching
    nonparametric correlation. *Comprehensive Psychology*, 3, 11.IT.3.1.
    doi:10.2466/11.IT.3.1
35. Wasserstein, R. L., & Lazar, N. A. (2016). The ASA's Statement on p-Values:
    Context, Process, and Purpose. *The American Statistician*, 70(2), 129–133.
    doi:10.1080/00031305.2016.1154108
36. Shadish, W. R., Cook, T. D., & Campbell, D. T. (2002). *Experimental and
    Quasi-Experimental Designs for Generalized Causal Inference.* Houghton
    Mifflin, Boston.
37. Directorate of Marketing & Inspection, Ministry of Agriculture & Farmers
    Welfare, Government of India. *AGMARKNET — Agricultural Marketing Information
    Network.* https://agmarknet.gov.in
38. Reserve Bank of India. *Database on Indian Economy (DBIE).* https://rbi.org.in

*Candidate additions requiring author verification before use:* Runge et al.
(2019, time-series causal discovery); Makridakis et al. (2020, M4 forecasting
competition); Huber & Ronchetti (2009, robust statistics); a Government of India
Ministry of MSME Annual Report and a peer-reviewed Indian MSME digital-adoption
study (for Section 1 motivation).

---

## Appendix A. Figure specifications

Figures are specified here rather than rendered; each uses only frozen data and
names its source experiment. If a figure cannot be produced faithfully from the
frozen record it must be left as a specification, not invented.

**Figure 1 — Architecture and evaluation decomposition.** A block diagram of the
pipeline (goal → capability detection → strategy generation → decision-simulation
layer → association graph → rule-based multi-agent evaluation → optimizer Eq. 1 →
explanation → memory), annotating which blocks are deterministic and where an
LLM, when configured, would act (goal parse and final narration only). Static;
no data.

**Figure 2 — Primary paired comparison (source: `0e1bd8dc`).** Left panel: mean
simulated goal achievement for configurations A, B, C, D with Student-t 95%
intervals. Right panel: the distribution of per-(scenario, seed) D − B
differences (60 points), with the 15 ties at zero and the 45 negative values
shown; overlay the mean (−0.401) and the bootstrap 95% interval [−0.477,
−0.327]. Caption states: designed scenarios, within-suite intervals, 0 wins / 15
ties / 45 losses.

**Figure 3 — Component ablation and risk-penalty mechanism.** Panel (a) (source:
`db58455b`): Δ simulated goal achievement versus Full for each removed component
— a single non-zero bar (decision simulation, +0.084, CI [0.013, 0.156]) and
four bars at exactly 0.000; a secondary axis shows the internal-confidence change
(association-graph removal 0.139 → 0.251). Panel (b) (source: `ba56e42b`): mean
simulated goal achievement for D0 (0.084) and D1 (λ = 0; 0.583) with 95%
intervals, annotated "risk manager decisive in 75% of pairs; 0/390 transmission
errors; D1 confidence collapses to 0.018 — not a usable configuration".

**Figure 4 — Risk recalibration and robustness (sources: `b8516eef`,
`0e1bd8dc`).** Panel (a): mean simulated goal achievement for R0, R1, R2-0.25,
R2-0.50, R2-0.75, R3 with 95% intervals and the pre-registered verdict labels;
annotate "R3 − R0 mean shift +0.083, 5 of 60 non-zero pairs, p = 0.025; not
promoted". Panel (b): the D − B mean paired difference computed on all 12
scenarios (−0.401) and excluding S04/S07 (−0.390), with bootstrap intervals, to
show the primary result is not driven by the two proxy scenarios.

---

## Appendix B. Forbidden-claim scan (author checklist for the final pass)

Every occurrence of the following terms in the manuscript was checked; the
approved usage is noted.

| Term | Approved usage in this draft | Prohibited usage (must not appear) |
|---|---|---|
| "validated" / "validation" | only "method validation" of causal recovery against synthetic ground truth; and negative forms ("not validated", "NOT READY", "BLOCKED") | real-SME validation; R3 validation; causal validation; LLM validation; production validation |
| "accuracy" | not used for any model metric (only "predictive-accuracy evaluation" as the name of a *future* activity in §18, and inside reference titles) | as a churn/forecasting metric label |
| "improves" / "improve" | only "improves the synthetic metric" / "raises the simulated goal-achievement metric", always with the synthetic qualifier; and RQ phrasing | improves SME decisions; improves outcomes; improves ROI |
| "superior" / "outperform" | not used | anywhere |
| "ROI" / "business impact" | only in §14/§16/§18 as *absent* evidence | as a result |
| "causal" | only for the synthetic method validation and the *association*-graph name (which explicitly avoids "causal") | real causal discovery; causal effect; causal validation |
| "LLM" | only to state it was not configured / not evaluated, and to describe future infrastructure | any reported LLM output or behaviour |
| "generalise" / "generalisation" | only in negative form ("we make no generalisation claim"; "does not generalise") | as a positive claim |
| "representative" | only "no representativeness claim" for Benroshan | as a positive claim |
| "customer behaviour" | not used (the synthetic customer dataset is not referenced as real behaviour) | describing synthetic data as real behaviour |

---

## Appendix C. Numerical consistency check (against frozen evidence)

| Quantity | Value in draft | Frozen source |
|---|---|---|
| Experiments | 16 | `experiment_manifest.json` `experiment_count` |
| Manifest SHA-256 | `94aa419c…` | file hash |
| A / B / C / D mean simulated goal achievement | 0.0000 / 0.4856 / 0.0025 / 0.0844 | `0e1bd8dc` aggregates |
| D − B mean paired diff / CI / W-T-L / N_nonzero / p | −0.4011 / [−0.4783, −0.3239] / 0-15-45 / 45 / <10⁻⁴ (4.8×10⁻⁹ recomputed) | `0e1bd8dc` paired `D_vs_B` |
| D − A mean paired diff / W-T-L / N_nonzero / p | +0.0844 / 10-50-0 / 10 / 0.0045 | `0e1bd8dc` paired `D_vs_A` |
| D − B excluding S04/S07 | n 50 / 0-15-35 / −0.3904 / p ≈ 2.2×10⁻⁷ | recomputed from `0e1bd8dc` observations |
| D − B bootstrap 95% CI | [−0.477, −0.327]; scenario-level (n=12) [−0.571, −0.235] | recomputed from `0e1bd8dc` observations, 20k resamples, seed 42 |
| Ablation Δ (decision simulation) / others | +0.0844 [0.0125, 0.1564] / exactly 0.000 | `db58455b` |
| Ablation internal confidence (assoc-graph removed) | 0.139 → 0.2512 | `db58455b` aggregates |
| D1 mean simulated goal achievement / CI | 0.5834 / [0.4692, 0.6976] | `ba56e42b` `d0_vs_d1` |
| D1 − D0 mean paired diff / CI / W-T-L / p | +0.4989 / [0.3827, 0.6152] / 35-25-0 / <10⁻⁴ | `ba56e42b` `paired_d1_minus_d0` |
| Eq. 1 verification / RM decisive / mismatch | 390/390 rows / 45 of 60 (75.0%), 35 improved 0 degraded 10 neutral / 0 of 390 | `ba56e42b` |
| D1 internal confidence / risk-discounted benefit | 0.0184 / −2521.95 | `b8516eef` D1 aggregates |
| R0/R1/R2-0.25/R2-0.50/R2-0.75/R3 mean simulated goal achievement | 0.0844 / 0.0844 / 0.1678 / 0.0844 / 0.0844 / 0.1678 | `b8516eef` aggregates |
| R3 simulated risk-discounted benefit / internal confidence | +40.50 / 0.1087 | `b8516eef` R3 aggregates |
| R3 − R0 mean paired diff / CI / W-T-L / N_nonzero / p | +0.083 / [0.0113, 0.1553] / 5-55-0 / 5 / 0.0253 | `b8516eef` `paired_vs_r0` R3 |
| R3 verdict | PROMISING — not promoted; production R0/D0 | `b8516eef` `verdict_by_variant`; `production_default` |
| Real-data probe: R0 == R1 rows / Spearman ρ / monotonicity violations / regimes | 184/184 / 0.9892 / 0 / 3 low, 11 moderate, 9 high | `70617412` `part_a_risk_regime` `overall`, `regime_counts` |
| Real-data probe: extreme probes penalised ≥ 0.15 under R1 | 82.2% of 45 | `70617412` `overall` |
| Real-LLM state | BLOCKED (`llm_enabled = false`) | `70617412` `part_c_real_llm` |
| Forecasting (synthetic) naive/linear/xgb MAE·RMSE·MAPE | as in Table 5 | `paper_results_snapshot.json` Table 1 |
| Churn (synthetic) P/R/F1/AUC | as in Table 5 | `paper_results_snapshot.json` Table 1 |
| Causal recovery precision/recall/F1/SHD | 0.40 / 1.00 / 0.571 / 3 | `36d0d404` / `paper_results_snapshot.json` Table 3 |
| Real SME outcomes / PredictionEvaluation / Table 2 / CAUSALLY_VALIDATED | 0 / 0 / NOT READY / 0 | `paper_results_snapshot.json`; database |
| Active / archived models | 6 / 3 — unchanged | database; manifest assertion |

---

## Appendix D. Author checklist

- **Paper complete:** YES — all 21 sections drafted with content (title, abstract,
  keywords, all sections, six tables, four figure specifications, one equation,
  statistical methodology, discussion, limitations, future work, conclusion,
  references).
- **All citations verified:** NO — 36 references were verified against
  publisher/ACL/arXiv/DOI pages during the literature phase; three carry a
  "verify" flag (Shmueli & Koppius 2011; Granger 1969; Wilcoxon 1945 DOIs) and
  an India MSME digitalization source for Section 1 is still required. Authors
  must complete these before submission.
- **Frozen evidence unchanged:** YES — no experiment, seed, score, manifest,
  model, or production configuration was modified; manifest SHA-256 unchanged;
  all draft numbers reconcile with the frozen records (Appendix C).
- **Statistical reporting complete:** YES — every paired contrast reports n,
  N_nonzero, mean paired difference, wins/ties/losses, Wilcoxon p, r = Z/√N with
  its caveat, and the rank-biserial; the primary contrast adds a bootstrap and a
  scenario-level analysis; CI construction and the clustering limitation are
  stated.
- **Table 2 explicitly NOT READY:** YES — Sections 14 and the Table 2 entry state
  0 records, the ≥ 5 threshold, and that no substitute is used.
- **Synthetic scope explicit in abstract:** YES — the first two sentences of the
  abstract state that the evaluation is controlled and synthetic and that no real
  SME outcomes were available.
- **No real-world / LLM claims fabricated:** YES — real-world effectiveness,
  ROI, superiority, generalisation, real causal effect, and LLM behaviour are
  all stated as absent; the real-LLM state is BLOCKED.
- **Forbidden-claim scan complete:** YES — Appendix B records the approved and
  prohibited usage of each sensitive term; a final read-through against it is
  listed as an author task.
- **Ready for venue formatting:** NO — the scientific content is complete and
  self-consistent, but before submission the authors must: (i) finish the
  citation verification and add the India MSME source; (ii) render Figures 2–4
  from the frozen data per Appendix A; (iii) apply the target venue's template,
  length limit, and citation style; (iv) run the Appendix B read-through on the
  final formatted text.
