# Kalshi vs options: research report
_Generated 2026-10-29 19:05 UTC by `python -m kme report`. Every figure below is computed from files in `data/`; sections without enough data say so._

## Data coverage
- Panel rows: 840 (840 live, 0 backfill); rows without a synchronised Kalshi quote: 15
- Candle-replay check (candle state at fetch time == live book, live rows): 95.4% of 825 rows agree
- Snapshots: 19; events: 15; first decision 2026-10-09T19:44:21.670578+00:00, last 2026-10-29T18:43:38.895395+00:00
- Settled events with outcomes: 13
- Smile model chosen: {'spline': 18, 'svi': 1}

## Edge funnel
Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. Model-error tolerance = 0.0021 (range contracts, same-day only). P&L is per contract after fees, t-stat clusters by event day, shown only with >= 40 settled event days.

| stage     |   signals |   contracts_distinct |   event_days |   settled_signals |   settled_days |   mean_pnl |   hit_rate |   daily_mean |   t_stat |
|:----------|----------:|---------------------:|-------------:|------------------:|---------------:|-----------:|-----------:|-------------:|---------:|
| naive     |       284 |                  153 |           15 |               248 |             13 |        nan |        nan |          nan |      nan |
| spread    |        31 |                   30 |           14 |                28 |             12 |        nan |        nan |          nan |      nan |
| fees      |        24 |                   24 |           14 |                22 |             12 |        nan |        nan |          nan |      nan |
| quote_unc |        21 |                   21 |           14 |                19 |             12 |        nan |        nan |          nan |      nan |
| model_unc |        15 |                   15 |           11 |                14 |             10 |        nan |        nan |          nan |      nan |
| size      |        10 |                   10 |           10 |                 9 |              9 |        nan |        nan |          nan |      nan |

## Which forecast was better? (log score on the realised range)
```
{
  "n_events": 9,
  "note": "insufficient data (n=9, need >= 40 settled events)"
}
```

## Risk premium or mispricing? (pricing-kernel tilt)
- Snapshots with a full partition + density grid: 10
- theta_kalshi: insufficient data (n=10, need >= 40)
- theta_realized: {"n": 9, "note": "insufficient data (n=9, need >= 40)"}

## Figures
![latest](figures/latest_snapshot.png)

![funnel](figures/edge_funnel.png)

