import numpy as np

from kme.tilt import theta_realized, tilted_bucket_probs
from sim import tilt_probs, world


def _inputs(theta_true, n, kalshi_theta, seed=0):
    rng = np.random.default_rng(seed)
    model, _ = world(hours=24)                         # 1-day horizon for identifiability
    F = model.F
    x = np.linspace(F * 0.9, F * 1.1, 4001)
    q = model.pdf(x)
    edges = F + 25.0 * np.arange(-8, 9)
    p_true, xx, c = tilt_probs(model, edges, theta_true, F)
    k = tilted_bucket_probs(x, q, F, edges, kalshi_theta)
    out = []
    for _ in range(n):
        level = np.interp(rng.uniform(), c, xx)
        b = int(np.searchsorted(edges, level))
        out.append(dict(event_ticker="E", snapshot_id="S", x=x, q=q, F=F, edges=edges, kalshi=k,
                        realized_bucket=b))
    return out


def test_tilt_zero_is_identity():
    model, _ = world()
    F = model.F
    x = np.linspace(F * 0.95, F * 1.05, 2001)
    edges = F + 25.0 * np.arange(-4, 5)
    p = tilted_bucket_probs(x, model.pdf(x), F, edges, 0.0)
    c = model.cdf(np.concatenate([edges]))
    expect = np.diff(np.concatenate([[0], c, [1]]))
    assert np.allclose(p, expect, atol=2e-3)


def test_theta_realized_recovers_sign_and_rejects_zero():
    res = theta_realized(_inputs(theta_true=60.0, n=1500, kalshi_theta=0.0))
    assert res["ci95"][0] < 60 < res["ci95"][1] and res["p_vs_zero"] < 0.01


def test_theta_realized_small_sample_guard():
    assert "insufficient" in theta_realized(_inputs(5.0, 5, 0.0))["note"]
