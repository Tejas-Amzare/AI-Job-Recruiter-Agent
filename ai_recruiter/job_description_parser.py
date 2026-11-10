"""
job_description_parser.py
-------------------------
Parses a raw job description into structured requirements:
  * required vs preferred skills
  * min/max years of experience
  * eligible graduation years
  * work mode / employment type / salary hints

Pure text analysis -- no external calls. An optional LLM refinement hook is
available but off by default.
"""
from __future__ import annotations

import re

from .models import Job
from .resume_analyzer import SKILL_ALIASES
from .utils import normalize, get_logger

log = get_logger("jd_parser")

# Experience patterns like "0-2 years", "1 to 3 years", "2+ years", "minimum 3 years"
_RANGE_RE = re.compile(r"(\d{1,2})\s*(?:-|to|–|—)\s*(\d{1,2})\s*\+?\s*year")
_PLUS_RE = re.compile(r"(\d{1,2})\s*\+\s*year")
_MIN_RE = re.compile(r"(?:minimum|min|at least|atleast)\s*(?:of\s*)?(\d{1,2})\s*year")
_SINGLE_RE = re.compile(r"(\d{1,2})\s*year")
_GRAD_RE = re.compile(r"(20\d{2})\s*(?:/|,|and|&|-|–)?\s*(20\d{2})?\s*(?:batch|pass|graduat)")

_FRESHER_WORDS = ("fresher", "fresh graduate", "no prior experience",
                  "0 year", "entry level", "entry-level", "graduate trainee")

# Sections that usually hold mandatory vs nice-to-have skills
_PREFERRED_MARKERS = ("preferred", "nice to have", "good to have", "bonus",
                      "plus", "advantageous", "desirable")
_REQUIRED_MARKERS = ("required", "must have", "must-have", "requirements",
                     "qualifications", "you have", "what you'll need",
                     "what we are looking for", "responsibilities")


def _skills_in(text: str) -> set[str]:
    low = normalize(text)
    found = set()
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if alias.strip() in low:
                found.add(canonical)
                break
    return found


def _split_required_preferred(text: str) -> tuple[set[str], set[str]]:
    """Heuristically split skills into required vs preferred using line context."""
    required: set[str] = set()
    preferred: set[str] = set()
    current = "required"
    for line in text.splitlines():
        low = line.lower()
        if any(m in low for m in _PREFERRED_MARKERS):
            current = "preferred"
        elif any(m in low for m in _REQUIRED_MARKERS):
            current = "required"
        line_skills = _skills_in(line)
        if current == "preferred":
            preferred |= line_skills
        else:
            required |= line_skills
    # Anything not explicitly preferred but present overall counts as required.
    all_skills = _skills_in(text)
    required |= (all_skills - preferred)
    preferred -= required
    return required, preferred


def _extract_experience(text: str) -> tuple[float | None, float | None]:
    low = normalize(text)
    if any(w in low for w in _FRESHER_WORDS):
        # fresher-friendly; still check for an explicit upper bound
        m = _RANGE_RE.search(low)
        if m:
            return float(m.group(1)), float(m.group(2))
        return 0.0, None
    m = _RANGE_RE.search(low)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = _MIN_RE.search(low)
    if m:
        return float(m.group(1)), None
    m = _PLUS_RE.search(low)
    if m:
        return float(m.group(1)), None
    m = _SINGLE_RE.search(low)
    if m:
        return float(m.group(1)), float(m.group(1))
    return None, None


def _extract_grad_years(text: str) -> list[int]:
    years: set[int] = set()
    for m in re.finditer(r"(20\d{2})\s*(?:batch|pass out|passout|passing|graduat)", text.lower()):
        years.add(int(m.group(1)))
    return sorted(years)


def _work_mode(text: str, existing: str) -> str:
    low = text.lower()
    if existing and existing not in ("Unknown", ""):
        return existing
    if "hybrid" in low:
        return "Hybrid"
    if "remote" in low:
        return "Remote"
    if "on-site" in low or "onsite" in low or "in office" in low:
        return "On-site"
    return "Unknown"


def _employment_type(text: str, existing: str) -> str:
    low = text.lower()
    if existing and existing not in ("Unknown", ""):
        return existing
    if "intern" in low:
        return "Internship"
    if "contract" in low:
        return "Contract"
    if "full-time" in low or "full time" in low:
        return "Full-time"
    return "Unknown"


def parse_job(job: Job) -> Job:
    text = " \n".join(filter(None, [job.title, job.description,
                                    job.requirements_text]))
    required, preferred = _split_required_preferred(text)
    job.required_skills = sorted(required)
    job.preferred_skills = sorted(preferred)
    job.min_years, job.max_years = _extract_experience(text)
    job.grad_years = _extract_grad_years(text)
    job.work_mode = _work_mode(text, job.work_mode)
    job.employment_type = _employment_type(text, job.employment_type)
    return job

