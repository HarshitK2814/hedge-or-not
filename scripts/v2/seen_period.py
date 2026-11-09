"""P6 v2 Task 6: seen-period re-run (2017-01..last complete month) and tearsheets, plus the replication check against the
live hedged fund. EVERY 2017-2026 number is 'seen period (v1 reported it)'; it is descriptive, not out-of-sample evidence.
Same books and conventions as scripts/v2/h1_h2.py: monthly USD returns of EFA + overlay, stress-aware costs (v1 x3 after VIX>30),
Sharpe on total monthly return (no risk-free subtracted), stationary bootstrap mean block 6, 5000 draws. The vol-capped target keeps
being chosen by the prereg walk-forward (anchored, 2-year blocks) with training data before each block.
Replication: monthly overlay net return (v1 costs, as in the v1 replication table) vs the live fund's hedge effect DDWM - DWM.
Run: python scripts/v2/seen_period.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import pandas as pd
from h1_h2 import ci_stat, cvar, diff_ci
from fxhedge import analysis as A
from fxhedge import model
from fxhedge.v2 import study
from fxhedge.v2.books import build
from fxhedge.v2.forward_log import complete_months
from fxhedge.v2.hedges import monthly
from qcore.bootstrap import bootstrap_stat, percentile_ci
from qengine.montecarlo import mc_summary
from qengine.tearsheet import write_tearsheet

ROOT = Path(__file__).resolve().parents[2]
TS = ROOT / "results" / "v2" / "tearsheets"
SEEN = study.SEEN
CHOICE = ("2006-01-01", "2016-12-31")
LABELS = ["unhedged", "static50", "static100", "v1_dynamic3", "mv60", "volcap_wf", "volcap_wf_guarded"]


def book_stats(name, H, ctx, window):
    r = study.month_returns(H, ctx)
    m = r["m"].loc[window[0]:window[1]]
    ov, dsl = r["ov"], slice(*window)
    hh = ov["hedge"].loc[dsl]
    return {"book": name, "window": f"{m.index[0].date()}..{m.index[-1].date()}", "n_months": int(len(m)),
            "ann_vol": ci_stat(m, study.ann_vol), "cvar95": ci_stat(m, cvar), "sharpe": ci_stat(m, study.sharpe_m),
            "mean_hedge_ratio": float(hh.mean()), "annual_cost_bp": float(ov["cost"].loc[dsl].mean() * 252 * 1e4)}, m, r


def main():
    ctx = study.context()
    last = ctx["efa_d"].index[-1]
    mm = complete_months(monthly(ctx["efa_d"]), last)
    lcm = mm.index[-1]                      # last complete month (labelled by its last trading day)
    SEEN_W = ("2017-01-01", str(lcm.date()))
    b = build(ctx, last_complete_month_end=lcm)
    TS.mkdir(parents=True, exist_ok=True)

    # consistency with h1_h2.json (same 2006-2016 vol-cap choices)
    h = json.load(open(study.TAB / "h1_h2.json"))
    old = [f["chosen_target"] for f in h["walk_forward_literal"]]
    new = [f["chosen_target"] for f in b["_wf"]["folds"][:len(old)]]
    assert old == new, (old, new)
    first_mv = b["mv60"].dropna(how="all").index[0]

    rows, ms, rs = [], {}, {}
    for k in LABELS:
        for wname, w in (("choice", CHOICE), ("seen", SEEN_W)):
            start = max(pd.Timestamp(w[0]), first_mv) if (k == "mv60" and wname == "choice") else pd.Timestamp(w[0])
            st, m, r = book_stats(k, b[k], ctx, (start, w[1]))
            st["period"] = "2006-2016 (choice window)" if wname == "choice" else f"2017-2026 - {SEEN}"
            rows.append(st)
            ms[(k, wname)] = m
            rs[(k, wname)] = r
    chk = next(r for r in rows if r["book"] == "volcap_wf" and r["period"].startswith("2006"))
    assert abs(chk["cvar95"][0] - h["rules"]["volcap_wf_literal"]["cvar95"][0]) < 1e-9

    def common(a, c, wname):
        i = ms[(a, wname)].index.intersection(ms[(c, wname)].index)
        return ms[(a, wname)].loc[i], ms[(c, wname)].loc[i]
    sh = study.sharpe_m
    diffs = {}
    for lab, (a, c, f) in {"mv60_minus_static50_vol": ("mv60", "static50", study.ann_vol),
                           "volcap_wf_minus_static50_cvar95": ("volcap_wf", "static50", cvar),
                           "volcap_wf_guarded_minus_static50_cvar95": ("volcap_wf_guarded", "static50", cvar),
                           "v1_dynamic3_minus_static50_sharpe": ("v1_dynamic3", "static50", sh),
                           "mv60_minus_v1_dynamic3_vol": ("mv60", "v1_dynamic3", study.ann_vol),
                           "volcap_wf_minus_v1_dynamic3_cvar95": ("volcap_wf", "v1_dynamic3", cvar),
                           "mv60_minus_static100_vol": ("mv60", "static100", study.ann_vol)}.items():
        x, y = common(a, c, "seen")
        diffs[lab] = diff_ci(x, y, f)

    # ---------------- replication vs live hedged fund (v1 costs, as v1)
    inp, etf = ctx["inp"], ctx["inp"]["etf"]
    dd = etf["DDWM"].dropna()
    gap = (A.monthly(dd) - A.monthly(etf["DWM"].reindex(dd.index))).dropna().loc[:lcm]
    wins = {"2017-2024 (v1 locked-test window)": ("2017-01-01", "2024-12-31"),
            "2025-01..last complete month": ("2025-01-01", str(lcm.date())),
            "all overlap (2016-02..last complete month)": ("2016-01-01", str(lcm.date()))}
    rep = []
    for k in ("static100", "static50", "v1_dynamic3", "mv60", "volcap_wf"):
        net = model.overlay(b[k], inp)["net"].reindex(dd.index).fillna(0.0)
        ours = A.monthly(net)
        for wn, (a0, a1) in wins.items():
            df = pd.concat([ours, gap], axis=1, keys=["ours", "fund"]).dropna().loc[a0:a1]
            if len(df) < 12:
                continue
            lo, hi = percentile_ci(bootstrap_stat(df, lambda d: d["ours"].corr(d["fund"]), n_boot=2000, mean_block=6, seed=0))
            rep.append({"book": k, "window": wn, "n_months": len(df), "corr": float(df.corr().iloc[0, 1]), "corr_ci95": [lo, hi],
                        "tracking_error_ann": float((df["ours"] - df["fund"]).std() * np.sqrt(12))})

    # ---------------- tearsheets (daily EFA + overlay, stress-aware costs)
    book_notes = {"static50": "Book: static 50% hedge.", "v1_dynamic3": "Book: v1 three-signal vote (rate, momentum, value).",
                  "mv60": "Book: rolling 60-month minimum-variance hedge (first ratio 2006-09).",
                  "volcap_wf": "Book: vol-capped hedge 1 - target / GJR-GARCH vol, target by walk-forward (literal GARCH; the CHF forecast explodes, so CHF is fully hedged at times)."}
    for k in book_notes:
        r = rs[(k, "choice")]
        for wname, w in (("choice_2006_2016", CHOICE), ("seen_2017_2026", SEEN_W)):
            s0 = max(pd.Timestamp(w[0]), first_mv) if (k == "mv60" and wname.startswith("choice")) else pd.Timestamp(w[0])
            eq = r["eq_daily"].loc[s0:w[1]]
            cst = r["ov"]["cost"].loc[eq.index].to_frame("overlay_cost")
            notes = ["Signals computed at the last business day of month m from data up to that day; hedge held from the next business day (monthly rebalance).",
                     "Returns: daily EFA (unhedged USD total return) plus the currency overlay on a 9-currency basket, net of costs.",
                     "Costs: v1 per-currency trade and roll bp, x3 on days after the previous VIX close was above 30 (stress rule). Roll is monthly. No capacity or market-impact model: overlay on notional exposure.",
                     "Data: Yahoo Finance ETF closes, FRED rates and spot, World Bank PPP; forward points proxied by interbank rate differentials.",
                     book_notes[k], "Sharpe CIs: stationary bootstrap. Research artifact, not investment advice."]
            ttl = f"P6 v2 {k} {w[0][:4]}-{w[1][:4]}" + (f" - {SEEN}" if wname.startswith("seen") else " (choice window)")
            if wname.startswith("seen"):
                notes.insert(0, f"{SEEN}: v1 already reported 2017-2026; descriptive, not out-of-sample evidence.")
            write_tearsheet(eq, TS / f"{k}_{wname}.html", ttl, costs=cst, mc=mc_summary(eq, n_paths=2000), notes=notes)

    out = {"seen_window": [SEEN_W[0], SEEN_W[1]], "label": SEEN, "last_data_date": str(last.date()),
           "sharpe_convention": "total monthly return, no risk-free subtracted (as h1_h2.json)",
           "costs": "stress-aware (v1 x3 after VIX>30), no capacity model",
           "rows": rows, "diffs_seen": diffs, "replication_vs_fund": rep,
           "volcap_walk_forward": b["_wf"]["folds"], "volcap_guarded_walk_forward": b["_wf_guarded"]["folds"],
           "volcap_last_target": b["_wf"]["last_target"], "mv_first_ratio_date": str(first_mv.date()),
           "vol_forecast_cache_ends": str(b["_vol_end"].date())}
    (study.TAB / "seen_period.json").write_text(json.dumps(out, indent=1, default=float))
    flat = [{"book": r["book"], "period": r["period"], "window": r["window"], "n_months": r["n_months"],
             "vol": r["ann_vol"][0], "vol_lo": r["ann_vol"][1], "vol_hi": r["ann_vol"][2],
             "cvar95": r["cvar95"][0], "cvar_lo": r["cvar95"][1], "cvar_hi": r["cvar95"][2],
             "sharpe": r["sharpe"][0], "sharpe_lo": r["sharpe"][1], "sharpe_hi": r["sharpe"][2],
             "mean_hedge_ratio": r["mean_hedge_ratio"], "annual_cost_bp": r["annual_cost_bp"]} for r in rows]
    pd.DataFrame(flat).to_csv(study.TAB / "seen_period.csv", index=False)
    pd.DataFrame([{**r, "corr_lo": r["corr_ci95"][0], "corr_hi": r["corr_ci95"][1]} for r in rep]).drop(columns="corr_ci95").to_csv(
        study.TAB / "replication_fund.csv", index=False)
    print(pd.DataFrame(flat).round(3).to_string())
    print(pd.DataFrame(rep).round(3).to_string())
    print(json.dumps(diffs, indent=1, default=float)[:2500])
    print("wf seen:", b["_wf"]["folds"][-6:])


if __name__ == "__main__":
    main()
