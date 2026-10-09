"""Which market forecast the close better: options or Kalshi?

To avoid overlapping observations, one snapshot per event is scored: the one
closest to ``target_minutes`` before the 4 pm settlement. Both forecasters are
scored on the same exhaustive partition of outcomes (lower tail, ranges,
upper tail), Kalshi mids normalised to sum to one (the overround is reported
separately), and compared with a Diebold-Mariano test across days.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from rnd.validation import berkowitz_test, diebold_mariano, log_score

from . import config
from .model import partition
from .storage import paths

TARGET_MINUTES = float(os.environ.get("KME_SCORE_MINUTES", "120"))


WINDOW_MINUTES = float(os.environ.get("KME_SCORE_WINDOW", "45"))


def select_snapshots(panel: pd.DataFrame, target_minutes: float = TARGET_MINUTES,
                     window: float = WINDOW_MINUTES, source: str | None = "live") -> pd.DataFrame:
    """One snapshot per event: closest to ``target_minutes`` before settlement, within ``window``.

    Live and backfill rows are scored separately (``source``) because they sit
    at different horizons; events with no snapshot inside the window are dropped
    rather than scored at some other horizon.
    """
    if panel.empty:
        return panel
    if source:
        panel = panel[panel["source"] == source]
    snaps = panel.groupby(["event_ticker", "snapshot_id"])["minutes_to_settle"].first().reset_index()
    snaps["dist"] = (snaps["minutes_to_settle"] - target_minutes).abs()
    snaps = snaps[snaps["dist"] <= window]
    best = snaps.sort_values("dist").groupby("event_ticker").head(1)
    return panel.merge(best[["event_ticker", "snapshot_id"]], on=["event_ticker", "snapshot_id"])


def grid_path(decision_utc: str, event_ticker: str):
    t = pd.Timestamp(decision_utc)
    return paths()["rnd"] / f"{t:%Y-%m-%d}" / f"{t:%H%M%S}Z_{event_ticker}.csv.gz"


def event_table(panel: pd.DataFrame, outcomes: pd.DataFrame, source: str | None = "live") -> pd.DataFrame:
    """One row per scored event, in chronological order: probability of the realised bucket under each forecaster."""
    if panel.empty or outcomes is None or outcomes.empty:
        return pd.DataFrame()
    sel = select_snapshots(panel, source=source)
    o = outcomes.drop_duplicates("ticker").set_index("ticker")
    rows = []
    for (ev, sid), g in sel.groupby(["event_ticker", "snapshot_id"]):
        if ev not in set(o["event_ticker"]):
            continue
        part = partition(g)
        if part is None:
            continue
        part = part[part["ticker"].isin(o.index)]
        mid = 0.5 * (part["yes_bid"].astype(float) + part["yes_ask"].astype(float))
        if mid.isna().any() or len(part) < 3:
            continue
        y = o.loc[part["ticker"], "yes"].to_numpy(float)
        if y.sum() != 1:
            continue
        k = mid.to_numpy() / mid.sum()
        q = part["q_point"].to_numpy(float)
        q = q / q.sum()
        level = float(o.loc[part["ticker"].iloc[0], "settlement_level"])
        row = dict(event_ticker=ev, event_date=g["event_date"].iloc[0], snapshot_id=sid,
                   minutes_to_settle=float(g["minutes_to_settle"].iloc[0]), n_buckets=len(part),
                   overround=float(mid.sum() - 1), p_kalshi=float(k[y == 1][0]), p_options=float(q[y == 1][0]),
                   settlement_level=level, F=float(g["F"].iloc[0]))
        gp = grid_path(g["decision_utc"].iloc[0], ev)
        if gp.exists():
            grid = pd.read_csv(gp)
            row["pit_options"] = float(np.interp(level, grid["x"], grid["cdf"]))
        rows.append(row)
    out = pd.DataFrame(rows)
    # chronological order matters: Berkowitz has an AR(1) term and DM uses Newey-West lags
    return out.sort_values("event_date").reset_index(drop=True) if len(out) else out


def compare(events: pd.DataFrame) -> dict:
    n = len(events)
    res = dict(n_events=n)
    if n < config.MIN_DAYS_FOR_INFERENCE:
        res["note"] = f"insufficient data (n={n}, need >= {config.MIN_DAYS_FOR_INFERENCE} settled events)"
        return res
    ls_k = log_score(events["p_kalshi"])
    ls_o = log_score(events["p_options"])
    res.update(mean_log_score_kalshi=float(ls_k.mean()), mean_log_score_options=float(ls_o.mean()),
               dm=diebold_mariano(-ls_o, -ls_k))       # negative mean_diff => options better
    if "pit_options" in events:
        res["berkowitz_options"] = berkowitz_test(events["pit_options"].dropna())
    res["mean_overround"] = float(events["overround"].mean())
    return res
