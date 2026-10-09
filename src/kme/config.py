"""Central configuration. Every value can be overridden with an environment variable."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("KME_ROOT", Path(__file__).resolve().parents[2]))
DATA = ROOT / "data"
RESULTS = ROOT / "results"

ET = "America/New_York"

# --- sources (public endpoints) ---------------------------------------------
KALSHI_BASE = os.environ.get("KME_KALSHI_BASE", "https://api.elections.kalshi.com/trade-api/v2")
CBOE_URL = os.environ.get("KME_CBOE_URL", "https://cdn.cboe.com/api/global/delayed_quotes/options/_SPX.json")
SERIES = [s.strip() for s in os.environ.get("KME_SERIES", "KXINX").split(",") if s.strip()]
USER_AGENT = os.environ.get(
    "KME_USER_AGENT",
    "kalshi-mispricing-engine/0.1 (academic research; github.com/japark22/kalshi-mispricing-engine)")
MIN_SECONDS_BETWEEN_REQUESTS = float(os.environ.get("KME_THROTTLE", "0.35"))
MAX_RETRIES = 3

# --- option side --------------------------------------------------------------
OPTION_ROOT = "SPXW"          # PM-settled on the 4:00 pm close, like the Kalshi contract
MAX_EVENT_DAYS_AHEAD = int(os.environ.get("KME_MAX_DAYS_AHEAD", "3"))
N_BOOT = int(os.environ.get("KME_N_BOOT", "60"))
KEEP_RAW = os.environ.get("KME_KEEP_RAW", "0") == "1"   # raw Cboe quotes are never committed

# --- fees (Kalshi fee schedule effective 2026-07-07; check before relying on it) ---
TAKER_FEE_COEF = float(os.environ.get("KME_TAKER_FEE", "0.07"))
MAKER_FEE_COEF = float(os.environ.get("KME_MAKER_FEE", "0.0175"))

# --- research thresholds --------------------------------------------------------
# Residual model error an option-implied 25-pt bucket probability can carry
# *beyond* its 90% band. Default = the maximum excess observed in
# option-implied-density's known-answer study, fat_tail_0dte case
# (results/known_answer_coverage_summary.csv: excess_max_pp = 0.207). Units: probability.
MODEL_ERROR_TOL = float(os.environ.get("KME_MODEL_TOL", "0.0021"))
# Display floor, not a power guarantee: see results/tilt_power.csv for how many
# days the tilt test actually needs.
MIN_DAYS_FOR_INFERENCE = int(os.environ.get("KME_MIN_DAYS", "40"))
