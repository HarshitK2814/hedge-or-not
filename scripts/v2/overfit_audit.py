"""P6 v2 Task 4 (H3): overfitting audit of the v1 vote rule. Pre-registration v2 (hash b2e9a0e506a9, FROZEN).
Family = every non-empty subset of the five v1 signals (31) + static 0/50/100 = 34 configs, 2001-09..2016-12, v1 costs.
Returns = monthly USD returns of EFA + overlay (prereg "Returns" definition; a pure-overlay variant is a labelled sensitivity,
because static 0% overlay is identically zero). PBO by CSCV with 10 blocks (monthly data: 184 points). Deflated Sharpe of
v1 `dynamic3` with n_trials = 34 and sr_var = variance of the 34 configs' per-month Sharpes (literal; configs are highly
correlated, so a smaller effective n would raise DSR; not applied).
H3 supported if PBO < 0.5 AND deflated Sharpe > 0.90.
Run: PREREG_HASH=b2e9a0e506a9 python scripts/v2/overfit_audit.py"""

from __future__ import annotations

import json
import os
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from fxhedge import model
from fxhedge.v2 import study
from fxhedge.v2.hedges import monthly
from qcore.bootstrap import bootstrap_stat, percentile_ci
from qcore.splits import file_hash
from qcore.validation import deflated_sharpe, expected_max_sharpe, pbo_cscv, probabilistic_sharpe

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "preregistration_v2.md"
START, END = "2001-09-01", "2016-12-31"


def family_ratios(inp: dict) -> dict[str, pd.DataFrame]:
    v = model.votes(inp)
    idx, ccys = inp["X"].index, inp["ccys"]
    fam = {}
    for k in range(1, len(model.EXTENDED) + 1):
        for sub in combinations(model.EXTENDED, k):
            fam["+".join(sub)] = model.hedge_ratios(v, sub)
    for r in (0.0, 0.5, 1.0):
        fam[f"static{int(r * 100)}"] = model.static(idx, ccys, r)
    return fam


def run(ctx: dict, fam: dict, equity: bool) -> pd.DataFrame:
    cols = {}
    for k, H in fam.items():
        ov = model.overlay(H, ctx["inp"])["net"]
        d = ov.reindex(ctx["efa_d"].index).fillna(0.0)
        d = ctx["efa_d"] + d if equity else d
        cols[k] = monthly(d).loc[START:END]
    return pd.DataFrame(cols)


def sh(x) -> float:
    x = np.asarray(x, dtype=float)
    return float(x.mean() / x.std(ddof=1) * np.sqrt(12))


def audit(M: pd.DataFrame, label: str, target: str = "rate+momentum+value") -> dict:
    ok = M.std() > 0
    Mx = M.loc[:, ok]                                    # PBO needs a non-degenerate column
    pbo = pbo_cscv(Mx, n_blocks=10)
    r = M[target]
    per = (M.mean() / M.std(ddof=1))[ok]                 # per-month Sharpe of each config
    sr_var = float(per.var(ddof=1))
    n_trials = 34
    emax = expected_max_sharpe(n_trials, sr_var)
    dsr = deflated_sharpe(r.to_numpy(), n_trials=n_trials, sr_var=sr_var)
    d = bootstrap_stat(r, lambda s: sh(s), n_boot=5000, mean_block=6)
    lo, hi = percentile_ci(d)
    best = M.apply(sh).sort_values(ascending=False)
    return {"label": label, "n_configs_in_family": int(M.shape[1]), "n_configs_in_pbo": int(Mx.shape[1]), "n_months": int(len(M)),
            "pbo": pbo["pbo"], "n_cscv_combinations": pbo["n_combinations"],
            "dynamic3_sharpe_ann_ci95": [sh(r), lo, hi], "dynamic3_per_month_sharpe": float(r.mean() / r.std(ddof=1)),
            "sr_var_per_month": sr_var, "expected_max_per_month_sharpe_null": emax,
            "expected_max_ann_sharpe_null": float(emax * np.sqrt(12)),
            "deflated_sharpe": dsr, "psr_vs_0": probabilistic_sharpe(r.to_numpy(), 0.0),
            "best_config": best.index[0], "best_ann_sharpe": float(best.iloc[0]),
            "dynamic3_rank_of_34": int(list(best.index).index(target) + 1),
            "n_configs_positive_sharpe": int((best > 0).sum()),
            "top5": {k: float(v) for k, v in best.head(5).items()},
            "h3_pbo_pass": bool(pbo["pbo"] < 0.5), "h3_dsr_pass": bool(dsr > 0.90),
            "h3_supported": bool(pbo["pbo"] < 0.5 and dsr > 0.90)}


def main() -> None:
    assert os.environ.get("PREREG_HASH") == file_hash(PREREG) == "b2e9a0e506a9", "prereg hash mismatch"
    ctx = study.context()
    fam = family_ratios(ctx["inp"])
    assert len(fam) == 34
    Me = run(ctx, fam, equity=True)
    Mo = run(ctx, fam, equity=False)
    out = {"prereg_hash": file_hash(PREREG), "window": [START, END], "costs": "v1 costs (no stress multiplier), per plan Task 4",
           "note": "monthly data: 184 points, PBO uses 10 CSCV blocks (252 combinations)",
           "primary_efa_plus_overlay": audit(Me, "EFA + overlay (prereg Returns definition)"),
           "sensitivity_pure_overlay_excl_degenerate_static0": audit(Mo, "overlay only (static0 column is identically zero and is dropped from PBO; still counted in n_trials = 34)")}
    # sensitivity: effective-trial deflation (not prereg). Cluster count from the correlation matrix of the family.
    C = Me.corr().to_numpy()
    ev = np.linalg.eigvalsh(C)
    n_eff = float(ev.sum() ** 2 / (ev ** 2).sum())
    per = (Me.mean() / Me.std(ddof=1))
    r = Me["rate+momentum+value"]
    out["sensitivity_effective_trials"] = {"n_eff_participation_ratio": n_eff,
                                          "deflated_sharpe_with_n_eff": deflated_sharpe(r.to_numpy(), max(int(round(n_eff)), 2), float(per.var(ddof=1))),
                                          "note": "NOT the prereg rule; shows how much DSR depends on the literal n_trials = 34 / highly correlated family"}
    (study.TAB / "h3_overfit.json").write_text(json.dumps(out, indent=1, default=float))
    Me.to_csv(study.RUNS / "h3_family_monthly_equity.csv")
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
