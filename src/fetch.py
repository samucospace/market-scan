"""Daily batch fetch job: pulls recent daily history for every watchlist ticker
from Yahoo Finance and upserts it into the local SQLite store.

Usage: python src/fetch.py
Intended to be run once a day (e.g. via Windows Task Scheduler).
"""
import logging
from pathlib import Path

import yaml
import yfinance as yf

from storage import get_connection, upsert_prices

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"

# ~3 months of daily bars is enough to compute 1D/1W/1M change with room for
# holidays/weekends, without requesting more history than needed.
FETCH_PERIOD = "3mo"


def load_tickers() -> list[str]:
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tickers = []
    for items in cfg["groups"].values():
        tickers.extend(item["ticker"] for item in items)
    return tickers


def main():
    tickers = load_tickers()
    log.info("Fetching %d tickers...", len(tickers))

    data = yf.download(
        tickers, period=FETCH_PERIOD, interval="1d",
        group_by="ticker", threads=True, progress=False, auto_adjust=False,
    )

    conn = get_connection()
    ok, failed = 0, []
    for ticker in tickers:
        try:
            df = data[ticker].dropna(how="all")
        except KeyError:
            df = data if len(tickers) == 1 else None
        if df is None or df.empty:
            failed.append(ticker)
            continue
        rows = upsert_prices(conn, ticker, df)
        log.info("%-15s %d rows", ticker, rows)
        ok += 1
    conn.close()

    log.info("Done: %d/%d tickers updated.", ok, len(tickers))
    if failed:
        log.warning("No data for: %s", failed)


if __name__ == "__main__":
    main()
