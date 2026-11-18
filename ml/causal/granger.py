"""Statistical relationship estimation for the Dynamic Causal Graph
(docs/CAUSAL_GRAPH_SPECIFICATION.md §6 "Methods" — priority 2: statistical
relationship estimation; priority 3: one selected causal method).

Two real, standard statistical tests, implemented directly on numpy/scipy
(both already dependencies via scikit-learn — no new dependency needed for
what would otherwise just be `statsmodels.tsa.stattools.grangercausalitytests`):

- Pearson correlation: same-day linear association.
- Granger causality (F-test): does `source`'s past values improve a linear
  prediction of `target` beyond `target`'s own past, at a given lag? This is
  "does X help predict Y", a standard, well-understood test of *predictive*
  precedence — not proof of causation. Callers must not label a significant
  result as CAUSALLY_VALIDATED (see docs/CAUSAL_GRAPH_SPECIFICATION.md §3);
  it supports DATA_SUPPORTED at most.

Never invents a p-value or effect size — every number returned is computed
from the two series passed in, or the function returns None when there
isn't enough data to test honestly.
"""
import numpy as np
from scipy import stats

MIN_PAIRED_OBSERVATIONS = 20


def correlation(source: np.ndarray, target: np.ndarray) -> tuple[float, float] | None:
    """Pearson (r, p-value) for two equal-length series, or None if either
    series has no variance (constant) or there's too little data to test."""
    if len(source) != len(target) or len(source) < MIN_PAIRED_OBSERVATIONS:
        return None
    if np.std(source) < 1e-9 or np.std(target) < 1e-9:
        return None
    r, p = stats.pearsonr(source, target)
    return float(r), float(p)


def _ols_rss(X: np.ndarray, y: np.ndarray) -> float:
    coeffs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    fitted = X @ coeffs
    return float(np.sum((y - fitted) ** 2))


def granger_causality_pvalue(source: np.ndarray, target: np.ndarray, lag: int) -> float | None:
    """F-test p-value for "source Granger-causes target" at the given lag:
    compares a restricted model (target ~ its own lagged values) against an
    unrestricted model (target ~ its own lags + source's lagged values).
    A small p-value means source's past significantly improves the
    prediction of target beyond target's own history.

    Returns None if there isn't enough data to fit both models reliably.
    """
    n = len(target)
    if n <= 3 * lag + 2 or len(source) != n:
        return None
    if np.std(source) < 1e-9 or np.std(target) < 1e-9:
        return None

    y = target[lag:]
    n_obs = len(y)

    x_restricted = np.ones((n_obs, 1))
    for l in range(1, lag + 1):
        x_restricted = np.hstack([x_restricted, target[lag - l : n - l].reshape(-1, 1)])

    x_unrestricted = x_restricted.copy()
    for l in range(1, lag + 1):
        x_unrestricted = np.hstack([x_unrestricted, source[lag - l : n - l].reshape(-1, 1)])

    rss_restricted = _ols_rss(x_restricted, y)
    rss_unrestricted = _ols_rss(x_unrestricted, y)
    df_unrestricted = n_obs - x_unrestricted.shape[1]
    if df_unrestricted <= 0 or rss_unrestricted <= 1e-12:
        return None

    f_stat = max(0.0, ((rss_restricted - rss_unrestricted) / lag) / (rss_unrestricted / df_unrestricted))
    return float(stats.f.sf(f_stat, lag, df_unrestricted))


def best_granger_result(
    source: np.ndarray, target: np.ndarray, max_lag: int = 3
) -> tuple[int, float] | None:
    """Tries lags 1..max_lag (capped by data length) and returns the
    (lag, p_value) with the strongest (smallest) p-value — a standard
    "search a small set of plausible lags" approach given we don't know the
    true lag structure. Returns None if no lag could be tested."""
    results = []
    feasible_max_lag = min(max_lag, max(1, len(target) // 6))
    for lag in range(1, feasible_max_lag + 1):
        p = granger_causality_pvalue(source, target, lag)
        if p is not None:
            results.append((lag, p))
    if not results:
        return None
    return min(results, key=lambda item: item[1])
