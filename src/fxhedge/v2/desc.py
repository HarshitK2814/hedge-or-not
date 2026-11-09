"""Helpers for the descriptive items D5-D8 (no hypothesis attached)."""

from __future__ import annotations

import pandas as pd

from fxhedge import model


def max_carry_ratios(inp: dict) -> pd.DataFrame:
    """D5 baseline: hedge a currency (100%) when the US 3m rate exceeds its rate, else 0%. Sampled on the last
    business day of the month, applied from the next one (v1 convention); 50% neutral if a rate is missing (as v1)."""
    r, ccys = inp["rates"], inp["ccys"]
    me = model.month_ends(r.index)
    carry = (r["USD"].reindex(me).values[:, None] - r[ccys].reindex(me).values > 0)
    h = pd.DataFrame(carry.astype(float), index=me, columns=ccys)
    h = h.where(r[ccys].reindex(me).notna(), 0.5)
    return h.reindex(r.index).ffill().shift(1)


def usd_regime(basket_m: pd.Series) -> pd.Series:
    """D7: label for month t from the trailing 12-month foreign-currency basket return known at the end of month t-1
    ('usd_rising' if it is negative, else 'usd_falling'). NaN while fewer than 12 past months exist."""
    trail = ((1 + basket_m).rolling(12).apply(lambda x: x.prod(), raw=True) - 1).shift(1)
    return pd.Series(["usd_rising" if t < 0 else "usd_falling" for t in trail], index=basket_m.index).where(trail.notna())


def basis_cost(hedge: pd.Series, bp_per_year: float) -> pd.Series:
    """D6: extra daily cost of a CIP basis of `bp_per_year` on the hedged notional share."""
    return hedge * bp_per_year / 1e4 / 252


def bond_sleeve(bond_local: pd.Series, basket_spot: pd.Series, basket_X: pd.Series, h: float) -> pd.Series:
    """D8: USD return of a foreign-bond sleeve hedged at ratio h: local bond return + FX spot move - h x forward excess."""
    return bond_local + basket_spot - h * basket_X
