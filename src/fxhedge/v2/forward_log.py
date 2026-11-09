"""Idempotent append for the P6 forward paper-tracking log (monthly; columns: date, book, net_return, prereg_hash)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLS = ["date", "book", "net_return", "prereg_hash"]


def complete_months(m: pd.Series, last_data_date: pd.Timestamp) -> pd.Series:
    """Drop the month containing `last_data_date` unless that date is the month's last business day."""
    last = pd.Timestamp(last_data_date)
    month_last_bday = (last + pd.offsets.BMonthEnd(0)).normalize()
    if last.normalize() >= month_last_bday:
        return m
    return m[m.index.to_period("M") < last.to_period("M")]


def append_new(path: str | Path, rows: pd.DataFrame) -> int:
    """Append rows whose (date, book) is not already in the CSV. Returns the number appended."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = rows[COLS].copy()
    rows["date"] = pd.to_datetime(rows["date"])
    if p.exists():
        old = pd.read_csv(p, parse_dates=["date"])
        seen = set(zip(old["date"], old["book"]))
        keep = [(d, b) not in seen for d, b in zip(rows["date"], rows["book"])]
        new = rows[keep]
        out = pd.concat([old, new], ignore_index=True) if len(new) else old
    else:
        new, out = rows, rows
    out = out.sort_values(["date", "book"]).reset_index(drop=True)
    out.to_csv(p, index=False, date_format="%Y-%m-%d")
    return len(new)
