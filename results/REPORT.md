# Kalshi vs options: research report
_Generated 2026-11-04 20:29 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 990 (990 live, 0 backfill); rows without a synchronised Kalshi quote: 15
- Candle-replay check (candle state at fetch time == live book, live rows): 95.4% of 975 rows agree
- Snapshots: 22; events: 18; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-11-04T20:09:14.469031+00:00
- Settled events with outcomes: 16
- Smile model chosen: {'spline': 21, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       343 |                  195 |           18 |               293 |             16 |        nan |        nan |          nan |      nan |
| spread    |        36 |                   34 |           16 |                34 |             15 |        nan |        nan |          nan |      nan |
| fees      |        27 |                   27 |           15 |                27 |             15 |        nan |        nan |          nan |      nan |
| quote_unc |        24 |                   24 |           15 |                24 |             15 |        nan |        nan |          nan |      nan |
| model_unc |        18 |                   18 |           13 |                18 |             13 |        nan |        nan |          nan |      nan |
| size      |        13 |                   13 |           12 |                13 |             12 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 12,
  "note": "insufficient data (n=12, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 12
- theta_kalshi: insufficient data (n=12, need >= 40)
- theta_realized: {"n": 12, "note": "insufficient data (n=12, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

