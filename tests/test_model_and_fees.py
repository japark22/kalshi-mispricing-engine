import numpy as np
import pandas as pd
import pytest

from kme.edge import kalshi_fee
from kme.kalshi import markets_frame
from kme.model import partition, realized_yes, yes_probability
from rnd.synthetic import Lognormal
from sim import kalshi_markets, world


class _R:   # minimal RND stand-in backed by a known model
    def __init__(self, m):
        self.m = m

    def prob_between(self, a, b):
        return self.m.cdf(b) - self.m.cdf(a)

    def prob_above(self, x):
        return 1 - self.m.cdf(x)

    def prob_below(self, x):
        return self.m.cdf(x)


def test_partition_probabilities_sum_to_one():
    model, T = world()
    m = markets_frame(kalshi_markets(model, "2026-10-05"))
    part = partition(m)
    assert part is not None and len(part) == len(m)
    p = yes_probability(_R(model), part["strike_type"], part["floor_strike"], part["cap_strike"])
    assert abs(p.sum() - 1) < 1e-3


def test_partition_rejects_gaps():
    model, T = world()
    m = markets_frame(kalshi_markets(model, "2026-10-05"))
    assert partition(m.drop(index=5)) is None


def test_realized_yes_matches_definitions():
    st = np.array(["between", "greater", "less"], dtype=object)
    y = realized_yes(st, [7525, 7549.9999, np.nan], [7549.9999, np.nan, 7350], 7530.0)
    assert list(y) == [1.0, 0.0, 0.0]


@pytest.mark.parametrize("p,fee", [(0.5, 0.0175), (0.10, 0.0063), (0.99, 0.0007)])
def test_taker_fee(p, fee):
    assert abs(kalshi_fee(p) - fee) < 1e-9
