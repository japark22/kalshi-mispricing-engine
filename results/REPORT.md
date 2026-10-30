# Kalshi vs options: research report
_Generated 2026-10-30 18:42 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 870 (870 live, 0 backfill); rows without a synchronised Kalshi quote: 15
- Candle-replay check (candle state at fetch time == live book, live rows): 95.2% of 855 rows agree
- Snapshots: 20; events: 15; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-10-30T18:19:52.471574+00:00
- Settled events with outcomes: 14
- Smile model chosen: {'spline': 19, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       286 |                  154 |           15 |               257 |             14 |        nan |        nan |          nan |      nan |
| spread    |        33 |                   31 |           14 |                29 |             13 |        nan |        nan |          nan |      nan |
| fees      |        26 |                   26 |           14 |                23 |             13 |        nan |        nan |          nan |      nan |
| quote_unc |        23 |                   23 |           14 |                20 |             13 |        nan |        nan |          nan |      nan |
| model_unc |        17 |                   17 |           12 |                15 |             11 |        nan |        nan |          nan |      nan |
| size      |        12 |                   12 |           11 |                10 |             10 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 10,
  "note": "insufficient data (n=10, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 11
- theta_kalshi: insufficient data (n=11, need >= 40)
- theta_realized: {"n": 10, "note": "insufficient data (n=10, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

