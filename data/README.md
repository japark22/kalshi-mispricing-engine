# data/

Written by `python -m kme ...`. Only derived statistics and public Kalshi top-of-book quotes are stored here.

| Path | Content |
|---|---|
| `panel/YYYY-MM.csv` | One row per Kalshi contract per snapshot, with a fixed schema (`storage.PANEL_COLS`). Timestamps: `asof_utc` ≤ `options_fetch_utc` ≤ `decision_utc`. Kalshi bid/ask are as of `asof_utc` (candle closed at `kalshi_quote_ts`), the live book is in `live_*`, the option-implied probability is in `q_point` with its nominal 90% band in `q_lo`/`q_hi`, followed by per-model values and fit diagnostics. No settlement fields. |
| `panel/backfill_YYYY-MM.csv` | Same schema, `source = backfill`, built from user-supplied EOD option files + Kalshi 1-minute candles. |
| `rnd/YYYY-MM-DD/HHMMSSZ_<event>.csv.gz` | Option-implied CDF (with band) and density on a 5-point grid, for PIT and tilt analysis. |
| `outcomes.csv` | Kalshi settlement results per contract, joined only after the event date and cross-checked against the settlement level. |
| `run_log.csv` | `run_time, stage, status, count, error_summary` for every stage of every run. |
| `raw/` | Optional local copy of raw Cboe quotes (`KME_KEEP_RAW=1`). Git-ignored. |
