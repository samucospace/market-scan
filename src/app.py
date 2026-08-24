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


st.title("Market Scan")

period = st.radio("Period", ["Daily", "Weekly", "Monthly"], horizontal=True)

table = build_table(period)

if table.empty:
    st.warning("No data found. Run `python src/fetch.py` to populate the database first.")
else:
    as_of = table["As Of"].dropna().max()
    st.caption(f"Data as of {as_of}")

    groups = ["All"] + sorted(table["Group"].unique())
    selected_group = st.selectbox("Filter by group", groups)
    if selected_group != "All":
        table = table[table["Group"] == selected_group]

    display = table.drop(columns=["As Of"]).reset_index(drop=True)
    display["% Change"] = display["% Change"].round(2)
    display["Last Close"] = display["Last Close"].round(4)

    st.dataframe(
        display.style.map(color_pct, subset=["% Change"]),
        width="stretch",
        hide_index=True,
    )
