"""End-to-end test suite for the Market Scan Macro & Swing Trading Engine."""
import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
from regime import calculate_macro_regime
from early_signals import scan_early_signals
from swing_screener import scan_swing_trades, generate_trade_chart
from metrics import calculate_rsi, calculate_atr, calculate_bollinger_bands
from storage import get_connection, get_prices


def main():
    print("========================================")
    print("TESTING MACRO REGIME ENGINE...")
    print("========================================")
    conn = get_connection()
    regime = calculate_macro_regime(conn)
    print(f"Quadrant: {regime.quadrant_name} ({regime.quadrant_tag})")
    print(f"Growth Score: {regime.growth_score:+.1f} | Inflation Score: {regime.inflation_score:+.1f}")
    print(f"Risk Sentiment: {regime.risk_sentiment_score:.1f} ({regime.risk_sentiment_label})")
    print(f"Rates Regime: {regime.rates_regime} - {regime.rates_description}")
    print("Yield Spreads:", regime.yield_spreads)
    print(f"Key Cross-Asset Ratios count: {len(regime.cross_asset_ratios)}")
    assert regime.quadrant_name is not None
    assert len(regime.asset_implications) > 0

    print("\n========================================")
    print("TESTING EARLY WARNING & DIVERGENCE RADAR...")
    print("========================================")
    early = scan_early_signals(conn)
    print(f"Active Alerts: {len(early.alerts)}")
    for a in early.alerts:
        print(f" - [{a.severity}] {a.title}: {a.implication}")
    print(f"Breadth: {early.breadth.pct_above_sma20:.1f}% > 20 SMA, {early.breadth.pct_above_sma50:.1f}% > 50 SMA")
    print(f"Squeeze Candidates: {len(early.squeeze_candidates)}")
    for sq in early.squeeze_candidates[:3]:
        print(f" - Squeeze: {sq.ticker} (Bandwidth {sq.bandwidth}%, RSI {sq.rsi})")

    print("\n========================================")
    print("TESTING TOP 3 SWING TRADE SCREENER...")
    print("========================================")
    watchlist_path = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"
    with open(watchlist_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    watchlist = []
    for g, items in cfg["groups"].items():
        for item in items:
            watchlist.append({"ticker": item["ticker"], "group": g, "note": item.get("note", "")})

    res = scan_swing_trades(watchlist, conn)
    print(f"Total Candidate Setups Screened: {len(res.all_setups)}")
    print(f"Top 3 Selected Trades: {len(res.top_3_trades)}")

    for idx, trade in enumerate(res.top_3_trades, 1):
        print(f"\n--- Trade #{idx}: {trade.direction} {trade.ticker} ({trade.group}) ---")
        print(f"Setup Archetype: {trade.archetype} | Score: {trade.conviction_score}/100 | Horizon: {trade.holding_period}")
        print(f"Current: {trade.last_price} | Entry: {trade.entry_zone}")
        print(f"Stop Loss: {trade.stop_loss} (-{trade.risk_pct}%) | Target 1: {trade.target_1} (+{trade.reward_pct}%) | R:R: {trade.risk_reward_ratio}:1")
        print(f"Macro Thesis: {trade.macro_thesis}")
        print(f"Technical Thesis: {trade.technical_thesis}")
        
        prices = get_prices(conn, trade.ticker)
        fig = generate_trade_chart(prices, trade)
        assert fig is not None
        print(f"Plotly chart generated successfully ({len(fig.data)} traces).")

    conn.close()
    print("\n>>> ALL ENGINE TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    main()
