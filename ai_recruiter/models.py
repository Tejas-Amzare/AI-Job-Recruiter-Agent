"""Shared Job data model used across the pipeline."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from dateutil import parser as _dtparse


@dataclass
class Job:
    # Identity / source
    source: str = "Unknown"            # greenhouse / lever / ashby / websearch
    company: str = "Unknown"
    title: str = "Unknown"
    location: str = "Unknown"
    work_mode: str = "Unknown"         # Remote / On-site / Hybrid / Unknown
    employment_type: str = "Unknown"
    salary: str = "Unknown"

    # Dates
    posted_at: datetime | None = None  # verified posting timestamp (UTC)
    updated_at: datetime | None = None
    posting_date_str: str = "Unknown"
    posting_time_str: str = "Unknown"
    age_hours: float | None = None
    date_verification: str = "Unknown"

    # Links
    jd_url: str = ""                   # job description page
    apply_url: str = ""                # direct application link
    apply_platform: str = "Unknown"
    link_verified: bool = False

    # Content
    description: str = ""
    requirements_text: str = ""

    # Parsed requirements
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    min_years: float | None = None
    max_years: float | None = None
    grad_years: list[int] = field(default_factory=list)

    # Scoring / evaluation
    score: float = 0.0
    recommendation: str = "Unknown"
    eligibility_status: str = "Unknown"
    matching_mandatory: list[str] = field(default_factory=list)
    matching_optional: list[str] = field(default_factory=list)
    missing_mandatory: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    why_apply: str = ""
    rejection_reasons: str = ""
    recruiter_note: str = ""
    verification_status: str = "Unknown"
    score_breakdown: dict = field(default_factory=dict)

    # Bookkeeping
    discovered_at: datetime | None = None
    dedup_key: str = ""

    # Persistent-tracker fields
    first_seen_date: str = ""       # date the job first entered the tracker
    is_new: bool = False            # discovered for the first time this run
    posted_within_window: str = "Unknown"   # Yes / No / Unknown

    def to_row(self) -> dict:
        return asdict(self)

    # ----- JSON (de)serialization for the history DB -----
    _DT_FIELDS = ("posted_at", "updated_at", "discovered_at")

    def to_json(self) -> str:
        d = asdict(self)
        for f in self._DT_FIELDS:
            d[f] = d[f].isoformat() if isinstance(d[f], datetime) else None
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, blob: str) -> "Job":
        d = json.loads(blob)
        for f in cls._DT_FIELDS:
            val = d.get(f)
            if val:
                try:
                    d[f] = _dtparse.parse(val)
                except (ValueError, TypeError):
                    d[f] = None
            else:
                d[f] = None
        # Drop any unexpected keys to stay compatible across versions.
        valid = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**valid)

