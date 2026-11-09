import numpy as np
import pandas as pd

from fxhedge.v2.conformal_hedge import conformal_hedge
from qengine.lookahead import check_lookahead


def _panel(n=160, seed=0, drift=0.0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2000-01-31", periods=n, freq="ME")
    return pd.DataFrame(rng.normal(drift, 0.02, (n, 2)), index=idx, columns=["EUR", "JPY"])


def test_rule_100_when_upper_below_zero_0_when_lower_above_zero():
    neg = _panel(drift=-0.05)                      # persistent loss in foreign FX, noise small vs drift
    pos = _panel(drift=+0.05)
    Hn, _ = conformal_hedge(neg, alpha=0.2, gamma=0.01, window=36)
    Hp, _ = conformal_hedge(pos, alpha=0.2, gamma=0.01, window=36)
    assert (Hn.dropna().iloc[-30:] == 1.0).all().all()
    assert (Hp.dropna().iloc[-30:] == 0.0).all().all()
    Hz, _ = conformal_hedge(_panel(drift=0.0), alpha=0.2, gamma=0.01, window=36)
    assert (Hz.dropna() == 0.5).mean().mean() > 0.7


def test_ratio_is_nan_until_history_exists():
    H, _ = conformal_hedge(_panel(), alpha=0.2, gamma=0.01, window=36)
    assert H.iloc[:11 + 36].isna().all().all()
    assert H.iloc[11 + 36 + 5:].notna().all().all()


def test_no_lookahead_and_coverage():
    P = _panel(n=200, seed=3)
    check_lookahead(lambda R: conformal_hedge(R, alpha=0.2, gamma=0.01, window=36)[0], P)
    _, cov = conformal_hedge(_panel(n=400, seed=4), alpha=0.2, gamma=0.01, window=36)
    assert abs(cov.dropna().to_numpy().mean() - 0.8) < 0.06
