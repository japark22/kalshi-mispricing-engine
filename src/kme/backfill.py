"""Historical backfill: end-of-day option files + Kalshi 1-minute candles.

For each EOD option snapshot on day d (quote time from the file, e.g. 16:00 ET)
and each PM-settled expiry e within ``max_days`` after d:

* fit the option-implied density from the file's quotes only;
* find the Kalshi S&P range event for e and read each contract's top of book
  from the last 1-minute candle that *closed at or before* the option quote
  time (``kalshi.quote_at``) - never a later candle;
* write panel rows with ``source = 'backfill'``: contract definitions and
  quotes only (no settled fields). Sizes are unknown from candles, so
  backfilled rows can never pass the funnel's size gate.

You supply the option files (see README: no option data is redistributed here).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from rnd.bootstrap import total_uncertainty
from rnd.io.optionsdx import iter_chains, load_eod

from . import config
from .kalshi import candlesticks, event_markets, event_ticker_for, markets_frame, quote_at
from .model import SUPPORTED, yes_probability
from .snapshot import save_grid
from .storage import PANEL_COLS, append_csv, log_stage, paths, read_panel, utcnow


def backfill_file(path: str | Path, series: str = "KXINX", n_boot: int | None = None, max_days: int = 3,
                  fetch_event=event_markets, fetch_candles=candlesticks) -> dict:
    """Backfill one EOD option file. Idempotent: snapshots already in the panel are skipped.

    Check the quote time stamped in your file (often 15:45 or 16:15 ET rather
    than 16:00): Kalshi is read as of exactly that time, so a wrong stamp
    shifts both sides of the comparison.
    """
    n_boot = n_boot or config.N_BOOT
    run_time = utcnow()
    df = load_eod(str(path))
    have = read_panel()
    done = set(zip(have["snapshot_id"], have["event_ticker"])) if len(have) else set()
    written, skipped, problems = 0, 0, []
    for chain in iter_chains(df, max_dte=max_days):
        exp = chain.expiry.date()
        ev = event_ticker_for(series, exp)
        t_asof = chain.quote_time.tz_convert("UTC")
        sid = t_asof.strftime("%Y%m%dT%H%M%SZ")
        if (sid, ev) in done:
            skipped += 1
            continue
        try:
            m = markets_frame(fetch_event(ev))
            # contract definitions only - settled fields (result, expiration_value,
            # final volume/open interest) must never enter the panel
            m = m[m["strike_type"].isin(SUPPORTED)][["ticker", "event_ticker", "event_date", "strike_type",
                                                      "floor_strike", "cap_strike"]].copy()
            if m.empty:
                problems.append(f"{ev}: no markets")
                continue
            ts = int(t_asof.timestamp())
            qd = pd.DataFrame([quote_at(fetch_candles(series, t, ts - 12 * 3600, ts, 1), ts) for t in m["ticker"]],
                              index=m.index)
            m = m.join(qd).dropna(subset=["yes_bid", "yes_ask"])
            if m.empty:
                problems.append(f"{ev}: no Kalshi candle in the 12 h before {chain.quote_time}")
                continue
            tu = total_uncertainty(chain, n_boot=n_boot, seed=ts % 10_000)
            fn = lambda r, m=m: yes_probability(r, m["strike_type"], m["floor_strike"], m["cap_strike"])  # noqa: E731
            qpt, lo, hi = tu.interval(fn)
            base = tu.ensembles[tu.best].base
            s = base.summary()
            r = m.copy()
            r["snapshot_id"] = sid
            r["asof_utc"] = r["options_fetch_utc"] = r["decision_utc"] = t_asof.isoformat()
            r["source"] = "backfill"
            r["settle_time_et"] = chain.expiry.isoformat()
            r["minutes_to_settle"] = (chain.expiry - chain.quote_time).total_seconds() / 60
            r["F"], r["DF"], r["atm_iv"] = s["F"], s["DF"], s["atm_iv"]
            r["fit_method"], r["rmse_halfspreads"], r["n_quotes"] = s["method"], s["rmse_halfspreads"], s["n_quotes"]
            r["models_in_band"] = "+".join(tu.ensembles)
            r["q_point"], r["q_lo"], r["q_hi"] = qpt, lo, hi
            r["q_svi"] = fn(tu.ensembles["svi"].base.rnd) if "svi" in tu.ensembles else np.nan
            r["q_spline"] = fn(tu.ensembles["spline"].base.rnd) if "spline" in tu.ensembles else np.nan
            append_csv(paths()["panel"] / f"backfill_{t_asof:%Y-%m}.csv", r.reindex(columns=PANEL_COLS))
            save_grid(base.rnd, tu, t_asof, ev)
            written += 1
        except Exception as e:  # noqa: BLE001
            problems.append(f"{ev}: {type(e).__name__}: {e}")
    status = "success" if written and not problems else ("partial" if written else
                                                         ("success" if skipped and not problems else "failed"))
    log_stage("backfill", status, written, "; ".join(problems[:10]), run_time)
    return dict(events=written, skipped=skipped, problems=problems)
