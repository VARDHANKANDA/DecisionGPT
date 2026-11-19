# SUBMISSION_CHECKLIST — forecast_study_v2 manuscript R2 (status 2026-10-22)

DONE = completed in this package; AUTHOR = requires the authors; OPEN = not done.

| # | item | status |
|---|---|---|
| 1 | Research question, hypotheses and decision rules fixed before outcomes | DONE (internal hash freeze; not a public pre-registration) |
| 2 | Confirmatory window with no earlier scoring of the evaluated entities | DONE (`WINDOW_USE_AUDIT.md`; period exposure disclosed) |
| 3 | All prespecified results reported, including inconclusive cells | DONE (Tables 2–4, A1) |
| 4 | Boundary cell (TX_1 H28, subset-day) resolved without changing any rule or stored result | DONE (`SUPPLEMENTARY_H3_RESOLUTION.md`; frozen verdict confirmed) |
| 5 | Claim–evidence matrix; claim-level reference check | DONE (`CLAIM_EVIDENCE_MATRIX.csv`, `REFERENCE_CLAIM_CHECK.csv`) |
| 6 | Tables generated from stored artifacts; numbers in prose checked | DONE (`tools/build_tables.py`, `tools/check_numbers.py`: 49/49) |
| 7 | Figures 1–3 embedded (PNG for review, PDF/SVG for typesetting) | DONE in `MANUSCRIPT_R2.md`; typesetting in the venue template OPEN |
| 8 | References checked | DONE at metadata level (Crossref/OpenAlex/publisher pages); claims checked mostly against abstracts and one pre-publication copy of the M5 report; **AUTHOR: read the sources behind each citation; M5 published version and Kolassa 2016/2020, Kourentzes 2014 not read** |
| 9 | Data-use terms confirmed from authoritative pages | DONE (Kaggle M5 rules text; UCI page); **AUTHOR: confirm with the rights holder if forecasts or aggregates are to be shared** |
| 10 | Restricted M5 data / sales-bearing predictions excluded from any release | DONE as a rule (`submission_prep/README.md`); AUTHOR: do not upload them |
| 11 | Venue instructions | PARTLY: TMLR and PLOS data/AI policies read; IJF guide and PLOS fee page unreachable (see `VENUE_COMPARISON.md`) |
| 12 | Template / anonymisation / BibTeX | PARTLY: `submission_prep/` has LaTeX starting point and `references.bib`; venue style file not downloaded (AUTHOR) |
| 13 | Author names, affiliations, contributions, funding, competing interests, ethics, AI-use declaration | AUTHOR (explicit placeholders in §14) |
| 14 | Statistical baselines (ETS/ARIMA/Theta) | OPEN: proposal only (`PROPOSAL_STATISTICAL_BASELINES.md`); AUTHOR decision |
| 15 | External validation / independent replication | NOT DONE (same-agent verification only) |
| 16 | Clean-environment reproduction | PARTIAL: one cell (Online Retail II, W2, H = 7) reproduced exactly in a fresh venv; 21 cells not re-run |
| 17 | Submission, accounts, fees, editor contact | NOT DONE — author action |
