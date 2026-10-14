"""Automated test script for Global 10Y Sovereign Yields & Differentials Engine."""
import sys
from pathlib import Path

src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from sovereign_yields import (
    SOVEREIGN_10Y_BENCHMARKS,
    FX_YIELD_PAIRS,
    get_latest_sovereign_yields,
    get_fx_yield_differentials,
    get_pair_yield_history,
)
from storage import get_connection


def test_sovereign_yields():
    print("Testing Global 10Y Sovereign Yields Engine...")
    assert len(SOVEREIGN_10Y_BENCHMARKS) == 8, f"Expected 8 benchmark countries, got {len(SOVEREIGN_10Y_BENCHMARKS)}"
    assert len(FX_YIELD_PAIRS) == 14, f"Expected 14 FX yield pairs, got {len(FX_YIELD_PAIRS)}"

    conn = get_connection()

    # 1. Test live / stored sovereign yields
    yields = get_latest_sovereign_yields(conn)
    assert len(yields) == 8, f"Expected 8 sovereign yield results, got {len(yields)}"
    print("\nGlobal 10Y Sovereign Debt Market Rates:")
    print("-" * 70)
    for curr, data in yields.items():
        assert "yield" in data and data["yield"] > 0, f"Invalid yield for {curr}"
        print(f"  {data['flag']} {curr:<4} | {data['country']:<22} | Yield: {data['yield']:.3f}% | 1D: {data.get('change_bps', 0.0):+.1f} bps")

    # 2. Test FX Yield Differentials
    diffs = get_fx_yield_differentials(conn)
    assert len(diffs) == 14, f"Expected 14 differential results, got {len(diffs)}"
    print("\nWatchlist FX 10-Year Yield Differentials:")
    print("-" * 80)
    print(f"{'Pair':<10} | {'Spot':<10} | {'10Y Spread':<15} | {'20D Trend':<12} | {'Cash Carry':<12} | {'Rating':<10}")
    print("-" * 80)
    valid_ratings = {"Bullish", "Neutral", "Bearish"}
    for d in diffs:
        assert d["macro_rating"] in valid_ratings, f"Invalid rating for {d['pair']}"
        print(f"{d['pair']:<10} | {d['spot_price']:<10.4f} | {d['spread_bps']:+8.1f} bps | {d['spread_20d_chg_bps']:+8.1f} bps | {d['policy_rate_spread_bps']:+8.1f} bps | {d['macro_rating']:<10}")

    # 3. Test historical pair alignment
    hist = get_pair_yield_history(conn, "USDJPY")
    assert not hist.empty, "Expected non-empty history for USDJPY"
    assert "spot_close" in hist.columns and "spread_bps" in hist.columns
    print(f"\nHistorical dual-axis chart points for USDJPY: {len(hist)} days aligned")

    conn.close()
    print("-" * 80)
    print(">>> ALL SOVEREIGN YIELDS & DIFFERENTIAL TESTS PASSED! <<<")


if __name__ == "__main__":
    test_sovereign_yields()
