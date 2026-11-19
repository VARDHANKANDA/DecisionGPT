"""
Indian POS Daily Revenue Forecasting — Advanced Econometric and ML Study (v2).

Evaluates 11+ forecasting methods using leakage-free rolling-origin
expanding-window cross-validation on the development set (68 dates),
selects the best model strictly on development CV error, and evaluates
once on the untouched 12-date test set (2025-03-17 to 2025-03-31).

Preserves the exact baseline target definition and comparison standards.
"""
import sys
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import Ridge, Lasso, ElasticNet, LinearRegression
from sklearn.ensemble import RandomForestRegressor, HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

try:
    import xgboost as xgb
except ImportError:
    xgb = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.model_comparison_service import load_pos_daily, make_features, split_dates, regression_metrics

SEED = 42

def enrich_features(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Leakage-safe features. Every feature for day t is computed strictly from days <= t-1

    or is a known calendar property of day t.
    """
    d = df.sort_values(["series_id", "date"]).copy()
    g = d.groupby("series_id")["y"]

    # 1. Lags
    d["lag_1"] = g.shift(1)
    d["lag_7"] = g.shift(7)
    
    # 2. Rolling stats (shifted by 1 so day t never sees day t)
    d["rolling_mean_3"] = g.transform(lambda s: s.shift(1).rolling(3, min_periods=2).mean())
    d["rolling_mean_7"] = g.transform(lambda s: s.shift(1).rolling(7, min_periods=5).mean())
    d["rolling_std_7"] = g.transform(lambda s: s.shift(1).rolling(7, min_periods=5).std().fillna(0))
    d["rolling_median_7"] = g.transform(lambda s: s.shift(1).rolling(7, min_periods=5).median())

    # 3. Expanding historical mean
    d["expanding_mean"] = g.transform(lambda s: s.shift(1).expanding(min_periods=7).mean())

    # 4. Lagged trend
    d["lag_trend_7"] = d["lag_1"] - d["lag_7"]

    # 5. Calendar features
    dow = d["date"].dt.dayofweek
    d["is_weekend"] = dow.isin([5, 6]).astype(int)
    d["day_of_month"] = d["date"].dt.day
    d["week_of_month"] = (d["date"].dt.day - 1) // 7 + 1
    d["month"] = d["date"].dt.month

    # One-hot day of week
    dow_cols = []
    for k in range(7):
        col = f"dow_{k}"
        d[col] = (dow == k).astype(int)
        dow_cols.append(col)

    # 6. Verified Indian Public Holidays & Major Festivals in Jan-Mar 2025
    # Republic Day (Jan 26), Maha Shivratri (Feb 26), Holi (Mar 14)
    holidays = {
        pd.Timestamp("2025-01-26"),
        pd.Timestamp("2025-02-26"),
        pd.Timestamp("2025-03-14"),
    }
    d["is_holiday"] = d["date"].isin(holidays).astype(int)

    base_feats = ["lag_1", "lag_7", "rolling_mean_7"] + dow_cols
    extended_feats = [
        "lag_1", "lag_7", "rolling_mean_3", "rolling_mean_7", "rolling_std_7",
        "rolling_median_7", "expanding_mean", "lag_trend_7", "is_weekend",
        "day_of_month", "week_of_month", "is_holiday"
    ] + dow_cols

    usable = d.dropna(subset=["y", "lag_1", "lag_7", "rolling_mean_7"]).reset_index(drop=True)
    return usable, base_feats, extended_feats

def calculate_mase(y_train, y_test, y_pred, seasonality=7):
    # Mean Absolute Scaled Error: MAE / in-sample seasonal naive MAE
    in_sample_naive_diff = np.abs(y_train[seasonality:] - y_train[:-seasonality])
    denom = np.mean(in_sample_naive_diff)
    if denom == 0:
        return None
    mae = np.mean(np.abs(y_test - y_pred))
    return float(mae / denom)

def calculate_smape(y_true, y_pred):
    denom = (np.abs(y_true) + np.abs(y_pred)) / 2.0
    diff = np.abs(y_true - y_pred)
    mask = denom > 0
    return float(np.mean(diff[mask] / denom[mask]) * 100)

def calculate_wape(y_true, y_pred):
    tot = np.sum(np.abs(y_true))
    if tot == 0:
        return None
    return float(np.sum(np.abs(y_true - y_pred)) / tot * 100)

def run_study():
    daily, info = load_pos_daily()
    usable, base_feats, ext_feats = enrich_features(daily)
    
    dates = sorted(usable["date"].unique())
    parts = split_dates(dates)
    
    train_dates = parts["train"]
    val_dates = parts["val"]
    test_dates = parts["test"]

    trval_mask = usable["date"].isin(set(train_dates) | set(val_dates))
    test_mask = usable["date"].isin(set(test_dates))

    trval_df = usable[trval_mask].sort_values("date").reset_index(drop=True)
    test_df = usable[test_mask].sort_values("date").reset_index(drop=True)

    print(f"Data Summary: {len(usable)} usable rows (68 train+val, {len(test_df)} held-out test)")
    print(f"Test period: {test_df['date'].min().strftime('%Y-%m-%d')} to {test_df['date'].max().strftime('%Y-%m-%d')}")

    # Expanding window CV on 68 train+val dates
    tv_dates = np.array(sorted(trval_df["date"].unique()))
    tscv = TimeSeriesSplit(n_splits=3)
    folds = []
    for tr_i, va_i in tscv.split(tv_dates):
        tr_m = trval_df["date"].isin(set(tv_dates[tr_i])).to_numpy()
        va_m = trval_df["date"].isin(set(tv_dates[va_i])).to_numpy()
        folds.append((tr_m, va_m))

    # Candidate Models Dictionary: name -> (estimator_func, feature_set)
    candidates = {}

    # 1. Simple Baselines
    # Historical Mean
    def pred_hist_mean(trval, va_mask):
        preds = []
        for idx in np.where(va_mask)[0]:
            preds.append(trval.iloc[:idx]["y"].mean())
        return np.array(preds)

    # Historical Weekday Mean
    def pred_weekday_mean(trval, va_mask):
        preds = []
        for idx in np.where(va_mask)[0]:
            target_dow = trval.iloc[idx]["date"].dayofweek
            past = trval.iloc[:idx]
            match = past[past["date"].dt.dayofweek == target_dow]["y"]
            preds.append(match.mean() if len(match) > 0 else past["y"].mean())
        return np.array(preds)

    # Machine Learning candidates
    candidates["Historical Mean"] = ("rule", "hist_mean")
    candidates["Historical Weekday Mean"] = ("rule", "weekday_mean")
    candidates["Naive (Lag 1)"] = ("rule", "lag_1")
    candidates["Seasonal Naive (Lag 7)"] = ("rule", "lag_7")
    candidates["Moving Avg 7D"] = ("rule", "rolling_mean_7")

    candidates["Ridge (Base Feats)"] = ("ml", lambda: make_pipeline(StandardScaler(), Ridge(alpha=10.0)), base_feats)
    candidates["Ridge (Ext Feats)"] = ("ml", lambda: make_pipeline(StandardScaler(), Ridge(alpha=25.0)), ext_feats)
    candidates["Lasso (Ext Feats)"] = ("ml", lambda: make_pipeline(StandardScaler(), Lasso(alpha=50.0)), ext_feats)
    candidates["ElasticNet (Ext Feats)"] = ("ml", lambda: make_pipeline(StandardScaler(), ElasticNet(alpha=20.0, l1_ratio=0.5)), ext_feats)
    candidates["Random Forest (Base)"] = ("ml", lambda: RandomForestRegressor(n_estimators=100, max_depth=3, min_samples_leaf=2, random_state=SEED), base_feats)
    candidates["Random Forest (Ext)"] = ("ml", lambda: RandomForestRegressor(n_estimators=150, max_depth=3, min_samples_leaf=2, random_state=SEED), ext_feats)
    candidates["HistGradientBoosting (Base)"] = ("ml", lambda: HistGradientBoostingRegressor(max_iter=100, learning_rate=0.03, max_depth=3, random_state=SEED), base_feats)
    candidates["HistGradientBoosting (Ext)"] = ("ml", lambda: HistGradientBoostingRegressor(max_iter=100, learning_rate=0.03, max_depth=3, random_state=SEED), ext_feats)

    if lgb is not None:
        candidates["LightGBM (Ext)"] = ("ml", lambda: lgb.LGBMRegressor(n_estimators=50, learning_rate=0.03, max_depth=3, num_leaves=7, random_state=SEED, verbose=-1), ext_feats)

    # 1. Evaluate Cross-Validation on Development Set (train+val)
    cv_scores = {}
    print("\n--- Cross-Validation Results on Development Set (68 dates) ---")
    for name, c_spec in candidates.items():
        fold_maes = []
        fold_rmses = []
        for tr_m, va_m in folds:
            y_va = trval_df.loc[va_m, "y"].to_numpy()
            if c_spec[0] == "rule":
                r_type = c_spec[1]
                if r_type == "hist_mean":
                    p = pred_hist_mean(trval_df, va_m)
                elif r_type == "weekday_mean":
                    p = pred_weekday_mean(trval_df, va_m)
                elif r_type == "lag_1":
                    p = trval_df.loc[va_m, "lag_1"].to_numpy()
                elif r_type == "lag_7":
                    p = trval_df.loc[va_m, "lag_7"].to_numpy()
                elif r_type == "rolling_mean_7":
                    p = trval_df.loc[va_m, "rolling_mean_7"].to_numpy()
            else:
                est = c_spec[1]()
                feats = c_spec[2]
                est.fit(trval_df.loc[tr_m, feats], trval_df.loc[tr_m, "y"])
                p = est.predict(trval_df.loc[va_m, feats])

            fold_maes.append(float(np.mean(np.abs(p - y_va))))
            fold_rmses.append(float(np.sqrt(np.mean((p - y_va)**2))))

        cv_scores[name] = {
            "cv_mae_mean": float(np.mean(fold_maes)),
            "cv_mae_sd": float(np.std(fold_maes)),
            "cv_rmse_mean": float(np.mean(fold_rmses)),
        }
        print(f"{name:30s} | CV MAE: {cv_scores[name]['cv_mae_mean']:10.1f} | CV RMSE: {cv_scores[name]['cv_rmse_mean']:10.1f}")

    # Select best model based strictly on CV MAE on train+val!
    best_candidate_name = min(candidates.keys(), key=lambda k: cv_scores[k]["cv_mae_mean"])
    print(f"\n>>> Selected Model by Development CV MAE: {best_candidate_name} (CV MAE = {cv_scores[best_candidate_name]['cv_mae_mean']:.1f})")

    # 2. Final Evaluation on Untouched Held-Out Test Set (12 dates)
    print("\n--- Final Evaluation on Held-Out Test Set (12 dates) ---")
    y_trval = trval_df["y"].to_numpy()
    y_te = test_df["y"].to_numpy()

    test_results = {}
    for name, c_spec in candidates.items():
        if c_spec[0] == "rule":
            r_type = c_spec[1]
            if r_type == "hist_mean":
                p = np.full(len(test_df), y_trval.mean())
            elif r_type == "weekday_mean":
                preds = []
                for _, r in test_df.iterrows():
                    dow = r["date"].dayofweek
                    m = trval_df[trval_df["date"].dt.dayofweek == dow]["y"]
                    preds.append(m.mean() if len(m) > 0 else y_trval.mean())
                p = np.array(preds)
            elif r_type == "lag_1":
                p = test_df["lag_1"].to_numpy()
            elif r_type == "lag_7":
                p = test_df["lag_7"].to_numpy()
            elif r_type == "rolling_mean_7":
                p = test_df["rolling_mean_7"].to_numpy()
        else:
            est = c_spec[1]()
            feats = c_spec[2]
            est.fit(trval_df[feats], y_trval)
            p = est.predict(test_df[feats])

        reg = regression_metrics(y_te, p)
        mase = calculate_mase(y_trval, y_te, p)
        smape = calculate_smape(y_te, p)
        wape = calculate_wape(y_te, p)
        
        test_results[name] = {
            **reg,
            "mase": mase,
            "smape": smape,
            "wape": wape,
            "cv_mae": cv_scores[name]["cv_mae_mean"],
            "cv_rmse": cv_scores[name]["cv_rmse_mean"],
        }
        r2_str = f"{reg['r2']:.4f}" if reg['r2'] is not None else "N/A"
        print(f"{name:30s} | MAE: {reg['mae']:8.1f} | RMSE: {reg['rmse']:8.1f} | R2: {r2_str:7s} | MAPE: {reg['mape_pct']:5.1f}% | sMAPE: {smape:5.1f}% | WAPE: {wape:5.1f}% | MASE: {mase:.4f}")

    return {
        "dataset": "india_pos_register",
        "n_usable_observations": len(usable),
        "split": {
            "train_val_dates": len(trval_df),
            "test_dates": len(test_df),
            "test_range": [str(test_df["date"].min())[:10], str(test_df["date"].max())[:10]],
        },
        "selected_model": best_candidate_name,
        "selection_metric": "cv_mae_mean",
        "cv_scores": cv_scores,
        "test_results": test_results,
    }

if __name__ == "__main__":
    out = run_study()
    out_file = ROOT / "experiments" / "results" / "improved_pos_forecasting_study.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(out, indent=2))
    print(f"\nSaved study results to {out_file}")

