"""Streamlit dashboard: ranked list of watchlist tickers by % change."""
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st
import yaml

from historical_analysis import compute_momentum_analysis
from metrics import last_close, last_date, pct_change
from storage import get_connection, get_db_last_write_time, get_prices

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


@st.cache_data(ttl=1800)
def get_news_articles(ticker: str, description: str, limit: int = 6) -> list[dict]:
    query_parts = [ticker, description, "market move reason"]
    query = " ".join(part for part in query_parts if part)
    rss_url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )

    req = Request(
        rss_url,
        headers={
            "User-Agent": "Mozilla/5.0",
        },
    )

    try:
        with urlopen(req, timeout=8) as response:
            xml_bytes = response.read()
        root = ET.fromstring(xml_bytes)
    except Exception:
        return []

    articles = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source = (item.findtext("source") or "").strip()
        if not title or not link:
            continue
        articles.append({
            "title": title,
            "link": link,
            "pub_date": pub_date,
            "source": source,
        })
        if len(articles) >= limit:
            break

    return articles


def render_top_movers_news(table: pd.DataFrame) -> None:
    top_movers = (
        table.dropna(subset=["% Change"])
        .sort_values("% Change", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )
    if top_movers.empty:
        return

    st.subheader("Top Movers: Why They Moved")
    st.caption("Articles are fetched from Google News search and may include multiple viewpoints.")

    tab_labels = [
        f"{row['Ticker']} ({row['% Change']:+.2f}%)"
        for _, row in top_movers.iterrows()
    ]
    tabs = st.tabs(tab_labels)

    for tab, (_, row) in zip(tabs, top_movers.iterrows()):
        with tab:
            st.markdown(
                f"**{row['Ticker']}** | Group: {row['Group']} | Last close: {row['Last Close']:.4f}"
            )
            if row["Description"]:
                st.caption(row["Description"])

            articles = get_news_articles(str(row["Ticker"]), str(row["Description"]), limit=6)
            if not articles:
                st.info("No recent articles found for this instrument right now.")
                continue

            for article in articles:
                title = article["title"]
                link = article["link"]
                source = article["source"] or "Unknown source"
                pub_date = article["pub_date"] or "Unknown time"
                st.markdown(f"- [{title}]({link})")
                st.caption(f"{source} | {pub_date}")


def render_market_freshness_badge(as_of: str) -> None:
    try:
        market_date = datetime.strptime(as_of, "%Y-%m-%d").date()
    except ValueError:
        st.caption("Market freshness: unknown")
        return

    lag_days = (date.today() - market_date).days
    if lag_days <= 0:
        badge_text = "Fresh (today)"
        bg_color = "#d1fae5"
        text_color = "#065f46"
    elif lag_days == 1:
        badge_text = "1 day behind"
        bg_color = "#fef3c7"
        text_color = "#92400e"
    else:
        badge_text = f"{lag_days} days behind"
        bg_color = "#fee2e2"
        text_color = "#991b1b"

    st.markdown(
        (
            "<div style='display:inline-block;padding:0.2rem 0.6rem;"
            "border-radius:999px;font-size:0.85rem;font-weight:600;"
            f"background:{bg_color};color:{text_color};'>"
            f"Market freshness: {badge_text}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


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


def dataframe_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=900)
def load_momentum_results(top_k: int):
    return compute_momentum_analysis(load_watchlist(), top_k=top_k, horizons=(1, 5))


def render_historical_analysis_section() -> None:
    st.subheader("Historical Momentum Check")
    st.caption(
        "Tests whether top daily movers tend to stay near the top and keep rising versus baseline."
    )

    top_k = st.slider("Top bucket size", min_value=1, max_value=10, value=5, step=1)
    result = load_momentum_results(top_k)

    if not result.summary:
        st.info("Not enough historical data in the local database yet.")
        return

    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    with stats_col1:
        st.metric("Tickers", result.summary["total_tickers"])
    with stats_col2:
        st.metric("Sample days", result.summary["sample_days"])
    with stats_col3:
        st.metric("Top-bucket samples", result.summary["top_occurrences"])
    with stats_col4:
        st.metric("Date range", f"{result.summary['date_start']} to {result.summary['date_end']}")

    if result.summary["sample_days"] < 120:
        st.warning(
            "Only a short history is available right now. Consider fetching a longer period for stronger confidence."
        )

    st.markdown("**Continuation vs Baseline**")
    st.dataframe(result.horizon_stats.round(3), width="stretch", hide_index=True)

    st.markdown("**Persistence At The Top**")
    st.dataframe(result.persistence_stats.round(3), width="stretch", hide_index=True)

    export_col1, export_col2, export_col3 = st.columns(3)
    with export_col1:
        st.download_button(
            "Download continuation CSV",
            data=dataframe_to_csv_bytes(result.horizon_stats),
            file_name=f"continuation_top{top_k}.csv",
            mime="text/csv",
        )
    with export_col2:
        st.download_button(
            "Download persistence CSV",
            data=dataframe_to_csv_bytes(result.persistence_stats),
            file_name=f"persistence_top{top_k}.csv",
            mime="text/csv",
        )
    with export_col3:
        st.download_button(
            "Download group breakdown CSV",
            data=dataframe_to_csv_bytes(result.group_breakdown),
            file_name=f"group_breakdown_top{top_k}.csv",
            mime="text/csv",
        )

    top_col, group_col = st.columns(2)
    with top_col:
        st.markdown("**Most Frequent Top-1 Names**")
        st.dataframe(result.top1_frequency.head(15), width="stretch", hide_index=True)
    with group_col:
        st.markdown("**Group Breakdown (1D continuation)**")
        st.dataframe(result.group_breakdown.round(3), width="stretch", hide_index=True)


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
    db_updated_at = get_db_last_write_time()
    info_col, badge_col = st.columns([4, 3])
    with info_col:
        if db_updated_at:
            st.caption(f"Latest market date: {as_of} | Database updated at: {db_updated_at} (local time)")
        else:
            st.caption(f"Latest market date: {as_of}")
    with badge_col:
        render_market_freshness_badge(as_of)

    render_top_movers_news(table)
    render_historical_analysis_section()
    render_group_cards(table, cols_per_row=cols_per_row, max_card_height=max_card_height)
