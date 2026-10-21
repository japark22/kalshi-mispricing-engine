# Kalshi vs options: research report
_Generated 2026-10-21 18:09 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 510 (510 live, 0 backfill); rows without a synchronised Kalshi quote: 2
- Candle-replay check (candle state at fetch time == live book, live rows): 95.7% of 508 rows agree
- Snapshots: 12; events: 9; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-10-21T17:45:57.721076+00:00
- Settled events with outcomes: 7
- Smile model chosen: {'spline': 11, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       194 |                   97 |            9 |               127 |              7 |        nan |        nan |          nan |      nan |
| spread    |        19 |                   18 |            7 |                18 |              6 |        nan |        nan |          nan |      nan |
| fees      |        14 |                   14 |            7 |                13 |              6 |        nan |        nan |          nan |      nan |
| quote_unc |        11 |                   11 |            7 |                10 |              6 |        nan |        nan |          nan |      nan |
| model_unc |         9 |                    9 |            6 |                 8 |              5 |        nan |        nan |          nan |      nan |
| size      |         5 |                    5 |            5 |                 4 |              4 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 3,
  "note": "insufficient data (n=3, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 4
- theta_kalshi: insufficient data (n=4, need >= 40)
- theta_realized: {"n": 3, "note": "insufficient data (n=3, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

