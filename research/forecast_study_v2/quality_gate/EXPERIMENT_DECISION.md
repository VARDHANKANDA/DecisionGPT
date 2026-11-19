# EXPERIMENT_DECISION — R3 quality gate (2026-10-22)

Decisions are made from the audit evidence (`INITIAL_AUDIT.md`, `SCIENTIFIC_ISSUES.csv`, `results/audit_sensitivity.json`), not from a wish for favourable results. Nothing below changes, replaces or is merged into the frozen v2 study.

## 1. Issues driving the decisions

| issue | severity | evidence | what would address it |
|---|---|---|---|
| SI-03 no ETS/ARIMA/Theta (and no other competitor classes) | major | `PROPOSAL_STATISTICAL_BASELINES.md`; manuscript Limitations | a fresh-window comparison with these baselines (E3) or an explicit scope restriction |
| SI-01 selection among eight candidates on three validation blocks with margins of 0.02–1.1 % | major | `audit_sensitivity.json` (B) | scoring all candidates on W2 test (E2, exploratory) and reporting the class-level result |
| SI-02 item-day gain not shown for asymmetric loss | major | `audit_sensitivity.json` (C) | already computed on stored predictions (exploratory); no new experiment needed |
| SI-05 dual-method rule shares dependence assumptions; weekly autocorrelation up to +0.65 | moderate | `audit_sensitivity.json` (A) | already computed (stationary-week sensitivity: all 22 H1/H2 verdicts unchanged); no new experiment needed |
| SI-12 reproduction coverage 1/22 | minor | R2 report | full clean-environment reproduction (E1) |

## 2. Experiments

| id | decision | rationale | protocol / inference | scope relation to v2 | resources |
|---|---|---|---|---|---|
| **E1** clean-environment reproduction of all 22 cells | **approved and run** | the only way to turn "reproduced 1/22" into a defensible coverage statement; no new hypothesis | fresh Python 3.12.0 venv with the pinned `requirements.txt`; each (window, dataset) pair re-run with the v2 pipeline (`stage both`, seeds 43/44 for W2) into a scratch directory outside the repository; compare selections, baseline identities, every stored method summary, and the selected models' forecasts element-wise | none (re-execution) | ≈ 3–4 h (4 cores) |
| **E2** selection-robustness (all 8 candidates on the W2 test blocks) | **approved, exploratory, post-hoc** | tests whether the item-day advantage is a property of the median-type class or of the selected configuration (winner's curse); needed to word the main claim correctly | refit the 8 candidates on the 6 W2 test blocks with the frozen pipeline functions; compare improvement over the same validation-selected baselines; report rank of the selected model, spread across median-type candidates, mean-type candidates; **no p-values, no new decision rule**; forecasts kept outside the repository | exploratory supplement on the confirmatory window; reported as such; may not be used to change any H1 verdict | ≈ 1 h |
| **E3** fresh-window study with ETS/ARIMA/Theta (`forecast_study_v3_fresh_stats`) | **approved, scaled down, separately versioned** | the largest remaining reviewer concern; a fresh window (M5 stores CA_2, TX_2, WI_2 × W4) exists whose targets were never scored for any entity and the stores were never evaluated; feasibility pilot (statsforecast 2.1.1, 4–16 series): Theta ≈ 0.43 s, ETS ≈ 0.43 s, restricted AutoARIMA ≈ 1 s per series-origin under load | `forecast_study_v3_fresh_stats/PROTOCOL_V3.md`: 3 stores × 2 horizons = 6 cells; v2 candidates, rules, inference unchanged; 31 + 6 baselines; primary H1 = item-day model vs best matched baseline of the expanded set; secondary H1b/H2/H3, H1-orig; interpretation rules fixed before outcomes; hash freeze (`FREEZE3.json`) before any data of the stores is modelled or scored | separate confirmatory family, never merged into v2 counts | statistical baselines ≈ 4–6 h (4 workers) + learned models ≈ 1–1.5 h |
| E3-b (replication on W2 for the three stores, other 4 unused stores) | **deferred** | doubles compute; the primary question is answerable on W4; further stores would be a later study | — | — | — |
| CatBoost, extra LightGBM tuning, neural models | **rejected** | would not test a different hypothesis relevant to the question ("does the median-type class beat simple baselines at item-day?"); invites a model search the frozen design excludes | — | — | — |
| probabilistic / quantile-score evaluation, decision-cost analysis | **deferred** (pinball sensitivity done exploratorily) | no real cost inputs exist; any cost analysis would be illustrative, not evidence of business value; proper-score evaluation requires probabilistic forecasts not produced by the study | — | — | — |
| bias-corrected median model (to separate "median bias" from "median-type ranking") | **deferred** | useful mechanistic check but would be a new model variant; belongs in a separately specified study | — | — | — |
| external replication by an independent researcher | **cannot be done by the assistant** | needs a human; requested in the review package | — | — | — |

## 3. Why E3 is scaled to three stores

Three stores × two horizons = six cells equals the size of v2's M5 confirmatory family and keeps the statistical-baseline compute within hours. Seven stores (the original proposal) would be about 2.3× the compute with no new hypothesis. The store choice (lowest-numbered unused store per state) is deterministic and fixed in the protocol before any of their data is modelled.

## 4. Does anything change the scope of the original study?

No. E1 re-executes it; E2 and the sensitivity analyses are exploratory supplements; E3 is a new, separately frozen study. The R3 manuscript reports E3 in its own section with its own labelling.
