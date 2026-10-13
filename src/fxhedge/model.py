"""Monthly dynamic hedge ratios from equal-weighted votes, and the daily P&L of the currency overlay.

Timing: signals use data up to and including the last business day of month m (the rebalance day). The new hedge
ratio applies from the next business day, for all of month m+1. A short forward on currency c earns
-(spot return + (i_c - i_US) dt), i.e. hedging gives up the foreign carry and the currency move.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import data
from .macro import fx_rates, fx_spot

DT = 1 / 252
DISCLOSED = ("rate", "momentum", "value")
EXTENDED = DISCLOSED + ("volatility", "cross_asset")


def inputs() -> dict:
    c = data.cfg()
    ccys = list(c["basket"])
    S = fx_spot()[ccys].dropna(how="all")
    idx = S.index
    rates = fx_rates(idx)
    spot_ret = S.ffill(limit=5).pct_change(fill_method=None)
    carry = rates[ccys].sub(rates["USD"], axis=0) * DT
    X = (spot_ret + carry.shift(1)).where(spot_ret.notna()).fillna(0.0)    # long-FX forward excess return
    etf = data.etf_returns()
    return {"cfg": c, "ccys": ccys, "S": S, "rates": rates, "X": X, "etf": etf,
            "fair": data.ppp_daily(idx)[ccys]}


def month_ends(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(idx, index=idx)
    return pd.DatetimeIndex(s.groupby(idx.to_period("M")).max().to_numpy())


def votes(inp: dict) -> dict[str, pd.DataFrame]:
    """Daily 0/1 votes ('1' = hedge this currency), each computed only from data up to that day."""
    c, S, rates, ccys = inp["cfg"], inp["S"].ffill(), inp["rates"], inp["ccys"]
    v = {}
    v["rate"] = (rates[ccys].rsub(rates["USD"], axis=0) > 0).astype(float).where(rates[ccys].notna())
    fast = S.rolling(c["momentum"]["fast"], min_periods=c["momentum"]["fast"]).mean()
    slow = S.rolling(c["momentum"]["slow"], min_periods=c["momentum"]["slow"]).mean()
    v["momentum"] = (fast < slow).astype(float).where(slow.notna())
    avg = S.rolling(c["value_window"], min_periods=c["value_window"]).mean()
    v["value"] = (avg > inp["fair"]).astype(float).where(inp["fair"].notna() & avg.notna())
    w, lb = c["volatility"]["window"], c["volatility"]["lookback"]
    vol = S.pct_change(fill_method=None).rolling(w, min_periods=w).std()
    med = vol.rolling(lb, min_periods=lb).median()
    v["volatility"] = (vol > med).astype(float).where(med.notna())
    spy = inp["etf"]["SPY"].reindex(S.index).fillna(0.0)
    trail = (1 + spy).rolling(c["cross_asset"]["window"]).apply(np.prod, raw=True) - 1
    down = (trail < 0).astype(float).where(trail.notna())
    ca = pd.DataFrame(index=S.index, columns=ccys, dtype=float)
    for ccy in ccys:
        ca[ccy] = down if ccy in c["cross_asset"]["risk_on"] else 1 - down
    v["cross_asset"] = ca
    return v


def hedge_ratios(v: dict[str, pd.DataFrame], signals: tuple[str, ...]) -> pd.DataFrame:
    """Monthly hedge ratio = mean vote over `signals`, sampled on month-ends, applied from the next day.
    A currency needs every signal available, otherwise its hedge ratio is the 50% neutral."""
    idx = v["rate"].index
    me = month_ends(idx)
    stack = [v[s].reindex(me) for s in signals]
    h = sum(stack) / len(stack)
    h = h.where(~pd.concat(stack).isna().groupby(level=0).any().reindex(me), 0.5)
    daily = h.reindex(idx).ffill().shift(1)          # set on month-end close, held from the next day
    return daily


def static(idx: pd.DatetimeIndex, ccys: list[str], ratio: float) -> pd.DataFrame:
    return pd.DataFrame(ratio, index=idx, columns=ccys)


def overlay(H: pd.DataFrame, inp: dict) -> dict[str, pd.Series]:
    """Daily overlay return on a portfolio with the basket's currency exposure, and its costs."""
    c = inp["cfg"]
    w = pd.Series(c["basket"], dtype=float)
    w = w / w.sum()
    H = H.reindex(inp["X"].index).fillna(0.0)
    gross = -(H * inp["X"]).mul(w, axis=1).sum(axis=1)
    cost_bp, roll_bp = pd.Series(c["cost_bp"]) / 1e4, pd.Series(c["roll_bp"]) / 1e4
    first_day = H.index.to_period("M") != pd.Index(H.index.to_period("M")).to_series().shift(1).to_numpy()
    trade = H.diff().abs().fillna(H.abs()).mul(w * cost_bp, axis=1).sum(axis=1)
    roll = H.abs().mul(w * roll_bp, axis=1).sum(axis=1).where(first_day, 0.0)
    cost = trade + roll
    return {"gross": gross, "cost": cost, "net": gross - cost, "hedge": H.mul(w, axis=1).sum(axis=1)}


def books(inp: dict) -> dict[str, dict]:
    v = votes(inp)
    idx, ccys = inp["X"].index, inp["ccys"]
    H = {"unhedged": static(idx, ccys, 0.0), "static50": static(idx, ccys, 0.5), "static100": static(idx, ccys, 1.0),
         "dynamic3": hedge_ratios(v, DISCLOSED), "extended5": hedge_ratios(v, EXTENDED)}
    for s in EXTENDED:
        H[f"only_{s}"] = hedge_ratios(v, (s,))
    out = {k: overlay(h, inp) for k, h in H.items()}
    for k in out:
        out[k]["ratios"] = H[k]
    return out


def hedged_equity(ov: dict, etf: pd.DataFrame) -> pd.Series:
    """EFA (unhedged USD total return) plus the currency overlay, on EFA trading days."""
    efa = etf["EFA"].dropna()
    o = ov["net"].reindex(efa.index).fillna(0.0)
    return efa + o
