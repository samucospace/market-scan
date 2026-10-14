# Market Scan — Investment Dashboard Spec

## 1. Purpose
A personal dashboard that shows **price changes** (daily / weekly / monthly, toggleable) across a
watchlist of assets (FX, indices, futures/commodities, bond yields, sector ETFs — no crypto),
refreshed **once per day** from a free data source. Not for real-time trading; delayed/EOD data is fine.
Displayed as a **ranked list, sorted by % change (highest first)** — not a heatmap grid (initial version).

## 2. Data Source Decision

### Chosen: Yahoo Finance via `yfinance` (Python)
- **Cost:** Free, no API key, no signup.
- **Coverage:** Global stocks, ETFs, indices, FX, bonds/futures — everything needed here, crypto excluded by choice.
- **Granularity:** Daily OHLC (`interval="1d"`), full history back to listing (`period="max"`), also weekly/monthly resample.
- **Batch use:** `yf.download(["AAPL","MSFT",...], period="3mo", interval="1d", group_by="ticker", threads=True)` fetches many tickers in one call — well suited to a once-a-day batch job.
- **Legal/ToS note:** `yfinance` is an unofficial wrapper around Yahoo's public endpoints, "intended for personal use only," which matches this project exactly. Not affiliated with Yahoo; could break if Yahoo changes its site, but is the most widely used, actively maintained option (25k+ GitHub stars, releases every few weeks) and requires zero cost/signup — the right tradeoff for a personal, once-daily job.
- **Rate limiting risk:** Yahoo can soft-block an IP that hammers requests. Mitigation: single run per day, small watchlist (tens, not thousands, of tickers), add small delay/backoff and retry logic, cache results locally so the dashboard never calls the network live.

### Rejected alternatives (for reference)
| API | Free tier | Why not first choice |
|---|---|---|
| Alpha Vantage | 25 requests/day, 5/min | Too restrictive once watchlist > ~20 symbols per update |
| Twelve Data | 800 requests/day, 8/min | Fine, but requires API key/account; yfinance needs nothing and covers more symbols per call |
| Financial Modeling Prep | 250 requests/day | EOD only on free tier, US-centric on free plan |
| Polygon.io | No usable free EOD tier for this use case | Paid plans required for meaningful history |

**Fallback plan:** keep the data-fetch layer behind a small adapter interface so Twelve Data (free
800 calls/day) can be swapped in as a backup source with minimal code changes if Yahoo ever blocks
the job.

## 3. Watchlist
Stored in `config/watchlist.yaml`, grouped by asset class. This is the user's actual list, mapped
from their original tickers (mixed TradingView/broker symbols) to Yahoo Finance equivalents — crypto
(`BTCUSD`) excluded per instruction. Groups: **FX**, **Equity Indices**, **Commodities & Futures**,
**US Government Bond Yields**, **Sector ETFs**, and **Credit Proxies**. The original watchlist was
checked against Yahoo Finance via `scripts/verify_tickers.py`; four JPY crosses were later added
for the currency-strength indicator and should be checked with the same script.

Notes on symbols that needed interpretation or were dropped (accepted as-is):
- `CN1!` (China A50 futures) and `FEF1!`/`TIO1!` (iron ore futures) — dropped, no Yahoo equivalent available for free.
- `FOOD` — dropped, no identifiable single ticker/index matched this entry.
- `IDX80` (Indonesia) — mapped to `^JKSE` (Jakarta Composite) as an approximation, not the same index.
- `ME` — interpreted as Mexico, mapped to `^MXX`.
- `TT1!` — interpreted as Cotton No. 2 futures (`CT=F`).
- `EURJPY=X`, `NZDJPY=X`, `CHFJPY=X`, and `GBPJPY=X` — added to support the currency-strength indicator.
- "Government bonds (1/3/5/10yr, US/China/AU/DE/NZ/CA)" — only **US** Treasury yields (`^IRX`, `^FVX`,
  `^TNX`, `^TYX`) are available free on Yahoo; non-US government bond yields have no good free source
  and are not included.

User can add/remove tickers in the yaml without touching code — re-run `scripts/verify_tickers.py`
after any change.

## 4. Architecture

```mermaid
flowchart LR
    A[Scheduled Job\n(Task Scheduler / cron, once daily)] --> B[Fetch Script\nyfinance batch download]
    B --> C[Compute % change\n1D / 1W / 1M]
    C --> D[(Local storage\nSQLite or Parquet/CSV)]
    D --> E[Dashboard App\nStreamlit]
    E --> F[Browser UI\nRanked list + toggle]
```

- **Fetch script** (`fetch.py`): runs once/day, pulls ~2 months of daily history per ticker (enough
  to compute 1D/1W/1M change and handle holidays/weekends), writes results to local storage.
- **Storage**: SQLite file (`data/market.db`) — one table of daily OHLC per ticker, append-only.
  Simple, no server needed, easy to inspect/query.
- **Dashboard app**: Streamlit (fastest way to build an interactive personal dashboard in Python,
  runs locally with `streamlit run app.py`, no separate frontend/backend to maintain).
  Reads from SQLite, computes % changes, and renders the ranked list.
- **Scheduling**: Windows Task Scheduler running `python fetch.py` once a day after market close
  (e.g., 22:00 local time to catch US close + buffer). No need for a cloud server.

## 5. Data Model (SQLite)
```sql
CREATE TABLE prices (
    ticker TEXT NOT NULL,
    date   TEXT NOT NULL,   -- ISO date, YYYY-MM-DD
    open   REAL,
    high   REAL,
    low    REAL,
    close  REAL,
    volume INTEGER,
    PRIMARY KEY (ticker, date)
);
```
Percent changes are computed on read (not stored), so definitions can change without a backfill:
- **Daily change** = last close vs prior close.
- **Weekly change** = last close vs close ~5 trading days ago (or prior Friday close).
- **Monthly change** = last close vs close ~21 trading days ago (or prior month-end close).

## 6. Dashboard UI/UX
- Single-page Streamlit app.
- **Toggle control** (radio buttons or segmented control) at top: `Daily | Weekly | Monthly`.
- **Ranked list** (not a heatmap, for this first version): every ticker in the watchlist, sorted by
  % change for the selected period, highest gain first. Each row shows: ticker, group/asset class,
  % change (color-coded text — green positive, red negative — for a quick visual cue), and last
  close price.
- Header shows "Data as of {last fetch date}" so staleness is obvious.
- Optional filter: dropdown/multiselect to show only one asset-class group at a time.
- Optional click-through: selecting a row shows a small price line chart for that ticker (Streamlit
  session state + Plotly line chart).
- A heatmap grid view can be added later as a second display mode once the ranked list is working.
- JPY relative-strength tab charts AUDJPY, EURJPY, USDJPY, NZDJPY, CHFJPY, GBPJPY, and CADJPY using
  `(close - 200-day SMA) / close` from stored daily closes.

## 7. Tech Stack Summary
| Layer | Choice | Reason |
|---|---|---|
| Data fetch | Python + `yfinance` | Free, no key, batch-friendly |
| Storage | SQLite | Zero-config, file-based, easy backup |
| Scheduling | Windows Task Scheduler | Already available on user's OS, no infra |
| Dashboard | Streamlit + Plotly | Fastest path to an interactive local dashboard, pure Python |
| Config | YAML watchlist file | Easy to edit without touching code |

## 8. Project Structure
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
├── currency_strength_indicator
├── requirements.txt
└── README.md
```

## 9. Build Plan (milestones)
1. `storage.py` — SQLite schema + upsert helper.
2. `fetch.py` — read watchlist, `yf.download` batch, upsert into SQLite, log success/failures.
3. `metrics.py` — 1D/1W/1M % change functions operating on the stored data.
4. `app.py` — Streamlit page: period toggle, ranked list sorted by % change, last-updated timestamp.
5. Task Scheduler entry to run `fetch.py` daily.
6. Manual QA: missing-data handling (new listings, holidays), stale-data banner if fetch failed.

## 10. Dashboard v2.0 Specification — Cross-Asset Tactical Ratings Matrix

### 10.1 Objectives & Design Principles
- **Coexistence:** Leave Dashboard v1.0 (`src/app.py`) intact while providing a dedicated v2.0 application (`src/app_v2.py`).
- **Core Focus:** Multi-factor institutional rating table across **12 global securities** with 3 distinct tabs:
  1. **Tab 1: 📊 Tactical Ratings Table**
  2. **Tab 2: 💱 Currency Strength vs JPY** (Pine Script Relative Strength model)
  3. **Tab 3: 📘 Quantitative Logic & Methodology** (transparent rules and 4-quadrant response matrix for user audit)

### 10.2 Tracked Securities Universe (12 Assets)
1. `AUDUSD` (`AUDUSD=X`) — Australian Dollar / US Dollar
2. `EURUSD` (`EURUSD=X`) — Euro / US Dollar
3. `GBPUSD` (`GBPUSD=X`) — British Pound / US Dollar
4. `USDJPY` (`USDJPY=X`) — US Dollar / Japanese Yen
5. `NZDUSD` (`NZDUSD=X`) — New Zealand Dollar / US Dollar
6. `US500` (`^GSPC`) — S&P 500 Index
7. `US Tech 100` (`^NDX`) — Nasdaq 100 Index
8. `USDCAD` (`USDCAD=X`) — US Dollar / Canadian Dollar
9. `Brent Crude` (`BZ=F`) — Brent Crude Oil Futures
10. `Copper` (`HG=F`) — Copper Futures (COMEX)
11. `Gold` (`GC=F`) — Gold Futures (COMEX)
12. `Silver` (`SI=F`) — Silver Futures (COMEX)

### 10.3 The 4 Quantitative Rating Dimensions

#### 1. Primary Trend (100-day EMA)
- **Model:** Calculates 100-day Exponential Moving Average ($\text{EMA}_{100}$) on daily closing prices.
- **Rules:**
  - $\text{Price} \ge \text{EMA}_{100} \times (1 + 0.30\%) \implies \mathbf{Bullish}$
  - $\text{Price} \le \text{EMA}_{100} \times (1 - 0.30\%) \implies \mathbf{Bearish}$
  - Within $\pm 0.30\% \implies \mathbf{Neutral}$ (testing trendline / consolidating)
  - Also incorporates 5-day slope of $\text{EMA}_{100}$ to confirm acceleration.

#### 2. Macro Environment (4-Quadrant Growth vs. Inflation Framework)
- **Model:** Uses `regime.py`'s composite Growth (-100 to +100) and Inflation (-100 to +100) scores:
  - *Quadrant 1: Goldilocks / Disinflationary Expansion* (Growth $\ge 0$, Inflation $\le 0$)
  - *Quadrant 2: Reflation / Overheating Expansion* (Growth $\ge 0$, Inflation $> 0$)
  - *Quadrant 3: Stagflation / Late Cycle Squeeze* (Growth $< 0$, Inflation $> 0$)
  - *Quadrant 4: Contraction / Deflationary Risk-Off* (Growth $< 0$, Inflation $\le 0$)
- **Asset Class Mapping:** Each asset is mapped to an institutional stance based on macroeconomic transmission theory:
  - Cyclical equities (`US500`, `US Tech 100`) thrive in Goldilocks and Reflation, suffer in Stagflation and Contraction.
  - Industrial commodities (`Copper`, `Brent Crude`) thrive in Reflation, struggle in Contraction.
  - Precious metals (`Gold`) excel in Stagflation and Contraction (flight to safety + falling real rates).
  - High-beta FX (`AUDUSD`, `NZDUSD`) track global growth and commodity demand.

#### 3. Daily Correlated Assets (Intermarket Transmission)
- **Model:** 60-trading-day rolling Pearson correlation ($\rho_i$) with benchmark intermarket drivers (DXY, 10Y yields, Copper, Crude Oil, S&P 500).
- **Formula:**
  $$\text{Impulse} = \frac{\sum_i (\rho_i \times R_{\text{today}, i})}{\sum_i |\rho_i|}$$
- **Thresholds:**
  - $\text{Impulse} > +0.05\% \implies \mathbf{Bullish}$
  - $\text{Impulse} < -0.05\% \implies \mathbf{Bearish}$
  - $-0.05\% \le \text{Impulse} \le +0.05\% \implies \mathbf{Neutral}$

#### 4. Tactical Technicals (Composite Quantitative Score)
- **Model:** 4-factor scoring model spanning trend, momentum, and volatility channels (range: $-4$ to $+4$):
  - 20-day EMA: Price $> 20$ EMA ($+1$) vs Price $< 20$ EMA ($-1$)
  - RSI (14): RSI $> 55$ ($+1$) vs RSI $< 45$ ($-1$) vs $45 \le \text{RSI} \le 55$ ($0$)
  - Bollinger Bands %B: $\%B > 0.60$ ($+1$) vs $\%B < 0.40$ ($-1$) vs $0.40 \le \%B \le 0.60$ ($0$)
  - Short-term Trend Stack: 10 EMA $> 20$ EMA ($+1$) vs 10 EMA $< 20$ EMA ($-1$)
- **Thresholds:**
  - $\text{Score} \ge +2 \implies \mathbf{Bullish}$
  - $\text{Score} \le -2 \implies \mathbf{Bearish}$
  - $\text{Score} \in \{-1, 0, +1\} \implies \mathbf{Neutral}$
