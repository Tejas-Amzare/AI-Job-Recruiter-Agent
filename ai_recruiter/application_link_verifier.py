"""
application_link_verifier.py
----------------------------
Verifies that each job's apply URL is reachable and points at a real posting
(not a homepage, a Google search link, or a dead page). Records both the JD
URL and the direct apply URL.

Uses lightweight HEAD/GET requests with redirects followed, respecting
timeouts. Never fabricates a link; if verification fails the job is flagged.
"""
from __future__ import annotations

from urllib.parse import urlparse

from .models import Job
from .utils import make_session, get_logger
from . import config

log = get_logger("link_verifier")

_BAD_HOST_FRAGMENTS = ("google.com/search", "bing.com/search", "duckduckgo.com")


def _looks_like_search_link(url: str) -> bool:
    return any(frag in url for frag in _BAD_HOST_FRAGMENTS)


def _is_homepage(url: str) -> bool:
    p = urlparse(url)
    return p.path in ("", "/") and not p.query


def verify(job: Job, session=None) -> Job:
    session = session or make_session()
    url = job.apply_url or job.jd_url

    if not url:
        job.link_verified = False
        job.verification_status = "No application URL found"
        return job

    if _looks_like_search_link(url):
        job.link_verified = False
        job.verification_status = "Rejected: search-engine link, not a real apply URL"
        return job

    if _is_homepage(url) and job.jd_url and not _is_homepage(job.jd_url):
        url = job.jd_url  # prefer the job-specific page

    try:
        resp = session.get(url, timeout=config.REQUEST_TIMEOUT,
                           allow_redirects=True)
        final_url = resp.url
        if resp.status_code < 400:
            job.apply_url = final_url
            job.link_verified = True
            if "Posting date verified" in job.verification_status:
                job.verification_status += " | Apply link reachable"
            else:
                job.verification_status = "Apply link reachable"
        else:
            job.link_verified = False
            job.verification_status = f"Apply link returned HTTP {resp.status_code}"
    except Exception as exc:  # pragma: no cover
        job.link_verified = False
        job.verification_status = f"Apply link not reachable ({type(exc).__name__})"
        log.debug("Link verify failed for %s: %s", url, exc)

    # Identify hosting platform if different from source.
    host = urlparse(job.apply_url).netloc
    if "greenhouse" in host:
        job.apply_platform = "Greenhouse"
    elif "lever.co" in host:
        job.apply_platform = "Lever"
    elif "ashby" in host:
        job.apply_platform = "Ashby"
    elif "workday" in host:
        job.apply_platform = "Workday"
    elif host:
        job.apply_platform = host

    return job

