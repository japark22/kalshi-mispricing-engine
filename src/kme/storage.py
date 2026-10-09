"""File layout and the append-only run log (every stage logs success/partial/failed)."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

RUN_LOG_COLS = ["run_time", "stage", "status", "count", "error_summary"]

# Fixed panel schema. Only contract definitions, quotes and model outputs - never
# settlement fields (result, expiration_value, final volume), so the panel cannot
# leak an outcome even when built from already-settled markets.
PANEL_COLS = ["snapshot_id", "asof_utc", "options_fetch_utc", "decision_utc", "source",
              "event_ticker", "event_date", "settle_time_et", "ticker", "strike_type", "floor_strike", "cap_strike",
              "yes_bid", "yes_ask", "kalshi_quote_ts", "live_yes_bid", "live_yes_ask",
              "candle_at_decision_bid", "candle_at_decision_ask",
              "live_yes_bid_size", "live_yes_ask_size", "minutes_to_settle",
              "F", "DF", "atm_iv", "fit_method", "rmse_halfspreads", "n_quotes", "models_in_band",
              "q_point", "q_lo", "q_hi", "q_svi", "q_spline"]


def utcnow() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(timezone.utc))


def paths():
    d = config.DATA
    return dict(panel=d / "panel", rnd=d / "rnd", outcomes=d / "outcomes.csv",
                run_log=d / "run_log.csv", raw=d / "raw")


def log_stage(stage: str, status: str, count: int = 0, error: str = "", run_time=None):
    p = paths()["run_log"]
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with open(p, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(RUN_LOG_COLS)
        w.writerow([(run_time or utcnow()).isoformat(), stage, status, count, (error or "")[:300]])


def append_csv(path: Path, df: pd.DataFrame):
    """Append with a schema check: a column mismatch raises instead of silently misaligning."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = list(pd.read_csv(path, nrows=0).columns)
        if existing != list(df.columns):
            raise ValueError(f"schema mismatch appending to {path}: {existing} vs {list(df.columns)}")
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


def read_panel(source: str | None = None) -> pd.DataFrame:
    """All panel files, de-duplicated on (snapshot_id, ticker), sorted by as-of time."""
    files = sorted(paths()["panel"].glob("*.csv"))
    if not files:
        return pd.DataFrame(columns=PANEL_COLS)
    p = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    p["event_date"] = p["event_date"].astype(str)
    p = p.drop_duplicates(["snapshot_id", "ticker"], keep="first").sort_values(["asof_utc", "ticker"])
    if source:
        p = p[p["source"] == source]
    return p.reset_index(drop=True)


def read_outcomes() -> pd.DataFrame:
    p = paths()["outcomes"]
    if not p.exists():
        return pd.DataFrame()
    o = pd.read_csv(p)
    o["event_date"] = o["event_date"].astype(str)
    return o.drop_duplicates("ticker", keep="first")


def read_run_log() -> pd.DataFrame:
    p = paths()["run_log"]
    return pd.read_csv(p) if p.exists() else pd.DataFrame(columns=RUN_LOG_COLS)
