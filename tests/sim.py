"""Synthetic but API-shaped inputs for offline tests (field names follow the public docs)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from rnd.synthetic import LognormalMixture, quote_chain
from kme.kalshi import event_ticker_for


def world(F=6700.0, hours=2.0, seed=0):
    T = hours / (24 * 365)
    return LognormalMixture(F, (0.8, 0.2), (1, 1), (0.12, 0.30), T), T


def cboe_payload(model, T, expiry, now_et, seed=0):
    K = np.arange(round(model.F / 5) * 5 - 250, round(model.F / 5) * 5 + 255, 5.0)
    ch = quote_chain(model, K, T, DF=1.0, rel_spread=0.02, seed=seed)
    ymd = pd.Timestamp(expiry).strftime("%y%m%d")
    last = (now_et - pd.Timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S")
    opts = []
    for i, k in enumerate(ch.strikes):
        for cp, b, a in (("C", ch.call_bid[i], ch.call_ask[i]), ("P", ch.put_bid[i], ch.put_ask[i])):
            opts.append({"option": f"SPXW{ymd}{cp}{int(k * 1000):08d}", "bid": float(b), "ask": float(a),
                         "bid_size": 10, "ask_size": 10, "iv": 0.2, "open_interest": 100, "volume": 50,
                         "last_trade_price": float(a), "last_trade_time": last})
    # an AM-settled monthly with the same date must be ignored
    opts.append({"option": f"SPX{ymd}C{int(model.F * 1000):08d}", "bid": 1.0, "ask": 999.0,
                 "last_trade_time": last})
    return {"timestamp": now_et.strftime("%Y-%m-%d %H:%M:%S"), "data": {"options": opts, "current_price": model.F}}


def tilt_probs(model, edges, theta, F):
    x = np.linspace(F * 0.9, F * 1.1, 20001)
    w = model.pdf(x) * np.exp(theta * np.log(x / F))
    c = np.concatenate([[0], np.cumsum(0.5 * (w[1:] + w[:-1]) * np.diff(x))])
    c /= c[-1]
    ce = np.interp(edges, x, c)
    return np.diff(np.concatenate([[0], ce, [1]])), x, c


def kalshi_markets(model, expiry, theta=0.0, half_spread=0.01, width=25.0, n_side=8, result_level=None):
    F = model.F
    base = round(F / width) * width
    edges = base + width * np.arange(-n_side, n_side + 1)          # range edges
    p, *_ = tilt_probs(model, edges, theta, F)
    ev = event_ticker_for("KXINX", pd.Timestamp(expiry).date())
    out = []
    specs = [("less", np.nan, edges[0])]
    specs += [("between", edges[i], edges[i + 1] - 0.0001) for i in range(len(edges) - 1)]
    specs += [("greater", edges[-1] - 0.0001, np.nan)]
    for (st, lo, hi), prob in zip(specs, p):
        bid = max(0.0, round(prob - half_spread, 2))
        ask = min(1.0, max(bid + 0.01, round(prob + half_spread, 2)))
        res, ev_val = "", ""
        if result_level is not None:
            yes = (st == "less" and result_level < hi) or (st == "greater" and result_level > lo) or \
                  (st == "between" and lo <= result_level <= hi)
            res, ev_val = ("yes" if yes else "no"), f"{result_level:.2f}"
        tick = f"{ev}-{'T' if st != 'between' else 'B'}{(hi if st == 'less' else lo):.4f}"
        out.append({"ticker": tick, "event_ticker": ev, "strike_type": st,
                    "floor_strike": None if np.isnan(lo) else lo, "cap_strike": None if np.isnan(hi) else hi,
                    "yes_bid_dollars": f"{bid:.4f}", "yes_ask_dollars": f"{ask:.4f}",
                    "yes_bid_size_fp": "100.00", "yes_ask_size_fp": "100.00",
                    "volume_fp": "10.00", "open_interest_fp": "10.00",
                    "status": "finalized" if result_level is not None else "active",
                    "result": res, "expiration_value": ev_val})
    return out


def fake_candles(markets: list[dict], lag_s: int = 30):
    """Candle fetcher returning, for each ticker, one closed candle ``lag_s`` before end_ts."""
    book = {m["ticker"]: m for m in markets}

    def fetch(series, ticker, start_ts, end_ts, period=1):
        m = book[ticker]
        return [{"end_period_ts": start_ts + 600,                   # sparse: one old change + nothing after
                 "yes_bid": {"close_dollars": m["yes_bid_dollars"]},
                 "yes_ask": {"close_dollars": m["yes_ask_dollars"]}},
                {"end_period_ts": end_ts - lag_s,
                 "yes_bid": {"close_dollars": m["yes_bid_dollars"]},
                 "yes_ask": {"close_dollars": m["yes_ask_dollars"]}},
                {"end_period_ts": end_ts + 60,                      # a future candle that must be ignored
                 "yes_bid": {"close_dollars": "0.9900"}, "yes_ask": {"close_dollars": "1.0000"}}]
    return fetch
