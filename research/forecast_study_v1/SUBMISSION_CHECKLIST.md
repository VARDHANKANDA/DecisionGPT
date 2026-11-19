# Submission readiness checklist (forecast_study_v1)

**Honest status: NOT submission-ready.** The scientific content (contribution, protocol, results, references, reproducibility) has been audited, but items that only the authors can supply are open, and no venue-formatted file exists. Nothing has been submitted, no account created, no editor contacted, no fee paid.

Legend: **DONE** = produced and checked here; **OPEN-A** = authors must do; **OPEN-V** = venue-specific formatting still to do.

## A. Scientific content

| Item | Status | Where |
|---|---|---|
| Contribution stated narrowly (empirical, protocol-focused; no new method; no SME claim) | DONE | manuscript §1, §19 |
| Hypotheses and decision rules written before confirmatory runs; plan + code hashed | DONE | `EXPERIMENT_PLAN.md`, `FREEZE.json` |
| Deviations disclosed (post-hoc E1; vacuous customer-disjoint design replaced; run order script added) | DONE | plan §11 |
| Leakage controls and tests | DONE | `run_forecast_study.py`, `tests/unit/test_forecast_study.py` |
| Independent verification of every cell | DONE | `verify_cell.py` → 24/24 (6 cells), 19/19 (4 ablations) |
| Negative / inconclusive results reported | DONE | manuscript §9–§16 |
| Evidence-to-claim matrix | DONE | `EVIDENCE_CLAIM_MATRIX.md` |
| Limitations and threats to validity | DONE | manuscript §19 |
| Seed-variance study | **NOT DONE** (stated limitation) | — |
| Stronger tuning / median-objective model selected on validation as a pre-registered arm | **NOT DONE** (post-hoc E1 only) | would change the conclusion's strength |

## B. Literature and references

| Item | Status |
|---|---|
| Every reference in §22 has bibliographic fields read from Crossref/proceedings/arXiv (no invented DOI) | DONE (`LITERATURE_REVIEW.md`) |
| Content of sources marked "bibliographic data only" read before any further paraphrase | **OPEN-A** |
| Systematic/venue-specific literature update for 2025–2026 (forecasting-evaluation papers, M5-based studies) | **OPEN-A** |
| Dataset citations (M5 licence/terms; Online Retail II donor citation and licence) confirmed | **OPEN-A** |
| BibTeX file for the chosen template | **OPEN-V** |

## C. Reproducibility

| Item | Status |
|---|---|
| One-command reproduction, environment, seeds, hashes | DONE (`REPRODUCIBILITY.md`, `environment_freeze.txt`, `run_all.sh`) |
| Historical benchmark reproduced before new work | DONE (`audit/`) |
| Predictions for every method stored | DONE (`results/*/predictions.npz`; ≈ 29 MB total) |
| Public repository / DOI for code and predictions | **OPEN-A** (not created; no publication without approval) |
| Raw data redistribution rights confirmed (raw files are not included) | **OPEN-A** |

## D. Manuscript package

| Item | Status |
|---|---|
| 22-section editable draft (Markdown) | DONE (`manuscript/MANUSCRIPT.md`) |
| Figures 1–4 (SVG) generated from stored results | DONE (`manuscript/figures/`) |
| Tables generated from stored results | DONE (`results/TABLES.md`) |
| Convert to venue template (IJF Word/LaTeX; TMLR LaTeX; PLOS ONE Word/LaTeX) | **OPEN-V** |
| Anonymisation for double-blind review (no author names, institution, repository URL that identifies authors) | **OPEN-V / OPEN-A** |
| Abstract/word-limit and keywords adjusted to venue | **OPEN-V** |
| Table/figure numbering reconciled with the template (manuscript refers to supplementary tables T1–T6, S2a–e) | **OPEN-V** |

## E. Declarations (authors only)

| Item | Status |
|---|---|
| Authors, affiliations, corresponding author | **OPEN-A** |
| Funding statement (none was stated; do not invent) | **OPEN-A** |
| Competing interests | **OPEN-A** |
| CRediT contributions (required by IJF) | **OPEN-A** |
| Generative-AI use declaration (the study code, analysis scripts and the draft were prepared with an AI coding assistant) | **OPEN-A** — must be made truthfully at submission |
| Ethics statement (public secondary data; no human-subject contact) | **OPEN-A** to confirm with institution |
| Data and code availability statement with the final repository link | **OPEN-A** |

## F. Venue

| Item | Status |
|---|---|
| Primary + two alternatives with verified scope information | DONE (`VENUE_COMPARISON.md`) |
| Fee / APC for each venue | **NOT VERIFIED** (IJF: not stated on pages read; PLOS ONE: page blocked, third-party figures conflict; TMLR: none stated) |
| Predatory-venue screen | partial: publishers' own pages only; name-alike "Forecasting" journal flagged |
| Decide primary venue and whether to post a preprint | **OPEN-A** |

## G. Final gate before the authors submit

1. Authors read the whole manuscript and every number against `results/TABLES.md`.
2. Authors fill Section 20 and the venue's declaration forms.
3. Do not re-run `make_freeze.py` (the freeze record is historical and must stay as written); re-run the verification commands in `REPRODUCIBILITY.md` on the release candidate instead.
4. Create the public archive (with DOI) only after the authors approve.
