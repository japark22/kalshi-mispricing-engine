from datetime import date

import numpy as np

from kme.kalshi import event_ticker_for, markets_frame, parse_event_ticker, quote_at


def test_event_ticker_round_trip():
    assert parse_event_ticker("KXINX-26OCT09H1600")["date"] == date(2026, 10, 9)
    assert event_ticker_for("KXINX", date(2026, 10, 9)) == "KXINX-26OCT09H1600"
    assert parse_event_ticker("garbage") is None


def test_markets_frame_reads_dollar_strings_and_legacy_cents():
    m = markets_frame([
        {"ticker": "A", "event_ticker": "KXINX-26OCT09H1600", "strike_type": "between", "floor_strike": 7525,
         "cap_strike": 7549.9999, "yes_bid_dollars": "0.1200", "yes_ask_dollars": "0.1500",
         "yes_bid_size_fp": "10.00"},
        {"ticker": "B", "event_ticker": "KXINX-26OCT09H1600", "strike_type": "greater", "floor_strike": 8049.9999,
         "yes_bid": 7, "yes_ask": 9},
    ])
    assert np.isclose(m.loc[0, "yes_bid"], 0.12) and np.isclose(m.loc[1, "yes_ask"], 0.09)
    assert str(m.loc[0, "event_date"]) == "2026-10-09"


def test_quote_at_never_uses_a_future_candle():
    candles = [{"end_period_ts": 100, "yes_bid": {"close_dollars": "0.10"}, "yes_ask": {"close_dollars": "0.12"}},
               {"end_period_ts": 160, "yes_bid": {"close_dollars": "0.50"}, "yes_ask": {"close_dollars": "0.52"}}]
    q = quote_at(candles, 159)
    assert q["kalshi_quote_ts"] == 100 and np.isclose(q["yes_bid"], 0.10)
    assert np.isnan(quote_at(candles, 99)["yes_bid"])
    assert np.isclose(quote_at(candles, 10_000)["yes_bid"], 0.50)         # sparse candles: carry forward
    assert np.isnan(quote_at(candles, 160 + 301, max_age_s=300)["yes_bid"])   # optional age cap


def test_quote_at_reads_legacy_cents():
    q = quote_at([{"end_period_ts": 10, "yes_bid": {"close": 12}, "yes_ask": {"close": 15}}], 10)
    assert np.isclose(q["yes_bid"], 0.12) and np.isclose(q["yes_ask"], 0.15)
