"""Historical momentum analysis on the local Yahoo price history."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from storage import get_connection, get_prices


@dataclass
class MomentumResult:
    summary: dict
    horizon_stats: pd.DataFrame
    persistence_stats: pd.DataFrame
    top1_frequency: pd.DataFrame
    group_breakdown: pd.DataFrame


def _streak_lengths(mask: pd.Series) -> list[int]:
    lengths: list[int] = []
    current = 0
    for value in mask.fillna(False).tolist():
        if value:
            current += 1
        elif current:
            lengths.append(current)
            current = 0
    if current:
        lengths.append(current)
    return lengths


def _safe_pct(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.mean() * 100)


def _safe_mean(series: pd.Series) -> float | None:
    if series.empty:
        return None
    return float(series.mean() * 100)


def _format_or_none(value: float | None) -> float | None:
    if value is None or math.isnan(value):
        return None
    return value


def compute_momentum_analysis(
    watchlist: list[dict],
    top_k: int = 5,
    horizons: tuple[int, ...] = (1, 5),
) -> MomentumResult:
    """Compute continuation and persistence for top-ranked daily movers."""
    ticker_to_group = {row["ticker"]: row["group"] for row in watchlist}

    conn = get_connection()
    closes: dict[str, pd.Series] = {}
    for ticker in ticker_to_group:
        prices = get_prices(conn, ticker)
        if prices.empty:
            continue
        close = prices["close"].dropna()
        if close.empty:
            continue
        closes[ticker] = close.rename(ticker)
    conn.close()

    if not closes:
        empty = pd.DataFrame()
        return MomentumResult(
            summary={},
            horizon_stats=empty,
            persistence_stats=empty,
            top1_frequency=empty,
            group_breakdown=empty,
        )

    close_df = pd.concat(closes.values(), axis=1).sort_index()
    daily_ret = close_df.pct_change()
    ranked = daily_ret.rank(axis=1, method="min", ascending=False, na_option="bottom")
    top_mask = ranked <= top_k

    valid_days = int((daily_ret.notna().sum(axis=1) > 0).sum())
    top_occurrences = int(top_mask.stack().sum())

    horizon_rows = []
    for horizon in horizons:
        fwd = close_df.shift(-horizon) / close_df - 1
        top_values = fwd.where(top_mask).stack().dropna()
        baseline_values = fwd.stack().dropna()

        top_up_prob = _safe_pct((top_values > 0).astype(float))
        baseline_up_prob = _safe_pct((baseline_values > 0).astype(float))
        top_avg = _safe_mean(top_values)
        baseline_avg = _safe_mean(baseline_values)

        horizon_rows.append({
            "Horizon (days)": horizon,
            "Top up probability %": _format_or_none(top_up_prob),
            "Baseline up probability %": _format_or_none(baseline_up_prob),
            "Probability edge (pp)": (
                None
                if top_up_prob is None or baseline_up_prob is None
                else top_up_prob - baseline_up_prob
            ),
            "Top avg forward return %": _format_or_none(top_avg),
            "Baseline avg forward return %": _format_or_none(baseline_avg),
            "Return edge %": (
                None
                if top_avg is None or baseline_avg is None
                else top_avg - baseline_avg
            ),
            "Top samples": int(len(top_values)),
            "Baseline samples": int(len(baseline_values)),
        })

    horizon_stats = pd.DataFrame(horizon_rows)

    persistence_rows = []
    for lag in (1, 2, 5):
        if len(top_mask.index) <= lag:
            continue
        today = top_mask.iloc[:-lag]
        later = top_mask.shift(-lag).iloc[:-lag]
        eligible = int(today.stack().sum())
        still_top = int((today & later).stack().sum())
        persistence_rows.append({
            "Lag (days)": lag,
            "Still in top-k probability %": (still_top / eligible * 100) if eligible else None,
            "Eligible samples": eligible,
        })

    streak_lengths: list[int] = []
    for ticker in top_mask.columns:
        streak_lengths.extend(_streak_lengths(top_mask[ticker]))

    persistence_stats = pd.DataFrame(persistence_rows)
    if streak_lengths:
        persistence_stats = pd.concat(
            [
                persistence_stats,
                pd.DataFrame([
                    {
                        "Lag (days)": "Streak mean",
                        "Still in top-k probability %": float(pd.Series(streak_lengths).mean()),
                        "Eligible samples": int(len(streak_lengths)),
                    },
                    {
                        "Lag (days)": "Streak median",
                        "Still in top-k probability %": float(pd.Series(streak_lengths).median()),
                        "Eligible samples": int(len(streak_lengths)),
                    },
                ]),
            ],
            ignore_index=True,
        )

    top1 = daily_ret.idxmax(axis=1).dropna().value_counts()
    top1_frequency = (
        top1.rename_axis("Ticker")
        .reset_index(name="Top-1 days")
        .sort_values("Top-1 days", ascending=False)
    )

    group_rows = []
    horizon_for_groups = 1
    fwd1 = close_df.shift(-horizon_for_groups) / close_df - 1
    for group in sorted(set(ticker_to_group.values())):
        tickers = [t for t, g in ticker_to_group.items() if g == group and t in close_df.columns]
        if not tickers:
            continue
        g_top_vals = fwd1[tickers].where(top_mask[tickers]).stack().dropna()
        g_base_vals = fwd1[tickers].stack().dropna()
        group_rows.append({
            "Group": group,
            "Top up prob % (1d)": _safe_pct((g_top_vals > 0).astype(float)),
            "Baseline up prob % (1d)": _safe_pct((g_base_vals > 0).astype(float)),
            "Prob edge (pp)": (
                None
                if g_top_vals.empty or g_base_vals.empty
                else _safe_pct((g_top_vals > 0).astype(float)) - _safe_pct((g_base_vals > 0).astype(float))
            ),
            "Top samples": int(len(g_top_vals)),
        })

    group_breakdown = pd.DataFrame(group_rows).sort_values("Top samples", ascending=False)

    summary = {
        "total_tickers": int(close_df.shape[1]),
        "sample_days": valid_days,
        "top_occurrences": top_occurrences,
        "date_start": str(close_df.index.min().date()) if len(close_df.index) else None,
        "date_end": str(close_df.index.max().date()) if len(close_df.index) else None,
    }

    return MomentumResult(
        summary=summary,
        horizon_stats=horizon_stats,
        persistence_stats=persistence_stats,
        top1_frequency=top1_frequency,
        group_breakdown=group_breakdown,
    )
