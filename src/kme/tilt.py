"""Is the Kalshi-vs-options gap mispricing, or a risk premium?

Option prices are risk-neutral (q); prediction-market prices are, at least in
part, beliefs about real-world (physical) probabilities (p). A standard link is
an exponential / power pricing-kernel tilt:

    p_theta(x)  ∝  q(x) * exp(theta * ln(x / F))      (CRRA: theta = risk aversion)

Three estimates:

* theta_realized  - MLE of theta from realised outcomes (what tilt makes the
                    option density a good *forecast*?), with a profile-
                    likelihood 95% interval;
* theta_kalshi    - per snapshot, the tilt that best maps q onto Kalshi's
                    normalised bucket prices;
* explained share - 1 - SSE(Kalshi, p_theta_kalshi) / SSE(Kalshi, q): how much
                    of the raw gap a single risk-premium parameter absorbs.

If Kalshi's theta matches theta_realized, Kalshi is pricing the physical
measure and the "mispricing" is the risk premium. If Kalshi's theta is ~0,
Kalshi is simply tracking the option market. The residual after the tilt is
the candidate for genuine mispricing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import chi2

from . import config
from .model import partition
from .score import grid_path, select_snapshots

BOUNDS = (-100.0, 100.0)


def tilted_bucket_probs(x, q, F, edges, theta):
    """Bucket probabilities under p_theta, edges = [-inf, e1, ..., en, +inf] as finite list e1..en."""
    w = q * np.exp(theta * np.log(x / F))
    cum = np.concatenate([[0.0], np.cumsum(0.5 * (w[1:] + w[:-1]) * np.diff(x))])
    cum = cum / cum[-1]
    c = np.interp(edges, x, cum)
    return np.diff(np.concatenate([[0.0], c, [1.0]]))


def load_inputs(panel: pd.DataFrame, outcomes: pd.DataFrame | None = None) -> list[dict]:
    """Per selected snapshot: grid, edges, Kalshi normalised mids, realised bucket (if settled)."""
    out = []
    sel = select_snapshots(panel).sort_values("asof_utc")
    o = outcomes.drop_duplicates("ticker").set_index("ticker") if outcomes is not None and len(outcomes) else None
    for (_, ev, sid), g in sel.groupby(["event_date", "event_ticker", "snapshot_id"], sort=True):
        part = partition(g)
        gp = grid_path(g["decision_utc"].iloc[0], ev)
        if part is None or not gp.exists():
            continue
        grid = pd.read_csv(gp)
        mid = 0.5 * (part["yes_bid"].astype(float) + part["yes_ask"].astype(float)).to_numpy()
        if np.isnan(mid).any():
            continue
        edges = np.concatenate([[float(part["cap_strike"].iloc[0])], part["cap_strike"].iloc[1:-1].astype(float)])
        d = dict(event_ticker=ev, snapshot_id=sid, x=grid["x"].to_numpy(), q=grid["pdf"].to_numpy(),
                 F=float(g["F"].iloc[0]), edges=edges, kalshi=mid / mid.sum())
        if o is not None and set(part["ticker"]).issubset(o.index):
            y = o.loc[part["ticker"], "yes"].to_numpy(float)
            if y.sum() == 1:
                d["realized_bucket"] = int(np.argmax(y))
        out.append(d)
    return out


def theta_realized(inputs: list[dict]) -> dict:
    data = [d for d in inputs if "realized_bucket" in d]
    n = len(data)
    if n < config.MIN_DAYS_FOR_INFERENCE:
        return dict(n=n, note=f"insufficient data (n={n}, need >= {config.MIN_DAYS_FOR_INFERENCE})")

    def nll(th):
        return -sum(np.log(max(tilted_bucket_probs(d["x"], d["q"], d["F"], d["edges"], th)[d["realized_bucket"]],
                               1e-9)) for d in data)

    r = minimize_scalar(nll, bounds=BOUNDS, method="bounded")
    th, best = r.x, r.fun
    grid = np.linspace(*BOUNDS, 401)
    prof = np.array([nll(t) for t in grid])
    inside = grid[2 * (prof - best) <= chi2.ppf(0.95, 1)]
    return dict(n=n, theta=float(th), ci95=(float(inside.min()), float(inside.max())),
                lr_vs_zero=float(2 * (nll(0.0) - best)), p_vs_zero=float(chi2.sf(2 * (nll(0.0) - best), 1)),
                at_bound=bool(abs(th) > 0.99 * BOUNDS[1]))


def theta_kalshi(inputs: list[dict]) -> pd.DataFrame:
    rows = []
    for d in inputs:
        q0 = tilted_bucket_probs(d["x"], d["q"], d["F"], d["edges"], 0.0)

        def sse(th, d=d):
            return float(np.sum((d["kalshi"] - tilted_bucket_probs(d["x"], d["q"], d["F"], d["edges"], th)) ** 2))

        r = minimize_scalar(sse, bounds=BOUNDS, method="bounded")
        base = float(np.sum((d["kalshi"] - q0) ** 2))
        rows.append(dict(event_ticker=d["event_ticker"], snapshot_id=d["snapshot_id"], theta=float(r.x),
                         sse_raw=base, sse_tilted=float(r.fun),
                         explained_share=float(1 - r.fun / base) if base > 0 else np.nan))
    return pd.DataFrame(rows)
