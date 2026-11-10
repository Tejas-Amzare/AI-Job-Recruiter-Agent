# AI Recruiter — Automatic Job Discovery, Resume Matching & Application Tracker

An AI-style recruiter pipeline that analyses your resume, searches **real,
legitimately-accessible** job sources, scores every opportunity against your
profile with an evidence-based model, verifies direct application links, and
produces a professional multi-sheet Excel report — `AI_Job_Research_Report.xlsx`.

Built for candidate: **Tejas Gajanan Amzare** — Java Backend Developer
(Spring Boot, REST APIs, PostgreSQL), B.E. IT 2025, Pune.

---

## ⚠️ Honest coverage & data limitations (read this first)

This tool only uses sources that can be accessed **without bypassing logins,
CAPTCHAs, or anti-bot protection**, per your own requirement to respect website
terms. In practice that means:

| Source | Status | Why |
|---|---|---|
| **Greenhouse / Lever / Ashby** public job-board JSON APIs | ✅ **Used (real jobs)** | Official, public, no auth, ToS-friendly. Verified posting timestamps. |
| LinkedIn, Naukri, Indeed, Foundit, Instahyre, Shine, Hirist, Cutshort, Internshala, Freshersworld | ❌ Not scraped | They block automated access / require login. Scraping them would violate their terms. |
| Workday career pages | ⚠️ Partially feasible | Per-tenant APIs; add tokens in `config.py` if you have them. |
| Google / Google Jobs | 🔌 Optional | Enable via a **permitted** search API key (`SERPAPI_KEY`). Off by default. |

**What this means for you:** the accessible ATS boards are dominated by global
product companies that post **India entry-level roles infrequently**. On a given
day there may be **zero** India Java-fresher roles posted in the last 24h on
these specific boards. That is a *real* data limitation, not a bug — the tool
will honestly report 0 rather than invent jobs. To get more India coverage:

1. Add more Indian-company ATS board tokens to `config.py`
   (`GREENHOUSE_BOARDS`, `LEVER_BOARDS`, `ASHBY_BOARDS`).
2. Enable the optional web-search connector with a permitted API key.
3. Widen the freshness window (e.g. `--window 72`) when daily volume is low.

**Nothing is ever fabricated** — jobs, dates, salaries, links and scores all come
from the source APIs and your resume.

---

## Quick start

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Your resume is already at data/resume.txt. To use a PDF/DOCX instead,
#     drop it into data/ or pass --resume <path>.)

# 3. Analyse resume only
python -m ai_recruiter.main --profile-only

# 4. Full run: discover -> score -> verify -> report (strict 24h window)
python -m ai_recruiter.main

# 5. Widen the freshness window to 72 hours (useful on low-volume days)
python -m ai_recruiter.main --window 72
```

Output:
- Console: candidate profile, top-20 jobs, coverage summary.
- `reports/AI_Job_Research_Report.xlsx` (overwritten each run).
- `reports/AI_Job_Research_Report_<timestamp>.xlsx` (historical copy, preserved).
- `data/job_history.sqlite3` (job history DB).
- `logs/ai_recruiter.log`.

---

## The Excel report (7 sheets)

The report is a **persistent, growing job tracker** backed by a local SQLite
database (`data/job_history.sqlite3`):

- **Every run only ADDS jobs that have never been seen before.**
- **A job is never repeated** — it is matched by a `company + title + location`
  fingerprint (primary key).
- **Each job keeps the date it was first discovered** (`Date Added` column).
  Jobs found today are stamped with today's date; tomorrow's new jobs get
  tomorrow's date, and today's jobs stay exactly as they were.
- Brand-new jobs for the current run are highlighted (`New This Run = YES`).

Sheets:

1. **Top Matched Jobs** — all accumulated roles scoring ≥ 60.
2. **Excellent Matches** — score ≥ 85.
3. **Good Matches** — 70–84.
4. **Possible Matches** — 60–69.
5. **Unverified Jobs** — relevant but uncertain posting date / link.
6. **Rejected Jobs** — rejected jobs from the current run **with the exact reason**.
7. **Daily Summary** — totals, new-today count, jobs by date added / platform /
   location, most-requested skills, and skills you're most often missing.

New columns for tracking: **Posted Within 24h**, **Date Added**, **New This Run**.

Formatting: frozen header row, auto-filters, wrapped text, tuned column widths,
clickable JD + Apply hyperlinks, colour-coded match scores.

> Note: the freshness window (`--window`) is informational in the tracker — a
> relevant India role is kept and dated even if it's older than the window, so
> the sheet accumulates useful jobs instead of staying empty. The
> `Posted Within 24h` column tells you which ones are genuinely fresh.

---

## Scoring model (evidence-based, weighted — from the spec)

| Criterion | Weight |
|---|---:|
| Technical skills match | 35 |
| Experience compatibility | 25 |
| Job responsibilities match | 15 |
| Education & graduation eligibility | 10 |
| Location & work preference | 10 |
| Employment type suitability | 5 |

Guardrails (caps, not random numbers):
- Roles requiring **> 2 yrs** mandatory experience (and not fresher-friendly)
  are capped at 45 (Not recommended).
- Roles with **no core backend skill overlap** are capped at 58.
- **Foreign locations** (work-authorization/visa barrier) are capped at 40 and
  filtered out of the eligible set.

Bands: 90–100 Excellent · 80–89 Very strong · 70–79 Good · 60–69 Possible ·
50–59 Weak · <50 Not recommended.

---

## Architecture / modules

```
ai_recruiter/
  config.py                     # all settings, target profile, ATS boards, gating
  utils.py                      # logging, HTTP session, time/text helpers
  models.py                     # Job dataclass
  resume_analyzer.py            # parse resume (txt/pdf/docx) -> CandidateProfile
  job_source_connectors.py      # Greenhouse / Lever / Ashby + web-search hook
  job_description_parser.py     # required/preferred skills, experience, grad years
  eligibility_checker.py        # relevance, entry-level, 24h freshness, India gating
  job_matcher.py                # weighted scoring + explanations + recruiter note
  application_link_verifier.py  # verifies apply URLs are real & reachable
  duplicate_detector.py         # fingerprint-based dedup across boards
  spreadsheet_generator.py      # 7-sheet formatted Excel
  storage.py                    # SQLite job history (preserves reports)
  daily_report.py               # run once + print top-N + email notify
  job_search_engine.py          # orchestrates the full pipeline
  scheduler.py                  # optional daily scheduling
  main.py                       # CLI entry point
```

---

## Optional features

### Web search (Google etc.)
Set a **permitted** search API key and the connector surfaces real result URLs
(past-24h filter) for the `job_description_parser` to process:
```powershell
$env:SERPAPI_KEY = "your-key"
```

### LLM enhancement
If you set `OPENAI_API_KEY`, the matcher can be extended to use an LLM for
nuanced JD-vs-resume reasoning (hook present; rule-based scoring works without it).

### Email notifications (excellent matches)
```powershell
$env:SMTP_HOST="smtp.gmail.com"; $env:SMTP_USER="you@gmail.com"
$env:SMTP_PASSWORD="app-password"; $env:NOTIFY_EMAIL="tejasamzare28@gmail.com"
```

### Daily scheduling (only when you opt in)
```powershell
python -m ai_recruiter.scheduler --time 09:00
```

---

## Adding more job sources

Open `config.py` and extend the board lists with the company's ATS slug:

```python
GREENHOUSE_BOARDS += ["company-slug"]   # boards.greenhouse.io/<slug>
LEVER_BOARDS      += ["company-slug"]   # jobs.lever.co/<slug>
ASHBY_BOARDS      += ["company-slug"]   # jobs.ashbyhq.com/<slug>
```
Invalid/removed boards are skipped gracefully. Find slugs from a company's
careers page URL.

---

## Compliance

- Only public, auth-free endpoints are queried; polite delays + timeouts.
- No CAPTCHA/login/anti-bot bypass.
- No fabricated jobs, dates, salaries, recruiters, links, or scores — unverifiable
  fields are marked `Unknown`.

#   A I - J o b - R e c r u i t e r - A g e n t  
 