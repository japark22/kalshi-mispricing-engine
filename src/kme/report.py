"""Build results/REPORT.md and figures from whatever data exists - and nothing else.

Every number in the report is computed here from files under data/. Sections
whose sample is too small say "insufficient data" instead of showing a number.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from . import config
from .edge import STAGES, attach_outcomes, funnel_rows, funnel_summary
from .score import compare, event_table
from .storage import log_stage, read_outcomes, read_panel, read_run_log, utcnow
from .tilt import load_inputs, theta_kalshi, theta_realized


def _md(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False, floatfmt=".4f") if len(df) else "_none_"


def attention(run_log: pd.DataFrame) -> list[str]:
    """Flag any stage that failed in at least half of its last 6 attempts (or in the last 5 log rows twice)."""
    msgs = []
    for stage, g in run_log.groupby("stage"):
        recent = g.tail(6)
        n_fail = int((recent["status"] == "failed").sum())
        if n_fail >= max(2, len(recent) // 2):
            err = recent.loc[recent["status"] == "failed", "error_summary"].dropna().astype(str)
            msgs.append(f"Stage `{stage}` failed {n_fail} of its last {len(recent)} attempts"
                        + (f": {err.iloc[-1][:200]}" if len(err) else ""))
    return msgs


def _replay(panel: pd.DataFrame) -> str:
    chk = panel[panel["source"] == "live"].dropna(subset=["candle_at_decision_bid", "live_yes_bid"])
    if chk.empty:
        return "no live rows yet"
    agree = ((chk["candle_at_decision_bid"] - chk["live_yes_bid"]).abs() < 1e-9) & \
            ((chk["candle_at_decision_ask"] - chk["live_yes_ask"]).abs() < 1e-9)
    return f"{agree.mean():.1%} of {len(chk):,} rows agree"


def coverage_flags(panel: pd.DataFrame) -> list[str]:
    flags = []
    if panel.empty:
        return flags
    live = panel[panel["source"] == "live"]
    if len(live):
        per_day = live.groupby(pd.to_datetime(live["decision_utc"]).dt.date)["snapshot_id"].nunique()
        if len(per_day) >= 5 and per_day.iloc[-1] < 0.5 * per_day.iloc[:-1].median():
            flags.append(f"Snapshot count dropped on {per_day.index[-1]}: {per_day.iloc[-1]} vs median "
                         f"{per_day.iloc[:-1].median():.0f}.")
        miss = live["q_point"].isna().mean()
        nosync = live["yes_bid"].isna().mean()
        chk = live.dropna(subset=["candle_at_decision_bid", "live_yes_bid"])
        if len(chk):
            agree = ((chk["candle_at_decision_bid"] - chk["live_yes_bid"]).abs() < 1e-9) & \
                    ((chk["candle_at_decision_ask"] - chk["live_yes_ask"]).abs() < 1e-9)
            if agree.mean() < 0.95:
                flags.append(f"Candle replay matches the live book for only {agree.mean():.1%} of rows - "
                             f"the carry-forward assumption behind synchronised quotes is weak.")
        if nosync > 0.10:
            flags.append(f"{nosync:.1%} of live rows lack a synchronised Kalshi candle quote.")
        if miss > 0.05:
            flags.append(f"{miss:.1%} of live panel rows have no option-implied probability.")
    return flags


def figures(panel: pd.DataFrame, fsum: pd.DataFrame):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from rnd.plotting import INK_2, S1, S2, style

    style()
    fig_dir = config.RESULTS / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    # 1) latest snapshot: Kalshi quotes vs options-implied probability with band
    last = panel[panel["snapshot_id"] == panel["snapshot_id"].max()]
    for ev, g in last.groupby("event_ticker"):
        g = g[g["strike_type"] == "between"].sort_values("floor_strike")
        if g.empty:
            continue
        g = g.dropna(subset=["yes_bid", "yes_ask"])
        if g.empty:
            continue
        x = 0.5 * (g["floor_strike"] + g["cap_strike"])
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.fill_between(x, g["q_lo"], g["q_hi"], color=S1, alpha=0.18, lw=0, label="Options-implied, nominal 90% band")
        ax.plot(x, g["q_point"], color=S1, label="Options-implied probability")
        ax.vlines(x, g["yes_bid"], g["yes_ask"], color=S2, lw=2.5, label="Kalshi bid-ask (as of option quotes)")
        ax.set_xlabel("S&P 500 range (midpoint)")
        ax.set_ylabel("Probability")
        ax.set_title(f"{ev}: snapshot {g['snapshot_id'].iloc[0]} "
                     f"({g['minutes_to_settle'].iloc[0]:.0f} min before settlement)", loc="left")
        ax.legend(loc="upper right", fontsize=8)
        fig.tight_layout()
        fig.savefig(fig_dir / "latest_snapshot.png", dpi=150)
        plt.close(fig)
        break
    # 2) funnel
    if len(fsum):
        fig, ax = plt.subplots(figsize=(8, 3.6))
        ax.bar(fsum["stage"], fsum["signals"], color=S1, width=0.6)
        for i, v in enumerate(fsum["signals"]):
            ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=8.5, color=INK_2)
        ax.set_ylabel("Signals (contract x snapshot x side)")
        ax.set_title("Edge funnel: apparent mispricings surviving each real-world cost", loc="left")
        fig.tight_layout()
        fig.savefig(fig_dir / "edge_funnel.png", dpi=150)
        plt.close(fig)


def build_report() -> str:
    run_time = utcnow()
    panel, outcomes, run_log = read_panel(), read_outcomes(), read_run_log()
    lines = [f"# Kalshi vs options: research report",
             f"_Generated {run_time:%Y-%m-%d %H:%M} UTC by `python -m kme report`. Every figure below is computed "
             f"from files in `data/`; sections without enough data say so._", ""]
    att = attention(run_log)
    if att:
        lines = ["## ⚠️ ATTENTION", *[f"- {m}" for m in att], ""] + lines

    if panel.empty:
        lines += ["No panel data yet - insufficient data. Run `python -m kme snapshot` during US market hours."]
        _write(lines)
        return "\n".join(lines)

    live = panel[panel["source"] == "live"]
    lines += ["## Data coverage",
              f"- Panel rows: {len(panel):,} ({len(live):,} live, {len(panel) - len(live):,} backfill); "
              f"rows without a synchronised Kalshi quote: {int(panel['yes_bid'].isna().sum()):,}",
              f"- Candle-replay check (candle state at fetch time == live book, live rows): {_replay(panel)}",
              f"- Snapshots: {panel['snapshot_id'].nunique():,}; events: {panel['event_ticker'].nunique():,}; "
              f"first decision {panel['decision_utc'].min()}, last {panel['decision_utc'].max()}",
              f"- Settled events with outcomes: {outcomes['event_ticker'].nunique() if len(outcomes) else 0}",
              f"- Smile model chosen: {panel.groupby('snapshot_id')['fit_method'].first().value_counts().to_dict()}",
              ""]
    for f in coverage_flags(panel):
        lines.append(f"- ⚠️ {f}")

    fr = attach_outcomes(funnel_rows(panel), outcomes)
    fsum = funnel_summary(fr)
    lines += ["## Edge funnel",
              f"Stages are cumulative (see `src/kme/edge.py`). Kalshi prices are synchronised to the option chain's "
              f"as-of time, so this measures mispricing; it is a tradeable backtest only with a real-time option feed. "
              f"Model-error tolerance = {config.MODEL_ERROR_TOL:.4f} (range contracts, same-day only). "
              f"P&L is per contract after fees, t-stat clusters by event day, shown only with >= "
              f"{config.MIN_DAYS_FOR_INFERENCE} settled event days.", "", _md(fsum), ""]
    sus = fsum[(fsum["settled_days"] >= config.MIN_DAYS_FOR_INFERENCE) & (fsum["mean_pnl"] > 0.10)]
    if len(sus):
        lines += ["### ⚠️ POSSIBLE LOOKAHEAD",
                  f"Stages {list(sus['stage'])} earn > 10 cents per contract. On liquid index ranges this is far more "
                  f"likely a timing/join bug than skill - audit decision_utc vs candle/settlement times first.", ""]

    ev = event_table(panel, outcomes)
    cmp = compare(ev)
    lines += ["## Which forecast was better? (log score on the realised range)", "```", json.dumps(cmp, indent=2,
              default=float), "```", ""]

    inputs = load_inputs(panel, outcomes)
    tk = theta_kalshi(inputs)
    tr = theta_realized(inputs)
    lines += ["## Risk premium or mispricing? (pricing-kernel tilt)",
              f"- Snapshots with a full partition + density grid: {len(inputs)}"]
    if len(tk) >= config.MIN_DAYS_FOR_INFERENCE:
        lines += [f"- theta_kalshi: median {tk['theta'].median():.2f} (IQR {tk['theta'].quantile(.25):.2f} to "
                  f"{tk['theta'].quantile(.75):.2f}); median share of the gap explained by the tilt "
                  f"{tk['explained_share'].median():.1%}"]
    else:
        lines += [f"- theta_kalshi: insufficient data (n={len(tk)}, need >= {config.MIN_DAYS_FOR_INFERENCE})"]
    lines += [f"- theta_realized: {json.dumps(tr, default=float)}", ""]

    figures(panel, fsum)
    lines += ["## Figures", "![latest](figures/latest_snapshot.png)", "", "![funnel](figures/edge_funnel.png)", ""]
    _write(lines)
    log_stage("report", "success", len(panel), "", run_time)
    return "\n".join(lines)


def _write(lines):
    config.RESULTS.mkdir(parents=True, exist_ok=True)
    (config.RESULTS / "REPORT.md").write_text("\n".join(lines) + "\n")
