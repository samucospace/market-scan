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
- One card per category (all categories visible on one screen).
- Card density toggle: Compact (4 columns), Balanced (3 columns), Spacious (2 columns).
- Top Movers section with 5 tabs (top 5 instruments by % change), each tab listing
	recent Google News search articles to help explain the move.
- Historical Momentum Check section:
	- Tests whether top daily movers continue rising vs baseline (1-day and 5-day horizons).
	- Shows persistence stats (how often top movers remain in the top bucket after 1/2/5 days).
	- Includes top-1 frequency and per-group continuation breakdowns.
	- CSV download buttons for continuation, persistence, and group breakdown tables.
- Data freshness indicators at the top:
	- Latest market date from the stored prices.
	- Database updated timestamp including time-of-day (local time).
	- Market freshness badge (today / 1 day behind / 2+ days behind).

Note: Top Movers news requires internet access when loading the dashboard.
Note: Statistical confidence still depends on data depth and regime variety, but a 2-year default window improves robustness vs a short sample.

## Editing the watchlist
Edit `config/watchlist.yaml`, then run:
```
python scripts/verify_tickers.py
```
to confirm every ticker resolves against Yahoo Finance before the next fetch.
