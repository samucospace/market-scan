# Market Scan

Personal daily-refresh dashboard: ranked list of watchlist assets (FX, indices,
commodities/futures, US Treasury yields, sector ETFs) sorted by % change,
toggleable between Daily / Weekly / Monthly. See [SPEC.md](SPEC.md) for the
full design.

## Setup
```
pip install -r requirements.txt
```

## Daily update
Run once a day (e.g. via Windows Task Scheduler, after market close):
```
python src/fetch.py
```
This pulls ~2 years of daily history per ticker from Yahoo Finance
(`yfinance`) and stores it in `data/market.db` (SQLite).

## Dashboard
```
python -m streamlit run src/app.py
```
> If plain `streamlit run ...` fails with `NativeCommandFailed`/`ApplicationFailedException`
> in PowerShell, it means the `streamlit` executable isn't on your PATH — use the
> `python -m streamlit ...` form above instead (or add Python's `Scripts` folder to PATH).

Opens a local browser tab showing the watchlist ranked by % change for the
selected period.

Dashboard highlights:
- Market Regime Check (top of page, toggleable between 1 Day, 1 Week, and 1 Month lookback):
	- Rates Impulse — average US Treasury yield change vs average major equity index change
	  (pro-growth expansion vs inflation scare/tightening).
	- FX & Dollar Strength — US Dollar Index (DXY) direction as a global financial conditions signal.
	- Copper vs Oil — cross-checks industrial cyclical demand against oil-led moves.
	- Credit Stress — HYG (high yield) vs IEF (Treasuries) relative performance, cross-checked
	  against equity direction, as a proxy for credit spread stress (no free real OAS spread feed).
- One card per category (all categories visible on one screen).
- Card density toggle: Compact (4 columns), Balanced (3 columns), Spacious (2 columns).
- Top 5 / Bottom 5 Movers sections below the cards, each with tabs per instrument listing
	recent Google News search articles to help explain the move.
- Data freshness indicators at the top:
	- Latest market date from the stored prices.
	- Database updated timestamp including time-of-day (local time).
	- Market freshness badge (today / 1 day behind / 2+ days behind).

Note: Top/Bottom Movers news requires internet access when loading the dashboard.
Note: The Historical Momentum Check analysis tab has been removed from the dashboard for now
(the underlying code remains in `src/historical_analysis.py` for future re-enable).

## Editing the watchlist
Edit `config/watchlist.yaml`, then run:
```
python scripts/verify_tickers.py
```
to confirm every ticker resolves against Yahoo Finance before the next fetch.
