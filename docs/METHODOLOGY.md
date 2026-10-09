# Methodology

## 1. Contract ↔ distribution mapping

Kalshi's `KXINX` series is *S&P 500 range, daily*. Each event (for example `KXINX-26OCT09H1600`) settles on the index level at 4:00 pm ET on its date. Its markets come in three kinds:

| `strike_type` | YES pays if | Option-implied probability |
|---|---|---|
| `between` (floor, cap) | floor ≤ S ≤ cap | `F(cap) − F(floor)` |
| `greater` (floor) | S > floor | `1 − F(floor)` |
| `less` (cap) | S < cap | `F(cap)` |

Here `F` is the option-implied CDF, computed analytically from the fitted smile (`rnd.density.RND.cdf`). Only **SPXW** expiries are used, because they are PM-settled on the 4:00 pm close. The **SPX** monthly root settles on the opening quotation and is excluded. Kalshi's [INX contract terms](https://assets.kalshi.com/contract_terms/INX.pdf) define the underlying as the S&P 500 value at the stated time on the stated date, with Kalshi as the source agency. The SPXW settlement value is the official closing print. We treat the two as the same number. Any difference between them is unmodelled noise.

## 2. Uncertainty of the option-implied probability

There are two sources of uncertainty:

1. **Quotes.** A quote is an interval. The whole pipeline is rerun with every two-sided quote replaced by a uniform draw inside [bid, ask] (60 draws per fitter by default). Model selection and the spline penalty are frozen at their values on the observed quotes.
2. **Model.** SVI and a penalised spline are fitted independently. Any fitter whose RMS pricing error is more than max(2, 1.5×best) half-spreads is rejected. The reported 90% band is the **union** of the surviving fitters' bootstrap bands.

The known-answer study in `option-implied-density` shows that this union still under-covers when the true density has fat tails: 61% coverage in the 0DTE case, so the band is **nominal** 90%. The edge funnel therefore subtracts an additional `MODEL_ERROR_TOL` of 0.0021, the largest excess beyond the band observed in that study. It is applied only to range contracts on same-day events, because that is where it was measured.

## 3. Scoring

- **One snapshot per event.** For each event we score the live snapshot closest to 120 minutes before settlement (`KME_SCORE_MINUTES`), and only if it lies within ±45 minutes of that target. This avoids overlapping observations and keeps every scored event at the same horizon. Events are scored in date order, because Berkowitz's AR(1) term and Newey-West both depend on it. Backfill is scored separately.
- **Common outcomes.** Both forecasters are scored on the same exhaustive partition: lower tail, contiguous ranges, upper tail. `model.partition` verifies that the edges tile the line.
- **Normalisation.** Kalshi mids are normalised to sum to one, and the overround is reported separately.
- **Scores and tests.** We record the log score of the realised bucket, run a Diebold-Mariano test with Newey-West variance across events, and compute PIT values of the option-implied CDF with a Berkowitz (2001) test. Risk-neutral densities are expected to fail the Berkowitz test because of the risk premium. The direction of the failure is the informative part.

## 4. Pricing-kernel tilt

With $p_\theta(x) \propto q(x)\,(x/F)^\theta$:

- **θ_realized.** Maximise $\sum_t \log P_{\theta,t}(\text{realised bucket}_t)$ over θ ∈ [−100, 100]. The 95% interval comes from the profile likelihood (χ²₁). The likelihood-ratio test against θ = 0 asks whether the risk-neutral density is a worse forecast than some tilt of itself.
- **θ_Kalshi,t.** Least squares between Kalshi's normalised bucket prices and $P_{\theta}$ at each snapshot.
- **Explained share.** Defined as `1 − SSE(Kalshi, p_θ̂) / SSE(Kalshi, q)`.

For a power-utility representative agent, θ equals relative risk aversion. At a 2-hour horizon, θ = 10 moves bucket probabilities by at most 0.62 pp, and the realised-outcome test has 26% power even after 2,500 days (`results/tilt_power.csv`). θ_realized is therefore an interval, not a finding, and θ_Kalshi (fitted to prices) carries the analysis. The report flags estimates at the bound.

## 5. Point-in-time checklist (tested)

| Rule | Where | Test |
|---|---|---|
| Kalshi read as of the option chain's as-of time, from the last candle closed at or before it (sparse candles carried forward); future candles are ignored | `snapshot.run_snapshot`, `kalshi.quote_at` | `test_end_to_end::test_snapshot_settle_report`, `test_kalshi_parsing` |
| Carry-forward of sparse candles validated against the live book each run | `snapshot.synced_quotes`, `report._replay` | same end-to-end test |
| Panel never contains settlement fields (result, expiration value) | `storage.PANEL_COLS` | same test |
| No outcome joined before the event date has passed | `settle.settle_pending` | same test (early settle call writes nothing) |
| Settlement level must agree with every contract's result | `settle.settle_pending` | same test |
| Backfill uses only candles closed at or before the decision time | `kalshi.quote_at` | `test_kalshi_parsing::test_quote_at_never_uses_a_future_candle` |
| Stale option chains are not used | `snapshot.options_freshness` | `test_end_to_end::test_stale_chain_is_skipped` |
| Failures are logged, never silently dropped | every stage | `test_end_to_end::test_failures_are_logged_not_raised` |
