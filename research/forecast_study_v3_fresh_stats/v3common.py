"""Constants of forecast_study_v3 (fresh-window evaluation with classical statistical baselines). Everything here is part of the frozen protocol (PROTOCOL_V3.md)."""
from pathlib import Path

STUDY = Path(__file__).resolve().parent
ROOT = STUDY.parents[1]
RESULTS = STUDY / "results"
WINDOW = "W4"
WINDOW_OFFSET = 756          # trailing days removed; T' = 1941 - 756 = 1185; validation + test span = days 933..1184 (0-based), 2013-08-19 .. 2014-04-27
STORES = {"m5_ca2": "CA_2", "m5_tx2": "TX_2", "m5_wi2": "WI_2"}   # lowest-numbered store of each state that no earlier experiment used as an evaluated entity
HORIZONS = (28, 7)
N_SERIES = 350
SERIES_SEED = 20261022       # fixed before any data of these stores was read
MAX_FIRST_SALE_DAY = 848     # = first validation day (933) - 85: same margin (>= MIN_HISTORY + 1 day) as the original rule for W3 (1100 vs 1185); uses nothing from validation or test
SEEDS_EXTRA = (43, 44)
STAT_MODELS = ("ets", "arima", "theta")
STAT_TRAIN_SPAN = 730        # days of history given to each local model (same span as the learned models' training window)
RETIRED_BENCHMARK_CSV = ROOT / "data" / "external" / "_retired_non_indian" / "m5_forecasting" / "processed" / "m5_forecasting.csv"
