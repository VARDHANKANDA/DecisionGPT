"""Build RELATED_WORK_MATRIX.csv and REFERENCE_AUDIT.csv. The audit compares the fields stated in ENTRIES with a FRESH Crossref lookup for every DOI (title words, first author, year, volume, pages)."""
import csv
import json
import re
import time
import unicodedata
import urllib.request

from research.forecast_study_v2.common import STUDY

# id, authors (first author family), year, title, venue, volume, pages, doi, verification, question, method, findings, limits, relation
E = [
 ("L01", "Gneiting", 2011, "Making and evaluating point forecasts", "Journal of the American Statistical Association", "106", "746-762", "10.1198/jasa.2011.r10138", "M+A (abstract on arXiv/alphaXiv)",
  "How should point forecasts be evaluated?", "Theory of scoring functions and elicitability", "Averaging a scoring function can mislead unless it matches the forecasting task; squared error is consistent for the mean, generalised piecewise-linear scores (e.g. absolute error) for quantiles", "Abstract read only; theory not retraced", "Explains why a mean-targeting model is not expected to win an absolute-error metric"),
 ("L02", "Kolassa", 2020, "Why the best point forecast depends on the error or accuracy measure", "International Journal of Forecasting", "36", "208-211", "10.1016/j.ijforecast.2019.02.017", "M+P (article page read)",
  "Which point forecast is best for which error measure?", "Commentary with a simulated gamma example", "Expected value minimises squared error; other point-forecast error measures minimise other functionals", "Short commentary", "Same mechanism; cited for the practical statement"),
 ("L03", "Kolassa", 2016, "Evaluating predictive count data distributions in retail sales forecasting", "International Journal of Forecasting", "32", "788-803", "10.1016/j.ijforecast.2015.12.004", "M+A (IDEAS abstract)",
  "How to evaluate forecasts of low retail counts?", "Randomised PIT and proper scoring rules on two daily retail datasets", "Point-accuracy measures such as MAD, MASE and wMAPE are poorly suited to count data; distributions should be evaluated with proper scoring rules", "Abstract only", "Motivates reporting an aggregation ladder and not relying on one WAPE"),
 ("L04", "Prestwich", 2014, "Mean-based error measures for intermittent demand forecasting", "International Journal of Production Research", "52", "6782-6791", "10.1080/00207543.2014.917771", "M+A (arXiv abstract)",
  "Do standard error measures rank intermittent-demand forecasters correctly?", "Analysis and new mean-based measures scored against the process mean", "Almost all known measures rank forecasters incorrectly on intermittent series", "Abstract only", "Supports the expectation that item-day WAPE can mis-rank on sparse demand"),
 ("L05", "Kourentzes", 2014, "On intermittent demand model optimisation and selection", "International Journal of Production Economics", "156", "180-190", "10.1016/j.ijpe.2014.06.007", "M+A (IDEAS abstract)",
  "How should intermittent-demand models be optimised?", "Comparison of conventional and two proposed cost functions, out-of-sample and inventory simulations", "The proposed metrics performed best and gave parameters consistent with the literature, unlike conventional metrics; separate smoothing parameters help", "Abstract only", "Related: loss choice changes fitted intermittent models"),
 ("L06", "Hyndman", 2006, "Another look at measures of forecast accuracy", "International Journal of Forecasting", "22", "679-688", "10.1016/j.ijforecast.2006.03.001", "M+A",
  "Which accuracy measures are adequate?", "Discussion and comparison of measures", "Many popular measures are degenerate in common situations; MASE proposed", "Does not treat WAPE explicitly in the abstract", "Basis for refusing MAPE and for scaled-error discussion"),
 ("L07", "Croston", 1972, "Forecasting and stock control for intermittent demands", "Journal of the Operational Research Society", "23", "289-303", "10.1057/jors.1972.50", "M",
  "How to forecast intermittent demand?", "Separate smoothing of size and interval", "(abstract not read)", "Bibliographic verification only", "Baseline estimator"),
 ("L08", "Syntetos", 2005, "The accuracy of intermittent demand estimates", "International Journal of Forecasting", "21", "303-314", "10.1016/j.ijforecast.2004.10.001", "M",
  "Bias of Croston's estimator", "Analysis; SBA correction", "(abstract not read)", "Bibliographic verification only", "Baseline estimator (SBA)"),
 ("L09", "Teunter", 2011, "Intermittent demand: Linking forecasting to inventory obsolescence", "European Journal of Operational Research", "214", "606-615", "10.1016/j.ejor.2011.05.018", "M",
  "Obsolescence-aware intermittent forecasting", "TSB method", "(abstract not read)", "Bibliographic verification only", "Baseline estimator (TSB)"),
 ("L10", "Nikolopoulos", 2011, "An aggregate-disaggregate intermittent demand approach (ADIDA) to forecasting: an empirical proposition and analysis", "Journal of the Operational Research Society", "62", "544-554", "10.1057/jors.2010.32", "M+A (partial, IDEAS)",
  "Does temporal aggregation help intermittent-demand forecasting?", "Aggregate to lower frequency, forecast, disaggregate", "Aggregating into lower-frequency buckets reduces zeros; secondary sources report an optimal aggregation level per series", "Abstract only partly read; ADIDA is not implemented in this study", "Related to the aggregation theme; an omitted baseline family"),
 ("L11", "Athanasopoulos", 2017, "Forecasting with temporal hierarchies", "European Journal of Operational Research", "262", "60-74", "10.1016/j.ejor.2017.02.046", "M+A",
  "Can forecasts at several temporal aggregation levels be combined?", "Temporal hierarchies with reconciliation", "Combining forecasts across temporal aggregation levels gives aligned, accurate forecasts", "Not about learned-vs-simple comparison", "Aggregation level matters; reconciliation not used here"),
 ("L12", "Hyndman", 2011, "Optimal combination forecasts for hierarchical time series", "Computational Statistics & Data Analysis", "55", "2579-2589", "10.1016/j.csda.2011.03.006", "M+A",
  "How to forecast hierarchical series?", "Regression-based reconciliation", "Optimal combination beats bottom-up or top-down", "Cross-sectional hierarchies", "Context for aggregated metrics"),
 ("L13", "Spiliotis", 2021, "Hierarchical forecast reconciliation with machine learning", "Applied Soft Computing", "112", "107756", "10.1016/j.asoc.2021.107756", "M+A",
  "Can ML improve hierarchical reconciliation?", "ML-based reconciliation", "Proposes an ML hierarchical approach (abstract)", "Different problem", "Context"),
 ("L14", "Makridakis", 2022, "M5 accuracy competition: Results, findings, and conclusions", "International Journal of Forecasting", "38", "1346-1364", "10.1016/j.ijforecast.2021.11.013", "M+A+P (passage on LightGBM; abstract)",
  "Results of the M5 accuracy track", "Competition report", "Forecasts at the lowest level were summed to upper levels; LightGBM was used by all top-50 teams", "Full text not read", "Dataset and context; the study is not the M5 setting"),
 ("L15", "Januschowski", 2022, "Forecasting with trees", "International Journal of Forecasting", "38", "1473-1481", "10.1016/j.ijforecast.2021.10.004", "M+A (abstract via search records)",
  "Why were tree-based methods so successful in M5?", "Discussion", "Tree-based methods outperformed other approaches in M5, in particular deep learning", "Abstract-level only", "Context for the choice of boosted trees"),
 ("L16", "Bojer", 2021, "Kaggle forecasting competitions: An overlooked learning opportunity", "International Journal of Forecasting", "37", "587-603", "10.1016/j.ijforecast.2020.07.007", "M+A (full abstract)",
  "What do six Kaggle forecasting competitions teach?", "Review of six competitions", "Kaggle data are intermittent and higher-entropy; ensemble cross-learning models tend to beat local ones; GBDT and NN are strong", "Review", "Context for ML strength on intermittent data"),
 ("L17", "Spiliotis", 2022, "Comparison of statistical and machine learning methods for daily SKU demand forecasting", "Operational Research", "22", "3037-3061", "10.1007/s12351-020-00605-2", "M+A (IDEAS abstract)",
  "ML vs statistical methods on daily SKU demand", "Large real dataset; local and cross-learning ML vs Croston etc.", "Some ML methods forecast better in error and bias; cross-learning helps some", "Abstract only", "Closest precedent for the model-vs-baseline question"),
 ("L18", "Makridakis", 2018, "Statistical and Machine Learning forecasting methods: Concerns and ways forward", "PLOS ONE", "13", "e0194889", "10.1371/journal.pone.0194889", "M+A",
  "Do ML methods beat statistical ones?", "1,045 monthly M3 series, eight statistical vs popular ML methods", "ML methods were dominated across accuracy measures and horizons", "Monthly M3 data; older ML methods", "Shows ML does not always win"),
 ("L19", "Makridakis", 2020, "The M4 Competition: 100,000 time series and 61 forecasting methods", "International Journal of Forecasting", "36", "54-74", "10.1016/j.ijforecast.2019.04.014", "M+A",
  "Results of M4", "Competition report", "Large-scale comparison of methods", "Not retail-intermittent", "Context"),
 ("L20", "Fildes", 2022, "Retail forecasting: Research and practice", "International Journal of Forecasting", "38", "1283-1318", "10.1016/j.ijforecast.2019.06.004", "M",
  "Retail forecasting review", "Review", "(not read)", "Metadata only", "Context"),
 ("L21", "Hewamalage", 2023, "Forecast evaluation for data scientists: common pitfalls and best practices", "Data Mining and Knowledge Discovery", "37", "788-832", "10.1007/s10618-022-00894-5", "M+A",
  "Pitfalls in forecast evaluation", "Methodological review", "Pitfalls in data partitioning, error calculation and statistical testing", "Review", "Methodological precedent for the protocol"),
 ("L22", "Koenker", 1978, "Regression quantiles", "Econometrica", "46", "33-50", "10.2307/1913643", "M",
  "Quantile regression", "Estimator", "(abstract not read)", "Metadata only", "Basis for absolute-error/median objectives"),
 ("L23", "Friedman", 2001, "Greedy function approximation: A gradient boosting machine", "The Annals of Statistics", "29", "1189-1232", "10.1214/aos/1013203451", "M",
  "Gradient boosting", "Method", "(abstract not read)", "Metadata only", "Model class"),
 ("L24", "Cameron", 2011, "Robust inference with multiway clustering", "Journal of Business & Economic Statistics", "29", "238-249", "10.1198/jbes.2010.07136", "M+A (working-paper abstract)",
  "Inference with two-way clustered data", "Two-way cluster-robust variance", "Extends the cluster-robust sandwich estimator to non-nested multi-way clustering; validated by Monte Carlo and applications", "Asymptotics in the number of clusters", "Secondary interval method (delta method)"),
 ("L25", "Owen", 2007, "The pigeonhole bootstrap", "The Annals of Applied Statistics", "1", "386-411", "10.1214/07-AOAS122", "M+A",
  "Bootstrap for crossed random-effects data", "Resample rows and columns separately", "Satisfies a mean-consistency property for heteroscedastic crossed unbalanced data; later work calls it mildly conservative (secondary)", "Designed for sparse unbalanced arrays", "Primary interval method; coverage checked by simulation"),
 ("L26", "Owen", 2012, "Bootstrapping data arrays of arbitrary order", "The Annals of Applied Statistics", "6", "895-927", "10.1214/12-AOAS547", "M",
  "Bootstrap for multi-way arrays", "Pigeonhole bootstrap extension", "(abstract not read)", "Metadata only", "Related"),
 ("L27", "Ke", 2017, "LightGBM: A highly efficient gradient boosting decision tree", "Advances in Neural Information Processing Systems", "30", "", "", "venue page (NeurIPS proceedings)",
  "Efficient GBDT", "System paper", "(page read: title/authors/venue)", "No DOI", "Model implementation"),
 ("L28", "Chen", 2016, "XGBoost: A scalable tree boosting system", "Proc. 22nd ACM SIGKDD", "", "785-794", "10.1145/2939672.2939785", "M",
  "Scalable boosting", "System paper", "(not read)", "Metadata only", "Model implementation"),
 ("L29", "Damato", 2026, "Intermittent time series forecasting: local vs global models", "arXiv preprint", "", "", "arXiv:2601.14031", "arXiv API (title, authors, year); preprint",
  "Local vs global models on intermittent series", "Five datasets, probabilistic models", "(abstract summarised in the earlier literature pass)", "Not peer reviewed when read", "Most similar recent work"),
 ("L30", "Diebold", 1995, "Comparing predictive accuracy", "Journal of Business & Economic Statistics", "13", "253-263", "10.1080/07350015.1995.10524599", "M",
  "Test of equal predictive accuracy", "DM test", "(not read)", "Metadata only", "Exploratory aggregate-level test (not used in v2)"),
 ("L31", "Politis", 1994, "The stationary bootstrap", "Journal of the American Statistical Association", "89", "1303-1313", "10.1080/01621459.1994.10476870", "M",
  "Bootstrap for stationary series", "Random block lengths", "(not read)", "Metadata only", "Secondary week-block bootstrap"),
 ("L32", "Chen", 2012, "Online Retail II [Dataset]. UCI Machine Learning Repository", "UCI Machine Learning Repository", "", "", "10.24432/C5CG6D", "UCI page (licence CC BY 4.0, donor, citation)",
  "Dataset", "", "", "", "Data source"),
]


def norm(s):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()).split())


def lookup(doi):
    req = urllib.request.Request("https://api.crossref.org/works/" + doi, headers={"User-Agent": "research/1.0 (mailto:solasa.dev@gmail.com)"})
    for k in range(4):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))["message"]
        except Exception as e:
            time.sleep(2 + 3 * k)
            err = e
    return {"error": str(err)}


rows_m, rows_a = [], []
for (i, au, yr, title, venue, vol, pages, doi, ver, q, meth, find, lim, rel) in E:
    rows_m.append({"id": i, "citation": f"{au} ({yr}). {title}. {venue}", "doi_or_id": doi, "verification_level": ver, "question": q, "method": meth, "findings_as_stated_by_source": find, "limitations": lim, "relation_to_this_study": rel})
    a = {"id": i, "stated_first_author": au, "stated_year": yr, "stated_title": title, "stated_volume": vol, "stated_pages": pages, "doi_or_id": doi, "verification_level": ver}
    if doi.startswith("10."):
        j = lookup(doi)
        if "error" in j:
            a.update({"crossref": "lookup failed: " + j["error"][:60], "status": "UNVERIFIED (lookup failed)"})
        else:
            rt = (j.get("title") or [""])[0]
            ra = (j.get("author") or [{}])[0].get("family", "")
            ry = (j.get("issued", {}).get("date-parts") or [[None]])[0][0]
            rp = (j.get("page") or "").replace("–", "-")
            chk = {"title_words": all(w in norm(rt) for w in norm(title).split()[:5]), "first_author": norm(au) in norm(ra) or norm(ra) in norm(au), "year": str(ry) == str(yr) or abs((ry or 0) - yr) <= 1,
                   "volume": (str(j.get("volume")) == vol) if vol else None, "pages": (rp == pages) if (pages and rp) else None}
            a.update({"crossref_title": rt, "crossref_first_author": ra, "crossref_year(issued)": ry, "crossref_volume": j.get("volume"), "crossref_pages": rp, "field_checks": json.dumps(chk),
                      "status": "VERIFIED (metadata)" if all(v in (True, None) for v in chk.values()) else "CHECK FIELDS"})
        time.sleep(0.5)
    else:
        a.update({"crossref": "no DOI", "status": "VERIFIED at venue/arXiv page (no DOI)" if "page" in ver or "arXiv" in ver else "UNVERIFIED"})
    rows_a.append(a)
    print(i, a["status"], flush=True)


def w(path, rows):
    keys = list({k: 1 for r in rows for k in r})
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows)


w(STUDY / "RELATED_WORK_MATRIX.csv", rows_m)
w(STUDY / "REFERENCE_AUDIT.csv", rows_a)
