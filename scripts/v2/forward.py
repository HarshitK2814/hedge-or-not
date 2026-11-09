"""P6 v2 forward paper tracker (monthly). Books (prereg v2): static50, v1_dynamic3, mv60, volcap_wf.
Ratios computed at the last business day of month m, applied from the next business day. Monthly net return = EFA + overlay,
stress-aware costs (v1 x3 after VIX>30). Only COMPLETE months at or after the forward start in configs/splits_v2.yaml are written,
through qcore.splits.select (locked by the v2 prereg hash b2e9a0e506a9). Idempotent (append only new (date, book) pairs).
The vol-capped target continues the prereg walk-forward (anchored, 2-year blocks, training data before each block).
Usage: PREREG_HASH=b2e9a0e506a9 python scripts/v2/forward.py [--refresh]
  --refresh re-downloads FRED / Yahoo data, the VIX series and the GARCH vol cache (slow) before tracking. Without it the tracker
  uses the data on disk, so seen-period numbers cannot shift. First read of results: 2027-11 (12 months); tracking only."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

from fxhedge import data, macro
from fxhedge.v2 import study
from fxhedge.v2.books import BOOKS, build
from fxhedge.v2.forward_log import append_new, complete_months
from fxhedge.v2.hedges import monthly
from qcore.splits import Splits, file_hash, select

ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research" / "preregistration_v2.md"
OUT = ROOT / "results" / "v2" / "forward" / "forward.csv"


def main(refresh: bool = False) -> int:
    if refresh:
        data.download()
        macro.download_macro()
        (data.RAW / "vix.parquet").unlink(missing_ok=True)
        (study.RUNS / "fx_garch_vol_ann.parquet").unlink(missing_ok=True)
    ctx = study.context()
    last = ctx["efa_d"].index[-1]
    lcm = complete_months(monthly(ctx["efa_d"]), last).index[-1]
    b = build(ctx, last_complete_month_end=lcm, last_year=max(2026, last.year))
    splits = Splits.from_dict(yaml.safe_load((ROOT / "configs" / "splits_v2.yaml").read_text()))
    h = file_hash(PREREG)
    rows = []
    for name in BOOKS:
        m = complete_months(study.month_returns(b[name], ctx)["m"], last)
        f = select(m, splits, "forward", PREREG)
        rows.append(pd.DataFrame({"date": f.index, "book": name, "net_return": f.to_numpy(), "prereg_hash": h}))
    n_new = append_new(OUT, pd.concat(rows, ignore_index=True))
    log = pd.read_csv(OUT, parse_dates=["date"])
    months = log["date"].nunique()
    print(f"data ends {last.date()}; forward start {splits.forward[0]}; new rows {n_new}; forward months tracked: {months} "
          f"(days: {int((ctx['efa_d'].index >= pd.Timestamp(splits.forward[0] + '-01')).sum())})")
    return months


if __name__ == "__main__":
    main("--refresh" in sys.argv)
