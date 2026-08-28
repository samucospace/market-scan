"""Quantitative Swing Trade Screener & Setup Generator.

Scans the 59-asset universe for high-probability swing trading setups
tailored for 3-day to 3-week holding periods across three distinct archetypes:
1. Trend Continuation & Pullback / Dip Buy (or Rip Sell)
2. Volatility Compression Breakout
3. Macro Extreme Mean Reversion

Computes an Opportunity Conviction Score (0-100), filters the Top 3 diversified
trades, and outputs actionable trade blueprints with exact Entry, SL, T1, T2 levels
and interactive Plotly chart generators.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from metrics import (
    calculate_atr,
    calculate_bollinger_bands,
    calculate_channel_extremes,
    calculate_ema,
    calculate_rsi,
    calculate_sma,
    pct_change,
)
from regime import calculate_macro_regime
from storage import get_connection, get_prices


@dataclass
class SwingTradeSetup:
    ticker: str
    group: str
    description: str
    direction: str  # "LONG" or "SHORT"
    archetype: str  # "Trend Pullback", "Volatility Breakout", "Mean Reversion"
    conviction_score: float  # 0 to 100
    holding_period: str  # e.g., "5-12 Days", "1-3 Weeks"
    last_price: float
    entry_zone: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    risk_pct: float
    reward_pct: float
    rsi_14: float
    atr_14: float
    sma20: float
    sma50: float
    macro_thesis: str
    technical_thesis: str
    invalidation_rules: str


@dataclass
class ScreenerResult:
    top_3_trades: list[SwingTradeSetup]
    all_setups: list[SwingTradeSetup]


def scan_swing_trades(
    watchlist: list[dict],
    conn: sqlite3.Connection | None = None,
) -> ScreenerResult:
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    macro = calculate_macro_regime(conn)
    setups: list[SwingTradeSetup] = []

    for item in watchlist:
        ticker = item["ticker"]
        group = item["group"]
        note = item.get("note", "")

        prices = get_prices(conn, ticker)
        if prices.empty or len(prices) < 50:
            continue

        closes = prices["close"].dropna()
        if len(closes) < 50:
            continue

        px = float(closes.iloc[-1])
        if px <= 0:
            continue

        # Indicators
        rsi = calculate_rsi(prices, 14) or 50.0
        atr = calculate_atr(prices, 14) or (px * 0.015)
        sma20 = calculate_sma(prices, 20) or px
        sma50 = calculate_sma(prices, 50) or px
        sma200 = calculate_sma(prices, 200) if len(closes) >= 200 else sma50
        ema20 = calculate_ema(prices, 20) or px
        bb = calculate_bollinger_bands(prices, 20, 2.0)

        chg_5d = pct_change(prices, 5) or 0.0
        chg_20d = pct_change(prices, 20) or 0.0
        chg_50d = pct_change(prices, 50) or 0.0

        bandwidth = bb.get("bandwidth") or 5.0
        bb_upper = bb.get("upper") or (px * 1.05)
        bb_lower = bb.get("lower") or (px * 0.95)

        # -------------------------------------------------------------
        # Archetype 1: Trend Continuation & Pullback / Dip Buy / Rip Sell
        # -------------------------------------------------------------
        # Long Pullback
        if px > sma50 and (sma50 >= sma200 or chg_50d > 0) and chg_20d > 0.8:
            dist_ema = (px - ema20) / ema20 * 100.0
            if -3.0 <= dist_ema <= 2.2 and 40.0 <= rsi <= 62.0:
                sl = px - max(1.5 * atr, px * 0.018)
                t1 = px + max(3.0 * atr, px * 0.040)
                t2 = px + max(5.0 * atr, px * 0.075)
                risk = px - sl
                reward = t1 - px
                rr = reward / risk if risk > 0 else 2.0

                score = 66.0
                if 44.0 <= rsi <= 54.0:
                    score += 10.0  # Ideal oscillator reset
                if dist_ema <= 0.8:
                    score += 8.0  # Perfect support bounce zone
                if group in ("Equity Indices", "Sector ETFs") and macro.growth_score > 0:
                    score += 10.0
                if group == "Commodities & Futures" and macro.inflation_score > 0:
                    score += 10.0
                if group == "FX" and ticker in ("AUDUSD=X", "AUDJPY=X") and macro.risk_sentiment_score > 55:
                    score += 10.0
                score = min(score, 96.0)

                setups.append(SwingTradeSetup(
                    ticker=ticker,
                    group=group,
                    description=note,
                    direction="LONG",
                    archetype="Trend Pullback",
                    conviction_score=round(score, 1),
                    holding_period="5 - 12 Days",
                    last_price=round(px, 4),
                    entry_zone=f"{round(px * 0.995, 4)} - {round(px * 1.005, 4)}",
                    entry_price=round(px, 4),
                    stop_loss=round(sl, 4),
                    target_1=round(t1, 4),
                    target_2=round(t2, 4),
                    risk_reward_ratio=round(rr, 2),
                    risk_pct=round((px - sl) / px * 100, 2),
                    reward_pct=round((t1 - px) / px * 100, 2),
                    rsi_14=round(rsi, 1),
                    atr_14=round(atr, 4),
                    sma20=round(sma20, 4),
                    sma50=round(sma50, 4),
                    macro_thesis=f"Aligned with {macro.quadrant_name} macro backdrop (Growth score {macro.growth_score:+.1f}).",
                    technical_thesis=(
                        f"Solid primary uptrend (20D: {chg_20d:+.1f}%) testing 20-day EMA support with RSI ({rsi:.1f}) "
                        f"resetting into an attractive risk/reward buy zone."
                    ),
                    invalidation_rules=f"Daily close below ${sl:.4f} (1.5x ATR below entry) invalidates the setup. Move stop to breakeven at Target 1.",
                ))

        # Short Pullback / Rip Sell
        elif px < sma50 and (sma50 <= sma200 or chg_50d < 0) and chg_20d < -0.8:
            dist_ema = (px - ema20) / ema20 * 100.0
            if -2.2 <= dist_ema <= 3.0 and 40.0 <= rsi <= 60.0:
                sl = px + max(1.5 * atr, px * 0.018)
                t1 = px - max(3.0 * atr, px * 0.040)
                t2 = px - max(5.0 * atr, px * 0.075)
                risk = sl - px
                reward = px - t1
                rr = reward / risk if risk > 0 else 2.0

                score = 65.0
                if 48.0 <= rsi <= 56.0:
                    score += 10.0
                if dist_ema >= -0.8:
                    score += 8.0
                if macro.risk_sentiment_score < 45:
                    score += 10.0
                score = min(score, 95.0)

                setups.append(SwingTradeSetup(
                    ticker=ticker,
                    group=group,
                    description=note,
                    direction="SHORT",
                    archetype="Trend Pullback",
                    conviction_score=round(score, 1),
                    holding_period="5 - 12 Days",
                    last_price=round(px, 4),
                    entry_zone=f"{round(px * 0.995, 4)} - {round(px * 1.005, 4)}",
                    entry_price=round(px, 4),
                    stop_loss=round(sl, 4),
                    target_1=round(t1, 4),
                    target_2=round(t2, 4),
                    risk_reward_ratio=round(rr, 2),
                    risk_pct=round((sl - px) / px * 100, 2),
                    reward_pct=round((px - t1) / px * 100, 2),
                    rsi_14=round(rsi, 1),
                    atr_14=round(atr, 4),
                    sma20=round(sma20, 4),
                    sma50=round(sma50, 4),
                    macro_thesis=f"Exploits macro headwinds and sector rotation under {macro.quadrant_name}.",
                    technical_thesis=(
                        f"Downtrend continuation (20D: {chg_20d:+.1f}%) rejecting the declining 20 EMA with RSI at {rsi:.1f}."
                    ),
                    invalidation_rules=f"Daily close above ${sl:.4f} invalidates the short bias. Trail stop to breakeven once Target 1 is reached.",
                ))

        # -------------------------------------------------------------
        # Archetype 2: Volatility Compression Breakout
        # -------------------------------------------------------------
        if bandwidth <= 4.5:
            # Bullish Breakout
            if px >= bb_upper * 0.99 and chg_5d > 0.6 and rsi >= 54.0:
                sl = px - max(1.6 * atr, px * 0.020)
                t1 = px + max(3.2 * atr, px * 0.045)
                t2 = px + max(5.5 * atr, px * 0.080)
                risk = px - sl
                reward = t1 - px
                rr = reward / risk if risk > 0 else 2.0

                score = 72.0 + (4.5 - bandwidth) * 4.0
                if chg_20d > 0:
                    score += 8.0
                score = min(score, 97.0)

                setups.append(SwingTradeSetup(
                    ticker=ticker,
                    group=group,
                    description=note,
                    direction="LONG",
                    archetype="Volatility Breakout",
                    conviction_score=round(score, 1),
                    holding_period="1 - 3 Weeks",
                    last_price=round(px, 4),
                    entry_zone=f"{round(px * 0.997, 4)} - {round(px * 1.008, 4)}",
                    entry_price=round(px, 4),
                    stop_loss=round(sl, 4),
                    target_1=round(t1, 4),
                    target_2=round(t2, 4),
                    risk_reward_ratio=round(rr, 2),
                    risk_pct=round((px - sl) / px * 100, 2),
                    reward_pct=round((t1 - px) / px * 100, 2),
                    rsi_14=round(rsi, 1),
                    atr_14=round(atr, 4),
                    sma20=round(sma20, 4),
                    sma50=round(sma50, 4),
                    macro_thesis=f"Volatility expansion aligned with {macro.quadrant_name} cycle tailwind.",
                    technical_thesis=(
                        f"Bollinger Band squeeze release (bandwidth {bandwidth:.1f}%) breaking above upper envelope "
                        f"with momentum expansion (5D: {chg_5d:+.1f}%)."
                    ),
                    invalidation_rules=f"Close back inside Bollinger mid-band or stop at ${sl:.4f}.",
                ))
            # Bearish Breakout
            elif px <= bb_lower * 1.01 and chg_5d < -0.6 and rsi <= 46.0:
                sl = px + max(1.6 * atr, px * 0.020)
                t1 = px - max(3.2 * atr, px * 0.045)
                t2 = px - max(5.5 * atr, px * 0.080)
                risk = sl - px
                reward = px - t1
                rr = reward / risk if risk > 0 else 2.0

                score = 70.0 + (4.5 - bandwidth) * 4.0
                score = min(score, 95.0)

                setups.append(SwingTradeSetup(
                    ticker=ticker,
                    group=group,
                    description=note,
                    direction="SHORT",
                    archetype="Volatility Breakout",
                    conviction_score=round(score, 1),
                    holding_period="1 - 3 Weeks",
                    last_price=round(px, 4),
                    entry_zone=f"{round(px * 0.992, 4)} - {round(px * 1.003, 4)}",
                    entry_price=round(px, 4),
                    stop_loss=round(sl, 4),
                    target_1=round(t1, 4),
                    target_2=round(t2, 4),
                    risk_reward_ratio=round(rr, 2),
                    risk_pct=round((sl - px) / px * 100, 2),
                    reward_pct=round((px - t1) / px * 100, 2),
                    rsi_14=round(rsi, 1),
                    atr_14=round(atr, 4),
                    sma20=round(sma20, 4),
                    sma50=round(sma50, 4),
                    macro_thesis=f"Downside volatility expansion under macro rotation and tightening.",
                    technical_thesis=(
                        f"Bollinger compression breakdown (bandwidth {bandwidth:.1f}%) through lower channel "
                        f"with negative 5D momentum ({chg_5d:+.1f}%)."
                    ),
                    invalidation_rules=f"Close back above Bollinger middle band or stop loss at ${sl:.4f}.",
                ))

        # -------------------------------------------------------------
        # Archetype 3: Macro-Extreme Mean Reversion
        # -------------------------------------------------------------
        # Oversold Long Bounce
        if rsi <= 29.0 and px <= bb_lower:
            sl = px - max(1.5 * atr, px * 0.02)
            t1 = sma20
            t2 = t1 + (1.0 * atr)
            if t1 > px:
                risk = px - sl
                reward = t1 - px
                rr = reward / risk if risk > 0 else 2.0
                score = 68.0 + (30.0 - rsi) * 1.2
                setups.append(SwingTradeSetup(
                    ticker=ticker,
                    group=group,
                    description=note,
                    direction="LONG",
                    archetype="Mean Reversion",
                    conviction_score=round(min(score, 94.0), 1),
                    holding_period="3 - 8 Days",
                    last_price=round(px, 4),
                    entry_zone=f"{round(px * 0.995, 4)} - {round(px * 1.01, 4)}",
                    entry_price=round(px, 4),
                    stop_loss=round(sl, 4),
                    target_1=round(t1, 4),
                    target_2=round(t2, 4),
                    risk_reward_ratio=round(rr, 2),
                    risk_pct=round((px - sl) / px * 100, 2),
                    reward_pct=round((t1 - px) / px * 100, 2),
                    rsi_14=round(rsi, 1),
                    atr_14=round(atr, 4),
                    sma20=round(sma20, 4),
                    sma50=round(sma50, 4),
                    macro_thesis=f"Statistical extreme oversold discount across {group} asset class.",
                    technical_thesis=(
                        f"Severe RSI exhaustion ({rsi:.1f}) piercing lower Bollinger Band with stretched 20D distance."
                    ),
                    invalidation_rules=f"Daily close below swing low at ${sl:.4f}. Close trade on first touch of 20 SMA.",
                ))
        # Overbought Short Mean Reversion
        elif rsi >= 73.0 and px >= bb_upper:
            sl = px + max(1.5 * atr, px * 0.02)
            t1 = sma20
            t2 = t1 - (1.0 * atr)
            if t1 < px:
                risk = sl - px
                reward = px - t1
                rr = reward / risk if risk > 0 else 2.0
                score = 68.0 + (rsi - 70.0) * 1.2
                setups.append(SwingTradeSetup(
                    ticker=ticker,
                    group=group,
                    description=note,
                    direction="SHORT",
                    archetype="Mean Reversion",
                    conviction_score=round(min(score, 94.0), 1),
                    holding_period="3 - 8 Days",
                    last_price=round(px, 4),
                    entry_zone=f"{round(px * 0.99, 4)} - {round(px * 1.005, 4)}",
                    entry_price=round(px, 4),
                    stop_loss=round(sl, 4),
                    target_1=round(t1, 4),
                    target_2=round(t2, 4),
                    risk_reward_ratio=round(rr, 2),
                    risk_pct=round((sl - px) / px * 100, 2),
                    reward_pct=round((px - t1) / px * 100, 2),
                    rsi_14=round(rsi, 1),
                    atr_14=round(atr, 4),
                    sma20=round(sma20, 4),
                    sma50=round(sma50, 4),
                    macro_thesis=f"Momentum overextension ripe for tactical profit-taking in {group}.",
                    technical_thesis=(
                        f"RSI overbought exhaustion ({rsi:.1f}) extended far above upper Bollinger Band."
                    ),
                    invalidation_rules=f"Daily close above upper extreme at ${sl:.4f}. Take full profit at 20-day SMA.",
                ))

    if should_close:
        conn.close()

    # Sort all setups by conviction score
    setups.sort(key=lambda s: s.conviction_score, reverse=True)

    # Pick Top 3 with Asset Class Diversity (max 1 per asset group if possible)
    top_3: list[SwingTradeSetup] = []
    used_groups: set[str] = set()

    for s in setups:
        if s.group not in used_groups and len(top_3) < 3:
            top_3.append(s)
            used_groups.add(s.group)

    if len(top_3) < 3:
        for s in setups:
            if s not in top_3 and len(top_3) < 3:
                top_3.append(s)

    return ScreenerResult(
        top_3_trades=top_3,
        all_setups=setups,
    )


def generate_trade_chart(prices: pd.DataFrame, setup: Any) -> go.Figure:
    """Generate an interactive Plotly chart with Bollinger bands, moving averages,
    and visual trade execution levels (Entry, Stop Loss, Target 1, Target 2).
    Accepts SwingTradeSetup dataclass or dict.
    """
    df = prices.tail(65).copy()
    if df.empty:
        return go.Figure()

    # Extract fields regardless of dict or object
    ticker = getattr(setup, "ticker", None) or (setup.get("ticker") if isinstance(setup, dict) else "")
    description = getattr(setup, "description", None) or (setup.get("description") if isinstance(setup, dict) else "")
    direction = getattr(setup, "direction", None) or (setup.get("direction") if isinstance(setup, dict) else "LONG")
    archetype = getattr(setup, "archetype", None) or (setup.get("archetype") if isinstance(setup, dict) else "")
    entry_price = float(getattr(setup, "entry_price", None) or (setup.get("entry_price") if isinstance(setup, dict) else 0.0))
    stop_loss = float(getattr(setup, "stop_loss", None) or (setup.get("stop_loss") if isinstance(setup, dict) else 0.0))
    target_1 = float(getattr(setup, "target_1", None) or (setup.get("target_1") if isinstance(setup, dict) else 0.0))
    target_2 = float(getattr(setup, "target_2", None) or (setup.get("target_2") if isinstance(setup, dict) else 0.0))
    risk_pct = float(getattr(setup, "risk_pct", None) or (setup.get("risk_pct") if isinstance(setup, dict) else 0.0))
    reward_pct = float(getattr(setup, "reward_pct", None) or (setup.get("reward_pct") if isinstance(setup, dict) else 0.0))
    risk_reward_ratio = float(getattr(setup, "risk_reward_ratio", None) or (setup.get("risk_reward_ratio") if isinstance(setup, dict) else 2.0))

    # Calculate indicators over the chart window
    closes = prices["close"].dropna()
    rolling_20 = closes.rolling(20).mean()
    rolling_50 = closes.rolling(50).mean()
    rolling_std = closes.rolling(20).std()
    upper_bb = rolling_20 + (2.0 * rolling_std)
    lower_bb = rolling_20 - (2.0 * rolling_std)

    df["sma20"] = rolling_20.reindex(df.index)
    df["sma50"] = rolling_50.reindex(df.index)
    df["upper_bb"] = upper_bb.reindex(df.index)
    df["lower_bb"] = lower_bb.reindex(df.index)

    fig = go.Figure()

    # Bollinger Band Shading
    fig.add_trace(go.Scatter(
        x=df.index, y=df["upper_bb"],
        mode="lines",
        line=dict(color="rgba(148, 163, 184, 0.2)", width=1),
        showlegend=False,
        name="Upper BB",
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["lower_bb"],
        mode="lines",
        line=dict(color="rgba(148, 163, 184, 0.2)", width=1),
        fill="tonexty",
        fillcolor="rgba(148, 163, 184, 0.08)",
        showlegend=False,
        name="Lower BB",
    ))

    # Candlestick or Line
    if all(col in df.columns for col in ["open", "high", "low", "close"]):
        fig.add_trace(go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=ticker,
            increasing_line_color="#10b981",
            decreasing_line_color="#ef4444",
        ))
    else:
        fig.add_trace(go.Scatter(
            x=df.index, y=df["close"],
            mode="lines",
            name="Close",
            line=dict(color="#3b82f6", width=2),
        ))

    # Moving Averages
    fig.add_trace(go.Scatter(
        x=df.index, y=df["sma20"],
        mode="lines",
        name="20 SMA",
        line=dict(color="#f59e0b", width=1.5),
    ))
    fig.add_trace(go.Scatter(
        x=df.index, y=df["sma50"],
        mode="lines",
        name="50 SMA",
        line=dict(color="#8b5cf6", width=1.5),
    ))

    # Trade Levels Lines
    # Entry
    fig.add_hline(
        y=entry_price,
        line_dash="dash",
        line_color="#3b82f6",
        line_width=1.5,
        annotation_text=f"Entry: {entry_price:.4f}",
        annotation_position="top right",
    )
    # Stop Loss
    fig.add_hline(
        y=stop_loss,
        line_dash="dot",
        line_color="#ef4444",
        line_width=2.0,
        annotation_text=f"Stop Loss: {stop_loss:.4f} (-{risk_pct:.1f}%)",
        annotation_position="bottom right",
    )
    # Target 1
    fig.add_hline(
        y=target_1,
        line_dash="dash",
        line_color="#10b981",
        line_width=2.0,
        annotation_text=f"Target 1: {target_1:.4f} (+{reward_pct:.1f}%)",
        annotation_position="top right",
    )
    # Target 2
    if target_2 > 0:
        fig.add_hline(
            y=target_2,
            line_dash="dashdot",
            line_color="#059669",
            line_width=1.5,
            annotation_text=f"Target 2: {target_2:.4f}",
            annotation_position="top right",
        )

    fig.update_layout(
        title=f"{direction} {ticker} ({description}) — {archetype} Setup (R:R {risk_reward_ratio}:1)",
        height=380,
        margin=dict(l=30, r=30, t=40, b=25),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
    )
    return fig


def evaluate_live_trade_invalidation(
    trade: dict | Any,
    conn: sqlite3.Connection,
) -> dict:
    """Evaluate real-time live performance, stop loss invalidation, indicator invalidation,
    and target hits for an active saved trade.
    """
    ticker = getattr(trade, "ticker", None) or (trade.get("ticker") if isinstance(trade, dict) else "")
    direction = str(getattr(trade, "direction", None) or (trade.get("direction") if isinstance(trade, dict) else "LONG")).upper()
    archetype = str(getattr(trade, "archetype", None) or (trade.get("archetype") if isinstance(trade, dict) else ""))
    entry_price = float(getattr(trade, "entry_price", None) or (trade.get("entry_price") if isinstance(trade, dict) else 0.0))
    stop_loss = float(getattr(trade, "stop_loss", None) or (trade.get("stop_loss") if isinstance(trade, dict) else 0.0))
    target_1 = float(getattr(trade, "target_1", None) or (trade.get("target_1") if isinstance(trade, dict) else 0.0))
    target_2 = float(getattr(trade, "target_2", None) or (trade.get("target_2") if isinstance(trade, dict) else 0.0))
    invalidation_rules = str(getattr(trade, "invalidation_rules", None) or (trade.get("invalidation_rules") if isinstance(trade, dict) else ""))

    prices = get_prices(conn, ticker)
    if prices.empty or len(prices) < 20:
        return {
            "status_flag": "UNKNOWN",
            "status_label": "⚪ UNKNOWN DATA",
            "is_invalidated": False,
            "badge_bg": "#f3f4f6",
            "badge_txt": "#4b5563",
            "current_price": entry_price,
            "unrealized_pnl_pct": 0.0,
            "unrealized_r": 0.0,
            "distance_to_sl_pct": 0.0,
            "distance_to_t1_pct": 0.0,
            "latest_rsi": 50.0,
            "latest_sma20": entry_price,
            "latest_sma50": entry_price,
            "reasons": ["No current price history available in database."],
        }

    closes = prices["close"].dropna()
    current_px = float(closes.iloc[-1])
    current_high = float(prices["high"].iloc[-1]) if "high" in prices.columns else current_px
    current_low = float(prices["low"].iloc[-1]) if "low" in prices.columns else current_px

    rsi = calculate_rsi(prices, 14) or 50.0
    sma20 = calculate_sma(prices, 20) or current_px
    sma50 = calculate_sma(prices, 50) or current_px
    ema20 = calculate_ema(prices, 20) or current_px
    bb = calculate_bollinger_bands(prices, 20, 2.0)
    bandwidth = bb.get("bandwidth", 5.0)

    # Performance calculations
    if direction == "LONG":
        unrealized_pnl_pct = (current_px - entry_price) / entry_price * 100.0 if entry_price > 0 else 0.0
        initial_risk = entry_price - stop_loss
        unrealized_r = (current_px - entry_price) / initial_risk if initial_risk > 0 else 0.0
        dist_to_sl_pct = (current_px - stop_loss) / current_px * 100.0 if current_px > 0 else 0.0
        dist_to_t1_pct = (target_1 - current_px) / current_px * 100.0 if current_px > 0 else 0.0
    else:
        unrealized_pnl_pct = (entry_price - current_px) / entry_price * 100.0 if entry_price > 0 else 0.0
        initial_risk = stop_loss - entry_price
        unrealized_r = (entry_price - current_px) / initial_risk if initial_risk > 0 else 0.0
        dist_to_sl_pct = (stop_loss - current_px) / current_px * 100.0 if current_px > 0 else 0.0
        dist_to_t1_pct = (current_px - target_1) / current_px * 100.0 if current_px > 0 else 0.0

    invalidation_reasons = []
    target_reasons = []
    warning_reasons = []
    healthy_reasons = []

    # 1. Check Stop Loss Invalidation
    if direction == "LONG":
        if current_px <= stop_loss:
            invalidation_reasons.append(f"Daily close (${current_px:.4f}) breached Stop Loss level (${stop_loss:.4f}).")
        elif current_low <= stop_loss:
            warning_reasons.append(f"Daily low (${current_low:.4f}) tagged Stop Loss (${stop_loss:.4f}), close (${current_px:.4f}) currently above.")
    else:
        if current_px >= stop_loss:
            invalidation_reasons.append(f"Daily close (${current_px:.4f}) breached Stop Loss level (${stop_loss:.4f}).")
        elif current_high >= stop_loss:
            warning_reasons.append(f"Daily high (${current_high:.4f}) tagged Stop Loss (${stop_loss:.4f}), close (${current_px:.4f}) currently below.")

    # 2. Check Indicator & Archetype-specific Invalidation
    if "Pullback" in archetype:
        if direction == "LONG":
            if current_px < sma50:
                invalidation_reasons.append(f"Price broke below primary trend 50 SMA (${sma50:.4f}).")
            if rsi < 36.0:
                invalidation_reasons.append(f"RSI collapsed to {rsi:.1f} (below pullback support floor 36.0).")
            elif 40.0 <= rsi <= 60.0:
                healthy_reasons.append(f"RSI ({rsi:.1f}) is holding within ideal pullback zone (40-60).")
        else:
            if current_px > sma50:
                invalidation_reasons.append(f"Price climbed above primary downtrend 50 SMA (${sma50:.4f}).")
            if rsi > 64.0:
                invalidation_reasons.append(f"RSI surged to {rsi:.1f} (above short invalidation ceiling 64.0).")
            elif 40.0 <= rsi <= 60.0:
                healthy_reasons.append(f"RSI ({rsi:.1f}) is holding within ideal short bounce zone.")

    elif "Breakout" in archetype:
        if direction == "LONG":
            if current_px < sma20:
                invalidation_reasons.append(f"Price fell back below 20 SMA mid-band (${sma20:.4f}), breaking breakout momentum.")
            else:
                healthy_reasons.append(f"Price is sustaining above 20 SMA mid-band (${sma20:.4f}).")
        else:
            if current_px > sma20:
                invalidation_reasons.append(f"Price rose back above 20 SMA mid-band (${sma20:.4f}), breaking breakdown momentum.")
            else:
                healthy_reasons.append(f"Price is sustaining below 20 SMA mid-band (${sma20:.4f}).")

    elif "Mean Reversion" in archetype:
        if direction == "LONG":
            if current_px >= sma20:
                target_reasons.append(f"20 SMA Mean Reversion target reached (${sma20:.4f}).")
            if rsi < 24.0:
                warning_reasons.append(f"Severe breakdown momentum with RSI at {rsi:.1f}.")
        else:
            if current_px <= sma20:
                target_reasons.append(f"20 SMA Mean Reversion target reached (${sma20:.4f}).")
            if rsi > 76.0:
                warning_reasons.append(f"Severe overbought extension with RSI at {rsi:.1f}.")

    # 3. Check Target Milestones
    if direction == "LONG":
        if target_2 > 0 and (current_high >= target_2 or current_px >= target_2):
            target_reasons.append(f"🎉 Target 2 Runner reached (${target_2:.4f}).")
        elif target_1 > 0 and (current_high >= target_1 or current_px >= target_1):
            target_reasons.append(f"🎯 Target 1 reached (${target_1:.4f}) — Lock 50% profit and trail stop to breakeven (${entry_price:.4f}).")
    else:
        if target_2 > 0 and (current_low <= target_2 or current_px <= target_2):
            target_reasons.append(f"🎉 Target 2 Runner reached (${target_2:.4f}).")
        elif target_1 > 0 and (current_low <= target_1 or current_px <= target_1):
            target_reasons.append(f"🎯 Target 1 reached (${target_1:.4f}) — Lock 50% profit and trail stop to breakeven (${entry_price:.4f}).")

    # 4. Synthesize Status
    if invalidation_reasons:
        status_flag = "INVALIDATED"
        status_label = "🚨 INVALIDATED"
        is_invalidated = True
        badge_bg = "#fee2e2"
        badge_txt = "#991b1b"
        reasons = invalidation_reasons + warning_reasons
    elif target_reasons:
        status_flag = "TARGET_HIT"
        status_label = "🎯 TARGET HIT"
        is_invalidated = False
        badge_bg = "#d1fae5"
        badge_txt = "#065f46"
        reasons = target_reasons + healthy_reasons
    elif dist_to_sl_pct < 0.6 or warning_reasons:
        status_flag = "WARNING"
        status_label = "⚠️ NEAR STOP / CAUTION"
        is_invalidated = False
        badge_bg = "#fef3c7"
        badge_txt = "#92400e"
        reasons = warning_reasons or [f"Price is within {dist_to_sl_pct:.1f}% of Stop Loss."]
    else:
        status_flag = "VALID"
        status_label = "✅ THESIS VALID & ACTIVE"
        is_invalidated = False
        badge_bg = "#ecfdf5"
        badge_txt = "#047857"
        reasons = healthy_reasons or [f"Setup is operating within expected risk boundaries. Distance to SL: {dist_to_sl_pct:+.1f}%."]

    return {
        "status_flag": status_flag,
        "status_label": status_label,
        "is_invalidated": is_invalidated,
        "badge_bg": badge_bg,
        "badge_txt": badge_txt,
        "current_price": round(current_px, 4),
        "unrealized_pnl_pct": round(unrealized_pnl_pct, 2),
        "unrealized_r": round(unrealized_r, 2),
        "distance_to_sl_pct": round(dist_to_sl_pct, 2),
        "distance_to_t1_pct": round(dist_to_t1_pct, 2),
        "latest_rsi": round(rsi, 1),
        "latest_sma20": round(sma20, 4),
        "latest_sma50": round(sma50, 4),
        "reasons": reasons,
    }

