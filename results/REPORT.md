# Kalshi vs options: research report
_Generated 2026-10-17 16:33 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 330 (330 live, 0 backfill); rows without a synchronised Kalshi quote: 2
- Candle-replay check (candle state at fetch time == live book, live rows): 96.6% of 328 rows agree
- Snapshots: 8; events: 5; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-10-16T19:56:04.024367+00:00
- Settled events with outcomes: 5
- Smile model chosen: {'spline': 7, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       110 |                   44 |            5 |               110 |              5 |        nan |        nan |          nan |      nan |
| spread    |        13 |                   12 |            4 |                13 |              4 |        nan |        nan |          nan |      nan |
| fees      |         8 |                    8 |            4 |                 8 |              4 |        nan |        nan |          nan |      nan |
| quote_unc |         7 |                    7 |            4 |                 7 |              4 |        nan |        nan |          nan |      nan |
| model_unc |         6 |                    6 |            4 |                 6 |              4 |        nan |        nan |          nan |      nan |
| size      |         3 |                    3 |            3 |                 3 |              3 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 1,
  "note": "insufficient data (n=1, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 1
- theta_kalshi: insufficient data (n=1, need >= 40)
- theta_realized: {"n": 1, "note": "insufficient data (n=1, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

