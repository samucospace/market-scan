# Market Scan — Global Macro, Central Banks & Swing Trading Platform

Personal daily-refresh dashboard: institutional macro regime analysis, central bank policy tracking, early warning anomaly radar, and algorithmic swing trade generator across a multi-asset universe (FX, Equities, Commodities, US Treasury Yields, and Sector ETFs).

## Setup
```bash
pip install -r requirements.txt
```

## Daily update
Run once a day (e.g. via Windows Task Scheduler, after market close):
```bash
python src/fetch.py
```
This pulls ~2 years of daily OHLCV history per ticker from Yahoo Finance (`yfinance`) and stores it in `data/market.db` (SQLite).

## Launching the Dashboard
```bash
python -m streamlit run src/app.py
```

## Core Features & Dashboard Tabs

1. **Top KPI Header**:
   - **Macro Regime Badge**: Identifies the 4-Quadrant macro cycle (*Goldilocks*, *Reflation*, *Stagflation*, *Contraction*).
   - **Risk Sentiment Score (0–100)**: Synthesizes equity momentum, high-yield credit spreads (`HYG/IEF`), FX carry (`AUD/JPY`), and safe haven flows.
   - **Yield Curve Dynamics**: Classifies curve state into *Bull/Bear Steepening* or *Bull/Bear Flattening* with 10Y-3M and 10Y-5Y spreads.
   - **Next Central Bank Meeting Banner**: Real-time countdown to the next global interest rate decision.

2. **🎯 Top 3 Swing Trades**:
   - Automatically selects the 3 highest-conviction swing ideas tailored for **multi-day to multi-week holding horizons** (3 to 20 trading days).
   - Ensures **asset class diversification** across Equities, Commodities, FX, and Sectors.
   - Provides complete **Trade Blueprints**: Entry Zone, Stop Loss, Target 1, Target 2, Risk-to-Reward Ratio ($\ge 2.0$), Macro & Technical theses, and trade management rules.
   - Interactive Plotly chart with Bollinger Bands, 20 & 50 SMAs, and plotted trade execution levels.

3. **🌐 Market Regime & Macro Matrix**:
   - 2D Growth vs Inflation Quadrant Matrix.
   - US Treasury Yield Curve Profile (3M, 5Y, 10Y, 30Y yields).
   - Key Cross-Asset Ratios: Copper/Gold (global growth), HYG/IEF (credit stress), Gold/Silver (crisis fear), XLY/XLP (consumer cyclical confidence), XLK/XLU (risk appetite), AUD/JPY (FX risk barometer).

4. **🏛️ Central Banks & Interest Rates (NEW)**:
   - **G10 + MAS Central Bank Policy Matrix**: Compares Fed (USD), ECB (EUR), BOJ (JPY), BOE (GBP), RBA (AUD), BOC (CAD), SNB (CHF), RBNZ (NZD), and MAS (SGD).
   - **Interest Rate Differentials vs Fed**: Yield spreads driving structural FX trends and carry trade viability.
   - **Hawkish vs Dovish Policy Spectrum**: Interactive ranking of central bank stances from most dovish to most hawkish.
   - **Meeting Schedule Timeline**: Comprehensive chronological calendar of all upcoming decision dates with countdowns.
   - **Central Bank Dossiers**: Policy summary, inflation/labor drivers, and tactical FX implications per bank.

5. **⚡ Early Signs & Inflection Radar**:
   - Active anomaly and divergence alerts (e.g. Credit vs Equities, Copper/Gold vs SPX, AUD/JPY lead turns, Dollar Squeeze).
   - Market Breadth Gauges: % of universe above 20-day and 50-day SMAs, Overbought & Oversold asset clusters.
   - **Volatility Squeeze Scanner**: Highlights coiling assets (Bollinger Bandwidth $\le 4.0\%$) preparing for explosive multi-week breakouts.

6. **📊 Watchlist & Category Rankings**:
   - Ranked performance tables sorted by % change (Daily / Weekly / Monthly / Quarterly).
   - Customizable density (Compact, Balanced, Spacious) or full Table View mode with RSI and 20 SMA indicators.

7. **🔍 All Setups Screener**:
   - Complete filterable table of all 59 watchlist assets.
   - Filter by Strategy Archetype (*Trend Pullback*, *Volatility Breakout*, *Mean Reversion*), Direction (*LONG*, *SHORT*), and minimum Conviction Score.

8. **📰 Movers & Catalyst News**:
   - Google News integration providing contextual driver explanations for top gainers and decliners.

## Running Tests
To verify all calculations and modules end-to-end:
```bash
python scripts/test_engine.py
```
