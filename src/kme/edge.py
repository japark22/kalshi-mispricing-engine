"""The edge funnel: how many apparent mispricings survive each real-world cost.

For every panel row both trades are considered:

* buy YES at ``yes_ask``       - fair value under options: q
* buy NO  at ``1 - yes_bid``   - fair value under options: 1 - q

Stages (each a subset of the previous one):

1. naive      |kalshi_mid - q| >= 1 cent              (what most write-ups report)
2. spread     the trade's fair value beats its executable price
3. fees       ... after Kalshi's taker fee
4. quote_unc  ... using the conservative end of the bootstrap band (q_lo / q_hi)
5. model_unc  ... and after the residual model-error tolerance from the
                  known-answer study. That tolerance was measured for 25-point
                  *range* buckets on a same-day expiry only, so tail contracts
                  (`greater`/`less`) and multi-day events cannot pass this stage
                  ("not calibrated") rather than borrowing a number never measured.
6. size       ... with at least one contract displayed at that price (live book
                  at fetch time, used as a proxy for size at the as-of time)

Prices are the synchronised quotes (Kalshi as of the option chain's as-of
time). Treating them as executable assumes a real-time option feed; with the
delayed public feed this is a measurement of mispricing, not a tradeable
backtest.

Realised P&L per contract is computed for settled signals at every stage, so
the funnel shows not only how many signals survive but whether they paid.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

STAGES = ["naive", "spread", "fees", "quote_unc", "model_unc", "size"]
SAME_DAY_MINUTES = 390          # a full regular session; the known-answer 0DTE case is 5 hours


def kalshi_fee(price, coef=None, contracts=1.0):
    """Per-contract taker fee for an order of ``contracts`` contracts.

    Kalshi fee schedule (effective 2026-07-07): fee = round up(M x 0.07 x C x P x (1-P)),
    rounded so that fee + position cost lands on a centicent ($0.0001). M is the
    series multiplier (1 for KXINX per GET /series/KXINX: fee_type quadratic,
    fee_multiplier 1). Older schedules rounded up to the next whole cent; set
    KME_TAKER_FEE or adapt this function if the schedule changes.
    """
    coef = config.TAKER_FEE_COEF if coef is None else coef
    p = np.asarray(price, float)
    raw = coef * contracts * p * (1 - p)
    return np.ceil(np.round(raw * 1e4, 6)) / 1e4 / contracts


def funnel_rows(panel: pd.DataFrame, model_tol: float | None = None) -> pd.DataFrame:
    """Long table: one row per (panel row, side) with stage flags and edge at each stage."""
    tol = config.MODEL_ERROR_TOL if model_tol is None else model_tol
    p = panel.dropna(subset=["q_point", "yes_bid", "yes_ask"]).copy()
    p = p[(p["yes_ask"] > 0) & (p["yes_ask"] <= 1) & (p["yes_bid"] >= 0) & (p["yes_bid"] < p["yes_ask"])]
    mid = 0.5 * (p["yes_bid"] + p["yes_ask"])
    out = []
    for side in ("yes", "no"):
        d = p.copy()
        d["side"] = side
        if side == "yes":
            price = d["yes_ask"]
            fair, fair_cons = d["q_point"], d["q_lo"]
            size = d["live_yes_ask_size"] if "live_yes_ask_size" in d else pd.Series(np.nan, index=d.index)
            naive_dir = d["q_point"] - mid
        else:
            price = 1 - d["yes_bid"]
            fair, fair_cons = 1 - d["q_point"], 1 - d["q_hi"]
            size = d["live_yes_bid_size"] if "live_yes_bid_size" in d else pd.Series(np.nan, index=d.index)
            naive_dir = mid - d["q_point"]
        fee = kalshi_fee(price)
        d["price"] = price
        d["fee"] = fee
        d["edge_spread"] = fair - price
        d["edge_fees"] = fair - price - fee
        d["edge_quote_unc"] = fair_cons - price - fee
        d["edge_model_unc"] = fair_cons - price - fee - tol
        d["naive"] = naive_dir >= 0.01
        d["spread"] = d["naive"] & (d["edge_spread"] > 0)
        d["fees"] = d["spread"] & (d["edge_fees"] > 0)
        d["quote_unc"] = d["fees"] & (d["edge_quote_unc"] > 0)
        calibrated = (d["strike_type"] == "between") & (d["minutes_to_settle"] <= SAME_DAY_MINUTES)
        d["model_unc"] = d["quote_unc"] & calibrated & (d["edge_model_unc"] > 0)
        # sizes missing (e.g. backfill from candles) cannot pass the size gate
        d["size"] = d["model_unc"] & (size.fillna(0).to_numpy() >= 1)
        out.append(d)
    return pd.concat(out, ignore_index=True)


def attach_outcomes(fr: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    if outcomes is None or outcomes.empty:
        fr = fr.copy()
        fr["yes"] = np.nan
        return fr
    o = outcomes[["ticker", "yes"]].drop_duplicates("ticker")
    fr = fr.merge(o, on="ticker", how="left")
    win = np.where(fr["side"] == "yes", fr["yes"], 1 - fr["yes"])
    fr["pnl"] = np.where(np.isnan(fr["yes"]), np.nan, win - fr["price"] - fr["fee"])
    return fr


def funnel_summary(fr: pd.DataFrame) -> pd.DataFrame:
    """Counts and realised P&L per stage, clustered by event-day for the t-stat."""
    rows = []
    for st in STAGES:
        s = fr[fr[st]]
        settled = s.dropna(subset=["yes"]) if "yes" in s else s.iloc[0:0]
        n_days = settled["event_date"].nunique() if len(settled) else 0
        row = dict(stage=st, signals=int(len(s)), contracts_distinct=int(s["ticker"].nunique()),
                   event_days=int(s["event_date"].nunique()), settled_signals=int(len(settled)),
                   settled_days=int(n_days))
        if n_days >= config.MIN_DAYS_FOR_INFERENCE:
            daily = settled.groupby("event_date")["pnl"].mean()
            row.update(mean_pnl=float(settled["pnl"].mean()), hit_rate=float((settled["pnl"] > 0).mean()),
                       daily_mean=float(daily.mean()),
                       t_stat=float(daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily)))))
        else:
            row.update(mean_pnl=np.nan, hit_rate=np.nan, daily_mean=np.nan, t_stat=np.nan)
        rows.append(row)
    return pd.DataFrame(rows)
