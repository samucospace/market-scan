"""Central Bank Policy Engine & Meeting Tracker.

Tracks:
1. G10 + MAS Central Bank Policy Rates, Stances, and Trajectories
2. Interest Rate Differentials vs USD and Carry Potential
3. Next Meeting Dates, Countdowns, and Full Scheduled Calendars
4. FX Pair Linkage and Tactical Policy Divergence Implications
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from metrics import last_close, pct_change
from storage import get_connection, get_prices

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "central_banks.yaml"


@dataclass
class CentralBankInfo:
    code: str  # e.g., "USD"
    name: str  # e.g., "Federal Reserve (Fed)"
    currency: str  # e.g., "USD"
    flag: str  # e.g., "🇺🇸"
    policy_rate_name: str
    policy_rate: float
    rate_display: str
    rate_spread_vs_usd: float  # Policy Rate - Fed Rate
    stance: str
    stance_score: float  # -10 (Dovish) to +10 (Hawkish)
    chair: str
    balance_sheet: str
    next_meeting: str
    days_to_meeting: int
    meetings_schedule: list[str]
    primary_fx_pair: str
    fx_pair_display: str
    fx_last_price: float | None
    fx_chg_20d: float | None
    summary: str
    key_drivers: list[str]
    fx_implication: str


@dataclass
class UpcomingMeeting:
    currency: str
    bank_name: str
    flag: str
    meeting_date: str
    days_left: int
    policy_rate: float
    stance: str


@dataclass
class CentralBanksReport:
    banks: list[CentralBankInfo]
    usd_rate: float
    next_upcoming_meeting: UpcomingMeeting | None
    all_upcoming_meetings: list[UpcomingMeeting]
    policy_matrix: pd.DataFrame


def load_central_banks_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_central_banks_report(
    conn: sqlite3.Connection | None = None,
    current_date: date | None = None,
) -> CentralBanksReport:
    if current_date is None:
        current_date = date.today()

    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    cfg = load_central_banks_config()
    cb_data = cfg.get("central_banks", {})

    usd_rate = cb_data.get("USD", {}).get("policy_rate", 4.625)

    banks_list: list[CentralBankInfo] = []
    upcoming_meetings_list: list[UpcomingMeeting] = []

    for code, item in cb_data.items():
        pol_rate = float(item.get("policy_rate", 0.0))
        spread_vs_usd = round(pol_rate - usd_rate, 3)

        # Parse next meeting and calculate days left
        meetings = item.get("meetings_schedule", [])
        valid_future_meetings = []
        for m_str in meetings:
            try:
                m_date = datetime.strptime(m_str, "%Y-%m-%d").date()
                if m_date >= current_date:
                    valid_future_meetings.append((m_str, (m_date - current_date).days))
            except ValueError:
                pass

        if valid_future_meetings:
            next_m_date, days_left = min(valid_future_meetings, key=lambda x: x[1])
        else:
            next_m_date, days_left = item.get("next_meeting", "TBD"), 999

        # Fetch linked FX pair data
        fx_pair = item.get("primary_fx_pair", "")
        fx_last_px = None
        fx_20d = None
        if fx_pair:
            prices = get_prices(conn, fx_pair)
            if not prices.empty:
                fx_last_px = last_close(prices)
                fx_20d = pct_change(prices, 20)

        bank_info = CentralBankInfo(
            code=code,
            name=item.get("name", code),
            currency=item.get("currency", code),
            flag=item.get("flag", "🌐"),
            policy_rate_name=item.get("policy_rate_name", "Policy Rate"),
            policy_rate=pol_rate,
            rate_display=item.get("rate_display", f"{pol_rate:.2f}%"),
            rate_spread_vs_usd=spread_vs_usd,
            stance=item.get("stance", "Neutral"),
            stance_score=float(item.get("stance_score", 0.0)),
            chair=item.get("chair", ""),
            balance_sheet=item.get("balance_sheet", ""),
            next_meeting=next_m_date,
            days_to_meeting=days_left,
            meetings_schedule=meetings,
            primary_fx_pair=fx_pair,
            fx_pair_display=item.get("fx_pair_display", fx_pair),
            fx_last_price=round(fx_last_px, 4) if fx_last_px is not None else None,
            fx_chg_20d=round(fx_20d, 2) if fx_20d is not None else None,
            summary=item.get("summary", ""),
            key_drivers=item.get("key_drivers", []),
            fx_implication=item.get("fx_implication", ""),
        )
        banks_list.append(bank_info)

        # Add all upcoming meetings to the global calendar
        for m_str, d_left in valid_future_meetings:
            upcoming_meetings_list.append(UpcomingMeeting(
                currency=code,
                bank_name=bank_info.name,
                flag=bank_info.flag,
                meeting_date=m_str,
                days_left=d_left,
                policy_rate=pol_rate,
                stance=bank_info.stance,
            ))

    if should_close:
        conn.close()

    # Sort upcoming meetings chronologically
    upcoming_meetings_list.sort(key=lambda x: x.days_left)
    next_up = upcoming_meetings_list[0] if upcoming_meetings_list else None

    # Build a clean summary matrix DataFrame
    matrix_rows = []
    for b in banks_list:
        matrix_rows.append({
            "Currency": f"{b.flag} {b.currency}",
            "Central Bank": b.name,
            "Policy Rate": b.rate_display,
            "Spread vs Fed (USD)": f"{b.rate_spread_vs_usd:+.2f}%" if b.currency != "USD" else "— (Benchmark)",
            "Stance": b.stance,
            "Next Decision": b.next_meeting,
            "Countdown": f"In {b.days_to_meeting} days" if b.days_to_meeting < 999 else "TBD",
            "Linked FX Pair": f"{b.fx_pair_display}: {b.fx_last_price}" if b.fx_last_price else b.fx_pair_display,
            "20D FX Momentum": f"{b.fx_chg_20d:+.2f}%" if b.fx_chg_20d is not None else "—",
        })

    matrix_df = pd.DataFrame(matrix_rows)

    return CentralBanksReport(
        banks=banks_list,
        usd_rate=usd_rate,
        next_upcoming_meeting=next_up,
        all_upcoming_meetings=upcoming_meetings_list,
        policy_matrix=matrix_df,
    )
