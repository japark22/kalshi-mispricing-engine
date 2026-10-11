"""Offline end-to-end: snapshot -> settle -> report on simulated, API-shaped data."""
import numpy as np
import pandas as pd
import pytest

from kme import config
from kme.report import build_report
from kme.settle import settle_pending
from kme.snapshot import run_snapshot
from kme.storage import read_outcomes, read_panel, read_run_log
from sim import cboe_payload, fake_candles, kalshi_markets, world


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA", tmp_path / "data")
    monkeypatch.setattr(config, "RESULTS", tmp_path / "results")
    monkeypatch.setattr(config, "MIN_DAYS_FOR_INFERENCE", 3)
    return tmp_path


def _day(d, seed, theta=0.0):
    now = pd.Timestamp(f"{d} 14:00", tz="America/New_York").tz_convert("UTC")
    model, T = world(hours=2.0, seed=seed)
    payload = cboe_payload(model, T, d, now.tz_convert("America/New_York"), seed=seed)
    mk = kalshi_markets(model, d, theta=theta)
    return now, model, payload, mk


def test_snapshot_settle_report(tmp_project):
    days = pd.bdate_range("2026-10-05", periods=4)
    rng = np.random.default_rng(0)
    levels = {}
    for i, d in enumerate(days):
        d = d.date()
        now, model, payload, mk = _day(d, i)
        out = run_snapshot(fetch_options=lambda p=payload: p,
                           fetch_kalshi=lambda mk=mk: __import__("kme.kalshi", fromlist=["x"]).markets_frame(mk),
                           fetch_candles=fake_candles(mk), now=now, n_boot=8)
        assert out["status"] == "success", read_run_log().tail(3).to_dict("records")
        levels[d] = float(model.F * np.exp(rng.normal(0, 0.003)))

    panel = read_panel()
    assert (panel["decision_utc"] >= panel["options_fetch_utc"]).all()          # point-in-time order
    assert (panel["asof_utc"] <= panel["options_fetch_utc"]).all()              # delayed feed: as-of <= fetch
    assert (panel["kalshi_quote_ts"] <= pd.to_datetime(panel["asof_utc"]).map(lambda t: t.timestamp())).all()
    assert panel["yes_ask"].max() < 0.99                                        # the future candle was ignored
    assert not {"result", "expiration_value"} & set(panel.columns)              # no outcome fields in the panel
    assert (panel["candle_at_decision_bid"] == panel["live_yes_bid"]).all()      # replay check populated
    assert panel["fit_method"].notna().all() and (panel["q_lo"] <= panel["q_hi"] + 1e-12).all()
    for _, g in panel.groupby("snapshot_id"):
        assert abs(g["q_point"].sum() - 1) < 0.01                               # partition sums to one

    # Settlement before the event date must not join anything
    first = days[0].date()
    early = settle_pending(fetch_event=lambda ev: [], now=pd.Timestamp(f"{first} 15:00", tz="UTC"))
    assert early["settled"] == 0 and read_outcomes().empty

    def fetch_event(ev):
        d = [k for k in levels if ev.endswith(pd.Timestamp(k).strftime("%y%b%dH1600").upper())][0]
        model, T = world(hours=2.0)
        return kalshi_markets(model, d, result_level=levels[d])

    res = settle_pending(fetch_event=fetch_event, now=pd.Timestamp(days[-1] + pd.Timedelta(days=2), tz="UTC"))
    assert res["settled"] == 4
    o = read_outcomes()
    assert o.groupby("event_ticker")["yes"].sum().eq(1).all()

    text = build_report()
    assert "Edge funnel" in text and "mean_log_score_kalshi" in text
    assert (tmp_project / "results" / "REPORT.md").exists()
    assert (tmp_project / "results" / "figures" / "edge_funnel.png").exists()


def test_stale_chain_is_skipped(tmp_project):
    d = pd.Timestamp("2026-10-05").date()
    now, model, payload, mk = _day(d, 0)
    for o in payload["data"]["options"]:
        o["last_trade_time"] = "2026-10-02T15:59:00"        # Friday's chain on a Monday
    out = run_snapshot(fetch_options=lambda: payload, fetch_kalshi=lambda: None, now=now, n_boot=5)
    assert out["status"] == "skipped_stale" and read_panel().empty


def test_no_open_markets_after_close_is_a_skip_not_a_failure(tmp_project):
    import kme.kalshi as K
    d = pd.Timestamp("2026-10-05").date()
    model, T = world(hours=2.0, seed=0)
    empty = lambda: K.markets_frame([])                     # noqa: E731
    for hhmm, expected, logged in [("16:30", "skipped_closed", "partial"), ("14:00", "failed", "failed")]:
        now_et = pd.Timestamp(f"{d} {hhmm}", tz="America/New_York")
        payload = cboe_payload(model, T, d, now_et, seed=0)
        out = run_snapshot(fetch_options=lambda p=payload: p, fetch_kalshi=empty,
                           now=now_et.tz_convert("UTC"), n_boot=5)
        assert out["status"] == expected and read_run_log().iloc[-1]["status"] == logged, hhmm


def test_failures_are_logged_not_raised(tmp_project):
    def boom():
        raise ConnectionError("blocked")
    out = run_snapshot(fetch_options=boom, now=pd.Timestamp("2026-10-05 18:00", tz="UTC"))
    log = read_run_log()
    assert out["status"] == "failed" and log.iloc[-1]["status"] == "failed" and "blocked" in log.iloc[-1]["error_summary"]
