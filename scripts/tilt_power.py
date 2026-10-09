"""Power of the pricing-kernel tilt test: how many days before theta is detectable?

Simulates the scoring set-up (one 25-pt range partition per day, outcome drawn
from the *tilted* density) with the fat-tailed 0DTE world from the known-answer
study, and records how often the likelihood-ratio test rejects theta = 0 at 5%.
Stationary world, no estimation noise in q: this is an upper bound on power.

Writes results/tilt_power.csv.   Usage: python scripts/tilt_power.py [--sims 300]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.stats import chi2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sib = ROOT.parent / "option-implied-density" / "src"
if sib.exists():
    sys.path.insert(0, str(sib))

from kme.tilt import BOUNDS, tilted_bucket_probs  # noqa: E402
from sim import world  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sims", type=int, default=300)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    rows = []
    for hours in (2.0, 24.0):
        model, _ = world(hours=hours)
        F = model.F
        x = np.linspace(F * 0.85, F * 1.15, 6001)
        q = model.pdf(x)
        edges = F + 25.0 * np.arange(-12, 13)
        cache = {}

        def P(th):
            key = round(th, 6)
            if key not in cache:
                cache[key] = np.maximum(tilted_bucket_probs(x, q, F, edges, th), 1e-12)
            return cache[key]

        for theta in (2.0, 5.0, 10.0, 30.0, 100.0):
            p_true = P(theta)
            shift = float(np.abs(p_true - P(0.0)).max())
            for n in (250, 1000, 2500):
                rej = 0
                for _ in range(a.sims):
                    counts = rng.multinomial(n, p_true / p_true.sum())

                    def nll(th):
                        return -float(np.dot(counts, np.log(tilted_bucket_probs(x, q, F, edges, th).clip(1e-12))))

                    r = minimize_scalar(nll, bounds=BOUNDS, method="bounded", options={"xatol": 1e-3})
                    lr = 2 * (nll(0.0) - r.fun)
                    rej += lr > chi2.ppf(0.95, 1)
                rows.append(dict(horizon_hours=hours, theta=theta, max_bucket_shift_pp=100 * shift,
                                 days=n, power=rej / a.sims, sims=a.sims))
                print(rows[-1])
    out = ROOT / "results" / "tilt_power.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
