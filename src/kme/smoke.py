"""Smoke test against the live public endpoints. Run this first on a new machine."""
from __future__ import annotations

import time

import pandas as pd

from rnd.io.cboe import parse_cboe_delayed

from . import config
from .kalshi import candlesticks, list_markets, markets_frame
from .snapshot import fetch_options


def smoke() -> dict:
    out = {}
    try:
        payload = fetch_options()
        df, meta = parse_cboe_delayed(payload)
        spxw = df[df["root"] == "SPXW"]
        now_utc = pd.Timestamp.now(tz="UTC")
        lt = pd.to_datetime(df["last_trade_time"], errors="coerce").dropna()
        latest = lt.max() if len(lt) else None
        out["cboe"] = dict(ok=True, options=len(df), spxw=len(spxw),
                           spxw_expiries=sorted(map(str, spxw["expiry"].unique()))[:5],
                           cboe_timestamp=meta.get("cboe_timestamp"),
                           underlying_last_trade_time=meta.get("last_trade_time"),
                           # timezone check: the right reading is the one that is small and positive
                           latest_option_trade_raw=str(latest),
                           minutes_behind_if_ET=None if latest is None else round(
                               (now_utc - latest.tz_localize("America/New_York")).total_seconds() / 60, 1),
                           minutes_behind_if_UTC=None if latest is None else round(
                               (now_utc - latest.tz_localize("UTC")).total_seconds() / 60, 1))
    except Exception as e:  # noqa: BLE001
        out["cboe"] = dict(ok=False, error=f"{type(e).__name__}: {e}")
    for s in config.SERIES:
        try:
            m = markets_frame(list_markets(series_ticker=s, status="open"))
            out[s] = dict(ok=True, open_markets=len(m),
                          events=sorted(m["event_ticker"].dropna().unique())[:5] if len(m) else [],
                          strike_types=m["strike_type"].value_counts().to_dict() if len(m) else {},
                          two_sided_quotes=int(((m["yes_bid"] > 0) & (m["yes_ask"] < 1)).sum()) if len(m) else 0,
                          example=m.head(2).to_dict("records") if len(m) else [])
            liquid = m.sort_values("volume", ascending=False)
            if len(liquid):
                t = liquid["ticker"].iloc[0]
                now = int(time.time())
                c = candlesticks(s, t, now - 3 * 3600, now, 1)
                out[s]["candles"] = dict(ticker=t, n_last_3h=len(c), last=c[-1] if c else None)
        except Exception as e:  # noqa: BLE001
            out[s] = dict(ok=False, error=f"{type(e).__name__}: {e}")
    out["checked_at_utc"] = str(pd.Timestamp.now(tz="UTC"))
    return out
