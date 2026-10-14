"""Market Scan v2.0 — Cross-Asset Tactical Intelligence Dashboard.

Features:
- Tab 1: Multi-Asset Tactical Ratings Table (12 securities across 4 quantitative dimensions:
         Primary Trend, Macro Environment, Daily Correlated Assets, Tactical Technicals)
- Tab 2: Currency Strength vs JPY Chart (Pine Script Relative Strength model)
- Tab 3: Quantitative Logic & Methodology Guide (transparent criteria & matrix for user audit)
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from metrics import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_price_vs_sma,
    calculate_rsi,
    last_close,
    last_date,
    pct_change,
)
from storage import get_connection, get_db_last_write_time, get_prices
from tactical_engine import (
    MACRO_QUADRANT_MATRIX,
    TARGET_SECURITIES,
    SecurityRating,
    compute_v2_dashboard_ratings,
)

JPY_STRENGTH_PAIRS = {
    "AUDJPY=X": ("AUD", "#10b981"),
    "EURJPY=X": ("EUR", "#3b82f6"),
    "USDJPY=X": ("USD", "#ef4444"),
    "NZDJPY=X": ("NZD", "#d946ef"),
    "CHFJPY=X": ("CHF", "#64748b"),
    "GBPJPY=X": ("GBP", "#eab308"),
    "CADJPY=X": ("CAD", "#06b6d4"),
}

st.set_page_config(
    page_title="Market Scan v2.0 — Tactical Matrix",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(ttl=120)
def load_v2_ratings():
    conn = get_connection()
    try:
        ratings, macro_rep = compute_v2_dashboard_ratings(conn)
        return ratings, macro_rep
    finally:
        conn.close()


@st.cache_data(ttl=300)
def build_jpy_strength_data() -> tuple[pd.DataFrame, list[str]]:
    conn = get_connection()
    series = {}
    missing_pairs = []
    try:
        for ticker, (currency, _) in JPY_STRENGTH_PAIRS.items():
            prices = get_prices(conn, ticker)
            strength = calculate_price_vs_sma(prices, window=200)
            if strength.empty:
                missing_pairs.append(ticker)
                continue
            series[currency] = strength.rename(currency)
    finally:
        conn.close()

    if not series:
        return pd.DataFrame(), missing_pairs
    return pd.concat(series.values(), axis=1, sort=False).sort_index(), missing_pairs


def badge_html(rating: str) -> str:
    color_map = {
        "Bullish": {"bg": "rgba(16, 185, 129, 0.15)", "text": "#10b981", "border": "#10b981", "icon": "🟢"},
        "Neutral": {"bg": "rgba(234, 179, 8, 0.15)", "text": "#eab308", "border": "#eab308", "icon": "🟡"},
        "Bearish": {"bg": "rgba(239, 68, 68, 0.15)", "text": "#ef4444", "border": "#ef4444", "icon": "🔴"},
    }
    cfg = color_map.get(rating, {"bg": "#334155", "text": "#94a3b8", "border": "#64748b", "icon": "⚪"})
    return (
        f"<span style='display:inline-flex;align-items:center;padding:0.25rem 0.65rem;"
        f"border-radius:999px;font-size:0.82rem;font-weight:700;"
        f"background:{cfg['bg']};color:{cfg['text']};border:1px solid {cfg['border']};'>"
        f"{cfg['icon']} {rating}"
        f"</span>"
    )


# --- TOP APP HEADER ---
ratings, macro_rep = load_v2_ratings()
db_updated_at = get_db_last_write_time()
as_of_date = max((r.as_of for r in ratings if r.as_of), default="N/A")

st.markdown(
    """
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.75rem;">
        <div>
            <h1 style="margin:0; font-size:2rem; font-weight:800; letter-spacing:-0.5px;">
                ⚡ Market Scan <span style="color:#38bdf8;">v2.0</span>
            </h1>
            <p style="margin:0.2rem 0 0 0; color:#94a3b8; font-size:0.95rem;">
                Cross-Asset Tactical Matrix: Trend, Macro Quadrant, Intermarket Correlations & Technical Health
            </p>
        </div>
        <div style="text-align:right;">
            <span style="background:rgba(56, 189, 248, 0.12); color:#38bdf8; padding:0.3rem 0.8rem; border-radius:8px; font-weight:600; font-size:0.85rem; border:1px solid rgba(56, 189, 248, 0.3);">
                Dashboard v2.0 Active
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Macro Overview KPI Cards
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
with col_m1:
    with st.container(border=True):
        st.caption("Active Macro Quadrant")
        st.markdown(f"**{macro_rep.quadrant_name.split('/')[0].strip()}**")
        st.caption(f"Tag: `{macro_rep.quadrant_tag}`")
with col_m2:
    with st.container(border=True):
        st.caption("Growth Impulse")
        g_color = "#10b981" if macro_rep.growth_score >= 0 else "#ef4444"
        st.markdown(f"<span style='font-size:1.4rem;font-weight:700;color:{g_color};'>{macro_rep.growth_score:+.1f}</span>", unsafe_allow_html=True)
        st.caption("Range: -100 to +100")
with col_m3:
    with st.container(border=True):
        st.caption("Inflation Impulse")
        i_color = "#f97316" if macro_rep.inflation_score >= 0 else "#38bdf8"
        st.markdown(f"<span style='font-size:1.4rem;font-weight:700;color:{i_color};'>{macro_rep.inflation_score:+.1f}</span>", unsafe_allow_html=True)
        st.caption("Range: -100 to +100")
with col_m4:
    with st.container(border=True):
        st.caption("Risk Sentiment Score")
        s_score = macro_rep.risk_sentiment_score
        s_color = "#10b981" if s_score >= 60 else ("#ef4444" if s_score <= 40 else "#eab308")
        st.markdown(f"<span style='font-size:1.4rem;font-weight:700;color:{s_color};'>{s_score:.1f} / 100</span>", unsafe_allow_html=True)
        st.caption(macro_rep.risk_sentiment_label.split("(")[0].strip())
with col_m5:
    with st.container(border=True):
        st.caption("Market Data As Of")
        st.markdown(f"**{as_of_date}**")
        st.caption(f"DB Synced: {db_updated_at[:10] if db_updated_at else 'Active'}")

# --- TABS DEFINITION ---
tab_matrix, tab_currency, tab_logic = st.tabs([
    "📊 Tactical Ratings Table",
    "💱 Currency Strength vs JPY",
    "📘 Methodology & Logic Rules",
])


# =============================================================
# TAB 1: TACTICAL RATINGS TABLE
# =============================================================
with tab_matrix:
    st.markdown("### Cross-Asset Quantitative Rating Matrix")
    st.caption(
        "Real-time institutional ratings across **Primary Trend (100 EMA)**, "
        "**Macro Environment (4 Quadrants)**, **Daily Correlated Assets**, and **Tactical Technicals**."
    )

    # Filter controls
    f_col1, f_col2, f_col3 = st.columns([2, 2, 3])
    with f_col1:
        category_filter = st.selectbox("Asset Class Filter", ["All Assets", "FX", "Equities", "Commodities"], index=0)
    with f_col2:
        stance_filter = st.selectbox("Consensus Stance Filter", ["All Stances", "Bullish", "Neutral", "Bearish"], index=0)
    with f_col3:
        search_query = st.text_input("Search Security", placeholder="e.g. Gold, US500, AUDUSD...").strip().lower()

    # Filtered list
    filtered_ratings = ratings
    if category_filter != "All Assets":
        filtered_ratings = [r for r in filtered_ratings if r.category == category_filter]
    if stance_filter != "All Stances":
        filtered_ratings = [r for r in filtered_ratings if r.overall_stance == stance_filter]
    if search_query:
        filtered_ratings = [
            r for r in filtered_ratings
            if search_query in r.symbol.lower() or search_query in r.name.lower() or search_query in r.category.lower()
        ]

    # Stance distribution summary badges
    bull_count = sum(1 for r in ratings if r.overall_stance == "Bullish")
    neut_count = sum(1 for r in ratings if r.overall_stance == "Neutral")
    bear_count = sum(1 for r in ratings if r.overall_stance == "Bearish")

    st.markdown(
        f"""
        <div style="display:flex;gap:1.5rem;align-items:center;margin:0.6rem 0 1rem 0;padding:0.6rem 1rem;background:rgba(255,255,255,0.03);border-radius:8px;border:1px solid rgba(255,255,255,0.08);">
            <span style="font-size:0.88rem;color:#94a3b8;font-weight:600;">12-Asset Sentiment Overview:</span>
            <span>🟢 <b>{bull_count}</b> Bullish</span>
            <span>🟡 <b>{neut_count}</b> Neutral</span>
            <span>🔴 <b>{bear_count}</b> Bearish</span>
            <span style="margin-left:auto;color:#64748b;font-size:0.82rem;">Showing {len(filtered_ratings)} of 12 tracked securities</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render Table via HTML
    rows_html = []
    for r in filtered_ratings:
        chg_color = "#10b981" if r.daily_change_pct >= 0 else "#ef4444"
        chg_sign = "+" if r.daily_change_pct >= 0 else ""
        px_fmt = f"{r.last_price:.4f}" if r.last_price < 10 else f"{r.last_price:,.2f}"

        # Stance badge
        score_pill = (
            f"<span style='font-size:0.78rem;font-weight:700;padding:0.2rem 0.5rem;border-radius:4px;"
            f"background:{'rgba(16,185,129,0.2)' if r.net_score > 0 else ('rgba(239,68,68,0.2)' if r.net_score < 0 else 'rgba(234,179,8,0.2)')};"
            f"color:{'#10b981' if r.net_score > 0 else ('#ef4444' if r.net_score < 0 else '#eab308')};'>"
            f"{r.overall_stance} ({r.net_score:+d})"
            f"</span>"
        )

        rows_html.append(
            f"""
            <tr style="border-bottom:1px solid rgba(255,255,255,0.07); height:3.2rem;">
                <td style="padding:0.6rem 0.8rem; font-weight:700; font-size:1.02rem;">
                    {r.symbol}
                    <div style="font-size:0.75rem; color:#94a3b8; font-weight:400;">{r.name}</div>
                </td>
                <td style="padding:0.6rem 0.8rem;">
                    <span style="font-size:0.75rem; background:rgba(255,255,255,0.06); padding:0.2rem 0.5rem; border-radius:4px; color:#cbd5e1;">{r.category}</span>
                </td>
                <td style="padding:0.6rem 0.8rem; font-family:monospace; font-size:0.96rem;">
                    <b>{px_fmt}</b>
                    <div style="font-size:0.75rem; color:{chg_color}; font-weight:600;">{chg_sign}{r.daily_change_pct:.2f}%</div>
                </td>
                <td style="padding:0.6rem 0.8rem;">
                    {badge_html(r.primary_trend)}
                    <div style="font-size:0.72rem; color:#94a3b8; margin-top:2px;">{r.primary_trend_details['dist_pct']:+.1f}% vs 100EMA</div>
                </td>
                <td style="padding:0.6rem 0.8rem;">
                    {badge_html(r.macro_environment)}
                    <div style="font-size:0.72rem; color:#94a3b8; margin-top:2px;">{macro_rep.quadrant_name.split('/')[0].strip()}</div>
                </td>
                <td style="padding:0.6rem 0.8rem;">
                    {badge_html(r.correlated_assets)}
                    <div style="font-size:0.72rem; color:#94a3b8; margin-top:2px;">Impulse: {r.correlated_details['impulse_pct']:+.2f}%</div>
                </td>
                <td style="padding:0.6rem 0.8rem;">
                    {badge_html(r.tactical_technicals)}
                    <div style="font-size:0.72rem; color:#94a3b8; margin-top:2px;">RSI: {r.tactical_details['rsi']:.1f} | Score: {r.tactical_details['score']:+d}/4</div>
                </td>
                <td style="padding:0.6rem 0.8rem; text-align:center;">
                    {score_pill}
                </td>
            </tr>
            """
        )

    table_html = f"""
    <div style="overflow-x:auto; border:1px solid rgba(255,255,255,0.1); border-radius:8px;">
        <table style="width:100%; border-collapse:collapse; text-align:left; font-size:0.9rem;">
            <thead>
                <tr style="background:rgba(255,255,255,0.05); border-bottom:1px solid rgba(255,255,255,0.12); color:#94a3b8; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.5px;">
                    <th style="padding:0.75rem 0.8rem;">Security</th>
                    <th style="padding:0.75rem 0.8rem;">Asset Class</th>
                    <th style="padding:0.75rem 0.8rem;">Price & 1D Move</th>
                    <th style="padding:0.75rem 0.8rem;">Primary Trend (100 EMA)</th>
                    <th style="padding:0.75rem 0.8rem;">Macro Environment (4 Quadrants)</th>
                    <th style="padding:0.75rem 0.8rem;">Daily Correlated Assets</th>
                    <th style="padding:0.75rem 0.8rem;">Tactical Technicals</th>
                    <th style="padding:0.75rem 0.8rem; text-align:center;">Consensus Stance</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows_html)}
            </tbody>
        </table>
    </div>
    """
    st.markdown(table_html, unsafe_allow_html=True)

    # --- DEEP-DIVE INSPECTION ACCORDION ---
    st.markdown("---")
    st.subheader("🔍 Deep-Dive Security Inspection")
    st.caption("Select any instrument to view its granular sub-components, technical indicators, and correlated driver impulses.")

    selected_symbol = st.selectbox(
        "Select Security to Inspect",
        options=[r.symbol for r in ratings],
        format_func=lambda s: f"{s} — {next(r.display_name for r in ratings if r.symbol == s)}",
    )

    sec_match = next(r for r in ratings if r.symbol == selected_symbol)

    d_col1, d_col2 = st.columns([1, 1])

    with d_col1:
        with st.container(border=True):
            st.markdown(f"#### 📈 {sec_match.symbol} Rating Synthesis")
            st.markdown(f"**Asset Class:** {sec_match.category} | **Ticker:** `{sec_match.ticker}` | **Price:** `{sec_match.last_price:.4f}`")
            
            st.markdown(f"- **Primary Trend:** {badge_html(sec_match.primary_trend)} — {sec_match.primary_trend_details['summary']}", unsafe_allow_html=True)
            st.markdown(f"- **Macro Quadrant:** {badge_html(sec_match.macro_environment)} — {sec_match.macro_details['rationale']}", unsafe_allow_html=True)
            st.markdown(f"- **Daily Correlated Assets:** {badge_html(sec_match.correlated_assets)} — {sec_match.correlated_details['summary']}", unsafe_allow_html=True)
            st.markdown(f"- **Tactical Technicals:** {badge_html(sec_match.tactical_technicals)} — {sec_match.tactical_details['summary']}", unsafe_allow_html=True)

            st.markdown("##### 🛠️ Technical Breakdown")
            tb = sec_match.tactical_details.get("breakdown", {})
            for ind_name, ind_val in tb.items():
                st.markdown(f"- **{ind_name}:** `{ind_val['signal']}` — {ind_val['desc']}")

    with d_col2:
        with st.container(border=True):
            st.markdown(f"#### 🌐 Intermarket Correlated Drivers")
            st.caption("60-day empirical return correlations and current-day impulse:")
            driver_list = sec_match.correlated_details.get("drivers", [])
            if driver_list:
                d_df = pd.DataFrame([
                    {
                        "Driver Ticker": d["ticker"],
                        "Name": d["name"],
                        "60D Correlation": f"{d['correlation']:+.2f}",
                        "Today Return": f"{d['daily_change_pct']:+.2f}%",
                        "Impulse Impact": f"{d['impulse']:+.3f}%",
                    }
                    for d in driver_list
                ])
                st.dataframe(d_df, use_container_width=True, hide_index=True)
            else:
                st.info("No correlated drivers data available.")

    # Price Chart with 100 EMA and 20 EMA
    conn = get_connection()
    sec_prices = get_prices(conn, sec_match.ticker)
    conn.close()

    if not sec_prices.empty and len(sec_prices) >= 30:
        with st.expander(f"📊 Interactive Technical Chart: {sec_match.symbol} (with 100 EMA, 20 EMA & Bollinger Bands)", expanded=False):
            closes = sec_prices["close"].dropna()
            ema100_s = closes.ewm(span=100, adjust=False).mean()
            ema20_s = closes.ewm(span=20, adjust=False).mean()
            bb_mid = closes.rolling(20).mean()
            bb_std = closes.rolling(20).std()
            bb_upper = bb_mid + (2 * bb_std)
            bb_lower = bb_mid - (2 * bb_std)

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=closes.index, y=closes, name="Close Price", line={"color": "#38bdf8", "width": 2}))
            fig.add_trace(go.Scatter(x=closes.index, y=ema100_s, name="100 EMA (Primary)", line={"color": "#f59e0b", "width": 2, "dash": "dash"}))
            fig.add_trace(go.Scatter(x=closes.index, y=ema20_s, name="20 EMA (Tactical)", line={"color": "#a855f7", "width": 1.5}))
            fig.add_trace(go.Scatter(x=closes.index, y=bb_upper, name="BB Upper (20,2)", line={"color": "#64748b", "width": 1, "dash": "dot"}))
            fig.add_trace(go.Scatter(x=closes.index, y=bb_lower, name="BB Lower (20,2)", line={"color": "#64748b", "width": 1, "dash": "dot"}, fill="tonexty", fillcolor="rgba(100, 116, 139, 0.05)"))

            fig.update_layout(
                height=450,
                hovermode="x unified",
                legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
                margin={"l": 20, "r": 20, "t": 20, "b": 20},
                yaxis={"title": "Price"},
                xaxis={
                    "rangeselector": {
                        "buttons": [
                            {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
                            {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
                            {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
                            {"step": "all", "label": "All"},
                        ]
                    },
                    "rangeslider": {"visible": False},
                },
            )
            st.plotly_chart(fig, use_container_width=True)


# =============================================================
# TAB 2: CURRENCY STRENGTH CHART
# =============================================================
with tab_currency:
    st.subheader("Currency Strength vs JPY")
    st.caption(
        "Institutional relative strength versus Japanese Yen (JPY), matching the supplied TradingView Pine Script: "
        "`(Close - 200 SMA) / Close`. Positive readings indicate structural outperformance above the 200-day trend."
    )

    strength_data, missing_pairs = build_jpy_strength_data()
    if strength_data.empty:
        st.warning("No indicator history is available yet. Run `python src/fetch.py` to fetch daily history.")
    else:
        if missing_pairs:
            st.info("Missing pairs for: " + ", ".join(missing_pairs))

        # Currency strength leaderboard cards
        latest_vals = strength_data.iloc[-1].dropna().sort_values(ascending=False)
        st.markdown("##### 🏆 Current JPY Relative Strength Leaderboard")
        rank_cols = st.columns(len(latest_vals))
        for idx, (curr, val) in enumerate(latest_vals.items()):
            with rank_cols[idx]:
                with st.container(border=True):
                    st.caption(f"Rank #{idx+1}")
                    st.markdown(f"**{curr}**")
                    val_color = "#10b981" if val >= 0 else "#ef4444"
                    st.markdown(f"<span style='color:{val_color};font-weight:700;'>{val:+.2%}</span>", unsafe_allow_html=True)

        fig_strength = go.Figure()
        for ticker, (currency, color) in JPY_STRENGTH_PAIRS.items():
            if currency not in strength_data:
                continue
            fig_strength.add_trace(go.Scatter(
                x=strength_data.index,
                y=strength_data[currency],
                mode="lines",
                name=currency,
                line={"color": color, "width": 2.2},
                hovertemplate="%{x|%Y-%m-%d}<br><b>" + currency + "</b>: %{y:.2%}<extra></extra>",
            ))
        fig_strength.add_hline(y=0, line_color="#94a3b8", line_dash="dot", line_width=1.5, annotation_text="200 SMA Baseline")
        fig_strength.update_layout(
            height=600,
            hovermode="x unified",
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
            margin={"l": 20, "r": 20, "t": 20, "b": 20},
            yaxis={"title": "Distance from 200-day SMA (%)", "tickformat": ".1%", "zeroline": False},
            xaxis={
                "title": None,
                "rangeselector": {
                    "buttons": [
                        {"count": 3, "label": "3M", "step": "month", "stepmode": "backward"},
                        {"count": 6, "label": "6M", "step": "month", "stepmode": "backward"},
                        {"count": 1, "label": "1Y", "step": "year", "stepmode": "backward"},
                        {"step": "all", "label": "All"},
                    ]
                },
                "rangeslider": {"visible": False},
            },
        )
        st.plotly_chart(fig_strength, use_container_width=True)

        with st.expander("ℹ️ Pine Script Formula & Calculation Rules"):
            st.code(
                """
// TradingView Pine Script: Relative Strength v JPY
study(title="Relative Strength v JPY", precision=3)
ma = sma(close, 200)

strengthSec = ((close - ma) / close)
plot(strengthSec, title='Currency Strength', linewidth=2)
                """,
                language="c",
            )


# =============================================================
# TAB 3: QUANTITATIVE LOGIC & METHODOLOGY GUIDE
# =============================================================
with tab_logic:
    st.subheader("Quantitative Methodology & Rating Rules")
    st.caption("Comprehensive logic definitions for user verification across all 4 rating columns.")

    # Section 1: Primary Trend
    with st.expander("1️⃣ Column 1: Primary Trend (based on 100-day EMA)", expanded=True):
        st.markdown(r"""
        #### Objective
        Identifies whether the macro/institutional multi-month trend direction is upward, downward, or consolidating.

        #### Mathematical Model
        1. Compute the **100-day Exponential Moving Average (EMA)** of daily closing prices:
           $$\text{EMA}_{100, t} = \text{Close}_t \times \alpha + \text{EMA}_{100, t-1} \times (1 - \alpha), \quad \alpha = \frac{2}{100 + 1}$$
        2. Calculate the percentage distance of current Close from the 100-day EMA:
           $$\Delta\% = \frac{\text{Close} - \text{EMA}_{100}}{\text{EMA}_{100}} \times 100$$
        3. Measure the 5-day slope of the 100-day EMA to verify trendline acceleration.

        #### Decision Rules
        - **🟢 Bullish:** Close is above the 100-day EMA by $\ge +0.30\%$ (confirms price dominance over structural institutional average).
        - **🔴 Bearish:** Close is below the 100-day EMA by $\le -0.30\%$ (confirms structural downtrend below institutional average).
        - **🟡 Neutral:** Close is within $\pm 0.30\%$ of the 100-day EMA (indicates consolidation, inflection test, or trend transition).
        """)

    # Section 2: Macro Environment 4 Quadrants
    with st.expander("2️⃣ Column 2: Macro Environment (4-Quadrant Cycle Matrix)", expanded=True):
        st.markdown(r"""
        #### Objective
        Evaluates the macro regime using the **Growth vs. Inflation 4-Quadrant Framework** and determines whether the active regime is fundamentally a tailwind or headwind for each security.

        #### The 4 Macro Quadrants
        - **Quadrant 1 — Goldilocks / Disinflationary Expansion:** Growth $\ge 0$, Inflation $\le 0$. High risk appetite, strong corporate margins, soft USD liquidity.
        - **Quadrant 2 — Reflation / Overheating Expansion:** Growth $\ge 0$, Inflation $> 0$. Booming industrial production, surging commodity demand, rising interest rate yields.
        - **Quadrant 3 — Stagflation / Late Cycle Squeeze:** Growth $< 0$, Inflation $> 0$. Margin compression, decelerating output, supply frictions, capital flight to real stores of value.
        - **Quadrant 4 — Contraction / Deflationary Risk-Off:** Growth $< 0$, Inflation $\le 0$. Global demand destruction, de-leveraging, flight to cash and sovereign duration.

        #### Institutional Asset Class Macro Matrix
        Below is the institutional classification for each of the 12 securities across all 4 macro quadrants:
        """)

        # Generate matrix table
        matrix_rows = []
        for sec in TARGET_SECURITIES:
            sym = sec["symbol"]
            rules = MACRO_QUADRANT_MATRIX[sym]
            matrix_rows.append({
                "Security": sym,
                "Category": sec["category"],
                "Goldilocks (G>0, I≤0)": f"{rules['EXPANSION_GOLDILOCKS']['rating']}",
                "Reflation (G>0, I>0)": f"{rules['EXPANSION_REFLATION']['rating']}",
                "Stagflation (G<0, I>0)": f"{rules['STAGFLATION_LATE_CYCLE']['rating']}",
                "Contraction (G<0, I≤0)": f"{rules['CONTRACTION_RISK_OFF']['rating']}",
            })
        st.dataframe(pd.DataFrame(matrix_rows), use_container_width=True, hide_index=True)

        st.caption(f"Currently Active Macro Quadrant: **{macro_rep.quadrant_name}** (`{macro_rep.quadrant_tag}`).")

    # Section 3: Daily Correlated Assets
    with st.expander("3️⃣ Column 3: Daily Correlated Assets (Intermarket Transmission)", expanded=True):
        st.markdown(r"""
        #### Objective
        Quantifies whether the current day's moves in fundamentally correlated benchmark assets (e.g. DXY, Treasury Yields, Copper, Oil, Equity indices) provide a tailwind or headwind for the target asset.

        #### Mathematical Model
        1. For each target security, 3 to 4 key benchmark drivers are monitored.
        2. Calculate the **60-trading-day rolling Pearson correlation** ($\rho_i$) between daily returns of target asset and each driver asset:
           $$\rho_i = \text{Corr}(R_{\text{target}}, R_{\text{driver}, i})$$
        3. Capture the current day's % return ($R_{\text{today}, i}$) for each driver asset.
        4. Compute the **Weighted Correlated Impulse**:
           $$\text{Impulse} = \frac{\sum_i \rho_i \times R_{\text{today}, i}}{\sum_i |\rho_i|}$$

        #### Decision Rules
        - **🟢 Bullish:** Correlated Impulse $> +0.05\%$ (intermarket drivers are expanding in favor of the asset).
        - **🔴 Bearish:** Correlated Impulse $< -0.05\%$ (intermarket drivers are creating external drag).
        - **🟡 Neutral:** Correlated Impulse between $-0.05\%$ and $+0.05\%$ (balanced or offsetting intermarket moves).

        #### Correlated Drivers Universe
        """)
        drivers_summary = []
        for sec in TARGET_SECURITIES:
            d_names = [f"{d[1]} ({d[0]})" for d in sec["correlated_drivers"]]
            drivers_summary.append({
                "Security": sec["symbol"],
                "Tracked Correlated Drivers": ", ".join(d_names),
            })
        st.dataframe(pd.DataFrame(drivers_summary), use_container_width=True, hide_index=True)

    # Section 4: Tactical Technicals
    with st.expander("4️⃣ Column 4: Tactical Technicals (Multi-Factor Quantitative Composite)", expanded=True):
        st.markdown(r"""
        #### Objective
        Combines fast-moving trend, momentum, volatility channel, and moving average alignment indicators into a single unified technical score.

        #### The 4 Quantitative Component Factors
        1. **20-day Exponential Moving Average (20 EMA):**
           - $\text{Price} > \text{EMA}_{20} \implies \mathbf{+1}$ point (short-term uptrend)
           - $\text{Price} < \text{EMA}_{20} \implies \mathbf{-1}$ point (short-term downtrend)
        2. **14-day Relative Strength Index (RSI 14):**
           - $\text{RSI} > 55.0 \implies \mathbf{+1}$ point (bullish momentum expansion)
           - $\text{RSI} < 45.0 \implies \mathbf{-1}$ point (bearish momentum expansion)
           - $45.0 \le \text{RSI} \le 55.0 \implies \mathbf{0}$ points (neutral momentum)
        3. **Bollinger Bands %B (20 period, 2.0 std):**
           - $\%B = \frac{\text{Close} - \text{LowerBand}}{\text{UpperBand} - \text{LowerBand}}$
           - $\%B > 0.60 \implies \mathbf{+1}$ point (upper channel expansion / bullish positioning)
           - $\%B < 0.40 \implies \mathbf{-1}$ point (lower channel contraction / bearish positioning)
           - $0.40 \le \%B \le 0.60 \implies \mathbf{0}$ points (mean equilibrium)
        4. **Short-Term Trend Alignment (10 EMA vs 20 EMA):**
           - $\text{EMA}_{10} > \text{EMA}_{20} \implies \mathbf{+1}$ point (bullish moving average stack)
           - $\text{EMA}_{10} < \text{EMA}_{20} \implies \mathbf{-1}$ point (bearish moving average stack)

        #### Composite Score & Rating Thresholds
        $$\text{Composite Score} = \sum \text{Factor Points} \quad \in [-4, +4]$$

        - **🟢 Bullish:** Composite Score $\ge +2$ (robust multi-indicator technical alignment).
        - **🔴 Bearish:** Composite Score $\le -2$ (broad multi-indicator technical breakdown).
        - **🟡 Neutral:** Composite Score $\in \{-1, 0, +1\}$ (mixed or conflicting indicators).
        """)
