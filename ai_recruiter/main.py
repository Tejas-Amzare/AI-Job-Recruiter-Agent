"""
main.py
-------
Command-line entry point for the AI Recruiter.

Examples:
    python -m ai_recruiter.main                 # analyze resume + run once
    python -m ai_recruiter.main --resume cv.pdf # use a specific resume
    python -m ai_recruiter.main --profile-only  # just show candidate profile
    python -m ai_recruiter.main --window 48     # widen freshness window to 48h
"""
from __future__ import annotations

import argparse
import sys

from . import config
from .utils import get_logger

log = get_logger("main")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="AI Recruiter - automatic job discovery, resume matching & reporting")
    ap.add_argument("--resume", help="Path to resume (PDF/DOCX/TXT).")
    ap.add_argument("--window", type=int,
                    help="Freshness window in hours (default 24).")
    ap.add_argument("--profile-only", action="store_true",
                    help="Only analyze the resume and print the profile.")
    args = ap.parse_args(argv)

    if args.window:
        config.SEARCH_WINDOW_HOURS = args.window

    if args.profile_only:
        from .resume_analyzer import analyze_resume, profile_summary
        print(profile_summary(analyze_resume(args.resume)))
        return 0

    from .daily_report import run_once
    try:
        run_once(args.resume)
    except FileNotFoundError as exc:
        log.error(str(exc))
        print(f"\nERROR: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

