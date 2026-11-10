"""
storage.py
----------
SQLite-backed persistent job tracker.

Guarantees:
  * Once a job is added it is stored forever (preserved history).
  * A job is NEVER duplicated across runs/days -- dedup_key is the primary key.
  * Each job keeps the DATE it was first discovered (first_seen).
  * Each run only ADDS jobs it has never seen before; existing jobs keep their
    original discovery date.
"""
from __future__ import annotations

import sqlite3

from . import config
from .models import Job
from .utils import get_logger, now_utc

log = get_logger("storage")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    dedup_key   TEXT PRIMARY KEY,
    company     TEXT,
    title       TEXT,
    location    TEXT,
    score       REAL,
    first_seen  TEXT,
    last_seen   TEXT,
    data        TEXT
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def upsert_jobs(jobs: list[Job]) -> list[Job]:
    """
    Insert jobs that have never been seen before; update last_seen for ones we
    already have. Returns the list of jobs that are NEW this run.
    """
    conn = _connect()
    now = now_utc().isoformat()
    today = now_utc().strftime("%Y-%m-%d")
    new_jobs: list[Job] = []

    with conn:
        for j in jobs:
            if not j.dedup_key:
                continue
            row = conn.execute(
                "SELECT first_seen FROM jobs WHERE dedup_key=?", (j.dedup_key,)
            ).fetchone()
            if row is None:
                j.first_seen_date = today
                j.is_new = True
                conn.execute(
                    "INSERT INTO jobs "
                    "(dedup_key, company, title, location, score, first_seen, "
                    " last_seen, data) VALUES (?,?,?,?,?,?,?,?)",
                    (j.dedup_key, j.company, j.title, j.location, j.score,
                     now, now, j.to_json()),
                )
                new_jobs.append(j)
            else:
                conn.execute(
                    "UPDATE jobs SET last_seen=?, score=?, data=? WHERE dedup_key=?",
                    (now, j.score, j.to_json(), j.dedup_key),
                )
    conn.close()
    log.info("Tracker updated: %d new job(s) added, %d total submitted.",
             len(new_jobs), len(jobs))
    return new_jobs


def load_all_jobs() -> list[Job]:
    """Rebuild every accumulated job from the history DB for reporting."""
    conn = _connect()
    rows = conn.execute(
        "SELECT first_seen, data FROM jobs ORDER BY first_seen DESC, score DESC"
    ).fetchall()
    conn.close()
    jobs: list[Job] = []
    for first_seen, data in rows:
        try:
            job = Job.from_json(data)
        except Exception:
            continue
        job.first_seen_date = (first_seen or "")[:10]
        job.is_new = False
        jobs.append(job)
    return jobs
