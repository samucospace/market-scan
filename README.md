# Market Scan — Global Macro, Central Banks & Swing Trading Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.38%2B-FF4B4B.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An institutional-grade macro regime analysis, central bank policy tracker, early warning anomaly radar, and algorithmic swing trade generator across a diversified multi-asset universe (FX, Equities, Commodities, US Treasury Yields, and Sector ETFs).

---

## ⚡ Quickstart

### 1. Prerequisites & Environment Setup
Clone the repository and install the dependencies:
```bash
git clone https://github.com/samucospace/market-scan.git
cd market-scan
pip install -r requirements.txt
```

### 2. Fetch Market Data
Run the daily ingestion script to pull ~2 years of daily OHLCV history for all 64 tracked assets from Yahoo Finance into a local high-performance SQLite database:
```bash
python src/fetch.py
```
> **Note**: This populates `data/market.db`. Scheduled daily updates can be automated via Windows Task Scheduler or cron after major market closes.

### 3. Launch the Interactive Dashboards

- **Dashboard v2.0 (New Tactical Ratings Matrix, Currency Strength & Methodology):**
  ```bash
  python -m streamlit run src/app_v2.py
  ```

- **Dashboard v1.0 (Original Macro Regime, Central Banks & Swing Trade Platform):**
  ```bash
  python -m streamlit run src/app.py
  ```

---

## ⚡ Dashboard v2.0 — Cross-Asset Tactical Matrix

Dashboard v2.0 (`src/app_v2.py`) provides an institutional multi-factor matrix across **12 core global assets**, categorizing each asset into **Bullish 🟢**, **Neutral 🟡**, or **Bearish 🔴** across 4 key dimensions:

### Tracked Securities (12 Assets)
- **FX:** `AUDUSD`, `EURUSD`, `GBPUSD`, `USDJPY`, `NZDUSD`, `USDCAD`
- **Equities:** `US500` (S&P 500 Index - `^GSPC`), `US Tech 100` (Nasdaq 100 Index - `^NDX`)
- **Commodities:** `Brent Crude` (`BZ=F`), `Copper` (`HG=F`), `Gold` (`GC=F`), `Silver` (`SI=F`)

### The 4 Rating Columns
1. **Primary Trend (100-day EMA):** Evaluates whether price is trading above ($\ge +0.30\% \to$ Bullish), below ($\le -0.30\% \to$ Bearish), or within ($\pm 0.30\% \to$ Neutral) of the 100-day Exponential Moving Average, with 5-day slope verification.
2. **Macro Environment (4 Quadrants):** Maps the current Growth vs Inflation regime (*Goldilocks*, *Reflation*, *Stagflation*, *Contraction*) to an asset-specific institutional response matrix.
3. **Daily Correlated Assets:** Uses 60-day rolling return correlations ($\rho_i$) with benchmark intermarket drivers (DXY, 10Y yields, Copper, Crude Oil, S&P 500) and today's returns to compute a weighted impulse ($\text{Impulse} > +0.05\% \to$ Bullish, $< -0.05\% \to$ Bearish).
4. **Tactical Technicals:** Synthesizes 20-day EMA (+1/-1), RSI 14 (+1/0/-1), Bollinger Bands %B (+1/0/-1), and 10/20 EMA trend stack (+1/-1) into a composite $-4$ to $+4$ score ($\ge +2 \to$ Bullish, $\le -2 \to$ Bearish).

### Dashboard v2.0 Tabs
- **Tab 1: 📊 Tactical Ratings Table:** Live rating table, asset-class and stance filters, summary cards, and an interactive drill-down inspector with technical price charts.
- **Tab 2: 💱 Currency Strength vs JPY:** TradingView Pine Script relative strength model `(close - 200 SMA) / close` for AUD, EUR, USD, NZD, CHF, GBP, and CAD with leaderboard rankings.
- **Tab 3: 📘 Methodology & Logic Rules:** Complete, transparent institutional documentation detailing all formulas, cutoffs, and the full 12-asset $\times$ 4-quadrant response matrix for user auditing.

---

## 🏛️ Core Features & Dashboard Capabilities (Dashboard v1.0)

### 1. Top KPI Header
- **Macro Regime Badge**: Automatically identifies the current 4-Quadrant macro cycle (*Goldilocks*, *Reflation*, *Stagflation*, *Contraction*).
- **Risk Sentiment Score (0–100)**: Synthesizes equity momentum, high-yield credit spreads (`HYG/IEF`), FX carry (`AUD/JPY`), and safe-haven flows.
- **Yield Curve Dynamics**: Classifies curve state (*Bull/Bear Steepening* or *Bull/Bear Flattening*) with 10Y-3M, 10Y-5Y, and 30Y-10Y spreads.
- **Next Central Bank Decision Banner**: Real-time countdown to the next upcoming global interest rate decision.

### 2. 🎯 Top 3 Algorithmic Swing Trades
- Automatically screens candidate setups and selects the 3 highest-conviction trade ideas tailored for **multi-day to multi-week holding horizons** (3 to 20 trading days).
- Enforces **asset class diversification** across Equities, Commodities, FX, and Sectors.
- Generates complete **Trade Blueprints**: Entry Zone, Stop Loss, Target 1, Target 2, Risk-to-Reward Ratio ($\ge 2.0$), Macro & Technical theses, and trade invalidation rules.
- Interactive Plotly chart with Bollinger Bands, 20 & 50 SMAs, and plotted trade execution levels.

### 3. 🌐 Market Regime & Macro Matrix
- **2D Growth vs. Inflation Quadrant Matrix** with historical regime shift trajectories.
- **US Treasury Yield Curve Profile** (13-week, 5Y, 10Y, and 30Y yields).
- **Key Cross-Asset Intermarket Ratios**: Copper/Gold (global growth barometer), HYG/IEF (credit risk/spreads), Gold/Silver (crisis fear), XLY/XLP (consumer cyclical confidence), XLK/XLU (risk appetite), and AUD/JPY (FX risk barometer).

### 4. 🏛️ Central Banks & Interest Rates
- **G10 + MAS Central Bank Policy Matrix**: Comprehensive tracking of the Fed (USD), ECB (EUR), BOJ (JPY), BOE (GBP), RBA (AUD), BOC (CAD), SNB (CHF), RBNZ (NZD), and MAS (SGD).
- **Rate Differentials vs Fed**: Yield spreads driving structural currency trends and carry trade viability.
- **Hawkish vs Dovish Spectrum**: Interactive ranking of global central bank policy stances from most dovish to most hawkish.
- **Decision Schedule Timeline**: Chronological calendar of all upcoming decision dates with live countdowns.
- **Central Bank Dossiers**: Policy summaries, inflation/labor key drivers, and tactical FX implications.

### 5. ⚡ Early Warning & Inflection Radar
- **Active Divergence & Anomaly Alerts**: Early warning detection of structural intermarket divergences (e.g., Credit leading Equities, Copper/Gold decoupling from SPX, AUD/JPY lead turns, Dollar Squeeze).
- **Market Breadth Gauges**: Universe percentage trading above 20-day and 50-day SMAs, plus Overbought and Oversold asset clusters.
- **Volatility Squeeze Scanner**: Pinpoints coiling assets (Bollinger Bandwidth $\le 4.0\%$) preparing for explosive multi-week breakouts.

### 6. 📊 Watchlist & Category Rankings
- Ranked performance tables sorted by % change across Daily, Weekly, Monthly, and Quarterly timeframes.
- Density toggle (*Compact*, *Balanced*, *Spacious*) and full Table View with integrated RSI and 20 SMA indicators.

### 7. 💱 JPY Relative Strength
- Daily chart of AUD, EUR, USD, NZD, CHF, GBP, and CAD against JPY.
- Each line plots `(close - 200-day SMA) / close`, matching the supplied TradingView indicator, with selectable chart lookbacks.

### 8. 🔍 All Setups Screener
- Complete filterable table of all 64 watchlist assets.
- Filter by Strategy Archetype (*Trend Pullback*, *Volatility Breakout*, *Mean Reversion*), Direction (*LONG*, *SHORT*), and minimum Conviction Score.

### 9. 📰 Catalysts & Contextual News
- Integrated market news feed providing real-time macro catalysts and fundamental driver context for top gainers and decliners.

---

## 🧪 Verification & Automated Testing

To run the automated test suite verifying all quantitative models, central bank matrices, divergence radars, trade generation engines, and v2 tactical engine:
```bash
# Dashboard v2.0 Tactical Engine Verification
python scripts/test_v2_engine.py

# Dashboard v1.0 Engines Verification
python scripts/test_engine.py
python scripts/test_saved_trades.py
```

---

## 📁 Project Structure

```
market-scan/
├── config/
│   ├── central_banks.yaml    # Central bank rates, schedules, and FX drivers
│   └── watchlist.yaml        # 64 cross-asset tickers grouped by asset class
├── data/
│   └── market.db             # Local SQLite database (git-ignored)
├── scripts/
│   ├── test_engine.py        # End-to-end engine verification suite (v1)
│   ├── test_saved_trades.py  # Trade inventory & invalidation tests (v1)
│   ├── test_v2_engine.py     # Multi-factor ratings engine verification (v2)
│   └── verify_tickers.py     # Yahoo Finance ticker live check utility
├── src/
│   ├── app.py                # Dashboard v1.0 Streamlit application
│   ├── app_v2.py             # Dashboard v2.0 Streamlit application
│   ├── central_banks.py      # Central bank policy & calendar analytics
│   ├── early_signals.py      # Divergence detection, breadth & squeeze scanner
│   ├── fetch.py              # Yahoo Finance batch ingestion job
│   ├── historical_analysis.py# Historical regime lookbacks & momentum
│   ├── metrics.py            # Technical indicators (RSI, ATR, Bollinger, SMA, EMA)
│   ├── regime.py             # Macro regime classification & yield curve analysis
│   ├── storage.py            # SQLite schema, upsert, and query layer
│   ├── swing_screener.py     # Algorithmic trade generation & blueprinting
│   └── tactical_engine.py    # Dashboard v2.0 quantitative multi-factor ratings engine
├── .gitignore
├── currency_strength_indicator
├── LICENSE
├── requirements.txt
├── SPEC.md
└── tickers.xlsx
```

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright &copy; 2026 samucospace.
