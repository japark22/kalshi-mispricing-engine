# Kalshi vs options: research report
_Generated 2026-10-14 18:05 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 150 (150 live, 0 backfill); rows without a synchronised Kalshi quote: 0
- Candle-replay check (candle state at fetch time == live book, live rows): 99.3% of 150 rows agree
- Snapshots: 3; events: 4; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-10-14T17:41:34.571216+00:00
- Settled events with outcomes: 2
- Smile model chosen: {'spline': 2, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |        49 |                   37 |            4 |                 8 |              2 |        nan |        nan |          nan |      nan |
| spread    |         4 |                    4 |            2 |                 1 |              1 |        nan |        nan |          nan |      nan |
| fees      |         2 |                    2 |            2 |                 1 |              1 |        nan |        nan |          nan |      nan |
| quote_unc |         2 |                    2 |            2 |                 1 |              1 |        nan |        nan |          nan |      nan |
| model_unc |         2 |                    2 |            2 |                 1 |              1 |        nan |        nan |          nan |      nan |
| size      |         1 |                    1 |            1 |                 1 |              1 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 0,
  "note": "insufficient data (n=0, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 1
- theta_kalshi: insufficient data (n=1, need >= 40)
- theta_realized: {"n": 0, "note": "insufficient data (n=0, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

