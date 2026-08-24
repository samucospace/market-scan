"""SQLite storage layer for daily OHLC price history."""
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "market.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, date)
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def upsert_prices(conn: sqlite3.Connection, ticker: str, df: pd.DataFrame) -> int:
    """Upsert a per-ticker OHLCV dataframe indexed by date. Returns rows written."""
    if df.empty:
        return 0
    rows = [
        (ticker, idx.strftime("%Y-%m-%d"), row.get("Open"), row.get("High"),
         row.get("Low"), row.get("Close"), row.get("Volume"))
        for idx, row in df.iterrows()
    ]
    conn.executemany(
        """
        INSERT INTO prices (ticker, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ticker, date) DO UPDATE SET
            open=excluded.open, high=excluded.high, low=excluded.low,
            close=excluded.close, volume=excluded.volume
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def get_prices(conn: sqlite3.Connection, ticker: str) -> pd.DataFrame:
    """Return a ticker's price history ordered by date, indexed by date."""
    df = pd.read_sql_query(
        "SELECT date, open, high, low, close, volume FROM prices WHERE ticker = ? ORDER BY date",
        conn, params=(ticker,), parse_dates=["date"],
    )
    return df.set_index("date")


def get_all_tickers(conn: sqlite3.Connection) -> list[str]:
    cur = conn.execute("SELECT DISTINCT ticker FROM prices")
    return [row[0] for row in cur.fetchall()]


def get_last_updated(conn: sqlite3.Connection) -> str | None:
    cur = conn.execute("SELECT MAX(date) FROM prices")
    row = cur.fetchone()
    return row[0] if row else None


def get_db_last_write_time() -> str | None:
    """Return local timestamp of last DB write (file mtime), if available."""
    if not DB_PATH.exists():
        return None
    ts = datetime.fromtimestamp(DB_PATH.stat().st_mtime)
    return ts.strftime("%Y-%m-%d %H:%M:%S")
