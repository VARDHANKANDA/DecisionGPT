import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from lightgbm import LGBMRegressor

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
print(f"Total days: {len(daily)}")
print(f"Revenue stats: mean={daily['revenue_inr'].mean():.2f}, std={daily['revenue_inr'].std():.2f}, min={daily['revenue_inr'].min():.2f}, max={daily['revenue_inr'].max():.2f}")

daily["date_dt"] = pd.to_datetime(daily["date"])
daily["day_of_week"] = daily["date_dt"].dt.dayofweek
daily["day_of_month"] = daily["date_dt"].dt.day
daily["is_weekend"] = daily["day_of_week"].isin([5, 6]).astype(int)

# Use 14-day lags so we only drop 14 days instead of 28 days
for lag in [1, 2, 3, 7, 14]:
    daily[f"rev_lag_{lag}"] = daily["revenue_inr"].shift(lag)
    daily[f"tx_lag_{lag}"] = daily["transactions"].shift(lag)

daily["rev_roll_mean_7"] = daily["revenue_inr"].shift(1).rolling(7, min_periods=3).mean()
daily["rev_roll_std_7"] = daily["revenue_inr"].shift(1).rolling(7, min_periods=3).std().fillna(0)
daily["tx_roll_mean_7"] = daily["transactions"].shift(1).rolling(7, min_periods=3).mean()

clean_daily = daily.dropna().reset_index(drop=True)
print(f"Clean daily records with 14d lags: {len(clean_daily)} days (vs 61 days with 28d lags)")

feature_cols = [c for c in clean_daily.columns if c.startswith(("rev_lag_", "tx_lag_", "rev_roll_", "tx_roll_"))] + ["day_of_week", "day_of_month", "is_weekend"]

# Let's test with test_len = 14 days (2 full weeks)
test_len = 14
train_df = clean_daily.iloc[:-test_len].copy()
test_df = clean_daily.iloc[-test_len:].copy()

X_train, y_train = train_df[feature_cols], train_df["revenue_inr"]
X_test, y_test = test_df[feature_cols], test_df["revenue_inr"]

print(f"Train days: {len(train_df)}, Test days: {len(test_df)}")
print(f"Test mean: {y_test.mean():.2f}, Test std: {y_test.std():.2f}")

# 1. Seasonal Naive 7-day
naive_preds = test_df["rev_lag_7"].values
r2_naive = r2_score(y_test, naive_preds)
mae_naive = mean_absolute_error(y_test, naive_preds)
print(f"Seasonal Naive 7-day: R2 = {r2_naive:.4f}, MAE = {mae_naive:,.2f}")

# 2. Ridge Regression
ridge = Ridge(alpha=50.0)
ridge.fit(X_train, y_train)
ridge_preds = ridge.predict(X_test)
print(f"Ridge Regression: R2 = {r2_score(y_test, ridge_preds):.4f}, MAE = {mean_absolute_error(y_test, ridge_preds):,.2f}")

# 3. Random Forest
rf = RandomForestRegressor(n_estimators=100, max_depth=4, min_samples_leaf=3, random_state=42)
rf.fit(X_train, y_train)
rf_preds = rf.predict(X_test)
print(f"Random Forest: R2 = {r2_score(y_test, rf_preds):.4f}, MAE = {mean_absolute_error(y_test, rf_preds):,.2f}")

# 4. LightGBM
lgb = LGBMRegressor(n_estimators=60, num_leaves=8, learning_rate=0.03, min_child_samples=5, random_state=42, verbose=-1)
lgb.fit(X_train, y_train)
lgb_preds = lgb.predict(X_test)
print(f"LightGBM: R2 = {r2_score(y_test, lgb_preds):.4f}, MAE = {mean_absolute_error(y_test, lgb_preds):,.2f}")

# 5. Log-transformed Ridge / RF
ridge_log = Ridge(alpha=20.0)
ridge_log.fit(X_train, np.log1p(y_train))
ridge_log_preds = np.expm1(ridge_log.predict(X_test))
print(f"Log-Transformed Ridge: R2 = {r2_score(y_test, ridge_log_preds):.4f}, MAE = {mean_absolute_error(y_test, ridge_log_preds):,.2f}")

# 6. Ensemble (Average of Ridge + RF + Naive)
ens_preds = 0.5 * ridge_preds + 0.3 * rf_preds + 0.2 * naive_preds
print(f"Ensemble (Ridge + RF + Naive): R2 = {r2_score(y_test, ens_preds):.4f}, MAE = {mean_absolute_error(y_test, ens_preds):,.2f}")

