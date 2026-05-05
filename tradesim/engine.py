"""
engine.py — Candle-by-candle simulator engine.

Design rules (per user spec):
  - Fills: next-bar open (no lookahead)
  - Stop/Target: checked against bar's high/low
  - Tie-break (both stop+target hit same bar): stop wins (worst-case)
  - R-multiple = (exit - entry) / |entry - stop|  (signed for direction)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np
import pandas as pd

Side = Literal["LONG", "SHORT"]


@dataclass
class PendingOrder:
    side: Side
    stop: float
    target: float
    # Journal fields
    setup: str = ""
    trigger: str = ""
    emotag: str = ""
    emo_intensity: int = 0
    rule_adherence: int = 1
    notes: str = ""


@dataclass
class Position:
    side: Side
    entry_time: int          # epoch seconds
    entry: float
    stop: float
    target: float
    # Journal fields
    setup: str = ""
    trigger: str = ""
    emotag: str = ""
    emo_intensity: int = 0
    rule_adherence: int = 1
    notes: str = ""

    # ------------------------------------------------------------------ #
    def initial_r(self) -> float:
        """Risk in price units from entry to stop. Always positive."""
        r = abs(self.entry - self.stop)
        return r

    def r_multiple(self, exit_price: float) -> float:
        r0 = self.initial_r()
        if r0 < 1e-10:
            return float("nan")
        if self.side == "LONG":
            return (exit_price - self.entry) / r0
        return (self.entry - exit_price) / r0

    def rr_ratio(self) -> float:
        r0 = self.initial_r()
        if r0 < 1e-10:
            return float("nan")
        if self.side == "LONG":
            return (self.target - self.entry) / r0
        return (self.entry - self.target) / r0


@dataclass
class HitResult:
    exit_price: float
    exit_reason: str          # "STOP" | "TARGET" | "STOP (both hit: worst-case)"


def check_bar(pos: Position, bar: pd.Series) -> Optional[HitResult]:
    """
    Evaluate a completed bar against an open position.
    bar must have keys: open, high, low, close, time
    Returns HitResult if position is closed, else None.
    """
    h, l = float(bar["high"]), float(bar["low"])

    if pos.side == "LONG":
        hit_stop   = l <= pos.stop
        hit_target = h >= pos.target
        if hit_stop and hit_target:
            return HitResult(pos.stop, "STOP (both hit: worst-case)")
        if hit_stop:
            return HitResult(pos.stop, "STOP")
        if hit_target:
            return HitResult(pos.target, "TARGET")

    else:  # SHORT
        hit_stop   = h >= pos.stop
        hit_target = l <= pos.target
        if hit_stop and hit_target:
            return HitResult(pos.stop, "STOP (both hit: worst-case)")
        if hit_stop:
            return HitResult(pos.stop, "STOP")
        if hit_target:
            return HitResult(pos.target, "TARGET")

    return None


# ── Metrics ────────────────────────────────────────────────────────────────── #

def compute_stats(r_series: pd.Series) -> dict:
    """Given a Series of R-multiples, return key trading metrics."""
    r = r_series.dropna().astype(float)
    if r.empty:
        return {}

    wins  = r[r > 0]
    losses = r[r <= 0]

    expectancy   = float(r.mean())
    win_rate     = float((r > 0).mean())
    avg_win      = float(wins.mean())   if not wins.empty   else float("nan")
    avg_loss     = float(losses.mean()) if not losses.empty else float("nan")

    # Equity curve in R units
    equity = r.cumsum()
    peak   = equity.cummax()
    dd     = equity - peak
    max_dd = float(dd.min())

    # Profit factor
    gross_win  = float(wins.sum())  if not wins.empty  else 0.0
    gross_loss = abs(float(losses.sum())) if not losses.empty else 0.0
    pf = (gross_win / gross_loss) if gross_loss > 1e-10 else float("inf")

    return {
        "trades":       int(len(r)),
        "win_rate":     win_rate,
        "expectancy_R": expectancy,
        "avg_win_R":    avg_win,
        "avg_loss_R":   avg_loss,
        "max_dd_R":     max_dd,
        "profit_factor": pf,
        "equity_curve": equity.tolist(),
    }


def monte_carlo(r_series: pd.Series, n_sims: int = 500, n_trades: int = 100) -> dict:
    """
    Bootstrap Monte Carlo on R-multiples.
    Returns dict with percentile equity curves and ruin stats.
    """
    r = r_series.dropna().astype(float).values
    if len(r) < 5:
        return {}

    rng = np.random.default_rng(42)
    sims = rng.choice(r, size=(n_sims, n_trades), replace=True).cumsum(axis=1)

    final = sims[:, -1]
    p5, p25, p50, p75, p95 = np.percentile(final, [5, 25, 50, 75, 95])

    # Ruin = equity ever drops below -20R threshold
    ruin_threshold = -20.0
    ruin_pct = float((sims.min(axis=1) <= ruin_threshold).mean())

    return {
        "p5":   float(p5),
        "p25":  float(p25),
        "p50":  float(p50),
        "p75":  float(p75),
        "p95":  float(p95),
        "ruin_pct": ruin_pct,
        "curves_sample": sims[:50].tolist(),   # 50 sample paths for plotting
    }
