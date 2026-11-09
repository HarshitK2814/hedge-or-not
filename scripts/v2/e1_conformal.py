"""P6 v2 Task 5, E1 (EXPLORATORY, never headline): conformal-interval hedge. Pre-registration v2 (hash b2e9a0e506a9).
yhat = trailing 12-month mean of the currency's monthly forward excess return (known at month-end t); ACI (alpha 0.2,
gamma 0.01, window 36 months) interval for month t+1; labels are non-overlapping months, so plain ACI (no delay) is valid:
the interval at month-end t uses scores of months realised by t. Hedge 100% if upper < 0, 0% if lower > 0, else 50%,
applied from the next business day (v1 convention). Coverage reported 2004-2016; hedged-portfolio vs static 50% on 2004-2016.
Run: PREREG_HASH=b2e9a0e506a9 python scripts/v2/e1_conformal.py"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

from fxhedge import data
from fxhedge.v2 import study
from fxhedge.v2.conformal_hedge import conformal_hedge
from fxhedge.v2.hedges import monthly, to_daily
from qcore.bootstrap import bootstrap_stat, percentile_ci
from qcore.metrics import var_cvar
from qcore.splits import file_hash
from qengine.lookahead import check_lookahead

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "preregistration_v2.md"
A0, Z0 = "2004-01-01", "2016-12-31"
ALPHA = 0.2


def sh(m) -> float:
    m = pd.Series(np.asarray(m, dtype=float))
    return float(m.mean() / m.std(ddof=1) * np.sqrt(12))


def cv(m) -> float:
    return var_cvar(pd.Series(np.asarray(m, dtype=float)), 0.95)[1]


def vol(m) -> float:
    return float(pd.Series(np.asarray(m, dtype=float)).std(ddof=1) * np.sqrt(12))


def ci(m: pd.Series, f) -> list[float]:
    lo, hi = percentile_ci(bootstrap_stat(m, f, n_boot=2000, mean_block=6))
    return [float(f(m)), lo, hi]


def dci(a: pd.Series, b: pd.Series, f) -> list[float]:
    D = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    lo, hi = percentile_ci(bootstrap_stat(D, lambda x: f(x["a"]) - f(x["b"]), n_boot=2000, mean_block=6))
    return [float(f(D["a"]) - f(D["b"])), lo, hi, int(len(D))]


def main() -> None:
    assert os.environ.get("PREREG_HASH") == file_hash(PREREG) == "b2e9a0e506a9", "prereg hash mismatch"
    ctx = study.context()
    X, w = ctx["X"], ctx["w"]
    Xm = monthly(X.loc["1999-01-01":])
    H, C = conformal_hedge(Xm, alpha=ALPHA, gamma=0.01, window=36)
    check_lookahead(lambda R: conformal_hedge(R, alpha=ALPHA, gamma=0.01, window=36)[0], Xm, cut=int(len(Xm) * 0.7))
    cov = C.loc[A0:Z0]
    by_ccy = cov.mean()
    monthly_mean = cov.mean(axis=1).dropna()
    lo, hi = percentile_ci(bootstrap_stat(monthly_mean, lambda x: float(np.mean(x)), n_boot=2000, mean_block=6))
    share = {"hedge100": float((H.loc[A0:Z0] == 1.0).to_numpy().mean()), "hedge0": float((H.loc[A0:Z0] == 0.0).to_numpy().mean()),
             "hedge50": float((H.loc[A0:Z0] == 0.5).to_numpy().mean())}
    Hd = to_daily(H, X.index)
    r_e1 = study.month_returns(Hd, ctx)
    r_50 = study.month_returns(to_daily(pd.DataFrame(0.5, index=Xm.index, columns=Xm.columns), X.index), ctx)
    me, m5 = r_e1["m"].loc[A0:Z0], r_50["m"].loc[A0:Z0]
    out = {"label": "EXPLORATORY (E1); not a hypothesis test; never headline", "prereg_hash": file_hash(PREREG),
           "timing": "signal at month-end t from data to t; interval for month t+1 from scores of months realised by t; applied from next business day",
           "params": {"alpha": ALPHA, "gamma": 0.01, "window_months": 36, "yhat": "trailing 12-month mean"},
           "coverage_2004_2016": {"nominal": 1 - ALPHA, "overall": float(cov.stack().mean()), "bootstrap_ci95_month_mean": [lo, hi],
                                  "by_currency": {k: float(v) for k, v in by_ccy.items()}, "n_currency_months": int(cov.stack().shape[0])},
           "hedge_state_shares_2004_2016": share,
           "portfolio_2004_2016": {"n_months": int(len(me)),
                                   "e1_vol": ci(me, vol), "static50_vol": ci(m5, vol), "e1_cvar95": ci(me, cv), "static50_cvar95": ci(m5, cv),
                                   "e1_sharpe_total_return": ci(me, sh), "static50_sharpe_total_return": ci(m5, sh),
                                   "diff_vol": dci(me, m5, vol), "diff_cvar95": dci(me, m5, cv), "diff_sharpe": dci(me, m5, sh),
                                   "mean_hedge_ratio_e1": float(r_e1["ov"]["hedge"].loc[A0:Z0].mean()),
                                   "monthly_turnover_e1": float(Hd.fillna(0.0).diff().abs().mul(w, axis=1).sum(axis=1).loc[A0:Z0].sum() / len(me))},
           "lookahead": "qengine.lookahead.check_lookahead passed on monthly hedge-ratio frame (shock after 70% cut)"}
    # optional MAPIE cross-check on EUR
    try:
        from mapie.regression import TimeSeriesRegressor
        from mapie.subsample import BlockBootstrap
        from sklearn.linear_model import LinearRegression
        y = Xm["EUR"]
        yhat = y.rolling(12).mean()
        df = pd.concat([yhat.rename("f"), y.shift(-1).rename("y")], axis=1).dropna()
        trn, tst = df.loc[:"2003-12-31"], df.loc[A0:Z0]
        m = TimeSeriesRegressor(LinearRegression(), method="enbpi", cv=BlockBootstrap(n_resamplings=30, length=12, overlapping=True, random_state=0),
                                agg_function="mean", n_jobs=1)
        m.fit(trn[["f"]].to_numpy(), trn["y"].to_numpy())
        _, pi = m.predict(tst[["f"]].to_numpy(), confidence_level=1 - ALPHA, ensemble=True)
        mc = float(((tst["y"].to_numpy() >= pi[:, 0, 0]) & (tst["y"].to_numpy() <= pi[:, 1, 0])).mean())
        out["mapie_enbpi_crosscheck_EUR"] = {"coverage": mc, "n": int(len(tst)), "aci_coverage_EUR": float(by_ccy["EUR"]),
                                             "note": "static EnbPI fitted to 2003 (residuals not refreshed) vs our ACI; EUR only"}
    except Exception as e:  # noqa: BLE001
        out["mapie_enbpi_crosscheck_EUR"] = {"skipped": repr(e)[:200]}
    (study.TAB / "e1_conformal.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
