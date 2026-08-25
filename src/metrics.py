"""Technical and quantitative metrics calculated over stored daily price history."""
from __future__ import annotations

import numpy as np
import pandas as pd

# Trading-day lookbacks (not calendar days) used to approximate 1W/1M/3M change.
LOOKBACK_TRADING_DAYS = {
    "Daily": 1,
    "Weekly": 5,
    "Monthly": 21,
    "Quarterly": 63,
}


def pct_change(prices: pd.DataFrame, period: str | int) -> float | None:
    """% change of 'close' from N trading days ago to the latest close."""
    if prices is None or prices.empty or "close" not in prices:
        return None
    closes = prices["close"].dropna()
    if isinstance(period, str):
        n = LOOKBACK_TRADING_DAYS.get(period, 1)
    else:
        n = int(period)
    if len(closes) <= n:
        return None
    latest = float(closes.iloc[-1])
    prior = float(closes.iloc[-1 - n])
    if prior == 0:
        return None
    return (latest - prior) / prior * 100.0


def last_close(prices: pd.DataFrame) -> float | None:
    if prices is None or prices.empty or "close" not in prices:
        return None
    closes = prices["close"].dropna()
    return float(closes.iloc[-1]) if len(closes) else None


def last_date(prices: pd.DataFrame) -> str | None:
    if prices is None or prices.empty or "close" not in prices:
        return None
    closes = prices["close"].dropna()
    return closes.index[-1].strftime("%Y-%m-%d") if len(closes) else None


def calculate_rsi(prices: pd.DataFrame, window: int = 14) -> float | None:
    """Calculate Relative Strength Index (RSI) using Wilder's smoothing."""
    if prices is None or prices.empty or "close" not in prices:
        return None
    closes = prices["close"].dropna()
    if len(closes) < window + 1:
        return None
    
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Wilder's exponential moving average
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0


def calculate_atr(prices: pd.DataFrame, window: int = 14) -> float | None:
    """Calculate Average True Range (ATR)."""
    if prices is None or prices.empty:
        return None
    df = prices[["high", "low", "close"]].dropna()
    if len(df) < window + 1:
        return None
    
    high = df["high"]
    low = df["low"]
    prev_close = df["close"].shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    val = atr.iloc[-1]
    return float(val) if pd.notna(val) else None


def calculate_sma(prices: pd.DataFrame, window: int) -> float | None:
    """Calculate Simple Moving Average for given window."""
    if prices is None or prices.empty or "close" not in prices:
        return None
    closes = prices["close"].dropna()
    if len(closes) < window:
        return None
    return float(closes.tail(window).mean())


def calculate_ema(prices: pd.DataFrame, window: int) -> float | None:
    """Calculate Exponential Moving Average for given window."""
    if prices is None or prices.empty or "close" not in prices:
        return None
    closes = prices["close"].dropna()
    if len(closes) < window:
        return None
    ema = closes.ewm(span=window, adjust=False).mean()
    return float(ema.iloc[-1])


def calculate_bollinger_bands(
    prices: pd.DataFrame, window: int = 20, num_std: float = 2.0
) -> dict[str, float | None]:
    """Calculate Bollinger Bands (middle, upper, lower, bandwidth, %B)."""
    if prices is None or prices.empty or "close" not in prices:
        return {"mid": None, "upper": None, "lower": None, "bandwidth": None, "pct_b": None}
    closes = prices["close"].dropna()
    if len(closes) < window:
        return {"mid": None, "upper": None, "lower": None, "bandwidth": None, "pct_b": None}
    
    rolling_mean = closes.rolling(window=window).mean()
    rolling_std = closes.rolling(window=window).std()
    
    mid = rolling_mean.iloc[-1]
    std = rolling_std.iloc[-1]
    upper = mid + (num_std * std)
    lower = mid - (num_std * std)
    last = closes.iloc[-1]
    
    bandwidth = ((upper - lower) / mid * 100.0) if mid and mid > 0 else None
    pct_b = ((last - lower) / (upper - lower)) if (upper - lower) > 0 else 0.5
    
    return {
        "mid": float(mid),
        "upper": float(upper),
        "lower": float(lower),
        "bandwidth": float(bandwidth) if bandwidth is not None else None,
        "pct_b": float(pct_b) if pct_b is not None else None,
    }


def calculate_channel_extremes(prices: pd.DataFrame, window: int = 20) -> dict[str, float | None]:
    """Calculate Donchian high and low over the given window."""
    if prices is None or prices.empty:
        return {"high": None, "low": None}
    df = prices.dropna(subset=["high", "low"])
    if len(df) < window:
        return {"high": None, "low": None}
    
    recent = df.tail(window)
    return {
        "high": float(recent["high"].max()),
        "low": float(recent["low"].min()),
    }
