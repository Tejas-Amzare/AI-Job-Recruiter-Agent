"""Shared helpers: logging, HTTP session, text utilities, timestamps."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import config

_IST_OFFSET_HOURS = 5.5


def get_logger(name: str = "ai_recruiter") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(config.LOGS_DIR / "ai_recruiter.log", encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


log = get_logger()


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT, "Accept": "application/json"})
    return s


def polite_get(session: requests.Session, url: str, **kwargs):
    """GET with timeout + a short politeness delay. Returns response or None."""
    try:
        resp = session.get(url, timeout=config.REQUEST_TIMEOUT, **kwargs)
        time.sleep(config.REQUEST_DELAY)
        if resp.status_code == 200:
            return resp
        log.debug("GET %s -> HTTP %s", url, resp.status_code)
    except requests.RequestException as exc:
        log.debug("GET %s failed: %s", url, exc)
    return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_ist_string(dt: datetime) -> str:
    """Return 'YYYY-MM-DD HH:MM IST' for display."""
    if dt is None:
        return "Unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist = dt.astimezone(timezone.utc)
    # shift to IST manually to avoid tz database dependency
    from datetime import timedelta
    ist = ist + timedelta(hours=_IST_OFFSET_HOURS)
    return ist.strftime("%Y-%m-%d %H:%M IST")


def hours_since(dt: datetime) -> float | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now_utc() - dt
    return round(delta.total_seconds() / 3600.0, 1)


def human_age(hours: float | None) -> str:
    if hours is None:
        return "Unknown"
    if hours < 1:
        return f"{int(hours * 60)} min"
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


_WS = re.compile(r"\s+")
_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = _HTML_TAG.sub(" ", text)
    # decode a few common entities without a full parser
    for a, b in (("&amp;", "&"), ("&nbsp;", " "), ("&lt;", "<"),
                 ("&gt;", ">"), ("&#39;", "'"), ("&quot;", '"')):
        text = text.replace(a, b)
    return _WS.sub(" ", text).strip()


def normalize(text: str) -> str:
    return _WS.sub(" ", (text or "").lower()).strip()

