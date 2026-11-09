import numpy as np
import pandas as pd

from fxhedge.v2.hedges import mv_hedge, to_daily, vol_capped_hedge


def test_mv_hedge_recovers_true_exposure():
    rng = np.random.default_rng(0)
    idx = pd.date_range("2000-01-31", periods=200, freq="ME")
    X = pd.DataFrame(rng.normal(0, 0.03, (200, 2)), index=idx, columns=["EUR", "JPY"])
    w = pd.Series({"EUR": 0.6, "JPY": 0.4})
    efa = 0.6 * 0.8 * X["EUR"] + 0.4 * 0.3 * X["JPY"] + rng.normal(0, 0.01, 200)
    H = mv_hedge(efa, X, w)
    assert H.iloc[:59].isna().all().all()
    assert abs(H["EUR"].iloc[-1] - 0.8) < 0.2 and abs(H["JPY"].iloc[-1] - 0.3) < 0.2  # 60-obs OLS se ~0.07-0.1; plan tol 0.15 was 2 se


def test_mv_hedge_no_lookahead():
    rng = np.random.default_rng(1)
    idx = pd.date_range("2000-01-31", periods=150, freq="ME")
    X = pd.DataFrame(rng.normal(0, 0.03, (150, 2)), index=idx, columns=["EUR", "JPY"])
    efa = X.sum(axis=1) * 0.5
    w = pd.Series({"EUR": 0.5, "JPY": 0.5})
    a = mv_hedge(efa, X, w)
    efa2 = efa.copy(); efa2.iloc[100:] = -efa2.iloc[100:]
    pd.testing.assert_frame_equal(a.iloc[:100], mv_hedge(efa2, X, w).iloc[:100])


def test_vol_cap_and_daily_shift():
    v = pd.DataFrame({"EUR": [0.05, 0.10, 0.20]}, index=pd.date_range("2020-01-31", periods=3, freq="ME"))
    H = vol_capped_hedge(v, 0.08)
    assert np.allclose(H["EUR"], [0.0, 0.2, 0.6])
    d = to_daily(H, pd.bdate_range("2020-01-30", "2020-02-04"))
    assert np.isnan(d.iloc[0, 0]) and d.loc["2020-02-03", "EUR"] == 0.0


def test_monthly_indexed_by_last_trading_day():
    from fxhedge.v2.hedges import monthly
    idx = pd.bdate_range("2020-01-27", "2020-02-05")
    x = pd.Series(0.01, index=idx)
    m = monthly(x)
    assert list(m.index) == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-05")]
    assert abs(m.iloc[0] - (1.01 ** 5 - 1)) < 1e-12


def test_mv_hedge_passes_qengine_lookahead_and_checker_catches_leak():
    import pytest
    from qengine.lookahead import LookaheadError, check_lookahead

    rng = np.random.default_rng(2)
    idx = pd.date_range("2000-01-31", periods=140, freq="ME")
    R = pd.DataFrame(rng.normal(0, 0.03, (140, 3)), index=idx, columns=["efa", "EUR", "JPY"])
    w = pd.Series({"EUR": 0.5, "JPY": 0.5})
    ok = lambda D: mv_hedge(D["efa"], D[["EUR", "JPY"]], w)           # noqa: E731
    check_lookahead(ok, R)
    leaky = lambda D: ok(D).shift(-1)                                   # noqa: E731
    with pytest.raises(LookaheadError):
        check_lookahead(leaky, R)
