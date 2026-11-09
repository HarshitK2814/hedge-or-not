import numpy as np
import pandas as pd

from fxhedge.v2.pysr_features import feature_panel

FEATS = ["rate_diff", "mom3", "mom12", "value_gap", "vol", "spy6"]


def _inp(n=700, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2000-01-03", periods=n)
    S = pd.DataFrame(1.0 + np.cumsum(rng.normal(0, 0.003, (n, 2)), axis=0), index=idx, columns=["EUR", "JPY"])
    X = S.pct_change(fill_method=None).fillna(0.0)
    rates = pd.DataFrame({"USD": 0.02, "EUR": 0.01, "JPY": 0.0}, index=idx)
    fair = pd.DataFrame(1.1, index=idx, columns=["EUR", "JPY"])
    spy = pd.Series(rng.normal(0, 0.01, n), index=idx)
    vol = pd.DataFrame(0.1, index=idx, columns=["EUR", "JPY"])
    return {"S": S, "X": X, "rates": rates, "fair": fair, "spy": spy, "ccys": ["EUR", "JPY"]}, vol


def test_panel_shape_and_label_is_next_month():
    inp, vol = _inp()
    P = feature_panel(inp, vol)
    assert list(P.columns) == FEATS + ["y"]
    assert P.index.names == ["date", "ccy"]
    d = P.index.get_level_values(0).unique()
    t = d[20]
    nxt = d[21]
    per = inp["X"]["EUR"].loc[(inp["X"].index > t) & (inp["X"].index <= nxt)]
    assert abs(P.loc[(t, "EUR"), "y"] - ((1 + per).prod() - 1)) < 1e-12


def test_features_do_not_use_data_after_the_date():
    inp, vol = _inp()
    P = feature_panel(inp, vol)
    cut = inp["S"].index[500]
    inp2 = {k: (v.copy() if hasattr(v, "copy") else v) for k, v in inp.items()}
    for k in ("S", "X", "rates", "fair"):
        inp2[k].loc[inp2[k].index > cut] = inp2[k].loc[inp2[k].index > cut] * 1.7 + 0.01
    inp2["spy"].loc[inp2["spy"].index > cut] = 0.05
    vol2 = vol.copy(); vol2.loc[vol2.index > cut] = 0.9
    P2 = feature_panel(inp2, vol2)
    before = P.index.get_level_values(0) <= cut
    pd.testing.assert_frame_equal(P.loc[before, FEATS], P2.loc[P2.index.get_level_values(0) <= cut, FEATS])
