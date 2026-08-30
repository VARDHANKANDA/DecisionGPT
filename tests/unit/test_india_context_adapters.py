"""India public-context adapters (festival calendar + macro). Deterministic,
generated offline; no network, no SME data.
"""
import pandas as pd

from ml.preprocessing import india_festival_adapter, india_macro_adapter


def test_festival_events_schema_and_content():
    ev = india_festival_adapter.build_events()
    assert list(ev.columns) == ["date", "festival", "festival_type", "is_national_holiday", "observed_in"]
    assert len(ev) > 100
    # a few well-known festivals appear
    names = " ".join(ev["festival"].str.lower())
    assert "diwali" in names or "deepavali" in names
    assert "independence day" in names
    # dates are ISO and within the declared window
    d = pd.to_datetime(ev["date"])
    assert d.min() >= pd.Timestamp("2019-01-01")
    assert d.max() <= pd.Timestamp("2027-12-31")
    assert ev["festival_type"].isin(
        {"national_civic", "religious_hindu", "religious_islamic", "religious_christian",
         "religious_sikh", "religious_jain", "religious_buddhist", "other_holiday"}
    ).all()


def test_festival_daily_distance_features_are_consistent():
    daily = india_festival_adapter.build_daily()
    assert list(daily.columns) == [
        "date", "is_festival", "days_to_next_festival", "days_since_last_festival"
    ]
    # on a festival day, distance-to-next is 0
    fest_rows = daily[daily["is_festival"] == 1]
    assert (fest_rows["days_to_next_festival"] == 0).all()
    # distances never negative except the -1 sentinel at the very ends
    assert daily["days_to_next_festival"].min() >= -1
    assert daily["days_since_last_festival"].min() >= -1
    # integer day counts (regression: the datetime64[D] -> int cast must not
    # go through the numpy-2-deprecated pd.Timedelta division path)
    assert daily["days_to_next_festival"].dtype.kind == "i"
    assert daily["days_since_last_festival"].dtype.kind == "i"
    # the day before a festival is exactly 1 day away
    d2n = daily.set_index("date")["days_to_next_festival"]
    fest_dates = set(daily.loc[daily["is_festival"] == 1, "date"])
    import datetime as _dt
    for fd in list(fest_dates)[:20]:
        prev = (_dt.date.fromisoformat(fd) - _dt.timedelta(days=1)).isoformat()
        if prev in d2n.index and prev not in fest_dates:
            assert d2n[prev] == 1


def test_festival_adapter_deterministic():
    pd.testing.assert_frame_equal(
        india_festival_adapter.build_events(), india_festival_adapter.build_events()
    )


def test_macro_repo_rate_series():
    df = india_macro_adapter.build_context()
    assert list(df.columns) == ["month", "repo_rate_pct", "repo_rate_change"]
    assert (df["repo_rate_pct"] > 0).all()
    assert (df["repo_rate_pct"] < 15).all()  # sanity: policy rate, not a typo
    # forward-filled: value only changes on a published change month
    changes = df[df["repo_rate_change"] != 0]
    assert len(changes) == len(india_macro_adapter.RBI_REPO_RATE_CHANGES) - 0 or len(changes) >= 10
    # the Feb-2023 hike to 6.50 is in there
    feb23 = df[df["month"] == "2023-02-01"]
    assert not feb23.empty and float(feb23["repo_rate_pct"].iloc[0]) == 6.50


def test_macro_adapter_deterministic():
    pd.testing.assert_frame_equal(
        india_macro_adapter.build_context(), india_macro_adapter.build_context()
    )
