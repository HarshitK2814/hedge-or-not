"""Hedge ratios for month m+1 may depend only on data up to the last business day of month m."""

import numpy as np
import pandas as pd

from fxhedge import model


def _inputs(seed=0, n=1400):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2001-01-01", periods=n)
    ccys = ["EUR", "JPY", "AUD"]
    S = pd.DataFrame(np.exp(np.cumsum(rng.normal(0, 0.006, (n, 3)), axis=0)), index=idx, columns=ccys)
    rates = pd.DataFrame({"USD": 0.03, "EUR": 0.02, "JPY": 0.001, "AUD": 0.05}, index=idx)
    fair = pd.DataFrame(1.0, index=idx, columns=ccys)
    etf = pd.DataFrame({"SPY": rng.normal(0.0004, 0.01, n)}, index=idx)
    X = S.pct_change().fillna(0.0)
    cfg = {"momentum": {"fast": 10, "slow": 240}, "value_window": 20,
           "volatility": {"window": 21, "lookback": 252},
           "cross_asset": {"window": 63, "risk_on": ["EUR", "AUD"], "safe_haven": ["JPY"]},
           "basket": {"EUR": 0.5, "JPY": 0.3, "AUD": 0.2}, "cost_bp": {c: 1.0 for c in ccys},
           "roll_bp": {c: 0.5 for c in ccys}}
    return {"cfg": cfg, "ccys": ccys, "S": S, "rates": rates, "X": X, "etf": etf, "fair": fair}


def test_ratios_unchanged_by_future_data():
    a = _inputs()
    cut = a["S"].index[900]
    b = {**a, "S": a["S"].copy(), "etf": a["etf"].copy()}
    later = b["S"].index > cut
    b["S"].loc[later] *= np.linspace(1.1, 2.0, later.sum())[:, None]
    b["etf"].loc[later] -= 0.05
    for sig in (model.DISCLOSED, model.EXTENDED):
        ha = model.hedge_ratios(model.votes(a), sig)
        hb = model.hedge_ratios(model.votes(b), sig)
        pd.testing.assert_frame_equal(ha.loc[:cut], hb.loc[:cut])


def test_ratio_steps():
    a = _inputs()
    h = model.hedge_ratios(model.votes(a), model.DISCLOSED).dropna()
    assert set(np.round(np.unique(h.to_numpy()), 6)) <= {0.0, round(1 / 3, 6), 0.5, round(2 / 3, 6), 1.0}


def test_ratio_constant_within_month():
    a = _inputs()
    h = model.hedge_ratios(model.votes(a), model.DISCLOSED).dropna()
    first = h.groupby(h.index.to_period("M")).transform("first")
    assert (h == first).all().all()
