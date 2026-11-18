import numpy as np

from ml.causal.granger import best_granger_result, correlation, granger_causality_pvalue

RNG_SEED = 42


def test_granger_detects_a_real_lagged_relationship():
    rng = np.random.default_rng(RNG_SEED)
    n = 200
    source = rng.normal(0, 1, n)
    noise = rng.normal(0, 0.5, n)
    target = np.zeros(n)
    for t in range(1, n):
        target[t] = 0.6 * source[t - 1] + 0.3 * target[t - 1] + noise[t]

    lag, p_value = best_granger_result(source, target)
    assert lag == 1
    assert p_value < 0.001


def test_granger_finds_nothing_in_independent_series():
    rng = np.random.default_rng(RNG_SEED)
    n = 200
    a = rng.normal(0, 1, n)
    b = rng.normal(0, 1, n)

    result = best_granger_result(a, b)
    assert result is not None
    _, p_value = result
    assert p_value > 0.05


def test_correlation_requires_minimum_observations():
    short_series = np.arange(10, dtype=float)
    assert correlation(short_series, short_series) is None


def test_correlation_requires_variance():
    constant = np.ones(30)
    varying = np.arange(30, dtype=float)
    assert correlation(constant, varying) is None


def test_correlation_detects_a_real_linear_relationship():
    rng = np.random.default_rng(RNG_SEED)
    x = rng.normal(0, 1, 100)
    y = 2 * x + rng.normal(0, 0.1, 100)

    result = correlation(x, y)
    assert result is not None
    r, p = result
    assert r > 0.9
    assert p < 0.001


def test_granger_returns_none_for_insufficient_data():
    short_series = np.arange(5, dtype=float)
    assert granger_causality_pvalue(short_series, short_series, lag=1) is None
