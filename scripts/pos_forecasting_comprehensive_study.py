import sys
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from lightgbm import LGBMRegressor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

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
daily["day_of_month"] = daily["date_dt"].dt.day
daily["is_weekend"] = daily["day_of_week"].isin([5, 6]).astype(int)

# 14-day history features
for lag in [1, 2, 3, 7, 14]:
    daily[f"rev_lag_{lag}"] = daily["revenue_inr"].shift(lag)
    daily[f"tx_lag_{lag}"] = daily["transactions"].shift(lag)

daily["rev_roll_mean_7"] = daily["revenue_inr"].shift(1).rolling(7, min_periods=3).mean()
daily["rev_roll_std_7"] = daily["revenue_inr"].shift(1).rolling(7, min_periods=3).std().fillna(0)
daily["tx_roll_mean_7"] = daily["transactions"].shift(1).rolling(7, min_periods=3).mean()

clean_daily = daily.dropna().reset_index(drop=True)

feature_cols = [c for c in clean_daily.columns if c.startswith(("rev_lag_", "tx_lag_", "rev_roll_", "tx_roll_"))] + ["day_of_week", "day_of_month", "is_weekend"]

test_len = 14
train_df = clean_daily.iloc[:-test_len].copy()
test_df = clean_daily.iloc[-test_len:].copy()

y_train = train_df["revenue_inr"].values
y_test = test_df["revenue_inr"].values

# In-sample naive benchmark for MASE
naive_in_sample_mae = np.mean(np.abs(np.diff(y_train)))

def calc_all_metrics(y_true, y_pred, y_train_full):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    r2 = r2_score(y_true, y_pred)
    # sMAPE
    smape = 100 * np.mean(2 * np.abs(y_pred - y_true) / (np.abs(y_true) + np.abs(y_pred) + 1e-8))
    # WAPE
    wape = np.sum(np.abs(y_pred - y_true)) / np.sum(y_true)
    # MASE
    naive_diff = np.mean(np.abs(np.diff(y_train_full)))
    mase = mae / (naive_diff + 1e-8)
    # Forecast bias
    bias = np.mean(y_pred - y_true)
    return {
        "mae": round(float(mae), 2),
        "rmse": round(float(rmse), 2),
        "r2": round(float(r2), 4),
        "smape": round(float(smape), 2),
        "wape": round(float(wape), 4),
        "forecast_accuracy": round(float((1.0 - wape) * 100), 2),
        "mase": round(float(mase), 4),
        "bias": round(float(bias), 2),
    }

print("=== 1. FIXED HOLDOUT TEST SET (14 Days) ===")
# A. Seasonal Naive 7-Day
sn7_pred = test_df["rev_lag_7"].values
m_sn7 = calc_all_metrics(y_test, sn7_pred, y_train)
print("Seasonal Naive 7D:", m_sn7)

# B. LightGBM
lgb = LGBMRegressor(n_estimators=80, num_leaves=12, learning_rate=0.03, subsample=0.85, random_state=42, verbose=-1)
lgb.fit(train_df[feature_cols], y_train)
lgb_pred = lgb.predict(test_df[feature_cols])
m_lgb = calc_all_metrics(y_test, lgb_pred, y_train)
print("LightGBM Regressor:", m_lgb)

# C. Random Forest
rf = RandomForestRegressor(n_estimators=120, max_depth=5, min_samples_leaf=2, random_state=42)
rf.fit(train_df[feature_cols], y_train)
rf_pred = rf.predict(test_df[feature_cols])
m_rf = calc_all_metrics(y_test, rf_pred, y_train)
print("Random Forest Regressor:", m_rf)

# D. Ridge Linear Regression
ridge = Ridge(alpha=30.0, random_state=42)
ridge.fit(train_df[feature_cols], y_train)
ridge_pred = ridge.predict(test_df[feature_cols])
m_ridge = calc_all_metrics(y_test, ridge_pred, y_train)
print("Ridge Linear Regression:", m_ridge)

print("\n=== 2. WALK-FORWARD / EXPANDING WINDOW ROLLING ORIGIN (14 Folds) ===")
# Walk-forward 1-step ahead prediction
wf_preds_rf = []
wf_preds_sn7 = []
wf_actuals = []

for i in range(len(clean_daily) - test_len, len(clean_daily)):
    curr_train = clean_daily.iloc[:i]
    curr_test = clean_daily.iloc[i:i+1]
    
    # Model train
    m = RandomForestRegressor(n_estimators=80, max_depth=5, min_samples_leaf=2, random_state=42)
    m.fit(curr_train[feature_cols], curr_train["revenue_inr"])
    p = m.predict(curr_test[feature_cols])[0]
    
    wf_preds_rf.append(p)
    wf_preds_sn7.append(curr_test["rev_lag_7"].values[0])
    wf_actuals.append(curr_test["revenue_inr"].values[0])

wf_actuals = np.array(wf_actuals)
wf_preds_rf = np.array(wf_preds_rf)
wf_preds_sn7 = np.array(wf_preds_sn7)

m_wf_rf = calc_all_metrics(wf_actuals, wf_preds_rf, y_train)
m_wf_sn7 = calc_all_metrics(wf_actuals, wf_preds_sn7, y_train)
print("Walk-Forward Random Forest:", m_wf_rf)
print("Walk-Forward Seasonal Naive:", m_wf_sn7)

