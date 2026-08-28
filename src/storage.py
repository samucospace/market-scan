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

CREATE TABLE IF NOT EXISTS saved_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    ticker TEXT NOT NULL,
    group_name TEXT NOT NULL,
    description TEXT,
    direction TEXT NOT NULL,
    archetype TEXT NOT NULL,
    conviction_score REAL,
    holding_period TEXT,
    entry_zone TEXT,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    target_1 REAL NOT NULL,
    target_2 REAL NOT NULL,
    risk_reward_ratio REAL,
    risk_pct REAL,
    reward_pct REAL,
    macro_thesis TEXT,
    technical_thesis TEXT,
    invalidation_rules TEXT,
    initial_rsi REAL,
    initial_atr REAL,
    initial_sma20 REAL,
    initial_sma50 REAL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    exit_price REAL,
    exit_date TEXT,
    exit_notes TEXT,
    user_notes TEXT
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
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


def save_trade(conn: sqlite3.Connection, setup: Any, user_notes: str = "") -> int:
    """Persist a trade setup to the database. Returns new trade ID."""
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        """
        INSERT INTO saved_trades (
            created_at, ticker, group_name, description, direction, archetype,
            conviction_score, holding_period, entry_zone, entry_price, stop_loss,
            target_1, target_2, risk_reward_ratio, risk_pct, reward_pct,
            macro_thesis, technical_thesis, invalidation_rules,
            initial_rsi, initial_atr, initial_sma20, initial_sma50,
            status, user_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?)
        """,
        (
            created_at,
            setup.ticker,
            setup.group,
            setup.description,
            setup.direction,
            setup.archetype,
            setup.conviction_score,
            setup.holding_period,
            setup.entry_zone,
            setup.entry_price,
            setup.stop_loss,
            setup.target_1,
            setup.target_2,
            setup.risk_reward_ratio,
            setup.risk_pct,
            setup.reward_pct,
            setup.macro_thesis,
            setup.technical_thesis,
            setup.invalidation_rules,
            setup.rsi_14,
            setup.atr_14,
            setup.sma20,
            setup.sma50,
            user_notes,
        ),
    )
    conn.commit()
    return cur.lastrowid


def get_saved_trades(conn: sqlite3.Connection) -> list[dict]:
    """Retrieve all saved trades ordered with ACTIVE first (by created_at DESC) and EXITED last."""
    cur = conn.execute(
        """
        SELECT * FROM saved_trades
        ORDER BY 
            CASE WHEN status = 'ACTIVE' THEN 0 ELSE 1 END ASC,
            id DESC
        """
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def update_trade_exit(
    conn: sqlite3.Connection,
    trade_id: int,
    exit_price: float,
    exit_date: str,
    exit_notes: str = "",
) -> bool:
    """Record exit price, exit date, and notes for a trade, changing status to EXITED."""
    cur = conn.execute(
        """
        UPDATE saved_trades
        SET status = 'EXITED', exit_price = ?, exit_date = ?, exit_notes = ?
        WHERE id = ?
        """,
        (exit_price, exit_date, exit_notes, trade_id),
    )
    conn.commit()
    return cur.rowcount > 0


def reopen_saved_trade(conn: sqlite3.Connection, trade_id: int) -> bool:
    """Reopen an exited trade back to ACTIVE status."""
    cur = conn.execute(
        """
        UPDATE saved_trades
        SET status = 'ACTIVE', exit_price = NULL, exit_date = NULL, exit_notes = NULL
        WHERE id = ?
        """,
        (trade_id,),
    )
    conn.commit()
    return cur.rowcount > 0


def delete_saved_trade(conn: sqlite3.Connection, trade_id: int) -> bool:
    """Delete a saved trade entry."""
    cur = conn.execute("DELETE FROM saved_trades WHERE id = ?", (trade_id,))
    conn.commit()
    return cur.rowcount > 0


def is_trade_saved_and_active(conn: sqlite3.Connection, ticker: str, direction: str) -> bool:
    """Check if a specific ticker with direction is currently saved and active."""
    cur = conn.execute(
        "SELECT 1 FROM saved_trades WHERE ticker = ? AND direction = ? AND status = 'ACTIVE' LIMIT 1",
        (ticker, direction),
    )
    return cur.fetchone() is not None

