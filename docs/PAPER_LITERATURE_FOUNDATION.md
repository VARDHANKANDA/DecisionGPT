# DecisionGPT — Literature Foundation & Citation Map

**Purpose.** External literature research for the DecisionGPT paper. This is **not**
the manuscript. It supplies a verified citation foundation so the paper can be
written without fabricated references or unsupported novelty claims.

**Paper positioning (fixed by the prior audit).** A controlled component-level
evaluation / negative-result / reproducibility study of an integrated
decision-support architecture for data-constrained SMEs. Central claim: *on a
controlled 12-scenario suite, deterministic Digital-Twin simulation is the only
component that improves goal achievement; adding a multi-agent debate layer
significantly reduces it, through an identifiable scoring-rule mechanism rather
than an unequal strategy space.*

**Verification.** Every reference in §J-1 was located this session via web search
against the publisher / ACL Anthology / arXiv / DOI-registry page named beside
it. DOIs are given where confirmed on the publisher page; otherwise an
arXiv ID or publisher URL is given. §J-2 lists **candidate** references that are
well known in the field but were **not** re-verified this session — the authors
must confirm bibliographic details and DOIs before use. No DOI in this document
was invented; do not cite a §J-2 entry without checking it.

**Frozen findings are unchanged.** Nothing here alters any experiment result,
seed, ID, dataset, model, production default, or verdict from
`docs/PAPER_EVIDENCE_AUDIT_AND_BLUEPRINT.md`. See §18 of that document / §I here
for the values that must never be attributed to prior literature.

---

## A. Literature landscape

### A.1 Where DecisionGPT sits

DecisionGPT combines strands that are each individually mature but rarely
integrated *and evaluated component-by-component*:

- **Prescriptive analytics / decision support** (Lepenioti et al. 2020; Arnott &
  Pervan 2014) — the field name for "goal → recommended action", and the source
  of the observation that most systems stop at prediction. DecisionGPT's
  goal→strategy→simulation→recommendation loop is a prescriptive-analytics
  architecture; the field's own reviews note a shortage of *controlled empirical
  evaluation* of such pipelines.
- **Digital twins / simulation-based decision support** (Grieves & Vickers 2017;
  Tao et al. 2019; Kritzinger et al. 2018; Jones et al. 2020) — the load-bearing
  component in DecisionGPT's results. The literature is explicit that most
  systems calling themselves "digital twins" are actually *digital models* or
  *digital shadows* by the data-integration criterion (Kritzinger et al. 2018);
  this directly informs the terminology recommendation (§E).
- **Multi-agent / LLM-agent decision systems** (positive: Du et al. 2023; Liang
  et al. 2024; Li et al. 2024. critical/negative: Wang et al. 2024; Smit et al.
  2024; Huang et al. 2024; Cemri et al. 2025; Zheng et al. 2023) — the component
  that *regresses* in DecisionGPT. There is a substantial and growing negative /
  "does it actually help?" literature; the DecisionGPT result is consistent with
  it, not anomalous.
- **Risk-aware / safe optimization** (García & Fernández 2015; Rousseeuw & Croux
  1993; Yang et al. 2024) — the optimizer's `(BA+FA)/2 − λ(1−RM)` is an additive
  risk term in the objective, exactly the "modify the optimality criterion"
  family in the safe-RL taxonomy; the calibration study's robust scale is a
  standard MAD-based robust-statistics construction.
- **Causal discovery from observational time series** (Granger 1969; Spirtes et
  al. 2000; Pearl 2009; Benjamini & Hochberg 1995) — the causal-graph method and
  its documented limitations (pairwise Granger cannot separate direct from
  transitive edges; no multiple-comparison correction; observational ≠
  interventional).
- **Forecast-accuracy methodology** (Hyndman & Koehler 2006; Chen & Guestrin
  2016) — the naive/linear/XGBoost ladder and the reason MAPE is omitted for the
  real series (degenerate near zero actuals).
- **Reproducibility, pre-registration, negative results** (Baker 2016; Pineau et
  al. 2021; Nosek et al. 2018; Rosenthal 1979) — the methodological spine of the
  paper.
- **Statistical inference for paired non-parametric comparisons** (Wilcoxon
  1945; Fritz et al. 2012; Kerby 2014; Wasserstein & Lazar 2016) — the exact
  tests and effect sizes used, and the caveats on interpreting them.
- **Validity of controlled / synthetic evaluation** (Shadish, Cook & Campbell
  2002) — the four-way validity taxonomy the Threats section uses; external /
  ecological validity for designed synthetic scenarios.
- **SME / MSME digitalization context** (OECD 2021; plus India-specific sources
  the authors must add) — motivation only, never a validation claim.

### A.2 The gap the paper addresses

Across prescriptive-analytics and digital-twin reviews, evaluation is dominated
by *case studies* and *does-it-work* demonstrations; component-level ablation
with pre-registered statistics is rare. Across the LLM-agent literature, the
positive and negative results are both largely on QA/reasoning benchmarks, not
on a decision-selection task with a simulator in the loop. DecisionGPT's
contribution is at that intersection: a reproducible testbed that isolates each
component's marginal objective value inside one architecture, plus a
pre-registered diagnosis of a risk-scoring failure mode.

---

## B. Key papers by research area

Full bibliographic details and identifiers in §J. This section states, per
area, **what the literature establishes** and **how the paper should use it**.

### B.1 Decision intelligence / prescriptive analytics / DSS
- **Lepenioti et al. (2020)** — defines prescriptive analytics, surveys methods,
  names the "predictive → prescriptive" gap and the shortage of evaluation
  rigor. *Use:* Introduction (problem framing) + Related Work.
- **Arnott & Pervan (2014)** — critical review of ~1,466 DSS papers; documents
  method-quality issues and the rise of design science. *Use:* Related Work +
  positioning DecisionGPT as a design-science artefact with an empirical
  evaluation.
- **Shmueli & Koppius (2011)** — the explanatory-vs-predictive-modeling
  distinction. *Use:* Methodology, to justify separating "predictive/structural
  method validation" (forecasting, causal recovery on synthetic ground truth)
  from any causal or real-world claim.

### B.2 Digital twins
- **Grieves & Vickers (2017)** — canonical DT definition (virtual construct
  mirroring a physical entity, bidirectional data flow at maturity). *Use:*
  Architecture / Related Work; and to show the implemented mechanism does *not*
  meet the full definition.
- **Tao et al. (2019)** — state-of-the-art DT survey, five-dimensional model.
  *Use:* Related Work.
- **Kritzinger et al. (2018)** — the **Digital Model / Digital Shadow / Digital
  Twin** taxonomy by degree of *automatic* data integration: Digital Model = no
  automatic data exchange; Digital Shadow = automatic one-way (physical →
  digital); Digital Twin = automatic bidirectional. *Use:* the central citation
  for the terminology recommendation (§E). DecisionGPT's simulation runs on
  manually uploaded business data with no automatic or bidirectional sync → it
  is, on this taxonomy, a **Digital Model** used for what-if simulation.
- **Jones et al. (2020)** — systematic DT review; 13 characteristics, research
  gaps incl. "twinning rate", fidelity, and the physical-to-virtual /
  virtual-to-physical connections. *Use:* Related Work + Limitations (fidelity
  and validation are unaddressed here).

### B.3 Multi-agent systems / LLM agents — the pro case (context to argue against)
- **Du et al. (2023)** — multi-agent debate improves factuality/reasoning on
  several benchmarks. *Use:* Related Work — the claim the paper's result
  qualifies.
- **Liang et al. (2024)** — multi-agent debate with a *judge* managing the
  process; improves on reasoning tasks; notes degeneration-of-thought without
  debate. *Use:* Related Work — closest structural analogue to DecisionGPT's
  optimizer-as-arbiter; the paper should note its result differs because the
  task is decision selection with a simulator, and agent scores are rule-based.
- **Li et al. (2024), "More Agents Is All You Need"** — sampling-and-voting
  scales with agent count on many tasks. *Use:* Related Work — the "more agents
  help" position; contrast with the budgeted-synergy and social-degradation
  findings.

### B.4 Multi-agent systems / LLM agents — the critical / negative case (primary support for the headline)
- **Wang et al. (2024, ACL), "Rethinking the Bounds of LLM Reasoning"** — a
  **single agent with a strong prompt matches the best multi-agent discussion**
  across reasoning tasks and backbones; multi-agent only helps without
  in-context demonstrations. *Use:* the strongest single citation that "adding
  agents need not add value"; Related Work + Discussion.
- **Smit et al. (2024, ICML), "Should we be going MAD?"** — multi-agent debate
  does **not reliably outperform** self-consistency / ensembling; gains are
  hyperparameter-sensitive and hard to optimize. *Use:* Related Work +
  Discussion — supports "the implemented configuration underperforms; MAD is
  fragile", and cautions against over-generalizing the negative result.
- **Huang et al. (2024, ICLR), "LLMs Cannot Self-Correct Reasoning Yet"** —
  intrinsic self-correction (no external signal) does not improve, and can
  degrade, reasoning. *Use:* explains why DecisionGPT's round-2 peer review is
  inert / non-beneficial in template mode.
- **Cemri et al. (2025), "Why Do Multi-Agent LLM Systems Fail?"** — MAST
  taxonomy: 14 failure modes in 3 categories (system-design, inter-agent
  misalignment, task verification) from 1,600+ traces; notes MAS often show
  "minimal performance gains" despite enthusiasm. *Use:* Related Work +
  Failure-Analysis framing — the DecisionGPT failure modes
  (`CANDIDATE_SET_MISMATCH` → `RISK_OVERRULE`) can be positioned relative to this
  taxonomy (system-design + verification categories).
- **Zheng et al. (2023, NeurIPS D&B), "Judging LLM-as-a-Judge"** — LLM
  evaluators exhibit position, verbosity and self-enhancement bias. *Use:*
  Future Work / Threats — relevant if the real-LLM arm ever replaces the
  rule-based agent scores; also supports keeping the scorer deterministic and
  auditable.

### B.5 Risk-aware optimization / robust scale / OOD
- **García & Fernández (2015)** — safe-RL survey; two families: (a) modify the
  optimality criterion with a risk/safety term, (b) modify exploration via a
  risk metric. *Use:* Risk Manager section — DecisionGPT's
  `final_score = (BA+FA)/2 − λ(1−RM)` is family (a); the λ study asks how heavily
  to weight that term, a recognized design question.
- **Rousseeuw & Croux (1993)** — MAD and alternatives as robust scale
  estimators: 50% breakdown, the 1.4826 normal-consistency constant, MAD's
  ~37% Gaussian efficiency. *Use:* Risk Calibration — supports using
  `1.4826·MAD` as a robust σ and *also* supports the caveat that MAD-based scale
  is low-efficiency and symmetric-distribution-oriented (a limitation of R1/R3).
- **Yang et al. (2024)** — generalized OOD-detection survey (anomaly / novelty /
  open-set / OOD / outlier). *Use:* Digital Twin / Risk Manager — frames
  "extrapolation beyond the observed input range" as an OOD-reliability concern;
  note DecisionGPT uses a simple range-overshoot heuristic, not a learned OOD
  detector.

### B.6 Causal inference
- **Granger (1969)** — the testable definition of predictive causality; explicitly
  warns that apparent instantaneous causality can arise from slow sampling or an
  omitted variable. *Use:* Causal Graph section — the method's origin and its
  own author's stated caveats.
- **Spirtes, Glymour & Scheines (2000)** — constraint-based causal discovery
  (PC); faithfulness assumption; equivalence classes; the general problem of
  distinguishing direct from indirect effects. *Use:* Causal Graph — situates
  pairwise Granger as a *weak* discovery method and explains the transitive
  false-positive (`A→C` when `A→B→C`).
- **Pearl (2009)** — do-operator; interventions vs observation; counterfactuals;
  direct/indirect effects. *Use:* the citation for "observational/synthetic
  correlation ≠ causal effect"; supports `CAUSALLY_VALIDATED = 0` and the
  requirement of real interventions.
- **Benjamini & Hochberg (1995)** — false discovery rate control for multiple
  hypothesis tests. *Use:* Causal Graph — the paper notes DecisionGPT's pairwise
  Granger applies *no* multiple-comparison correction across candidate edges,
  which inflates false positives (precision 0.40).

### B.7 Forecasting
- **Hyndman & Koehler (2006)** — forecast-accuracy measures; MAPE and several
  others are **degenerate when actuals are zero or near zero**; proposes MASE.
  *Use:* the citation for omitting MAPE on the Benroshan series (zero-sales
  days) and for reporting MAE/RMSE; optionally motivates adding MASE.
- **Chen & Guestrin (2016)** — XGBoost. *Use:* Methodology (the gradient-boosting
  baseline).

### B.8 SME / MSME digitalization
- **OECD (2021), "The Digital Transformation of SMEs"** — authoritative synthesis
  of SME digital-adoption barriers: financing, skills/data-science gap,
  uncertain ROI, data scarcity. *Use:* Introduction — motivation for a
  capability-gated, data-frugal architecture.
- **India-specific (authors to source, §J-2):** Ministry of MSME Annual Report;
  a peer-reviewed study of Indian MSME digital adoption / analytics. Required so
  the "Indian SME" framing is grounded — but **only as motivation**, never as
  evidence that DecisionGPT was validated on Indian SMEs.

### B.9 Explainable AI
- **Bansal et al. (2021, CHI)** — across three tasks, AI **explanations did not
  increase** complementary human-AI team performance beyond the accuracy signal
  alone. *Use:* the citation for "generating explanations ≠ improving decision
  quality / understanding"; supports the paper explicitly *not* claiming an
  explainability benefit.
- **Jacovi & Goldberg (2020, ACL)** — faithfulness vs plausibility; explanation
  quality is a distinct, gradient construct needing its own evaluation. *Use:*
  Limitations — DecisionGPT's confidence formula is reproducible/auditable
  (a faithfulness property) but no plausibility / comprehension study was run.

### B.10 Reproducibility / pre-registration / negative results
- **Baker (2016, Nature)** — the reproducibility-crisis survey (~90% see a
  crisis). *Use:* Introduction / Reproducibility — motivation for the manifest +
  clean-room validation.
- **Pineau et al. (2021, JMLR)** — the NeurIPS reproducibility program; the ML
  reproducibility checklist; code+data+seed reporting norms. *Use:*
  Reproducibility — the standard the infrastructure contribution is measured
  against.
- **Nosek et al. (2018, PNAS)** — pre-registration separates hypothesis
  generation from testing and curbs analytic flexibility. *Use:* Methodology —
  the risk-calibration study fixed its formula, variants, λ-rule and 7 criteria
  *before* running (`docs/RISK_CALIBRATION_ANALYSIS.md`); this is a genuine
  pre-registration and should be cited as such.
- **Rosenthal (1979)** — the file-drawer problem / publication bias against null
  results. *Use:* Discussion — why the negative multi-agent result is reported
  rather than buried.

### B.11 Statistical methods
- **Wilcoxon (1945)** — the signed-rank test. *Use:* Methodology (the paired
  test).
- **Fritz, Morris & Richler (2012)** — effect-size reporting; gives
  **r = Z/√N** for non-parametric tests (exactly DecisionGPT's `|Z|/√N_nonzero`).
  *Use:* Methodology + every results table — the citation for the effect-size
  formula *and* for the caution that effect sizes must be interpreted with the
  test and sample in view.
- **Kerby (2014)** — the matched-pairs rank-biserial correlation (simple
  difference formula f − u) as a Wilcoxon effect size, and its link to the
  common-language effect size. *Use:* Methodology — an alternative/companion
  effect-size interpretation; supports reporting wins/ties/losses proportions
  alongside r.
- **Wasserstein & Lazar (2016)** — the ASA statement: *small p-values do not
  imply large or important effects*. *Use:* Results/Discussion — the citation
  for the "statistical sign-consistency ≠ practical magnitude" framing, and for
  foregrounding the **mean shift** (+0.084, +0.083) next to every p and r.

### B.12 Validity of controlled / synthetic evaluation
- **Shadish, Cook & Campbell (2002)** — internal / external / construct /
  statistical-conclusion validity; external and *ecological* validity; threats
  when a treatment interacts with the setting or units. *Use:* the organizing
  citation for the Threats-to-Validity section; supports "designed synthetic
  scenarios give within-suite estimates, not population inference".

### B.13 India data sources
- **AGMARKNET** — Directorate of Marketing & Inspection, Ministry of Agriculture
  & Farmers Welfare, Government of India; wholesale mandi prices for ~300
  commodities across ~7,000 markets; also on data.gov.in under NDSAP. *Use:*
  Data Governance — describe accurately as **agricultural wholesale price
  context**, `DATA_PENDING`, not SME retail data.
- **RBI Database on Indian Economy** — the policy repo-rate series. *Use:* Data
  Governance — the macro covariate's provenance.

---

## C. Citation map

`Cite? ` = Y (needs a citation), N (project-internal fact, no external cite),
CAUTION (cite for context but do not let it imply DecisionGPT is validated).

| Paper section | Claim / statement | Cite? | Best source(s) | Why |
|---|---|---|---|---|
| Introduction | SMEs are data-constrained and underserved by action-oriented decision support | Y | OECD 2021; Lepenioti et al. 2020; + India MSME source (§J-2) | establishes the problem and the ROI/skills/data barriers |
| Introduction | BI/predictive analytics stops short of recommending actions | Y | Lepenioti et al. 2020; Shmueli & Koppius 2011 | the predictive→prescriptive gap |
| Introduction | Reproducibility and negative-result reporting are under-served in ML | Y | Baker 2016; Pineau et al. 2021; Rosenthal 1979 | motivates the methodological contribution |
| Related Work — DSS/prescriptive | field definitions, method-quality history | Y | Arnott & Pervan 2014; Lepenioti et al. 2020 | positioning |
| Related Work — digital twins | DT definition and maturity levels | Y | Grieves & Vickers 2017; Tao et al. 2019; Kritzinger et al. 2018; Jones et al. 2020 | terminology + prior art |
| Related Work — multi-agent (pro) | debate/many-agents can improve reasoning | Y | Du et al. 2023; Liang et al. 2024; Li et al. 2024 | the claim the paper qualifies |
| Related Work — multi-agent (con) | added agents/debate often do not help; are fragile; can degrade | Y | Wang et al. 2024; Smit et al. 2024; Huang et al. 2024; Cemri et al. 2025 | makes the negative result expected, not anomalous |
| Related Work — risk-aware opt. | additive risk terms in the objective; weighting is a design choice | Y | García & Fernández 2015 | frames `−λ(1−RM)` |
| Related Work — causal discovery | constraint-based discovery, faithfulness, Granger | Y | Granger 1969; Spirtes et al. 2000; Pearl 2009 | method lineage + limits |
| Architecture — Digital Twin / "decision simulation layer" | what distinguishes a twin from prediction; why the implemented mechanism is a *model* not a full twin | Y | Kritzinger et al. 2018; Grieves & Vickers 2017; Jones et al. 2020 | terminology (§E) |
| Architecture — Causal Graph | pairwise Granger; evidence levels; no auto-promotion to validated | Y (method) / N (the level thresholds are project design) | Granger 1969; Spirtes et al. 2000 | method basis |
| Architecture — Multi-Agent | rule-based agents, 2-round debate, optimizer arbitrates | N (design) — but cite Liang et al. 2024 for the judge-arbitrated debate pattern | CAUTION | describe as a design; the analogue is Liang et al. |
| Architecture — Risk Manager / optimizer | `final_score=(BA+FA)/2 − λ(1−RM)`, λ=1 | N (the formula is project design) + Y for the *class* | García & Fernández 2015 | situate the additive penalty |
| Architecture — Explainability | post-hoc narration; not a decision input | Y | Jacovi & Goldberg 2020; Bansal et al. 2021 | explanation ≠ decision quality |
| Data Governance — MAPE omission on the real series | MAPE is undefined/degenerate near zero actuals | Y | Hyndman & Koehler 2006 | standard methodological citation |
| Data Governance — forecasting baselines | naive baseline, XGBoost | Y | Hyndman & Koehler 2006; Chen & Guestrin 2016 | baseline choices |
| Data Governance — AGMARKNET, RBI | what these sources are | Y | AGMARKNET (GoI/DMI); RBI DBIE | provenance accuracy |
| Data Governance — synthetic vs real separation | why categories are not merged; external validity | Y | Shadish, Cook & Campbell 2002; Shmueli & Koppius 2011 | validity framing |
| Methodology — pre-registration of the risk study | fixing hypotheses/criteria before running improves credibility | Y | Nosek et al. 2018 | the risk study is genuinely pre-registered |
| Methodology — paired Wilcoxon | the test and its assumptions | Y | Wilcoxon 1945 | the test |
| Methodology — effect size r = Z/√N | formula and interpretation caution | Y | Fritz et al. 2012; Kerby 2014 | the exact formula + companion measure |
| Methodology — p-value interpretation | small p ≠ large effect; report magnitude | Y | Wasserstein & Lazar 2016 | the sign-consistency vs magnitude framing |
| Methodology — Student-t CI on designed scenarios | CI describes within-suite variability, not a population | Y | Shadish, Cook & Campbell 2002 | external-validity limit |
| Predictive Component Evaluation — forecasting/churn numbers | the metric values | N (project results) | — | frozen experiment output |
| Causal Method Validation — precision 0.40 explained by transitive/reverse FPs and no MC correction | the *reasons* are methodological | Y | Spirtes et al. 2000; Benjamini & Hochberg 1995; Granger 1969 | supports the caveat, not the number |
| Causal — "no real causal effect is established" | observational/synthetic ≠ causal | Y | Pearl 2009 | the standard citation |
| Architecture Comparison — the negative D-vs-B result | the numbers | N | — | frozen |
| Architecture Comparison — "this is consistent with prior negative multi-agent findings" | the framing | Y | Wang et al. 2024; Smit et al. 2024; Cemri et al. 2025 | positions the result |
| Multi-Agent Failure Analysis — failure-mode taxonomy language | mapping to a known taxonomy | Y (CAUTION) | Cemri et al. 2025 | optional cross-walk; the project's failure-mode labels are its own |
| Multi-Agent Failure Analysis — round-2 self-review inert | intrinsic self-correction doesn't help | Y | Huang et al. 2024 | explains the observation |
| Risk Manager Calibration — R0 zero/low-variance degeneracy | the *analysis* is project-internal; the robust-scale fix uses standard tools | N (finding) + Y (tools) | Rousseeuw & Croux 1993 | MAD robust scale + its efficiency/symmetry caveats |
| Risk Manager Calibration — extrapolation = OOD-reliability concern | framing | Y | Yang et al. 2024 | situates the heuristic |
| Risk Manager Calibration — λ weighting is a legitimate design axis | framing | Y | García & Fernández 2015 | the risk-term-weight question |
| Real-data probe (Benroshan) — "no inferential test; n_businesses = 1" | clustering / independence | Y | Shadish, Cook & Campbell 2002 | the statistical-conclusion-validity limit |
| Discussion — reporting the negative result | publication bias against nulls | Y | Rosenthal 1979; Baker 2016 | why it is reported |
| Reproducibility | manifest, seeds, clean-room rebuild vs community norms | Y | Pineau et al. 2021 | the checklist / norms |
| Limitations / Threats | four validity categories | Y | Shadish, Cook & Campbell 2002 | organizing framework |
| Future Work — real-LLM arm & evaluator bias | LLM-as-judge biases | Y | Zheng et al. 2023 | caution for the future arm |
| SME context throughout | "designed for Indian SME data constraints" | CAUTION | OECD 2021 + India source | motivation only; never "validated for Indian SMEs" |

---

## D. Novelty audit

Skeptical assessment. "Novel" is reserved for what the literature does **not**
already contain.

### D.1 Already well established (do NOT claim as novel)
- Integrating prediction + simulation + agents + explanation into a
  decision-support pipeline. Prescriptive-analytics and digital-twin-DSS reviews
  (Lepenioti et al. 2020; decision-support-within-DT reviews) show many such
  integrations exist.
- Multi-agent debate / critique / self-reflection for LLM tasks (Du et al. 2023;
  Liang et al. 2024; Li et al. 2024) — and its criticism (Wang et al. 2024;
  Smit et al. 2024; Huang et al. 2024; Cemri et al. 2025).
- Additive risk penalties in a decision objective; robust MAD-based scale
  estimation (García & Fernández 2015; Rousseeuw & Croux 1993).
- Pairwise Granger causality and its limitations; constraint-based causal
  discovery; FDR control (Granger 1969; Spirtes et al. 2000; Benjamini &
  Hochberg 1995).
- MAPE degeneracy near zero; gradient-boosted-tree forecasting (Hyndman &
  Koehler 2006; Chen & Guestrin 2016).
- "Explanations do not automatically improve decisions" (Bansal et al. 2021).
- Pre-registration, reproducibility checklists, negative-result reporting (Nosek
  et al. 2018; Pineau et al. 2021; Baker 2016; Rosenthal 1979).

### D.2 Engineering-integration contribution (real, but not scientific novelty)
- The specific end-to-end wiring (capability gating → goal-templated strategy
  generation → simulation → evidence-labelled causal context → rule-based
  3-agent debate → fixed version-tagged optimizer → reproducible confidence →
  decision/outcome memory), with production/research isolation and a
  16-experiment manifest. This is a substantial artefact; frame as
  design-science engineering, not a scientific claim.
- The capability-detection layer that returns an explicit insufficient-evidence
  result rather than a fabricated value. Sensible and well-executed, but
  "degrade gracefully when data is missing" is standard practice, not novel.

### D.3 Empirical contribution (this is where the value is)
- A **reproduced, mechanism-diagnosed negative result** for a multi-agent debate
  layer *on a decision-selection task with a simulator in the loop* — a setting
  the existing negative literature (mostly QA/reasoning benchmarks) does not
  cover. Novel *as an empirical data point in this setting*, not as a general
  claim.
- The demonstration that within this architecture the objective value is
  entirely in the deterministic simulation component and that causal/agent/
  explanation/memory components contribute exactly 0.000 to the objective on the
  suite (causal moves only confidence). A clean, quantified component-isolation
  result.
- The finding that a candidate-space confound, once corrected, leaves the result
  byte-identical — a rare, cleanly-controlled demonstration that a plausible
  alternative explanation is *not* responsible.

### D.4 Methodological contribution (real, modest)
- The **pre-registered** extrapolation-risk calibration protocol (formula,
  variants, λ-selection rule, 7 acceptance criteria fixed before running) plus a
  **self-disclosed negative external result** (R3 inert on real data). Applying
  registered-report discipline to an ML sub-component study is uncommon in
  practice and worth highlighting — but pre-registration itself is not novel
  (Nosek et al. 2018).
- The strict five-category data-governance scheme with a "never averaged" rule
  and a NOT-READY/BLOCKED discipline for real-outcome, Table 2 and real-LLM
  evidence. Good practice; not novel.

### D.5 Probably NOT novel / reviewers will push back
- "An integrated AI decision-support architecture for SMEs" — many exist; the
  integration per se is not a contribution.
- "A business digital twin" — terminology overreach (see §E); the mechanism is a
  what-if simulator on manually-loaded data.
- "Causal reasoning in the pipeline" — it is pairwise Granger graph construction
  with evidence labels; it changes only a confidence number and validates 0 real
  edges.
- "Risk-aware optimization" — an additive penalty with λ=1; standard.
- The R3 calibration as a *result* — it is PROMISING on a synthetic suite that
  was *designed* to contain the pathology, and inert on the one real dataset;
  reviewers will (correctly) read it as a pre-registered diagnosis, not a
  validated improvement.

### D.6 Claims reviewers will challenge (and the needed response)
| Challenge | Response the paper must be able to give |
|---|---|
| "Synthetic scenarios → no external validity" | Shadish et al. 2002; frame as within-suite; real validation is future work with a ready workflow |
| "Template-mode agents are a strawman" | scope the claim; Smit et al. 2024 (MAD is fragile / config-sensitive); Wang et al. 2024 (single strong agent ≈ multi-agent); real-LLM arm is pre-specified |
| "No external system baseline" | the contribution is component isolation + methodology + infrastructure, not SOTA; Arnott & Pervan 2014 on the value of rigorous evaluation over yet another artefact |
| "Precision 0.40 on causal recovery is weak" | Spirtes et al. 2000 (direct vs transitive), Benjamini & Hochberg 1995 (no MC correction); it is *method validation*, `CAUSALLY_VALIDATED = 0` |
| "Wilcoxon on few non-zero pairs; r≈0.9 is inflated" | Fritz et al. 2012 + Wasserstein & Lazar 2016; report N_nonzero and the mean shift as the magnitude |
| "'Digital twin' is overclaimed" | adopt the Kritzinger et al. 2018 taxonomy explicitly; call it a decision-simulation layer / digital model |
| "Explainability contribution?" | none claimed; Bansal et al. 2021; Jacovi & Goldberg 2020 |

---

## E. Recommended terminology

Decisions grounded in the literature; the authors make the final call.

| Term in current docs | Issue | Recommended paper wording | Basis |
|---|---|---|---|
| "Business Digital Twin" | By Kritzinger et al. (2018), a *Digital Twin* requires **automatic bidirectional** data flow between the physical entity and its virtual counterpart. DecisionGPT's mechanism runs on **manually uploaded** business data, produces **offline what-if simulations**, and has **no automatic or return** data path. That is a **Digital Model**. | Introduce once as *"a business **decision-simulation layer** (a *digital model* in the sense of Kritzinger et al. 2018, not a fully data-integrated digital twin)"*, then use **"decision simulation"** or **"the simulation layer"**. If "digital twin" is kept for continuity with the system's name, every substantive use must carry the qualifier. | Kritzinger et al. 2018; Grieves & Vickers 2017; Jones et al. 2020 |
| "Dynamic Causal Graph" / "causal reasoning" | The mechanism is **pairwise Granger graph construction with heuristic evidence labels**; it identifies no causal effects and changes only a confidence value. | *"an evidence-labelled association graph built with pairwise Granger tests"*; reserve "causal" for the ground-truth synthetic method-validation and always pair it with "method validation". Never "causal reasoning improves decisions". | Granger 1969; Spirtes et al. 2000; Pearl 2009 |
| "Multi-Agent Debate" | Accurate structurally, but "debate" implies LLM argumentation; here agents are **deterministic rule-based scorers** with a fixed 2-round exchange. | *"a rule-based multi-agent evaluation layer with a two-round structured exchange"*; state plainly that agent scores are deterministic and LLM-independent, and that an LLM (when configured) only parses the goal and narrates the result. | project code (`app/agents/base.py`); Liang et al. 2024 for the arbitrated-debate pattern |
| "Risk Manager calibration" / "R3" | Fine, but "calibration" can read as "we improved production". | *"a pre-registered calibration **study**"*; always attach "PROMISING on the synthetic suite; not adopted; production uses R0". | Nosek et al. 2018; García & Fernández 2015 |
| "goal achievement", "confidence", "risk-adjusted score" | Model-internal constructs. | Name them as *"a simulated goal-attainment metric"*, *"an internal confidence value (reproducible from stored components; not human-calibrated)"*, *"a simulated risk-discounted benefit"*. | Shadish, Cook & Campbell 2002 (construct validity); Jacovi & Goldberg 2020 |
| "validated" (anywhere near real SMEs / R3 / causality / LLM) | Not supported. | Use *"evaluated on a controlled suite"*, *"probed on one real dataset"*, *"NOT VALIDATED"*, *"BLOCKED"*, *"NOT READY"* exactly as the frozen reports do. | prior audit; Pearl 2009 for causal |
| "12-scenario suite" CIs | "confidence interval" without qualification implies population inference. | *"a Student-t interval describing sampling variability **within the designed scenario suite**"*. | Wasserstein & Lazar 2016; Shadish et al. 2002 |

---

## F. Methodological references (the "methods" backbone)

| Need | Reference | Exact use |
|---|---|---|
| Paired non-parametric comparison | Wilcoxon 1945 | the signed-rank test statistic and p-value |
| Non-parametric effect size | Fritz, Morris & Richler 2012 | `r = Z/√N` (matches the codebase's `|Z|/√N_nonzero`); interpret with N in view |
| Companion effect size / CLES | Kerby 2014 | matched-pairs rank-biserial (f − u); justifies reporting wins/ties/losses proportions |
| p-value interpretation | Wasserstein & Lazar 2016 | "small p ≠ large/important effect"; report the mean shift as magnitude |
| Validity taxonomy | Shadish, Cook & Campbell 2002 | internal / external / construct / statistical-conclusion validity; ecological validity; treatment×setting interaction |
| Pre-registration | Nosek et al. 2018 | the risk-calibration study's fixed-before-running design |
| Reproducibility norms | Pineau et al. 2021; Baker 2016 | the ML reproducibility checklist; crisis motivation |
| Publication bias / nulls | Rosenthal 1979 | why the negative result is published |
| Forecast-accuracy measures | Hyndman & Koehler 2006 | MAE/RMSE reporting; MAPE degeneracy near zero; MASE option |
| Robust scale | Rousseeuw & Croux 1993 | `1.4826·MAD` as robust σ; breakdown / efficiency / symmetry caveats |
| Risk term in the objective | García & Fernández 2015 | additive risk/safety penalty family; λ-weighting as a design axis |
| Causal-discovery limits | Spirtes et al. 2000; Granger 1969; Pearl 2009; Benjamini & Hochberg 1995 | transitive/reverse false positives; no MC correction; observational ≠ interventional |
| Predictive vs explanatory modelling | Shmueli & Koppius 2011 | separating method validation from causal/real-world claims |

---

## G. Reviewer-positioning guidance

1. **Lead with the question, not the system.** Open Related Work by laying out
   *both* the pro-multi-agent (Du et al. 2023; Li et al. 2024; Liang et al.
   2024) and the critical (Wang et al. 2024; Smit et al. 2024; Huang et al.
   2024; Cemri et al. 2025) literature, then state that the decision-selection +
   simulator setting is under-examined. This makes the negative result a
   contribution to an active debate, not a failed system.
2. **Pre-empt the strawman charge.** State up front that agent scores are
   rule-based and the result is scoped to that configuration; cite Smit et al.
   2024 (MAD fragility) and Wang et al. 2024 (single strong agent ≈ multi-agent)
   as evidence that this is a known regime; commit to the frozen real-LLM
   protocol as the next step.
3. **Adopt the Kritzinger taxonomy explicitly** (§E) so a reviewer cannot spend
   a paragraph on "this isn't a digital twin".
4. **Report magnitude beside significance everywhere** (Wasserstein & Lazar
   2016; Fritz et al. 2012): mean shift, N_nonzero, wins/ties/losses, then p and
   r. Never let r ≈ 0.9 stand alone.
5. **Frame the causal component as method validation** (Spirtes et al. 2000;
   Pearl 2009) and put `CAUSALLY_VALIDATED = 0` in the abstract's non-claims.
6. **Frame reproducibility + pre-registration as a first-class contribution**
   (Pineau et al. 2021; Nosek et al. 2018; Baker 2016), not boilerplate.
7. **Keep every "Indian SME" sentence to motivation** (OECD 2021 + an India
   source), and put "no real SME outcomes; not validated on SMEs" in the
   abstract.
8. **Cite the negative-results norm** (Rosenthal 1979) once, in the Discussion,
   to justify the paper's existence.

---

## H. Claims that REQUIRE a citation

(If the paper asserts any of these, it must cite the listed source; it must not
state them as common knowledge.)

1. Prescriptive analytics is defined as goal→action support beyond
   descriptive/predictive analytics → **Lepenioti et al. 2020**.
2. A "digital twin" (strict sense) requires automatic bidirectional data flow;
   offline simulators are "digital models" → **Kritzinger et al. 2018**;
   **Grieves & Vickers 2017**.
3. Multi-agent debate can improve LLM reasoning/factuality → **Du et al. 2023**;
   **Liang et al. 2024**; scaling with agent count → **Li et al. 2024**.
4. A single agent with a strong prompt can match multi-agent discussion →
   **Wang et al. 2024**.
5. Multi-agent debate does not reliably beat self-consistency/ensembling and is
   hyperparameter-sensitive → **Smit et al. 2024**.
6. LLMs do not reliably self-correct reasoning without external signal →
   **Huang et al. 2024**.
7. Multi-agent LLM systems have characteristic failure modes and often show
   minimal benchmark gains → **Cemri et al. 2025**.
8. LLM evaluators exhibit position/verbosity/self-enhancement bias →
   **Zheng et al. 2023**.
9. Additive risk/safety penalties in the objective are a recognized family;
   weighting is a design choice → **García & Fernández 2015**.
10. `1.4826·MAD` is a robust σ estimator; MAD has ~37% Gaussian efficiency and
    assumes symmetry → **Rousseeuw & Croux 1993**.
11. Extrapolation beyond observed inputs is an OOD-reliability concern →
    **Yang et al. 2024**.
12. Pairwise Granger cannot distinguish direct from transitive effects; apparent
    causality can come from omitted variables/slow sampling → **Granger 1969**;
    **Spirtes et al. 2000**.
13. Multiple hypothesis tests without correction inflate false positives →
    **Benjamini & Hochberg 1995**.
14. Observational/synthetic association is not a causal effect; interventions are
    required → **Pearl 2009**.
15. MAPE is degenerate/undefined near zero actuals → **Hyndman & Koehler 2006**.
16. XGBoost / scalable gradient-boosted trees → **Chen & Guestrin 2016**.
17. AI explanations do not automatically improve human-AI team decision quality →
    **Bansal et al. 2021**.
18. Explanation faithfulness is a distinct, graded construct → **Jacovi &
    Goldberg 2020**.
19. There is a reproducibility crisis; ML has reproducibility norms/checklists →
    **Baker 2016**; **Pineau et al. 2021**.
20. Pre-registration separates hypothesis generation from testing and improves
    credibility → **Nosek et al. 2018**.
21. Publication bias suppresses null/negative results → **Rosenthal 1979**.
22. r = Z/√N is a standard non-parametric effect size → **Fritz et al. 2012**;
    matched-pairs rank-biserial → **Kerby 2014**.
23. Small p-values do not imply large/important effects → **Wasserstein & Lazar
    2016**.
24. External/ecological validity limits of designed studies; validity taxonomy →
    **Shadish, Cook & Campbell 2002**.
25. SME digital-adoption barriers (cost, skills, data scarcity, uncertain ROI) →
    **OECD 2021** (+ India source, §J-2).
26. AGMARKNET is a Government-of-India agricultural wholesale-price network →
    **AGMARKNET / DMI, GoI**.

---

## I. Claims that must NOT be cited as established facts (project-specific findings)

These are DecisionGPT's own frozen results. They are supported **only** by the
experiment manifest / stored runs, never by external literature. Do not attach a
citation that would make them look like received knowledge, and do not let the
literature soften or restate them.

| Finding | Value (frozen) | Only source |
|---|---|---|
| Architecture A / B / C / D mean goal achievement | 0.000 / 0.486 / 0.003 / 0.084 | exp `0e1bd8dc` |
| Full DecisionGPT vs Prediction+Digital-Twin | D − B = −0.401; wins 0 / ties 15 / losses 45; paired Wilcoxon p < 0.0001; r = 0.87 | exp `0e1bd8dc` |
| Ablation: only removing the Digital Twin moves the objective | Δ +0.084 (95% CI [+0.013, +0.156]); Causal/Multi-Agent/Explainability/Memory Δ = 0.000; Causal removal moves confidence 0.139→0.251 | exp `db58455b` |
| Candidate-space correction | coverage 0.333→0.833; missing-supported 0.500→0.000; aggregates byte-identical PRE vs POST | exps `c58c4537`→`f24abc1b`; `675cf17e`==`0e1bd8dc` |
| Risk-penalty diagnosis (D1) | D0 0.084 → D1 0.583; D1 confidence 0.018; p < 0.0001; r = 0.89; 0/390 RISK_SCORE_MISMATCH | exp `ba56e42b` |
| Risk calibration R3 | goal achievement 0.168 (95% CI [0.071, 0.265]); risk-adjusted +40.5; confidence 0.109; Wilcoxon p = 0.0253; 5 non-zero positive pairs; Spearman ρ 0.969; 0 monotonicity violations; PROMISING; **not promoted** | exp `b8516eef` |
| Real Indian data probe | R0 == R1 on 184/184 risk rows; ρ 0.989; 0 violations; SIMULATED decision identical across variants; no inferential test (n_businesses = 1); R3 has no measurable effect | exp `70617412` |
| Forecasting (synthetic platform) | XGBoost MAE 15.14 / RMSE 21.86 / MAPE 10.30% | exp `c2b3a2fa` |
| Forecasting (Benroshan real, 51 test days) | naive 19.92/31.25; linear 18.47/28.51; XGBoost 15.27/23.89; MAPE omitted | Table 1 (archived v2 models) |
| Causal recovery (synthetic ground truth) | precision 0.40; recall 1.00; F1 0.571; SHD 3 | exp `36d0d404` |
| Real SME outcomes | 0 | DB / `paper_results_snapshot` |
| Real-LLM validation | BLOCKED (`llm_enabled = False`) | settings |
| CAUSALLY_VALIDATED | 0 | `causal_feedback_service` |

The literature explains *why such results are plausible or how to interpret
them* (e.g. Wang et al. 2024, Smit et al. 2024 for the multi-agent regression;
Spirtes et al. 2000 for precision 0.40; Hyndman & Koehler 2006 for the MAPE
omission). It never provides the numbers.

---

## J. Bibliography candidate list

### J-1. Verified this session (located via publisher / ACL / arXiv / DOI page)

DOIs shown were seen on the publisher or a DOI-registry page during this
session. Authors should still run a final check (title, year, page range) before
submission.

**Decision support / prescriptive analytics**

1. Lepenioti, K., Bousdekis, A., Apostolou, D., & Mentzas, G. (2020).
   *Prescriptive analytics: Literature review and research challenges.*
   International Journal of Information Management, 50, 57–70.
   DOI 10.1016/j.ijinfomgt.2019.04.003
2. Arnott, D., & Pervan, G. (2014). *A critical analysis of decision support
   systems research revisited: the rise of design science.* Journal of
   Information Technology, 29(4), 269–293. DOI 10.1057/jit.2014.16
3. Shmueli, G., & Koppius, O. R. (2011). *Predictive Analytics in Information
   Systems Research.* MIS Quarterly, 35(3), 553–572.
   (JSTOR / MISQ; DOI 10.2307/23042796 — verify)

**Digital twins**

4. Grieves, M., & Vickers, J. (2017). *Digital Twin: Mitigating Unpredictable,
   Undesirable Emergent Behavior in Complex Systems.* In: Transdisciplinary
   Perspectives on Complex Systems, Springer, 85–113.
   DOI 10.1007/978-3-319-38756-7_4
5. Tao, F., Zhang, H., Liu, A., & Nee, A. Y. C. (2019). *Digital Twin in
   Industry: State-of-the-Art.* IEEE Transactions on Industrial Informatics,
   15(4), 2405–2415. DOI 10.1109/TII.2018.2873186
6. Kritzinger, W., Karner, M., Traar, G., Henjes, J., & Sihn, W. (2018).
   *Digital Twin in manufacturing: A categorical literature review and
   classification.* IFAC-PapersOnLine, 51(11), 1016–1022.
   DOI 10.1016/j.ifacol.2018.08.474
7. Jones, D., Snider, C., Nassehi, A., Yon, J., & Hicks, B. (2020).
   *Characterising the Digital Twin: A systematic literature review.* CIRP
   Journal of Manufacturing Science and Technology, 29, 36–52.
   (DOI 10.1016/j.cirpj.2020.02.002 — verify page range)

**Multi-agent / LLM agents**

8. Du, Y., Li, S., Torralba, A., Tenenbaum, J. B., & Mordatch, I. (2023/2024).
   *Improving Factuality and Reasoning in Language Models through Multiagent
   Debate.* ICML 2024. arXiv:2305.14325
9. Liang, T., He, Z., Jiao, W., Wang, X., Wang, Y., Wang, R., Yang, Y., Shi, S.,
   & Tu, Z. (2024). *Encouraging Divergent Thinking in Large Language Models
   through Multi-Agent Debate.* EMNLP 2024, 17889–17904.
   ACL Anthology 2024.emnlp-main.992. arXiv:2305.19118
10. Li, J., Zhang, Q., Yu, Y., Fu, Q., & Ye, D. (2024). *More Agents Is All You
    Need.* Transactions on Machine Learning Research. arXiv:2402.05120
11. Wang, Q., Wang, Z., Su, Y., Tong, H., & Song, Y. (2024). *Rethinking the
    Bounds of LLM Reasoning: Are Multi-Agent Discussions the Key?* ACL 2024
    (Long). ACL Anthology 2024.acl-long.331. arXiv:2402.18272
12. Smit, A. P., Grinsztajn, N., Duckworth, P., Barrett, T. D., & Pretorius, A.
    (2024). *Should we be going MAD? A Look at Multi-Agent Debate Strategies for
    LLMs.* ICML 2024, PMLR 235. arXiv:2311.17371
13. Huang, J., Chen, X., Mishra, S., Zheng, H. S., Yu, A., Song, X., & Zhou, D.
    (2024). *Large Language Models Cannot Self-Correct Reasoning Yet.* ICLR
    2024. arXiv:2310.01798
14. Cemri, M., Pan, M. Z., Yang, S., et al. (2025). *Why Do Multi-Agent LLM
    Systems Fail?* arXiv:2503.13657
15. Zheng, L., Chiang, W.-L., Sheng, Y., et al. (2023). *Judging LLM-as-a-Judge
    with MT-Bench and Chatbot Arena.* NeurIPS 2023 Datasets & Benchmarks Track.
    arXiv:2306.05685

**Risk-aware optimization / robust statistics / OOD**

16. García, J., & Fernández, F. (2015). *A Comprehensive Survey on Safe
    Reinforcement Learning.* Journal of Machine Learning Research, 16, 1437–1480.
17. Rousseeuw, P. J., & Croux, C. (1993). *Alternatives to the Median Absolute
    Deviation.* Journal of the American Statistical Association, 88(424),
    1273–1283. DOI 10.1080/01621459.1993.10476408
18. Yang, J., Zhou, K., Li, Y., & Liu, Z. (2024). *Generalized Out-of-Distribution
    Detection: A Survey.* International Journal of Computer Vision, 132(12),
    5635–5662. DOI 10.1007/s11263-024-02117-4

**Causal inference**

19. Granger, C. W. J. (1969). *Investigating Causal Relations by Econometric
    Models and Cross-spectral Methods.* Econometrica, 37(3), 424–438.
    (DOI 10.2307/1912791 — verify)
20. Spirtes, P., Glymour, C., & Scheines, R. (2000). *Causation, Prediction, and
    Search* (2nd ed.). MIT Press. ISBN 978-0-262-19440-2
21. Pearl, J. (2009). *Causal inference in statistics: An overview.* Statistics
    Surveys, 3, 96–146. DOI 10.1214/09-SS057
22. Benjamini, Y., & Hochberg, Y. (1995). *Controlling the False Discovery Rate:
    A Practical and Powerful Approach to Multiple Testing.* Journal of the Royal
    Statistical Society: Series B, 57(1), 289–300.
    DOI 10.1111/j.2517-6161.1995.tb02031.x

**Forecasting**

23. Hyndman, R. J., & Koehler, A. B. (2006). *Another look at measures of
    forecast accuracy.* International Journal of Forecasting, 22(4), 679–688.
    DOI 10.1016/j.ijforecast.2006.03.001
24. Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System.*
    KDD '16, 785–794. DOI 10.1145/2939672.2939785. arXiv:1603.02754

**SME / MSME context**

25. OECD (2021). *The Digital Transformation of SMEs.* OECD Studies on SMEs and
    Entrepreneurship, OECD Publishing, Paris. DOI 10.1787/bdb9256a-en

**Explainable AI**

26. Bansal, G., Wu, T., Zhou, J., Fok, R., Nushi, B., Kamar, E., Ribeiro, M. T.,
    & Weld, D. (2021). *Does the Whole Exceed its Parts? The Effect of AI
    Explanations on Complementary Team Performance.* CHI '21.
    DOI 10.1145/3411764.3445717
27. Jacovi, A., & Goldberg, Y. (2020). *Towards Faithfully Interpretable NLP
    Systems: How Should We Define and Evaluate Faithfulness?* ACL 2020,
    4198–4205. ACL Anthology 2020.acl-main.386

**Reproducibility / pre-registration / negative results**

28. Baker, M. (2016). *1,500 scientists lift the lid on reproducibility.*
    Nature, 533(7604), 452–454. DOI 10.1038/533452a
29. Pineau, J., Vincent-Lamarre, P., Sinha, K., Larivière, V., Beygelzimer, A.,
    d'Alché-Buc, F., Fox, E., & Larochelle, H. (2021). *Improving Reproducibility
    in Machine Learning Research (A Report from the NeurIPS 2019 Reproducibility
    Program).* JMLR, 22(164), 1–20. arXiv:2003.12206
30. Nosek, B. A., Ebersole, C. R., DeHaven, A. C., & Mellor, D. T. (2018).
    *The preregistration revolution.* PNAS, 115(11), 2600–2606.
    DOI 10.1073/pnas.1708274114
31. Rosenthal, R. (1979). *The file drawer problem and tolerance for null
    results.* Psychological Bulletin, 86(3), 638–641.
    DOI 10.1037/0033-2909.86.3.638

**Statistical methods**

32. Wilcoxon, F. (1945). *Individual comparisons by ranking methods.* Biometrics
    Bulletin, 1(6), 80–83. (DOI 10.2307/3001968 — verify)
33. Fritz, C. O., Morris, P. E., & Richler, J. J. (2012). *Effect size
    estimates: Current use, calculations, and interpretation.* Journal of
    Experimental Psychology: General, 141(1), 2–18. DOI 10.1037/a0024338
34. Kerby, D. S. (2014). *The simple difference formula: An approach to teaching
    nonparametric correlation.* Comprehensive Psychology, 3, 11.IT.3.1.
    DOI 10.2466/11.IT.3.1
35. Wasserstein, R. L., & Lazar, N. A. (2016). *The ASA's Statement on p-Values:
    Context, Process, and Purpose.* The American Statistician, 70(2), 129–133.
    DOI 10.1080/00031305.2016.1154108

**Experimental design / validity**

36. Shadish, W. R., Cook, T. D., & Campbell, D. T. (2002). *Experimental and
    Quasi-Experimental Designs for Generalized Causal Inference.* Houghton
    Mifflin, Boston.

**India data sources (official portals — cite as institutional sources)**

37. Directorate of Marketing & Inspection, Ministry of Agriculture & Farmers
    Welfare, Government of India. *AGMARKNET — Agricultural Marketing Information
    Network.* https://agmarknet.gov.in (data also via https://data.gov.in under
    NDSAP). Launched March 2000.
38. Reserve Bank of India. *Database on Indian Economy (DBIE)* —
    policy repo rate series. https://rbi.org.in

### J-2. Candidate references — NOT verified this session (authors must confirm before citing)

These are well known in their fields and likely appropriate, but their exact
bibliographic details / DOIs were **not** checked in this session. **Do not cite
without verifying.** Do not copy a DOI from memory.

- Runge, J., et al. (2019). *Detecting and quantifying causal associations in
  large nonlinear time series datasets.* Science Advances, 5(11), eaau4996.
  — for time-series causal-discovery limitations (PCMCI). *Verify.*
- Makridakis, S., Spiliotis, E., & Assimakopoulos, V. (2020). *The M4
  Competition: 100,000 time series and 61 forecasting methods.* International
  Journal of Forecasting, 36(1), 54–74. — statistical vs ML forecasting
  baselines. *Verify.*
- Huber, P. J., & Ronchetti, E. M. (2009). *Robust Statistics* (2nd ed.). Wiley.
  — the 1.4826 MAD consistency factor and robust-scale theory. *Verify.*
- Sculley, D., Snoek, J., Wiltschko, A., & Rahimi, A. (2018). *Winner's Curse?
  On Pace, Progress, and Empirical Rigor.* ICLR 2018 Workshop. — empirical rigor
  in ML. *Verify.*
- Adadi, A., & Berrada, M. (2018). *Peeking Inside the Black-Box: A Survey on
  Explainable Artificial Intelligence (XAI).* IEEE Access, 6, 52138–52160.
  — XAI survey. *Verify.*
- Guidotti, R., et al. (2018). *A Survey of Methods for Explaining Black Box
  Models.* ACM Computing Surveys, 51(5), 93. — XAI survey. *Verify.*
- Ministry of Micro, Small & Medium Enterprises, Government of India. *Annual
  Report* (latest available). — Indian MSME landscape / digitalization.
  *Authors to source the specific year and any peer-reviewed India MSME
  analytics paper.*
- A peer-reviewed study on Indian MSME digital / analytics adoption (e.g. from
  Journal of Small Business Management, Technological Forecasting & Social
  Change, or an Indian management journal). *Authors to identify and verify.*
- Stone, M. (1974). *Cross-validatory choice and assessment of statistical
  predictions.* JRSS-B, 36(2), 111–147. — if the chronological-split / holdout
  methodology needs a citation. *Verify.*
- Wolpert, D. H. (1992). *Stacked generalization.* Neural Networks, 5(2),
  241–259. — if the optimizer's score aggregation is framed as an ensemble.
  *Verify.*

### J-3. Coverage check vs the blueprint's §J areas

| Blueprint area | Covered by | Gap? |
|---|---|---|
| SME / MSME decision support | 25 (+ J-2 India sources) | **India-specific source still needed** (authors) |
| Decision intelligence / prescriptive analytics | 1, 2, 3 | ok |
| Business digital twins | 4, 5, 6, 7 | ok |
| Causal inference | 19, 20, 21, 22 (+ Runge J-2) | ok |
| Multi-agent systems (both directions) | 8–15 | strong |
| Risk-aware optimization | 16, 17, 18 (+ Huber J-2) | ok |
| Forecasting | 23, 24 (+ M4 J-2) | ok |
| Explainable AI | 26, 27 (+ surveys J-2) | ok |
| Business intelligence | 2, 3 | thin but adequate for a non-BI-focused paper |
| Reproducibility / pre-registration / negatives | 28, 29, 30, 31 | strong |
| Synthetic data / controlled scenarios / external validity | 36 | adequate; a dedicated synthetic-eval methods cite is optional |
| Statistical methodology | 32, 33, 34, 35 | strong |
| India data sources | 37, 38 (+ MSME report J-2) | ok |

---

## K. Final positioning statement (for the Introduction)

> DecisionGPT is an integrated, capability-gated decision-support architecture
> that connects goal specification, strategy generation, a business
> decision-simulation layer, an evidence-labelled association graph, a
> rule-based multi-agent evaluation with a fixed scoring rule, post-hoc
> explanation, and decision memory. Rather than claiming that this integration
> improves outcomes, this paper asks — under controlled conditions — **where the
> value inside such an architecture actually comes from.** On a pre-registered
> 12-scenario, 5-seed evaluation (60 paired observations per configuration), the
> deterministic simulation layer is the only component that improves a simulated
> goal-attainment metric; adding a multi-agent debate layer on top of it
> significantly *reduces* that metric, and we trace the cause to the optimizer's
> risk-penalty term acting on a mis-scaled extrapolation-risk heuristic rather
> than to an unequal strategy space (which we identified, corrected, and showed
> leaves the result byte-identical). We further report a pre-registered
> diagnosis and attempted calibration of that risk heuristic — promising on the
> synthetic suite, inert on the one real Indian dataset available — and we
> release the full experiment manifest, data-category separation, and clean-room
> reproduction. This negative, mechanism-level result is consistent with a
> growing literature questioning whether added agent layers reliably help
> [Wang et al. 2024; Smit et al. 2024; Cemri et al. 2025], and it is offered in
> that spirit: as evidence about architectural value, not as a validated system.

**The paper is NOT positioned as:** proof of DecisionGPT superiority;
validation on Indian SMEs; real-world causal validation; real-LLM validation; or
proof that multi-agent systems improve business decisions. All decision evidence
is synthetic and scenario-based; there are zero real SME decision outcomes; the
real-LLM arm is BLOCKED; and no human explainability study was conducted.

---

*This document performed literature research only. It did not write the paper
and did not modify any code, dataset, experiment, seed, model, or production
configuration.*
