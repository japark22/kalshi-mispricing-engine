# Kalshi vs options: research report
_Generated 2026-10-19 19:24 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 360 (360 live, 0 backfill); rows without a synchronised Kalshi quote: 2
- Candle-replay check (candle state at fetch time == live book, live rows): 96.4% of 358 rows agree
- Snapshots: 9; events: 6; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-10-19T18:54:20.845416+00:00
- Settled events with outcomes: 5
- Smile model chosen: {'spline': 8, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       120 |                   54 |            6 |               110 |              5 |        nan |        nan |          nan |      nan |
| spread    |        15 |                   14 |            5 |                13 |              4 |        nan |        nan |          nan |      nan |
| fees      |        10 |                   10 |            5 |                 8 |              4 |        nan |        nan |          nan |      nan |
| quote_unc |         9 |                    9 |            5 |                 7 |              4 |        nan |        nan |          nan |      nan |
| model_unc |         8 |                    8 |            5 |                 6 |              4 |        nan |        nan |          nan |      nan |
| size      |         4 |                    4 |            4 |                 3 |              3 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 1,
  "note": "insufficient data (n=1, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 2
- theta_kalshi: insufficient data (n=2, need >= 40)
- theta_realized: {"n": 1, "note": "insufficient data (n=1, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

