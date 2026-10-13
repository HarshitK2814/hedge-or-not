"""Run the hedging study. Usage:

    python scripts/run.py download
    python scripts/run.py dev      # development + validation (always allowed)
    python scripts/run.py test     # locked: needs PREREG_HASH = hash of research/preregistration.md
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from fxhedge import analysis as A
from fxhedge import data, model

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results"
MAIN = ["unhedged", "static50", "static100", "dynamic3", "extended5"]
SINGLE = [f"only_{s}" for s in model.EXTENDED]


def build():
    inp = model.inputs()
    b = model.books(inp)
    etf = inp["etf"]
    rf = (data.fred("DTB3") / 100 / 252) if not (data.RAW / "dtb3.parquet").exists() else \
        pd.read_parquet(data.RAW / "dtb3.parquet")["DTB3"]
    rf.to_frame("DTB3").to_parquet(data.RAW / "dtb3.parquet")
    eq = {k: model.hedged_equity(v, etf) for k, v in b.items()}
    rf_d = rf.reindex(etf.index).ffill().fillna(0.0)
    (OUT / "runs").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(eq).to_parquet(OUT / "runs" / "hedged_equity_daily.parquet")
    pd.DataFrame({k: v["net"] for k, v in b.items()}).to_parquet(OUT / "runs" / "overlay_daily.parquet")
    pd.DataFrame({k: v["hedge"] for k, v in b.items()}).to_parquet(OUT / "runs" / "hedge_ratio_daily.parquet")
    b["dynamic3"]["ratios"].to_parquet(OUT / "runs" / "dynamic3_ratios.parquet")
    return inp, b, eq, etf, rf_d


def excess_monthly(r: pd.Series, rf: pd.Series) -> pd.Series:
    return A.monthly(r.dropna()) - A.monthly(rf.reindex(r.dropna().index).fillna(0.0))


def replication(b, etf, name: str) -> pd.DataFrame:
    """Our overlay vs the real hedged-minus-unhedged ETF return gap, monthly."""
    pairs = {"static100 vs HEFA-EFA": ("static100", "HEFA", "EFA"),
             "static100 vs DBEF-EFA": ("static100", "DBEF", "EFA"),
             "dynamic3 vs DDWM-DWM": ("dynamic3", "DDWM", "DWM"),
             "static100 vs DDWM-DWM": ("static100", "DDWM", "DWM"),
             "static50 vs DDWM-DWM": ("static50", "DDWM", "DWM")}
    rows = {}
    for lab, (book, h, u) in pairs.items():
        gap = (A.monthly(etf[h].dropna()) - A.monthly(etf[u].reindex(etf[h].dropna().index))).dropna()
        ours = A.monthly(b[book]["net"].reindex(etf[h].dropna().index).fillna(0.0))
        df = A.period(pd.concat([ours, gap], axis=1).dropna(), name)
        if len(df) >= 12:
            te = (df.iloc[:, 0] - df.iloc[:, 1]).std() * np.sqrt(12)
            rows[lab] = {"corr": df.corr().iloc[0, 1], "tracking_error": te, "n_months": len(df)}
    return pd.DataFrame(rows).T


def regret(eq, rf, name: str) -> pd.DataFrame:
    """Per calendar year: Sharpe (daily, annualised) shortfall of each rule to the best static hedge in hindsight."""
    ex = pd.DataFrame({k: eq[k] - rf.reindex(eq[k].index).fillna(0.0) for k in MAIN + SINGLE}).dropna()
    ex = A.period(ex, name)
    yearly = ex.groupby(ex.index.year).apply(lambda d: d.mean() / d.std() * np.sqrt(252))
    best = yearly[["unhedged", "static50", "static100"]].max(axis=1)
    worst = yearly[["unhedged", "static50", "static100"]].min(axis=1)
    reg = yearly.rsub(best, axis=0)
    return pd.DataFrame({"mean_regret": reg.mean(), "max_regret": reg.max(),
                         "years_worse_than_worst_static": yearly.lt(worst, axis=0).sum(),
                         "n_years": len(yearly)})


def holm(pvals: dict) -> dict:
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m, out, run = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        out[k] = run
    return out


def mean_diff_test(a: pd.Series, b: pd.Series) -> dict:
    d = (a - b).dropna()
    fit = sm.OLS(d, np.ones(len(d))).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
    t = float(fit.tvalues.iloc[0])
    from scipy import stats
    return {"mean_ann": float(d.mean() * 12), "t": t, "p_one_sided": float(1 - stats.norm.cdf(t)), "n_months": len(d)}


def report(b, eq, etf, rf, periods, tag):
    out = {}
    for p in periods:
        ex = {k: A.period(excess_monthly(eq[k], rf), p) for k in MAIN + SINGLE}
        t = pd.DataFrame({k: A.summary(v, 12) for k, v in ex.items()}).T
        ovl = {k: A.period(A.monthly(b[k]["net"]), p) for k in MAIN + SINGLE}
        t["overlay_ann"] = pd.Series({k: v.mean() * 12 for k, v in ovl.items()})
        t["avg_hedge"] = pd.Series({k: A.period(b[k]["hedge"], p).mean() for k in MAIN + SINGLE})
        t["cost_bp_yr"] = pd.Series({k: A.period(b[k]["cost"], p).sum() / max(len(A.period(b[k]["cost"], p)) / 252, 1e-9) * 1e4
                                     for k in MAIN + SINGLE})
        t.to_csv(OUT / "tables" / f"summary_{p}.csv")
        reg = regret(eq, rf, p)
        reg.to_csv(OUT / "tables" / f"regret_{p}.csv")
        print(reg.round(3).to_string())
        rep = replication(b, etf, p)
        rep.to_csv(OUT / "tables" / f"replication_{p}.csv")
        print(f"\n===== {p} =====")
        print(t[["n_periods", "ann_return", "ann_vol", "sharpe", "sharpe_ci95_lo", "sharpe_ci95_hi", "max_drawdown",
                 "overlay_ann", "avg_hedge", "cost_bp_yr"]].round(3).to_string())
        print(rep.round(3).to_string())
        out[p] = {"summary": t.to_dict(orient="index"), "replication": rep.to_dict(orient="index")}
    (OUT / "runs" / f"summary_{tag}.json").write_text(json.dumps(out, default=str, indent=1))


def hypotheses(b, eq, rf, name):
    ex = {k: A.period(excess_monthly(eq[k], rf), name) for k in MAIN + SINGLE}
    ovl = {k: A.period(A.monthly(b[k]["net"]), name) for k in MAIN + SINGLE}
    h3 = {s: mean_diff_test(ovl[f"only_{s}"], ovl["static50"]) for s in model.DISCLOSED}
    adj = holm({s: v["p_one_sided"] for s, v in h3.items()})
    h = {"H1_dynamic3_vs_static50_sharpe": A.sharpe_diff_test(ex["dynamic3"], ex["static50"]),
         "H2_extended5_vs_dynamic3_sharpe": A.sharpe_diff_test(ex["extended5"], ex["dynamic3"]),
         "H3_single_signal_overlay_vs_static50": {s: {**v, "p_holm": adj[s]} for s, v in h3.items()},
         "secondary_dynamic3_vs_unhedged_sharpe": A.sharpe_diff_test(ex["dynamic3"], ex["unhedged"]),
         "secondary_dynamic3_vs_static100_sharpe": A.sharpe_diff_test(ex["dynamic3"], ex["static100"])}
    print(name, json.dumps(h, indent=1, default=lambda x: round(x, 4) if isinstance(x, float) else str(x)))
    (OUT / "runs" / f"hypotheses_{name}.json").write_text(json.dumps(h, indent=1, default=str))


def main(cmd):
    if cmd == "download":
        data.download()
        return
    inp, b, eq, etf, rf = build()
    if cmd == "dev":
        report(b, eq, etf, rf, ["development", "validation"], "devval")
        for p in ("development", "validation"):
            hypotheses(b, eq, rf, p)
    elif cmd == "test":
        report(b, eq, etf, rf, ["test", "recent"], "test")
        hypotheses(b, eq, rf, "test")
        hypotheses(b, eq, rf, "recent")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dev")
