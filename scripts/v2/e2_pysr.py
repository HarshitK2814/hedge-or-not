"""P6 v2 Task 5, E2 (EXPLORATORY, never headline): PySR symbolic currency-return formula turned into a hedge ratio.
Pre-registration v2 (hash b2e9a0e506a9). Trained once on 2001-09..2010-12 (rows dated <= 2010-11 so the label month ends by 2010-12),
judged ONCE on 2011-2016. Features at month-end close: rate differential, 3/12-month spot momentum, PPP value gap, GARCH FX vol
(GUARDED vol: the literal GJR-GARCH CHF forecast explodes, 1e11 annualised, which would poison the regression), SPY trailing 6-month return.
Label = next month's long-FX forward excess return. Hedge = clip(0.5 - 0.5 tanh(pred / sigma_pred), 0, 1), sigma_pred = training std of
predictions. Compared with static 50% and v1 dynamic3 (stress-aware costs): vol, CVaR(95%), net Sharpe. Deflated Sharpe with
n_trials = Pareto-front size, sr_var = variance of the front equations' per-month Sharpes on 2011-2016 (to deflate the chosen equation;
the choice was fixed by PySR 'best' on training data before judging).
Run: PREREG_HASH=b2e9a0e506a9 python scripts/v2/e2_pysr.py"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from fxhedge import data, model
from fxhedge.v2 import study
from fxhedge.v2.hedges import monthly, to_daily
from fxhedge.v2.pysr_features import feature_panel
from qcore.bootstrap import bootstrap_stat, percentile_ci
from qcore.metrics import var_cvar
from qcore.splits import file_hash
from qcore.validation import deflated_sharpe

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "preregistration_v2.md"
FEATS = ["rate_diff", "mom3", "mom12", "value_gap", "vol", "spy6"]
TRAIN_FIRST, TRAIN_LAST = "2001-09-01", "2010-11-30"
TEST0, TEST1 = "2011-01-01", "2016-12-31"


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
    TAB = study.TAB
    try:
        from pysr import PySRRegressor
    except Exception as e:  # noqa: BLE001
        (TAB / "e2_pysr.json").write_text(json.dumps({"skipped": f"pysr not importable: {e!r}"[:300]}))
        return
    ctx = study.context()
    X, inp, w = ctx["X"], ctx["inp"], ctx["w"]
    g = study.fx_garch_vol(X)
    gg, bad = study.guard_vol(g, X)
    P = feature_panel({**inp, "spy": inp["etf"]["SPY"]}, gg)
    d = P.index.get_level_values(0)
    tr = P[(d >= TRAIN_FIRST) & (d <= TRAIN_LAST)].dropna()
    model_ = PySRRegressor(niterations=60, binary_operators=["+", "-", "*", "/"], unary_operators=["tanh", "sign", "abs"],
                           maxsize=12, populations=16, elementwise_loss="L1DistLoss()", deterministic=True,
                           parallelism="serial", random_state=0, model_selection="best", progress=False,
                           output_directory=str(study.RUNS / "pysr"))
    model_.fit(tr[FEATS], tr["y"])
    front = model_.equations_
    front.to_csv(TAB / "e2_pysr_front.csv", index=False)
    chosen = str(model_.sympy())

    # ---- judged ONCE on 2011-2016
    te = P[(d >= "2010-12-01") & (d <= TEST1)].dropna(subset=FEATS)
    rho = stats.spearmanr(model_.predict(te.dropna(subset=["y"])[FEATS]), te.dropna(subset=["y"])["y"])

    def book(i: int | None) -> tuple[pd.Series, pd.DataFrame]:
        pr = (lambda Z: model_.predict(Z[FEATS], index=i)) if i is not None else (lambda Z: model_.predict(Z[FEATS]))
        sig = float(np.std(pr(tr)))
        pred = pd.Series(pr(te), index=te.index)
        ratio = (0.5 - 0.5 * np.tanh(pred / sig)).clip(0, 1).unstack("ccy")
        Hd = to_daily(ratio, X.index)
        r = study.month_returns(Hd, ctx)
        return r["m"].loc[TEST0:TEST1], Hd

    m_eq, H_eq = book(None)
    b = model.books(inp)
    m50 = study.month_returns(b["static50"]["ratios"], ctx)["m"].loc[TEST0:TEST1]
    m_v1 = study.month_returns(b["dynamic3"]["ratios"], ctx)["m"].loc[TEST0:TEST1]
    rf_d = pd.read_parquet(data.RAW / "dtb3.parquet")["DTB3"]
    rf_m = monthly(rf_d.reindex(X.index).ffill().fillna(0.0).loc["2001-09-01":]).reindex(m_eq.index).fillna(0.0)
    ex = lambda m: m - rf_m.reindex(m.index)                               # noqa: E731
    per = {}
    for i in range(len(front)):
        mi, _ = book(i)
        per[i] = mi
    persh = np.array([(x - rf_m).mean() / (x - rf_m).std(ddof=1) for x in per.values()])
    dsr = (deflated_sharpe((m_eq - rf_m).to_numpy(), n_trials=len(front), sr_var=float(np.var(persh, ddof=1))) if len(front) > 1 else None)
    out = {"label": "EXPLORATORY (E2); judged once on 2011-2016; never headline", "prereg_hash": file_hash(PREREG),
           "train": {"rows": int(len(tr)), "first": TRAIN_FIRST, "last_row_date": TRAIN_LAST, "label_month_ends_by": "2010-12"},
           "vol_input": "GUARDED GJR-GARCH vol (literal CHF forecast explodes); n guarded daily forecasts: " + str(int(bad.sum().sum())),
           "chosen_equation_sympy": chosen, "n_pareto_equations": int(len(front)),
           "pooled_spearman_pred_vs_next_month_return_2011_2016": {"rho": float(rho.statistic), "p": float(rho.pvalue)},
           "portfolio_2011_2016": {"n_months": int(len(m_eq)),
                                   "eq": {"vol": ci(m_eq, vol), "cvar95": ci(m_eq, cv), "sharpe_excess": ci(ex(m_eq), sh)},
                                   "static50": {"vol": ci(m50, vol), "cvar95": ci(m50, cv), "sharpe_excess": ci(ex(m50), sh)},
                                   "v1_dynamic3": {"vol": ci(m_v1, vol), "cvar95": ci(m_v1, cv), "sharpe_excess": ci(ex(m_v1), sh)},
                                   "diff_eq_minus_static50": {"vol": dci(m_eq, m50, vol), "cvar95": dci(m_eq, m50, cv), "sharpe": dci(ex(m_eq), ex(m50), sh)},
                                   "diff_eq_minus_v1": {"vol": dci(m_eq, m_v1, vol), "cvar95": dci(m_eq, m_v1, cv), "sharpe": dci(ex(m_eq), ex(m_v1), sh)},
                                   "mean_hedge_ratio_eq": float((H_eq.mul(w, axis=1).sum(axis=1)).loc[TEST0:TEST1].mean()),
                                   "monthly_turnover_eq": float(H_eq.fillna(0.0).diff().abs().mul(w, axis=1).sum(axis=1).loc[TEST0:TEST1].sum() / len(m_eq))},
           "deflated_sharpe_chosen_monthly": dsr, "front_sharpe_excess_2011_2016": {int(i): sh(x - rf_m) for i, x in per.items()}}
    (TAB / "e2_pysr.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
