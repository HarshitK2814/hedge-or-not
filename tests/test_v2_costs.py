import numpy as np
import pandas as pd
import pytest

from fxhedge import model
from fxhedge.data import RAW
from fxhedge.v2.costs import stress_multiplier


def test_stress_multiplier_lagged():
    idx = pd.bdate_range("2020-03-02", periods=4)
    m = stress_multiplier(pd.Series([20.0, 40.0, 40.0, 20.0], index=idx))
    assert list(m) == [1.0, 1.0, 3.0, 3.0]


@pytest.mark.skipif(not (RAW / "fred_macro.parquet").exists(), reason="needs local data")
def test_overlay_default_unchanged_and_mult_scales_costs():
    inp = model.inputs()
    H = model.books(inp)["dynamic3"]["ratios"].loc[:"2016-12-31"]
    a = model.overlay(H, inp)
    b = model.overlay(H, inp, cost_mult=pd.Series(2.0, index=H.index))
    pd.testing.assert_series_equal(a["net"], model.overlay(H, inp, cost_mult=None)["net"])
    assert np.allclose(b["cost"].loc[H.index], 2 * a["cost"].loc[H.index])
