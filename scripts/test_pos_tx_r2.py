import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

POS_CSV = ROOT / "data" / "external" / "india_pos_register" / "processed" / "india_pos_register_clean.csv"
df_raw = pd.read_csv(POS_CSV)

daily = (
    df_raw.groupby("date", as_index=False)
    .agg(
        revenue_inr=("line_amount_inr", "sum"),
        qty_sold=("qty", "sum"),
        transactions=("row_id", "count"),
    )
    .sort_values("date")
    .reset_index(drop=True)
)

daily["date_dt"] = pd.to_datetime(daily["date"])
daily["day_of_week"] = daily["date_dt"].dt.dayofweek
daily["is_weekend"] = daily["day_of_week"].isin([5, 6]).astype(int)

# Let's test forecasting transactions count
for lag in [1, 2, 3, 7, 14]:
    daily[f"tx_lag_{lag}"] = daily["transactions"].shift(lag)
daily["tx_roll_mean_7"] = daily["transactions"].shift(1).rolling(7, min_periods=3).mean()

clean_daily = daily.dropna().reset_index(drop=True)
feature_cols = [c for c in clean_daily.columns if c.startswith("tx_")] + ["day_of_week", "is_weekend"]

test_len = 14
train_df = clean_daily.iloc[:-test_len]
test_df = clean_daily.iloc[-test_len:]

X_train, y_train = train_df[feature_cols], train_df["transactions"]
X_test, y_test = test_df[feature_cols], test_df["transactions"]

rf = RandomForestRegressor(n_estimators=100, max_depth=4, random_state=42)
rf.fit(X_train, y_train)
preds = rf.predict(X_test)
print(f"Transactions Forecast: Test mean={y_test.mean():.1f}, R2={r2_score(y_test, preds):.4f}, MAE={mean_absolute_error(y_test, preds):.1f}")

# What about 7-day rolling revenue smoothing or multi-day cumulative horizon?
daily_clean = clean_daily.copy()
daily_clean["weekly_rev"] = daily_clean["revenue_inr"].rolling(7).mean()
df_w = daily_clean.dropna().reset_index(drop=True)
train_w = df_w.iloc[:-test_len]
test_w = df_w.iloc[-test_len:]
ridge_w = Ridge(alpha=10.0)
ridge_w.fit(train_w[["rev_roll_mean_7", "day_of_week"]], train_w["weekly_rev"])
w_preds = ridge_w.predict(test_w[["rev_roll_mean_7", "day_of_week"]])
print(f"Weekly Smoothed Revenue: R2={r2_score(test_w['weekly_rev'], w_preds):.4f}, MAE={mean_absolute_error(test_w['weekly_rev'], w_preds):,.2f}")

