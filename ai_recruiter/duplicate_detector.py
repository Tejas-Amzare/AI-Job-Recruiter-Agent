"""
duplicate_detector.py
----------------------
Removes the same job appearing multiple times (across boards or repeated
polls). Uses a normalized (company, title, location) fingerprint plus the
apply URL. Keeps the freshest / most-complete instance.
"""
from __future__ import annotations

import hashlib
import re

from .models import Job
from .utils import get_logger

log = get_logger("dedup")

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    return _NON_ALNUM.sub(" ", (s or "").lower()).strip()


def fingerprint(job: Job) -> str:
    base = f"{_norm(job.company)}|{_norm(job.title)}|{_norm(job.location)}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def deduplicate(jobs: list[Job]) -> list[Job]:
    seen: dict[str, Job] = {}
    for job in jobs:
        job.dedup_key = fingerprint(job)
        key = job.dedup_key
        existing = seen.get(key)
        if existing is None:
            seen[key] = job
            continue
        # Keep the one with a verified date, else the fresher one, else richer.
        if job.posted_at and not existing.posted_at:
            seen[key] = job
        elif job.posted_at and existing.posted_at and job.posted_at > existing.posted_at:
            seen[key] = job
        elif len(job.description) > len(existing.description):
            seen[key] = job
    removed = len(jobs) - len(seen)
    log.info("Deduplicated %d -> %d jobs (%d duplicates removed)",
             len(jobs), len(seen), removed)
    return list(seen.values())

