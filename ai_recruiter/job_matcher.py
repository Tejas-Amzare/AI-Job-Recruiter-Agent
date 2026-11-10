"""
job_matcher.py
--------------
Evidence-based match scoring (0-100) using the weighted model from the spec:

    Technical skills match ....... 35
    Experience compatibility ..... 25
    Job responsibilities match ... 15
    Education & grad eligibility . 10
    Location & work preference ... 10
    Employment type suitability .. 5

Produces, per job: score, breakdown, matching/missing skills (mandatory vs
optional), eligibility flags, why-apply text, rejection risks and a recruiter
note. All numbers are derived from resume vs JD evidence, never random.
"""
from __future__ import annotations

from . import config
from .models import Job
from .resume_analyzer import CandidateProfile
from .utils import normalize, get_logger

log = get_logger("matcher")

# Responsibility keywords that map to the candidate's demonstrated strengths.
RESPONSIBILITY_SIGNALS = {
    "rest api": ["rest", "api", "endpoint"],
    "backend": ["backend", "server-side", "server side"],
    "database": ["database", "sql", "query", "schema"],
    "authentication": ["authentication", "authorization", "jwt", "oauth", "security"],
    "microservices": ["microservice", "distributed"],
    "testing": ["unit test", "testing", "junit", "test coverage"],
    "spring": ["spring", "spring boot"],
}


def _skill_match(job: Job, profile: CandidateProfile):
    cand = {s.lower() for s in profile.skills}
    req = [s for s in job.required_skills]
    pref = [s for s in job.preferred_skills]

    matching_mand = [s for s in req if s.lower() in cand]
    missing_mand = [s for s in req if s.lower() not in cand]
    matching_opt = [s for s in pref if s.lower() in cand]
    missing_opt = [s for s in pref if s.lower() not in cand]

    job.matching_mandatory = matching_mand
    job.matching_optional = matching_opt
    job.missing_mandatory = missing_mand
    job.missing_optional = missing_opt

    # Technical score: weight mandatory heavily, optional lightly.
    if not req and not pref:
        tech_ratio = 0.6  # unknown requirements -> neutral-ish
    else:
        mand_ratio = (len(matching_mand) / len(req)) if req else 1.0
        opt_ratio = (len(matching_opt) / len(pref)) if pref else 1.0
        tech_ratio = 0.8 * mand_ratio + 0.2 * opt_ratio
    return tech_ratio


def _experience_score(job: Job, profile: CandidateProfile) -> float:
    yrs = profile.years_experience
    lo, hi = job.min_years, job.max_years
    if lo is None:
        return 0.85  # unspecified -> likely open, slight uncertainty
    if lo <= config.MAX_ELIGIBLE_YEARS:
        # fully eligible band
        if lo <= 1:
            return 1.0
        return 0.9
    # requires more than entry-level
    gap = lo - yrs
    if gap <= 1:
        return 0.5
    if gap <= 2:
        return 0.3
    return 0.05


def _responsibility_score(job: Job, profile: CandidateProfile) -> float:
    blob = normalize(f"{job.title} {job.description}")
    cand_skills = {s.lower() for s in profile.skills}
    hits = 0
    total = 0
    for canonical, signals in RESPONSIBILITY_SIGNALS.items():
        total += 1
        if any(sig in blob for sig in signals):
            # candidate can demonstrate this area?
            if canonical in ("rest api", "backend", "database", "spring",
                             "authentication", "testing") and (
                    cand_skills & {"java", "spring boot", "rest apis",
                                   "postgresql", "spring security", "junit"}):
                hits += 1
            elif canonical == "microservices" and "microservices" in cand_skills:
                hits += 1
    return hits / total if total else 0.5


def _education_score(job: Job, profile: CandidateProfile) -> float:
    score = 1.0
    if job.grad_years:
        if profile.graduation_year in job.grad_years:
            score = 1.0
        else:
            # grad year restriction the candidate misses
            score = 0.4
    return score


def _location_score(job: Job) -> float:
    loc = normalize(job.location)
    if not loc or loc == "unknown":
        return 0.7
    if config.location_is_india(job.location):
        if "remote" in loc:
            return 1.0
        for p in ("pune", "hyderabad", "mumbai", "bengaluru", "bangalore"):
            if p in loc:
                return 1.0
        return 0.9
    if config.location_is_foreign(job.location):
        return 0.1
    if "remote" in loc:
        return 0.8
    return 0.3


def _employment_score(job: Job) -> float:
    et = normalize(job.employment_type)
    if not et or et == "unknown":
        return 0.7
    if any(t in et for t in ("full", "permanent", "graduate", "trainee")):
        return 1.0
    if "intern" in et:
        return 0.8
    if "contract" in et:
        return 0.5
    return 0.6


def score_job(job: Job, profile: CandidateProfile) -> Job:
    tech = _skill_match(job, profile)
    exp = _experience_score(job, profile)
    resp = _responsibility_score(job, profile)
    edu = _education_score(job, profile)
    loc = _location_score(job)
    emp = _employment_score(job)

    w = config.WEIGHTS
    breakdown = {
        "technical_skills": round(tech * w["technical_skills"], 1),
        "experience": round(exp * w["experience"], 1),
        "responsibilities": round(resp * w["responsibilities"], 1),
        "education": round(edu * w["education"], 1),
        "location": round(loc * w["location"], 1),
        "employment_type": round(emp * w["employment_type"], 1),
    }
    total = round(sum(breakdown.values()), 1)

    # Hard eligibility penalty: mandatory experience the candidate can't meet.
    if job.min_years is not None and job.min_years > config.MAX_ELIGIBLE_YEARS:
        blob = normalize(job.description)
        if not any(w_ in blob for w_ in ("fresher", "fresh graduate",
                                         "entry level", "graduate trainee")):
            total = min(total, 45.0)  # cap: not recommended

    # Technical-fit floor: a backend role where almost no resume skill matches
    # should not ride location/education to a high score.
    core = {"java", "spring boot", "spring security", "rest apis",
            "postgresql", "mysql", "jpa", "hibernate", "microservices"}
    cand_core = {s.lower() for s in profile.skills} & core
    jd_core_hits = [s for s in (job.required_skills + job.preferred_skills)
                    if s.lower() in cand_core]
    if not jd_core_hits:
        # No core backend skill overlap detected in the JD text.
        total = min(total, 58.0)

    # Foreign location = effectively not pursuable (visa); cap hard.
    if config.location_is_foreign(job.location):
        total = min(total, 40.0)

    job.score = total
    job.score_breakdown = breakdown
    job.recommendation = config.band_for_score(total)

    _build_explanations(job, profile)
    return job


def _build_explanations(job: Job, profile: CandidateProfile) -> None:
    mand_match = ", ".join(job.matching_mandatory) or "general backend skills"
    exp_desc = (f"role accepts {job.min_years:.0f}"
                f"{'-' + str(int(job.max_years)) if job.max_years else '+'} yrs"
                if job.min_years is not None else
                "experience requirement not strictly specified")

    # Why apply
    reasons = []
    if job.matching_mandatory:
        reasons.append(f"Resume matches required skills: {mand_match}.")
    if job.score_breakdown.get("experience", 0) >= 20:
        reasons.append(f"Experience fit: {exp_desc}.")
    if _location_score(job) >= 0.85:
        reasons.append(f"Preferred/remote location ({job.location}).")
    job.why_apply = " ".join(reasons) or "Relevant backend/software role."

    # Rejection risks
    risks = []
    if job.missing_mandatory:
        risks.append("Missing required skills: " + ", ".join(job.missing_mandatory) + ".")
    if job.min_years is not None and job.min_years > config.MAX_ELIGIBLE_YEARS:
        risks.append(f"May require {job.min_years:.0f}+ yrs experience.")
    if job.grad_years and profile.graduation_year not in job.grad_years:
        risks.append(f"Graduation-year restriction: {job.grad_years}.")
    if _location_score(job) < 0.4:
        risks.append(f"Location {job.location} may be outside preference.")
    job.rejection_reasons = " ".join(risks) or "No major blockers identified."

    # Recruiter-style note (only facts from JD + resume)
    strong = ", ".join([s for s in ("Java", "Spring Boot", "Spring Security",
                                     "REST APIs", "PostgreSQL")
                        if s in profile.skills])
    verdict = ("The candidate should apply." if job.score >= 70
               else "Borderline - apply only if interested."
               if job.score >= 60 else "Not recommended.")
    job.recruiter_note = (
        f"{job.recommendation} for this {job.title} role at {job.company}. "
        f"Candidate strengths: {strong}. "
        f"Professional backend experience on a multi-tenant EV platform (TreviaEV CMS) "
        f"is relevant. {exp_desc.capitalize()}. {verdict}"
    )

