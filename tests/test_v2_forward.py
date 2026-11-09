import pandas as pd

from fxhedge.v2.forward_log import append_new, complete_months

BOOKS = ("static50", "v1_dynamic3", "mv60", "volcap_wf")


def _rows(dates, book="static50"):
    return pd.DataFrame({"date": pd.to_datetime(dates), "book": book, "net_return": 0.01, "prereg_hash": "h"})


def test_append_is_idempotent(tmp_path):
    p = tmp_path / "forward.csv"
    assert append_new(p, _rows(["2026-11-30", "2026-12-31"])) == 2
    assert append_new(p, _rows(["2026-11-30", "2026-12-31"])) == 0
    assert append_new(p, _rows(["2026-12-31", "2027-01-29"])) == 1
    df = pd.read_csv(p)
    assert len(df) == 3 and not df.duplicated(["date", "book"]).any()


def test_four_books_append_twice_no_duplicates(tmp_path):
    p = tmp_path / "f.csv"
    rows = pd.concat([_rows(["2026-11-30", "2026-12-31"], b) for b in BOOKS])
    assert append_new(p, rows) == 8
    assert append_new(p, rows) == 0
    assert len(pd.read_csv(p)) == 8


def test_empty_creates_header_only(tmp_path):
    p = tmp_path / "f.csv"
    assert append_new(p, _rows([]).iloc[0:0]) == 0
    assert list(pd.read_csv(p).columns) == ["date", "book", "net_return", "prereg_hash"]


def test_complete_months_drops_partial_last_month():
    m = pd.Series([0.01, 0.02, 0.03], index=pd.to_datetime(["2026-08-31", "2026-09-30", "2026-10-13"]))
    out = complete_months(m, pd.Timestamp("2026-10-13"))
    assert list(out.index) == list(pd.to_datetime(["2026-08-31", "2026-09-30"]))
    # data through the last business day of the month: that month is complete
    m2 = pd.Series([0.01, 0.02], index=pd.to_datetime(["2026-09-30", "2026-10-30"]))
    assert len(complete_months(m2, pd.Timestamp("2026-10-30"))) == 2


def test_volcap_folds_continue_after_2016():
    from fxhedge.v2.books import vc_folds
    idx = pd.bdate_range("2001-01-01", "2026-10-13")
    f = vc_folds(idx, 2026)
    assert f[0][2] == pd.Timestamp("2006-01-01") and f[0][1] == pd.Timestamp("2005-12-31")
    last_old = [x for x in f if x[2].year == 2016]
    assert len(last_old) == 1 and last_old[0][3] == pd.Timestamp("2016-12-31")     # 2016 block is one year, as in h1_h2
    seen = [x for x in f if x[2].year >= 2017]
    assert seen[0][1] == pd.Timestamp("2016-12-31") and seen[-1][3] == pd.Timestamp("2026-12-31")
    assert all(x[0] == idx[0] for x in f)                                          # anchored
    assert all(x[1] < x[2] for x in f)                                             # train ends before test starts
