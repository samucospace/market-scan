"""Early Signs & Cross-Asset Divergence Radar.

Detects:
1. Cross-Asset Divergence Anomaly Signals (Credit vs Equities, Copper/Gold, AUD/JPY, Sector rotations)
2. Market Breadth & Momentum Exhaustions (% above 20D/50D SMAs, RSI Clusters)
3. Volatility Compression / Squeeze Scanner (Bollinger squeezes preceding multi-week breakouts)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

import pandas as pd

from metrics import (
    calculate_bollinger_bands,
    calculate_rsi,
    calculate_sma,
    pct_change,
)
from regime import compute_ratio_series
from storage import get_connection, get_prices


@dataclass
class EarlyAlert:
    severity: str  # "HIGH", "MEDIUM", "INFO"
    category: str  # "Credit Divergence", "Macro Canary", "Liquidity", "Sector Rotation", "Volatility Squeeze"
    title: str
    description: str
    implication: str


@dataclass
class BreadthStats:
    pct_above_sma20: float
    pct_above_sma50: float
    overbought_count: int
    oversold_count: int
    total_assets: int
    overbought_tickers: list[str]
    oversold_tickers: list[str]


@dataclass
class SqueezeCandidate:
    ticker: str
    note: str
    group: str
    bandwidth: float
    pct_b: float
    rsi: float
    last_close: float


@dataclass
class EarlySignalsReport:
    alerts: list[EarlyAlert]
    breadth: BreadthStats
    squeeze_candidates: list[SqueezeCandidate]
    divergence_matrix: list[dict[str, Any]]


def scan_early_signals(conn: sqlite3.Connection | None = None) -> EarlySignalsReport:
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    # 1. Fetch benchmark price data
    spx = get_prices(conn, "^GSPC")
    ndx = get_prices(conn, "^NDX")
    dxy = get_prices(conn, "DX-Y.NYB")
    hyg = get_prices(conn, "HYG")
    ief = get_prices(conn, "IEF")
    copper = get_prices(conn, "HG=F")
    gold = get_prices(conn, "GC=F")
    silver = get_prices(conn, "SI=F")
    audjpy = get_prices(conn, "AUDJPY=X")
    xly = get_prices(conn, "XLY")
    xlp = get_prices(conn, "XLP")
    xlk = get_prices(conn, "XLK")
    xlu = get_prices(conn, "XLU")

    alerts: list[EarlyAlert] = []
    divergence_matrix: list[dict[str, Any]] = []

    # --- 2. Credit vs Equity Divergence ---
    spx_5d = pct_change(spx, 5) or 0.0
    spx_20d = pct_change(spx, 20) or 0.0
    hyg_ief_ratio = compute_ratio_series(hyg, ief)
    
    hyg_ief_5d = 0.0
    hyg_ief_20d = 0.0
    if len(hyg_ief_ratio) >= 21:
        hyg_ief_5d = (hyg_ief_ratio.iloc[-1] / hyg_ief_ratio.iloc[-5] - 1) * 100
        hyg_ief_20d = (hyg_ief_ratio.iloc[-1] / hyg_ief_ratio.iloc[-21] - 1) * 100

    if spx_20d > 1.5 and hyg_ief_20d < -0.8:
        alerts.append(EarlyAlert(
            severity="HIGH",
            category="Credit Divergence",
            title="Bearish Credit Divergence (Equities vs High Yield Spreads)",
            description=(
                f"S&P 500 is up +{spx_20d:.2f}% over 20 days, while the HYG/IEF credit spread ratio "
                f"fell {hyg_ief_20d:.2f}%. Smart money in credit markets is demanding higher risk premium."
            ),
            implication="Tighten trailing stops on cyclical equity longs; watch for a 3-5% index pullback.",
        ))
    elif spx_20d < -1.5 and hyg_ief_20d > 0.8:
        alerts.append(EarlyAlert(
            severity="MEDIUM",
            category="Credit Divergence",
            title="Bullish Credit Leading Recovery",
            description=(
                f"Equities pulled back {spx_20d:.2f}% over 20 days, but high yield credit spread (HYG/IEF) "
                f"held firm (+{hyg_ief_20d:.2f}%). Credit is refusing to confirm the selloff."
            ),
            implication="High probability dip-buying opportunity for equities and high-beta assets.",
        ))

    divergence_matrix.append({
        "Signal": "Credit vs S&P 500",
        "Asset 1": f"S&P 500 (20D: {spx_20d:+.2f}%)",
        "Asset 2": f"HYG/IEF (20D: {hyg_ief_20d:+.2f}%)",
        "Status": "DIVERGENT (Bearish)" if (spx_20d > 1.5 and hyg_ief_20d < -0.8) else (
            "DIVERGENT (Bullish)" if (spx_20d < -1.5 and hyg_ief_20d > 0.8) else "Aligned"
        ),
    })

    # --- 3. Copper / Gold vs Equity Divergence ---
    cu_au_ratio = compute_ratio_series(copper, gold)
    cu_au_20d = 0.0
    if len(cu_au_ratio) >= 21:
        cu_au_20d = (cu_au_ratio.iloc[-1] / cu_au_ratio.iloc[-21] - 1) * 100

    if spx_20d > 2.0 and cu_au_20d < -3.0:
        alerts.append(EarlyAlert(
            severity="MEDIUM",
            category="Macro Canary",
            title="Industrial Growth De-coupling (Copper/Gold lagging Equities)",
            description=(
                f"Copper/Gold ratio has dropped {cu_au_20d:.2f}% over 20 days despite equity strength. "
                "The physical industrial cycle is not confirming equity market optimism."
            ),
            implication="Favor defensive or tech secular growth over heavy industrial/materials swing longs.",
        ))

    divergence_matrix.append({
        "Signal": "Copper/Gold vs S&P 500",
        "Asset 1": f"S&P 500 (20D: {spx_20d:+.2f}%)",
        "Asset 2": f"Copper/Gold (20D: {cu_au_20d:+.2f}%)",
        "Status": "DIVERGENT (Warning)" if (spx_20d > 2.0 and cu_au_20d < -3.0) else "Aligned",
    })

    # --- 4. AUD/JPY FX Canary Divergence ---
    audjpy_20d = pct_change(audjpy, 20) or 0.0
    if spx_20d > 2.0 and audjpy_20d < -2.0:
        alerts.append(EarlyAlert(
            severity="HIGH",
            category="Macro Canary",
            title="FX Risk Bellwether Roll-over (AUD/JPY vs Equities)",
            description=(
                f"AUD/JPY (global carry & risk sentiment leader) is down {audjpy_20d:.2f}% over 20 days "
                f"while S&P 500 gained +{spx_20d:.2f}%. FX carries often lead equity reversals."
            ),
            implication="Hedge long risk exposure; look for tactical short setups on overextended equities.",
        ))

    divergence_matrix.append({
        "Signal": "AUD/JPY vs S&P 500",
        "Asset 1": f"S&P 500 (20D: {spx_20d:+.2f}%)",
        "Asset 2": f"AUD/JPY (20D: {audjpy_20d:+.2f}%)",
        "Status": "DIVERGENT (Bearish Lead)" if (spx_20d > 2.0 and audjpy_20d < -2.0) else "Aligned",
    })

    # --- 5. Dollar Squeeze & Global Liquidity Alert ---
    dxy_20d = pct_change(dxy, 20) or 0.0
    dxy_sma50 = calculate_sma(dxy, 50)
    dxy_last = dxy["close"].dropna().iloc[-1] if not dxy.empty else None
    
    if dxy_last and dxy_sma50 and dxy_last > dxy_sma50 and dxy_20d > 1.8:
        alerts.append(EarlyAlert(
            severity="MEDIUM",
            category="Liquidity",
            title="US Dollar (DXY) Liquidity Squeeze",
            description=(
                f"US Dollar Index rallied +{dxy_20d:.2f}% over 20 days above its 50-day SMA ({dxy_sma50:.2f}). "
                "Rising dollar tightens global financial conditions, pressuring commodities and EM equities."
            ),
            implication="Be cautious on commodity longs and non-US equities; look for USD strength swing trades.",
        ))

    # --- 6. Defensive Sector Stealth Rotation ---
    xly_xlp_ratio = compute_ratio_series(xly, xlp)
    xlu_xlk_ratio = compute_ratio_series(xlu, xlk)
    xly_xlp_20d = (
        (xly_xlp_ratio.iloc[-1] / xly_xlp_ratio.iloc[-21] - 1) * 100 if len(xly_xlp_ratio) >= 21 else 0.0
    )
    xlu_xlk_20d = (
        (xlu_xlk_ratio.iloc[-1] / xlu_xlk_ratio.iloc[-21] - 1) * 100 if len(xlu_xlk_ratio) >= 21 else 0.0
    )

    if spx_20d > 1.0 and (xly_xlp_20d < -3.0 or xlu_xlk_20d > 4.0):
        alerts.append(EarlyAlert(
            severity="MEDIUM",
            category="Sector Rotation",
            title="Defensive Stealth Rotation (Staples/Utilities outperforming Growth)",
            description=(
                f"Despite headline index gains, defensive Utilities/Staples are outperforming cyclicals "
                f"(XLY/XLP: {xly_xlp_20d:+.2f}%, XLU/XLK: {xlu_xlk_20d:+.2f}%). Institutional funds are taking risk off."
            ),
            implication="Rotate into quality defensive setups or lower overall portfolio beta.",
        ))

    # --- 7. Breadth & Volatility Squeeze Scanner across All Database Assets ---
    cur = conn.execute("SELECT DISTINCT ticker FROM prices")
    all_tickers = [row[0] for row in cur.fetchall()]

    above_sma20_count = 0
    above_sma50_count = 0
    overbought_tickers = []
    oversold_tickers = []
    squeeze_candidates: list[SqueezeCandidate] = []
    total_valid = 0

    for ticker in all_tickers:
        prices = get_prices(conn, ticker)
        if prices.empty or len(prices) < 50:
            continue
        
        total_valid += 1
        closes = prices["close"].dropna()
        last_px = closes.iloc[-1]
        
        sma20 = calculate_sma(prices, 20)
        sma50 = calculate_sma(prices, 50)
        rsi = calculate_rsi(prices, 14) or 50.0
        bb = calculate_bollinger_bands(prices, 20, 2.0)

        if sma20 and last_px > sma20:
            above_sma20_count += 1
        if sma50 and last_px > sma50:
            above_sma50_count += 1

        if rsi >= 70.0:
            overbought_tickers.append(f"{ticker} (RSI {rsi:.1f})")
        elif rsi <= 30.0:
            oversold_tickers.append(f"{ticker} (RSI {rsi:.1f})")

        # Volatility Squeeze detection: Bandwidth <= 3.8% indicates extreme consolidation
        bw = bb.get("bandwidth")
        pct_b = bb.get("pct_b")
        if bw is not None and bw <= 4.0:
            squeeze_candidates.append(SqueezeCandidate(
                ticker=ticker,
                note="",
                group="",
                bandwidth=round(bw, 2),
                pct_b=round(pct_b, 2) if pct_b is not None else 0.5,
                rsi=round(rsi, 1),
                last_close=round(last_px, 4),
            ))

    if should_close:
        conn.close()

    pct_above_sma20 = (above_sma20_count / total_valid * 100) if total_valid else 50.0
    pct_above_sma50 = (above_sma50_count / total_valid * 100) if total_valid else 50.0

    breadth = BreadthStats(
        pct_above_sma20=round(pct_above_sma20, 1),
        pct_above_sma50=round(pct_above_sma50, 1),
        overbought_count=len(overbought_tickers),
        oversold_count=len(oversold_tickers),
        total_assets=total_valid,
        overbought_tickers=overbought_tickers[:8],
        oversold_tickers=oversold_tickers[:8],
    )

    # Breadth alerts
    if pct_above_sma20 > 82:
        alerts.append(EarlyAlert(
            severity="MEDIUM",
            category="Breadth Exhaustion",
            title="Overextended Market Breadth (>80% of assets above 20D SMA)",
            description=f"{pct_above_sma20:.1f}% of watchlist assets are trading above their 20-day SMA. Historically indicates near-term momentum exhaustion.",
            implication="Expect mean-reversion pullbacks; wait for dips rather than chasing breakouts.",
        ))
    elif pct_above_sma20 < 18:
        alerts.append(EarlyAlert(
            severity="MEDIUM",
            category="Breadth Washout",
            title="Oversold Market Washout (<20% of assets above 20D SMA)",
            description=f"Only {pct_above_sma20:.1f}% of watchlist assets are above their 20-day SMA. Market is deeply oversold.",
            implication="Look for sharp counter-trend relief rallies and oversold bounce setups.",
        ))

    # Sort squeeze candidates by bandwidth (tightest squeeze first)
    squeeze_candidates.sort(key=lambda x: x.bandwidth)

    return EarlySignalsReport(
        alerts=alerts,
        breadth=breadth,
        squeeze_candidates=squeeze_candidates[:10],
        divergence_matrix=divergence_matrix,
    )
