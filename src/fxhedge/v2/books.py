"""The four tracked books (static 50, v1 dynamic3, MV 60m, vol-capped walk-forward) as daily hedge-ratio frames.
Timing: ratios computed at the last business day of month m from data up to that day, applied from the next business day.
The vol-capped target is chosen by the prereg walk-forward (anchored, 2-year test blocks): 2006-2016 exactly as in
scripts/v2/h1_h2.py, then the same rule continued over the seen period (2017-2026) with training windows that end before each block."""

from __future__ import annotations

import numpy as np
import pandas as pd

from fxhedge import model
from fxhedge.v2 import study
from fxhedge.v2.hedges import monthly, mv_hedge, to_daily, vol_capped_hedge
from qcore.metrics import var_cvar
from qengine.walkforward import plateau_select, wf_folds

TARGETS = [0.04, 0.06, 0.08, 0.10]
BOOKS = ("static50", "v1_dynamic3", "mv60", "volcap_wf")


def cvar95(m: pd.Series) -> float:
    return var_cvar(m, 0.95)[1]


def vc_folds(index: pd.DatetimeIndex, last_year: int) -> list:
    """2006-2016 folds as in h1_h2.py, then 2-year blocks from 2017 to last_year (anchored)."""
    f = wf_folds(index, 2006, 2, 2016, anchored=True)
    if last_year >= 2017:
        f += wf_folds(index, 2017, 2, last_year, anchored=True)
    return f


def volcap_walk_forward(vol_m: pd.DataFrame, ctx: dict, last_year: int = 2026) -> dict:
    """vol_m: month-end annualised vol forecasts. Target per fold = plateau-smoothed min trailing monthly CVaR(95%)."""
    X = ctx["X"]
    cand_H = {t: to_daily(vol_capped_hedge(vol_m, t), X.index) for t in TARGETS}
    cand_m = {t: study.month_returns(H, ctx)["m"] for t, H in cand_H.items()}
    avail_from = vol_m.dropna().index[0]
    pieces, rows = [], []
    for tr0, tr1, te0, te1 in vc_folds(X.index, last_year):
        tr_months = cand_m[TARGETS[0]].loc[max(pd.Timestamp(tr0), avail_from) + pd.Timedelta(days=1):tr1].index
        scores = np.array([-cvar95(cand_m[t].loc[tr_months]) for t in TARGETS])
        best = plateau_select(scores)[0]
        rows.append({"fold_test": f"{te0.date()}..{te1.date()}", "chosen_target": TARGETS[best], "n_train_months": len(tr_months)})
        pieces.append(cand_H[TARGETS[best]].loc[te0:te1])
    H = pd.concat(pieces).reindex(X.index)
    return {"H": H, "folds": rows, "cand_H": cand_H, "last_target": rows[-1]["chosen_target"]}


def build(ctx: dict, last_complete_month_end: pd.Timestamp | None = None, last_year: int = 2026) -> dict:
    """Daily ratio frames for every tracked book (+ the guarded vol-cap sensitivity). Months after
    `last_complete_month_end` are not used for MV/GARCH sampling (a partial last month must not enter)."""
    inp, X, w, efa_d = ctx["inp"], ctx["X"], ctx["w"], ctx["efa_d"]
    b = model.books(inp)
    Xm = monthly(X.loc["2001-09-01":])
    efa_m = monthly(efa_d.loc["2001-09-01":])
    if last_complete_month_end is not None:
        efa_m = efa_m.loc[:last_complete_month_end]
    Xm = Xm.loc[efa_m.index]
    H_mv = to_daily(mv_hedge(efa_m, Xm, w, 60), X.index)
    g = study.fx_garch_vol(X)
    me = Xm.index[Xm.index <= g.index[-1]]
    g_m = g.reindex(me)
    gg, _ = study.guard_vol(g, X)
    wf = volcap_walk_forward(g_m, ctx, last_year)
    wf_g = volcap_walk_forward(gg.reindex(me), ctx, last_year)
    return {"static50": b["static50"]["ratios"], "static100": b["static100"]["ratios"], "unhedged": b["unhedged"]["ratios"],
            "v1_dynamic3": b["dynamic3"]["ratios"], "mv60": H_mv, "volcap_wf": wf["H"], "volcap_wf_guarded": wf_g["H"],
            "_wf": wf, "_wf_guarded": wf_g, "_g_m": g_m, "_vol_end": g.index[-1]}
