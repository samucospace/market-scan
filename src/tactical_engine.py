"""Tactical Quantitative Matrix Engine for Dashboard v2.0.

Computes 4 institutional multi-factor ratings for key global securities:
1. Primary Trend (based on 100-day EMA)
2. Macro Environment (4-Quadrant Growth vs Inflation Cycle)
3. Daily Correlated Assets (intermarket drivers, 60-day correlations, and daily impulse)
4. Tactical Technicals (composite of 20 EMA, RSI 14, Bollinger Bands %B, and 10/20 EMA trend)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from metrics import (
    calculate_bollinger_bands,
    calculate_ema,
    calculate_rsi,
    last_close,
    last_date,
    pct_change,
)
from regime import calculate_macro_regime
from storage import get_connection, get_prices

# The 12 target securities requested for Dashboard v2.0
TARGET_SECURITIES = [
    {
        "symbol": "AUDUSD",
        "ticker": "AUDUSD=X",
        "name": "AUD / USD",
        "category": "FX",
        "display_name": "AUD/USD (Australian Dollar)",
        "correlated_drivers": [
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("HG=F", "Copper Futures", 1),
            ("^GSPC", "S&P 500", 1),
            ("CL=F", "WTI Crude", 1),
        ],
    },
    {
        "symbol": "EURUSD",
        "ticker": "EURUSD=X",
        "name": "EUR / USD",
        "category": "FX",
        "display_name": "EUR/USD (Euro)",
        "correlated_drivers": [
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("^STOXX50E", "Euro Stoxx 50", 1),
            ("^TNX", "US 10Y Yield", -1),
        ],
    },
    {
        "symbol": "GBPUSD",
        "ticker": "GBPUSD=X",
        "name": "GBP / USD",
        "category": "FX",
        "display_name": "GBP/USD (British Pound)",
        "correlated_drivers": [
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("EURUSD=X", "EUR/USD", 1),
            ("^FTSE", "FTSE 100", 1),
        ],
    },
    {
        "symbol": "USDJPY",
        "ticker": "USDJPY=X",
        "name": "USD / JPY",
        "category": "FX",
        "display_name": "USD/JPY (Japanese Yen)",
        "correlated_drivers": [
            ("^TNX", "US 10Y Yield", 1),
            ("DX-Y.NYB", "US Dollar Index", 1),
            ("^N225", "Nikkei 225", 1),
        ],
    },
    {
        "symbol": "NZDUSD",
        "ticker": "NZDUSD=X",
        "name": "NZD / USD",
        "category": "FX",
        "display_name": "NZD/USD (New Zealand Dollar)",
        "correlated_drivers": [
            ("AUDUSD=X", "AUD/USD", 1),
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("^GSPC", "S&P 500", 1),
        ],
    },
    {
        "symbol": "US500",
        "ticker": "^GSPC",
        "name": "S&P 500",
        "category": "Equities",
        "display_name": "US500 (S&P 500 Index)",
        "correlated_drivers": [
            ("HYG", "High Yield Credit ETF", 1),
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("^TNX", "US 10Y Yield", -1),
            ("XLK", "Technology ETF", 1),
        ],
    },
    {
        "symbol": "US Tech 100",
        "ticker": "^NDX",
        "name": "Nasdaq 100",
        "category": "Equities",
        "display_name": "US Tech 100 (Nasdaq 100)",
        "correlated_drivers": [
            ("XLK", "Technology ETF", 1),
            ("^TNX", "US 10Y Yield", -1),
            ("^GSPC", "S&P 500", 1),
            ("DX-Y.NYB", "US Dollar Index", -1),
        ],
    },
    {
        "symbol": "USDCAD",
        "ticker": "USDCAD=X",
        "name": "USD / CAD",
        "category": "FX",
        "display_name": "USD/CAD (Canadian Dollar)",
        "correlated_drivers": [
            ("DX-Y.NYB", "US Dollar Index", 1),
            ("CL=F", "WTI Crude", -1),
            ("BZ=F", "Brent Crude", -1),
        ],
    },
    {
        "symbol": "Brent Crude",
        "ticker": "BZ=F",
        "name": "Brent Crude",
        "category": "Commodities",
        "display_name": "Brent Crude Oil Futures",
        "correlated_drivers": [
            ("CL=F", "WTI Crude Futures", 1),
            ("XLE", "Energy Sector ETF", 1),
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("^GSPC", "S&P 500", 1),
        ],
    },
    {
        "symbol": "Copper",
        "ticker": "HG=F",
        "name": "Copper",
        "category": "Commodities",
        "display_name": "Copper Futures (COMEX)",
        "correlated_drivers": [
            ("XLB", "Materials ETF", 1),
            ("^GSPC", "S&P 500", 1),
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("AUDUSD=X", "AUD/USD", 1),
        ],
    },
    {
        "symbol": "Gold",
        "ticker": "GC=F",
        "name": "Gold",
        "category": "Commodities",
        "display_name": "Gold Futures (COMEX)",
        "correlated_drivers": [
            ("DX-Y.NYB", "US Dollar Index", -1),
            ("^TNX", "US 10Y Yield", -1),
            ("SI=F", "Silver Futures", 1),
        ],
    },
    {
        "symbol": "Silver",
        "ticker": "SI=F",
        "name": "Silver",
        "category": "Commodities",
        "display_name": "Silver Futures (COMEX)",
        "correlated_drivers": [
            ("GC=F", "Gold Futures", 1),
            ("HG=F", "Copper Futures", 1),
            ("DX-Y.NYB", "US Dollar Index", -1),
        ],
    },
]

# Macro 4-Quadrant Institutional Matrix for each asset
# Quadrant tags:
#   EXPANSION_GOLDILOCKS: Growth > 0, Inflation <= 0
#   EXPANSION_REFLATION:  Growth > 0, Inflation > 0
#   STAGFLATION_LATE_CYCLE: Growth < 0, Inflation > 0
#   CONTRACTION_RISK_OFF: Growth < 0, Inflation <= 0
MACRO_QUADRANT_MATRIX: dict[str, dict[str, dict[str, str]]] = {
    "AUDUSD": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "High-beta currency benefits from expanding global trade, risk appetite, and soft USD.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "Strong commodity demand, raw material inflation, and mining exports power Australian terms of trade.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bearish",
            "rationale": "Decelerating global trade and stagflationary cost pressures weigh on pro-cyclical currencies.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Severe risk aversion and global recession prompt liquidation of high-beta commodity currencies.",
        },
    },
    "EURUSD": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "Synchronized global expansion softens USD liquidity squeeze and promotes European exporter inflows.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Neutral",
            "rationale": "European growth acceleration is counterbalanced by higher US rate differentials and import costs.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bearish",
            "rationale": "Eurozone vulnerability to elevated energy costs and sluggish domestic consumption degrades Euro.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Broad safe-haven flight into US Dollar reserve liquidity depresses EUR/USD.",
        },
    },
    "GBPUSD": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "Global risk-on conditions and UK market cyclicality support cross-border sterling flows.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Neutral",
            "rationale": "Persistent domestic inflation and BoE rate uncertainty create balanced two-way volatility.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bearish",
            "rationale": "Stagflationary cost-of-living drag and fiscal caution weaken GBP against defensive US Dollar.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Global de-risking and capital retrenchment spur institutional flight to USD cash.",
        },
    },
    "USDJPY": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "Low global volatility and stable yield curves encourage FX carry trades, depressing JPY.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "Surging US Treasury yields widen US-Japan interest rate differentials, powering USD/JPY upside.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Neutral",
            "rationale": "Elevated US rates conflict with Yen safe-haven repatriation flows, producing choppy ranges.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Aggressive safe-haven unwinding into JPY and sharp drops in US Treasury yields drag USD/JPY down.",
        },
    },
    "NZDUSD": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "Buoyant global demand, soft USD, and agricultural trade recovery favor NZD.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "Surging food/dairy commodity export prices boost New Zealand external balance.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bearish",
            "rationale": "Contracting real global disposable income and trade friction erode high-beta FX.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Cyclical currency liquidation and liquidity de-risking push capital into USD.",
        },
    },
    "US500": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "The ideal equity backdrop: robust earnings expansion coupled with benign, disinflationary cost of capital.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "Nominal revenue growth and cyclical earnings momentum outweigh discount rate expansion.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bearish",
            "rationale": "Corporate profit margin compression from sticky input costs and elevated borrowing hurdles.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Earnings recession, credit tightening, and broad institutional de-equitization.",
        },
    },
    "US Tech 100": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "Prime winner: disinflationary yields protect rich valuation multiples while tech adoption expands.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Neutral",
            "rationale": "Solid secular tech fundamentals face duration discount rate headwinds from surging bond yields.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bearish",
            "rationale": "High-multiple valuation compression and enterprise software/hardware capex budget cuts.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "De-leveraging, high-beta valuation contraction, and growth equity liquidation.",
        },
    },
    "USDCAD": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bearish",
            "rationale": "Risk appetite and solid Canadian commodity exports strengthen CAD, pushing USD/CAD lower.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bearish",
            "rationale": "High oil and energy revenues generate major trade surpluses for Canada, appreciating CAD vs USD.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bullish",
            "rationale": "US Dollar safe-haven strength and risk aversion dominate Canadian commodity support.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bullish",
            "rationale": "Severe collapse in energy prices hammers CAD, while global flight to safety bids USD aggressively.",
        },
    },
    "Brent Crude": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Neutral",
            "rationale": "Healthy underlying consumption, but disinflationary environment caps speculative energy premiums.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "Industrial utilization, rising travel/transport demand, and inventory depletion spur crude rally.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bullish",
            "rationale": "Supply inelasticity, structural energy tightness, and cost-push inflation support oil prices.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Industrial contraction and consumer recession lead to swift demand destruction.",
        },
    },
    "Copper": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "Manufacturing revival, global electrification capex, and healthy industrial confidence drive demand.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "High industrial capacity utilization, infrastructure spending, and physical tightness fuel 'Doctor Copper'.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bearish",
            "rationale": "Manufacturing slowdown and stagflation squeeze undermine physical factory orders.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Industrial recession and warehouse destocking cause acute price drops.",
        },
    },
    "Gold": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Neutral",
            "rationale": "Absence of crisis reduces safe-haven urgency, though moderate yields prevent heavy selling.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "Prime monetary asset to hedge against accelerating inflation and purchasing power erosion.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Bullish",
            "rationale": "The premier stagflation asset: simultaneously offers real wealth preservation and crisis defense.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bullish",
            "rationale": "Plunging bond yields, anticipated central bank rate cuts, and systemic flight to gold safety.",
        },
    },
    "Silver": {
        "EXPANSION_GOLDILOCKS": {
            "rating": "Bullish",
            "rationale": "Dual benefits: accelerating industrial/green electrification demand alongside firm precious metals.",
        },
        "EXPANSION_REFLATION": {
            "rating": "Bullish",
            "rationale": "High-beta hybrid: industrial commodity demand supercharged by monetary inflation hedging.",
        },
        "STAGFLATION_LATE_CYCLE": {
            "rating": "Neutral",
            "rationale": "Precious metals safe-haven appeal is partially dragged down by weakening industrial demand.",
        },
        "CONTRACTION_RISK_OFF": {
            "rating": "Bearish",
            "rationale": "Industrial fabrication slump outweighs safe-haven bids; silver historically underperforms gold in slumps.",
        },
    },
}


@dataclass
class SecurityRating:
    symbol: str
    ticker: str
    name: str
    category: str
    display_name: str
    last_price: float
    daily_change_pct: float
    as_of: str

    # 1. Primary Trend
    primary_trend: str  # Bullish, Neutral, Bearish
    primary_trend_details: dict[str, Any]

    # 2. Macro Environment
    macro_environment: str  # Bullish, Neutral, Bearish
    macro_details: dict[str, Any]

    # 3. Daily Correlated Assets
    correlated_assets: str  # Bullish, Neutral, Bearish
    correlated_details: dict[str, Any]

    # 4. Tactical Technicals
    tactical_technicals: str  # Bullish, Neutral, Bearish
    tactical_details: dict[str, Any]

    # Summary
    overall_stance: str  # Bullish, Neutral, Bearish
    net_score: int  # -4 to +4


def evaluate_primary_trend(prices: pd.DataFrame) -> dict[str, Any]:
    """Evaluates Primary Trend based on 100-day EMA.
    
    Logic:
    - Calculates the 100-day Exponential Moving Average (EMA).
    - Compares current Close to EMA100: dist_pct = (Close - EMA100) / EMA100 * 100.
    - Evaluates 5-day slope of EMA100: slope_pct = (EMA100_t - EMA100_{t-5}) / EMA100_{t-5} * 100.
    - Rating:
        - Bullish: Close > EMA100 by >= +0.3% (or Close > EMA100 and EMA is sloping up)
        - Bearish: Close < EMA100 by <= -0.3% (or Close < EMA100 and EMA is sloping down)
        - Neutral: Close is within +/- 0.3% of EMA100 (testing trendline / consolidating)
    """
    if prices is None or prices.empty or "close" not in prices:
        return {
            "rating": "Neutral",
            "close": None,
            "ema100": None,
            "dist_pct": 0.0,
            "slope_pct": 0.0,
            "summary": "Insufficient price data",
        }

    closes = prices["close"].dropna()
    if len(closes) < 100:
        return {
            "rating": "Neutral",
            "close": float(closes.iloc[-1]) if len(closes) else None,
            "ema100": None,
            "dist_pct": 0.0,
            "slope_pct": 0.0,
            "summary": "Need at least 100 trading days of history",
        }

    ema_series = closes.ewm(span=100, adjust=False).mean()
    c = float(closes.iloc[-1])
    ema100 = float(ema_series.iloc[-1])
    ema100_5d_ago = float(ema_series.iloc[-6]) if len(ema_series) >= 6 else ema100

    dist_pct = ((c - ema100) / ema100) * 100.0
    slope_pct = ((ema100 - ema100_5d_ago) / ema100_5d_ago) * 100.0 if ema100_5d_ago else 0.0

    if dist_pct >= 0.30:
        rating = "Bullish"
        summary = f"Trading {dist_pct:+.2f}% above 100 EMA ({ema100:.4f}) with {'rising' if slope_pct >= 0 else 'flat'} trendline"
    elif dist_pct <= -0.30:
        rating = "Bearish"
        summary = f"Trading {dist_pct:+.2f}% below 100 EMA ({ema100:.4f}) with {'falling' if slope_pct <= 0 else 'flat'} trendline"
    else:
        rating = "Neutral"
        summary = f"Consolidating within {dist_pct:+.2f}% of 100 EMA ({ema100:.4f})"

    return {
        "rating": rating,
        "close": c,
        "ema100": ema100,
        "dist_pct": dist_pct,
        "slope_pct": slope_pct,
        "summary": summary,
    }


def evaluate_macro_environment(symbol: str, active_quadrant_tag: str) -> dict[str, Any]:
    """Maps the active 4-quadrant macro regime to asset institutional rating."""
    asset_rules = MACRO_QUADRANT_MATRIX.get(symbol, {})
    rule = asset_rules.get(active_quadrant_tag)
    if not rule:
        return {
            "rating": "Neutral",
            "rationale": "Macro regime response neutral or unmapped.",
        }
    return {
        "rating": rule["rating"],
        "rationale": rule["rationale"],
    }


def evaluate_correlated_assets(
    conn: sqlite3.Connection,
    symbol: str,
    ticker: str,
    drivers: list[tuple[str, str, int]],
    prices_cache: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Calculates reading from daily correlated driver assets.
    
    Logic:
    - Calculates 60-day rolling correlation of daily returns between target asset and each driver.
    - Captures latest 1-day return of each driver.
    - Computes correlated impulse:
        Impulse = Sum(corr_i * return_i) / Sum(|corr_i|)
    - Rating:
        - Bullish: Impulse > +0.05%
        - Bearish: Impulse < -0.05%
        - Neutral: -0.05% <= Impulse <= +0.05%
    """
    if prices_cache is None:
        prices_cache = {}

    if ticker not in prices_cache:
        prices_cache[ticker] = get_prices(conn, ticker)
    target_df = prices_cache[ticker]

    if target_df.empty or "close" not in target_df:
        return {
            "rating": "Neutral",
            "impulse_pct": 0.0,
            "drivers": [],
            "summary": "No target price history available",
        }

    target_ret = target_df["close"].pct_change().dropna()
    driver_results = []

    for d_ticker, d_name, expected_sign in drivers:
        if d_ticker not in prices_cache:
            prices_cache[d_ticker] = get_prices(conn, d_ticker)
        d_df = prices_cache[d_ticker]
        if d_df.empty or "close" not in d_df:
            continue
        d_ret = d_df["close"].pct_change().dropna()
        if len(d_ret) < 20:
            continue

        aligned = pd.concat([target_ret.rename("target"), d_ret.rename("driver")], axis=1, sort=False).dropna().tail(60)
        if len(aligned) < 15:
            continue

        empirical_corr = float(aligned["target"].corr(aligned["driver"]))
        if np.isnan(empirical_corr):
            empirical_corr = float(expected_sign) * 0.5  # fallback to theoretical sign

        latest_driver_ret = float(d_ret.iloc[-1]) * 100.0 if not d_ret.empty else 0.0
        # Impulse contribution to target asset
        impulse = latest_driver_ret * empirical_corr

        driver_results.append({
            "ticker": d_ticker,
            "name": d_name,
            "correlation": empirical_corr,
            "daily_change_pct": latest_driver_ret,
            "impulse": impulse,
        })

    if not driver_results:
        return {
            "rating": "Neutral",
            "impulse_pct": 0.0,
            "drivers": [],
            "summary": "Insufficient correlated driver history",
        }

    weights_sum = sum(abs(r["correlation"]) for r in driver_results) or 1.0
    total_impulse = sum(r["impulse"] for r in driver_results) / weights_sum

    if total_impulse >= 0.05:
        rating = "Bullish"
        summary = f"Positive cross-asset impulse ({total_impulse:+.2f}%) supported by intermarket moves"
    elif total_impulse <= -0.05:
        rating = "Bearish"
        summary = f"Negative cross-asset drag ({total_impulse:+.2f}%) from correlated headwinds"
    else:
        rating = "Neutral"
        summary = f"Balanced cross-asset impulse ({total_impulse:+.2f}%) across intermarket drivers"

    return {
        "rating": rating,
        "impulse_pct": total_impulse,
        "drivers": driver_results,
        "summary": summary,
    }


def evaluate_tactical_technicals(prices: pd.DataFrame) -> dict[str, Any]:
    """Combines 20-day EMA, RSI (14), Bollinger Bands %B, and 10/20 EMA trend.
    
    Point Scoring Model:
    1. 20-day EMA:
       - Price > 20 EMA: +1
       - Price < 20 EMA: -1
    2. RSI (14):
       - RSI > 55: +1 (Bullish momentum)
       - RSI < 45: -1 (Bearish momentum)
       - 45 <= RSI <= 55: 0 (Neutral)
    3. Bollinger Bands %B (20, 2):
       - %B > 0.60: +1 (Upper expansion / Bullish)
       - %B < 0.40: -1 (Lower contraction / Bearish)
       - 0.40 <= %B <= 0.60: 0 (Middle equilibrium)
    4. Short-term Trend (10 EMA vs 20 EMA):
       - 10 EMA > 20 EMA: +1 (Short trend bullish)
       - 10 EMA < 20 EMA: -1 (Short trend bearish)
       
    Composite Score = sum of points (range -4 to +4):
       - Score >= +2: Bullish
       - Score <= -2: Bearish
       - Score in {-1, 0, +1}: Neutral
    """
    if prices is None or prices.empty or "close" not in prices:
        return {
            "rating": "Neutral",
            "score": 0,
            "rsi": None,
            "ema20": None,
            "ema10": None,
            "pct_b": None,
            "bb_bandwidth": None,
            "summary": "Insufficient price data",
            "breakdown": {},
        }

    c = last_close(prices)
    ema20 = calculate_ema(prices, 20)
    ema10 = calculate_ema(prices, 10)
    rsi = calculate_rsi(prices, 14)
    bb = calculate_bollinger_bands(prices, 20)
    pct_b = bb.get("pct_b")
    bandwidth = bb.get("bandwidth")

    points = 0
    breakdown = {}

    # 1. 20 EMA
    if c is not None and ema20 is not None:
        if c > ema20:
            points += 1
            breakdown["20 EMA"] = {"signal": "Bullish (+1)", "desc": f"Price ({c:.4f}) > 20 EMA ({ema20:.4f})"}
        else:
            points -= 1
            breakdown["20 EMA"] = {"signal": "Bearish (-1)", "desc": f"Price ({c:.4f}) < 20 EMA ({ema20:.4f})"}
    else:
        breakdown["20 EMA"] = {"signal": "Neutral (0)", "desc": "N/A"}

    # 2. RSI (14)
    if rsi is not None:
        if rsi > 55.0:
            points += 1
            breakdown["RSI (14)"] = {"signal": "Bullish (+1)", "desc": f"RSI is {rsi:.1f} (above 55 momentum)"}
        elif rsi < 45.0:
            points -= 1
            breakdown["RSI (14)"] = {"signal": "Bearish (-1)", "desc": f"RSI is {rsi:.1f} (below 45 momentum)"}
        else:
            breakdown["RSI (14)"] = {"signal": "Neutral (0)", "desc": f"RSI is {rsi:.1f} (balanced 45-55)"}
    else:
        breakdown["RSI (14)"] = {"signal": "Neutral (0)", "desc": "N/A"}

    # 3. Bollinger Bands %B
    if pct_b is not None:
        if pct_b > 0.60:
            points += 1
            breakdown["Bollinger %B"] = {"signal": "Bullish (+1)", "desc": f"%B is {pct_b:.2f} (upper band zone)"}
        elif pct_b < 0.40:
            points -= 1
            breakdown["Bollinger %B"] = {"signal": "Bearish (-1)", "desc": f"%B is {pct_b:.2f} (lower band zone)"}
        else:
            breakdown["Bollinger %B"] = {"signal": "Neutral (0)", "desc": f"%B is {pct_b:.2f} (mid-band equilibrium)"}
    else:
        breakdown["Bollinger %B"] = {"signal": "Neutral (0)", "desc": "N/A"}

    # 4. 10 EMA vs 20 EMA alignment
    if ema10 is not None and ema20 is not None:
        if ema10 > ema20:
            points += 1
            breakdown["10/20 EMA Trend"] = {"signal": "Bullish (+1)", "desc": f"10 EMA ({ema10:.4f}) > 20 EMA ({ema20:.4f})"}
        else:
            points -= 1
            breakdown["10/20 EMA Trend"] = {"signal": "Bearish (-1)", "desc": f"10 EMA ({ema10:.4f}) < 20 EMA ({ema20:.4f})"}
    else:
        breakdown["10/20 EMA Trend"] = {"signal": "Neutral (0)", "desc": "N/A"}

    # Overall rating
    if points >= 2:
        rating = "Bullish"
        summary = f"Bullish technical confluence ({points:+d}/4) with price above short EMAs and positive momentum"
    elif points <= -2:
        rating = "Bearish"
        summary = f"Bearish technical confluence ({points:+d}/4) with price below short EMAs and negative momentum"
    else:
        rating = "Neutral"
        summary = f"Mixed/Neutral technical indicators ({points:+d}/4) across moving averages and oscillators"

    return {
        "rating": rating,
        "score": points,
        "rsi": rsi,
        "ema20": ema20,
        "ema10": ema10,
        "pct_b": pct_b,
        "bb_bandwidth": bandwidth,
        "summary": summary,
        "breakdown": breakdown,
    }


def compute_v2_dashboard_ratings(conn: sqlite3.Connection | None = None) -> tuple[list[SecurityRating], Any]:
    """Generates the complete quantitative ratings table for all 12 target securities."""
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    try:
        macro_report = calculate_macro_regime(conn)
        active_quadrant = macro_report.quadrant_tag

        prices_cache: dict[str, pd.DataFrame] = {}
        ratings: list[SecurityRating] = []

        for sec in TARGET_SECURITIES:
            sym = sec["symbol"]
            ticker = sec["ticker"]

            if ticker not in prices_cache:
                prices_cache[ticker] = get_prices(conn, ticker)
            df = prices_cache[ticker]

            c = last_close(df) or 0.0
            d_chg = pct_change(df, 1) or 0.0
            dt = last_date(df) or ""

            # 1. Primary Trend (100-day EMA)
            trend_res = evaluate_primary_trend(df)

            # 2. Macro Environment (4 Quadrants)
            macro_res = evaluate_macro_environment(sym, active_quadrant)

            # 3. Daily Correlated Assets
            corr_res = evaluate_correlated_assets(
                conn, sym, ticker, sec["correlated_drivers"], prices_cache=prices_cache
            )

            # 4. Tactical Technicals (20 EMA, RSI, Bollinger Bands, 10 EMA)
            tact_res = evaluate_tactical_technicals(df)

            # Calculate Consensus Overall Stance
            col_ratings = [
                trend_res["rating"],
                macro_res["rating"],
                corr_res["rating"],
                tact_res["rating"],
            ]
            score_map = {"Bullish": 1, "Neutral": 0, "Bearish": -1}
            net_score = sum(score_map.get(r, 0) for r in col_ratings)

            if net_score >= 2:
                overall_stance = "Bullish"
            elif net_score <= -2:
                overall_stance = "Bearish"
            else:
                overall_stance = "Neutral"

            ratings.append(
                SecurityRating(
                    symbol=sym,
                    ticker=ticker,
                    name=sec["name"],
                    category=sec["category"],
                    display_name=sec["display_name"],
                    last_price=c,
                    daily_change_pct=d_chg,
                    as_of=dt,
                    primary_trend=trend_res["rating"],
                    primary_trend_details=trend_res,
                    macro_environment=macro_res["rating"],
                    macro_details=macro_res,
                    correlated_assets=corr_res["rating"],
                    correlated_details=corr_res,
                    tactical_technicals=tact_res["rating"],
                    tactical_details=tact_res,
                    overall_stance=overall_stance,
                    net_score=net_score,
                )
            )

        return ratings, macro_report

    finally:
        if should_close:
            conn.close()
