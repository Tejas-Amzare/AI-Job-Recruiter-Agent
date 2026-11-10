"""
daily_report.py
---------------
High-level entry that runs the pipeline once, writes the spreadsheet, prints
the top-N jobs, a coverage summary, and optionally emails excellent matches.
"""
from __future__ import annotations

import smtplib
from email.mime.text import MIMEText

from . import config
from .resume_analyzer import analyze_resume, profile_summary
from .job_search_engine import run_pipeline
from .spreadsheet_generator import generate_report
from .utils import get_logger, human_age

log = get_logger("daily_report")


def _notify_excellent(excellent):
    if not excellent:
        return
    if not (config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASSWORD):
        log.info("Email not configured; skipping notification for %d excellent matches.",
                 len(excellent))
        return
    body_lines = [f"{j.score:.0f} | {j.company} - {j.title}\n{j.apply_url}"
                  for j in excellent]
    msg = MIMEText("New excellent matches:\n\n" + "\n\n".join(body_lines))
    msg["Subject"] = f"[AI Recruiter] {len(excellent)} new excellent job match(es)"
    msg["From"] = config.SMTP_USER
    msg["To"] = config.NOTIFY_EMAIL
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
            s.starttls()
            s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        log.info("Sent notification email to %s", config.NOTIFY_EMAIL)
    except Exception as exc:  # pragma: no cover
        log.warning("Email notification failed: %s", exc)


def print_top(jobs, n=config.TOP_N_DISPLAY):
    ranked = sorted(jobs, key=lambda j: -j.score)[:n]
    print("\n" + "=" * 100)
    print(f"TOP {len(ranked)} SUITABLE JOBS (score-ranked)")
    print("=" * 100)
    if not ranked:
        print("No eligible jobs scored >= 60 in this run "
              "(see report's Unverified/Rejected sheets and the note below).")
    for i, j in enumerate(ranked, 1):
        print(f"\n#{i}  [{j.score:.0f} | {j.recommendation}]  {j.title} @ {j.company}")
        print(f"    Location: {j.location} | Mode: {j.work_mode} | "
              f"Exp: {j.min_years if j.min_years is not None else 'n/a'} | "
              f"Posted: {j.posting_date_str} {j.posting_time_str} "
              f"({human_age(j.age_hours)} ago)")
        print(f"    Apply: {j.apply_url}")
        print(f"    Why: {j.why_apply}")
        if j.missing_mandatory:
            print(f"    Missing(mandatory): {', '.join(j.missing_mandatory)}")
    print("=" * 100)


def run_once(resume_path: str | None = None) -> str:
    log.info("=== AI Recruiter run starting ===")
    profile = analyze_resume(resume_path)
    print(profile_summary(profile))

    accumulated, new_jobs, unverified, rejected, discovered = run_pipeline(profile)

    report_path = generate_report(accumulated, unverified, rejected, discovered)

    excellent = [j for j in accumulated if j.score >= 85]
    print_top(accumulated)

    print("\nNEW JOBS ADDED THIS RUN (not seen before): "
          f"{len(new_jobs)}")
    for j in sorted(new_jobs, key=lambda x: -x.score)[:15]:
        print(f"  + [{j.score:.0f}] {j.title} @ {j.company} "
              f"({j.location}) | added {j.first_seen_date}")
        print(f"      Apply: {j.apply_url}")

    print("\nSEARCH COVERAGE & VERIFICATION SUMMARY")
    print("-" * 60)
    print(f"Jobs scanned this run (public ATS boards): {discovered}")
    print(f"Matched jobs in tracker (accumulated, de-duplicated): {len(accumulated)}")
    print(f"  - New this run:     {len(new_jobs)}")
    print(f"  - Excellent (>=85): {len(excellent)}")
    print(f"  - Good (70-84):     {sum(1 for j in accumulated if 70 <= j.score < 85)}")
    print(f"  - Possible (60-69): {sum(1 for j in accumulated if 60 <= j.score < 70)}")
    print(f"Unverified date: {len(unverified)}  |  Rejected this run: {len(rejected)}")
    print(f"\nExcel report: {report_path}")

    _notify_excellent([j for j in new_jobs if j.score >= config.NOTIFY_SCORE_THRESHOLD])
    log.info("=== AI Recruiter run complete ===")
    return report_path

