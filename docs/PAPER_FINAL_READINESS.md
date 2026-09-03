# DecisionGPT Paper — Final Readiness Report

Prepared alongside `docs/PAPER_DRAFT.md`. This is a publication-preparation
record. No experiment was run; no research artifact was modified.

## 1. Frozen-artifact integrity

Verified **before and after** all edits in this pass:

| Invariant | Value | Status |
|---|---|---|
| `experiments/experiment_manifest.json` SHA-256 | `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff` | unchanged |
| Frozen experiment count | 16 | unchanged |
| `git diff -- experiments/ backend/` | (empty) | no experiment / dataset / model / backend change |
| Production decision config | R0 / D0 (`risk_model = None`, `risk_penalty_lambda = 1.0`) | unchanged |
| R3 status | PROMISING — NOT PROMOTED | unchanged |
| Real Indian SME decision outcomes | 0 | unchanged |
| `PredictionEvaluation` records | 0 | unchanged |
| Table 2 (real predicted-vs-actual) | NOT READY (`paper_results_snapshot.json` `available: false`) | unchanged |
| Real-LLM evaluation | BLOCKED (`llm_enabled = false`) | unchanged |
| `CAUSALLY_VALIDATED` | 0 (`causal_edges`: assumed 20 / observational 5 / data_supported 1) | unchanged |
| Active / archived models | 6 / 3 | unchanged |
| Alembic head | 0007 | unchanged |

## 2. What was verified / completed this pass

- **DOI verification (3 flagged references).**
  - Shmueli & Koppius 2011 → MIS Quarterly 35(3):553–572, DOI 10.2307/23042796 — **confirmed** (publisher misq.umn.edu; AIS eLibrary).
  - Granger 1969 → Econometrica 37(3):424–438, DOI 10.2307/1912791 — **confirmed** (Econometric Society; RePEc; JSTOR 1912791).
  - Wilcoxon 1945 → Biometrics Bulletin 1(6):80–83, DOI 10.2307/3001968 — **confirmed** (JSTOR 3001968; DOI resolves via CrossRef).
  The "verify" flags were removed and replaced with the located identifiers.
- **India MSME motivation source added.** Buteau, S. (2021), *Roadmap for digital
  technology to foster India's MSME ecosystem — opportunities and challenges*,
  CSI Transactions on ICT 9(4):233–244, DOI 10.1007/s40012-021-00345-4 (Springer;
  open access PMC8662980). Added as reference 39 and cited once in Section 1 for
  the informality / limited-records / credit-history point; used as **motivation
  only**. The Introduction sentence was updated to state exactly what the source
  supports. A second, optional India source is listed as an author candidate.
- **Citation audit.** All 39 numbered references checked for existence, correct
  author/year, and claim support; higher-risk statements (multi-agent, LLM
  self-correction, digital twins, causal discovery, explainability,
  reproducibility, statistics, Indian MSMEs) spot-audited in
  `docs/PAPER_REFERENCES.md`. One wording tightening: the "direct vs transitive"
  limitation is now attributed to Spirtes et al. 2000 rather than sitting next to
  the Granger 1969 cite. No citation supports a claim stronger than its source;
  no project-specific frozen result is attributed to external literature.
- **Figures rendered.** `docs/figures/make_figures.py` renders Figures 1–4 to SVG
  (+ PNG previews) from `docs/figures/figure_data.json` — values extracted
  read-only from the frozen experiment runs (source IDs recorded in that file).
  The only stochastic element is the Figure 2 paired bootstrap, seeded
  `numpy.default_rng(42)` (a re-analysis of frozen paired differences, not a new
  experiment). Full captions are in Appendix A of the draft. Axes are not
  truncated to exaggerate effects (bar charts start at 0; the difference panel
  spans the observed range).
- **Numerical consistency check.** A 66-point automated comparison of draft
  numbers against `figure_data.json` (extracted from frozen runs),
  `experiments/paper_results_snapshot.json`, and
  `experiments/experiment_manifest.json` — **66/66 passed**. Covered: experiment
  count and manifest hash; A/B/C/D means and CIs; D−B and D−A paired stats
  (mean, W/T/L, N_nonzero, p, CI); scenario-level counts; S04/S07-excluded
  re-analysis; ablation values and the association-graph confidence shift; D1
  and D1−D0; Eq. 1 verification / RM-decisive / mismatch; R0–R3 variant means,
  RAS, confidence, R3−R0 paired stats and verdicts; forecasting and churn
  metrics; causal precision/recall/F1/SHD; Table 2 NOT READY; real-SME /
  PredictionEvaluation / CAUSALLY_VALIDATED = 0; real-LLM BLOCKED.
- **Statistical reporting check.** Each paired contrast in the draft reports n,
  N_nonzero, mean paired difference (led with as the magnitude), wins/ties/losses,
  Wilcoxon two-sided p, the p-derived r = Z/√N_nonzero **with its explicit
  caveat**, the matched-pairs rank-biserial, and the CI with its construction.
  - **D − B:** n = 60, N_nonzero = 45, mean −0.4011, median −0.4132, W/T/L
    0/15/45, p < 10⁻⁴ (recomputed 4.8×10⁻⁹), rank-biserial −1.00, Student-t CI
    [−0.478, −0.324], paired bootstrap 95% CI [−0.477, −0.327], scenario-level
    (n = 12) bootstrap [−0.571, −0.235]. **Present and central.**
  - **D − A:** disclosed that only 10 of 60 pairs are non-zero, that r ≈ 0.90 is
    not an independent effect-size estimate, and that the +0.084 mean shift is
    the interpretable magnitude.
  - **R3 − R0:** disclosed N_nonzero = 5, W/T/L 5/55/0, mean +0.083, p = 0.0253,
    that r = 1.00 is driven by sign agreement among only five non-zero pairs, and
    that R3 is NOT PROMOTED.
  - **Clustering:** the draft states the 60 observations arise from 12 designed
    scenarios × 5 seeds, are not 60 independent scenarios, and presents the
    scenario-level analysis as the conservative view; it makes no population
    inference.
- **Forbidden-claim scan (full text).** Every occurrence of *validated,
  validation, accurate, accuracy, superior, superiority, improves, improvement,
  ROI, business impact, production, real-world, Indian SME, causal, causal
  discovery, LLM, autonomous, generalise/generalize, representative, customer
  behaviour, effectiveness, state-of-the-art, outperform* was classified. All
  hits are: a supported (synthetic-scoped) claim, an explicit non-claim, a
  limitation, a prior-work description, future work, terminology, a reference
  title, or an appendix audit row. No unqualified overclaim found. "accurate" —
  0 hits. "ROI" — appears only as a scenario objective label with "(revenue
  proxy)" attached, and as absent evidence.
- **Narrative hierarchy check.** The draft leads with (1) A→B 0.000→0.486, then
  (2) B→D 0.486→0.084, then (3) the D1 mechanism 0.084→0.583, then (4) R3
  0.084→0.168 as promising-but-unpromoted, then (5) the absent real-world
  evidence. R3 is confined to a section labelled *supplementary*; the negative
  result is the abstract's and conclusion's headline.
- **Table audit.** Tables 1 (scenarios), 2 (NOT READY), 3 + 3b (architecture),
  4 (ablation), 5 (predictive), 6 (recalibration) each carry synthetic/real and
  primary/supporting/supplementary labels; decimal precision is consistent within
  each table; S04/S07 are marked "(revenue proxy)" in Table 1 and flagged in
  Sections 6.1, 7, 9.3, 16 and Appendix A/C; predictive tables never use
  "accuracy". Table column counts are internally consistent.
- **Format check.** Heading levels are consistent (`##` for the 20 numbered
  sections, `###` for subsections, `## Appendix A–D`); no broken table syntax;
  the manuscript is venue-neutral Markdown with no premature page-limit trimming.
- **Secrets check.** No credential, API key, password, or token appears in the
  manuscript or in `docs/PAPER_REFERENCES.md` / this file. The reproducibility
  section describes gates and governance, not secrets.

## 3. Deliverables

| Deliverable | Location |
|---|---|
| Final manuscript | `docs/PAPER_DRAFT.md` |
| Rendered figures (SVG + PNG) | `docs/figures/figure{1,2,3,4}_*.svg` |
| Figure render script | `docs/figures/make_figures.py` |
| Figure source data (extracted read-only from frozen runs) | `docs/figures/figure_data.json` |
| Reference verification log | `docs/PAPER_REFERENCES.md` |
| This readiness report | `docs/PAPER_FINAL_READINESS.md` |

## 4. Remaining venue-specific work (author)

1. Choose a target venue and apply its template, length limit, and citation
   style (Markdown → LaTeX/Word). No venue is specified in the repository.
2. Optionally add and confirm a second peer-reviewed Indian MSME digital-adoption
   source (candidate listed in `docs/PAPER_REFERENCES.md`).
3. Re-check exact page ranges / editions of all references under the chosen
   citation style.
4. Run the Appendix B read-through on the final venue-formatted text.
5. Convert the SVG figures to the venue's required format/resolution if not SVG.

## 5. Final checklist

| Item | Answer | Note |
|---|---|---|
| Paper complete | **YES** | 21 sections + appendices; tables 1–6 (+3b); Figures 1–4 with full captions. |
| All citations verified | **YES** | 39 numbered refs verified; 3 previously flagged DOIs re-checked; log in `docs/PAPER_REFERENCES.md`. One *optional* second India source left as an author candidate. |
| India MSME source added and verified | **YES** | Buteau 2021 (ref 39), DOI 10.1007/s40012-021-00345-4; Introduction updated to match what it supports; motivation only. |
| Figures 1–4 rendered | **YES** | `docs/figures/*.svg` from frozen data via `make_figures.py`. |
| Numerical consistency verified | **YES** | 66/66 automated checks against the frozen manifest / snapshot / extracted observations. |
| Statistical reporting verified | **YES** | n, N_nonzero, mean shift, W/T/L, Wilcoxon p, rank-biserial, p-derived r **with caveat**, CI + construction for every contrast; clustering and scenario-level view stated. |
| Table 2 explicitly NOT READY | **YES** | 0 records, ≥ 5 threshold, no substitution, future work. |
| Synthetic scope explicit in abstract | **YES** | First two sentences state controlled synthetic evaluation and that no real SME outcomes were available. |
| Multi-agent claim correctly scoped | **YES** | Every claim ties the result to the tested deterministic rule-based configuration; an explicit non-generalisation sentence appears in the abstract, §7-equivalent wording, §15, and Figure captions. |
| Real-world claims absent | **YES** | 0 real outcomes, 0 PredictionEvaluation, no human study, no external baseline, no ROI, no business-impact claim — all stated as absent. |
| LLM claims absent / future-only | **YES** | Real-LLM BLOCKED; no LLM output, prompt, latency, or judge score reported; future arm described only. |
| Causal claims correctly scoped | **YES** | Synthetic method validation only; `CAUSALLY_VALIDATED = 0` in the abstract's non-claims and §13/§14. |
| Frozen manifest unchanged | **YES** | SHA-256 `94aa419c…` identical before and after. |
| No experiments modified | **YES** | `git diff -- experiments/` empty. |
| No backend / production changes | **YES** | `git diff -- backend/` empty; R0/D0 unchanged. |
| Venue formatting pending | **YES** | No venue chosen; template/style not applied. |
| Ready for final author / venue formatting | **YES** | Scientific content, figures, references, and audits are complete; only venue-specific formatting and the optional second India source remain. |
