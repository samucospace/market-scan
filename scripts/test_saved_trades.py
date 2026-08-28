import sys
from datetime import datetime
from pathlib import Path

# Fix Windows console UTF-8 output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml
from storage import (
    delete_saved_trade,
    get_connection,
    get_saved_trades,
    is_trade_saved_and_active,
    reopen_saved_trade,
    save_trade,
    update_trade_exit,
)
from swing_screener import (
    SwingTradeSetup,
    evaluate_live_trade_invalidation,
    scan_swing_trades,
)


def test_saved_trades_lifecycle():
    print("========================================")
    print("TESTING SAVED TRADES STORAGE & INVENTORY")
    print("========================================")
    conn = get_connection()

    # Create dummy setup
    setup = SwingTradeSetup(
        ticker="TEST_TICKER",
        group="Test Group",
        description="Test description for unit testing",
        direction="LONG",
        archetype="Trend Pullback",
        conviction_score=88.5,
        holding_period="5 - 12 Days",
        last_price=100.0,
        entry_zone="99.5 - 100.5",
        entry_price=100.0,
        stop_loss=95.0,
        target_1=110.0,
        target_2=120.0,
        risk_reward_ratio=2.0,
        risk_pct=5.0,
        reward_pct=10.0,
        rsi_14=48.5,
        atr_14=3.2,
        sma20=99.0,
        sma50=94.0,
        macro_thesis="Macro testing regime",
        technical_thesis="Testing technical pullback",
        invalidation_rules="Daily close below 95.0 invalidates setup.",
    )

    # 1. Save Trade
    trade_id = save_trade(conn, setup, user_notes="Initial unit test note")
    print(f"Saved Trade ID: {trade_id}")
    assert trade_id > 0

    # 2. Check active state
    is_act = is_trade_saved_and_active(conn, "TEST_TICKER", "LONG")
    print(f"is_trade_saved_and_active: {is_act}")
    assert is_act is True

    # 3. Retrieve list
    saved_list = get_saved_trades(conn)
    matching = [t for t in saved_list if t["id"] == trade_id]
    assert len(matching) == 1
    t_record = matching[0]
    assert t_record["ticker"] == "TEST_TICKER"
    assert t_record["status"] == "ACTIVE"
    assert float(t_record["entry_price"]) == 100.0
    print("Retrieved saved trade successfully.")

    # 4. Test Invalidation Engine against real ticker
    watchlist_path = Path(__file__).resolve().parent.parent / "config" / "watchlist.yaml"
    with open(watchlist_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    watchlist = []
    for g, items in cfg["groups"].items():
        for item in items:
            watchlist.append({"ticker": item["ticker"], "group": g, "note": item.get("note", "")})

    res = scan_swing_trades(watchlist, conn)
    assert len(res.top_3_trades) > 0
    top_trade = res.top_3_trades[0]
    real_id = save_trade(conn, top_trade)
    print(f"Saved real candidate: {top_trade.direction} {top_trade.ticker} (ID: {real_id})")

    # Evaluate live invalidation on real candidate
    eval_res = evaluate_live_trade_invalidation(top_trade, conn)
    print(f"Live Invalidation Evaluation for {top_trade.ticker}:")
    print(f"  Status Flag: {eval_res['status_flag']} ({eval_res['status_label']})")
    print(f"  Current Price: {eval_res['current_price']} | Unrealized P&L: {eval_res['unrealized_pnl_pct']:+.2f}%")
    print(f"  Reasons: {eval_res['reasons']}")
    assert eval_res["status_flag"] in ("VALID", "TARGET_HIT", "WARNING", "INVALIDATED")

    # 5. Record Exit for real candidate
    exit_px = top_trade.entry_price * 1.05
    exit_ok = update_trade_exit(
        conn,
        trade_id=real_id,
        exit_price=exit_px,
        exit_date=datetime.now().strftime("%Y-%m-%d"),
        exit_notes="Closed at Target 1 with +5.0% profit",
    )
    assert exit_ok is True
    print("Recorded trade exit successfully.")

    # 6. Verify sorting: ACTIVE should be first, EXITED at bottom
    all_trades = get_saved_trades(conn)
    exited_ones = [t for t in all_trades if t["status"] == "EXITED"]
    active_ones = [t for t in all_trades if t["status"] == "ACTIVE"]
    assert any(t["id"] == real_id for t in exited_ones)
    assert any(t["id"] == trade_id for t in active_ones)

    # Check that in all_trades, active ones appear before exited ones
    first_exited_idx = next(i for i, t in enumerate(all_trades) if t["status"] == "EXITED")
    for i, t in enumerate(all_trades):
        if t["status"] == "ACTIVE":
            assert i < first_exited_idx, "Active trades must appear before exited trades!"
    print("Verified ordering: Active trades top, Exited trades bottom.")

    # 7. Reopen Exited Trade
    reopen_ok = reopen_saved_trade(conn, real_id)
    assert reopen_ok is True
    reopened = [t for t in get_saved_trades(conn) if t["id"] == real_id][0]
    assert reopened["status"] == "ACTIVE"
    assert reopened["exit_price"] is None
    print("Reopened trade successfully.")

    # 8. Clean up test records
    delete_saved_trade(conn, trade_id)
    delete_saved_trade(conn, real_id)
    assert not any(t["id"] in (trade_id, real_id) for t in get_saved_trades(conn))
    print("Cleaned up test records.")

    conn.close()
    print("\n>>> ALL SAVED TRADES TESTS PASSED SUCCESSFULLY! <<<")


if __name__ == "__main__":
    test_saved_trades_lifecycle()
