"""Free data: FRED FX spot and OECD 3-month rates, World Bank PPP, Yahoo ETF prices."""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
# Unhedged / fully hedged / dividend-weighted unhedged / the dynamic-hedge fund itself / a second hedged EAFE ETF
ETFS = ["EFA", "HEFA", "DWM", "DDWM", "DBEF", "SPY"]


def cfg() -> dict:
    return yaml.safe_load((ROOT / "configs" / "hedge.yaml").read_text())


def fred(series_id: str) -> pd.Series:
    txt = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", timeout=60).text
    df = pd.read_csv(io.StringIO(txt))
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna().rename(series_id)


def world_bank_ppp(countries: list[str]) -> pd.DataFrame:
    url = (f"https://api.worldbank.org/v2/country/{';'.join(countries)}/indicator/PA.NUS.PPP"
           "?format=json&per_page=5000")
    rows = requests.get(url, timeout=60).json()[1]
    df = pd.DataFrame([{"c": r["countryiso3code"], "year": int(r["date"]), "ppp": r["value"]} for r in rows])
    return df.pivot(index="year", columns="c", values="ppp").sort_index()


def download() -> None:
    import yfinance as yf

    from .macro import download_macro

    RAW.mkdir(parents=True, exist_ok=True)
    download_macro()
    c = cfg()
    isos = (set(c["ppp_country"].values()) - {"EUROAREA"}) | set(c["euro_ppp_weights"]) | {"USA"}
    world_bank_ppp(sorted(isos)).to_parquet(RAW / "ppp.parquet")
    px = yf.download(ETFS, start="1999-01-01", auto_adjust=True, progress=False)["Close"]
    px.to_parquet(RAW / "etf_close.parquet")


def etf_returns() -> pd.DataFrame:
    px = pd.read_parquet(RAW / "etf_close.parquet")
    return px.pct_change(fill_method=None)


def ppp_daily(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Fair value in USD per unit of foreign currency = 1 / PPP (LCU per international $), point-in-time:
    year-Y PPP is usable from 1 Jan of Y + ppp_lag_years."""
    c = cfg()
    p = pd.read_parquet(RAW / "ppp.parquet")
    ew = pd.Series(c["euro_ppp_weights"])
    p["EUROAREA"] = np.exp((np.log(p[ew.index]) * ew).sum(axis=1, min_count=len(ew)) / ew.sum())
    out = {}
    for ccy, iso in c["ppp_country"].items():
        s = (1 / p[iso]).dropna()
        s.index = pd.to_datetime([f"{y + c['ppp_lag_years']}-01-01" for y in s.index])
        out[ccy] = s.reindex(index.union(s.index)).ffill().reindex(index)
    return pd.DataFrame(out)
