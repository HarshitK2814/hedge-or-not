"""E1 (EXPLORATORY): conformal hedge. Per currency, yhat(t) = trailing 12-month mean of the monthly forward excess return
(known at month-end t); ACI interval for the NEXT month's return. Labels are non-overlapping months, so the interval
at month-end t only uses scores of months realised by t (qcore.aci_intervals residuals up to row t-1 = month t).
Rule: hedge 100% if the upper bound < 0, 0% if the lower bound > 0, else 50%."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qcore.conformal import aci_intervals


def conformal_hedge(Xm: pd.DataFrame, alpha: float = 0.2, gamma: float = 0.01, window: int = 36,
                    mean_window: int = 12) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Xm: monthly forward excess returns (rows = month-ends). Returns (ratios at month-end, coverage of the next month)."""
    H = pd.DataFrame(np.nan, index=Xm.index, columns=Xm.columns)
    C = H.copy()
    for c in Xm.columns:
        y = Xm[c]
        yhat = y.rolling(mean_window).mean()                 # known at month-end t
        y_next = y.shift(-1)                                 # realised one month later
        ok = yhat.notna()
        iv = aci_intervals(y_next[ok], yhat[ok], alpha=alpha, gamma=gamma, window=window)
        up, lo = iv["hi"], iv["lo"]
        ratio = pd.Series(0.5, index=iv.index).where(~((up < 0) | (lo > 0)), np.where(up < 0, 1.0, 0.0))
        H.loc[iv.index, c] = ratio.where(iv["lo"].notna())
        C.loc[iv.index, c] = iv["covered"].where(y_next[ok].notna() & iv["lo"].notna())
    return H, C
