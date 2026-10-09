"""One snapshot: options-implied probabilities vs Kalshi quotes, synchronised and point-in-time.

The option feed is delayed (~15 min), Kalshi is live. Comparing them at fetch
time would set a stale distribution against a fresh price and manufacture
disagreements whenever the index moves. So:

1. fetch the delayed SPX chain; its *as-of* time ``t_asof`` is the newest
   trade it contains (capped at the fetch time);
2. read Kalshi top-of-book *as of t_asof* from the last 1-minute candle that
   closed at or before t_asof (``kalshi.quote_at``). Candles exist only for
   minutes with changes, so the last close is carried forward; the same
   candles are replayed at the fetch time and compared with the live book
   (``candle_at_decision_*`` vs ``live_*``) to validate that every run.
   Both sides of every comparison therefore describe the same moment, and
   neither can contain information from after it;
3. also store the live book at fetch time (``live_*`` columns; sizes are only
   available from the live book and are used as a proxy in the size gate);
4. fit the density only from step-1 data and map each contract to a
   probability with a nominal 90% band.

Outcomes are joined later by ``settle.py``. Raw Cboe quotes are not committed.
"""
from __future__ import annotations

import gzip
import json
import traceback

import numpy as np
import pandas as pd

from rnd.bootstrap import total_uncertainty
from rnd.io.cboe import asof_time, chain_from_table, parse_cboe_delayed

from . import config
from .http import get_json
from .kalshi import candlesticks, list_markets, markets_frame, parse_event_ticker, quote_at
from .model import SUPPORTED, yes_probability
from .storage import PANEL_COLS, append_csv, log_stage, paths, utcnow

ET = config.ET


def fetch_options() -> dict:
    return get_json(config.CBOE_URL, timeout=60)


def fetch_kalshi_open() -> pd.DataFrame:
    frames = [markets_frame(list_markets(series_ticker=s, status="open")) for s in config.SERIES]
    frames = [f for f in frames if len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


LOOKBACK_S = 12 * 3600      # candles are sparse; look back far enough to find the last change


def synced_quotes(markets: pd.DataFrame, asof_ts: int, decision_ts: int, fetch_candles=candlesticks) -> pd.DataFrame:
    rows = []
    for t, ev in zip(markets["ticker"], markets["event_ticker"]):
        series = (parse_event_ticker(ev) or {}).get("series", config.SERIES[0])
        try:
            c = fetch_candles(series, t, asof_ts - LOOKBACK_S, decision_ts, 1)
            q = quote_at(c, asof_ts)
            d = quote_at(c, decision_ts)
            q.update(candle_at_decision_bid=d["yes_bid"], candle_at_decision_ask=d["yes_ask"])
            rows.append(q)
        except Exception:  # noqa: BLE001 - a missing candle is a NaN quote, counted in the log
            rows.append(dict(yes_bid=np.nan, yes_ask=np.nan, kalshi_quote_ts=None,
                             candle_at_decision_bid=np.nan, candle_at_decision_ask=np.nan))
    return pd.DataFrame(rows, index=markets.index)


def run_snapshot(fetch_options=fetch_options, fetch_kalshi=fetch_kalshi_open, fetch_candles=candlesticks,
                 now=None, n_boot: int | None = None, max_stale_minutes: float = 45.0) -> dict:
    n_boot = n_boot or config.N_BOOT
    run_time = now or utcnow()
    out = dict(run_time=str(run_time), events=0, rows=0, status="failed")

    # ---- stage 1: options ------------------------------------------------
    try:
        payload = fetch_options()
        t_fetch = now or utcnow()
        opts, meta = parse_cboe_delayed(payload)
        if opts.empty:
            raise ValueError("empty option payload")
        t_asof = asof_time(opts, t_fetch)
        stale = (t_fetch - t_asof).total_seconds() / 60
        if stale > max_stale_minutes:
            log_stage("snapshot_options", "partial", 0,
                      f"stale chain ({stale:.0f} min since last trade); market closed?", run_time)
            out["status"] = "skipped_stale"
            out["reason"] = (f"newest option trade is {stale:.0f} min old (as of {t_asof:%Y-%m-%d %H:%M} ET): "
                             f"US market closed. Run between 09:35 and 16:00 ET (21:35-04:00 HKT during US DST).")
            return out
        if config.KEEP_RAW:
            p = paths()["raw"] / f"{t_fetch:%Y-%m-%d}" / f"cboe_{t_fetch:%H%M%S}Z.json.gz"
            p.parent.mkdir(parents=True, exist_ok=True)
            with gzip.open(p, "wt") as f:
                json.dump(payload, f)
        log_stage("snapshot_options", "success", len(opts), f"asof lag {stale:.1f} min", run_time)
    except Exception as e:  # noqa: BLE001
        log_stage("snapshot_options", "failed", 0, f"{type(e).__name__}: {e}", run_time)
        return out

    # ---- stage 2: kalshi live book + synchronised candles -----------------
    try:
        km = fetch_kalshi()
        t_decision = now or utcnow()
        if km is None or km.empty:
            raise ValueError("no open markets returned")
        today = t_asof.date()
        km = km[km["strike_type"].isin(SUPPORTED) & km["event_date"].notna()].copy()
        km = km[[0 <= (pd.Timestamp(d).date() - today).days <= config.MAX_EVENT_DAYS_AHEAD
                 for d in km["event_date"]]]
        km = km.rename(columns={"yes_bid": "live_yes_bid", "yes_ask": "live_yes_ask",
                                "yes_bid_size": "live_yes_bid_size", "yes_ask_size": "live_yes_ask_size"})
        asof_ts = int(t_asof.tz_convert("UTC").timestamp())
        km = km.join(synced_quotes(km, asof_ts, int(t_decision.timestamp()), fetch_candles))
        n_sync = int(km["yes_bid"].notna().sum())
        log_stage("snapshot_kalshi", "success" if n_sync == len(km) else "partial", n_sync,
                  "" if n_sync == len(km) else f"{len(km) - n_sync} of {len(km)} markets lack a synced quote",
                  run_time)
    except Exception as e:  # noqa: BLE001
        log_stage("snapshot_kalshi", "failed", 0, f"{type(e).__name__}: {e}", run_time)
        return out

    # ---- stage 3: fit + map, per event -----------------------------------
    rows, errors = [], []
    for ev, g in km.groupby("event_ticker"):
        info = parse_event_ticker(ev) or {}
        hhmm = info.get("hhmm", "1600")
        pm_close = f"{hhmm[:2]}:{hhmm[2:]}"
        ev_date = pd.Timestamp(g["event_date"].iloc[0]).date()
        try:
            chain = chain_from_table(opts, ev_date, t_asof, root=config.OPTION_ROOT, pm_close=pm_close)
            tu = total_uncertainty(chain, n_boot=n_boot, seed=asof_ts % 10_000)
            fn = lambda r, g=g: yes_probability(r, g["strike_type"], g["floor_strike"], g["cap_strike"])  # noqa: E731
            q, lo, hi = tu.interval(fn)
            per_model = {m: fn(e.base.rnd) for m, e in tu.ensembles.items()}
            base = tu.ensembles[tu.best].base
            s = base.summary()
            settle = pd.Timestamp(f"{ev_date} {pm_close}", tz=ET)
            r = g.copy()
            r["snapshot_id"] = t_asof.tz_convert("UTC").strftime("%Y%m%dT%H%M%SZ")
            r["asof_utc"] = t_asof.tz_convert("UTC").isoformat()
            r["options_fetch_utc"] = t_fetch.isoformat()
            r["decision_utc"] = t_decision.isoformat()
            r["source"] = "live"
            r["settle_time_et"] = settle.isoformat()
            r["minutes_to_settle"] = (settle - t_asof).total_seconds() / 60
            r["F"], r["DF"], r["atm_iv"] = s["F"], s["DF"], s["atm_iv"]
            r["fit_method"], r["rmse_halfspreads"], r["n_quotes"] = s["method"], s["rmse_halfspreads"], s["n_quotes"]
            r["models_in_band"] = "+".join(tu.ensembles)
            r["q_point"], r["q_lo"], r["q_hi"] = q, lo, hi
            r["q_svi"] = per_model.get("svi", np.nan)
            r["q_spline"] = per_model.get("spline", np.nan)
            rows.append(r.reindex(columns=PANEL_COLS))
            save_grid(base.rnd, tu, t_decision, ev)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{ev}: {type(e).__name__}: {e}")
            traceback.print_exc()

    if rows:
        panel = pd.concat(rows, ignore_index=True)
        append_csv(paths()["panel"] / f"{t_decision:%Y-%m}.csv", panel)
        out.update(events=len(rows), rows=len(panel))
    status = "success" if rows and not errors else ("partial" if rows else "failed")
    if not rows and not errors:
        status, errors = "partial", ["no Kalshi event within the horizon had a matching SPXW expiry"]
    log_stage("snapshot_fit", status, out["rows"], "; ".join(errors), run_time)
    out["status"] = status
    return out


def save_grid(rnd, tu, t_decision, event_ticker):
    """Store the CDF / PDF on a 5-point grid (with band) for PIT and tilt analysis."""
    lo_x, hi_x = rnd.quantile([0.0005, 0.9995])
    x = np.arange(np.floor(lo_x / 5) * 5, np.ceil(hi_x / 5) * 5 + 5, 5.0)
    c, c_lo, c_hi = tu.cdf_band(x)
    g = pd.DataFrame(dict(x=x, cdf=c, cdf_lo=c_lo, cdf_hi=c_hi, pdf=np.maximum(rnd.pdf(x), 0.0)))
    p = paths()["rnd"] / f"{t_decision:%Y-%m-%d}" / f"{t_decision:%H%M%S}Z_{event_ticker}.csv.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    g.to_csv(p, index=False, float_format="%.8g")
