"""Stress-aware costs: trade and roll costs widen when VIX (known the day before) is above a threshold."""

from __future__ import annotations

import pandas as pd

from fxhedge.data import RAW, fred


def stress_multiplier(vix: pd.Series, threshold: float = 30.0, mult: float = 3.0) -> pd.Series:
    """Cost multiplier at t uses VIX at t-1 (known before trading at t)."""
    return (1 + (mult - 1) * (vix.shift(1) > threshold)).fillna(1.0)


def load_vix() -> pd.Series:
    """FRED VIXCLS, cached to data/raw/vix.parquet."""
    p = RAW / "vix.parquet"
    if p.exists():
        return pd.read_parquet(p)["VIXCLS"]
    s = fred("VIXCLS")
    s.to_frame("VIXCLS").to_parquet(p)
    return s
