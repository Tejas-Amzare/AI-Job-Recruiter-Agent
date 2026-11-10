"""
eligibility_checker.py
----------------------
Decides whether a job should proceed to scoring, and produces an
eligibility status + rejection reasons.

Checks:
  * Relevance (title/description matches target profile, not a negative title)
  * Entry-level experience eligibility (required years <= MAX_ELIGIBLE_YEARS)
  * Freshness (verified posting within SEARCH_WINDOW_HOURS)
  * Location acceptable / remote / India
"""
from __future__ import annotations

from dataclasses import dataclass

from . import config
from .models import Job
from .utils import hours_since, normalize, human_age, to_ist_string, get_logger

log = get_logger("eligibility")


@dataclass
class EligibilityResult:
    relevant: bool
    entry_level: bool
    fresh: bool
    location_ok: bool
    date_verified: bool
    status: str                 # Eligible / Not eligible / Unverified
    reasons: list[str]


def _is_relevant(job: Job) -> tuple[bool, str]:
    title = normalize(job.title)
    for neg in config.NEGATIVE_TITLE_KEYWORDS:
        if neg in title:
            return False, f"Title contains excluded term '{neg.strip()}'"
    # Title must be an actual software-engineering role, not just any mention
    # of 'java' somewhere in the body.
    if not config.title_is_software_role(job.title):
        return False, "Title is not a software-engineering/developer role"
    blob = normalize(f"{job.title} {job.description}")
    if any(k in blob for k in config.RELEVANCE_KEYWORDS):
        return True, ""
    return False, "No target keywords (java/spring/backend/software engineer) found"


def _is_entry_level(job: Job) -> tuple[bool, str]:
    if job.min_years is None:
        # No explicit requirement -> treat as potentially entry level
        return True, ""
    if job.min_years <= config.MAX_ELIGIBLE_YEARS:
        return True, ""
    # Even if min years higher, accept if JD explicitly welcomes freshers
    blob = normalize(job.description)
    if any(w in blob for w in ("fresher", "fresh graduate", "entry level",
                               "graduate trainee")):
        return True, ""
    return False, (f"Requires {job.min_years:.0f}+ years mandatory experience "
                   f"(> {config.MAX_ELIGIBLE_YEARS} yr entry-level limit)")


def _is_fresh(job: Job) -> tuple[bool, bool, str]:
    """Returns (fresh, date_verified, reason)."""
    if job.posted_at is None:
        return False, False, "Posting date could not be verified"
    age = hours_since(job.posted_at)
    job.age_hours = age
    if age is None:
        return False, False, "Posting date could not be computed"
    if age <= config.SEARCH_WINDOW_HOURS:
        return True, True, ""
    return False, True, (f"Posted {human_age(age)} ago "
                         f"(> {config.SEARCH_WINDOW_HOURS}h window)")


def _location_ok(job: Job) -> tuple[bool, str]:
    loc = normalize(job.location)
    if not loc or loc == "unknown":
        return True, ""  # don't reject on unknown location, flag later
    if config.location_is_india(job.location):
        return True, ""
    if "remote" in loc and not config.location_is_foreign(job.location):
        return True, ""  # generic remote without a foreign country tag
    if config.location_is_foreign(job.location):
        return False, (f"Location '{job.location}' is outside India "
                       f"(work authorization/visa required)")
    return False, f"Location '{job.location}' outside preferred India/remote list"


def check(job: Job) -> EligibilityResult:
    reasons: list[str] = []

    relevant, r = _is_relevant(job)
    if r:
        reasons.append(r)

    entry, r = _is_entry_level(job)
    if r:
        reasons.append(r)

    fresh, date_verified, r = _is_fresh(job)
    if r:
        reasons.append(r)

    loc_ok, r = _location_ok(job)
    if r:
        reasons.append(r)

    # Decide overall status.
    # Freshness no longer EXCLUDES a job -- it is tracked as a flag/column so
    # the report accumulates all relevant India roles over time (deduplicated).
    foreign = config.location_is_foreign(job.location)
    job.posted_within_window = ("Yes" if fresh else
                                "No" if date_verified else "Unknown")

    if not relevant or not entry or foreign:
        status = "Not eligible"
    elif not date_verified:
        status = "Unverified"
    else:
        status = "Eligible"

    # Populate standard job fields for the report.
    job.age_hours = hours_since(job.posted_at)
    job.posting_date_str = (to_ist_string(job.posted_at).split(" ")[0]
                            if job.posted_at else "Unknown")
    job.posting_time_str = (to_ist_string(job.posted_at).split(" ", 1)[1]
                            if job.posted_at else "Unknown")
    job.eligibility_status = status
    job.verification_status = (
        "Posting date verified via source API" if date_verified
        else "Posting date NOT verified"
    )

    return EligibilityResult(
        relevant=relevant, entry_level=entry, fresh=fresh,
        location_ok=loc_ok, date_verified=date_verified,
        status=status, reasons=reasons,
    )

