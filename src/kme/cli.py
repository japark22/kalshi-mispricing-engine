"""Command line: python -m kme {snapshot,settle,report,backfill,smoke}."""
from __future__ import annotations

import argparse
import json
import sys


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kme")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot", help="one live point-in-time snapshot (run during US market hours)")
    sub.add_parser("settle", help="join Kalshi settlement outcomes for past events")
    sub.add_parser("report", help="rebuild results/REPORT.md and figures")
    b = sub.add_parser("backfill", help="historical rows from EOD option files + Kalshi candles")
    b.add_argument("files", nargs="+")
    b.add_argument("--series", default="KXINX")
    sub.add_parser("smoke", help="check that both public endpoints answer and parse")
    a = ap.parse_args(argv)

    if a.cmd == "snapshot":
        from .snapshot import run_snapshot
        out = run_snapshot()
    elif a.cmd == "settle":
        from .settle import settle_pending
        out = settle_pending()
    elif a.cmd == "report":
        from .report import build_report
        build_report()
        out = {"report": "results/REPORT.md"}
    elif a.cmd == "backfill":
        from .backfill import backfill_file
        out = {f: backfill_file(f, series=a.series) for f in a.files}
    else:
        from .smoke import smoke
        out = smoke()
    print(json.dumps(out, indent=2, default=str))
    if isinstance(out, dict) and out.get("status") == "failed":
        sys.exit(1)
    if a.cmd == "smoke":
        broken = [k for k, v in out.items() if isinstance(v, dict) and not v.get("ok", True)]
        if broken:
            print(f"smoke failed for: {broken}", file=sys.stderr)
            sys.exit(1)
