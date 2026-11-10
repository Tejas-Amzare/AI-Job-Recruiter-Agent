"""
resume_analyzer.py
------------------
Reads the resume (.txt / .pdf / .docx), extracts structured data and builds a
CandidateProfile that the rest of the pipeline uses as the source of truth.

No information is invented. Anything not found is left empty / Unknown.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .utils import get_logger, normalize

log = get_logger("resume")

# --------------------------------------------------------------------------- #
# Skill taxonomy -- canonical skill -> list of aliases to look for in text.
# --------------------------------------------------------------------------- #
SKILL_ALIASES: dict[str, list[str]] = {
    "Java": ["java 17", "java17", "core java", "java"],
    "SQL": ["sql"],
    "Spring Boot": ["spring boot", "springboot", "spring boot 3"],
    "Spring MVC": ["spring mvc"],
    "Spring Security": ["spring security"],
    "Spring Data JPA": ["spring data jpa"],
    "REST APIs": ["rest api", "rest apis", "restful", "rest"],
    "Microservices": ["microservice", "microservices"],
    "JWT": ["jwt"],
    "RBAC": ["rbac", "role-based access", "role based access"],
    "OAuth2": ["oauth", "oauth2"],
    "Hibernate": ["hibernate"],
    "JPA": ["jpa", "java persistence"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Flyway": ["flyway"],
    "Liquibase": ["liquibase"],
    "JUnit": ["junit", "junit 5"],
    "Mockito": ["mockito"],
    "Swagger/OpenAPI": ["swagger", "openapi", "open api"],
    "Postman": ["postman"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"],
    "AWS": ["aws", "ec2", "amazon web services", " s3 ", "rds", "iam"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Git": ["git", "github", "gitlab"],
    "Maven": ["maven"],
    "Gradle": ["gradle"],
    "Agile": ["agile", "scrum"],
    "SDLC": ["sdlc"],
    "HTML": ["html"],
    "CSS": ["css"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript"],
    "React": ["react"],
    "Python": ["python"],
    "C++": ["c++"],
    "Collections Framework": ["collections framework", "collections"],
    "Exception Handling": ["exception handling"],
    "Hibernate/ORM": ["orm"],
    "CI/CD": ["ci/cd", "jenkins", "github actions"],
}


@dataclass
class CandidateProfile:
    raw_text: str = ""
    full_name: str = "Unknown"
    email: str = "Unknown"
    phone: str = "Unknown"
    location: str = "Unknown"
    education: str = "Unknown"
    graduation_year: int | None = None
    years_experience: float = 0.0
    current_title: str = "Unknown"
    skills: set[str] = field(default_factory=set)
    certifications: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    target_titles: list[str] = field(default_factory=list)

    # Derived buckets
    strongest_skills: list[str] = field(default_factory=list)
    weaker_or_missing: list[str] = field(default_factory=list)

    def skill_set_lower(self) -> set[str]:
        return {s.lower() for s in self.skills}


# --------------------------------------------------------------------------- #
# File loading
# --------------------------------------------------------------------------- #
def _load_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(str(path)) as pdf:
                return "\n".join(p.extract_text() or "" for p in pdf.pages)
        except Exception as exc:  # pragma: no cover
            log.warning("Could not read PDF %s: %s", path, exc)
            return ""
    if suffix in (".docx", ".doc"):
        try:
            import docx
            d = docx.Document(str(path))
            return "\n".join(p.text for p in d.paragraphs)
        except Exception as exc:  # pragma: no cover
            log.warning("Could not read DOCX %s: %s", path, exc)
            return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _find_resume() -> Path | None:
    # 1. Explicit configured path
    if config.RESUME_PATH.exists():
        return config.RESUME_PATH
    # 2. Any resume-like file in the data dir
    for pattern in ("*.pdf", "*.docx", "*.doc", "*.txt"):
        for p in config.DATA_DIR.glob(pattern):
            if "resume" in p.name.lower() or "cv" in p.name.lower():
                return p
    # 3. First supported document in data dir
    for pattern in ("*.pdf", "*.docx", "*.txt"):
        files = sorted(config.DATA_DIR.glob(pattern))
        if files:
            return files[0]
    return None


# --------------------------------------------------------------------------- #
# Extraction helpers
# --------------------------------------------------------------------------- #
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\s-]{8,}\d)")
YEAR_RE = re.compile(r"(19|20)\d{2}")


def _extract_skills(text: str) -> set[str]:
    low = normalize(text)
    found = set()
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in aliases:
            if alias in low:
                found.add(canonical)
                break
    return found


def _extract_grad_year(text: str) -> int | None:
    # Prefer a year attached to a B.E./B.Tech line or an education range end.
    ranges = re.findall(r"(20\d{2})\s*[-–]\s*(20\d{2})", text)
    if ranges:
        return int(max(end for _, end in ranges))
    years = [int(y) for y in re.findall(r"20\d{2}", text)]
    return max(years) if years else None


def _extract_name(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line and len(line.split()) <= 5 and line.replace(" ", "").isalpha():
            return line.title()
    return "Unknown"


def _extract_certifications(text: str) -> list[str]:
    certs: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("CERTIFICATION"):
            capture = True
            continue
        if capture:
            if not stripped:
                continue
            if up.isupper() and len(stripped.split()) <= 3 and not stripped.startswith("-"):
                break  # next section header
            cleaned = stripped.lstrip("-•* ").strip()
            if cleaned:
                certs.append(cleaned)
    return certs


def _extract_projects(text: str) -> list[str]:
    projects: list[str] = []
    capture = False
    for line in text.splitlines():
        stripped = line.strip()
        up = stripped.upper()
        if up.startswith("PROJECTS"):
            capture = True
            continue
        if capture:
            if up.startswith("EDUCATION") or up.startswith("CERTIFICATION"):
                break
            if stripped and not stripped.startswith("-") and ":" in stripped:
                projects.append(stripped.split("  ")[0].strip())
    return projects


def analyze_resume(path: str | Path | None = None) -> CandidateProfile:
    resume_path = Path(path) if path else _find_resume()
    if not resume_path or not resume_path.exists():
        raise FileNotFoundError(
            "No resume found. Place your resume (PDF/DOCX/TXT) in the 'data/' "
            "folder or pass --resume <path>."
        )

    text = _load_text(resume_path)
    if not text.strip():
        raise ValueError(f"Resume at {resume_path} appears empty or unreadable.")

    log.info("Analyzing resume: %s (%d chars)", resume_path.name, len(text))

    skills = _extract_skills(text)
    email = (EMAIL_RE.search(text) or [None])
    email = email.group(0) if hasattr(email, "group") else "Unknown"
    phone_m = PHONE_RE.search(text)
    grad_year = _extract_grad_year(text)

    profile = CandidateProfile(
        raw_text=text,
        full_name=_extract_name(text),
        email=EMAIL_RE.search(text).group(0) if EMAIL_RE.search(text) else "Unknown",
        phone=phone_m.group(0).strip() if phone_m else "Unknown",
        location="Pune, Maharashtra, India" if "pune" in text.lower() else "Unknown",
        education="B.E. Information Technology" if "information technology" in text.lower()
        else "Unknown",
        graduation_year=grad_year,
        years_experience=config.CANDIDATE_YEARS_EXPERIENCE,
        current_title="Java Developer Intern" if "developer intern" in text.lower()
        else "Unknown",
        skills=skills,
        certifications=_extract_certifications(text),
        projects=_extract_projects(text),
        target_titles=list(config.TARGET_TITLES),
    )

    # Derived analysis -------------------------------------------------------
    core_backend = [
        "Java", "Spring Boot", "Spring Security", "REST APIs",
        "PostgreSQL", "JWT", "Hibernate", "JPA",
    ]
    profile.strongest_skills = [s for s in core_backend if s in skills]

    # Commonly-requested skills the candidate does NOT clearly have.
    common_wanted = [
        "Microservices", "Docker", "Kubernetes", "Kafka", "Redis",
        "AWS", "CI/CD", "MongoDB", "React", "Python",
    ]
    profile.weaker_or_missing = [s for s in common_wanted if s not in skills]

    log.info("Extracted %d skills; strongest: %s",
             len(skills), ", ".join(profile.strongest_skills))
    return profile


def profile_summary(p: CandidateProfile) -> str:
    lines = [
        "=" * 70,
        "CANDIDATE PROFILE (from resume - source of truth)",
        "=" * 70,
        f"Name            : {p.full_name}",
        f"Email           : {p.email}",
        f"Phone           : {p.phone}",
        f"Location        : {p.location}",
        f"Education        : {p.education}",
        f"Graduation year : {p.graduation_year}",
        f"Experience      : ~{p.years_experience} years (entry-level)",
        f"Current title   : {p.current_title}",
        "",
        f"Strongest skills: {', '.join(p.strongest_skills) or 'Unknown'}",
        f"All skills ({len(p.skills)}): {', '.join(sorted(p.skills))}",
        "",
        f"Certifications  : {'; '.join(p.certifications) or 'Unknown'}",
        f"Projects        : {'; '.join(p.projects) or 'Unknown'}",
        "",
        f"Likely-requested skills you lack: {', '.join(p.weaker_or_missing)}",
        "",
        "Recommended target titles:",
        "  " + ", ".join(p.target_titles[:8]),
        "Avoid: Senior/Lead/Architect/Manager roles, non-Java stacks "
        "(iOS/Android/PHP/.NET), data-science/ML-heavy roles.",
        "=" * 70,
    ]
    return "\n".join(lines)

