"""Figures. Needs results/runs from `run.py test` (PREREG_HASH set)."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from fxhedge import analysis as A
from fxhedge import data

ROOT = Path(__file__).resolve().parents[1]
FIG, RUNS = ROOT / "results" / "figures", ROOT / "results" / "runs"
INK, MUTED, GRID = "#1f2328", "#6e7781", "#d8dee4"
BLUE, ORANGE, GREEN, GREY = "#2f6fdf", "#e07b00", "#1a7f37", "#8c959f"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": GRID, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "figure.dpi": 150})


def main():
    FIG.mkdir(parents=True, exist_ok=True)
    O = pd.read_parquet(RUNS / "overlay_daily.parquet")
    Hr = pd.read_parquet(RUNS / "hedge_ratio_daily.parquet")
    etf = data.etf_returns()

    # 1. Our hedge ratio vs the fund's implied hedge ratio (rolling 12-month regression of its hedge effect)
    idx = etf["DDWM"].dropna().index
    gap = (A.monthly(etf["DDWM"].dropna()) - A.monthly(etf["DWM"].reindex(idx))).dropna()
    full = A.monthly(O["static100"].reindex(idx).fillna(0.0)).reindex(gap.index)
    roll = (gap.rolling(12).cov(full) / full.rolling(12).var()).clip(-0.2, 1.2)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ax.plot(Hr["dynamic3"].loc["2002":], color=BLUE, lw=1.3, label="Our three-signal hedge ratio (basket average)")
    ax.plot(roll, color=INK, lw=1.4, ls="--", label="Fund's implied hedge ratio (rolling 12 m, from its NAV)")
    ax.axhline(0.5, color=GREY, lw=0.8, ls=":")
    ax.axvspan(pd.Timestamp("2017-01-01"), pd.Timestamp("2024-12-31"), color="#fff8c5", zorder=0)
    ax.text(pd.Timestamp("2017-02-01"), 1.12, "locked test", fontsize=8, color=MUTED)
    ax.set_ylim(-0.1, 1.2)
    ax.set_ylabel("Share of FX exposure hedged")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    ax.set_title("A 0-100% hedge rebuilt from a 497K prospectus", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "hedge_ratio.png")
    plt.close(fig)

    # 2. Replication scatter, test period
    ours = A.monthly(O["dynamic3"].reindex(idx).fillna(0.0))
    df = A.period(pd.concat([ours, gap], axis=1).dropna(), "test")
    df.columns = ["ours", "fund"]
    fig, ax = plt.subplots(figsize=(4.8, 4.2))
    ax.scatter(df["ours"] * 100, df["fund"] * 100, s=14, color=BLUE, alpha=0.75)
    lim = max(abs(df.to_numpy()).max() * 100, 1) * 1.1
    ax.plot([-lim, lim], [-lim, lim], color=GREY, lw=0.8)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_xlabel("Our overlay, % per month")
    ax.set_ylabel("Real fund minus unhedged twin, %")
    ax.set_title(f"Test 2017-24: corr {df.corr().iloc[0, 1]:.2f}", loc="left", color=INK, fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "replication.png")
    plt.close(fig)

    # 3. Growth of $1 of currency overlay (cumulative hedge P&L) for each rule
    fig, ax = plt.subplots(figsize=(9, 3.8))
    for k, c, lab in (("static100", GREY, "Static 100%"), ("static50", MUTED, "Static 50%"),
                      ("dynamic3", BLUE, "Dynamic 3-signal"), ("extended5", ORANGE, "Dynamic 5-signal (ours)")):
        ax.plot((1 + O[k].loc["2001-09":]).cumprod(), color=c, lw=1.4, label=lab)
    ax.axvspan(pd.Timestamp("2017-01-01"), pd.Timestamp("2024-12-31"), color="#fff8c5", zorder=0)
    ax.set_ylabel("Cumulative hedge P&L (growth of $1)")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right", ncol=2)
    ax.set_title("What hedging added to an unhedged EAFE investor, net of costs", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "overlay_pnl.png")
    plt.close(fig)

    # 4. Sharpe by rule: dev+val vs test
    rf = pd.read_parquet(data.RAW / "dtb3.parquet")["DTB3"]
    E = pd.read_parquet(RUNS / "hedged_equity_daily.parquet")
    rows = {}
    for k in ["unhedged", "static50", "static100", "dynamic3", "extended5", "only_rate", "only_momentum",
              "only_value", "only_volatility", "only_cross_asset"]:
        ex = A.monthly(E[k].dropna()) - A.monthly(rf.reindex(E[k].dropna().index).fillna(0.0))
        rows[k] = {"dev+val": A.sharpe_m(pd.concat([A.period(ex, "development"), A.period(ex, "validation")])),
                   "test": A.sharpe_m(A.period(ex, "test"))}
    sh = pd.DataFrame(rows).T
    sh.to_csv(ROOT / "results" / "tables" / "sharpe_by_rule.csv")
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    x = np.arange(len(sh))
    ax.bar(x - 0.2, sh["dev+val"], 0.4, color=GREY, label="Development + validation 2001-16")
    ax.bar(x + 0.2, sh["test"], 0.4, color=BLUE, label="Locked test 2017-24")
    ax.set_xticks(x, [k.replace("only_", "").replace("_", "\n") for k in sh.index], fontsize=8.5)
    ax.set_ylabel("Sharpe of hedged EAFE")
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("Hedged-equity Sharpe by hedging rule", loc="left", color=INK)
    fig.tight_layout()
    fig.savefig(FIG / "sharpe_by_rule.png")
    plt.close(fig)
    print(sh.round(3))


if __name__ == "__main__":
    main()
