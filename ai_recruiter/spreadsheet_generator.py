"""
spreadsheet_generator.py
------------------------
Builds AI_Job_Research_Report.xlsx with 7 worksheets, professional formatting,
frozen headers, filters, wrapped text, clickable hyperlinks, conditional
colour-coding for match scores, and a daily summary.

Historical reports are preserved: each run also writes a timestamped copy.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from . import config
from .models import Job
from .utils import get_logger, human_age, to_ist_string, now_utc

log = get_logger("spreadsheet")

HEADERS = [
    "Rank", "Company Name", "Job Title", "Match Score", "Recommendation",
    "Posting Date", "Posting Time", "Job Age", "Location", "Work Mode",
    "Experience Required", "Employment Type", "Salary", "Job Platform",
    "Job Description Link", "Direct Apply Link", "Mandatory Matching Skills",
    "Optional Matching Skills", "Missing Mandatory Skills", "Missing Optional Skills",
    "Why I Should Apply", "Potential Rejection Reasons", "Eligibility Status",
    "Recruiter / Hiring Information", "Verification Status", "Discovered At",
    "Posted Within 24h", "Date Added", "New This Run",
]

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center")
THIN = Side(style="thin", color="D9D9D9")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# Score -> fill colour
SCORE_FILLS = [
    (85, PatternFill("solid", fgColor="C6EFCE")),   # green
    (70, PatternFill("solid", fgColor="FFF2CC")),   # yellow
    (60, PatternFill("solid", fgColor="FCE4D6")),   # orange
    (0,  PatternFill("solid", fgColor="F8CBAD")),   # red-ish
]

COL_WIDTHS = {
    "Rank": 6, "Company Name": 20, "Job Title": 30, "Match Score": 11,
    "Recommendation": 18, "Posting Date": 13, "Posting Time": 12, "Job Age": 10,
    "Location": 20, "Work Mode": 12, "Experience Required": 16,
    "Employment Type": 15, "Salary": 16, "Job Platform": 13,
    "Job Description Link": 24, "Direct Apply Link": 24,
    "Mandatory Matching Skills": 28, "Optional Matching Skills": 24,
    "Missing Mandatory Skills": 26, "Missing Optional Skills": 24,
    "Why I Should Apply": 40, "Potential Rejection Reasons": 36,
    "Eligibility Status": 15, "Recruiter / Hiring Information": 50,
    "Verification Status": 28, "Discovered At": 20,
    "Posted Within 24h": 15, "Date Added": 13, "New This Run": 12,
}


def _exp_str(job: Job) -> str:
    if job.min_years is None:
        return "Not specified"
    if job.max_years is not None:
        return f"{job.min_years:.0f}-{job.max_years:.0f} yrs"
    return f"{job.min_years:.0f}+ yrs"


def _score_fill(score: float) -> PatternFill:
    for threshold, fill in SCORE_FILLS:
        if score >= threshold:
            return fill
    return SCORE_FILLS[-1][1]


def _write_sheet(ws, jobs: list[Job], title_note: str = "") -> None:
    ws.append(HEADERS)
    for ci, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=ci)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = BORDER
        ws.column_dimensions[get_column_letter(ci)].width = COL_WIDTHS.get(header, 18)

    for rank, job in enumerate(
            sorted(jobs, key=lambda j: (j.first_seen_date or "", j.score),
                   reverse=True), start=1):
        row = [
            rank, job.company, job.title, job.score, job.recommendation,
            job.posting_date_str, job.posting_time_str, human_age(job.age_hours),
            job.location, job.work_mode, _exp_str(job), job.employment_type,
            job.salary, job.apply_platform,
            "Open JD", "Apply",
            ", ".join(job.matching_mandatory) or "-",
            ", ".join(job.matching_optional) or "-",
            ", ".join(job.missing_mandatory) or "-",
            ", ".join(job.missing_optional) or "-",
            job.why_apply, job.rejection_reasons, job.eligibility_status,
            job.recruiter_note, job.verification_status,
            to_ist_string(job.discovered_at) if job.discovered_at else "Unknown",
            job.posted_within_window, job.first_seen_date or "Unknown",
            "YES" if job.is_new else "No",
        ]
        ws.append(row)
        r = ws.max_row
        for ci in range(1, len(HEADERS) + 1):
            c = ws.cell(row=r, column=ci)
            c.alignment = WRAP
            c.border = BORDER

        # Score colour
        ws.cell(row=r, column=4).fill = _score_fill(job.score)
        ws.cell(row=r, column=4).alignment = CENTER
        ws.cell(row=r, column=4).font = Font(bold=True)

        # Highlight brand-new jobs (New This Run column + flag)
        new_cell = ws.cell(row=r, column=len(HEADERS))
        if job.is_new:
            new_fill = PatternFill("solid", fgColor="D9EAD3")
            new_cell.fill = new_fill
            new_cell.font = Font(bold=True, color="38761D")
            ws.cell(row=r, column=len(HEADERS) - 1).fill = new_fill  # Date Added

        # Hyperlinks
        jd_cell = ws.cell(row=r, column=15)
        if job.jd_url:
            jd_cell.hyperlink = job.jd_url
            jd_cell.font = Font(color="0563C1", underline="single")
        apply_cell = ws.cell(row=r, column=16)
        if job.apply_url:
            apply_cell.hyperlink = job.apply_url
            apply_cell.font = Font(color="0563C1", underline="single")

    # Freeze header + enable filter
    ws.freeze_panes = "A2"
    if ws.max_row >= 1:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{max(ws.max_row,1)}"


def _summary_sheet(ws, eligible, excellent, good, possible,
                   unverified, rejected, discovered) -> None:
    title = ws.cell(row=1, column=1, value="DAILY SUMMARY")
    title.font = Font(bold=True, size=14, color="1F4E78")

    def line(r, label, value):
        ws.cell(row=r, column=1, value=label).font = Font(bold=True)
        ws.cell(row=r, column=2, value=value)

    new_today = sum(1 for j in eligible if j.is_new)
    r = 3
    line(r, "Generated at", to_ist_string(now_utc())); r += 1
    line(r, "Search window (hours)", config.SEARCH_WINDOW_HOURS); r += 1
    line(r, "Jobs scanned this run", discovered); r += 1
    line(r, "Matched jobs in tracker (accumulated)", len(eligible)); r += 1
    line(r, "New jobs added this run", new_today); r += 1
    verified_24h = sum(1 for j in eligible if j.posted_within_window == "Yes")
    line(r, "Matched jobs posted within 24h", verified_24h); r += 1
    line(r, "Excellent matches (>=85)", len(excellent)); r += 1
    line(r, "Good matches (70-84)", len(good)); r += 1
    line(r, "Possible matches (60-69)", len(possible)); r += 1
    line(r, "Unverified jobs", len(unverified)); r += 1
    line(r, "Rejected jobs (this run)", len(rejected)); r += 2

    # Jobs by platform
    ws.cell(row=r, column=1, value="Jobs by platform").font = Font(bold=True); r += 1
    for plat, n in Counter(j.apply_platform for j in eligible).most_common():
        line(r, f"  {plat}", n); r += 1
    r += 1

    # Jobs by location
    ws.cell(row=r, column=1, value="Jobs by location").font = Font(bold=True); r += 1
    for loc, n in Counter(j.location for j in eligible).most_common(10):
        line(r, f"  {loc}", n); r += 1
    r += 1

    # Jobs by date added
    ws.cell(row=r, column=1, value="Jobs by date added").font = Font(bold=True); r += 1
    for d, n in Counter(j.first_seen_date or "Unknown" for j in eligible).most_common():
        line(r, f"  {d}", n); r += 1
    r += 1

    # Most common required skills
    ws.cell(row=r, column=1, value="Most requested skills").font = Font(bold=True); r += 1
    skill_counter = Counter()
    for j in eligible:
        skill_counter.update(j.required_skills)
    for sk, n in skill_counter.most_common(12):
        line(r, f"  {sk}", n); r += 1
    r += 1

    # Missing skills frequently requested
    ws.cell(row=r, column=1, value="Frequently-requested skills you lack").font = Font(bold=True); r += 1
    miss_counter = Counter()
    for j in eligible:
        miss_counter.update(j.missing_mandatory)
    for sk, n in miss_counter.most_common(12):
        line(r, f"  {sk}", n); r += 1

    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 40


def generate_report(eligible: list[Job], unverified: list[Job],
                    rejected: list[Job], discovered: int = 0) -> str:
    """
    `eligible` is the ACCUMULATED, de-duplicated tracker set (all matched jobs
    ever found, each stamped with its Date Added). The report grows over time
    and never repeats a job.
    """
    excellent = [j for j in eligible if j.score >= 85]
    good = [j for j in eligible if 70 <= j.score < 85]
    possible = [j for j in eligible if 60 <= j.score < 70]

    wb = Workbook()

    ws1 = wb.active
    ws1.title = "Top Matched Jobs"
    _write_sheet(ws1, [j for j in eligible if j.score >= 60])

    _write_sheet(wb.create_sheet("Excellent Matches"), excellent)
    _write_sheet(wb.create_sheet("Good Matches"), good)
    _write_sheet(wb.create_sheet("Possible Matches"), possible)
    _write_sheet(wb.create_sheet("Unverified Jobs"), unverified)
    _write_sheet(wb.create_sheet("Rejected Jobs"), rejected)
    _summary_sheet(wb.create_sheet("Daily Summary"),
                   eligible, excellent, good, possible,
                   unverified, rejected, discovered)

    main_path = config.REPORTS_DIR / config.REPORT_FILENAME
    stamp = now_utc().strftime("%Y%m%d_%H%M%S")
    try:
        wb.save(main_path)
    except PermissionError:
        # File is open in Excel / locked. Save to a fallback name instead.
        main_path = config.REPORTS_DIR / f"AI_Job_Research_Report_LATEST_{stamp}.xlsx"
        wb.save(main_path)
        log.warning("Main report was locked (open in Excel?). Saved to %s instead. "
                    "Close the open file to let future runs overwrite it.",
                    main_path.name)

    # Historical timestamped copy
    hist_path = config.REPORTS_DIR / f"AI_Job_Research_Report_{stamp}.xlsx"
    try:
        wb.save(hist_path)
    except PermissionError:
        hist_path = None

    log.info("Report written: %s%s", main_path,
             f" (and history copy {hist_path.name})" if hist_path else "")
    return str(main_path)

