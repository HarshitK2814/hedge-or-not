"""P6 v2 Task 4: descriptive items D1-D9 (no hypothesis). Pre-registration v2 (hash b2e9a0e506a9, FROZEN).
Windows: A = 2001-09..2016-12 (choice window, v1 rules); B = 2006-10..2016-12 (every rule incl. MV, the vol-capped walk-forward);
S = 2017-01..2026-10 labelled `seen period (v1 reported it)` (v1 rules, static, max-carry, MV; the vol-capped rule has no walk-forward past 2016, so it is skipped there).
Returns = monthly USD returns of EFA + overlay; Sharpe is on excess over 3m T-bill (DTB3). Bootstrap: stationary, mean block 6, 2000 draws.
Run (needs results/v2/runs/H_*.parquet from h1_h2.py): PREREG_HASH=b2e9a0e506a9 python scripts/v2/descriptive.py [d3]"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from fxhedge import data, macro, model
from fxhedge.v2 import study
from fxhedge.v2.desc import basis_cost, bond_sleeve, max_carry_ratios, usd_regime
from fxhedge.v2.hedges import monthly
from qcore.bootstrap import bootstrap_stat, percentile_ci
from qcore.risk import christoffersen_ind, garch_vol_forecast, kupiec_pof
from qcore.splits import file_hash

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "preregistration_v2.md"
TAB, RUNS = study.TAB, study.RUNS
WIN = {"A_2001-09..2016-12": ("2001-09-01", "2016-12-31"), "B_2006-10..2016-12": ("2006-10-01", "2016-12-31"),
       f"S_2017-01..2026-10 [{study.SEEN}]": ("2017-01-01", "2026-12-31")}
NB = 2000


def sh(m) -> float:
    m = pd.Series(np.asarray(m, dtype=float))
    return float(m.mean() / m.std(ddof=1) * np.sqrt(12))


def sh_ci(m: pd.Series) -> list[float]:
    d = bootstrap_stat(m, sh, n_boot=NB, mean_block=6)
    lo, hi = percentile_ci(d)
    return [sh(m), lo, hi]


def diff_ci(a: pd.Series, b: pd.Series, f=sh) -> list[float]:
    D = pd.concat([a, b], axis=1, keys=["a", "b"]).dropna()
    d = bootstrap_stat(D, lambda x: f(x["a"]) - f(x["b"]), n_boot=NB, mean_block=6)
    lo, hi = percentile_ci(d)
    return [float(f(D["a"]) - f(D["b"])), lo, hi, int(len(D))]


def rule_books(ctx: dict, b: dict) -> dict[str, pd.DataFrame]:
    H = {"unhedged": b["unhedged"]["ratios"], "static50": b["static50"]["ratios"], "static100": b["static100"]["ratios"],
         "v1_dynamic3": b["dynamic3"]["ratios"], "v1_extended5": b["extended5"]["ratios"], "max_carry_D5": max_carry_ratios(ctx["inp"]),
         "mv60": pd.read_parquet(RUNS / "H_mv60_daily.parquet"), "volcap_wf": pd.read_parquet(RUNS / "H_volcap_wf_literal_daily.parquet")}
    return H


def cut(m: pd.Series, w: tuple[str, str], name: str) -> pd.Series:
    s = m.loc[w[0]:w[1]]
    if name in ("mv60", "volcap_wf"):            # no ratio before the first full estimate / outside the walk-forward
        first = {"mv60": "2006-10-01", "volcap_wf": "2006-01-01"}[name]
        s = s.loc[first:]
        if name == "volcap_wf":
            s = s.loc[:"2016-12-31"]
    return s


def main() -> None:
    assert os.environ.get("PREREG_HASH") == file_hash(PREREG) == "b2e9a0e506a9", "prereg hash mismatch"
    ctx = study.context()
    X, w, inp = ctx["X"], ctx["w"], ctx["inp"]
    b = model.books(inp)
    Hs = rule_books(ctx, b)
    rf_d = pd.read_parquet(data.RAW / "dtb3.parquet")["DTB3"]
    rf_m = monthly(rf_d.reindex(X.index).ffill().fillna(0.0).loc["2001-09-01":])
    out: dict = {"prereg_hash": file_hash(PREREG), "windows": {k: list(v) for k, v in WIN.items()},
                 "note_sharpe": "Sharpe on excess of 3m T-bill; ann = sqrt(12) x monthly"}

    # ---------------------------------------------------------------- D1 cost sensitivity
    regimes = {"v1_costs": None, "stress_x3_vix30": "stress", "2x_stress": 2 * ctx["mult"]}
    runs: dict[str, dict] = {}
    for rn, cm in regimes.items():
        runs[rn] = {k: study.month_returns(H, ctx, cost_mult=cm) for k, H in Hs.items()}
    d1 = []
    for rn in regimes:
        for k in Hs:
            for wn, wb in WIN.items():
                m = cut(runs[rn][k]["m"], wb, k)
                if "S_" in wn and k == "volcap_wf":
                    continue
                if len(m) < 24:
                    continue
                ex = m - rf_m.reindex(m.index).fillna(0.0)
                ov = runs[rn][k]["ov"]["cost"]
                d1.append({"regime": rn, "rule": k, "window": wn, "n_months": int(len(m)), "net_ret_ann": float(m.mean() * 12),
                           "vol_ann": float(m.std(ddof=1) * np.sqrt(12)), "sharpe_excess": sh_ci(ex),
                           "overlay_cost_bp_yr": float(ov.loc[wb[0]:wb[1]].mean() * 252 * 1e4)})
    out["D1_cost_sensitivity"] = d1
    base = runs["stress_x3_vix30"]

    # ---------------------------------------------------------------- D2 regret
    d2 = []
    for k in Hs:
        for wn, wb in WIN.items():
            if "B_" in wn:
                continue
            if "S_" in wn and k == "volcap_wf":
                continue
            m = cut(base[k]["m"], wb, k)
            if len(m) < 24:
                continue
            u, f = cut(base["unhedged"]["m"], wb, "x"), cut(base["static100"]["m"], wb, "x")
            idx = m.index
            d2.append({"rule": k, "window": wn, "n_months": int(len(idx)), "share_beats_unhedged": float((m > u.reindex(idx)).mean()),
                       "share_beats_fully_hedged": float((m > f.reindex(idx)).mean())})
    out["D2_regret"] = d2

    # ---------------------------------------------------------------- D4 benchmark set (hedge effect = overlay net return)
    ovm = {k: monthly(base[k]["ov"]["net"].reindex(ctx["efa_d"].index).fillna(0.0)) for k in Hs}
    etf = inp["etf"]
    fund = {"live_fund_DDWM_minus_DWM": monthly(etf["DDWM"].dropna()) - monthly(etf["DWM"].reindex(etf["DDWM"].dropna().index)),
            "HEFA_minus_EFA (100% hedged)": monthly(etf["HEFA"].dropna()) - monthly(etf["EFA"].reindex(etf["HEFA"].dropna().index))}
    d4 = []
    for wn, wb in WIN.items():
        for k, s in {**{k: ovm[k] for k in Hs}, **fund}.items():
            if k == "volcap_wf" and "S_" in wn:
                continue
            m = cut(s, wb, k) if k in Hs else s.loc[wb[0]:wb[1]]
            if len(m) < 24:
                continue
            row = {"window": wn, "series": k, "n_months": int(len(m)), "hedge_effect_ann": float(m.mean() * 12)}
            for st in ("unhedged", "static50", "static100"):
                dd = diff_ci(m, ovm[st], f=lambda x: float(np.mean(x)) * 12)
                row[f"minus_{st}"] = dd[:3]
            d4.append(row)
    out["D4_benchmark_set"] = d4
    out["D4_note"] = ("hedge effect = monthly overlay return (live funds: hedged ETF minus its unhedged twin). DDWM starts 2016-02 and HEFA 2014-02, so "
                      "fund rows fall almost entirely in the seen period. Static ratios are never picked from a seen period.")

    # ---------------------------------------------------------------- D5 Max-Carry baseline
    d5 = []
    for wn, wb in WIN.items():
        a = cut(base["v1_dynamic3"]["m"], wb, "x") - rf_m.reindex(cut(base["v1_dynamic3"]["m"], wb, "x").index).fillna(0.0)
        c = cut(base["max_carry_D5"]["m"], wb, "x") - rf_m.reindex(cut(base["max_carry_D5"]["m"], wb, "x").index).fillna(0.0)
        if len(a) < 24:
            continue
        d5.append({"window": wn, "dynamic3_sharpe": sh_ci(a), "max_carry_sharpe": sh_ci(c), "dynamic3_minus_max_carry": diff_ci(a, c),
                   "beats_baseline_with_ci_excluding_0": bool(diff_ci(a, c)[1] > 0)})
    out["D5_max_carry"] = d5
    out["D5_note"] = "Max-Carry equals the v1 rate-signal-only book (hedge when the US 3m rate exceeds the currency's). Baseline, not a test."

    # ---------------------------------------------------------------- D6 CIP basis sensitivity
    d6 = []
    for bp in (0, 10, 25):
        for k, H in Hs.items():
            r = base[k]
            adj = r["eq_daily"] - basis_cost(r["ov"]["hedge"].reindex(r["eq_daily"].index).fillna(0.0), bp)
            m = cut(monthly(adj), WIN["B_2006-10..2016-12"], k)
            if k == "volcap_wf":
                m = m.loc["2006-10-01":]
            ex = m - rf_m.reindex(m.index).fillna(0.0)
            d6.append({"basis_bp_per_year": bp, "rule": k, "window": "B", "net_ret_ann": float(m.mean() * 12), "sharpe_excess": sh_ci(ex)})
    out["D6_cip_basis"] = d6
    out["D6_note"] = ("v1 uses 3m OECD rates for 1m forwards. Bound, not a measurement: extra bp/yr charged on the hedged notional "
                      "(free forward-point data not available).")

    # ---------------------------------------------------------------- D7 regimes
    spot_b = (inp["S"].ffill(limit=5).pct_change(fill_method=None)[inp["ccys"]].mul(w, axis=1).sum(axis=1)).reindex(X.index).fillna(0.0)
    reg = usd_regime(monthly(spot_b.loc["2001-01-01":]))
    d7 = []
    for wn, wb in WIN.items():
        if "B_" in wn:
            continue
        for k in Hs:
            if k == "volcap_wf" and "S_" in wn:
                continue
            m = cut(base[k]["m"], wb, k)
            for rg in ("usd_rising", "usd_falling"):
                x = m[reg.reindex(m.index) == rg]
                ex = x - rf_m.reindex(x.index).fillna(0.0)
                if len(x) >= 12:
                    d7.append({"rule": k, "window": wn, "regime": rg, "n_months": int(len(x)), "ann_net_ret": float(x.mean() * 12),
                               "ann_vol": float(x.std(ddof=1) * np.sqrt(12)), "mean_monthly_excess_t": float(ex.mean() / ex.std(ddof=1) * np.sqrt(len(ex)))})
    out["D7_regimes"] = d7

    # ---------------------------------------------------------------- D8 synthetic bond sleeve
    bonds = macro.bond_excess_returns()["UST10"].reindex(X.index)
    bond_tot = (bonds + rf_d.reindex(X.index).ffill().fillna(0.0)).fillna(0.0)
    Xb = X.mul(w, axis=1).sum(axis=1)
    d8 = []
    sl = slice("2001-09-01", "2016-12-31")
    for h in (0.0, 0.5, 1.0):
        ov = model.overlay(model.static(X.index, inp["ccys"], h), inp)
        sleeve = bond_sleeve(bond_tot, spot_b, Xb, h) - ov["cost"]
        eq = ctx["efa_d"] + ov["net"].reindex(ctx["efa_d"].index).fillna(0.0)
        for nm, s in (("synthetic_bond_sleeve", sleeve), ("equity_EFA", eq)):
            m = monthly(s.loc[sl])
            ex = m - rf_m.reindex(m.index).fillna(0.0)
            d8.append({"asset": nm, "hedge_ratio": h, "n_months": int(len(m)), "ann_vol": float(m.std(ddof=1) * np.sqrt(12)),
                       "ann_ret": float(m.mean() * 12), "sharpe_excess": sh_ci(ex)})
    for nm in ("synthetic_bond_sleeve", "equity_EFA"):
        v = {r["hedge_ratio"]: r["ann_vol"] for r in d8 if r["asset"] == nm}
        out[f"D8_vol_reduction_100pct_hedge_{nm}"] = float(1 - v[1.0] / v[0.0])
    out["D8_bond_sleeve"] = d8
    out["D8_construction"] = ("Synthetic: foreign government bond = US 10y constant-maturity par-bond total return (FRED DGS10, macro.bond_excess_returns + 3m T-bill) "
                              "used as the local-currency bond return; USD return = local bond + basket spot move - h x basket forward excess return - overlay cost. "
                              "No foreign yield curves are free; local-bond/currency correlation is therefore not a measurement of any real bond market. Descriptive only.")

    # ---------------------------------------------------------------- D9 roll volume
    d9 = []
    for k, H in Hs.items():
        r = base[k]
        Hf = H.reindex(X.index).fillna(0.0)
        dH = Hf.diff().abs().mul(w, axis=1).sum(axis=1)
        hedge = r["ov"]["hedge"]
        for wn, wb in WIN.items():
            if "B_" in wn or (k == "volcap_wf" and "S_" in wn):
                continue
            s0, s1 = wb
            if k == "mv60":
                s0 = max(s0, "2006-10-01")
            if k == "volcap_wf":
                s0, s1 = max(s0, "2006-01-01"), min(s1, "2016-12-31")
            h = hedge.loc[s0:s1]
            nm = max(len(h) / 21.0, 1)
            d9.append({"rule": k, "window": wn, "avg_forward_notional_share_of_portfolio": float(h.mean()),
                       "monthly_turnover_share": float(dH.loc[s0:s1].sum() / nm)})
    out["D9_roll_volume"] = d9
    (TAB / "descriptive.json").write_text(json.dumps(out, indent=1, default=float))
    print("D1-D2, D4-D9 saved")

    if len(sys.argv) > 1 and sys.argv[1] == "d3":
        d3(ctx, base, Hs)


def d3(ctx: dict, base: dict, Hs: dict) -> None:
    """99% one-month VaR (monthly hits) and, as a more powerful secondary, 99% one-day VaR hits, from a GJR-GARCH(1,1,1)-t
    forecast on the rule's DAILY hedged return. 1-month VaR approximated as 2.326 x sigma_1d x sqrt(21) (normal quantile, iid scaling)."""
    res = []
    for k in ("unhedged", "static50", "static100", "v1_dynamic3", "mv60", "volcap_wf"):
        p = RUNS / f"garch_{k}.parquet"
        eq = base[k]["eq_daily"]
        if p.exists():
            sig = pd.read_parquet(p)["sig"]
        else:
            sig = garch_vol_forecast(eq.loc["2001-09-01":], refit_every=21)
            sig.to_frame("sig").to_parquet(p)
        bad_n = int((sig > 0.05).sum() + (~np.isfinite(sig.dropna())).sum())   # > 5% daily vol is not credible for hedged EFA
        sig_g = sig.where(sig <= 0.05)
        for variant, s in (("literal", sig), ("guarded_sensitivity", sig_g.ffill())):
            for wn, (a, z) in (("choice 2004-09..2016-12", ("2004-09-01", "2016-12-31")), (f"S [{study.SEEN}]", ("2017-01-01", "2026-12-31"))):
                if "S [" in wn and k == "volcap_wf":
                    continue
                if k == "mv60":
                    a = max(a, "2006-10-01")
                if k == "volcap_wf":
                    a = max(a, "2006-01-01")
                # daily
                loss_d = -eq
                var_d = (2.326 * s).shift(1)
                dd = pd.concat([loss_d.rename("l"), var_d.rename("v")], axis=1).loc[a:z].dropna()
                hd = dd["l"] > dd["v"]
                kd, cd = kupiec_pof(hd, 0.01), christoffersen_ind(hd)
                # monthly: VaR set at month-end m for month m+1
                me = monthly(eq).index
                r_m = monthly(eq)
                var_m = (2.326 * s.reindex(me) * np.sqrt(21)).shift(1)
                mm = pd.concat([(-r_m).rename("l"), var_m.rename("v")], axis=1).loc[a:z].dropna()
                hm = mm["l"] > mm["v"]
                km, cm = (kupiec_pof(hm, 0.01), christoffersen_ind(hm)) if len(hm) > 5 else (None, None)
                res.append({"rule": k, "variant": variant, "window": wn, "garch_days_above_5pct_daily_vol": bad_n,
                            "monthly": None if km is None else {"n": km["n"], "breaches": km["breaches"], "kupiec_p": km["p"],
                                                                "christoffersen_p": cm["p"], "mean_var99_pct": float(mm["v"].mean() * 100)},
                            "daily_secondary": {"n": kd["n"], "breaches": kd["breaches"], "breach_rate": kd["breaches"] / kd["n"],
                                                "kupiec_p": kd["p"], "christoffersen_p": cd["p"]}})
    (TAB / "d3_var_backtest.json").write_text(json.dumps({"approximation": "VaR_1m = 2.326 x sigma_1d(GJR-GARCH-t, made at month-end) x sqrt(21); normal quantile; "
                                                          "monthly backtest has few observations (~150), so Kupiec has low power; daily 1-day VaR reported as secondary",
                                                          "rows": res}, indent=1, default=float))
    print("D3 saved")


if __name__ == "__main__":
    main()
