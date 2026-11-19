"""Step 13: REFERENCE_AND_DATA_RIGHTS_AUDIT.csv from the automated registry checks (work/step9_refs.json) plus the manual verifications done during the audit."""
import csv
import json
from pathlib import Path

AUD = Path(__file__).parent
refs = json.load(open(AUD / "work" / "step9_refs.json", encoding="utf-8"))
rows = []

# per-reference: what the automatic check found, and manual notes
MANUAL = {
    "Guo": ("PMLR page proceedings.mlr.press/v70/guo17a.html read: title, 4 authors in order, ICML 2017, PMLR 70, pp. 1321-1330 all match", "Cited for 'ECE with ten equal-width bins': the cited paper defines ECE with equal-width bins; the bin count used there was NOT checked in this audit, so the manuscript should say only that the ECE definition follows Guo et al. and state its own bin policy", "supports the definition; bin count not checked"),
    "Holm": ("Not available on Crossref; JSTOR stable record 4615733 / DOI 10.2307/4615733 reported by secondary sources (search results), Scand. J. Statist. 6(2):65-70 matches", "Supports the procedure cited.", "verified (secondary sources; publisher page not opened)"),
    "Ke, G.": ("NeurIPS proceedings page read: title, 8 authors, NIPS 2017 (vol. 30) match; page range not shown", "Supports the model citation.", "verified (pages absent in manuscript)"),
    "Prokhorenkova": ("NeurIPS proceedings page read: title, 5 authors, NeurIPS 2018 (vol. 31) match; page range 6638-6648 stated in the manuscript NOT confirmed by the page", "Supports the model citation.", "verified except pages (unconfirmed)"),
    "Gibbs": ("arXiv record matches title/authors/year; NeurIPS 2021 volume 34 venue confirmed via search of the NeurIPS proceedings entry", "Supports 'coverage can drift under distribution shift' (the paper targets distribution shift).", "verified"),
    "Ansari": ("arXiv record matches title/authors/year; TMLR 2024 confirmed via search (OpenReview forum gerNCVqqtR)", "Cited only to name foundation models as not evaluated.", "verified"),
    "Damato": ("arXiv record matches title/authors/year; preprint (not peer reviewed when read)", "Cited as related work (local vs global on intermittent series); flagged preprint in text.", "verified (preprint)"),
    "Hewamalage": ("Crossref: print vol. 37(2) 2023, pages 788-832 match; registry 'issued' year 2022 = online-first", "Supports 'pitfalls in forecast evaluation'.", "verified (year convention: online 2022 / print 2023)"),
    "Spiliotis": ("Crossref: vol. 22(3), pages 3037-3061 match; registry 'issued' year 2020 = online-first; print year 2022", "Sentence 'report lower error and bias for some ML methods' not re-read in this audit (abstract-level support from the earlier literature pass).", "verified metadata; claim support partially checked"),
}
for e in refs:
    key = next((k for k in MANUAL if k in e["manuscript_text"][:40]), None)
    auto = []
    if "registry_title" in e:
        auto.append(f"title match={e.get('title_in_manuscript')}; first-author match={e.get('first_author_matches')}; year match={e.get('year_matches_registry')}; pages match={e.get('pages_match_registry')}")
    man = MANUAL.get(key) if key else None
    rows.append({"item_type": "reference", "item": e["manuscript_text"][:140], "source_checked": e.get("source", "") + (" | " + man[0] if man else ""),
                 "automatic_field_check": "; ".join(auto) or "n/a (no DOI/arXiv id in manuscript)", "supports_the_attached_sentence": man[1] if man else "see in-text rows below",
                 "status": (man[2] if man else ("verified" if all(e.get(k) in (True, None) for k in ("first_author_matches",)) and e.get("title_in_manuscript") else "check")),
                 "action": "Add DOI/page range where missing; report print vs online year consistently" if key in ("Hewamalage", "Spiliotis", "Ke, G.", "Prokhorenkova") else "none"})

IN_TEXT = [
    ("Makridakis et al. 2022a - 'tree-based methods dominated the top of the M5 competition'", "M5 article body read (ScienceDirect): LightGBM used by all of the top 50 competitors", "supported", "none"),
    ("Januschowski et al. 2022 - boosted trees in competitions", "Bibliographic data verified; abstract-level support from the prior literature pass; not re-read in this audit", "plausibly supported", "re-read before submission"),
    ("Bojer & Meldgaard 2021 - boosted trees in Kaggle retail competitions", "Bibliographic data verified; abstract-level support from the prior literature pass", "plausibly supported", "re-read before submission"),
    ("Kolassa 2020 - best point forecast depends on the error measure", "Article page read: expected value minimises MSE; other measures other functionals", "supported", "also cite Gneiting 2011"),
    ("Angelopoulos & Bates 2023 - 'Mondrian' split-conformal", "Tutorial covers conformal prediction and conditional/group coverage; the term 'Mondrian' is, to my knowledge, from Vovk and co-authors (NOT verified in this audit)", "partially supported", "verify the attribution of 'Mondrian' conformal and cite the original source if confirmed"),
    ("Saito & Rehmsmeier 2015 - PR-AUC reporting", "Title/abstract supports PR vs ROC on imbalanced data", "supported", "none"),
    ("Syntetos & Boylan 2005 - SBA correction; Croston 1972; Teunter 2011 - TSB", "Metadata verified; standard attributions", "supported", "none"),
    ("Künsch 1989 / Politis & Romano 1994 - block / stationary bootstrap", "Metadata verified; standard attributions", "supported", "none"),
]
for it, src, st, act in IN_TEXT:
    rows.append({"item_type": "in-text citation support", "item": it, "source_checked": src, "automatic_field_check": "", "supports_the_attached_sentence": st, "status": st, "action": act})

MISSING = [
    ("Gneiting, T. (2011). Making and evaluating point forecasts. JASA 106(494):746-762. doi:10.1198/jasa.2011.r10138", "Crossref record verified; abstract (arXiv/alphaXiv) says scoring function must match the target functional; absolute error <-> median (secondary sources)", "NOT CITED in manuscript - closest theoretical precedent of the central finding"),
    ("Prestwich, Rossi, Tarim & Hnich (2014). Mean-based error measures for intermittent demand forecasting. Int. J. Production Research 52(22):6782-6791. doi:10.1080/00207543.2014.917771", "Crossref record verified; abstract (arXiv 1310.5663): almost all known measures rank forecasters incorrectly on intermittent demand", "NOT CITED - directly relevant to item-day absolute-error metrics on intermittent demand"),
    ("Kolassa, S. (2016). Evaluating predictive count data distributions in retail sales forecasting. IJF 32(3):788-803. doi:10.1016/j.ijforecast.2015.12.004", "Crossref record verified (content not read)", "NOT CITED - candidate; read before citing"),
    ("Kourentzes, N. (2014). On intermittent demand model optimisation and selection. Int. J. Production Economics 156:180-190. doi:10.1016/j.ijpe.2014.06.007", "Crossref record verified (content not read)", "NOT CITED - candidate; read before citing"),
    ("Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D", "UCI dataset page: recommended citation, DOI and licence read", "Dataset citation missing in manuscript (placeholder text) - add"),
    ("M5 Forecasting - Accuracy (Kaggle, University of Nicosia / Makridakis et al.) data citation", "Kaggle competition pages read (data description and rules)", "Dataset citation/terms statement missing - add and confirm permission"),
]
for it, src, st in MISSING:
    rows.append({"item_type": "missing reference / citation", "item": it, "source_checked": src, "automatic_field_check": "", "supports_the_attached_sentence": "n/a", "status": st, "action": "add after reading" if "candidate" in st else "add"})

RIGHTS = [
    ("Dataset: M5 Forecasting - Accuracy", "Kaggle rules page (read 2026-10-22): 'DATA ACCESS AND USE: Competition Use, Academic, Non-Commercial Use'; 'You may access and use the Competition Data for non-commercial purposes only, including ... for academic research and education'; 'You agree not to transmit, duplicate, publish, redistribute or otherwise provide or make available the Competition Data to any party not participating in the Competition.' Data page: files require signing in and accepting the rules. The GitHub Mcompetitions/M5-methods page states no licence.",
     "Academic non-commercial use of the data: permitted. Public redistribution of the raw data or derived arrays containing actual sales (predictions.npz holds y for 700 series, validation targets): NOT permitted without permission; unresolved. IJF posts datasets of published papers on its website; PLOS requires public deposit unless third-party restrictions are documented.",
     "Do not upload data or arrays with actual sales; publish code, metrics and aggregate results; document the access route (Kaggle account + rules) in the data statement; ask the rights holder (University of Nicosia / Kaggle) in writing whether derived series may be shared."),
    ("Dataset: UCI Online Retail II", "UCI repository page (read 2026-10-22): licensed CC BY 4.0; donor Daqing Chen; DOI 10.24432/C5CG6D; recommended citation 'Chen, D. (2012)...'",
     "Redistribution of the data and derived arrays permitted with attribution. The study uses a CSV conversion of the xlsx made earlier in the project; attribution and a description of the cleaning rules are required.", "Add the dataset citation and licence statement; include the cleaning rules; processed data and predictions for this dataset may be archived."),
    ("Study code (research/forecast_study_v1) and results JSON", "Own work in the repository; no third-party code copied into it (imports ml.benchmark from this repository)", "Sharing rights depend on the repository's licence and the authors' decision; the repository licence was not audited here.", "Authors choose a licence; confirm third-party package licences (LightGBM, XGBoost, CatBoost, scikit-learn) are compatible; do not publish until approved."),
    ("Stored predictions (predictions.npz)", "Contain per-series actuals y plus forecasts", "M5-derived arrays: rights unresolved (see above). Online Retail II-derived arrays: CC BY allows.", "Publish only OR II arrays, or arrays with M5 actuals removed (forecasts alone do not reproduce the metrics - provide a script that fetches actuals from the user's own licensed copy)."),
    ("Ethics / privacy", "Public secondary data. Online Retail II includes pseudonymous customer IDs (5,852 customers); the classification study uses them", "Customer IDs are pseudonymous; no names or personal attributes in the processed file; whether an institutional ethics/data-protection review is needed is not established by this audit and depends on the venue and institution.", "Authors/institution decide; do not publish customer-level score files with IDs unless the licence and institutional review allow; state this in the ethics statement."),
]
for it, src, status, act in RIGHTS:
    rows.append({"item_type": "data/code rights", "item": it, "source_checked": src, "automatic_field_check": "", "supports_the_attached_sentence": "n/a", "status": status, "action": act})

with open(AUD / "REFERENCE_AND_DATA_RIGHTS_AUDIT.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(len(rows), "rows")
