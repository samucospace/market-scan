"""Automated test script for Dashboard v2.0 engine."""
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from tactical_engine import (
    TARGET_SECURITIES,
    MACRO_QUADRANT_MATRIX,
    compute_v2_dashboard_ratings,
)
from storage import get_connection


def test_v2_engine():
    print("Testing Dashboard v2.0 Tactical Engine...")
    assert len(TARGET_SECURITIES) == 12, f"Expected 12 target securities, got {len(TARGET_SECURITIES)}"
    
    # Check all 12 are in MACRO_QUADRANT_MATRIX
    for sec in TARGET_SECURITIES:
        sym = sec["symbol"]
        assert sym in MACRO_QUADRANT_MATRIX, f"Missing macro matrix for {sym}"
        quadrants = MACRO_QUADRANT_MATRIX[sym]
        for q in ["EXPANSION_GOLDILOCKS", "EXPANSION_REFLATION", "STAGFLATION_LATE_CYCLE", "CONTRACTION_RISK_OFF"]:
            assert q in quadrants, f"Missing quadrant {q} for {sym}"
            assert quadrants[q]["rating"] in ["Bullish", "Neutral", "Bearish"], f"Invalid rating for {sym} {q}"

    conn = get_connection()
    ratings, macro_rep = compute_v2_dashboard_ratings(conn)
    conn.close()

    assert len(ratings) == 12, f"Expected 12 rating results, got {len(ratings)}"
    print(f"\nActive Macro Quadrant: {macro_rep.quadrant_name} ({macro_rep.quadrant_tag})")
    print(f"Growth Score: {macro_rep.growth_score:+.1f} | Inflation Score: {macro_rep.inflation_score:+.1f}")
    print("-" * 105)
    print(f"{'Security':<14} | {'Price':<10} | {'Primary (100EMA)':<18} | {'Macro Env':<12} | {'Daily Correlated':<18} | {'Technicals':<12} | {'Overall':<10}")
    print("-" * 105)

    valid_ratings = {"Bullish", "Neutral", "Bearish"}
    for r in ratings:
        assert r.primary_trend in valid_ratings, f"Invalid primary trend {r.primary_trend} for {r.symbol}"
        assert r.macro_environment in valid_ratings, f"Invalid macro {r.macro_environment} for {r.symbol}"
        assert r.correlated_assets in valid_ratings, f"Invalid correlated {r.correlated_assets} for {r.symbol}"
        assert r.tactical_technicals in valid_ratings, f"Invalid tactical {r.tactical_technicals} for {r.symbol}"
        assert r.overall_stance in valid_ratings, f"Invalid overall {r.overall_stance} for {r.symbol}"

        print(f"{r.symbol:<14} | {r.last_price:<10.4f} | {r.primary_trend:<18} | {r.macro_environment:<12} | {r.correlated_assets:<18} | {r.tactical_technicals:<12} | {r.overall_stance:<10}")

    print("-" * 105)
    print("All 12 securities successfully evaluated with valid Bullish/Neutral/Bearish ratings across all 4 columns!")


if __name__ == "__main__":
    test_v2_engine()
