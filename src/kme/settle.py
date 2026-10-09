"""Join outcomes *after* the fact, from Kalshi's own settlement records.

Only events whose date is strictly before today (ET) and whose markets all
carry a final yes/no result are written. The settlement level
(``expiration_value``) is cross-checked against each contract's result; any
disagreement is logged and the event is held back rather than guessed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .kalshi import event_markets, markets_frame
from .model import realized_yes
from .storage import append_csv, log_stage, paths, read_outcomes, read_panel, utcnow


def settle_pending(fetch_event=event_markets, now=None) -> dict:
    run_time = now or utcnow()
    panel = read_panel()
    if panel.empty:
        log_stage("settle", "success", 0, "panel empty", run_time)
        return dict(settled=0)
    done = read_outcomes()
    done_events = set(done["event_ticker"]) if len(done) else set()
    today = run_time.tz_convert(config.ET).date()
    pending = sorted({e for e, d in zip(panel["event_ticker"], panel["event_date"])
                      if e not in done_events and pd.Timestamp(d).date() < today})
    written, problems = 0, []
    for ev in pending:
        try:
            m = markets_frame(fetch_event(ev))
            if m.empty or not m["result"].isin(["yes", "no"]).all():
                problems.append(f"{ev}: not fully settled yet")
                continue
            levels = m["expiration_value"].dropna().unique()
            level = float(levels[0]) if len(levels) == 1 else np.nan
            y = (m["result"] == "yes").astype(float).to_numpy()
            check = realized_yes(m["strike_type"], m["floor_strike"], m["cap_strike"], level)
            known = ~np.isnan(check)
            consistent = bool(np.isfinite(level) and np.all(check[known] == y[known]))
            if not consistent:
                problems.append(f"{ev}: settlement level {level} inconsistent with results; held back")
                continue
            rows = m[["event_ticker", "event_date", "ticker", "strike_type", "floor_strike", "cap_strike",
                      "result"]].copy()
            rows["yes"] = y
            rows["settlement_level"] = level
            rows["settled_seen_utc"] = run_time.isoformat()
            append_csv(paths()["outcomes"], rows)
            written += 1
        except Exception as e:  # noqa: BLE001
            problems.append(f"{ev}: {type(e).__name__}: {e}")
    status = "success" if not problems else ("partial" if written else ("success" if all(
        "not fully settled" in p for p in problems) else "failed"))
    log_stage("settle", status, written, "; ".join(problems), run_time)
    return dict(settled=written, problems=problems)
