# DecisionGPT R1 — Final Submission Audit

End-to-end integrity audit for the R1 IEEE submission package. **Publication
finalization only — no new experiment was run.** This document is the single
place a reader can confirm that the manuscript, its numbers, and every frozen
artifact are consistent and unchanged.

Date of this audit pass: 2026-09-07.

---

## 1. Experimental integrity

| Item | Value | Source |
|---|---|---|
| R1 locked-test run count | **exactly 1** | `experiments/r1/config.json` → `locked_test_run: true`; the runner refuses a second `run --partition locked_test` |
| Locked scenario families | 12 | `config.json` → `partitions.locked_test` |
| Structural scenarios | 34 / family × 12 = **408** | `statistical_results.json` → `n_scenarios_eligible: 408` |
| Seeds | 10 (`20260906`–`20260915`) | `config.json`, `R1_PREREGISTRATION.md` §7 |
| Decisions per condition | 34 × 12 × 10 = **4080** | `config.json` → `runs.locked_test.n_instances: 4080` |
| Harness errors | **0** | `config.json` → `runs.locked_test.n_error: 0` |
| Post-hoc exclusions | **0** | `statistical_results.json` → `excluded.count: 0` |
| Elasticity fallback rate on the locked run | **0.0 %** | `R1_PRELOCK_GATE.md` / `R1_RESULTS.md` |
| Pre-registration frozen | git `22ce18c965b61641f3dd28cc35e0cfac22f61dca`, **before** the run | `config.json` → `prereg.git_commit_at_freeze` |
| Master seed | `20260907` | `config.json` → `master_seed` |
| Suite checksum | `cd73f0d59aafa87c7b1502f24d2c737fc9d92e77f43280ee06fb43abfbba9afd` | `config.json` → `suite_checksum` |
| Raw locked results | `results.json` SHA-256 `9e302f1d1cf575940e62e9abdb66393c0e7d9e9d2f2ec940abe2bd161c853065` | `config.json` → `runs.locked_test.results_sha256`; re-hashed this pass ✅ |

**No re-run, re-seed, extension, retune, rebalance, or resample was performed.**

## 2. Frozen-artifact integrity (verified BEFORE and AFTER this pass)

| Artifact | Expected | BEFORE | AFTER |
|---|---|---|---|
| `experiments/experiment_manifest.json` | `94aa419c703b1babb465975463b26e55255755a7687ecbecadb6db4c4c15cbff` | ✅ match | ✅ match |
| `experiments/paper_results_snapshot.json` | `8e09d298ac3ba3cbdfe5cc7b9a06c092967a52bc69a42b3874105238623bf10a` | ✅ match | ✅ match |
| `docs/PAPER_DRAFT.md` | `72e454490845788b0996fd0bb4575d3ce6762839cac422fffa62f39a5da31d95` | ✅ match | ✅ match |
| `docs/ieee_paper/main.tex` | `25b1858fc1df596ce98238dc97bf80954566dfd13eb4e58b4103ceca6a73f26b` | ✅ match | ✅ match |
| `docs/ieee_paper/references.bib` | `f1ba0c8c3d3287442f80342d7aeac4776d83f53cb43d7b87ade0e4f33e4d0033` | ✅ match | ✅ match |
| `docs/ieee_paper/README.md` | `5069be0e1c728e6f4634e1592483a810a1f9300ce9ed0d43ba665ea8da336403` | ✅ match | ✅ match |
| `experiments/r1/results.json` | `9e302f1d…c853065` | ✅ match | ✅ match |

| Config state | Expected | Verified |
|---|---|---|
| R0 / D0 | `risk_model=None`, `risk_penalty_lambda=1.0`, `label()='full'` | ✅ (memory + `PipelineOptions()` defaults; production decision endpoint unchanged) |
| R3 | NOT PROMOTED (`RISK_FORMULA_VERSION == "extrapolation_range_v1"`) | ✅ |
| V1 | `status: evaluation_complete` | ✅ |
| V2 | `status: STOPPED_AT_PRELOCK_GATE`, `locked_test_run: false` | ✅ |
| R1 | `status: R1_COMPLETE`, `prereg_frozen: true`, `locked_test_run: true`, `result.classification: NEGATIVE` | ✅ |

`git diff --stat` on `experiments/experiment_manifest.json`,
`experiments/paper_results_snapshot.json`, `docs/PAPER_DRAFT.md`,
`docs/ieee_paper/`, `experiments/results/`, `experiments/upgraded_controlled_v1/`,
`experiments/upgraded_controlled_v2/`, and
`backend/app/{services,analytics,agents,decision_engine}` — **empty** before and
after. All R1 publication work is in new, untracked files.

## 3. Statistical integrity

| Check | Result |
|---|---|
| Independent recomputation from raw `results.json` (no reuse of summaries) | **75 / 75** checks reproduce (`experiments/r1/independent_recheck.json`) |
| Machine audit | **26 / 26** pass (`experiments/r1/MACHINE_AUDIT.md`) |
| Manuscript number cross-check vs frozen artifacts | **66 / 66** (59 headline + 7 per-family optimal-action rates recomputed from raw `results.json`) |
| Primary contrast `D_vs_B` | mean **+0.0852**, 95 % cluster-bootstrap CI **[+0.0479, +0.1231]**, Wilcoxon p **5.4×10⁻¹⁰**, Holm p ≈ 0, matched-pairs rank-biserial **−0.469**, D-better/tie/D-worse **99 / 35 / 274**, n≠ 373 |
| Sign convention | `X_vs_Y = regret_X − regret_Y`; negative ⇒ X better. Positive `D_vs_B` ⇒ **D worse**. |
| Robustness | **18 / 18** perturbation cells preserve the D-worse sign; `primary_conclusion_changes = false` |
| Leave-one-family-out | all 12 estimates positive, **+0.050 … +0.159** |
| Multiplicity | Holm over the pre-registered family `{B_vs_A, C_vs_B, D_vs_C, D_vs_B}`; raw + adjusted p both reported |
| Clustering | unit of analysis = scenario (n = 408); 10 seeds averaged to the scenario mean before every test; bootstrap resamples scenarios |
| Power | prospective, from development-stage variance (SD 0.282→0.30), `estimated_power = 0.894`; tie-unaware (35/408 ties) — disclosed |

## 4. Publication integrity

| Item | Status |
|---|---|
| Manuscript | `docs/ieee_paper_r1/main.tex` — IEEEtran `conference`, two-column, 24 numbered sections + Reproducibility Statement + Ethics, **9 tables, 5 figures** |
| LaTeX structural validation | ✅ all `\begin/\end` balanced; every `\ref` → a `\label`; every `\cite` (29 keys) resolves in `references.bib`; no orphan citations |
| LaTeX PDF compilation | **NOT performed** — no `pdflatex`/`bibtex`/`latexmk` in this environment. Header and `README.md` state this explicitly. |
| Figures | `figures/r1_figure{1..5}.svg` (reproducible from `experiments/r1/figure_data.json` via `scripts/r1_figures.py`) + `.pdf` (via `scripts/r1_figures_to_pdf.py`, svglib+reportlab). Not visually verified in a compiled PDF. |
| Tables | all 9 trace cell-by-cell to `experiments/r1/*.json` / raw `results.json`; 66/66 automated cross-check |
| Author block | names / order / affiliation / supervisor note mirror the frozen `docs/ieee_paper/main.tex`; **no** student IDs, ORCID, or funding asserted; corresponding-author contact left as placeholder |
| References | verbatim copy of the verified `docs/ieee_paper/references.bib`; no fabricated entries or DOIs |
| Forbidden-term / claim scan | `scripts/scan_r1_claims.py` → `experiments/r1/forbidden_term_scan.json`: **0 prohibited across 12 docs** including `main.tex` |
| Hostile review | `docs/R1_HOSTILE_REVIEW.md` — 16 dimensions; no Critical issue substantiated; addressed in the manuscript (scope + censored-demand foregrounded; dedicated "synthetic-artifact" rebuttal added) |
| Publication readiness | `docs/R1_PUBLICATION_READINESS.md` — 6 PASS / 5 QUALIFIED / 0 FAIL |
| Reproducibility package | `docs/ieee_paper_r1/README.md` — scope, provenance, commit, prereg hash, raw-result hash, analysis + figure commands, environment, and the explicit "reproduce analysis ≠ rerun experiment" distinction |

## 5. Remaining risks (honest list)

1. **PDF not compiled here.** Overfull boxes, page count, venue-template
   conformance, and a visual figure check (especially Fig. 2, 408 bars at
   column width) are unverified until the authors compile on a TeX install.
2. **Novelty framing.** A reviewer wanting a positive / deployment / real-SME
   result may see a synthetic negative result as incremental. Mitigation: the
   framing is explicit and the contribution is the diagnosis + minimal-correction
   method + mechanism + reproducibility, not a system-superiority claim.
3. **Research-only correction authored in-house.** `ε̂` is data-estimated (0 %
   fallback) and the scorer is an independent functional form, but a fully
   independent re-implementation of the correction would remove the last degree
   of freedom.
4. **Two D-favourable families are censored-demand.** Disclosed and foregrounded;
   the aggregate holds without them (LOFO +0.114 / +0.159), but a reviewer may
   still want a follow-up with an uncensored elasticity estimator (future work).
5. **External validity is F by construction.** The paper says so repeatedly; a
   reviewer who conflates controlled evaluation with validation will not be
   satisfied — correctly, and by design.
6. **No bundled lockfile / clean-room analysis rerun in this pass.** The repo's
   `requirements.txt` is pinned; a container + fresh-venv analysis rerun would
   strengthen the package.
7. **Citations are the verified V1 set** with no fresh 2024–2025 search.

None of these is fixable — or should be addressed — by running another
experiment.

## 6. Response to the strongest reviewer line

> "Your result is simply an artifact of a synthetic scenario design."

The manuscript answers this in Threats-to-Validity with four design features,
none of which claims equivalence to real-world validation:

1. **Independent ground truth.** The scoring objective is an additive-linear
   function — a different functional form from both the log-linear history engine
   and the constant-elasticity correction — statically verified to import no
   environment or pipeline code, and applied only *after* action selection. The
   oracle is reproduced by independent enumeration on all 408 locked scenarios.
2. **Multiple structural families.** The effect holds across 12 structurally
   distinct families and in 10 of 12 individually; leave-one-family-out is
   positive for every removal (+0.050 … +0.159).
3. **Pre-registration + one-shot lock.** Families, parameters, N, seeds, the
   contrast family, MEI, α, and the analysis code were frozen at git `22ce18c`
   before the single locked run; 0 exclusions, 0 tuning.
4. **Robustness.** The D-worse sign is unchanged in all 18 pre-registered
   perturbation cells (`primary_conclusion_changes = false`).

The transparent, disclosed research-only correction and the explicit
external-validity limitation are part of that answer — the paper does **not**
argue that a synthetic evaluation substitutes for real-world validation.

---

## Verdict

**The R1 submission package is internally consistent, numerically verified, and
frozen-artifact-clean.** It is ready to submit as a controlled component-level
evaluation / negative-result / reproducibility paper after the authors compile
the PDF and complete the venue-formatting pass. No experimental work remains;
attempting another experimental iteration is explicitly out of scope.
