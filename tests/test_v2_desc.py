import numpy as np
import pandas as pd
import pytest

from fxhedge import model
from fxhedge.data import RAW
from fxhedge.v2.desc import basis_cost, bond_sleeve, max_carry_ratios, usd_regime


def test_usd_regime_uses_only_past_months():
    idx = pd.date_range("2010-01-31", periods=30, freq="ME")
    b = pd.Series(0.01, index=idx)                      # FX basket rising -> USD falling
    b.iloc[20:] = -0.03                                 # then USD rising
    reg = usd_regime(b)
    assert reg.iloc[:12].isna().all()                   # needs 12 trailing months, known before the month
    assert reg.iloc[12] == "usd_falling"
    b2 = b.copy(); b2.iloc[25:] = 0.5                   # change only the future
    pd.testing.assert_series_equal(reg.iloc[:25], usd_regime(b2).iloc[:25])
    assert reg.iloc[29] == "usd_rising"                 # trailing 12m ends month 28: negative


def test_basis_cost_scales_with_hedged_notional():
    h = pd.Series([0.0, 0.5, 1.0], index=pd.bdate_range("2020-01-01", periods=3))
    c = basis_cost(h, 25.0)
    assert np.allclose(c, [0.0, 0.5 * 25e-4 / 252, 25e-4 / 252])
    assert (basis_cost(h, 0.0) == 0).all()


def test_bond_sleeve_hedge_is_linear_in_ratio():
    idx = pd.bdate_range("2020-01-01", periods=5)
    bond = pd.Series([0.001, -0.002, 0.003, 0.0, 0.001], index=idx)
    spot = pd.Series([0.004, -0.001, 0.002, 0.003, -0.002], index=idx)
    X = pd.Series([0.0041, -0.0009, 0.0021, 0.0031, -0.0019], index=idx)
    s0, s1 = bond_sleeve(bond, spot, X, 0.0), bond_sleeve(bond, spot, X, 1.0)
    assert np.allclose(s0, bond + spot)
    assert np.allclose(s1 - s0, -X)


@pytest.mark.skipif(not (RAW / "fred_macro.parquet").exists(), reason="needs local data")
def test_max_carry_is_the_rate_vote_only_book():
    inp = model.inputs()
    mc = max_carry_ratios(inp)
    b = model.books(inp)["only_rate"]["ratios"]
    pd.testing.assert_frame_equal(mc.loc["2002":], b.loc["2002":])
    assert set(np.unique(mc.loc["2005":].to_numpy())) <= {0.0, 1.0}
