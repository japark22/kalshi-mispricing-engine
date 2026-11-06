# Kalshi vs options: research report
_Generated 2026-11-06 20:00 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 1,080 (1,080 live, 0 backfill); rows without a synchronised Kalshi quote: 15
- Candle-replay check (candle state at fetch time == live book, live rows): 95.4% of 1,065 rows agree
- Snapshots: 24; events: 19; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-11-06T19:45:26.014137+00:00
- Settled events with outcomes: 18
- Smile model chosen: {'spline': 23, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       377 |                  204 |           19 |               307 |             18 |        nan |        nan |          nan |      nan |
| spread    |        40 |                   38 |           18 |                38 |             17 |        nan |        nan |          nan |      nan |
| fees      |        31 |                   31 |           17 |                29 |             16 |        nan |        nan |          nan |      nan |
| quote_unc |        28 |                   28 |           17 |                26 |             16 |        nan |        nan |          nan |      nan |
| model_unc |        21 |                   21 |           15 |                20 |             14 |        nan |        nan |          nan |      nan |
| size      |        14 |                   14 |           13 |                13 |             12 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 12,
  "note": "insufficient data (n=12, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 13
- theta_kalshi: insufficient data (n=13, need >= 40)
- theta_realized: {"n": 12, "note": "insufficient data (n=12, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

