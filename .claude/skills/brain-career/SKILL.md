---
name: brain-career
description: Run a job search: target roles, find postings on every employer job system, rank what to do, tailor resumes and letters, outreach, interviews, offers. Use for "job search", "find me jobs", "tailor my resume", "prepare my interview", "negotiate", or "busca trabajo", "mi currículum".
---

# Career: a job search, end to end

The outcome is offers the person wants, sooner: interviews at employers that fit, documents that pass applicant-tracking systems and read human, and a funnel that shows where to put the next hour. Evidence is in `docs/research/job-search-evidence.md`; `BRAIN recall "<topic>" --family career` gives the playbook lines.

## 1. The project

Personal data never goes in the brain. Work in the person's job-search repository. If it lacks the kit, `BRAIN jobs init <repo>` installs it: `profile.json`, `documents/`, `data/`, `tracker.jsonl`, `tools/jobfeeds.py`, `tools/mddocx.py`, `tools/check.py` (the gate) and a daily GitHub Action. With no repository attached, add a `NEEDS_YOU.md` step to create an empty private one, build the kit in a local folder, and send the key files.

Fill `profile.json` from what the person said: tags (from `kits/jobsearch/taxonomy.json`), target role families with title keywords and weights, roles to avoid, places, pay floor, years asked at most, plus and minus keywords. Record each guess in `.brain/DECISIONS.md`.

## 2. What to do, in order

`BRAIN jobs rank --profile profile.json --tracker tracker.jsonl --out RANKED_USES.md` ranks the 1,000+ uses in `kits/jobsearch/uses/` by expected value per hour: impact, evidence grade, the lever's measured effect, fit to the person's tags, the funnel stage that leaks, and the hours it costs, with a diversity pass. Work from the top; re-rank weekly.

## 3. Find the jobs

- `python3 tools/jobfeeds.py sweep` reads every target's board and writes `MATCHES.md` (fit 0-100 with reasons; NEW since last time). Companies come from `data/companies.jsonl` ({"name", "careers"}), from a probe of each name on ten job systems, and from `tools/jobfeeds.py discover` (every board on each system, from the Common Crawl index; it falls back to older crawls when the newest is busy).
- `tools/jobfeeds.py detect <url>` names a careers page's job system; `probe "<name>"` finds a board from a name alone; `board <ats> <slug>` lists one board.
- Only public feeds: no logging in, no CAPTCHA, robots.txt honoured. Pages that refuse go to `UNREADABLE.md` with what to open by hand.

## 4. Documents

The master resume is `documents/resume.md`; a tailored copy per posting is `documents/resume-<company>.md` using the posting's own words for skills the person really has, results with numbers first, one page early in a career. Cover letters under 250 words: why this company, one proof story, the ask. `python3 tools/check.py` builds every document into `out/*.docx` and fails on template placeholders. Read `method/dod/job-application.md` before delivering.

## 5. Outreach and referrals

For each top-tier employer, find the referral path first (alumni, former colleagues, second-degree contacts, recruiters), then draft short messages into `documents/outreach.md` with a day-5 follow-up. Never send anything for the person: sending is theirs, so it goes in `NEEDS_YOU.md` or the reply.

## 6. Track and adapt

`BRAIN jobs track --company "<c>" --role "<r>" --status applied --channel referral --url <link>` records each step and rewrites `TRACKER.md` with the funnel, response rate by channel and the weakest step. The next ranking weights that step.

## 7. Interviews and offers

Stories with numbers from the person's real work; mock each format (screen, behavioral, case, panel, Spanish-language) with Claude as interviewer, scored against the posting. For an offer, prepare a counter backed by BLS OEWS figures for the metro and occupation, and ask about time off, title and start date as well as pay.

## Timebox

One tailored application: aim for 30 minutes, stop at 60. A sweep stops at its `--max-minutes`. A week's plan comes from the ranking, not from more research.

## Tell the person

What is new (matches, documents built, messages ready), the one thing they must do themselves, and where to look on their phone (`MATCHES.md`, `out/`, `TRACKER.md`).
