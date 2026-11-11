# Job search

Everything for one person's job search, run by Claude with the Claude Brain.

| File | What it is | Who changes it |
|---|---|---|
| `profile.json` | Who you are, what you want, where, pay floor, roles to avoid | You (or Claude, when you say so in chat) |
| `MATCHES.md` | Open postings that fit, scored 0-100 with reasons, newest marked NEW | The daily sweep |
| `RANKED_USES.md` | Every way Claude can help, ranked for you (over 1,000) | `brain jobs rank` |
| `TRACKER.md` | Your applications, the funnel, and where it leaks | `brain jobs track` |
| `documents/` | Resume, cover letters, outreach messages, as Markdown | Claude |
| `out/` | The Word files built from `documents/` | `python3 tools/check.py` |
| `data/companies.jsonl` | Target employers: one `{"name", "careers"}` per line | You or Claude |
| `data/boards.jsonl` | Every job board found on the public job systems | `tools/jobfeeds.py discover` |
| `research/` | Evidence and market memos with sources | Claude |

## From your phone

In a Claude Code chat with this repository and the brain attached, say what you want:

- "Sweep for jobs" — reads every target employer's job board and writes `MATCHES.md`.
- "Tailor my resume for <link>" — writes `documents/resume-<company>.md` and the Word file in `out/`.
- "Write the outreach for <company>" — finds the right people to ask and drafts the messages.
- "I applied to <company>", "I got an interview at <company>" — updates the tracker.
- "What should I do this week?" — the top of the ranking for where your funnel stands now.

Or on GitHub: Actions, "Job sweep", Run workflow. It also runs by itself every morning.

## How postings are found

Only from feeds employers publish for the purpose: the public job-board APIs of Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Workday, BambooHR, Breezy and Personio, and schema.org job data on careers pages. Companies are found three ways: your list, a probe of each name on every job system, and the Common Crawl index of all boards on each system. Nothing logs in, solves CAPTCHAs or ignores robots.txt; a page that refuses is listed in `UNREADABLE.md` for you to open in a browser.
