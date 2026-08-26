"""Streamlit dashboard: Market Regime, Early Warning Radar, Top 3 Swing Trades, and Central Banks."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml

from central_banks import get_central_banks_report
from early_signals import scan_early_signals
from metrics import (
    calculate_rsi,
    calculate_sma,
    last_close,
    last_date,
    pct_change,
)
from regime import calculate_macro_regime
from storage import get_connection, get_db_last_write_time, get_prices
from swing_screener import generate_trade_chart, scan_swing_trades

WATCHLIST_PATH = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"

st.set_page_config(
    page_title="Market Scan — Macro Regime, Central Banks & Swing Trading",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


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
        rsi = calculate_rsi(prices, 14)
        sma20 = calculate_sma(prices, 20)
        px_close = last_close(prices)
        records.append({
            "Ticker": entry["ticker"],
            "Group": entry["group"],
            "Description": entry["note"],
            "% Change": pct_change(prices, period),
            "Last Close": px_close,
            "RSI (14)": round(rsi, 1) if rsi is not None else None,
            "Above 20 SMA": "Yes" if (px_close and sma20 and px_close > sma20) else "No",
            "As Of": last_date(prices),
        })
    conn.close()
    df = pd.DataFrame(records)
    return df.sort_values("% Change", ascending=False, na_position="last")


def color_pct(val):
    if pd.isna(val):
        return ""
    color = "#10b981" if val >= 0 else "#ef4444"
    return f"color: {color}; font-weight: 600"


def render_badge(text: str, bg_color: str, text_color: str) -> None:
    st.markdown(
        (
            "<div style='display:inline-block;padding:0.25rem 0.75rem;"
            "border-radius:999px;font-size:0.85rem;font-weight:600;"
            f"background:{bg_color};color:{text_color};margin-right:0.5rem;'>"
            f"{text}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=1800)
def get_news_articles(ticker: str, description: str, limit: int = 5) -> list[dict]:
    query_parts = [ticker, description, "market move reason"]
    query = " ".join(part for part in query_parts if part)
    rss_url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )
    req = Request(rss_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(req, timeout=6) as response:
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


# -------------------------------------------------------------
# Main Header & Macro KPI Banner
# -------------------------------------------------------------
watchlist = load_watchlist()
conn = get_connection()
macro_report = calculate_macro_regime(conn)
early_report = scan_early_signals(conn)
screener_result = scan_swing_trades(watchlist, conn)
cb_report = get_central_banks_report(conn)
conn.close()

st.title("Market Scan")
st.caption("Institutional Macro Regime Analysis, Central Bank Tracker, Early Warning Radar & Actionable Swing Trade Engine")

# Expandable Overview & Framework Guide
with st.expander("📖 Dashboard Primer: How to Read & Apply This Platform", expanded=False):
    st.markdown(r"""
    ### Institutional Macro & Swing Trading Framework
    This platform operates in continuous layers to turn raw multi-asset market data into high-probability trades:
    1. **Top KPI Header (Macro Weather Report):** Identifies the prevailing economic cycle quadrant, overall risk appetite score (0–100), US Treasury yield curve structure, and active cross-asset divergences.
    2. **Macro Regime Matrix (The 'Why'):** Evaluates **Growth vs. Inflation impulses**. Different assets structurally thrive in different quadrants (e.g., Commodities thrive in *Reflation*, Tech in *Goldilocks*, Gold/Defensives in *Stagflation*, Bonds/Cash in *Contraction*).
    3. **Central Banks & Interest Rates (The Policy Anchor):** Monetary policy and policy rate differentials drive long-term currency valuations and multi-week FX trends.
    4. **Early Warning Radar (The 'When'):** Smart capital leaves footprints in leading indicators (Corporate credit spreads, Copper/Gold, AUD/JPY, Dollar squeezes) days or weeks before headline equity indices roll over.
    5. **Top 3 Swing Trades (The 'What to Trade'):** Algorithmic setups designed for **3-day to 3-week holding periods**, aligning micro technical entry setups with overarching macro tailwinds.
    """)

# Top KPI Status Cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

with kpi1:
    with st.container(border=True):
        st.markdown("**Macro Regime**")
        if "EXPANSION_GOLDILOCKS" in macro_report.quadrant_tag:
            badge_bg, badge_txt = "#d1fae5", "#065f46"
        elif "EXPANSION_REFLATION" in macro_report.quadrant_tag:
            badge_bg, badge_txt = "#fef3c7", "#92400e"
        elif "STAGFLATION" in macro_report.quadrant_tag:
            badge_bg, badge_txt = "#fee2e2", "#991b1b"
        else:
            badge_bg, badge_txt = "#fee2e2", "#991b1b"
        render_badge(macro_report.quadrant_name, badge_bg, badge_txt)
        st.caption(f"Growth: **{macro_report.growth_score:+.1f}** | Inflation: **{macro_report.inflation_score:+.1f}**")
        st.caption("ℹ️ *Determines which asset classes have fundamental tailwinds.*")

with kpi2:
    with st.container(border=True):
        st.markdown("**Risk Sentiment Score**")
        score = macro_report.risk_sentiment_score
        score_bg = "#d1fae5" if score >= 60 else ("#fee2e2" if score <= 40 else "#fef3c7")
        score_txt = "#065f46" if score >= 60 else ("#991b1b" if score <= 40 else "#92400e")
        render_badge(f"{score:.1f} / 100 — {macro_report.risk_sentiment_label}", score_bg, score_txt)
        st.caption("Composite of Equity Breadth, HYG/IEF Credit, FX Carry & USD")
        st.caption("ℹ️ *>60 = Risk-On | 40-60 = Neutral/Transition | <40 = Risk-Off*")

with kpi3:
    with st.container(border=True):
        st.markdown("**Yield Curve & Rates**")
        curve_bg = "#eff6ff" if "Steepening" in macro_report.rates_regime else "#f5f3ff"
        curve_txt = "#1e40af" if "Steepening" in macro_report.rates_regime else "#5b21b6"
        render_badge(macro_report.rates_regime, curve_bg, curve_txt)
        s10_3 = macro_report.yield_spreads.get("10Y - 3M", 0.0)
        st.caption(f"10Y-3M Spread: **{s10_3:+.2f}%** | 10Y Yield: **{macro_report.yield_levels.get('10Y (^TNX)', 0):.2f}%**")
        st.caption("ℹ️ *Slope of the yield curve drives bank lending & liquidity.*")

with kpi4:
    with st.container(border=True):
        st.markdown("**Next Central Bank Meeting**")
        if cb_report.next_upcoming_meeting:
            next_m = cb_report.next_upcoming_meeting
            render_badge(f"{next_m.flag} {next_m.bank_name}", "#eff6ff", "#1e40af")
            st.caption(f"Date: **{next_m.meeting_date}** (In **{next_m.days_left}** days)")
            st.caption(f"Current Rate: **{next_m.policy_rate:.2f}%** | Stance: `{next_m.stance}`")
        else:
            st.caption("No upcoming meetings scheduled.")

st.divider()

# -------------------------------------------------------------
# Main Application Tabs
# -------------------------------------------------------------
tab_swing, tab_macro, tab_cb, tab_signals, tab_watchlist, tab_screener, tab_news = st.tabs([
    "🎯 Top 3 Swing Trades",
    "🌐 Market Regime & Macro Matrix",
    "🏛️ Central Banks & Rates",
    "⚡ Early Signs & Inflection Radar",
    "📊 Watchlist & Group Rankings",
    "🔍 All Setups Screener",
    "📰 Movers & Catalyst News",
])

# =============================================================
# TAB 1: Top 3 Swing Trades
# =============================================================
with tab_swing:
    st.subheader("Top 3 High-Conviction Swing Trade Setups")
    st.caption("Institutional multi-day to multi-week holding plans (3-20 trading days) with diversified multi-asset exposure.")

    with st.expander("💡 Swing Trading Execution Blueprint & Risk Management Guide", expanded=False):
        st.markdown(r"""
        ### How to Trade These Setups Effectively
        - **Holding Horizon (3 to 20 Trading Days):** Swing trading captures the meat of multi-day momentum swings, avoiding intraday noise while not getting trapped in multi-month drawdowns.
        - **The 3 Strategy Archetypes:**
          1. **Trend Pullback / Dip Buy (or Rip Sell):** We identify strong primary trends (above 50 & 200 SMA) that temporarily pull back towards the 20-day Exponential Moving Average (EMA) with RSI resetting into a non-overbought zone (40–55). This offers high reward-to-risk dip entries.
          2. **Volatility Compression Breakout:** Bollinger Bands narrow into a tight squeeze (bandwidth $\le 4.0\%$). When price closes outside the envelope with expanding momentum, we ride the explosive multi-week volatility expansion.
          3. **Extreme Mean Reversion:** Assets stretched to statistical limits (RSI < 28 or > 74) at key Bollinger outer bands, looking for quick snapback trades to the 20-day mean.
        - **Risk-to-Reward Ratio ($R:R \ge 2.0:1$):** Every trade enforces a potential reward at least $2\times$ the initial dollar risk.
        - **Execution Playbook:**
          - **Entry:** Enter inside the defined Entry Zone upon confirmation.
          - **Stop Loss (Invalidation):** Placed objectively at $1.5\times$ ATR beyond structural support/resistance. If price closes beyond the stop, the trade thesis is invalidated—exit immediately without emotion.
          - **Target 1 (Primary TP):** Take $50\%$ profit off the table and **trail your Stop Loss to Breakeven (Entry Price)**.
          - **Target 2 (Runner):** Let the remaining $50\%$ run toward multi-week swing targets or trail along the 20-day EMA.
        """)

    if not screener_result.top_3_trades:
        st.info("No high-conviction swing setups matching current criteria. Explore the 'All Setups Screener' tab.")
    else:
        for idx, trade in enumerate(screener_result.top_3_trades, start=1):
            with st.container(border=True):
                col_head1, col_head2 = st.columns([3, 1])
                with col_head1:
                    dir_color = "#10b981" if trade.direction == "LONG" else "#ef4444"
                    st.markdown(
                        f"### #{idx}: <span style='color:{dir_color}; font-weight:700'>{trade.direction} {trade.ticker}</span> — {trade.description}",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"**Asset Class:** {trade.group} | **Setup Archetype:** `{trade.archetype}` | **Holding Horizon:** `{trade.holding_period}`")
                with col_head2:
                    st.metric(
                        label="Conviction Score",
                        value=f"{trade.conviction_score:.0f} / 100",
                        delta=f"R:R {trade.risk_reward_ratio:.2f}:1",
                    )

                # Metrics Grid
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Current Price", f"{trade.last_price:.4f}")
                m2.metric("Entry Zone", trade.entry_zone)
                m3.metric("Invalidation (Stop Loss)", f"{trade.stop_loss:.4f}", f"-{trade.risk_pct:.1f}%", delta_color="inverse")
                m4.metric("Target 1 (50% Take Profit)", f"{trade.target_1:.4f}", f"+{trade.reward_pct:.1f}%")
                m5.metric("Target 2 (Runner Expansion)", f"{trade.target_2:.4f}")

                # Detailed Narrative & Playbook
                col_thesis, col_rules = st.columns(2)
                with col_thesis:
                    st.markdown("**Macro & Technical Rationale:**")
                    st.info(f"🌐 **Macro Thesis:** {trade.macro_thesis}\n\n📈 **Technical Catalyst:** {trade.technical_thesis}")
                with col_rules:
                    st.markdown("**Trade Management & Risk Controls:**")
                    st.warning(
                        f"🛡️ **Invalidation Rule:** {trade.invalidation_rules}\n\n"
                        f"📊 **Indicators:** RSI (14) = `{trade.rsi_14:.1f}` | 14-Day ATR = `{trade.atr_14:.4f}` | 20 SMA = `{trade.sma20:.4f}`"
                    )

                # Detailed Expandable Step-by-Step Playbook for this specific trade
                with st.expander(f"🔍 Step-by-Step Execution Plan for {trade.direction} {trade.ticker}", expanded=False):
                    st.markdown(rf"""
                    - **Order Type:** Limit order inside **`{trade.entry_zone}`** or Market order near current close (`{trade.last_price:.4f}`).
                    - **Position Sizing:** Risk no more than $1.0\% - 1.5\%$ of total trading portfolio on this trade.
                      $$\text{{Position Units}} = \frac{{\text{{Account Size}} \times 0.01}}{{|\text{{Entry Price}} - \text{{Stop Loss}}|}}$$
                    - **Trade Day 1-3:** Monitor daily close. If price closes beyond `{trade.stop_loss:.4f}`, cut the trade cleanly.
                    - **Reaching Target 1 (`{trade.target_1:.4f}`):** Lock in half the position size (+{trade.reward_pct:.1f}% gain) and adjust stop loss on the remainder to breakeven (`{trade.entry_price:.4f}`). The trade is now mathematically risk-free.
                    - **Reaching Target 2 (`{trade.target_2:.4f}`):** Close remaining position or trail a stop along the 20-day EMA.
                    """)

                # Plotly Interactive Chart
                conn = get_connection()
                prices = get_prices(conn, trade.ticker)
                conn.close()
                if not prices.empty:
                    fig = generate_trade_chart(prices, trade)
                    st.plotly_chart(fig, use_container_width=True)

# =============================================================
# TAB 2: Market Regime & Macro Matrix
# =============================================================
with tab_macro:
    st.subheader("Global Macro Regime & Cross-Asset Framework")
    st.caption("Synchronized analysis of Growth, Inflation, Yield Curve dynamics, and Liquidity.")

    with st.expander("📚 Deep Dive: The 4-Quadrant Macro Cycle & Asset Class Dynamics", expanded=False):
        st.markdown(r"""
        ### Bridgewater / Global Macro 4-Quadrant Framework
        The financial markets are primarily driven by two macro forces: **Growth** (accelerating vs decelerating) and **Inflation** (rising vs falling).
        This creates 4 distinct economic regimes:
        
        | Quadrant | Economic Conditions | Outperforming Assets | Underperforming Assets |
        |---|---|---|---|
        | **1. Goldilocks / Expansion** | Growth ↑, Inflation ↓ / Stable | Growth Equities (Tech, Discretionary), High-Beta FX (AUD), High Yield Credit | Cash, Defensive Utilities, Volatility |
        | **2. Reflation / Overheating** | Growth ↑, Inflation ↑ | Commodities (Crude Oil, Copper, Ags), Energy (XLE), Financials (XLF), Value | Long-Duration Treasuries, High Valuation Tech |
        | **3. Stagflation / Late Cycle** | Growth ↓, Inflation ↑ | Gold (GC=F), Energy, Defensive Cash Flows (Healthcare, Staples, Utilities) | Broad Equities, High-Yield Credit, Consumer Discretionary |
        | **4. Contraction / Risk-Off** | Growth ↓, Inflation ↓ | Safe Treasuries (IEF/TLT), US Dollar (DXY Cash), Defensive Staples | Industrial Commodities, Cyclicals, High-Beta FX |
        """)

    col_q1, col_q2 = st.columns([3, 2])

    with col_q1:
        with st.container(border=True):
            st.markdown(f"### Current Regime: **{macro_report.quadrant_name}**")
            st.write(macro_report.regime_description)
            st.divider()
            st.markdown("**Tactical Asset Allocation Implications:**")
            for imp in macro_report.asset_implications:
                st.markdown(f"• **{imp.split(':')[0]}:** {imp.split(':')[1] if ':' in imp else ''}")

    with col_q2:
        with st.container(border=True):
            st.markdown("### Macro Quadrant Matrix")
            scatter_df = pd.DataFrame([{
                "Regime": macro_report.quadrant_name,
                "Growth Score": macro_report.growth_score,
                "Inflation Score": macro_report.inflation_score,
            }])
            fig_matrix = px.scatter(
                scatter_df,
                x="Growth Score",
                y="Inflation Score",
                text="Regime",
                range_x=[-100, 100],
                range_y=[-100, 100],
            )
            fig_matrix.add_hline(y=0, line_dash="dash", line_color="gray")
            fig_matrix.add_vline(x=0, line_dash="dash", line_color="gray")
            fig_matrix.update_traces(marker=dict(size=18, color="#3b82f6"), textposition="top center")
            fig_matrix.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                annotations=[
                    dict(x=50, y=-50, text="<b>Goldilocks</b><br>Growth +, Inflation -", showarrow=False, font=dict(color="#059669")),
                    dict(x=50, y=50, text="<b>Reflation</b><br>Growth +, Inflation +", showarrow=False, font=dict(color="#d97706")),
                    dict(x=-50, y=50, text="<b>Stagflation</b><br>Growth -, Inflation +", showarrow=False, font=dict(color="#dc2626")),
                    dict(x=-50, y=-50, text="<b>Contraction</b><br>Growth -, Inflation -", showarrow=False, font=dict(color="#4b5563")),
                ],
                template="plotly_white",
            )
            st.plotly_chart(fig_matrix, use_container_width=True)

    st.divider()
    st.subheader("Key Cross-Asset Ratios & Barometers")
    st.caption("Institutional cross-market ratios that reflect true capital flows and risk appetite across financial markets.")

    with st.expander("📖 Why These 6 Cross-Asset Ratios Matter", expanded=False):
        st.markdown(r"""
        - **Copper / Gold ("Dr. Copper"):** Copper is the lifeblood of physical infrastructure and industrial production, whereas Gold is the ultimate monetary safe haven. When this ratio rises, it confirms genuine global manufacturing expansion. When it drops, economic growth is stalling.
        - **Credit Spread (HYG / IEF):** High Yield corporate bonds (`HYG`) vs safe 7–10Y Treasuries (`IEF`). Bond investors are senior in the capital structure and have asymmetric downside risk; they demand higher spreads and dump junk debt weeks before stock markets realize liquidity is drying up.
        - **Gold / Silver Ratio:** Silver has extensive industrial applications (electronics, solar, manufacturing) while Gold is primarily a store of value. A surging Gold/Silver ratio (>80–85) indicates extreme market anxiety, defensive hoarding, or a liquidity squeeze.
        - **Discretionary vs Staples (XLY / XLP):** Compares luxury/lifestyle spending (`XLY` - automotive, apparel, restaurants) against non-negotiable consumer staples (`XLP` - food, household essentials). Rising ratio reflects confident consumer spending.
        - **Tech vs Utilities (XLK / XLU):** High-beta long-duration growth (`XLK`) vs regulated, bond-proxy defensive dividend utilities (`XLU`). A high ratio indicates strong risk tolerance in equity markets.
        - **FX Risk Appetite (AUD / JPY):** The Australian Dollar is tied to global commodity demand, while the Japanese Yen is a low-yielding global funding & safe-haven currency. AUD/JPY is the FX market's premier global carry trade and risk-sentiment barometer.
        """)

    r_cols = st.columns(3)
    ratio_items = list(macro_report.cross_asset_ratios.items())

    for idx, (r_name, r_data) in enumerate(ratio_items):
        with r_cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"**{r_data['name']}**")
                val_str = f"{r_data['value']:.4f}" if r_data['value'] is not None else "N/A"
                chg_str = f"{r_data['chg_1m_pct']:+.2f}% (1M)" if r_data['chg_1m_pct'] is not None else "N/A"
                delta_color = "normal" if (r_data['chg_1m_pct'] or 0) >= 0 else "inverse"
                st.metric(label="Current Ratio", value=val_str, delta=chg_str, delta_color=delta_color)
                st.caption(f"Status: **{r_data['status']}**")
                st.caption(f"💡 {r_data['desc']}")

    st.divider()
    st.subheader("US Treasury Yield Curve Structure & Rate Impulse")

    with st.expander("📈 Understanding the Yield Curve & The 4 Rate Regimes", expanded=False):
        st.markdown(r"""
        ### The 4 Yield Curve Regimes
        The slope of the Treasury yield curve (long-term yield minus short-term yield) is the master key to global debt pricing and bank liquidity:
        - **1. Bear Steepening (Current):** Long yields rise faster than short yields. Driven by accelerating growth, fiscal deficits/bond supply, or inflation expectations. Positive for commodities and financials, tough for high-valuation long-duration tech.
        - **2. Bull Steepening:** Short yields plunge faster than long yields. Driven by central bank rate cuts in response to economic slowdown or recession. Classic transition into new expansion.
        - **3. Bear Flattening:** Short yields surge faster than long yields. Driven by aggressive monetary tightening (rate hikes) by the central bank to squash inflation. Tightens conditions across all markets.
        - **4. Bull Flattening:** Long yields fall faster than short yields. Driven by cooling inflation and flight to safe duration. Bullish for government bonds and duration assets.
        """)

    yc_col1, yc_col2 = st.columns([2, 3])
    with yc_col1:
        with st.container(border=True):
            st.markdown(f"**Curve Dynamics:** `{macro_report.rates_regime}`")
            st.write(macro_report.rates_description)
            st.divider()
            for spread_name, spread_val in macro_report.yield_spreads.items():
                st.metric(spread_name, f"{spread_val:+.2f}%")
    with yc_col2:
        with st.container(border=True):
            st.markdown("**Current Yield Curve Profile**")
            yc_df = pd.DataFrame([
                {"Tenor": k, "Yield (%)": v} for k, v in macro_report.yield_levels.items()
            ])
            fig_yc = px.line(yc_df, x="Tenor", y="Yield (%)", markers=True, text="Yield (%)")
            fig_yc.update_traces(textposition="top center", line_color="#2563eb")
            fig_yc.update_layout(height=280, margin=dict(l=20, r=20, t=20, b=20), template="plotly_white")
            st.plotly_chart(fig_yc, use_container_width=True)

# =============================================================
# TAB 3: Central Banks & Interest Rates
# =============================================================
with tab_cb:
    st.subheader("Major Central Banks: Current Position & Upcoming Meetings")
    st.caption("Monetary policy stances, interest rate differentials vs. Fed, meeting schedules, and FX carry trade drivers.")

    with st.expander("📚 How Central Bank Differentials Drive FX Trends & Carry Trades", expanded=False):
        st.markdown(r"""
        ### The Mechanics of FX Carry & Monetary Divergence
        1. **Interest Rate Parity & Carry Trades:** Capital flows from low-yielding currencies (e.g. `JPY` at ~0.50%, `CHF` at 1.00%) to high-yielding currencies (e.g. `USD` at 4.625%, `GBP` at 4.50%, `AUD` at 4.10%). The investor earns the interest rate differential (*positive carry*).
        2. **Policy Divergence as a Trend Driver:** When one central bank is actively raising rates (or holding high) while another is cutting, the currency pair develops strong multi-month directional trends.
        3. **Event-Driven Volatility:** Central bank rate decisions, accompanying press conferences, and the 'dot plot' / forward guidance are the primary volatility catalysts for multi-week swing traders.
        """)

    # Top KPI Metrics for Central Banks
    cb_m1, cb_m2, cb_m3, cb_m4 = st.columns(4)
    with cb_m1:
        with st.container(border=True):
            st.markdown("**Next Upcoming Decision**")
            if cb_report.next_upcoming_meeting:
                nxt = cb_report.next_upcoming_meeting
                st.markdown(f"### {nxt.flag} {nxt.currency}")
                st.caption(f"**{nxt.bank_name}**")
                st.caption(f"🗓️ `{nxt.meeting_date}` (**In {nxt.days_left} days**)")
    with cb_m2:
        with st.container(border=True):
            st.markdown("**US Fed Benchmark Rate**")
            st.markdown(f"### {cb_report.usd_rate:.2f}%")
            st.caption("Fed Funds Target: 4.50% - 4.75%")
            st.caption("Anchor for global dollar liquidity")
    with cb_m3:
        with st.container(border=True):
            st.markdown("**Widest G10 Spread vs USD**")
            st.markdown("### -4.125% (JPY)")
            st.caption("BOJ Rate: 0.50% vs Fed: 4.625%")
            st.caption("Primary global carry trade driver")
    with cb_m4:
        with st.container(border=True):
            st.markdown("**Central Bank Normalization**")
            st.markdown("### 🇯🇵 BOJ (+5.5)")
            st.caption("Only G10 bank in active tightening cycle")
            st.caption("Trigger for global carry unwinds")

    st.divider()

    # Section A: Global Central Bank Policy Matrix
    st.subheader("Global Central Bank Policy Matrix")
    st.caption("Comparative view of G10 + MAS central banks, rate spreads against the US Dollar, and upcoming decision countdowns.")
    st.dataframe(cb_report.policy_matrix, hide_index=True, use_container_width=True)

    st.divider()

    # Section B: Policy Stance Spectrum (Plotly Bar Chart)
    col_chart, col_timeline = st.columns([3, 2])

    with col_chart:
        st.subheader("Policy Stance Spectrum (Hawkish vs. Dovish)")
        st.caption("Ranked from most Dovish (actively cutting) to most Hawkish (hiking / restrictive).")

        spectrum_data = []
        for b in sorted(cb_report.banks, key=lambda x: x.stance_score):
            spectrum_data.append({
                "Bank": f"{b.flag} {b.currency} ({b.code})",
                "Stance Score": b.stance_score,
                "Stance Label": b.stance,
                "Rate": b.rate_display,
            })
        spec_df = pd.DataFrame(spectrum_data)

        fig_spec = px.bar(
            spec_df,
            x="Stance Score",
            y="Bank",
            orientation="h",
            text="Stance Label",
            color="Stance Score",
            color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
            range_x=[-7, 8],
        )
        fig_spec.add_vline(x=0, line_dash="dash", line_color="gray", annotation_text="Neutral", annotation_position="top")
        fig_spec.update_layout(
            height=380,
            margin=dict(l=20, r=20, t=20, b=20),
            coloraxis_showscale=False,
            template="plotly_white",
        )
        fig_spec.update_traces(textposition="inside")
        st.plotly_chart(fig_spec, use_container_width=True)

    with col_timeline:
        st.subheader("Upcoming Meeting Schedule")
        st.caption("Chronological calendar of the next central bank interest rate decisions.")
        
        timeline_rows = []
        for m in cb_report.all_upcoming_meetings[:10]:
            timeline_rows.append({
                "Date": m.meeting_date,
                "Countdown": f"In {m.days_left}d",
                "Central Bank": f"{m.flag} {m.currency} ({m.bank_name.split('(')[0].strip()})",
                "Current Rate": f"{m.policy_rate:.2f}%",
            })
        st.dataframe(pd.DataFrame(timeline_rows), hide_index=True, use_container_width=True, height=350)

    st.divider()

    # Section C: Detailed Central Bank Dossiers
    st.subheader("Individual Central Bank Dossiers")
    st.caption("Policy overview, key macroeconomic drivers, and tactical FX implications per central bank.")

    cb_cols = st.columns(3)
    for idx, b in enumerate(cb_report.banks):
        with cb_cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"### {b.flag} {b.name}")
                st.markdown(f"**Policy Rate:** `{b.rate_display}` | **Spread vs Fed:** `{b.rate_spread_vs_usd:+.2f}%`")
                st.markdown(f"**Stance:** `{b.stance}` | **Chair/Governor:** {b.chair}")
                st.markdown(f"🗓️ **Next Decision:** `{b.next_meeting}` (In **{b.days_to_meeting}** days)")
                st.caption(f"**Balance Sheet:** {b.balance_sheet}")
                st.divider()
                st.markdown(f"**Policy Outlook:** {b.summary}")
                st.markdown("**Key Monitoring Drivers:**")
                for d in b.key_drivers:
                    st.markdown(f"• {d}")
                st.info(f"💱 **FX Implication ({b.fx_pair_display}):** {b.fx_implication}")

# =============================================================
# TAB 4: Early Signs & Inflection Radar
# =============================================================
with tab_signals:
    st.subheader("Early Warning Signals & Cross-Asset Divergence Radar")
    st.caption("Leading indicators and anomaly detectors designed to catch market turning points before broad index moves.")

    with st.expander("⚠️ How to Interpret Cross-Asset Divergences & Anomalies", expanded=False):
        st.markdown(r"""
        ### Why Cross-Asset Divergences Lead Price Action
        In mature trends, headline indices (like S&P 500 or Nasdaq) are often kept afloat by a handful of mega-cap stocks even as underlying market health deteriorates.
        Cross-asset divergences reveal the internal rot or internal strength before the headline indices turn:
        - **Credit vs Equities Divergence:** If equities continue higher while `HYG/IEF` spread rolls over, corporate debt investors are refusing to finance the equity optimism. This is one of the highest-probability early warning signals for an impending 3–5% equity pullback.
        - **Copper/Gold Lag:** If stocks rally but Copper/Gold breaks down, the physical industrial economy is not confirming the financial market's growth narrative.
        - **AUD/JPY Lead:** FX carry trades are highly leveraged; institutions unwind currency carries days before closing stock positions.
        - **Dollar Liquidity Squeeze (DXY > 50 SMA):** When the US Dollar surges rapidly, it drains global dollar liquidity, putting heavy downward pressure on emerging markets and dollar-denominated commodities.
        """)

    # Alert Cards
    if not early_report.alerts:
        st.success("✅ No critical cross-asset divergences or exhaustion anomalies detected. Market momentum is harmonious.")
    else:
        for alert in early_report.alerts:
            severity_icon = "🔴" if alert.severity == "HIGH" else ("🟡" if alert.severity == "MEDIUM" else "🔵")
            with st.container(border=True):
                st.markdown(f"#### {severity_icon} [{alert.category}] {alert.title}")
                st.write(alert.description)
                st.warning(f"🎯 **Tactical Action:** {alert.implication}")

    st.divider()
    col_sig1, col_sig2 = st.columns(2)

    with col_sig1:
        st.subheader("Cross-Asset Divergence Inspection Monitor")
        div_df = pd.DataFrame(early_report.divergence_matrix)
        st.dataframe(div_df, hide_index=True, use_container_width=True)

        st.subheader("Market Breadth & Participation Health")
        st.caption("Measures what percentage of the entire 59-asset universe is participating in the uptrend.")
        b1, b2 = st.columns(2)
        b1.metric("% Watchlist > 20 SMA", f"{early_report.breadth.pct_above_sma20:.1f}%")
        b2.metric("% Watchlist > 50 SMA", f"{early_report.breadth.pct_above_sma50:.1f}%")

        if early_report.breadth.overbought_tickers:
            st.caption(f"🔥 **Overbought Cluster (RSI > 70):** {', '.join(early_report.breadth.overbought_tickers)}")
        if early_report.breadth.oversold_tickers:
            st.caption(f"❄️ **Oversold Cluster (RSI < 30):** {', '.join(early_report.breadth.oversold_tickers)}")

    with col_sig2:
        st.subheader("⚡ Volatility Compression / Squeeze Radar")
        st.caption("Assets in severe Bollinger Band compression (Bandwidth ≤ 4.0%). Explosive multi-week breakout imminent.")
        with st.expander("💡 What is a Volatility Squeeze?", expanded=False):
            st.markdown(r"""
            Volatility is cyclical: **Periods of extreme low volatility are mathematically followed by explosive high volatility breakouts.**
            When Bollinger Bandwidth drops below $4.0\%$, the instrument is 'coiling like a spring'. Watch for a breakout above the upper band (buy) or below the lower band (short).
            """)
        if not early_report.squeeze_candidates:
            st.info("No instruments currently in tight volatility squeeze.")
        else:
            sq_df = pd.DataFrame([
                {
                    "Ticker": s.ticker,
                    "Bandwidth %": f"{s.bandwidth:.1f}%",
                    "RSI (14)": s.rsi,
                    "Last Close": s.last_close,
                    "Status": "Coiling for Breakout",
                }
                for s in early_report.squeeze_candidates
            ])
            st.dataframe(sq_df, hide_index=True, use_container_width=True)

# =============================================================
# TAB 5: Watchlist & Category Rankings
# =============================================================
with tab_watchlist:
    st.subheader("Watchlist Performance & Technical Health")
    st.caption("Explore price changes across asset classes with technical trend filters.")

    with st.expander("📊 Guide to Reading Watchlist Performance & Technical Indicators", expanded=False):
        st.markdown(r"""
        - **Lookback Period Toggle (Daily / Weekly / Monthly / Quarterly):**
          - *Daily:* Immediate sentiment, news reactions, and short-term volatility.
          - *Weekly / Monthly:* The core swing trading trend horizon (reveals institutional rotation).
          - *Quarterly:* Primary macro trend direction.
        - **RSI (14) Indicator:**
          - $> 70$: Overbought (extended, watch for pullback or breakout pause).
          - $40 - 60$: Balanced zone (healthy pullback support in bull markets).
          - $< 30$: Oversold (washout, potential relief rally bounce).
        - **Above 20 SMA:** Confirms short-term bullish momentum when price trades above its 20-day Simple Moving Average.
        """)

    filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])
    with filter_col1:
        period = st.radio("Lookback Period", ["Daily", "Weekly", "Monthly", "Quarterly"], horizontal=True)
    with filter_col2:
        density = st.radio("Card Layout", ["Balanced (3 Cols)", "Compact (4 Cols)", "Spacious (2 Cols)"], horizontal=True, index=0)
    with filter_col3:
        table_view = st.toggle("Table View Mode", value=False)

    cols_per_row = 4 if "Compact" in density else (2 if "Spacious" in density else 3)
    table = build_table(period)

    if table.empty:
        st.warning("No data found. Run `python src/fetch.py` to populate the database.")
    else:
        as_of = table["As Of"].dropna().max()
        db_updated_at = get_db_last_write_time()
        st.caption(f"Latest market date: **{as_of}** | Database updated: **{db_updated_at}** (local time)")

        if table_view:
            st.dataframe(
                table.style.map(color_pct, subset=["% Change"]),
                use_container_width=True,
                hide_index=True,
                height=550,
            )
        else:
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
                    card_height = min(400, 80 + (len(group_df) * 35))

                    with row_cols[idx]:
                        with st.container(border=True):
                            st.subheader(group)
                            st.caption(f"{len(group_df)} instruments")
                            st.dataframe(
                                group_df.style.map(color_pct, subset=["% Change"]),
                                use_container_width=True,
                                hide_index=True,
                                height=card_height,
                            )

# =============================================================
# TAB 6: All Setups Screener
# =============================================================
with tab_screener:
    st.subheader("Quantitative Swing Trade Screener (All 59 Assets)")
    st.caption("Filter and explore candidate setups across all three strategy archetypes.")

    with st.expander("🔍 Screener Metrics & Setup Evaluation Glossary", expanded=False):
        st.markdown(r"""
        - **Conviction Score (0 to 100):** Multi-factor score combining Trend Strength (30%), Macro Regime Alignment (30%), Risk/Reward Potential (20%), and Oscillator Reset Quality (20%). Scores $\ge 80$ represent prime high-probability setups.
        - **Entry Zone:** The allowable buy/sell range. Avoid chasing beyond the upper bound.
        - **Stop Loss:** Calculated at $1.5\times$ ATR from entry or structural swing support/resistance.
        - **Target 1 & Target 2:** Defined profit targets calculated to ensure minimum $2.0:1$ mathematical Risk-to-Reward.
        """)

    scr_col1, scr_col2, scr_col3 = st.columns(3)
    with scr_col1:
        arch_filter = st.multiselect(
            "Filter Archetype",
            ["Trend Pullback", "Volatility Breakout", "Mean Reversion"],
            default=["Trend Pullback", "Volatility Breakout", "Mean Reversion"],
        )
    with scr_col2:
        dir_filter = st.multiselect("Filter Direction", ["LONG", "SHORT"], default=["LONG", "SHORT"])
    with scr_col3:
        min_score = st.slider("Minimum Conviction Score", min_value=50, max_value=95, value=65)

    filtered_setups = [
        s for s in screener_result.all_setups
        if s.archetype in arch_filter and s.direction in dir_filter and s.conviction_score >= min_score
    ]

    if not filtered_setups:
        st.info("No setups match the selected filters.")
    else:
        st.caption(f"Showing **{len(filtered_setups)}** candidate setups:")
        full_df = pd.DataFrame([
            {
                "Direction": s.direction,
                "Ticker": s.ticker,
                "Group": s.group,
                "Description": s.description,
                "Archetype": s.archetype,
                "Conviction": f"{s.conviction_score:.0f}",
                "Horizon": s.holding_period,
                "Current Price": s.last_price,
                "Entry Zone": s.entry_zone,
                "Stop Loss": s.stop_loss,
                "Target 1": s.target_1,
                "Target 2": s.target_2,
                "R:R": f"{s.risk_reward_ratio:.2f}:1",
                "RSI (14)": s.rsi_14,
            }
            for s in filtered_setups
        ])
        st.dataframe(full_df, hide_index=True, use_container_width=True, height=500)

# =============================================================
# TAB 7: Movers & Catalyst News
# =============================================================
with tab_news:
    st.subheader("Top & Bottom Movers: Why They Moved")
    st.caption("Live Google News search analysis explaining recent price action catalysts.")

    with st.expander("📰 Connecting Price Action with Fundamental News & Catalysts", expanded=False):
        st.markdown(r"""
        - **Market Moves Need Context:** While technical charts show *where* price is going, news and economic reports explain *why* institutional capital is flowing.
        - **Signal vs Noise:** Use news to confirm if a move is backed by structural fundamental changes (e.g. interest rate decisions, OPEC supply cuts, earnings beats) or temporary noise that might offer a mean-reversion fade opportunity.
        """)

    def render_movers_news_tab(table_data: pd.DataFrame, ascending: bool, heading: str) -> None:
        movers = (
            table_data.dropna(subset=["% Change"])
            .sort_values("% Change", ascending=ascending)
            .head(5)
            .reset_index(drop=True)
        )
        if movers.empty:
            return

        st.markdown(f"### {heading}")
        tab_labels = [
            f"{row['Ticker']} ({row['% Change']:+.2f}%)"
            for _, row in movers.iterrows()
        ]
        tabs = st.tabs(tab_labels)
        for tab, (_, row) in zip(tabs, movers.iterrows()):
            with tab:
                st.markdown(f"**{row['Ticker']}** | Group: {row['Group']} | Last close: {row['Last Close']:.4f}")
                if row["Description"]:
                    st.caption(row["Description"])
                articles = get_news_articles(str(row["Ticker"]), str(row["Description"]), limit=5)
                if not articles:
                    st.info("No recent news articles found right now.")
                    continue
                for article in articles:
                    st.markdown(f"- [{article['title']}]({article['link']})")
                    st.caption(f"{article['source'] or 'Source'} | {article['pub_date'] or ''}")

    m_table = build_table("Daily")
    if not m_table.empty:
        render_movers_news_tab(m_table, ascending=False, heading="🚀 Top 5 Daily Gainers")
        st.divider()
        render_movers_news_tab(m_table, ascending=True, heading="🔻 Top 5 Daily Decliners")
