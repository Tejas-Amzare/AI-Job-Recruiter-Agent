"""
job_search_engine.py
--------------------
Orchestrates the full pipeline:

  collect -> parse -> eligibility -> dedup -> score -> verify links -> bucket

Returns (all_jobs, eligible, unverified, rejected) ready for reporting.
"""
from __future__ import annotations

from .models import Job
from .resume_analyzer import CandidateProfile
from . import job_source_connectors as connectors
from . import job_description_parser as jdp
from . import eligibility_checker as elig
from . import duplicate_detector as dedup
from . import job_matcher as matcher
from . import application_link_verifier as linkver
from . import storage
from .utils import get_logger, make_session

log = get_logger("engine")


def run_pipeline(profile: CandidateProfile):
    # 1. Collect real jobs from public ATS boards
    raw = connectors.collect_all_jobs()

    # 2. Parse requirements
    for job in raw:
        jdp.parse_job(job)

    # 3. Deduplicate
    unique = dedup.deduplicate(raw)

    # 4. Eligibility + bucket
    eligible: list[Job] = []
    unverified: list[Job] = []
    rejected: list[Job] = []

    for job in unique:
        result = elig.check(job)
        if result.status == "Eligible":
            eligible.append(job)
        elif result.status == "Unverified":
            unverified.append(job)
            job.rejection_reasons = "; ".join(result.reasons)
        else:
            job.rejection_reasons = "; ".join(result.reasons) or "Not a fit"
            rejected.append(job)

    log.info("Eligible: %d | Unverified: %d | Rejected: %d",
             len(eligible), len(unverified), len(rejected))

    # 5. Score eligible + unverified (so user sees scores even if date unsure)
    for job in eligible + unverified:
        matcher.score_job(job, profile)

    # Re-bucket: an eligible job scoring < 50 moves to rejected
    still_eligible = []
    for job in eligible:
        if job.score < 50:
            job.rejection_reasons = (job.rejection_reasons
                                     or "Match score below 50 (not recommended).")
            rejected.append(job)
        else:
            still_eligible.append(job)
    eligible = still_eligible

    # 6. Verify apply links for the jobs we will recommend
    session = make_session()
    for job in [j for j in eligible if j.score >= 60]:
        linkver.verify(job, session)

    # 7. Persist to the tracker: only NEW jobs are added; existing ones are
    #    never duplicated and keep their original discovery date.
    new_jobs = storage.upsert_jobs(eligible)
    new_keys = {j.dedup_key for j in new_jobs}

    # 8. Build the report set from the ACCUMULATED tracker (all jobs ever
    #    found), so the sheet grows day by day and never repeats a job.
    accumulated = storage.load_all_jobs()
    for job in accumulated:
        job.is_new = job.dedup_key in new_keys
    # Keep only meaningful matches in the accumulated report set.
    accumulated = [j for j in accumulated if j.score >= 50]
    accumulated.sort(key=lambda j: (j.first_seen_date, j.score), reverse=True)

    log.info("Accumulated tracker now holds %d matched jobs (%d new today).",
             len(accumulated), len(new_jobs))

    return accumulated, new_jobs, unverified, rejected, len(unique)

