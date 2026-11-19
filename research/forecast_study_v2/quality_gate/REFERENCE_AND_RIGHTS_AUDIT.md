# REFERENCE_AND_RIGHTS_AUDIT — R3 quality gate (2026-10-22)

Verifier: the same AI assistant that wrote the study (not an external audit). Sources were read through the tools available in this session (publisher pages, Crossref, OpenAlex, Semantic Scholar, IDEAS/RePEc, arXiv API, Lancaster eprints, the Kaggle rules page rendered in a browser, UCI page, venue pages). **Verification levels:** *full text* (read in this session), *abstract*, *metadata* (Crossref/OpenAlex/publisher listing: authors, title, year, venue, pages, DOI), *not accessed*.

## 1. Scope and limits of the literature work

The review behind the manuscript is **bounded, not systematic**: sources were found by targeted searches on the topics below and by following citations of the sources read. It cannot show that no earlier work combines endpoint-matched validation selection, never-scored windows under a written freeze, a large prespecified baseline set and paired two-way dependence-aware intervals; the manuscript says only that no such report was found in the sources reviewed. The novelty claim is correspondingly weak: the dependence of the best point forecast on the scoring function is established theory (Gneiting 2011; Koenker & Bassett 1978; Kolassa 2020), and the contribution is the quantification described in the manuscript.

## 2. Claim-level verification (what each cited work was checked for)

| manuscript statement | reference(s) | level | evidence seen | status |
|---|---|---|---|---|
| In M5, most examined methods and almost all top-50 methods with a description were LightGBM-based | Makridakis et al. 2022 (IJF 38, 1346) | **full text of a pre-publication copy** (ResearchGate PDF, 45 pp.); published article not accessible (HTTP 403) | "most of the methods examined utilized LightGBM"; "almost all" of the top-50 methods "for which a method description was available" trained LightGBM models; the 50 top-performing methods beat the best statistical benchmark by >14 % on the competition metric | supported; an earlier draft said "all of the top 50" — **corrected** (R2) |
| Tree-based methods out-shone other solutions in M5 | Januschowski et al. 2022 | abstract | "Tree-based methods out-shone other solutions, in particular deep learning-based solutions" | supported |
| Kaggle retail-type competitions with intermittent data: GBDT and neural networks strong | Bojer & Meldgaard 2021 | abstract | "gradient boosted decision trees and neural networks are strong forecast methods"; data "are intermittent" | supported |
| Scoring function and task must match; mean ↔ squared error, quantile ↔ absolute error | Gneiting 2011; Koenker & Bassett 1978 | abstracts (Gneiting also on arXiv) | Gneiting: misguided inferences unless the scoring function and the forecasting task are matched; functionals such as the mean or a quantile. Koenker & Bassett: least-absolute-deviation estimator as the special case of regression quantiles (Econometric Society listing) | supported |
| Why the "best" point forecast depends on the measure | Kolassa 2020 | metadata/title only (invited commentary; no abstract retrievable) | — | cited for the general point only; not read |
| Conventional accuracy measures can rank intermittent-demand forecasters incorrectly; percentage-error measures degenerate with zeros | Prestwich et al. 2014; Hyndman & Koehler 2006 | Prestwich abstract; **Hyndman & Koehler full text** (author-site PDF, 18 pp.) | Prestwich: "almost all known measures rank forecasters incorrectly on intermittent demand series". H&K: percentage errors infinite/undefined with zeros; "intermittent demand data often contain zeros"; only the MASE usable on such series. H&K do **not** state that MAE rewards zero forecasts — that statement is attributed in the manuscript to scoring-function theory, not to H&K | supported (as restated) |
| WAPE/wMAPE and MAD are unsuitable for evaluating count-data forecasts | Kolassa 2016 | abstract (IDEAS/RePEc) | "classical point-forecast accuracy measures ... MAD, MASE and wMAPE are inherently unsuitable for count data" (paraphrase of the abstract) | supported for the abstract-level statement; **now cited in R3 as a limitation of the primary endpoint** (issue SI-07) |
| Optimisation and selection of intermittent-demand models, evaluation by error metrics | Kourentzes 2014 | abstract (Lancaster eprints) | conventional error metrics evaluated for parameter optimisation; two new metrics proposed | topic citation |
| Aggregation changes the forecasting problem | Nikolopoulos et al. 2011; Athanasopoulos et al. 2017 | abstracts | ADIDA time-bucket aggregation; temporal hierarchies | supported |
| Hierarchical reconciliation (related work) | Hyndman et al. 2011; Spiliotis et al. 2021 | metadata (abstracts read in an earlier pass) | — | topic citation |
| ML does not automatically beat statistical methods | Makridakis et al. 2018; Makridakis et al. 2020 | abstracts | 2018: ML methods dominated by statistical ones on a monthly M3 subset; M4 abstract (earlier pass) | supported (different data) |
| Retail forecasting practice; evaluation guidance | Fildes et al. 2022; Hewamalage et al. 2023; Spiliotis et al. 2022 | abstracts (Fildes, Hewamalage); metadata (Spiliotis) | — | supported / metadata only |
| Local vs global models for intermittent series (preprint) | Damato et al. 2026 | arXiv API (authors, title, date) | — | verified; preprint, not peer-reviewed |
| Methods: LightGBM, XGBoost, gradient boosting, Croston, SBA, TSB | Ke 2017; Chen & Guestrin 2016; Friedman 2001; Croston 1972; Syntetos & Boylan 2005; Teunter et al. 2011 | metadata (Ke et al.: NeurIPS proceedings page: 8 authors) | — | definitions standard |
| Inference methods | Cameron et al. 2011; Owen 2007; Owen & Eckles 2012; Politis & Romano 1994; Diebold & Mariano 1995 | metadata | — | implemented from the original descriptions; coverage checked only in a synthetic simulation |
| Online Retail II dataset | Chen 2012 | UCI page | CC BY 4.0, DOI 10.24432/C5CG6D, 1,067,371 instances, donated 2019 | verified |
| Statistical models | Nixtla statsforecast 2.1.1 (v3 study) | package metadata | — | version pinned; no citation to a peer-reviewed article was verified for it |

Bibliographic metadata of the 32 reference entries were machine-compared with Crossref (29 DOI entries), the NeurIPS page, the arXiv API and the UCI page (`REFERENCE_AUDIT.csv`). **Not accessed:** full text of the published M5 article, Kolassa 2016 and 2020, Kourentzes 2014, Gneiting 2011 (abstract only), and the other cited works beyond the levels above. **A human must read the sources behind each citation before submission.**

## 3. Data rights (authoritative pages read 2026-10-22; not legal advice)

**M5 Forecasting–Accuracy** (Kaggle, University of Nicosia competition). Rules page, "Competition Data": *Data Access and Use:* "You may access and use the Competition Data for non-commercial purposes only, including for participating in the Competition and on Kaggle.com forums, and for academic research and education." *Data Security:* "You agree not to transmit, duplicate, publish, redistribute or otherwise provide or make available the Competition Data to any party not participating in the Competition." The rules do not say whether derived forecasts or aggregate statistics may be shared.
* Academic research use for this study: consistent with the clause.
* **Not to be released:** the raw files; `predictions.npz` (contains the actual sales `y`); the fitted forecast arrays (`fits/*.npy`), which reproduce forecasts of M5 series; the stored `y.npy` series arrays of v3.
* **Uncertain — requires confirmation by the rights holder or a qualified person:** whether (i) aggregate result tables and figures, (ii) code and configurations containing series identifiers, (iii) forecasts without actuals, may be published. The manuscript treats (i) and (ii) as acceptable derived statistics and (iii) as not cleared.

**Online Retail II** (UCI; creator Daqing Chen): CC BY 4.0; credit required; no other restriction stated on the dataset page. Redistribution of the data and derived arrays is permitted with attribution (not a legal guarantee).

**Software:** LightGBM, XGBoost, scikit-learn, pandas, numpy, scipy are permissively licensed (not audited here); statsforecast / statsmodels (v3) licences were not audited.

## 4. Venue instructions (see `VENUE_COMPARISON.md` for the table)

Verified from official pages in this session: TMLR author guide, editorial policies and acceptance criteria; PLOS ONE data-availability policy and AI policy. **Not verified** (pages returned HTTP 403 or were not reachable): the International Journal of Forecasting guide for authors (APC, data policy, AI declaration, review type) and the PLOS fee page (a search summary quoted USD 2,477; not confirmed). Third-party or earlier-session descriptions were not used to fill these gaps.
