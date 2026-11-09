"""Industry benchmark hedge ratios. Minimum-variance: Campbell, Serfaty-de Medeiros & Viceira (2010).
Vol-capped: hedge enough that the unhedged part of each currency's vol stays below a target."""

from __future__ import annotations

import numpy as np
import pandas as pd


def monthly(x):
    """Compound daily returns to months, indexed by the month's LAST TRADING DAY (the v1 rebalance day),
    so to_daily applies the ratio from the next business day exactly as v1 does."""
    per = x.index.to_period("M")
    m = (1 + x).groupby(per).prod() - 1
    last = pd.Series(x.index, index=x.index).groupby(per).max()
    m.index = pd.DatetimeIndex(last.to_numpy())
    return m


def mv_hedge(efa_m: pd.Series, X_m: pd.DataFrame, w: pd.Series, window: int = 60) -> pd.DataFrame:
    """Hedged = EFA - sum_c w_c H_c X_c. Minimising its variance gives w*H = OLS slope of EFA on X.
    Row m uses months m-window+1..m only."""
    df = pd.concat([efa_m.rename("_y"), X_m], axis=1).dropna()
    out = pd.DataFrame(np.nan, index=df.index, columns=X_m.columns)
    for i in range(window - 1, len(df)):
        win = df.iloc[i - window + 1:i + 1]
        A = np.column_stack([np.ones(window), win[X_m.columns].to_numpy()])
        beta = np.linalg.lstsq(A, win["_y"].to_numpy(), rcond=None)[0][1:]
        out.iloc[i] = np.clip(beta / w.reindex(X_m.columns).to_numpy(), 0.0, 1.0)
    return out


def vol_capped_hedge(fx_vol_ann: pd.DataFrame, target: float) -> pd.DataFrame:
    return (1 - target / fx_vol_ann).clip(lower=0.0, upper=1.0)


def to_daily(Hm: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    return Hm.reindex(Hm.index.union(idx)).ffill().reindex(idx).shift(1)
