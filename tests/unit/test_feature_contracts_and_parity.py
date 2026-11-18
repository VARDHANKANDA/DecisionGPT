"""Training/inference feature parity and the feature contract. Small synthetic histories; no registry, no database."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from app.analytics import forecast_service as fs
from ml.features.churn_features import FEATURE_COLUMNS as CHURN_COLS, build_churn_features
from ml.features.contracts import CHURN_V1, FORECASTING_V1, FeatureContractError, contract_for
from ml.features.forecasting_features import FEATURE_COLUMNS as FC_COLS, build_forecasting_features


def _history(n=90, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n)
    return pd.DataFrame({"series_id": "s", "date": dates, "units_sold": rng.integers(5, 30, n).astype(float), "price": 100.0 + rng.integers(0, 5, n),
                         "marketing_spend": rng.integers(0, 3, n).astype(float), "promotion_flag": 0})


# ------------------------------------------------------------------ parity
@pytest.mark.parametrize("n,seed", [(60, 1), (90, 2), (200, 3)])
def test_the_inference_feature_row_equals_the_training_builder_for_the_same_day(n, seed):
    """For the day after the history, ``build_feature_row`` (serving) must equal the row the TRAINING builder produces for that day."""
    h = _history(n, seed)
    next_day = h["date"].iloc[-1] + timedelta(days=1)
    price, mk = 103.0, 1.0
    train_frame = pd.concat([h, pd.DataFrame([{"series_id": "s", "date": next_day, "units_sold": 0.0, "price": price, "marketing_spend": mk,
                                               "promotion_flag": 0}])], ignore_index=True)
    train_row = build_forecasting_features(train_frame).iloc[-1]
    assert pd.Timestamp(train_row["date"]) == next_day
    serve_row = fs.build_feature_row(list(h["units_sold"]), next_day, price, mk).iloc[0]
    for c in FC_COLS:
        assert float(serve_row[c]) == pytest.approx(float(train_row[c])), c


def test_serving_and_training_use_the_same_column_list_and_contract():
    assert list(fs.build_feature_row([1.0] * 40, pd.Timestamp("2025-02-01"), 1.0, 0.0).columns) == list(FC_COLS) == list(FORECASTING_V1.columns)
    assert contract_for("forecasting_v1") is FORECASTING_V1 and contract_for("churn_v1") is CHURN_V1 and contract_for("nope") is None


def test_churn_features_are_built_by_one_function_for_training_and_serving():
    df = pd.DataFrame({"tenure_days": [400, 100], "recency_days": [20, 90], "frequency": [8, 2], "avg_order_value": [500.0, 200.0],
                       "monetary_value": [4000.0, 400.0]})
    out = build_churn_features(df)
    assert list(out[CHURN_COLS].columns) == list(CHURN_V1.columns)
    assert out.loc[0, "recency_ratio"] == pytest.approx(20 / 400)
    assert out.loc[0, "purchase_rate_per_year"] == pytest.approx(8 / (400 / 365))


# ------------------------------------------------------------------ the contract
def _good():
    return pd.DataFrame([{c: 1.0 for c in FC_COLS}])


def test_a_conforming_frame_passes_and_is_returned_in_contract_order():
    f = _good()
    assert list(FORECASTING_V1.validate(f[list(reversed(FC_COLS))].pipe(lambda d: d[list(FC_COLS)])).columns) == list(FC_COLS)


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d.drop(columns=["price"]), "missing columns"),
    (lambda d: d.assign(extra=1.0), "unexpected columns"),
    (lambda d: d[list(reversed(list(d.columns)))], "order"),
    (lambda d: d.assign(price=np.nan), "missing value"),
    (lambda d: d.assign(lag_1=np.inf), "infinite"),
    (lambda d: d.assign(month="June"), "not numeric"),
    (lambda d: d.iloc[0:0], "no rows"),
])
def test_a_violating_frame_is_refused_with_every_problem_named(mutate, needle):
    with pytest.raises(FeatureContractError) as e:
        FORECASTING_V1.validate(mutate(_good()))
    assert needle in str(e.value) and e.value.problems


def test_churn_scoring_refuses_a_frame_that_does_not_match_the_contract():
    bad = pd.DataFrame({"tenure_days": [1.0], "recency_days": [np.nan]})
    with pytest.raises(FeatureContractError):
        CHURN_V1.validate(bad)
