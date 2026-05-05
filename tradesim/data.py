"""
data.py — yfinance download + normalisation + LightweightCharts format conversion.

Constraint from yfinance docs:
    "Intraday data cannot extend last 60 days"
    For intervals < 1d: enforce max 60-day window before downloading.
"""
from __future__ import annotations

from datetime import date, timezone
from typing import Any, Dict, List, Set

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

INTRADAY_INTERVALS: Set[str] = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
MAX_INTRADAY_DAYS = 60


def validate_date_range(interval: str, start: date, end: date) -> str | None:
    """Return an error message string if the range is invalid, else None."""
    delta = (end - start).days
    if interval in INTRADAY_INTERVALS and delta > MAX_INTRADAY_DAYS:
        return (
            f"Intraday interval `{interval}` נבחר אבל טווח "
            f"({delta} ימים) חורג מ-{MAX_INTRADAY_DAYS} ימים המותרים ב-yfinance. "
            "הקטן את טווח התאריכים."
        )
    return None


@st.cache_data(show_spinner="מוריד נתונים מ-Yahoo Finance…")
def load(symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
    """
    Download OHLCV from yfinance and return a clean DataFrame.

    Columns: open, high, low, close, volume, time (epoch seconds int)
    Index:   RangeIndex (reset)
    """
    raw = yf.download(
        symbol,
        start=str(start),
        end=str(end),
        interval=interval,
        auto_adjust=True,
        progress=False,
    )

    if raw is None or raw.empty:
        return pd.DataFrame()

    # Flatten MultiIndex columns (yfinance >=0.2 may add ticker level)
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw.rename(columns={
        "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Volume": "volume",
    })
    df = df[["open", "high", "low", "close", "volume"]].dropna().copy()

    # Convert index to UTC epoch seconds
    idx = df.index
    if getattr(idx, "tz", None) is None:
        idx = idx.tz_localize(timezone.utc)
    else:
        idx = idx.tz_convert(timezone.utc)
    df["time"] = (idx.view("int64") // 1_000_000_000).astype(int)

    # ── Critical for LightweightCharts: deduplicate & sort ──────────────
    df = df.drop_duplicates(subset="time", keep="last")
    df = df.sort_values("time").reset_index(drop=True)

    return df


# ── Technical indicators ──────────────────────────────────────────────────────

def ema(df: pd.DataFrame, period: int) -> pd.Series:
    return df["close"].ewm(span=period, adjust=False).mean()


def sma(df: pd.DataFrame, period: int) -> pd.Series:
    return df["close"].rolling(period).mean()


# ── LightweightCharts serialisers (vectorised — no iterrows) ──────────────────

def to_candles(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Convert DataFrame to LightweightCharts candlestick series format."""
    d = df[["time", "open", "high", "low", "close"]].copy()
    d[["open", "high", "low", "close"]] = d[["open", "high", "low", "close"]].round(6)
    return d.to_dict("records")


def to_volume(df: pd.DataFrame) -> List[Dict[str, Any]]:
    colors = np.where(df["close"].values >= df["open"].values, "#22C55E66", "#EF444466")
    return [
        {"time": int(t), "value": float(v), "color": c}
        for t, v, c in zip(df["time"], df["volume"], colors)
    ]


def to_line(df: pd.DataFrame, col: str = "close") -> List[Dict[str, Any]]:
    return [
        {"time": int(t), "value": round(float(v), 6)}
        for t, v in zip(df["time"], df[col])
        if pd.notna(v)
    ]
