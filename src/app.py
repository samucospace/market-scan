"""Streamlit dashboard: ranked list of watchlist tickers by % change."""
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import pandas as pd
import streamlit as st
import yaml

from metrics import last_close, last_date, pct_change
from storage import get_connection, get_db_last_write_time, get_prices

YIELD_TICKERS = ["^IRX", "^FVX", "^TNX", "^TYX"]
EQUITY_TICKERS = ["^GSPC", "^NDX", "^DJI"]
DOLLAR_TICKER = "DX-Y.NYB"
COPPER_TICKER = "HG=F"
OIL_TICKERS = ["CL=F", "BZ=F"]
CREDIT_RISK_TICKER = "HYG"
CREDIT_SAFE_TICKER = "IEF"

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


def render_movers_news(table: pd.DataFrame, ascending: bool, heading: str) -> None:
    movers = (
        table.dropna(subset=["% Change"])
        .sort_values("% Change", ascending=ascending)
        .head(5)
        .reset_index(drop=True)
    )
    if movers.empty:
        return

    st.subheader(heading)
    st.caption("Articles are fetched from Google News search and may include multiple viewpoints.")

    tab_labels = [
        f"{row['Ticker']} ({row['% Change']:+.2f}%)"
        for _, row in movers.iterrows()
    ]
    tabs = st.tabs(tab_labels)

    for tab, (_, row) in zip(tabs, movers.iterrows()):
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

    render_badge(f"Market freshness: {badge_text}", bg_color, text_color)


def render_badge(text: str, bg_color: str, text_color: str) -> None:
    st.markdown(
        (
            "<div style='display:inline-block;padding:0.2rem 0.6rem;"
            "border-radius:999px;font-size:0.85rem;font-weight:600;"
            f"background:{bg_color};color:{text_color};'>"
            f"{text}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _direction(value: float | None, eps: float = 0.02) -> str:
    if value is None or pd.isna(value):
        return "flat"
    if value > eps:
        return "up"
    if value < -eps:
        return "down"
    return "flat"


@st.cache_data(ttl=300)
def get_regime_pct_changes(tickers: tuple[str, ...], period: str) -> dict:
    conn = get_connection()
    result = {}
    for ticker in tickers:
        prices = get_prices(conn, ticker)
        result[ticker] = pct_change(prices, period) if not prices.empty else None
    conn.close()
    return result


def _avg(values: list[float | None]) -> float | None:
    clean = [v for v in values if v is not None and not pd.isna(v)]
    return sum(clean) / len(clean) if clean else None


REGIME_PERIODS = {"1 Day": "Daily", "1 Week": "Weekly", "1 Month": "Monthly"}
# Longer lookbacks naturally produce bigger moves, so "flat" thresholds scale up too.
REGIME_EPS_SCALE = {"Daily": 1.0, "Weekly": 2.5, "Monthly": 5.0}


def render_market_regime_section() -> None:
    header_col, toggle_col = st.columns([3, 2])
    with header_col:
        st.subheader("Market Regime Check")
    with toggle_col:
        period_label = st.radio(
            "Regime lookback", list(REGIME_PERIODS.keys()), horizontal=True, index=0, label_visibility="collapsed"
        )
    period = REGIME_PERIODS[period_label]
    scale = REGIME_EPS_SCALE[period]
    st.caption(f"Based on {period_label.lower()} change.")

    all_tickers = tuple(sorted(set(
        YIELD_TICKERS + EQUITY_TICKERS + [DOLLAR_TICKER, COPPER_TICKER, CREDIT_RISK_TICKER, CREDIT_SAFE_TICKER]
        + OIL_TICKERS
    )))
    changes = get_regime_pct_changes(all_tickers, period)

    yield_change = _avg([changes.get(t) for t in YIELD_TICKERS])
    equity_change = _avg([changes.get(t) for t in EQUITY_TICKERS])
    dollar_change = changes.get(DOLLAR_TICKER)
    copper_change = changes.get(COPPER_TICKER)
    oil_change = _avg([changes.get(t) for t in OIL_TICKERS])
    hyg_change = changes.get(CREDIT_RISK_TICKER)
    ief_change = changes.get(CREDIT_SAFE_TICKER)
    hy_relative = None if hyg_change is None or ief_change is None else hyg_change - ief_change

    yields_dir = _direction(yield_change, eps=0.02 * scale)
    equities_dir = _direction(equity_change, eps=0.02 * scale)
    dollar_dir = _direction(dollar_change, eps=0.15 * scale)
    copper_dir = _direction(copper_change, eps=0.2 * scale)
    oil_dir = _direction(oil_change, eps=0.2 * scale)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        with st.container(border=True):
            st.markdown("**Rates Impulse**")
            st.caption("Yields up + equities up = pro-growth. Yields up + equities down = inflation scare.")
            st.caption(
                f"Yields avg: {yield_change:+.2f}%" if yield_change is not None else "Yields avg: n/a"
            )
            st.caption(
                f"Equities avg: {equity_change:+.2f}%" if equity_change is not None else "Equities avg: n/a"
            )
            if yields_dir == "up" and equities_dir == "up":
                render_badge("Pro-growth expansion", "#d1fae5", "#065f46")
            elif yields_dir == "up" and equities_dir == "down":
                render_badge("Inflation scare / tightening", "#fee2e2", "#991b1b")
            elif yields_dir == "down" and equities_dir == "up":
                render_badge("Dovish rally", "#fef3c7", "#92400e")
            elif yields_dir == "down" and equities_dir == "down":
                render_badge("Growth scare / flight to quality", "#fee2e2", "#991b1b")
            else:
                render_badge("Mixed / flat signal", "#e5e7eb", "#374151")

    with col2:
        with st.container(border=True):
            st.markdown("**FX & Dollar Strength**")
            st.caption("A surging dollar tightens global conditions, pressuring EM and commodity importers.")
            st.caption(f"DXY: {dollar_change:+.2f}%" if dollar_change is not None else "DXY: n/a")
            if dollar_dir == "up":
                render_badge("Dollar strength - global tightening", "#fee2e2", "#991b1b")
            elif dollar_dir == "down":
                render_badge("Dollar weakness - easier conditions", "#d1fae5", "#065f46")
            else:
                render_badge("Dollar flat - no confirmation", "#e5e7eb", "#374151")

    with col3:
        with st.container(border=True):
            st.markdown("**Copper vs Oil**")
            st.caption("Copper up + oil stable = cyclical demand. Oil spiking alone = consumer tax.")
            st.caption(f"Copper: {copper_change:+.2f}%" if copper_change is not None else "Copper: n/a")
            st.caption(f"Oil avg: {oil_change:+.2f}%" if oil_change is not None else "Oil avg: n/a")
            if copper_dir == "up" and oil_dir != "up":
                render_badge("Industrial demand strengthening", "#d1fae5", "#065f46")
            elif oil_dir == "up" and copper_dir != "up":
                render_badge("Oil-led move - consumer tax risk", "#fef3c7", "#92400e")
            elif copper_dir == "up" and oil_dir == "up":
                render_badge("Broad commodity demand strength", "#d1fae5", "#065f46")
            elif copper_dir == "down" and oil_dir == "down":
                render_badge("Broad commodity demand weakening", "#fee2e2", "#991b1b")
            else:
                render_badge("Mixed signal", "#e5e7eb", "#374151")

    with col4:
        with st.container(border=True):
            st.markdown("**Credit Stress**")
            st.caption("Equities down + HY spreads tight = routine pullback. Spreads blowout too = systemic risk.")
            st.caption(
                f"HYG vs IEF: {hy_relative:+.2f}%" if hy_relative is not None else "HYG vs IEF: n/a"
            )
            if equities_dir != "down":
                render_badge("No equity stress to cross-check", "#e5e7eb", "#374151")
            elif hy_relative is None:
                render_badge("Credit data unavailable", "#e5e7eb", "#374151")
            elif hy_relative < -0.4 * scale:
                render_badge("Credit stress building - spreads widening", "#fee2e2", "#991b1b")
            else:
                render_badge("Routine pullback - credit stable", "#d1fae5", "#065f46")


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

render_market_regime_section()
st.divider()

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

    render_group_cards(table, cols_per_row=cols_per_row, max_card_height=max_card_height)

    st.divider()
    render_movers_news(table, ascending=False, heading="Top 5 Movers: Why They Moved")
    render_movers_news(table, ascending=True, heading="Bottom 5 Movers: Why They Moved")
