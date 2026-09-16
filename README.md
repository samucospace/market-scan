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
Run the daily ingestion script to pull ~2 years of daily OHLCV history for all 59 tracked assets from Yahoo Finance into a local high-performance SQLite database:
```bash
python src/fetch.py
```
> **Note**: This populates `data/market.db`. Scheduled daily updates can be automated via Windows Task Scheduler or cron after major market closes.

### 3. Launch the Interactive Dashboard
Launch the Streamlit analytical platform:
```bash
python -m streamlit run src/app.py
```

---

## 🏛️ Core Features & Dashboard Capabilities

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

### 7. 🔍 All Setups Screener
- Complete filterable table of all 59 watchlist assets.
- Filter by Strategy Archetype (*Trend Pullback*, *Volatility Breakout*, *Mean Reversion*), Direction (*LONG*, *SHORT*), and minimum Conviction Score.

### 8. 📰 Catalysts & Contextual News
- Integrated market news feed providing real-time macro catalysts and fundamental driver context for top gainers and decliners.

---

## 🧪 Verification & Automated Testing

To run the automated test suite verifying all quantitative models, central bank matrices, divergence radars, and trade generation engines:
```bash
python scripts/test_engine.py
python scripts/test_saved_trades.py
```

---

## 📁 Project Structure

```
market-scan/
├── config/
│   ├── central_banks.yaml    # Central bank rates, schedules, and FX drivers
│   └── watchlist.yaml        # 59 cross-asset tickers grouped by asset class
├── data/
│   └── market.db             # Local SQLite database (git-ignored)
├── scripts/
│   ├── test_engine.py        # End-to-end engine verification suite
│   ├── test_saved_trades.py  # Trade inventory & invalidation tests
│   └── verify_tickers.py     # Yahoo Finance ticker live check utility
├── src/
│   ├── app.py                # Main Streamlit dashboard application
│   ├── central_banks.py      # Central bank policy & calendar analytics
│   ├── early_signals.py      # Divergence detection, breadth & squeeze scanner
│   ├── fetch.py              # Yahoo Finance batch ingestion job
│   ├── historical_analysis.py# Historical regime lookbacks & momentum
│   ├── metrics.py            # Technical indicators (RSI, ATR, Bollinger, SMA)
│   ├── regime.py             # Macro regime classification & yield curve analysis
│   ├── storage.py            # SQLite schema, upsert, and query layer
│   └── swing_screener.py     # Algorithmic trade generation & blueprinting
├── .gitignore
├── LICENSE
├── requirements.txt
├── SPEC.md
└── tickers.xlsx
```

---

## 📄 License

Distributed under the [MIT License](LICENSE). Copyright &copy; 2026 samucospace.
