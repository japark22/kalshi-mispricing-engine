"""Map Kalshi contract definitions onto an option-implied distribution."""
from __future__ import annotations

import numpy as np
import pandas as pd

SUPPORTED = {"between", "greater", "greater_or_equal", "less", "less_or_equal"}


def yes_probability(rnd, strike_type, floor, cap) -> np.ndarray:
    """P(YES) under ``rnd`` for each contract (vectorised).

    between            -> P(floor <= S <= cap)   (Kalshi ranges are inclusive)
    greater(_or_equal) -> P(S > floor)
    less(_or_equal)    -> P(S < cap)
    The density is continuous, so inclusive/exclusive edges do not matter.
    Unsupported strike types return NaN.
    """
    st = np.asarray(strike_type, dtype=object)
    floor = np.asarray(floor, float)
    cap = np.asarray(cap, float)
    out = np.full(len(st), np.nan)
    b = st == "between"
    g = np.isin(st, ["greater", "greater_or_equal"])
    l_ = np.isin(st, ["less", "less_or_equal"])
    if b.any():
        out[b] = rnd.prob_between(floor[b], cap[b])
    if g.any():
        out[g] = rnd.prob_above(floor[g])
    if l_.any():
        out[l_] = rnd.prob_below(cap[l_])
    return out


def realized_yes(strike_type, floor, cap, level) -> np.ndarray:
    """Outcome implied by a settlement level (used to cross-check Kalshi's ``result``)."""
    st = np.asarray(strike_type, dtype=object)
    floor = np.asarray(floor, float)
    cap = np.asarray(cap, float)
    out = np.full(len(st), np.nan)
    b = st == "between"
    out[b] = ((level >= floor[b]) & (level <= cap[b])).astype(float)
    g = st == "greater"
    out[g] = (level > floor[g]).astype(float)
    ge = st == "greater_or_equal"
    out[ge] = (level >= floor[ge]).astype(float)
    l_ = st == "less"
    out[l_] = (level < cap[l_]).astype(float)
    le = st == "less_or_equal"
    out[le] = (level <= cap[le]).astype(float)
    return out


def partition(markets: pd.DataFrame, tol: float = 0.01) -> pd.DataFrame | None:
    """Return markets that tile the real line (lower tail, contiguous ranges, upper tail).

    Needed to score the two forecasters on a common, exhaustive set of
    outcomes. Kalshi writes range caps as e.g. 7549.9999 followed by a floor
    of 7550, so edges are matched within ``tol`` index points. Returns None
    when the event's contracts do not form a partition.
    """
    m = markets[markets["strike_type"].isin(SUPPORTED)]
    lows = m[m["strike_type"].isin(["less", "less_or_equal"])]
    highs = m[m["strike_type"].isin(["greater", "greater_or_equal"])]
    mids = m[m["strike_type"] == "between"].sort_values("floor_strike")
    if len(mids) == 0 or len(lows) == 0 or len(highs) == 0:
        return None
    lo = lows.loc[lows["cap_strike"].astype(float).idxmin()]
    hi = highs.loc[highs["floor_strike"].astype(float).idxmax()]
    edge = float(lo["cap_strike"])
    for _, r in mids.iterrows():
        if abs(float(r["floor_strike"]) - edge) > tol:
            return None
        edge = float(r["cap_strike"])
    if abs(float(hi["floor_strike"]) - edge) > tol:
        return None
    return pd.concat([lo.to_frame().T, mids, hi.to_frame().T]).reset_index(drop=True)
