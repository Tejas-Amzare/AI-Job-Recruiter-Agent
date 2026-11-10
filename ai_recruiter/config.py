"""
Central configuration for the AI Recruiter automation.

Everything that controls search behaviour, scoring, locations and the
company ATS boards that are polled for real jobs lives here.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "job_history.sqlite3"
RESUME_PATH = DATA_DIR / "resume.txt"   # also accepts .pdf / .docx

for _d in (DATA_DIR, REPORTS_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

REPORT_FILENAME = "AI_Job_Research_Report.xlsx"

# --------------------------------------------------------------------------- #
# Search window
# --------------------------------------------------------------------------- #
# Only jobs whose VERIFIED posting timestamp is within this many hours are
# treated as "fresh". Configurable per the master spec.
SEARCH_WINDOW_HOURS = int(os.getenv("SEARCH_WINDOW_HOURS", "24"))

# How many jobs to print to the console at the end.
TOP_N_DISPLAY = 20

# --------------------------------------------------------------------------- #
# Target job profile (initial configuration from the master prompt)
# --------------------------------------------------------------------------- #
TARGET_TITLES = [
    "Java Developer",
    "Java Backend Developer",
    "Spring Boot Developer",
    "Junior Java Developer",
    "Junior Backend Engineer",
    "Software Engineer",
    "Software Developer",
    "Associate Software Engineer",
    "Graduate Software Engineer",
    "Backend Software Engineer",
    "Application Developer",
    "Software Development Engineer",
    "Trainee Software Engineer",
    "Graduate Engineer Trainee",
    "Software Engineer Intern",
    "Backend Developer Intern",
]

# Keywords that make a posting *relevant* (any match). Lower-cased.
RELEVANCE_KEYWORDS = [
    "java", "spring", "spring boot", "backend", "back end", "back-end",
    "software engineer", "software developer", "sde", "rest api", "microservice",
    "application developer", "associate engineer", "graduate engineer",
]

# A posting's TITLE must contain at least one of these to be considered a
# software-engineering role (prevents non-dev "engineer"/"associate" titles
# such as Sourcer, Coordinator, RTL Design Engineer, Legal Associate).
POSITIVE_TITLE_KEYWORDS = [
    "software engineer", "software developer", "backend", "back end", "back-end",
    "java", "full stack", "full-stack", "fullstack", "sde",
    "software development", "application developer", "web developer",
    "api engineer", "platform engineer", "server", "programmer",
    "graduate engineer", "engineer trainee", "trainee software",
]

# Location gating: a role must be in India / India-remote to be eligible,
# otherwise work-authorization/visa makes it impractical.
INDIA_MARKERS = [
    "india", "pune", "hyderabad", "mumbai", "bengaluru", "bangalore",
    "chennai", "delhi", "gurgaon", "gurugram", "noida", "kolkata",
    "ahmedabad", "indore", "coimbatore", "trivandrum", "kochi",
]
FOREIGN_MARKERS = [
    "usa", "united states", "u.s.", " us ", "san francisco", "new york",
    "seattle", "austin", "boston", "chicago", "los angeles", "canada",
    "toronto", "london", "united kingdom", " uk", "dublin", "ireland",
    "germany", "berlin", "amsterdam", "netherlands", "france", "paris",
    "singapore", "australia", "sydney", "dubai", "uae", "poland",
    "brazil", "mexico", "japan", "tokyo", "emea", "apac", "latam",
]

# Titles / keywords that usually mean the role is NOT a fit (hard filter).
NEGATIVE_TITLE_KEYWORDS = [
    "senior", "sr.", "staff", "principal", "lead", "architect", "manager",
    "director", "head of", "vp ", "ios", "android", "frontend", "front end",
    "front-end", "react native", "data scientist", "machine learning engineer",
    "devops lead", "sales", "marketing", "recruiter", "sourcer", "hr ",
    "accountant", "php", "ruby on rails", ".net architect",
    "coordinator", "partnerships", "legal", "privacy", "operations associate",
    "rtl", "hardware", "asic", "analog", "mechanical", "electrical engineer",
    "designer", "content", "support engineer", "customer", "finance",
    "talent", "people ", "office ", "administrative",
]

# Preferred locations (lower-cased match against the job location string).
PREFERRED_LOCATIONS = [
    "pune", "hyderabad", "mumbai", "bengaluru", "bangalore",
    "remote", "india",
]

# Employment types we accept.
ACCEPTED_EMPLOYMENT_TYPES = [
    "full-time", "full time", "permanent", "internship", "intern",
    "graduate", "trainee", "apprentice", "contract-to-hire",
]

# Search query variations (used by the pluggable web-search connector).
SEARCH_QUERIES = [
    "Java Developer Fresher India",
    "Java Backend Developer 0-2 Years India",
    "Spring Boot Developer Entry Level India",
    "Graduate Software Engineer Java India",
    "Associate Software Engineer Java India",
    "Junior Backend Engineer India",
    "Java Developer Hiring Freshers India",
    "Software Engineer 2025 Graduates India",
    "Java Spring Boot Trainee India",
    "Entry Level Backend Developer India",
    "Remote Junior Java Developer India",
]

# --------------------------------------------------------------------------- #
# Experience eligibility
# --------------------------------------------------------------------------- #
# Max years of REQUIRED experience we treat as entry-level eligible.
MAX_ELIGIBLE_YEARS = 2
# Candidate's own years of professional experience (derived from resume, but
# can be overridden here). Trevia internship since Nov 2025.
CANDIDATE_YEARS_EXPERIENCE = 0.5
CANDIDATE_GRADUATION_YEAR = 2025

# --------------------------------------------------------------------------- #
# Scoring weights (must sum to 100) -- from the master spec
# --------------------------------------------------------------------------- #
WEIGHTS = {
    "technical_skills": 35,
    "experience": 25,
    "responsibilities": 15,
    "education": 10,
    "location": 10,
    "employment_type": 5,
}

SCORE_BANDS = [
    (90, "Excellent match"),
    (80, "Very strong match"),
    (70, "Good match"),
    (60, "Possible match"),
    (50, "Weak match"),
    (0, "Not recommended"),
]

# --------------------------------------------------------------------------- #
# Real, legitimately-accessible sources.
#
# Greenhouse, Lever and Ashby all expose PUBLIC JSON job-board APIs that do
# not require authentication and are intended for public consumption. These
# give us REAL open roles with REAL apply links -- no CAPTCHA/login bypass.
#
# `board_token` is the company slug used in the public API URL. Add or remove
# companies freely. Invalid/removed boards are skipped gracefully.
# --------------------------------------------------------------------------- #
GREENHOUSE_BOARDS = [
    # India-HQ / strong India presence (prioritised)
    "razorpay", "swiggy", "gojek", "postman", "freshworks", "cleartax",
    "zeta", "sprinklr", "games24x7", "mindtickle", "hasura", "browserstack",
    "chargebee", "innovaccer", "whatfix", "druva", "meesho", "groww",
    "phonepe", "sumologic", "mywork", "udaan", "upgrad", "simpplr",
    "icertis", "gupshup", "nutanix", "quantiphi", "harness", "tekion",
    # Global product companies that also hire in India
    "rubrik", "cockroachlabs", "databricks", "coinbase", "stripe",
    "airbnb", "dropbox", "twilio", "gitlab", "mongodb", "elastic",
    "hashicorp", "confluent", "atlassian",
]

LEVER_BOARDS = [
    "leadsquared", "yellowai", "netradyne", "spinny", "cred",
    "plivo", "exotel", "hevodata", "vymo", "fampay", "jupiter",
    "slice", "m2pfintech", "bharatpe", "classplus", "rupeek",
    "khatabook", "mfine", "pixis", "zluri", "darwinbox",
]

ASHBY_BOARDS = [
    "ashby", "openai", "linear", "ramp", "notion", "runway",
    "posthog", "deel", "vanta", "mistral", "hasura", "atlan",
    "fampay", "zluri", "sarvam", "portkey",
]

# Network politeness
REQUEST_TIMEOUT = 15          # seconds
REQUEST_DELAY = 0.4           # seconds between calls to the same host
USER_AGENT = (
    "AIRecruiterBot/1.0 (+personal job-search assistant; respects robots.txt)"
)

# --------------------------------------------------------------------------- #
# Optional LLM enhancement
# --------------------------------------------------------------------------- #
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
USE_LLM = bool(OPENAI_API_KEY)

# --------------------------------------------------------------------------- #
# Email notifications (only used if fully configured)
# --------------------------------------------------------------------------- #
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
NOTIFY_EMAIL = os.getenv("NOTIFY_EMAIL", "tejasamzare28@gmail.com")
NOTIFY_SCORE_THRESHOLD = 85


def band_for_score(score: float) -> str:
    for threshold, label in SCORE_BANDS:
        if score >= threshold:
            return label
    return "Not recommended"


def location_is_india(location: str) -> bool:
    low = (location or "").lower()
    return any(m in low for m in INDIA_MARKERS)


def location_acceptable(location: str) -> bool:
    """
    Allowlist approach (robust): a role is pursuable only if it is clearly in
    India, is a global/India remote role, or the location is unknown. Any
    location that names a specific non-India place is treated as not acceptable
    (work-authorization/visa barrier).
    """
    low = (location or "").strip().lower()
    if not low or low in ("unknown", "multiple locations", "various"):
        return True  # unknown -> keep but will be flagged
    if location_is_india(low):
        return True
    if "remote" in low and any(g in low for g in
                               ("india", "global", "worldwide", "anywhere")):
        return True
    return False


def location_is_foreign(location: str) -> bool:
    return not location_acceptable(location)


def title_is_software_role(title: str) -> bool:
    low = (title or "").lower()
    return any(k in low for k in POSITIVE_TITLE_KEYWORDS)


