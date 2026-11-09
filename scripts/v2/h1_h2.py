"""P6 v2 Task 3 (H1, H2). Pre-registration v2 (hash b2e9a0e506a9, FROZEN). Choices use data up to 2016-12 only.
Timing: ratios computed at the last business day of month m from data up to that day, applied from the next business day.
Returns: monthly USD returns of EFA + currency overlay, net of costs with the stress-aware rule (v1 costs x3 after VIX > 30).
H1: rolling 60-month minimum-variance hedge vs static 50%, hedged-portfolio volatility difference, stationary bootstrap
    (mean block 6 months, 5000 draws) 95% CI must exclude 0 (and be negative).
H2: vol-capped hedge clip(1 - target / GJR-GARCH vol, 0, 1), target in {4,6,8,10}% by walk-forward (anchored, 2-year test
    blocks from 2006, min trailing monthly CVaR(95%), plateau-smoothed), CVaR(95%) difference vs static 50%.
Run: PREREG_HASH=b2e9a0e506a9 python scripts/v2/h1_h2.py"""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxhedge import model
from fxhedge.v2 import study
from fxhedge.v2.hedges import monthly, mv_hedge, to_daily, vol_capped_hedge
from qcore.bootstrap import bootstrap_stat, percentile_ci
from qcore.metrics import var_cvar
from qcore.splits import file_hash
from qengine.lookahead import check_lookahead
from qengine.walkforward import plateau_select, wf_folds

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "preregistration_v2.md"
TARGETS = [0.04, 0.06, 0.08, 0.10]
N_BOOT = 5000
E0, E1 = study.EVAL


def cvar(m: pd.Series) -> float:
    return var_cvar(m, 0.95)[1]


def sharpe(m: pd.Series) -> float:
    return study.sharpe_m(m)


def ci_stat(m: pd.Series, f, n_boot: int = N_BOOT) -> list[float]:
    d = bootstrap_stat(m, lambda s: f(pd.Series(np.asarray(s))), n_boot=n_boot, mean_block=6)
    lo, hi = percentile_ci(d)
    return [float(f(m)), lo, hi]


def diff_ci(a: pd.Series, b: pd.Series, f, n_boot: int = N_BOOT) -> dict:
    D = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    d = bootstrap_stat(D, lambda x: f(x["a"]) - f(x["b"]), n_boot=n_boot, mean_block=6)
    lo, hi = percentile_ci(d)
    return {"diff": float(f(D["a"]) - f(D["b"])), "ci95": [lo, hi], "n_months": int(len(D)),
            "ci_excludes_0": bool(lo > 0 or hi < 0)}


def walk_forward_target(vol_m: pd.DataFrame, ctx: dict, label: str) -> dict:
    """vol_m: month-end annualised vol forecasts (NaN where unavailable). Returns stitched daily H, chosen targets."""
    X = ctx["X"]
    cand_H, cand_m = {}, {}
    for t in TARGETS:
        Hd = to_daily(vol_capped_hedge(vol_m, t), X.index)
        cand_H[t] = Hd
        cand_m[t] = study.month_returns(Hd, ctx)["m"]
    avail_from = vol_m.dropna().index[0]                       # first month-end with every currency's forecast
    folds = wf_folds(X.loc[:E1].index, 2006, 2, 2016, anchored=True)
    pieces, rows = [], []
    for tr0, tr1, te0, te1 in folds:
        tr_months = cand_m[TARGETS[0]].loc[max(pd.Timestamp(tr0), avail_from) + pd.Timedelta(days=1):tr1].index
        scores = np.array([-cvar(cand_m[t].loc[tr_months]) for t in TARGETS])
        best = plateau_select(scores)[0]
        rows.append({"fold_test": f"{te0.date()}..{te1.date()}", "chosen_target": TARGETS[best], "n_train_months": len(tr_months),
                     "train_cvar95": {str(t): float(-s) for t, s in zip(TARGETS, scores)}})
        pieces.append(cand_H[TARGETS[best]].loc[te0:te1])
    H = pd.concat(pieces)
    H = H.reindex(X.index)
    return {"H": H, "folds": rows, "cand_m": cand_m, "label": label}


def rule_stats(name: str, Hd: pd.DataFrame, ctx: dict, window=(E0, E1)) -> dict:
    r = study.month_returns(Hd, ctx)
    m = r["m"].loc[window[0]:window[1]]
    ov = r["ov"]
    dsl = slice(window[0], window[1])
    H = ov["hedge"].loc[dsl]
    Hf = Hd.reindex(ctx["X"].index).fillna(0.0)
    w = ctx["w"]
    dH = (Hf.diff().abs().mul(w, axis=1).sum(axis=1)).loc[dsl]
    return {"name": name, "n_months": int(len(m)),
            "ann_vol": ci_stat(m, study.ann_vol), "cvar95": ci_stat(m, cvar), "sharpe": ci_stat(m, sharpe),
            "mean_hedge_ratio": float(H.mean()), "turnover_per_month": float(dH.sum() / max(len(m), 1)),
            "annual_cost_bp": float(ov["cost"].loc[dsl].mean() * 252 * 1e4),
            "avg_monthly_forward_notional_share": float(H.mean())}, m


def main() -> None:
    assert os.environ.get("PREREG_HASH") == file_hash(PREREG) == "b2e9a0e506a9", "prereg hash mismatch"
    ctx = study.context()
    X, w, efa_d = ctx["X"], ctx["w"], ctx["efa_d"]
    TAB, FIG = study.TAB, study.FIG
    inp, b = ctx["inp"], model.books(ctx["inp"])

    # ------------------------------------------------------------------ H1
    Xm = monthly(X.loc["2001-09-01":])
    efa_m = monthly(efa_d.loc["2001-09-01":])
    Xm = Xm.loc[efa_m.index]
    Hm_mv = mv_hedge(efa_m, Xm, w, window=60)
    check_lookahead(lambda D: mv_hedge(D["efa"], D[list(Xm.columns)], w), pd.concat([efa_m.rename("efa"), Xm], axis=1), cut=100)
    H_mv = to_daily(Hm_mv, X.index)
    first_mv = Hm_mv.dropna().index[0]
    H_s50 = b["static50"]["ratios"]
    books = {"unhedged": b["unhedged"]["ratios"], "static50": H_s50, "static100": b["static100"]["ratios"],
             "v1_dynamic3": b["dynamic3"]["ratios"], "mv60": H_mv}
    res, ms = {}, {}
    for k, H in books.items():
        res[k], ms[k] = rule_stats(k, H, ctx)

    # H1 on the common sample (months where the MV ratio is available): primary reading
    first_applied = H_mv.dropna(how="all").index[0]
    common = ms["mv60"].loc[first_applied:E1].index
    common = common[common >= pd.Timestamp(E0)]
    h1 = diff_ci(ms["mv60"].loc[common], ms["static50"].loc[common], study.ann_vol)
    h1["window"] = f"{common[0].date()}..{common[-1].date()} (first month with a full 60-month MV estimate; EFA starts 2001-08)"
    h1["vol_mv"] = study.ann_vol(ms["mv60"].loc[common]); h1["vol_static50"] = study.ann_vol(ms["static50"].loc[common])
    h1["supported"] = bool(h1["ci_excludes_0"] and h1["diff"] < 0)
    # sensitivity (not in prereg): static 50% before the first MV month, so the window is the full 2006-01..2016-12
    H_mv_fb = H_mv.where(H_mv.notna().any(axis=1), 0.5).copy()
    H_mv_fb.loc[:first_applied - pd.Timedelta(days=1)] = 0.5
    mfb = study.month_returns(H_mv_fb, ctx)["m"].loc[E0:E1]
    h1_sens_fb = diff_ci(mfb, ms["static50"], study.ann_vol)
    # sensitivity: 36-month MV window (starts earlier)
    Hm36 = mv_hedge(efa_m, Xm, w, window=36)
    H36 = to_daily(Hm36, X.index)
    r36 = study.month_returns(H36, ctx)["m"]
    c36 = r36.loc[H36.dropna(how="all").index[0]:E1].index
    c36 = c36[c36 >= pd.Timestamp(E0)]
    h1_sens_36 = diff_ci(r36.loc[c36], ms["static50"].loc[c36], study.ann_vol)
    h1_sens_36["window"] = f"{c36[0].date()}..{c36[-1].date()}"

    # ------------------------------------------------------------------ H2
    g = study.fx_garch_vol(X)
    me = monthly(X.loc["2001-09-01":]).index
    g_m = g.reindex(me)
    gg, bad = study.guard_vol(g, X)
    gg_m = gg.reindex(me)
    insp = {"literal_min_max_ann_vol": [float(np.nanmin(g_m.to_numpy())), float(np.nanmax(g_m.to_numpy()))],
            "literal_nan_month_ends": int(g_m.loc[E0:E1].isna().sum().sum()),
            "n_daily_forecasts_rejected_by_guard": int(bad.sum().sum()),
            "n_daily_forecasts": int(g.notna().sum().sum()),
            "rejected_by_currency": {c: int(v) for c, v in bad.sum().items()}}
    lit = walk_forward_target(g_m, ctx, "literal GARCH")
    grd = walk_forward_target(gg_m, ctx, "guarded GARCH (sensitivity)")
    rv, mv_lit = rule_stats("volcap_wf_literal", lit["H"], ctx)
    res["volcap_wf_literal"], ms["volcap_wf_literal"] = rv, mv_lit
    rg, mg = rule_stats("volcap_wf_guarded", grd["H"], ctx)
    res["volcap_wf_guarded"], ms["volcap_wf_guarded"] = rg, mg
    fixed = {}
    for t in TARGETS:
        fixed[str(t)], _ = rule_stats(f"volcap_{t}", to_daily(vol_capped_hedge(g_m, t), X.index), ctx)
    h2 = diff_ci(ms["volcap_wf_literal"], ms["static50"], cvar)
    h2["cvar_volcap"] = cvar(ms["volcap_wf_literal"]); h2["cvar_static50"] = cvar(ms["static50"])
    h2["supported"] = bool(h2["ci_excludes_0"] and h2["diff"] < 0)
    h2["window"] = f"{E0}..{E1}"
    h2_g = diff_ci(ms["volcap_wf_guarded"], ms["static50"], cvar)
    h2_g["cvar_volcap"] = cvar(ms["volcap_wf_guarded"]); h2_g["supported"] = bool(h2_g["ci_excludes_0"] and h2_g["diff"] < 0)
    # vol-capped also vs v1 and vs unhedged (descriptive)
    desc_diffs = {"mv_minus_dynamic3_vol": diff_ci(ms["mv60"].loc[common], ms["v1_dynamic3"].loc[common], study.ann_vol),
                  "volcap_minus_dynamic3_cvar": diff_ci(ms["volcap_wf_literal"], ms["v1_dynamic3"], cvar),
                  "volcap_minus_static50_sharpe": diff_ci(ms["volcap_wf_literal"], ms["static50"], sharpe),
                  "mv_minus_static50_sharpe": diff_ci(ms["mv60"].loc[common], ms["static50"].loc[common], sharpe)}

    out = {"prereg_hash": file_hash(PREREG), "window": [E0, E1],
           "timing": "ratios from data to the last business day of month m, applied from the next business day (v1); returns EFA + overlay, "
                     "stress-aware costs (x3 after VIX>30), monthly",
           "costs": "v1 cost_bp/roll_bp x3 on days after VIX close > 30; no capacity assumption (overlay on notional exposure)",
           "H1": h1, "H1_sensitivity_static50_fallback_full_window": h1_sens_fb, "H1_sensitivity_window36": h1_sens_36,
           "mv_first_ratio_month_end": str(first_mv.date()),
           "H2": h2, "H2_guarded_sensitivity": h2_g, "garch_inspection": insp,
           "walk_forward_literal": lit["folds"], "walk_forward_guarded": grd["folds"],
           "rules": res, "fixed_targets_not_in_walk_forward": fixed, "descriptive_differences": desc_diffs,
           "lookahead": "qengine.lookahead.check_lookahead passed on mv_hedge (perturbation after cut 100)"}
    H_mv.to_parquet(study.RUNS / "H_mv60_daily.parquet"); lit["H"].to_parquet(study.RUNS / "H_volcap_wf_literal_daily.parquet")
    grd["H"].to_parquet(study.RUNS / "H_volcap_wf_guarded_daily.parquet")
    (TAB / "h1_h2.json").write_text(json.dumps(out, indent=1, default=float))

    # figures
    fig, ax = plt.subplots(figsize=(9, 4))
    for k, H in (("MV 60m", H_mv), ("vol-capped (WF)", lit["H"]), ("v1 dynamic3", books["v1_dynamic3"])):
        s = (H.mul(w, axis=1).sum(axis=1, min_count=1)).loc[E0:E1].resample("ME").last()
        ax.plot(s.index, s, label=k)
    ax.axhline(0.5, color="grey", lw=0.8, ls=":"); ax.set_ylabel("basket-weighted hedge ratio"); ax.legend(); ax.set_title("Hedge ratios, 2006-2016 (choice window)")
    fig.tight_layout(); fig.savefig(FIG / "hedge_ratios_v2.png", dpi=130); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4))
    names = ["unhedged", "static50", "static100", "v1_dynamic3", "mv60", "volcap_wf_literal"]
    vals = [res[n]["cvar95"] for n in names]
    ax.bar(range(len(names)), [v[0] * 100 for v in vals],
           yerr=[[ (v[0] - v[1]) * 100 for v in vals], [(v[2] - v[0]) * 100 for v in vals]], capsize=3)
    ax.set_xticks(range(len(names))); ax.set_xticklabels(names, rotation=20); ax.set_ylabel("monthly CVaR 95% (loss, %)")
    ax.set_title("CVaR(95%), 2006-2016 with bootstrap 95% CI")
    fig.tight_layout(); fig.savefig(FIG / "cvar_compare.png", dpi=130); plt.close(fig)
    print(json.dumps({k: out[k] for k in ("H1", "H1_sensitivity_static50_fallback_full_window", "H1_sensitivity_window36", "H2", "H2_guarded_sensitivity", "garch_inspection", "walk_forward_literal")}, indent=1, default=float))
    print(pd.DataFrame({k: {"vol": v["ann_vol"][0], "cvar": v["cvar95"][0], "sharpe": v["sharpe"][0], "H": v["mean_hedge_ratio"],
                            "turn/m": v["turnover_per_month"], "cost_bp/yr": v["annual_cost_bp"]} for k, v in res.items()}).T.round(4))


if __name__ == "__main__":
    main()
