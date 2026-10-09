# kalshi-mispricing-engine

**Two markets, one question: what is the probability that the S&P 500 closes inside this 25-point range today?**

## Research at a glance

**Question.** Kalshi's daily S&P 500 range contracts and same-day SPXW options both price one number: the probability that the index closes inside a given 25-point range at 4:00 pm today. When the two markets disagree, is it a tradeable mispricing, a risk premium, or noise?

**Why this design is different**

1. **Same outcome, same settlement, same day.** Earlier work compared Kalshi *year-end* contracts with options, which gives about one outcome a year. This repo uses daily contracts against options that expire the same afternoon, so every trading day settles one outcome across about 30 contracts.
2. **Point-in-time by construction, not by promise.** The public option feed is delayed by about 15 minutes. Kalshi is therefore replayed to the option chain's exact as-of time from its 1-minute candles. Each run checks that replay against the live order book, and the agreement rate is published. Outcomes are joined only after settlement and cross-checked against the settlement level. Tests enforce each of these rules.
3. **A disagreement is not an edge.** A six-stage funnel counts how many apparent mispricings survive the bid-ask, Kalshi's fee schedule, the uncertainty in the option-implied probability (from the [density engine's](https://github.com/japark22/option-implied-density) known-answer study), and the displayed size.
4. **Risk premium vs mistake.** Option prices are risk-neutral, so a gap may be compensation for risk rather than an error. A one-parameter pricing-kernel tilt separates the two.
5. **Power analysis before claims.** Simulation shows that realised outcomes alone cannot identify the tilt at this horizon. With risk aversion θ = 10, the test has **26% power after 2,500 trading days** ([`results/tilt_power.csv`](results/tilt_power.csv)). Inference therefore relies on the tilt implied by *prices*, which carries no outcome sampling noise.

**Engineering.** A GitHub Actions collector runs five times a trading day. Every stage is logged (`success` / `partial` / `failed`), and the report is rebuilt automatically. Inferential sections print "insufficient data" below 40 settled days. A lookahead tripwire flags implausible profits. Raw third-party quotes are never committed.

> **Status.** The pipeline and its offline tests are complete, and both public APIs are verified live. Collection accumulates in [`results/REPORT.md`](results/REPORT.md). No result in this repository is simulated or estimated by hand.

---

## Prior work, and what this adds

This comparison has been tried before, so the contribution is in the details.

| Prior work | What it did | Gap this repo addresses |
|---|---|---|
| [Stevens FSC student project (2025)](https://fsc.stevens.edu/event-contract-mispricing-via-options-implied-probabilities/) | Breeden-Litzenberger on SPXW vs Kalshi *year-end* S&P buckets, 2022–24, long-short portfolio | Only about one outcome a year, so there is almost no statistical power. The author also reports that liquidity and data gaps dominated. Here we use **daily** contracts against **same-day** SPXW: one settled outcome per trading day, with many buckets each. |
| [Dune: Kalshi vs Polymarket vs FedWatch](https://dune.com/blog/pricing-the-fed-kalshi-polymarket-cme-fedwatch) | FOMC hold probabilities across venues | Found that the gaps mostly came from the venues asking different questions. Here the contract and the option settle on the **same number at the same time**. |
| Calibration studies of Kalshi (e.g. [arXiv 2602.19520](https://arxiv.org/abs/2602.19520)) | Favourite-longshot and domain calibration | These score Kalshi alone. Here Kalshi is scored **against a second market's forecast** on identical outcomes. |

The usual write-up treats the option-implied probability as the truth and calls any difference a mispricing. This repo does not. Option prices are **risk-neutral**, so a gap can be a risk premium rather than a mistake. The tilt analysis separates the two.

## Design

```
 every snapshot (5x per US trading day, GitHub Actions)
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ 1. GET Cboe delayed SPX chain; as-of time t_asof = newest trade in it   │
 │ 2. GET Kalshi KXINX open markets (live book, kept as live_* columns)    │
 │    + each contract's last 1-min candle CLOSED at or before t_asof       │  both sides as of t_asof
 │ 3. for each event (settles at the close on date d, hour from ticker):    │
 │      SPXW expiry d only (PM-settled; AM-settled SPX ignored)             │
 │      parity forward -> OTM quotes -> SVI and spline smiles               │
 │      -> analytic density -> P(YES) for every contract                    │
 │      -> nominal 90% band = bid-ask bootstrap ∪ across smile models       │
 │ 4. append panel rows + CDF grid; log every stage to data/run_log.csv     │
 └──────────────────────────────────────────────────────────────────────────┘
 next morning: join Kalshi settlement results (only for dates < today, cross-checked)
              -> rebuild results/REPORT.md
```

**Point-in-time rules**

- **Synchronised, not just ordered.** The public option feed is about 15 minutes delayed, so comparing it with the live Kalshi book would set a stale distribution against a fresh price and manufacture disagreement whenever the index moves. Kalshi is therefore read **as of the option chain's as-of time**, from the last 1-minute candle that closed at or before it. Kalshi emits candles only in minutes where something changed, so the last close is carried forward and its age is stored. Every run replays the same candles at fetch time and compares them with the live book, and the report shows the agreement rate, so this assumption is tested rather than assumed. The live book is stored separately.
- Outcomes come from Kalshi's own settlement records. They are joined only for event dates before today (ET). If a settlement level contradicts any contract's result, that event is held back.
- The historical backfill reads Kalshi from the last 1-minute candle that **closed at or before** the option quote time (`kalshi.quote_at`). A unit test checks this.
- Stale chains are skipped: if the newest option trade is more than 45 minutes old, there is no snapshot (holidays, late cron runs).

## The edge funnel

Each contract is evaluated on both sides (buy YES at the ask, buy NO at 1 − bid). The stages are cumulative:

| Stage | Survives if... |
|---|---|
| `naive` | the Kalshi mid differs from the option probability by at least 1¢ (where most write-ups stop) |
| `spread` | the option fair value beats the **executable** price |
| `fees` | ...after Kalshi's taker fee, 0.07·P·(1−P) per contract rounded up to $0.0001 (fee schedule effective 2026-07-07; KXINX multiplier 1 per `GET /series/KXINX`) |
| `quote_unc` | ...using the conservative end of the option-implied band (nominal 90%; the known-answer study measured **61%** coverage in the 0DTE case) |
| `model_unc` | ...after a 0.21 pp model-error tolerance, the largest excess beyond the band seen in that study. It applies only where it was measured, so tail contracts and multi-day events cannot pass this stage. |
| `size` | ...with at least one contract displayed at that price (live book used as a proxy) |

Realised P&L per contract (after fees) is reported at every stage once 40 or more event-days have settled. Because prices are synchronised to the delayed option feed, the funnel **measures** mispricing. It becomes a tradeable backtest only with a real-time option feed. t-statistics cluster by event-day. If any stage earns more than 10¢ per contract, the report adds a **⚠️ POSSIBLE LOOKAHEAD** flag, because on liquid index ranges that is almost certainly a bug.

## Risk premium or mispricing?

Physical (real-world) and risk-neutral densities are linked through a pricing kernel. With a power kernel:

$$p_\theta(x) \;\propto\; q(x)\left(\tfrac{x}{F}\right)^{\theta}$$

Here $q$ is the option-implied density and $\theta$ plays the role of relative risk aversion. The report estimates three things:

- **$\theta_{\text{realized}}$**: the maximum-likelihood tilt that turns $q$ into the best forecast of realised outcomes, with a profile-likelihood 95% interval.
- **$\theta_{\text{Kalshi}}$**: for each snapshot, the tilt that best maps $q$ onto Kalshi's normalised bucket prices.
- **Explained share**: how much of the Kalshi-vs-options gap a single tilt parameter absorbs.

**Power check before any claim** ([`scripts/tilt_power.py`](scripts/tilt_power.py) → [`results/tilt_power.csv`](results/tilt_power.csv), 200 simulations per cell, fat-tailed 0DTE world, 2-hour horizon):

| True θ | Largest bucket shift | Power, 250 days | Power, 1,000 days | Power, 2,500 days |
|---|---|---|---|---|
| 2 | 0.12 pp | 4% | 7% | 7% |
| 10 | 0.62 pp | 6% | 12% | 26% |
| 30 | 1.91 pp | 25% | 62% | 95% |

At realistic risk aversion, **outcomes alone cannot identify θ at this horizon, even with ten years of data**. θ_realized is therefore reported only as an interval. The informative estimate is θ_Kalshi, which is fitted to *prices* at every snapshot and carries no outcome sampling noise.

How to read the results:

- If $\theta_{\text{Kalshi}} \approx \theta_{\text{realized}}$, Kalshi is pricing real-world probabilities and the "mispricing" is the risk premium.
- If $\theta_{\text{Kalshi}} \approx 0$, Kalshi is tracking the option market.
- What is left after the tilt is the candidate for genuine mispricing.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ../option-implied-density        # or: pip install -r requirements.txt
pip install -e . --no-deps

python -m kme smoke        # do both public endpoints answer and parse? (run this first)
python -m kme snapshot     # one live snapshot (US market hours)
python -m kme settle       # join outcomes for past events
python -m kme report       # rebuild results/REPORT.md
python -m kme backfill path/to/eod_options.csv   # optional: your own EOD option files
pytest -q                  # offline tests, no network needed
```

**Automated collection:**

1. Push this repo to GitHub, after `option-implied-density` is public, because `requirements.txt` installs it from there.
2. In *Settings → Actions → General*, allow workflows **read and write** permission.
3. Run the `collect` workflow manually with `task = smoke`.
4. After that, the schedule takes over.

GitHub may pause scheduled workflows in repositories with no activity for 60 days.

## Data and licensing

- **Kalshi:** public read-only market-data endpoints. There is no account, no authentication and no trading. Requests are throttled with retries and back-off.
- **Cboe:** the public delayed-quote JSON. **Raw option quotes are not committed.** Only derived statistics are stored: fitted forward, diagnostics, probabilities and CDF grids. Set `KME_KEEP_RAW=1` to keep raw payloads locally (git-ignored).
- **Backfill:** uses end-of-day option files that you obtain yourself, under that vendor's terms. Files without an option root cannot tell SPXW from the AM-settled SPX monthly, so third-Friday expiries are dropped.

## Limitations

- **Delayed option feed.** Comparisons are synchronised to the option chain's as-of time, which is inferred from the newest trade in the payload. A strategy acting on these signals would need a real-time option feed.
- **Top of book only.** Kalshi depth is not walked, so the size stage is a lower bound on what is needed.
- **Taker fees only.** Fees are modelled for taker orders. A maker strategy would need queue modelling, which is out of scope.
- **Model tolerance comes from simulation.** The tolerance is the largest excess in 12 simulated runs (`option-implied-density`, fat-tailed 0DTE case). The simulator shares the bootstrap's noise model, so it is a scale, not a bound.
- **No power for θ_realized.** Outcomes alone cannot pin down the tilt at intraday horizons (see the power table above).
- **Fixed close time.** Early-close days are handled through the event ticker's hour (e.g. `H1300`). This has not been verified against a live half-day listing.

## Layout

```
src/kme/      kalshi.py (client) · snapshot.py (collector) · settle.py · model.py (contract→probability)
              edge.py (funnel) · score.py (log score, DM, PIT) · tilt.py (pricing kernel) · backfill.py · report.py
tests/        offline tests on API-shaped synthetic data, incl. point-in-time and end-to-end
data/         derived panel, CDF grids, outcomes, run log (see data/README.md)
results/      REPORT.md + figures, rebuilt by `python -m kme report`
docs/         METHODOLOGY.md
```

MIT licence. Research code, not investment advice.
