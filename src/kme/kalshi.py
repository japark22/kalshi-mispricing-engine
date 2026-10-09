"""Read-only client for Kalshi's public market-data endpoints (no auth, no trading).

Field names follow the v2 REST docs: prices are fixed-point dollar strings
(``yes_bid_dollars`` = "0.5600"), sizes are fixed-point strings (``*_fp``).
Older integer-cent fields are accepted as a fallback.
"""
from __future__ import annotations

import re
from datetime import date

import numpy as np
import pandas as pd

from . import config
from .http import get_json

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
EVENT_RE = re.compile(r"^(?P<series>[A-Z0-9]+)-(?P<yy>\d{2})(?P<mon>[A-Z]{3})(?P<dd>\d{2})H(?P<hhmm>\d{4})$")


def parse_event_ticker(event_ticker: str) -> dict | None:
    """'KXINX-26OCT09H1600' -> {series, date(2026-10-09), hhmm '1600'}."""
    m = EVENT_RE.match(event_ticker or "")
    if not m or m["mon"] not in MONTHS:
        return None
    return dict(series=m["series"], date=date(2000 + int(m["yy"]), MONTHS[m["mon"]], int(m["dd"])),
                hhmm=m["hhmm"])


def event_ticker_for(series: str, d: date, hhmm: str = "1600") -> str:
    mon = [k for k, v in MONTHS.items() if v == d.month][0]
    return f"{series}-{d:%y}{mon}{d:%d}H{hhmm}"


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _price(m: dict, name: str) -> float:
    v = _num(m.get(f"{name}_dollars"))
    if np.isnan(v) and m.get(name) is not None:     # legacy integer cents
        v = _num(m.get(name)) / 100.0
    return v


def markets_frame(markets: list[dict]) -> pd.DataFrame:
    rows = []
    for m in markets:
        ev = parse_event_ticker(m.get("event_ticker", ""))
        rows.append(dict(
            ticker=m.get("ticker"), event_ticker=m.get("event_ticker"),
            event_date=ev["date"] if ev else None,
            strike_type=m.get("strike_type"),
            floor_strike=_num(m.get("floor_strike")), cap_strike=_num(m.get("cap_strike")),
            yes_bid=_price(m, "yes_bid"), yes_ask=_price(m, "yes_ask"),
            last_price=_price(m, "last_price"),
            yes_bid_size=_num(m.get("yes_bid_size_fp")), yes_ask_size=_num(m.get("yes_ask_size_fp")),
            volume=_num(m.get("volume_fp", m.get("volume"))),
            open_interest=_num(m.get("open_interest_fp", m.get("open_interest"))),
            status=m.get("status"), close_time=m.get("close_time"),
            result=m.get("result"), expiration_value=_num(m.get("expiration_value")),
        ))
    return pd.DataFrame(rows)


def list_markets(series_ticker: str | None = None, event_ticker: str | None = None,
                 status: str | None = None, historical: bool = False, max_pages: int = 50, **extra) -> list[dict]:
    """Paginate GET /markets (or /historical/markets for markets past the cutoff)."""
    url = f"{config.KALSHI_BASE}/{'historical/' if historical else ''}markets"
    params = {"limit": 1000, **extra}
    if series_ticker:
        params["series_ticker"] = series_ticker
    if event_ticker:
        params["event_ticker"] = event_ticker
    if status:
        params["status"] = status
    out, cursor = [], None
    for _ in range(max_pages):
        if cursor:
            params["cursor"] = cursor
        js = get_json(url, params, allow_404=historical) or {}
        out += js.get("markets", []) or []
        cursor = js.get("cursor")
        if not cursor:
            break
    return out


def event_markets(event_ticker: str) -> list[dict]:
    """All markets of one event, falling back to the historical archive."""
    ms = list_markets(event_ticker=event_ticker)
    if not ms:
        ms = list_markets(event_ticker=event_ticker, historical=True)
    return ms


def candlesticks(series: str, ticker: str, start_ts: int, end_ts: int, period: int = 1) -> list[dict]:
    """1-minute (or 60/1440) candles; live path first, historical path as fallback."""
    params = dict(start_ts=int(start_ts), end_ts=int(end_ts), period_interval=int(period))
    js = get_json(f"{config.KALSHI_BASE}/series/{series}/markets/{ticker}/candlesticks", params, allow_404=True)
    if not js or not js.get("candlesticks"):
        js = get_json(f"{config.KALSHI_BASE}/historical/markets/{ticker}/candlesticks", params, allow_404=True)
    return (js or {}).get("candlesticks", []) or []


def _close(side: dict | None) -> float:
    side = side or {}
    v = _num(side.get("close_dollars"))
    if np.isnan(v) and side.get("close") is not None:      # legacy integer cents
        v = _num(side.get("close")) / 100.0
    return v


def quote_at(candles: list[dict], ts: int, max_age_s: int | None = None) -> dict:
    """Top of book as of ``ts`` from the last candle whose period ended at or before ``ts``.

    Using only candles that have *closed* by ``ts`` keeps the read
    point-in-time. Kalshi emits a 1-minute candle only in minutes where the
    book or trades changed (live check 2026-10-09: 23 candles in 3 hours), so
    a missing minute means "unchanged" and the last close is carried forward.
    Its age is returned in ``kalshi_quote_ts``; the snapshot validates the
    carry-forward assumption against the live book every run. ``max_age_s``
    optionally rejects older quotes.
    """
    best = None
    for c in candles:
        end = int(c.get("end_period_ts", 0))
        if end <= ts and (best is None or end > int(best["end_period_ts"])):
            best = c
    if best is None or (max_age_s is not None and ts - int(best["end_period_ts"]) > max_age_s):
        return dict(yes_bid=np.nan, yes_ask=np.nan, kalshi_quote_ts=None)
    return dict(yes_bid=_close(best.get("yes_bid")), yes_ask=_close(best.get("yes_ask")),
                kalshi_quote_ts=int(best["end_period_ts"]))
