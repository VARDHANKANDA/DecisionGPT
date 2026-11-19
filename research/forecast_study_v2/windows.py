"""Evaluation windows of forecast_study_v2.

A *window* is defined by how many trailing days of the series are discarded BEFORE anything is built (``OFFSET``). On the truncated series of length T' the protocol
of forecast_study_v1 is applied unchanged: six consecutive 28-day test blocks cover the last 168 days of the truncated series, three 28-day validation blocks precede them.

  W1  offset 0     the original test period (already scored by forecast_study_v1 and examined repeatedly: NOT independent evidence)
  W2  offset 252   ends one day before W1's first validation block; never scored as a forecast target anywhere in the repository (see WINDOW_USE_AUDIT)
  W3  offset 504   one step earlier still; same status as W2 (M5 only: Online Retail II is too short)

Days are 0-based column indices. ``minimum lag H`` is the staleness of the freshest history input (every target day is an H-day-ahead forecast).
"""
from __future__ import annotations

BLOCK = 28
N_TEST = 6
N_VAL = 3
TRAIN_SPAN = 730
MIN_HISTORY = 84
OFFSETS = {"W1": 0, "W2": 252, "W3": 504}
HORIZONS = (28, 7)


class Infeasible(ValueError):
    pass


def truncated_length(T_full: int, window: str) -> int:
    return T_full - OFFSETS[window]


def blocks(T_trunc: int, H: int) -> dict:
    test = [T_trunc - BLOCK * N_TEST + BLOCK * k for k in range(N_TEST)]
    val = [test[0] - BLOCK * (N_VAL - j) for j in range(N_VAL)]
    if val[0] < H + MIN_HISTORY + BLOCK:
        raise Infeasible(f"first validation block starts at {val[0]}, too early for H={H}, min_history={MIN_HISTORY}")
    return {"test": test, "val": val}


def check_ordered(T_trunc: int, H: int) -> dict:
    b = blocks(T_trunc, H)
    ok = (b["test"][-1] + BLOCK == T_trunc and all(b["test"][i] + BLOCK == b["test"][i + 1] for i in range(N_TEST - 1)) and all(b["val"][i] + BLOCK == b["val"][i + 1] for i in range(N_VAL - 1))
          and b["val"][-1] + BLOCK == b["test"][0])
    if not ok:
        raise AssertionError(f"blocks overlap or leave a gap: {b}")
    return {"validation_blocks": [[o, o + BLOCK - 1] for o in b["val"]], "test_blocks": [[o, o + BLOCK - 1] for o in b["test"]], "T_trunc": T_trunc, "first_unused_day": T_trunc}


def disjoint_from(w_a: str, w_b: str, T_full: int) -> bool:
    """True when the scored span of window ``w_a`` (validation + test) does not intersect that of ``w_b``."""
    def span(w):
        Tp = T_full - OFFSETS[w]
        return Tp - BLOCK * (N_TEST + N_VAL), Tp
    a, b = span(w_a), span(w_b)
    return a[1] <= b[0] or b[1] <= a[0]
