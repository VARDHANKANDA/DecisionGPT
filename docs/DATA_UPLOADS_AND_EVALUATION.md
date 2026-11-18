# Data uploads and evaluation metrics

Two things changed together and are documented together: how a business uploads a file and how the Research Console presents evaluation metrics.
Neither changes a model, a frozen benchmark or a security control.

## 1. Uploading a business file

**Supported:** `.csv` (comma, semicolon, tab or pipe separated; UTF-8, UTF-8 with BOM, UTF-16, Windows-1252/Latin-1) and `.xlsx`. Old `.xls` is **not**
supported (there is no safe reader for it); the person is told to re-save as `.xlsx` or CSV.

**Limits** (all return a plain message, never a 500): 25 MB per file and 200,000 rows (`MAX_UPLOAD_BYTES`, `MAX_UPLOAD_ROWS`), 200 columns, 20 sheets,
5,000 characters per cell, 2,000 members / 250 MB expanded inside an `.xlsx` archive (zip-bomb guard). Empty, header-only, malformed and unsupported
files are refused with what to do next. If more than half of the rows cannot be imported (`MAX_SKIPPED_ROW_SHARE`), the whole file is refused and
nothing is saved: that pattern means a column was matched to the wrong field.

### What the cleaning does, and what it asks

| Step | Behaviour | Needs the person? |
| --- | --- | --- |
| Trim leading/trailing whitespace of every value; collapse repeated spaces **in headers only** | Spacing *inside* a value is never changed (two names that differ by a double space stay two values) | No |
| Remove fully blank rows and columns | Reported with counts | No |
| Blank / duplicate headers | Kept; the second `Name` becomes `Name (2)`; reported | No |
| Null spellings (`NA`, `n/a`, `null`, `-`, `#N/A` …) | Read as missing; **never imputed** | No |
| Numbers (`1,23,456.50`, `₹1,200` / `Rs. 1,200`, `(500)`, comma-decimal columns) | Converted only when unambiguous; a column mixing comma-decimal and dot-decimal is not guessed at; percentages and other text are not converted. Such rows are left out and listed | No |
| Dates | Converted when the order is certain (ISO, or a day above 12 shows it); otherwise **the person is asked** day-first or month-first | **Yes** |
| Column mapping | Automatic when required fields are matched; otherwise the person picks the column | **Yes** |
| Duplicate records | **Reported, never removed**: repeated rows can be genuine repeat sales | No (warning shown) |
| Extra columns | Kept in the stored original; shown as "not used", never as "deleted" | No |
| Quantities | Must be whole numbers; fractional quantities are left out and listed | No |
| Outliers | Never removed | — |

Every upload ends in a report: rows found, rows added, rows left out **with the reason and the first examples**, each tidy-up action, which column became
which field, columns not used, sheets not imported and why. It is stored with the upload (`summary_json`) and shown on the upload page and in the
data-quality list. Re-uploading the identical file (SHA-256) is refused with an explicit "Import it again anyway" choice.

### Integrity and safety

* The original file is kept unchanged (`BUSINESS_UPLOAD_PATH`, git-ignored, named by validated ids only, never by the uploaded name). The cleaned rows are
  separate. A mapping that is waiting for confirmation resumes from the stored original, not from a re-upload.
* All tables of one upload are saved in one transaction, or none. A failed import leaves the job marked `failed`, deletes the stored original and changes no
  business data. A double click cannot import twice (the pending job is claimed atomically).
* Column suggestions prefer the field's own name and earlier aliases (a `Product ID` column wins over `Product Name`); a column is mapped to at most one field.
* Cells are read as values only: formulas are never evaluated (`.xlsx` is opened with cached values), uploaded text is never executed, file names are
  reduced to a safe display name, and file content is never written to logs.
* Exports neutralise spreadsheet formula injection: a text cell that starts with `=`, `+`, `-`, `@`, tab or carriage return is prefixed with `'` (plain
  negative numbers are left alone).
* Every route is still scoped by `business_id` and the owning user; the unchanged authentication, tenant checks and rate limits apply.

Migration `0016` adds three nullable columns to `data_ingestion_jobs` (`file_sha256`, `file_size`, `storage_key`) and is reversible. In containers the
originals live on the `business-uploads` volume; see `docs/DEPLOYMENT.md` section 6 for backup.

## 2. Evaluation metrics in the Research Console

**Where:** Research Console → **Evaluation metrics** (`/research/evaluation`), admin only. Eight sections: Overview, Forecasting & Regression,
Classification, Model vs Baseline, Performance by Horizon, Dataset & Setup, Validation & Limitations, History.

**One definition per metric.** `backend/app/services/metric_registry.py` holds the name, abbreviation, unit, direction ("lower is better"), plain-language
meaning, caveat and sign convention of every metric. The API returns finished cards and the page renders them; the page contains no metric text of its own.
Nothing is computed in the browser.

**Four kinds of evidence, never merged**

| Kind | Source | Reads as |
| --- | --- | --- |
| Registered models | `models.metrics_json` from training runs | held-out part of the research dataset the model was trained on |
| Public benchmarks | stored files under `experiments/ml_benchmark_v1` (read-only, smoke and superseded runs hidden) | as stored |
| One business | a stored `forecast_eval` / `customer_eval` report of a business the signed-in admin owns | backtest on that business's own history |
| Live use | not aggregated into the console | **Not evaluated**, with the reason |

### Metric inventory

| Metric | Applies to | Direction | Note |
| --- | --- | --- | --- |
| MAE, RMSE | forecasting / regression | lower | in the units of the target (units/day) |
| WAPE | forecasting | lower | shown as a percent; **not defined** (and withheld) when the actual total is 0 |
| Bias (signed) | forecasting | closer to 0 | **forecast − actual**: positive = over-forecast, negative = under-forecast |
| Relative bias | business forecasts | closer to 0 | same sign convention, as a share of actual volume |
| MAPE | forecasting | lower | shown **only when valid** (see below) |
| Interval coverage | business forecasts | closer to the promised level | needs intervals **and** held-out actuals; registered models have neither → "Not evaluated" |
| Baseline MAE, change vs baseline | forecasting | higher is better | same rows and period; baseline = yesterday's value (models) or the best baseline of the same benchmark run |
| By horizon (7/14/28 d) | business forecasts | — | one-step registered models have no horizons → "Not evaluated" |
| ROC-AUC, PR-AUC | classification | higher | rank quality only |
| Precision, recall, F1, accuracy | classification | higher | computed from the confusion matrix at **one** validation-chosen threshold, so they agree with it; an older run without a matrix shows the stored default-cut-off values labelled as such and **no accuracy** |
| Confusion matrix, positive class, class balance | classification | — | positive class stated (`churned = 1`); train vs test rate and the shift |
| Brier, ECE | classification | lower | diagnostics; ECE is flagged not comparable when the positive rate shifts by ≥ 5 points |
| Evaluated points, zero actuals, invalid points | all | — | sample size and data-quality counts shown next to the metrics |

**MAPE policy.** A percentage error is withheld ("Not reliable", with the reason) when the run recorded zero actual values, or — for older runs that did not
record zero counts — when the stored value exceeds 1,000 % (it was decided by near-zero actuals, not by forecast quality). Otherwise it is shown with its
caveat. The same guard is applied to the research model pages and the business forecast explanation. WAPE is the recommended percentage metric.

**Never fabricated.** A missing, non-finite or undefined value becomes a card with a status and a reason (`Not available`, `Not evaluated`, `Not reliable`)
and `value: null`; the API never emits `NaN` or `Infinity`. Customer scores are ranking scores and are never presented as calibrated probabilities. No
metric is imputed and no metric is invented for a model type that cannot produce it.

New training runs additionally record `bias`, `n_eval`, `n_zero_actual` and `n_invalid` next to the existing metrics (additive; existing values are
unchanged). Older rows keep working and say which values they did not record; retraining records them.

### Forecast accuracy summary and re-evaluation (Model Performance page)

**Where:** Research Console -> **Model performance** (`/research/model-performance`) -> *Forecast accuracy on held-out test data*. One row per registered forecasting
model: status (evaluated / pending / unavailable / failed), WAPE, MAE, RMSE, relative WAPE change vs the baseline, the baseline's name, the number of test pairs, the
test period, the horizon, and the dataset. Every figure is a **held-out test** figure; validation and training figures are never shown there. No "best model" is
named across models scored on different datasets (their errors are in different volumes).

| Figure | Definition |
| --- | --- |
| WAPE (%) | 100 x sum of absolute errors / sum of actual volume over the test block (withheld, not 0, when the actual volume is 0) |
| MAE, RMSE | mean absolute error and root mean squared error, in units/day |
| Change vs baseline (%) | 100 x (baseline WAPE - model WAPE) / baseline WAPE on exactly the same rows (equals the relative MAE change on those rows) |
| Baseline | yesterday's value (1-day lag), scored on the same rows |

**Why WAPE was missing.** Models registered before 2026-10 recorded only MAE, RMSE and MAPE (no WAPE, evaluated-row count, bias or baseline errors), so the console
had nothing to show. The summary therefore says *Pending* for them instead of a number, and the page offers **Run evaluation**.

**Run evaluation** (`POST /research/evaluation/models/{id}/run`, and `.../run-pending`; admin/research access only) re-scores the *stored model artifact* on the held-out
test block of its own dataset, rebuilt with the same cleaning, features and chronological 70/15/15 split as training. It trains nothing, calls no external service,
and changes neither the model nor its recorded training metrics; the outcome is stored in `models.lifecycle_json['reevaluation']`. It is accepted only if the
recomputed MAE, RMSE and MAPE reproduce the values recorded at training (relative tolerance 1e-6):

* `evaluated` - reproduced; WAPE, bias, evaluated-row count, test period and the baseline's errors are shown, labelled "re-scored from the stored model";
* `failed` - not reproduced (the artifact or the rebuilt dataset is not the one that was evaluated): no figure from the re-scoring is shown;
* `unavailable` - the artifact or dataset is missing (the reason is shown).

A failed or unavailable attempt is shown as such and is not retried behind the scenes. Opening the page never starts an evaluation.

### What the console does not show

Live forecast accuracy against real outcomes (tracked per business under Outcome tracking), calibrated churn probabilities, and any per-horizon figure for
registered one-step models. Training and benchmark figures describe research and public datasets, not Indian SMEs, and are not evidence of business impact.

## 3. Evaluation results in chat

Ask in the chat page (or `POST /businesses/{id}/chat`). Evaluation questions are recognised by **rules**, before the AI question-understanding step, and answered
from the same evaluation service and metric registry as the Research Console (`backend/app/services/evaluation_chat_service.py`). No language model sees the
question's numbers or writes any of them; the response says so (`path: "evaluation_service"`, "Recorded evaluation results").

**Supported requests:** all results ("Show me all evaluation results"), what metrics exist ("What metrics are used to evaluate the models?"), a specific metric
("What is the WAPE?"), accuracy ("How accurate is this model?"), baseline comparison, forecasting or classification results only, customer-score reliability,
per-horizon results ("Show the 14-day horizon results"), unavailable metrics and why, historical benchmark results, validation results for the business,
validation history and a run by id, and "Run a forecast validation for my business" (stores a read-only report, changes no model).

**Who sees what.** The business's own validation is shown to its signed-in owner only (`business_id` is authorised by the route guard and is the only
business any query can touch; another business's run id is "not found"). Registered-model and benchmark results are research-dataset results and are shown
only to callers who could open the Research Console (an active admin session, or the research token while the console is enabled; `research_access_granted`
mirrors `require_research_access` and a test keeps them identical). Everyone else is told those results are in the Research Console.

**Never merged.** Your business's backtest, registered models, public benchmarks and live outcomes are separate sections. A public benchmark is never shown
as your performance, a backtest is never called live accuracy, and customer scores are never called probabilities.

**All of it, in pages.** "All results" returns every recorded result and metric value, grouped by evidence and kind. Large sets are split into pages of about
45 metric values without splitting a result across pages; every page states the grand totals, and the response carries a prompt for each page. Nothing is
dropped.

**Missing values.** A value that is not shown has one of seven states, with a reason: evaluated and available, not evaluated, not applicable, not recorded for
this run (an older run did not store it; nothing is backfilled), insufficient data, failed evaluation, withheld as not reliable. The frontend renders the
structured `details.evaluation`; a plain-text version of the same answer is always included.

"How accurate is this model?" explains that there is no single accuracy percentage and shows the metrics that do answer it for the task (forecast error
against a baseline; ranking quality and, at a stated threshold, precision, recall and accuracy for customer scores). Live accuracy against what actually
happened is not part of these results and is said not to be.
