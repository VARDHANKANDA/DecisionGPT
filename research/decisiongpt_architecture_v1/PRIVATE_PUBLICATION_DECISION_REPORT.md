# PRIVATE_PUBLICATION_DECISION_REPORT (2026-10-23) — for discussion with the guide and coauthors

Private. Nothing was submitted, uploaded, posted or sent; no similarity service or external AI service received the manuscript. Web access was used only to read public venue and policy pages. Evidence labels: **[F]** verified in a file or on an official page, **[I]** inference, **[?]** needs the authors/guide.

## 1. Executive recommendation

**Do not submit the current paper as a separate paper yet. Develop it as a consolidated/extended version of the R1 line of work (P1/P2), after two decisions and one small experiment (§11–§12).**

Reasons, in order of weight:
1. [F] The paper's central result (R1: the three-agent pipeline has +0.085 higher regret than simulation-only B, p = 5.4×10⁻¹⁰) and essentially every R1 number in its tables already appear in your earlier manuscript `docs/ieee_paper_r1/main.tex` — which has the **same title** — and mostly in `docs/ieee_paper_r2` and `overleaf/main.tex` (the PDF you attached). See `PRIOR_PAPER_OVERLAP_AUDIT.md` §2.
2. [F] What is genuinely new is real but incremental: the measured cost/quality–cost result, the independent recomputation with a replication check (and the three discrepancies it found), the full 80-scenario analysis, three sensitivity analyses, and the newer predictive benchmark.
3. [?] The status of the earlier manuscripts is unknown (draft, submitted, preprint?), and `origin/main` of the GitHub remote already holds P1 and the R1 report. IEEE conference policy forbids work "under review for another refereed publication" and requires a clear statement of how a new submission differs from earlier work (§6).
4. [I] The paper has an open scientific question that would make it stand on its own — *why* the pipeline loses (the risk-penalty hypothesis is untested on R1) — and a small, pre-registrable experiment would answer it.

## 2. Prior-paper overlap matrix (summary of the audit)

| Component | Directly reused | Re-analysed | Newly measured/analysed | Rewritten only |
|---|---|---|---|---|
| R1 408-scenario result set (D−B, B−A, C−B, D−C, ladder means, W/T/L, LOFO, robustness, mechanism counts) | ✔ | | | text, figures |
| A–D design, regret metric, statistics | ✔ | | rank-biserial convention disclosed | |
| 80-scenario study (full contrasts, family level) | | ✔ (one sentence in P2; details only in project docs) | family-level contrasts | |
| Sensitivity: fallback exclusion, first seed, re-run on another date | | | ✔ | |
| Cost and latency (408 scenarios + 96 repeats) | | | ✔ **NM** | |
| Predictive benchmark (M5 CA_1, Online Retail II, WAPE) and registry re-scoring | | | ✔ (benchmark run 2026-10-15 is after P0–P3; re-scoring 2026-10-22) | |
| Independent recomputation / replication check / discrepancies | | | ✔ | |
| Six-way ablation, risk-penalty diagnostic, causal graph | **not in the current paper**; present in P0/P3 | | | |
| Title, structure, prose | | | | ✔ (textual overlap ≈ 0.2 % of 6-word shingles; not scientific novelty) |

## 3. Which results are genuinely new / already reported

*Already reported (P1; most also P2/P3):* every R1 statistic in the current paper's RQ2/RQ3 section.
*New:* (a) cost per workflow: median 4.00 s (B, C) vs 4.35 s (D), D/B 1.08 (95 % CI 1.06–1.10), orchestration overhead 0.36 s (8 % of D), 0 model requests, timing noise ≈ 35 %, D dominated on (cost, regret); (b) 80-scenario results: D−B +0.034 (inconclusive), D−A +0.109 (Holm 0.003); (c) sensitivity: +0.085 without the 69 fallback instances, +0.078 first seed, +0.075 re-run (5/408 D choices differ); (d) discrepancies in earlier artifacts (§5); (e) predictive summary with strong baselines. All values re-confirmed from `results/*.json` this session (no experiment was re-run).

## 4. Novelty assessment

[I] Strongest defensible contribution: **a combination** — a reproducible negative-result evaluation (ladder) **plus** a measured quality–cost comparison **plus** an audit that found real inconsistencies in earlier artifacts. Taken alone, the quality–cost comparison (the only wholly new decision-relevant measurement) is modest: the agents add ~0.4 s over the simulator, so the "cost" side is not informative beyond "compute cost is small".
Not defensible: that multi-agent systems are inferior in general; that results transfer to real SMEs or LLM agents; that the risk term *causes* the loss (untested on R1). Replacing the title or restructuring the paper does not add scientific novelty.

## 5. Strengths and weaknesses of the current evidence

Strengths: pre-registered, locked, one-shot R1 and upgraded-v1 runs with exogenous scoring; independent recomputation reproduces every stored mean and p; honest disclosure of discrepancies; reproducible package; sensitivity results all agree.
Weaknesses: (1) synthetic benchmark authored by the same team; scorer is deterministic and risk-neutral, so a risk-averse optimizer is penalised (construct validity); (2) agents are rule-based, not LLM agents; (3) one code base, ~8 candidate actions; (4) R1 uses a research-only corrected simulator; (5) the 80-scenario study (production simulator) is inconclusive for the headline contrast; (6) cost timings are noisy and from one loaded laptop; (7) the mechanism of the loss is not established on R1; (8) the 5/408 flips on re-run are attributed to date-anchored histories but not tested; (9) **errors in earlier manuscripts**: "0.0 % fallback" (stored run: 69/4080 = 1.7 %), reversed W/T/L labels in the stored upgraded-v1 statistics file, undocumented rank-biserial convention.

## 6. Duplicate-publication and extended-version risks (official policies read 2026-10-23)

* IEEE Author Center, *Submission Policies* — <https://conferences.ieeeauthorcenter.ieee.org/author-ethics/guidelines-and-policies/submission-policies/> [F]: authors "should only submit original work that has neither appeared elsewhere for publication" nor be "under review for another refereed publication"; multiple submission = concurrent consideration by two or more publications; prior work "should be cited in the submitted article" and the submission must "very clearly" state "how the new submission differs from the previously published work(s)"; recycled material must be indicated with a full reference to the original.
* IEEE PSPB Operations Manual §8.2.4.F (handling of duplicate submission/self-reuse) is referenced from that page; its text was not retrievable [?]. A related page (<https://www.ieee.org/publications/rights/section-821>) returned no text.
* Extended conference → journal papers: sources conflict on a "30 % new material" rule; the IEEE COMPSAC 2020 page states 30 % (<https://ieeecompsac.computer.org/2020/jc-cj/>), whereas ComSoc says current IEEE policy is "substantial" difference at the editor's discretion, citing PSPB §8.1.7.E (<https://comsoc.org/publications/journals/ieee-tcom/information-authors/conference-vs-journal-papers>) [F as stated by those pages; the Operations Manual itself was not read]. Journal policies decide; text and figures may be reused if cited and disclosed.
* COMPSAC 2027: "Simultaneous submission to other publication venues is not permitted"; CrossCheck screening of all submissions; double-blind (<https://ieeecompsac.computer.org/2027/information-for-authors/>) [F]. CAIN 2027: submissions "must not be under review or submitted elsewhere"; preprints on arXiv are allowed but the title must not be publicised during review (<https://conf.researchr.org/track/cain-2027/cain-2027-call-for-papers>) [F].
* Status of P0–P3 [?]: **not established by the repository.** Evidence: P1, P0 and the R1 report are on the remote tracking branch; no file records a submission, acceptance, DOI or preprint ID; `docs/ORIGINALITY_AUDIT.md` calls an earlier `overleaf/main.tex` a "two-column preprint version" (ambiguous wording). If any of P0–P3 is under review elsewhere, do not submit overlapping work. If one is published, the current paper must cite it and state the delta as above; copyright/reuse terms then apply. If the GitHub repository is public, P0/P1 are publicly available (a technical-report-like state) and must be cited.
* Double-blind self-citation: both candidate venues require citing one's own work in the third person and anonymising artifact links; the current manuscript does so via one anonymised reference.
* Coauthors: authorship and order must be agreed with all coauthors and the guide (§10). Note: P0/P1/P2 list K. S. Sri Vardhan as corresponding author and a faculty supervisor in a `\thanks`; the attached P3 has neither, and the current private author block follows P3. [F]

## 7. Alternative venue candidates (official information read 2026-10-23; none is a guarantee of acceptance)

| Rank | Venue | Official source | Verified facts | Fit / main risk | Revisions | Page-limit implication |
|---|---|---|---|---|---|---|
| 1 (best topical fit, tight deadline) | **IEEE/ACM CAIN 2027** (Conference on AI Engineering – Software Engineering for AI; co-located with ICSE 2027, Dublin; IEEE format this year) | <https://conf.researchr.org/track/cain-2027/cain-2027-call-for-papers> | research papers due **Fri 30 Oct 2026 AoE, "firm, no extensions"**; notification 11 Jan 2027; **10 pages + up to 2 for references**; double-anonymous, 3 reviews; IEEE/ACM Digital Libraries; "Secondary studies, replication studies, and negative results are also welcome"; at least one author must register and present; conference dates TBA | strongest match to a negative-result/replication-style evaluation of an AI-enabled system. Risks: only 7 days left; overlap decision and author consent unresolved; "predominantly data science or ML algorithms" desk-rejected (the paper is a systems evaluation, so low risk) | add an explicit software-engineering framing (architecture trade-offs, cost); keep anonymisation; state the delta vs the earlier manuscript | current ~9 pages + refs fits |
| 2 (feasible window) | **IEEE COMPSAC 2027**, Tokyo, 13–16 Jul 2027 | <https://ieeecompsac.computer.org/2027/information-for-authors/>, <https://ieeecompsac.computer.org/2027/call-for-papers/> | full papers due **31 Jan 2027** (time zone not stated; 2026 FAQ said 23:59 AoE); **10 pages including references**; double-blind; AI use disclosed in acknowledgments; submission system not yet stated; theme "Trusted Agentic Ecosystems Engineering for Autonomous Intelligence" | theme fits (agentic, assurance, evaluation); CFP lists no tracks. Risk: dual-submission/CrossCheck exposure to P1/P2/P3; no stated policy on negative results | consolidate with new evidence (§12) so the delta is substantive; keep the AI disclosure | currently exactly 10 pages incl. references; any addition needs cuts |
| 3 (journal route for a consolidated paper) | **Decision Support Systems** (Elsevier) | <https://shop.elsevier.com/journals/decision-support-systems/0167-9236> (scope); Guide for Authors <https://www.sciencedirect.com/journal/decision-support-systems/publish/guide-for-authors> returned HTTP 403 | scope: "foundations, functionality, interfaces, implementation, impacts, and evaluation of decision support systems"; article types, negative-result policy, preprint/AI policies, length **not verified** | scope fits; risk: journals expect a substantially larger contribution than the current paper, and a consolidated R1+cost+mechanism manuscript | expand with the mechanism experiment, real or risk-sensitive evaluation, fuller related work | no tight limit expected [?] |

Not recommended now: **AAMAS 2027** main track (deadline 8 Oct 2026 AoE already passed; 8 pages + refs; <https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/call-for-main-track/>); **ICSA 2027** (research-track dates not published; Early-Career track "dates TBA", <https://conf.researchr.org/track/icsa-2027/icsa-2027-early-career-track>); **IEEE CAI 2027** (submission dates not posted; <https://cai.ieee.org/2027/>); **IEEE Access** (acceptance based on "originality and technical correctness", ~20 % acceptance per its landing page, <https://ieeeaccess.ieee.org/authors/>; scope, APC and negative-result policy were not retrievable — treat as an unverified fallback only).

## 8. Revisions needed before any submission (all candidates)

1. Resolve the overlap and title (§11); cite the earlier manuscript(s) and write a precise "what is new" paragraph.
2. Correct the earlier artifacts that contain the "0.0 % fallback" statement and the unlabeled rank-biserial convention (do not edit frozen files without a documented amendment).
3. If kept as a separate paper: drop the full R1 tables (cite P1) and lead with the new material (cost, audit, 80-scenario, sensitivity) and the mechanism test.
4. Replace the system name or the author-identifying phrases only if the venue's double-blind rule and the public status of the repository require it.

## 9. Evidence adequacy by candidate

* CAIN 2027: adequate as a negative-result/replication evaluation *if* the delta over P1 is accepted; weak on "SE for AI" framing (no engineering study of costs beyond compute time).
* COMPSAC 2027: adequate for a controlled-evaluation paper; reviewers will weigh the synthetic-only and rule-based-agent limits.
* DSS journal: insufficient as is; needs substantially more.

## 10. Questions only you, your coauthors and your guide can answer

1. Have P0, P1, P2 or P3 been submitted anywhere, posted as a preprint, or shared publicly? Is the GitHub repository `VARDHANKANDA/DecisionGPT` public?
2. Which manuscript is the vehicle for the R1 result: P3 (system paper, contains R1 as a subsection), P1/P2 (R1 paper), or a consolidated paper? Two papers should not both lead with the same result.
3. Authorship: who are the authors of this paper, in what order, and is the faculty supervisor (listed in P0/P1/P2, absent in P3) an author or acknowledged? Who is the corresponding author?
4. Is the AI-assistance disclosure (code, analysis, text drafted with Claude) acceptable to the guide and to the target venue's policy?
5. Do you want to run the experiments in §12 before choosing a venue?

## 11. Minimum next steps before submission

1. Answer §10 (1)–(3); do not submit anything until then.
2. Choose one vehicle for R1; unify or change titles.
3. Run the two small experiments in §12 (not run automatically) or consciously decide not to.
4. Write the delta statement; correct the earlier "0.0 %" statements.
5. Rebuild the anonymous PDF; re-check page limit and anonymisation for the chosen venue.

## 12. Smallest additional experiments that would materially strengthen the contribution (not run)

| # | Experiment | Why it matters | Cost |
|---|---|---|---|
| E1 | Re-run the 5 instances whose D choice changed with the history anchored to the stored run's date (or fixed anchor date) | converts the date-anchoring hypothesis into a finding; removes the non-reproducibility caveat | minutes; no new data |
| E2 | A new pre-registered locked comparison on the R1 scenarios of D with the risk penalty neutralised (λ = 0, risk manager unchanged) vs D and B | tests the risk-term mechanism on the well-specified simulator; turns "hypothesis" into evidence and is the one result not in P0–P3 for R1 | one locked run (~1–2 h compute at the measured per-instance time) + prereg document |
| E3 (optional) | Score the same stored selections with a risk-adjusted ground truth agreed before looking | addresses the construct-validity objection | needs a stochastic scorer; moderate |
| – | Real SME outcome data; an LLM-agent variant | the real external-validity gaps; **blocked** (no data, no provider) | — |

## 13. Clear recommendation

**Develop as an extended/consolidated version, not as a separate submission now.** Merge the R1 paper's evidence with the new cost, audit, 80-scenario and sensitivity material, add E1/E2, cite P3 as the system paper, and then target COMPSAC 2027 (31 Jan 2027) or, if the authors can settle §10 within a week, CAIN 2027 (30 Oct 2026). If the status of earlier manuscripts turns out to be "under review elsewhere", do not submit overlapping work at all.

## 14. Corrections made to project files in this pass

* `overleaf/architecture_paper_v1/SUBMISSION_CHECKLIST.md`: the earlier statement that "no corresponding-author or supervisor designation is documented" was incorrect (P0/P1/P2 document both); corrected. No manuscript text, result or frozen artifact was changed. A baseline zip of the paper folder is in `baseline_snapshots/`.
