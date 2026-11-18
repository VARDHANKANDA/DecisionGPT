"""One definition of every evaluation metric the Research Console can show, and the one function that turns a recorded number into a card.

The API, the UI and the exported text all read these definitions, so a metric name, its unit, its direction ("lower is better") and its caveat
are written once. Nothing here computes a model metric: ``card`` only formats a value that a training run, a benchmark file or a validation
report recorded, and refuses to show anything that is missing, non-finite or not defined (it says why instead).

Status of a card
  available      a finite value from a recorded evaluation
  not_available  the evaluation did not record it (older run, or the inputs were not there); ``reason`` says which
  not_evaluated  the check was never run for this subject
  unreliable     a value exists but its denominators make it misleading (e.g. percentage error with zero actuals); no number is shown
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

AVAILABLE, NOT_AVAILABLE, NOT_EVALUATED, UNRELIABLE = "available", "not_available", "not_evaluated", "unreliable"

LOWER, HIGHER, ZERO, NOMINAL, INFO = "lower_is_better", "higher_is_better", "closer_to_zero_is_better", "closer_to_nominal_is_better", "informational"
_DIRECTION_TEXT = {
    LOWER: "Lower is better",
    HIGHER: "Higher is better",
    ZERO: "Closer to zero is better",
    NOMINAL: "Closer to the promised level is better",
    INFO: "For context; not a quality score",
}

# A legacy percentage error above this is dominated by near-zero actuals, not by forecast quality.
LEGACY_MAPE_IMPLAUSIBLE = 1000.0


@dataclass(frozen=True)
class MetricDef:
    key: str
    name: str
    abbr: str
    task: str                    # regression | classification | calibration | data
    unit: str                    # target_units | percent | ratio | multiple | score | count | none
    direction: str
    definition: str              # plain-language explanation shown on the card
    caveat: str = ""
    sign_note: str = ""          # for signed metrics: what + and - mean
    decimals: int = 2


def _d(*args, **kw) -> MetricDef:
    return MetricDef(*args, **kw)


REGISTRY: dict[str, MetricDef] = {m.key: m for m in [
    # ---- regression / forecasting
    _d("mae", "Mean absolute error", "MAE", "regression", "target_units", LOWER,
       "The average size of the miss, ignoring direction: on a typical day the forecast is off by about this much.",
       "Depends on the scale of what is forecast, so it cannot be compared across different targets."),
    _d("rmse", "Root mean squared error", "RMSE", "regression", "target_units", LOWER,
       "Like MAE but large misses count more, so it rises when a few forecasts are far off.",
       "Always at least as large as MAE; the gap between the two shows how uneven the errors are."),
    _d("wape", "Weighted absolute percentage error", "WAPE", "regression", "percent", LOWER,
       "Total absolute error divided by total actual volume: the share of volume that was mis-forecast.",
       "Dominated by the high-volume days when demand is intermittent. Not defined when the actual total is zero."),
    _d("forecast_accuracy", "Forecast Accuracy (1 − WAPE)", "Forecast Accuracy (1 − WAPE)", "regression", "percent", HIGHER,
       "Established continuous forecasting metric: 100 × (1 − WAPE). Reflects the share of total volume accurately predicted.",
       "Calculated consistently as 100 × (1 − WAPE) across all comparable forecasting models. Not classification accuracy."),
    _d("baseline_forecast_accuracy", "Baseline Forecast Accuracy (1 − WAPE)", "Baseline Acc (1 − WAPE)", "regression", "percent", HIGHER,
       "100 × (1 − baseline WAPE): the accuracy of the naive lag-1 reference forecast scored on exactly the same rows.",
       "Provides the direct baseline against which trained forecasting models are compared."),
    _d("bias", "Bias (mean error)", "Bias", "regression", "target_units", ZERO,
       "The average signed error (forecast minus actual). It shows whether the forecast leans high or low.",
       "Over- and under-forecasts cancel, so a bias near zero does not mean the forecasts are accurate.",
       sign_note="Positive = over-forecast (forecast above actual). Negative = under-forecast."),
    _d("relative_bias", "Relative bias", "Rel. bias", "regression", "percent", ZERO,
       "Signed error as a share of total actual volume.", "Not defined when the actual total is zero.",
       sign_note="Positive = over-forecast. Negative = under-forecast."),
    _d("mape", "Mean absolute percentage error", "MAPE", "regression", "percent", LOWER,
       "The average miss as a percentage of the actual value on each day.",
       "Unreliable whenever some actual values are zero or very small: one near-zero day can dominate the whole figure. Prefer WAPE."),
    _d("coverage", "Prediction-interval coverage", "Coverage", "regression", "percent", NOMINAL,
       "The share of held-out actual values that fell inside the forecast's uncertainty band.",
       "Compare with the level the band promises (for example 80%). Held-out points overlap in time, so this is an approximate check."),
    _d("baseline_mae", "Baseline MAE (yesterday's value)", "Baseline MAE", "regression", "target_units", LOWER,
       "The MAE of the simplest forecast: repeat the previous day's value, measured on the same rows and period as the model.",
       "A model is only useful if it beats this."),
    _d("mae_vs_baseline", "Change in MAE vs baseline", "vs baseline", "regression", "percent", HIGHER,
       "How much lower (positive) or higher (negative) the model's MAE is than the baseline's on the same rows.",
       "Computed from two recorded MAE values; it is not a new measurement."),
    _d("baseline_wape", "Baseline WAPE (yesterday's value)", "Baseline WAPE", "regression", "percent", LOWER,
       "The WAPE of the simplest forecast (repeat the previous day's value), measured on exactly the same rows and period as the model.",
       "Not defined when the actual total is zero."),
    _d("wape_vs_baseline", "Relative WAPE improvement over baseline", "WAPE vs baseline", "regression", "percent", HIGHER,
       "100 × (baseline WAPE − model WAPE) ÷ baseline WAPE: how much lower (positive) or higher (negative) the model's WAPE is than the baseline's on the same rows.",
       "Computed from two WAPE values of the same evaluation; it is not a new measurement. Because the model and the baseline are scored on exactly the same rows (same actual volume), it equals the relative MAE change. Not defined when the baseline WAPE is zero or missing."),
    _d("rmsse", "Root mean squared scaled error", "RMSSE", "regression", "ratio", LOWER,
       "Each series' RMSE divided by the RMSE of the simple one-step 'repeat yesterday' forecast on that series' own training history, then averaged "
       "over series. Below 1 means the forecasts are better than that simple rule would have been; above 1 means worse.",
       "Unit-free, so it suits many series of different sizes. Series whose training history never changed cannot be scaled and are left out (their "
       "number is shown). Only comparable between rows of the same benchmark run."),
    _d("aggregate_daily_wape", "Aggregate-day WAPE", "Agg. WAPE", "regression", "percent", LOWER,
       "WAPE after adding all series together for each day: how far off the forecast total is for the whole range on a typical day.",
       "Errors in different series cancel when added up, so this is far lower than the per-series WAPE and must not be compared with it."),
    _d("median_series_wape", "Median series WAPE", "Median WAPE", "regression", "percent", LOWER,
       "WAPE computed separately for each series, then the middle value across series: how a typical single series does.",
       "Series with no actual volume have no WAPE and are left out (their number is shown). Sparse series can exceed 100%."),
    _d("log_loss", "Log loss", "Log loss", "classification", "score", LOWER,
       "How surprised the model is by what happened, using its scores as probabilities: confident wrong scores are punished hard.",
       "Meaningful only if the scores behave like probabilities; probabilities are clipped to [0.000001, 0.999999]. No constant-forecast reference was "
       "recorded for it, so it cannot be read as better or worse than a baseline."),
    _d("brier_baseline", "Brier score of a constant forecast", "Brier (constant)", "calibration", "score", INFO,
       "The Brier score of always predicting the positive rate of the evaluated rows. A model's Brier score should be below it to add anything.",
       "Uses the evaluated rows' own positive rate, which makes it a demanding reference."),
    _d("brier_vs_baseline", "Brier improvement over the constant forecast", "Brier vs constant", "calibration", "percent", HIGHER,
       "How much lower (positive) or higher (negative) the model's Brier score is than the constant forecast's, on the same rows.",
       "Computed from two recorded Brier scores; it is not a new measurement."),
    _d("top_decile_lift", "Top-decile lift", "Top-10% lift", "classification", "multiple", HIGHER,
       "The share of the 10% highest-scored customers who turned out inactive, divided by the share among all customers. 1.0 is no better than "
       "picking at random.",
       "Ranking check against a proxy label (no purchase in the window), not churn. Based on a small group, so it moves a lot with few customers."),
    _d("top_decile_inactive_rate", "Inactive rate in the top 10%", "Top-10% rate", "classification", "ratio", INFO,
       "The share of the 10% highest-scored customers who bought nothing in the label window.", "Read together with the overall positive rate."),
    _d("n_eval", "Evaluated points", "n", "data", "count", INFO, "How many actual values the metrics were computed on.",
       "Small samples make every metric unstable."),
    _d("n_zero_actual", "Zero-valued actuals", "Zeros", "data", "count", INFO,
       "How many of the evaluated actual values were exactly zero (percentage errors are undefined there)."),
    _d("n_invalid", "Left-out invalid points", "Invalid", "data", "count", INFO,
       "Prediction/actual pairs that were missing or not finite and were left out of the metrics."),
    # ---- classification
    _d("roc_auc", "Area under the ROC curve", "ROC-AUC", "classification", "score", HIGHER,
       "How well the score ranks customers who did the event above those who did not: 0.5 is a coin flip, 1.0 is perfect ranking.",
       "Measures ranking only. It says nothing about whether the score is a true probability."),
    _d("pr_auc", "Area under the precision-recall curve", "PR-AUC", "classification", "score", HIGHER,
       "How precise the top-ranked customers are across all cut-offs. More informative than ROC-AUC when the event is rare.",
       "Its baseline is the event rate (prevalence), not 0.5."),
    _d("precision", "Precision", "Precision", "classification", "ratio", HIGHER,
       "Of the customers flagged as positive, the share that really were.", "Depends on the cut-off used."),
    _d("recall", "Recall", "Recall", "classification", "ratio", HIGHER,
       "Of the customers who really were positive, the share that were flagged.", "Depends on the cut-off used."),
    _d("f1", "F1 score", "F1", "classification", "ratio", HIGHER,
       "A single number combining precision and recall (their harmonic mean).", "Depends on the cut-off; ignores true negatives."),
    _d("accuracy", "Accuracy", "Accuracy", "classification", "ratio", HIGHER,
       "The share of customers classified correctly, computed from the confusion matrix.",
       "Misleading when one class is rare: predicting the majority class for everyone already scores high."),
    _d("brier", "Brier score", "Brier", "calibration", "score", LOWER,
       "The average squared gap between the score and what happened (0 or 1).",
       "Only a true probability error if the score is calibrated; compare with the Brier score of always predicting the event rate."),
    _d("ece", "Expected calibration error", "ECE", "calibration", "ratio", LOWER,
       "How far, on average, the score is from the observed event rate within bands of the score.",
       "Only meaningful when the event rate in the evaluation data matches the training data."),
    _d("prevalence", "Positive rate (prevalence)", "Positive rate", "data", "ratio", INFO,
       "The share of evaluated customers for whom the event happened.", "Needed to read precision, PR-AUC and accuracy."),
    _d("threshold", "Decision threshold", "Threshold", "classification", "score", INFO,
       "The score above which a customer is flagged. Chosen on validation data, never on the test data.", decimals=3),
]}


def _finite(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _format(d: MetricDef, v: float, target_unit: str | None) -> tuple[str, str]:
    """(display text, unit label). Percent metrics are stored as fractions or percentages depending on the source; callers pass percent."""
    if d.unit == "percent":
        return f"{v:+.1f}%" if d.key in ("relative_bias", "mae_vs_baseline", "wape_vs_baseline", "brier_vs_baseline") else f"{v:.1f}%", "%"
    if d.unit == "multiple":
        return f"{v:.2f}×", "×"
    if d.unit == "count":
        return f"{int(round(v)):,}", ""
    if d.unit == "target_units":
        label = target_unit or "units"
        text = f"{v:+,.{d.decimals}f}" if d.key == "bias" else f"{v:,.{d.decimals}f}"
        return f"{text} {label}", label
    return (f"{v:.3f}" if d.unit in ("ratio", "score") else f"{v:.{d.decimals}f}"), ""


# Why a value is not shown (the finer distinction behind ``status``; chat and the console both use it):
#   available | not_evaluated (never run) | not_applicable (does not exist for this subject) | not_recorded (an older run did not store it)
#   | insufficient_data | failed | unreliable (a value exists but would mislead)
KINDS = ("available", "not_evaluated", "not_applicable", "not_recorded", "insufficient_data", "failed", "unreliable")
_KIND_DISPLAY = {"not_evaluated": "Not evaluated", "unreliable": "Not reliable", "not_applicable": "Not applicable", "not_recorded": "Not available",
                 "insufficient_data": "Insufficient data", "failed": "Failed"}
_DEFAULT_KIND = {AVAILABLE: "available", NOT_EVALUATED: "not_evaluated", UNRELIABLE: "unreliable", NOT_AVAILABLE: "not_recorded"}


def card(key: str, value: Any, *, target_unit: str | None = None, reason: str | None = None, status: str | None = None,
         context: dict[str, Any] | None = None, extra_caveat: str | None = None, as_percent_of_fraction: bool = False,
         kind: str | None = None) -> dict[str, Any]:
    """The one presenter. ``value`` is whatever the evaluation recorded. ``as_percent_of_fraction`` converts a stored fraction (0.18) to a percentage."""
    d = REGISTRY[key]
    v = _finite(value)
    base = {
        "key": d.key, "name": d.name, "abbr": d.abbr, "task": d.task, "unit": d.unit if d.unit != "target_units" else (target_unit or "units"),
        "direction": d.direction, "direction_text": _DIRECTION_TEXT[d.direction], "explanation": d.definition,
        "caveat": " ".join(x for x in (d.caveat, extra_caveat) if x), "sign_note": d.sign_note or None, "context": context or {},
    }
    if status in (NOT_EVALUATED, UNRELIABLE) or v is None:
        st = status or NOT_AVAILABLE
        if kind is not None and kind not in KINDS:
            raise ValueError(f"unknown card kind {kind}")
        default = {NOT_EVALUATED: "This check has not been run.", UNRELIABLE: "The value would be misleading.",
                   NOT_AVAILABLE: "This evaluation did not record this value."}[st]
        return {**base, "status": st, "kind": kind or _DEFAULT_KIND[st], "value": None, "display": _KIND_DISPLAY[kind or _DEFAULT_KIND[st]],
                "reason": reason or default}
    if as_percent_of_fraction:
        v = v * 100.0
    display, unit_label = _format(d, v, target_unit)
    return {**base, "status": AVAILABLE, "kind": "available", "value": round(v, 6), "display": display, "reason": None}


def mape_card(value: Any, *, n_zero_actual: int | None, n_eval: int | None, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """MAPE with an explicit validity policy: never shown when a recorded zero actual makes it undefined, and never shown when an older run
    (which did not record zero counts) produced a value so large that near-zero actuals must have decided it."""
    v = _finite(value)
    if v is None:
        return card("mape", None, context=context)
    if n_zero_actual:
        return card("mape", None, status=UNRELIABLE, context=context,
                    reason=f"{n_zero_actual:,} of {n_eval:,} actual values are zero, so a percentage error is undefined for them. Use WAPE instead." if n_eval
                    else f"{n_zero_actual:,} actual values are zero, so a percentage error is undefined for them. Use WAPE instead.")
    if n_zero_actual is None and v > LEGACY_MAPE_IMPLAUSIBLE:
        return card("mape", None, status=UNRELIABLE, context=context,
                    reason="This run did not record how many actual values were zero, and the figure is so large that near-zero actuals almost certainly "
                           "decided it. It says nothing about forecast quality. Use WAPE instead.")
    return card("mape", v, context=context,
                extra_caveat=("This run did not record how many actual values were zero." if n_zero_actual is None else None))


def improvement_vs_baseline(model_mae: Any, baseline_mae: Any) -> float | None:
    """Percent by which the model's MAE is below the baseline's (positive = better than the baseline). None when either is missing or the baseline is 0."""
    m, b = _finite(model_mae), _finite(baseline_mae)
    if m is None or b is None or b <= 0:
        return None
    return (b - m) / b * 100.0


def metric_definitions() -> list[dict[str, Any]]:
    """The full glossary (also served to the UI so it never carries its own copy of a definition)."""
    return [{"key": d.key, "name": d.name, "abbr": d.abbr, "task": d.task, "direction": d.direction, "direction_text": _DIRECTION_TEXT[d.direction],
             "definition": d.definition, "caveat": d.caveat or None, "sign_note": d.sign_note or None} for d in REGISTRY.values()]
