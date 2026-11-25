## ⚠️ ATTENTION
- Stage `snapshot_options` failed 4 of its last 6 attempts: HTTPError: 403 Client Error: Forbidden for url: https://cdn-api.cboe.com/api/global/delayed_quotes/options/_SPX.json

# Kalshi vs options: research report
_Generated 2026-11-25 22:39 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 1,410 (1,410 live, 0 backfill); rows without a synchronised Kalshi quote: 29
- Candle-replay check (candle state at fetch time == live book, live rows): 94.9% of 1,381 rows agree
- Snapshots: 31; events: 25; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-11-19T21:04:34.081074+00:00
- Settled events with outcomes: 25
- Smile model chosen: {'spline': 30, 'svi': 1}

- ⚠️ Candle replay matches the live book for only 94.9% of rows - the carry-forward assumption behind synchronised quotes is weak.
## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       486 |                  276 |           25 |               486 |             25 |        nan |        nan |          nan |      nan |
| spread    |        49 |                   47 |           23 |                49 |             23 |        nan |        nan |          nan |      nan |
| fees      |        35 |                   35 |           19 |                35 |             19 |        nan |        nan |          nan |      nan |
| quote_unc |        32 |                   32 |           19 |                32 |             19 |        nan |        nan |          nan |      nan |
| model_unc |        24 |                   24 |           16 |                24 |             16 |        nan |        nan |          nan |      nan |
| size      |        17 |                   17 |           14 |                17 |             14 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 14,
  "note": "insufficient data (n=14, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 14
- theta_kalshi: insufficient data (n=14, need >= 40)
- theta_realized: {"n": 14, "note": "insufficient data (n=14, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

