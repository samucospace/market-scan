"""% change calculations over a stored daily price history."""
import pandas as pd

# Trading-day lookbacks (not calendar days) used to approximate 1W/1M change.
LOOKBACK_TRADING_DAYS = {
    "Daily": 1,
    "Weekly": 5,
    "Monthly": 21,
}


def pct_change(prices: pd.DataFrame, period: str) -> float | None:
    """% change of 'close' from N trading days ago to the latest close.
    Returns None if there isn't enough history yet.
    """
    closes = prices["close"].dropna()
    n = LOOKBACK_TRADING_DAYS[period]
    if len(closes) <= n:
        return None
    latest = closes.iloc[-1]
    prior = closes.iloc[-1 - n]
    if prior == 0:
        return None
    return (latest - prior) / prior * 100


def last_close(prices: pd.DataFrame) -> float | None:
    closes = prices["close"].dropna()
    return closes.iloc[-1] if len(closes) else None


def last_date(prices: pd.DataFrame) -> str | None:
    closes = prices["close"].dropna()
    return closes.index[-1].strftime("%Y-%m-%d") if len(closes) else None
