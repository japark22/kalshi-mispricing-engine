# Kalshi vs options: research report
_Generated 2026-10-13 19:55 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 90 (90 live, 0 backfill); rows without a synchronised Kalshi quote: 0
- Candle-replay check (candle state at fetch time == live book, live rows): 100.0% of 90 rows agree
- Snapshots: 2; events: 3; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-10-13T19:38:45.155088+00:00
- Settled events with outcomes: 1
- Smile model chosen: {'spline': 1, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |        27 |                   27 |            3 |                 6 |              1 |        nan |        nan |          nan |      nan |
| spread    |         1 |                    1 |            1 |                 1 |              1 |        nan |        nan |          nan |      nan |
| fees      |         1 |                    1 |            1 |                 1 |              1 |        nan |        nan |          nan |      nan |
| quote_unc |         1 |                    1 |            1 |                 1 |              1 |        nan |        nan |          nan |      nan |
| model_unc |         1 |                    1 |            1 |                 1 |              1 |        nan |        nan |          nan |      nan |
| size      |         1 |                    1 |            1 |                 1 |              1 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 0,
  "note": "insufficient data (n=0, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 0
- theta_kalshi: insufficient data (n=0, need >= 40)
- theta_realized: {"n": 0, "note": "insufficient data (n=0, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

