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
This pulls ~3 months of daily history per ticker from Yahoo Finance
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

## Editing the watchlist
Edit `config/watchlist.yaml`, then run:
```
python scripts/verify_tickers.py
```
to confirm every ticker resolves against Yahoo Finance before the next fetch.
