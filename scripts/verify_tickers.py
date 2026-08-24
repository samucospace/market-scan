"""Utility to sanity-check that every ticker in config/watchlist.yaml returns data
from Yahoo Finance. Run this after editing the watchlist, or whenever a ticker is
flagged '# VERIFY' in the yaml, to confirm it actually resolves.

Usage: python scripts/verify_tickers.py
"""
import sys
from pathlib import Path

import yaml
import yfinance as yf

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"


def load_tickers():
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tickers = []
    for group, items in cfg["groups"].items():
        for item in items:
            tickers.append((item["ticker"], group, item.get("note", "")))
    return tickers


def main():
    tickers = load_tickers()
    symbols = [t[0] for t in tickers]
    data = yf.download(symbols, period="5d", interval="1d", group_by="ticker",
                        threads=True, progress=False)

    failures = []
    for symbol, group, note in tickers:
        try:
            sub = data[symbol] if len(symbols) > 1 else data
            close = sub["Close"].dropna()
            ok = len(close) > 0
        except Exception:
            ok = False
        status = "OK" if ok else "FAILED"
        if not ok:
            failures.append(symbol)
        print(f"[{status:6s}] {group:25s} {symbol:15s} {note}")

    if failures:
        print(f"\n{len(failures)} ticker(s) returned no data: {failures}")
        sys.exit(1)
    print("\nAll tickers OK.")


if __name__ == "__main__":
    main()
