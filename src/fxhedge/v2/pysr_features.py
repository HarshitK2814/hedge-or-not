"""E2 (EXPLORATORY) feature panel: one row per (month-end, currency); features known at that month-end close,
label = the NEXT month's forward excess return of the currency (long-FX)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fxhedge.v2.hedges import monthly


def feature_panel(inp: dict, vol: pd.DataFrame) -> pd.DataFrame:
    S, X, rates, ccys = inp["S"].ffill(), inp["X"], inp["rates"], inp["ccys"]
    spy_c = (1 + inp["spy"].reindex(S.index).fillna(0.0)).cumprod()
    me = monthly(X).index                                   # last trading day of each month
    f = {
        "rate_diff": rates[ccys].sub(rates["USD"], axis=0),
        "mom3": S[ccys] / S[ccys].shift(63) - 1,
        "mom12": S[ccys] / S[ccys].shift(252) - 1,
        "value_gap": np.log(S[ccys] / inp["fair"][ccys]),
        "vol": vol[ccys].reindex(S.index),
    }
    spy6 = (spy_c / spy_c.shift(126) - 1)
    y = monthly(X[ccys]).shift(-1)
    rows = {}
    for c in ccys:
        d = pd.DataFrame({k: v[c].reindex(me) for k, v in f.items()})
        d["spy6"] = spy6.reindex(me)
        d["y"] = y[c].reindex(me)
        rows[c] = d
    P = pd.concat(rows, names=["ccy", "date"]).swaplevel().sort_index()
    P.index = P.index.set_names(["date", "ccy"])
    return P
