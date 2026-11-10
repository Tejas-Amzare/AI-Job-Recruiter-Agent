"""
job_source_connectors.py
------------------------
Connectors for REAL, legitimately-accessible job sources.

We use the PUBLIC JSON job-board APIs of Greenhouse, Lever and Ashby. These
endpoints are published by the vendors for public consumption, require no
authentication, and do not involve bypassing CAPTCHAs or logins.

Each connector yields Job objects with a *verified* posting timestamp where the
API provides one, so the strict 24h filter can be applied downstream.

A pluggable WebSearchConnector stub is included for optional integration with a
permitted search API (e.g. SerpAPI / Google Programmable Search). It is disabled
unless an API key is configured, and it never fabricates results.
"""
from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as dtparse

from . import config
from .models import Job
from .utils import get_logger, make_session, polite_get, strip_html, now_utc

log = get_logger("connectors")


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            # Lever/Ashby use epoch millis
            if value > 1e12:
                value = value / 1000.0
            return datetime.fromtimestamp(value, tz=timezone.utc)
        dt = dtparse.parse(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, OverflowError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Greenhouse  -- https://boards-api.greenhouse.io/v1/boards/<token>/jobs
# --------------------------------------------------------------------------- #
class GreenhouseConnector:
    name = "greenhouse"

    def __init__(self, session=None):
        self.session = session or make_session()

    def fetch(self, board_token: str) -> list[Job]:
        url = (f"https://boards-api.greenhouse.io/v1/boards/"
               f"{board_token}/jobs?content=true")
        resp = polite_get(self.session, url)
        if not resp:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []
        jobs: list[Job] = []
        for item in data.get("jobs", []):
            posted = _parse_dt(item.get("first_published") or item.get("updated_at"))
            updated = _parse_dt(item.get("updated_at"))
            loc = (item.get("location") or {}).get("name", "Unknown")
            jobs.append(Job(
                source=self.name,
                company=board_token.replace("-", " ").title(),
                title=item.get("title", "Unknown"),
                location=loc or "Unknown",
                posted_at=posted,
                updated_at=updated,
                jd_url=item.get("absolute_url", ""),
                apply_url=item.get("absolute_url", ""),
                apply_platform="Greenhouse",
                description=strip_html(item.get("content", "")),
                date_verification="Greenhouse API first_published",
                discovered_at=now_utc(),
            ))
        log.info("Greenhouse[%s]: %d jobs", board_token, len(jobs))
        return jobs


# --------------------------------------------------------------------------- #
# Lever  -- https://api.lever.co/v0/postings/<token>?mode=json
# --------------------------------------------------------------------------- #
class LeverConnector:
    name = "lever"

    def __init__(self, session=None):
        self.session = session or make_session()

    def fetch(self, board_token: str) -> list[Job]:
        url = f"https://api.lever.co/v0/postings/{board_token}?mode=json"
        resp = polite_get(self.session, url)
        if not resp:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []
        jobs: list[Job] = []
        for item in data:
            posted = _parse_dt(item.get("createdAt"))
            cats = item.get("categories", {}) or {}
            desc = strip_html(item.get("descriptionPlain") or item.get("description", ""))
            lists = item.get("lists", []) or []
            extra = " ".join(strip_html(l.get("content", "")) for l in lists)
            jobs.append(Job(
                source=self.name,
                company=board_token.replace("-", " ").title(),
                title=item.get("text", "Unknown"),
                location=cats.get("location", "Unknown") or "Unknown",
                employment_type=cats.get("commitment", "Unknown") or "Unknown",
                work_mode=cats.get("workplaceType", "Unknown") or "Unknown",
                posted_at=posted,
                updated_at=posted,
                jd_url=item.get("hostedUrl", ""),
                apply_url=item.get("applyUrl") or item.get("hostedUrl", ""),
                apply_platform="Lever",
                description=(desc + " " + extra).strip(),
                date_verification="Lever API createdAt",
                discovered_at=now_utc(),
            ))
        log.info("Lever[%s]: %d jobs", board_token, len(jobs))
        return jobs


# --------------------------------------------------------------------------- #
# Ashby  -- https://api.ashbyhq.com/posting-api/job-board/<token>
# --------------------------------------------------------------------------- #
class AshbyConnector:
    name = "ashby"

    def __init__(self, session=None):
        self.session = session or make_session()

    def fetch(self, board_token: str) -> list[Job]:
        url = (f"https://api.ashbyhq.com/posting-api/job-board/"
               f"{board_token}?includeCompensation=true")
        resp = polite_get(self.session, url)
        if not resp:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []
        jobs: list[Job] = []
        for item in data.get("jobs", []):
            posted = _parse_dt(item.get("publishedAt") or item.get("updatedAt"))
            comp = item.get("compensation") or {}
            salary = "Unknown"
            summary = comp.get("compensationTierSummary")
            if summary:
                salary = summary
            jobs.append(Job(
                source=self.name,
                company=item.get("organizationName")
                or board_token.replace("-", " ").title(),
                title=item.get("title", "Unknown"),
                location=item.get("location", "Unknown") or "Unknown",
                employment_type=item.get("employmentType", "Unknown") or "Unknown",
                work_mode="Remote" if item.get("isRemote") else "On-site",
                salary=salary,
                posted_at=posted,
                updated_at=_parse_dt(item.get("updatedAt")),
                jd_url=item.get("jobUrl", ""),
                apply_url=item.get("applyUrl") or item.get("jobUrl", ""),
                apply_platform="Ashby",
                description=strip_html(item.get("descriptionPlain")
                                       or item.get("descriptionHtml", "")),
                date_verification="Ashby API publishedAt",
                discovered_at=now_utc(),
            ))
        log.info("Ashby[%s]: %d jobs", board_token, len(jobs))
        return jobs


# --------------------------------------------------------------------------- #
# Optional web search connector (disabled unless a permitted API key is set).
# --------------------------------------------------------------------------- #
class WebSearchConnector:
    """
    Pluggable connector for a *permitted* search API such as SerpAPI or Google
    Programmable Search Engine. It is intentionally inert unless configured,
    and it NEVER fabricates jobs -- it only surfaces real result URLs that are
    then parsed by job_description_parser.

    Set env var SERPAPI_KEY to enable.
    """
    name = "websearch"

    def __init__(self, session=None):
        import os
        self.api_key = os.getenv("SERPAPI_KEY", "")
        self.session = session or make_session()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def search_urls(self, query: str) -> list[str]:
        if not self.enabled:
            return []
        url = "https://serpapi.com/search.json"
        params = {"engine": "google", "q": query, "api_key": self.api_key,
                  "num": 20, "tbs": "qdr:d"}  # qdr:d = past 24h
        resp = polite_get(self.session, url, params=params)
        if not resp:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []
        return [r.get("link") for r in data.get("organic_results", [])
                if r.get("link")]


def collect_all_jobs() -> list[Job]:
    """Run every configured connector and return the combined raw job list."""
    session = make_session()
    all_jobs: list[Job] = []

    gh = GreenhouseConnector(session)
    for token in config.GREENHOUSE_BOARDS:
        all_jobs.extend(gh.fetch(token))

    lv = LeverConnector(session)
    for token in config.LEVER_BOARDS:
        all_jobs.extend(lv.fetch(token))

    ab = AshbyConnector(session)
    for token in config.ASHBY_BOARDS:
        all_jobs.extend(ab.fetch(token))

    ws = WebSearchConnector(session)
    if ws.enabled:
        log.info("Web search connector enabled.")
        # URLs would be handed to job_description_parser; left as integration hook.
    else:
        log.info("Web search connector disabled (no SERPAPI_KEY). "
                 "Using public ATS boards only.")

    log.info("Collected %d raw jobs from all sources.", len(all_jobs))
    return all_jobs

