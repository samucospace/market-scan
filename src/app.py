"""Streamlit dashboard: ranked list of watchlist tickers by % change."""
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from metrics import last_close, last_date, pct_change
from storage import get_connection, get_prices

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"

st.set_page_config(page_title="Market Scan", layout="wide")


@st.cache_data(ttl=300)
def load_watchlist() -> list[dict]:
    with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    rows = []
    for group, items in cfg["groups"].items():
        for item in items:
            rows.append({"ticker": item["ticker"], "group": group, "note": item.get("note", "")})
    return rows


@st.cache_data(ttl=300)
def build_table(period: str) -> pd.DataFrame:
    conn = get_connection()
    watchlist = load_watchlist()
    records = []
    for entry in watchlist:
        prices = get_prices(conn, entry["ticker"])
        if prices.empty:
            continue
        records.append({
            "Ticker": entry["ticker"],
            "Group": entry["group"],
            "Description": entry["note"],
            "% Change": pct_change(prices, period),
            "Last Close": last_close(prices),
            "As Of": last_date(prices),
        })
    conn.close()
    df = pd.DataFrame(records)
    return df.sort_values("% Change", ascending=False, na_position="last")


def color_pct(val):
    if pd.isna(val):
        return ""
    color = "#1a7f37" if val >= 0 else "#c62828"
    return f"color: {color}; font-weight: 600"


def render_group_cards(table: pd.DataFrame, cols_per_row: int, max_card_height: int) -> None:
    groups = sorted(table["Group"].unique())

    for start in range(0, len(groups), cols_per_row):
        row_groups = groups[start:start + cols_per_row]
        row_cols = st.columns(cols_per_row)

        for idx, group in enumerate(row_groups):
            group_df = (
                table[table["Group"] == group]
                .drop(columns=["As Of", "Group"])
                .sort_values("% Change", ascending=False, na_position="last")
                .reset_index(drop=True)
            )
            group_df["% Change"] = group_df["% Change"].round(2)
            group_df["Last Close"] = group_df["Last Close"].round(4)

            card_height = min(max_card_height, 76 + (len(group_df) * 35))

            with row_cols[idx]:
                with st.container(border=True):
                    st.subheader(group)
                    st.caption(f"{len(group_df)} assets")
                    st.dataframe(
                        group_df.style.map(color_pct, subset=["% Change"]),
                        width="stretch",
                        hide_index=True,
                        height=card_height,
                    )


st.title("Market Scan")

period = st.radio("Period", ["Daily", "Weekly", "Monthly"], horizontal=True)

layout_density = st.radio(
    "Card density",
    ["Compact", "Balanced", "Spacious"],
    horizontal=True,
    index=1,
)

if layout_density == "Compact":
    cols_per_row = 4
    max_card_height = 300
elif layout_density == "Spacious":
    cols_per_row = 2
    max_card_height = 420
else:
    cols_per_row = 3
    max_card_height = 360

table = build_table(period)

if table.empty:
    st.warning("No data found. Run `python src/fetch.py` to populate the database first.")
else:
    as_of = table["As Of"].dropna().max()
    st.caption(f"Data as of {as_of}")
    render_group_cards(table, cols_per_row=cols_per_row, max_card_height=max_card_height)
