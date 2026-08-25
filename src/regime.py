"""Institutional Cross-Asset Macro Regime Engine.

Evaluates:
1. 4-Quadrant Growth vs Inflation Cycle (Goldilocks, Reflation, Stagflation, Contraction)
2. Yield Curve Dynamics & Rate Impulse (Bull/Bear Steepener/Flattener)
3. Cross-Asset Key Ratios (Copper/Gold, HYG/IEF, Gold/Silver, XLY/XLP, XLK/XLU)
4. Synthesized Cross-Asset Risk Sentiment Index (0 to 100)
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from metrics import calculate_rsi, calculate_sma, pct_change
from storage import get_connection, get_prices


@dataclass
class MacroRegimeReport:
    quadrant_name: str
    quadrant_tag: str
    growth_score: float  # -100 to +100
    inflation_score: float  # -100 to +100
    risk_sentiment_score: float  # 0 to 100
    risk_sentiment_label: str
    rates_regime: str
    rates_description: str
    yield_spreads: dict[str, float]
    yield_levels: dict[str, float]
    cross_asset_ratios: dict[str, dict[str, Any]]
    regime_description: str
    asset_implications: list[str]


def _safe_series(df: pd.DataFrame) -> pd.Series:
    if df.empty or "close" not in df:
        return pd.Series(dtype=float)
    return df["close"].dropna()


def compute_ratio_series(prices_num: pd.DataFrame, prices_den: pd.DataFrame) -> pd.Series:
    s_num = _safe_series(prices_num)
    s_den = _safe_series(prices_den)
    if s_num.empty or s_den.empty:
        return pd.Series(dtype=float)
    aligned = pd.concat([s_num.rename("num"), s_den.rename("den")], axis=1).dropna()
    if aligned.empty or (aligned["den"] == 0).all():
        return pd.Series(dtype=float)
    return (aligned["num"] / aligned["den"]).dropna()


def calculate_macro_regime(conn: sqlite3.Connection | None = None) -> MacroRegimeReport:
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True

    # 1. Fetch Key Price Histories
    spx = get_prices(conn, "^GSPC")
    ndx = get_prices(conn, "^NDX")
    dxy = get_prices(conn, "DX-Y.NYB")
    oil_wti = get_prices(conn, "CL=F")
    oil_brent = get_prices(conn, "BZ=F")
    copper = get_prices(conn, "HG=F")
    gold = get_prices(conn, "GC=F")
    silver = get_prices(conn, "SI=F")
    hyg = get_prices(conn, "HYG")
    ief = get_prices(conn, "IEF")
    audjpy = get_prices(conn, "AUDJPY=X")
    usdjpy = get_prices(conn, "USDJPY=X")
    
    # Sectors
    xly = get_prices(conn, "XLY")
    xlp = get_prices(conn, "XLP")
    xlk = get_prices(conn, "XLK")
    xlu = get_prices(conn, "XLU")
    xli = get_prices(conn, "XLI")
    xlf = get_prices(conn, "XLF")
    xle = get_prices(conn, "XLE")

    # Yields
    irx = get_prices(conn, "^IRX")  # 3-Month
    fvx = get_prices(conn, "^FVX")  # 5-Year
    tnx = get_prices(conn, "^TNX")  # 10-Year
    tyx = get_prices(conn, "^TYX")  # 30-Year

    if should_close:
        conn.close()

    # --- 2. Growth Score Calculation (-100 to +100) ---
    growth_components = []
    
    # Component A: Equity Index Trend (SPX & NDX 20D and 50D momentum)
    spx_20d = pct_change(spx, 20) or 0.0
    spx_50d = pct_change(spx, 50) or 0.0
    ndx_20d = pct_change(ndx, 20) or 0.0
    eq_growth_score = np.clip((spx_20d * 4.0 + spx_50d * 2.0 + ndx_20d * 3.0), -100, 100)
    growth_components.append(eq_growth_score)

    # Component B: Cyclicals vs Defensives (XLY/XLP & XLI/XLU)
    xly_xlp_ratio = compute_ratio_series(xly, xlp)
    if len(xly_xlp_ratio) >= 21:
        xly_xlp_20d = (xly_xlp_ratio.iloc[-1] / xly_xlp_ratio.iloc[-21] - 1) * 100
        growth_components.append(np.clip(xly_xlp_20d * 10.0, -100, 100))

    # Component C: Copper/Gold Ratio (Economic expansion bellwether)
    cu_au_ratio = compute_ratio_series(copper, gold)
    if len(cu_au_ratio) >= 21:
        cu_au_20d = (cu_au_ratio.iloc[-1] / cu_au_ratio.iloc[-21] - 1) * 100
        growth_components.append(np.clip(cu_au_20d * 8.0, -100, 100))

    # Component D: Credit Spread Momentum (HYG / IEF)
    hyg_ief_ratio = compute_ratio_series(hyg, ief)
    if len(hyg_ief_ratio) >= 21:
        hyg_ief_20d = (hyg_ief_ratio.iloc[-1] / hyg_ief_ratio.iloc[-21] - 1) * 100
        growth_components.append(np.clip(hyg_ief_20d * 15.0, -100, 100))

    growth_score = float(np.mean(growth_components)) if growth_components else 0.0

    # --- 3. Inflation / Commodity Score Calculation (-100 to +100) ---
    inflation_components = []
    
    # Component A: Energy Momentum (WTI & Brent 20D / 50D)
    wti_20d = pct_change(oil_wti, 20) or 0.0
    wti_50d = pct_change(oil_wti, 50) or 0.0
    brent_20d = pct_change(oil_brent, 20) or 0.0
    oil_inf_score = np.clip((wti_20d * 2.5 + brent_20d * 2.5 + wti_50d * 1.5), -100, 100)
    inflation_components.append(oil_inf_score)

    # Component B: 10Y Yield Momentum (^TNX 20D)
    tnx_20d = pct_change(tnx, 20) or 0.0
    inflation_components.append(np.clip(tnx_20d * 4.0, -100, 100))

    # Component C: Energy Sector (XLE) relative to SPX
    xle_spx_ratio = compute_ratio_series(xle, spx)
    if len(xle_spx_ratio) >= 21:
        xle_spx_20d = (xle_spx_ratio.iloc[-1] / xle_spx_ratio.iloc[-21] - 1) * 100
        inflation_components.append(np.clip(xle_spx_20d * 8.0, -100, 100))

    inflation_score = float(np.mean(inflation_components)) if inflation_components else 0.0

    # --- 4. Macro Quadrant Assignment ---
    # Growth > 0 vs <= 0; Inflation > 0 vs <= 0
    if growth_score >= 0 and inflation_score <= 0:
        quadrant_name = "Goldilocks / Disinflationary Expansion"
        quadrant_tag = "EXPANSION_GOLDILOCKS"
        regime_desc = (
            "Growth is resilient or expanding while inflation pressures are cooling. "
            "This is the most benign macro backdrop for risk assets, favoring high-beta equities, "
            "technology, cyclical sectors, and high-yielding currencies."
        )
        asset_implications = [
            "Overweight: Tech (XLK), Consumer Discretionary (XLY), Industrials (XLI)",
            "Bullish FX: High-beta FX (AUDUSD, AUDJPY), EURUSD against USD",
            "Neutral/Underweight: Energy (XLE), Cash, Ultra-defensive utilities",
            "Fixed Income: Constructive duration as yields stabilize",
        ]
    elif growth_score >= 0 and inflation_score > 0:
        quadrant_name = "Reflation / Overheating Expansion"
        quadrant_tag = "EXPANSION_REFLATION"
        regime_desc = (
            "Economic activity is strong accompanied by rising commodity and yields momentum. "
            "Cost pressures are building, favoring real assets, commodities, energy, and value/financials."
        )
        asset_implications = [
            "Overweight: Commodities (Crude Oil, Copper, Ags), Energy (XLE), Financials (XLF)",
            "Bullish FX: Commodity currencies (CAD, AUD), USDJPY (rate differentials)",
            "Underweight: Long-duration Treasuries, Growth tech with high valuation multiples",
            "Fixed Income: Curve steepeners, Short duration bias",
        ]
    elif growth_score < 0 and inflation_score > 0:
        quadrant_name = "Stagflation / Late Cycle Squeeze"
        quadrant_tag = "STAGFLATION_LATE_CYCLE"
        regime_desc = (
            "Growth momentum is decelerating while commodity/cost pressures remain stubborn. "
            "Challenging environment for broad equities and bonds; capital seeks real stores of value "
            "and quality cash flows."
        )
        asset_implications = [
            "Overweight: Gold (GC=F), Energy (XLE), Defensive Cash Flow (XLU, XLP, XLV)",
            "Bullish FX: US Dollar (DXY safe haven), Swiss Franc (USDCHF short)",
            "Underweight: Broad Equities, Consumer Discretionary (XLY), High Yield credit",
            "Fixed Income: Short-dated yields over long-duration",
        ]
    else:  # growth_score < 0 and inflation_score <= 0
        quadrant_name = "Contraction / Deflationary Risk-Off"
        quadrant_tag = "CONTRACTION_RISK_OFF"
        regime_desc = (
            "Economic growth is slowing and deflationary pressures are dominant. "
            "Flight to quality prevails, favoring government bonds, US Dollar cash, and low-volatility defensives."
        )
        asset_implications = [
            "Overweight: Treasuries (IEF/TLT), US Dollar (DXY), Gold (safe haven)",
            "Defensive Equities: Healthcare (XLV), Consumer Staples (XLP), Utilities (XLU)",
            "Underweight: Cyclicals, Industrial Commodities (Copper), High Yield (HYG)",
            "Bearish FX: High-beta commodity FX (AUD, NZD), Emerging Market currencies",
        ]

    # --- 5. Yield Curve & Rates Dynamics ---
    irx_val = irx["close"].dropna().iloc[-1] if not irx.empty else None
    fvx_val = fvx["close"].dropna().iloc[-1] if not fvx.empty else None
    tnx_val = tnx["close"].dropna().iloc[-1] if not tnx.empty else None
    tyx_val = tyx["close"].dropna().iloc[-1] if not tyx.empty else None

    yield_levels = {
        "3M (^IRX)": float(irx_val) if irx_val is not None else 0.0,
        "5Y (^FVX)": float(fvx_val) if fvx_val is not None else 0.0,
        "10Y (^TNX)": float(tnx_val) if tnx_val is not None else 0.0,
        "30Y (^TYX)": float(tyx_val) if tyx_val is not None else 0.0,
    }

    yield_spreads = {}
    if tnx_val is not None and irx_val is not None:
        yield_spreads["10Y - 3M"] = round(float(tnx_val - irx_val), 3)
    if tnx_val is not None and fvx_val is not None:
        yield_spreads["10Y - 5Y"] = round(float(tnx_val - fvx_val), 3)
    if tyx_val is not None and tnx_val is not None:
        yield_spreads["30Y - 10Y"] = round(float(tyx_val - tnx_val), 3)

    # Determine Curve Regime (Steepener vs Flattener; Bull vs Bear)
    tnx_1m_change = pct_change(tnx, 21) or 0.0
    s_10_3 = yield_spreads.get("10Y - 3M", 0.0)
    
    # Check 20D change in 10Y-3M spread
    curve_slope_20d_change = 0.0
    if not tnx.empty and not irx.empty:
        t_series = tnx["close"].dropna()
        i_series = irx["close"].dropna()
        t_i = pd.concat([t_series.rename("10y"), i_series.rename("3m")], axis=1).dropna()
        if len(t_i) >= 21:
            spread_now = t_i["10y"].iloc[-1] - t_i["3m"].iloc[-1]
            spread_prior = t_i["10y"].iloc[-21] - t_i["3m"].iloc[-21]
            curve_slope_20d_change = spread_now - spread_prior

    if curve_slope_20d_change >= 0.05:
        # Steepening
        if tnx_1m_change >= 0:
            rates_regime = "Bear Steepening"
            rates_desc = "Long yields rising faster than short yields (term premium / growth / fiscal supply expansion)."
        else:
            rates_regime = "Bull Steepening"
            rates_desc = "Short yields plunging faster than long yields (central bank easing / recession pricing)."
    elif curve_slope_20d_change <= -0.05:
        # Flattening
        if tnx_1m_change >= 0:
            rates_regime = "Bear Flattening"
            rates_desc = "Short yields rising faster than long yields (monetary policy tightening squeeze)."
        else:
            rates_regime = "Bull Flattening"
            rates_desc = "Long yields falling faster than short yields (disinflation / flight to duration safety)."
    else:
        rates_regime = "Neutral / Stable Curve"
        rates_desc = f"Curve slope is steady with 10Y-3M spread at {s_10_3:+.2f}%."

    # --- 6. Cross-Asset Ratios Deep Dive ---
    def summarize_ratio(series: pd.Series, name: str, desc: str) -> dict[str, Any]:
        if series.empty or len(series) < 21:
            return {"name": name, "value": None, "chg_1m_pct": None, "status": "No data", "desc": desc}
        val_curr = float(series.iloc[-1])
        val_prior = float(series.iloc[-21])
        chg_1m = ((val_curr - val_prior) / val_prior * 100.0) if val_prior else 0.0
        sma50 = float(series.tail(50).mean()) if len(series) >= 50 else val_curr
        status = "Uptrend (Bullish)" if val_curr > sma50 and chg_1m > 1.0 else (
            "Downtrend (Bearish)" if val_curr < sma50 and chg_1m < -1.0 else "Consolidating"
        )
        return {
            "name": name,
            "value": round(val_curr, 4),
            "chg_1m_pct": round(chg_1m, 2),
            "status": status,
            "desc": desc,
        }

    ratios = {
        "Copper / Gold": summarize_ratio(
            cu_au_ratio, "Copper / Gold", "Global manufacturing & growth confidence barometer."
        ),
        "Credit Spread (HYG/IEF)": summarize_ratio(
            hyg_ief_ratio, "HYG / IEF (Credit Risk)", "Corporate credit appetite vs safe Treasury duration."
        ),
        "Gold / Silver": summarize_ratio(
            compute_ratio_series(gold, silver), "Gold / Silver", "High ratio indicates risk aversion/liquidity stress."
        ),
        "Discretionary vs Staples (XLY/XLP)": summarize_ratio(
            xly_xlp_ratio, "XLY / XLP", "Consumer cyclical confidence vs defensive non-discretionary."
        ),
        "Tech vs Utilities (XLK/XLU)": summarize_ratio(
            compute_ratio_series(xlk, xlu), "XLK / XLU", "High-growth appetite vs defensive bond-proxy equity."
        ),
        "FX Risk Appetite (AUD/JPY)": summarize_ratio(
            _safe_series(audjpy), "AUD / JPY", "Global risk bellwether & carry trade barometer."
        ),
    }

    # --- 7. Composite Risk Sentiment Index (0 to 100) ---
    # 50 is neutral, > 60 is risk-on, < 40 is risk-off
    sentiment_points = 50.0
    
    # Equities momentum (+/- 15 pts)
    if spx_20d > 2.0:
        sentiment_points += 12
    elif spx_20d > 0.0:
        sentiment_points += 5
    elif spx_20d < -2.0:
        sentiment_points -= 12
    else:
        sentiment_points -= 5

    # Credit Spread HYG/IEF momentum (+/- 15 pts)
    hyg_chg = ratios["Credit Spread (HYG/IEF)"]["chg_1m_pct"]
    if hyg_chg is not None:
        if hyg_chg > 1.0:
            sentiment_points += 12
        elif hyg_chg < -1.0:
            sentiment_points -= 12
        elif hyg_chg < -0.3:
            sentiment_points -= 5

    # Dollar index drag (+/- 10 pts)
    dxy_20d = pct_change(dxy, 20) or 0.0
    if dxy_20d < -1.0:
        sentiment_points += 8  # Weak dollar fuels global liquidity
    elif dxy_20d > 1.5:
        sentiment_points -= 10  # Surging dollar tightens global liquidity

    # AUD/JPY (+/- 10 pts)
    audjpy_20d = pct_change(audjpy, 20) or 0.0
    if audjpy_20d > 1.5:
        sentiment_points += 8
    elif audjpy_20d < -1.5:
        sentiment_points -= 8

    # Copper / Gold (+/- 10 pts)
    cu_au_chg = ratios["Copper / Gold"]["chg_1m_pct"]
    if cu_au_chg is not None:
        if cu_au_chg > 2.0:
            sentiment_points += 8
        elif cu_au_chg < -2.0:
            sentiment_points -= 8

    risk_sentiment_score = float(np.clip(sentiment_points, 0.0, 100.0))

    if risk_sentiment_score >= 75:
        risk_sentiment_label = "Strong Risk-On (Bullish Expansion)"
    elif risk_sentiment_score >= 58:
        risk_sentiment_label = "Moderate Risk-On"
    elif risk_sentiment_score >= 42:
        risk_sentiment_label = "Neutral / Mixed Regime"
    elif risk_sentiment_score >= 25:
        risk_sentiment_label = "Moderate Risk-Off"
    else:
        risk_sentiment_label = "Severe Risk-Off (Defensive Flight)"

    return MacroRegimeReport(
        quadrant_name=quadrant_name,
        quadrant_tag=quadrant_tag,
        growth_score=round(growth_score, 1),
        inflation_score=round(inflation_score, 1),
        risk_sentiment_score=round(risk_sentiment_score, 1),
        risk_sentiment_label=risk_sentiment_label,
        rates_regime=rates_regime,
        rates_description=rates_desc,
        yield_spreads=yield_spreads,
        yield_levels=yield_levels,
        cross_asset_ratios=ratios,
        regime_description=regime_desc,
        asset_implications=asset_implications,
    )
