"""
scheduler.py
------------
Optional daily automated execution. Does nothing unless the user explicitly
runs it (per the spec: "Do not create a schedule until the user explicitly
configures it").

Usage:
    python -m ai_recruiter.scheduler --time 09:00
"""
from __future__ import annotations

import argparse
import time

from .utils import get_logger

log = get_logger("scheduler")


def start(run_time: str = "09:00"):
    try:
        import schedule
    except ImportError:
        raise SystemExit("Install the 'schedule' package: pip install schedule")

    from .daily_report import run_once

    schedule.every().day.at(run_time).do(run_once)
    log.info("Scheduler started. Daily run at %s. Ctrl+C to stop.", run_time)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="AI Recruiter daily scheduler")
    ap.add_argument("--time", default="09:00",
                    help="Daily run time, 24h HH:MM (local).")
    args = ap.parse_args()
    start(args.time)

