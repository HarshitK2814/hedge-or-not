"""Shared pieces for the v2 scripts: context, GARCH FX vols (cached, guarded), monthly books."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from fxhedge import model
from fxhedge.v2.costs import load_vix, stress_multiplier
from fxhedge.v2.hedges import monthly

ROOT = Path(__file__).resolve().parents[3]
RUNS = ROOT / "results" / "v2" / "runs"
TAB = ROOT / "results" / "v2" / "tables"
FIG = ROOT / "results" / "v2" / "figures"
EVAL = ("2006-01-01", "2016-12-31")          # H1-H2 evaluation window (prereg v2)
CHOICE_END = "2016-12-31"                    # choices use data up to here only
SEEN = "seen period (v1 reported it)"


def context() -> dict:
    inp = model.inputs()
    X = inp["X"]
    w = pd.Series(inp["cfg"]["basket"], dtype=float)
    w = w / w.sum()
    efa = inp["etf"]["EFA"].dropna()
    efa_d = efa.reindex(X.index).fillna(0.0).loc["2001-08-28":]
    vix = load_vix()
    return {"inp": inp, "X": X, "w": w, "efa": efa, "efa_d": efa_d, "mult": stress_multiplier(vix),
            "idx": X.index.intersection(efa_d.index)}


def fx_garch_vol(X: pd.DataFrame, refresh: bool = False) -> pd.DataFrame:
    """Annualised GJR-GARCH(1,1,1)-t one-step vol per currency (value at t made at close t), from 1999-01-04.
    Cached. LITERAL output; use guard_vol for the labelled sensitivity."""
    p = RUNS / "fx_garch_vol_ann.parquet"
    if p.exists() and not refresh:
        return pd.read_parquet(p)
    from qcore.risk import garch_vol_forecast
    out = {}
    for c in X.columns:
        out[c] = garch_vol_forecast(X[c].loc["1999-01-04":], refit_every=21) * np.sqrt(252)
    df = pd.DataFrame(out)
    df.to_parquet(p)
    return df


def guard_vol(g: pd.DataFrame, X: pd.DataFrame, lam: float = 0.94, ratio: float = 3.0, cap: float = 0.5) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sensitivity guard: a GARCH forecast is rejected (EWMA lambda=0.94 vol used instead) if non-finite, > cap
    annualised, or more than `ratio` x / less than 1/ratio of the EWMA vol. Returns (vol, rejected mask)."""
    ew = (X.loc["1999-01-04":] ** 2).ewm(alpha=1 - lam, adjust=False).mean().pow(0.5) * np.sqrt(252)
    ew = ew.reindex(g.index)
    bad = (~np.isfinite(g)) | (g > cap) | (g > ratio * ew) | (g < ew / ratio)
    return g.where(~bad & g.notna(), ew).where(g.notna()), bad & g.notna()


def month_returns(H_daily: pd.DataFrame, ctx: dict, cost_mult="stress") -> dict:
    """Overlay on the basket + EFA, monthly USD returns. H_daily: daily ratios (NaN = unavailable -> 0).
    cost_mult: "stress" (VIX x3 rule), None (v1 costs) or a Series."""
    cm = ctx["mult"] if isinstance(cost_mult, str) else cost_mult
    ov = model.overlay(H_daily, ctx["inp"], cost_mult=cm)
    net = ov["net"].reindex(ctx["efa_d"].index).fillna(0.0)
    eq = ctx["efa_d"] + net
    return {"ov": ov, "eq_daily": eq, "m": monthly(eq)}


def ann_vol(m: pd.Series) -> float:
    return float(m.std(ddof=1) * np.sqrt(12))


def sharpe_m(m: pd.Series) -> float:
    return float(m.mean() / m.std(ddof=1) * np.sqrt(12))
