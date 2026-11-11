#!/usr/bin/env python3
"""Job postings from the feeds employers publish, and how well each fits a profile.

Standalone on purpose (standard library only, no brain imports): `brain jobs
init` copies this file into a job-search project as `tools/jobfeeds.py`, where
it runs on its own (`python3 tools/jobfeeds.py sweep --profile profile.json`)
from a phone-triggered GitHub Action or a Claude Code session.

What it reads, and only that:
- applicant-tracking-system job-board APIs that are public by design
  (Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Workday's
  career-site JSON, BambooHR, Breezy, Personio);
- schema.org JobPosting data embedded in a careers page, after robots.txt
  allows the page;
- the Common Crawl URL index, to enumerate which companies have a board on
  each system (this is how "every company" is found: the boards, not a list).
It never logs in, never submits anything, never solves CAPTCHAs, sends a
plain user agent, waits between requests to one host, and gives up on a host
that refuses. A site that hides postings behind a login is reported, not
worked around.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import hashlib
import html
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path
from typing import Callable

USER_AGENT = "jobfeeds/1.0 (personal job search; respects robots.txt)"
TIMEOUT = 12.0
MAX_BYTES = 8_000_000
HOST_GAP = 0.35  # seconds between requests to one host
WORKERS = 8

# fetch(url, data=None, headers=None) -> (status, body_bytes)
Fetch = Callable[..., tuple]


# ---------------------------------------------------------------- network
_host_lock = threading.Lock()
_host_last: dict[str, float] = {}


def http_fetch(url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = TIMEOUT) -> tuple[int, bytes]:
    host = urllib.parse.urlsplit(url).hostname or ""
    with _host_lock:
        wait = _host_last.get(host, 0) + HOST_GAP - time.monotonic()
        _host_last[host] = time.monotonic() + max(0, wait)
    if wait > 0:
        time.sleep(wait)
    h = {"User-Agent": USER_AGENT, "Accept": "application/json, text/html;q=0.9, */*;q=0.5", "Accept-Encoding": "gzip"}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(MAX_BYTES)
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return r.status or 200, body
    except urllib.error.HTTPError as e:
        return e.code, b""
    except (urllib.error.URLError, OSError, ValueError):
        return 0, b""


def _json(fetch: Fetch, url: str, data=None, headers=None):
    status, body = fetch(url, data, headers)
    if status != 200 or not body:
        return None
    try:
        return json.loads(body.decode("utf-8", "replace"))
    except ValueError:
        return None


_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def robots_allows(url: str, fetch: Fetch) -> bool:
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    if base not in _robots:
        status, body = fetch(base + "/robots.txt")
        if status == 200:
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(body.decode("utf-8", "replace").splitlines())
            _robots[base] = rp
        else:
            _robots[base] = None  # no robots.txt (or unreadable): allowed
    rp = _robots[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


# ---------------------------------------------------------------- text
TAG_RE = re.compile(r"<[^>]+>")


def plain(text: str, limit: int = 6000) -> str:
    t = html.unescape(TAG_RE.sub(" ", html.unescape(str(text or ""))))
    return re.sub(r"\s+", " ", t).strip()[:limit]


def _date(v) -> str:
    if isinstance(v, (int, float)) and v > 10_000_000_000:  # milliseconds
        v = v / 1000
    if isinstance(v, (int, float)) and v > 0:
        return dt.datetime.fromtimestamp(v, dt.timezone.utc).strftime("%Y-%m-%d")
    if isinstance(v, str) and re.match(r"\d{4}-\d{2}-\d{2}", v):
        return v[:10]
    return ""


SAL_RE = re.compile(r"\$\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK])(?:\s*(?:-|–|to)\s*\$?\s?(\d{2,3}(?:,\d{3})+|\d{2,3}(?:\.\d)?\s?[kK]))?")


def _money(s: str) -> float | None:
    s = s.replace(",", "").replace(" ", "")
    try:
        return float(s[:-1]) * 1000 if s[-1] in "kK" else float(s)
    except (ValueError, IndexError):
        return None


def salary_range(text: str) -> tuple[float | None, float | None]:
    """Annual salary range found in text ($85,000 - $100,000, $90k to $110k).
    Hourly figures and amounts under 20,000 are ignored."""
    for m in SAL_RE.finditer(text or ""):
        lo, hi = _money(m.group(1)), _money(m.group(2)) if m.group(2) else None
        if lo and lo >= 20000 and (hi is None or hi >= lo):
            return lo, hi or lo
    return None, None


def posting(source: str, company: str, title: str, location: str, url: str, posted="", description: str = "",
            remote: bool | None = None, salary: tuple | None = None, ext_id: str = "") -> dict:
    desc = plain(description)
    lo, hi = salary if salary and salary[0] else salary_range(desc)
    loc = plain(location, 200)
    if remote is None:
        remote = bool(re.search(r"\bremote\b", f"{loc} {title}", re.I))
    if remote and loc and "remote" not in loc.lower():
        loc += " (remote allowed)"  # the employer flags it remote though the text names a hub
    pid = hashlib.sha256(f"{source}|{company}|{ext_id or url}".encode()).hexdigest()[:14]
    return {"id": pid, "source": source, "company": company, "title": plain(title, 200), "location": loc, "remote": remote,
            "url": url, "posted": _date(posted), "salary_min": lo, "salary_max": hi, "description": desc}


# ---------------------------------------------------------------- ATS
ATS_PATTERNS = [
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)")),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"jobs(?:\.eu)?\.lever\.co/([A-Za-z0-9_.-]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)")),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)")),
    ("workable", re.compile(r"apply\.workable\.com/([A-Za-z0-9_-]+)")),
    ("recruitee", re.compile(r"([a-z0-9-]+)\.recruitee\.com")),
    ("workday", re.compile(r"([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)")),
    ("bamboohr", re.compile(r"([a-z0-9-]+)\.bamboohr\.com")),
    ("breezy", re.compile(r"([a-z0-9-]+)\.breezy\.hr")),
    ("personio", re.compile(r"([a-z0-9-]+)\.jobs\.personio\.(?:de|com)")),
]
IGNORE_SLUGS = {"www", "api", "app", "jobs", "careers", "embed", "static", "assets", "help", "support", "boards", "v1", "cdn"}


def detect(text: str) -> list[dict]:
    """Every ATS board named in a URL or page: [{ats, slug, (host, site)}]."""
    out, seen = [], set()
    for ats, pat in ATS_PATTERNS:
        for m in pat.finditer(text or ""):
            if ats == "workday":
                b = {"ats": ats, "slug": m.group(1), "host": f"{m.group(1)}.{m.group(2)}.myworkdayjobs.com", "site": m.group(3)}
                if b["site"].lower() in ("wday", "en-us"):
                    continue
            else:
                b = {"ats": ats, "slug": urllib.parse.unquote(m.group(1))}
            if b["slug"].lower() in IGNORE_SLUGS:
                continue
            key = (b["ats"], b["slug"].lower(), b.get("site", ""))
            if key not in seen:
                seen.add(key)
                out.append(b)
    return out


def _gh(b, f):
    # Light mode (big sweeps): titles and places only; details() fetches the
    # text for the postings that pass the first cut.
    d = _json(f, f"https://boards-api.greenhouse.io/v1/boards/{b['slug']}/jobs?content={'false' if b.get('light') else 'true'}")
    for j in (d or {}).get("jobs", []):
        p = posting("greenhouse", b.get("company") or b["slug"], j.get("title", ""), (j.get("location") or {}).get("name", ""),
                    j.get("absolute_url", ""), j.get("updated_at", ""), j.get("content", ""), ext_id=str(j.get("id", "")))
        p["board"], p["ext_id"] = b["slug"], str(j.get("id", ""))
        yield p


def _lever(b, f):
    d = _json(f, f"https://api.lever.co/v0/postings/{b['slug']}?mode=json")
    if d is None:
        d = _json(f, f"https://api.eu.lever.co/v0/postings/{b['slug']}?mode=json")
    for j in d or []:
        cat = j.get("categories") or {}
        sr = j.get("salaryRange") or {}
        sal = (sr.get("min"), sr.get("max")) if sr.get("interval", "per-year-salary") == "per-year-salary" and sr.get("min") else None
        loc = cat.get("location") or ", ".join(cat.get("allLocations") or [])
        yield posting("lever", b.get("company") or b["slug"], j.get("text", ""), loc, j.get("hostedUrl", ""), j.get("createdAt", 0),
                      j.get("descriptionPlain") or j.get("description", ""), remote=j.get("workplaceType") == "remote" or None,
                      salary=sal, ext_id=j.get("id", ""))


def _ashby(b, f):
    d = _json(f, f"https://api.ashbyhq.com/posting-api/job-board/{urllib.parse.quote(b['slug'])}?includeCompensation=true")
    for j in (d or {}).get("jobs", []):
        comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
        loc = j.get("location", "")
        sec = [x.get("location", "") for x in j.get("secondaryLocations") or [] if isinstance(x, dict)]
        yield posting("ashby", b.get("company") or b["slug"], j.get("title", ""), "; ".join([loc] + sec), j.get("jobUrl", ""),
                      j.get("publishedAt", ""), f"{comp} {j.get('descriptionPlain', '')}", remote=j.get("isRemote"),
                      salary=salary_range(comp), ext_id=j.get("id", ""))


def _smart(b, f):
    for off in range(0, 1000, 100):
        d = _json(f, f"https://api.smartrecruiters.com/v1/companies/{b['slug']}/postings?limit=100&offset={off}")
        rows = (d or {}).get("content", [])
        for j in rows:
            loc = j.get("location") or {}
            yield posting("smartrecruiters", (j.get("company") or {}).get("name") or b["slug"], j.get("name", ""),
                          ", ".join(x for x in (loc.get("city"), loc.get("region"), loc.get("country")) if x),
                          f"https://jobs.smartrecruiters.com/{b['slug']}/{j.get('id', '')}", j.get("releasedDate", ""), "",
                          remote=loc.get("remote"), ext_id=str(j.get("id", "")))
        if len(rows) < 100:
            break


def _workable(b, f):
    d = _json(f, f"https://apply.workable.com/api/v1/widget/accounts/{b['slug']}")
    for j in (d or {}).get("jobs", []):
        yield posting("workable", (d or {}).get("name") or b["slug"], j.get("title", ""),
                      ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x), j.get("url") or j.get("shortlink", ""),
                      j.get("published_on", ""), j.get("description", ""), remote=j.get("telecommuting"), ext_id=j.get("shortcode", ""))


def _recruitee(b, f):
    d = _json(f, f"https://{b['slug']}.recruitee.com/api/offers/")
    for j in (d or {}).get("offers", []):
        yield posting("recruitee", j.get("company_name") or b["slug"], j.get("title", ""), j.get("location", ""), j.get("careers_url", ""),
                      j.get("published_at", ""), j.get("description", ""), remote=j.get("remote"), ext_id=str(j.get("id", "")))


def _workday(b, f):
    # Big tenants list thousands of jobs; with search terms (the profile's
    # places) only the matching ones are paged through.
    seen = set()
    for term in b.get("search") or [""]:
        for p in _workday_term(b, f, term):
            if p["id"] not in seen:
                seen.add(p["id"])
                yield p


def _workday_term(b, f, term):
    base = f"https://{b['host']}/wday/cxs/{b['slug']}/{b['site']}/jobs"
    total = 0
    for off in range(0, 2000, 20):
        d = _json(f, base, json.dumps({"appliedFacets": {}, "limit": 20, "offset": off, "searchText": term}).encode(),
                  {"Content-Type": "application/json"})
        rows = (d or {}).get("jobPostings", [])
        for j in rows:
            yield posting("workday", b.get("company") or b["slug"], j.get("title", ""), j.get("locationsText", ""),
                          f"https://{b['host']}/{b['site']}{j.get('externalPath', '')}", _workday_age(j.get("postedOn", "")), "",
                          ext_id=j.get("externalPath", ""))
        if off == 0:
            total = int((d or {}).get("total", 0) or 0)  # only the first page carries the total
        if len(rows) < 20 or off + 20 >= total:
            break


def _workday_age(text: str) -> str:
    """'Posted Today', 'Posted Yesterday', 'Posted 3 Days Ago', 'Posted 30+ Days Ago' as a date."""
    t = str(text).lower()
    days = 0 if "today" in t else 1 if "yesterday" in t else None
    m = re.search(r"(\d+)\+?\s*days", t)
    if m:
        days = int(m.group(1))
    if days is None:
        return ""
    return (dt.date.today() - dt.timedelta(days=days)).isoformat()


def _bamboo(b, f):
    d = _json(f, f"https://{b['slug']}.bamboohr.com/careers/list")
    for j in (d or {}).get("result", []):
        loc = j.get("location") or {}
        yield posting("bamboohr", b.get("company") or b["slug"], j.get("jobOpeningName", ""),
                      ", ".join(x for x in (loc.get("city"), loc.get("state")) if x),
                      f"https://{b['slug']}.bamboohr.com/careers/{j.get('id', '')}", "", "", remote=bool(j.get("isRemote")) or None,
                      ext_id=str(j.get("id", "")))


def _breezy(b, f):
    d = _json(f, f"https://{b['slug']}.breezy.hr/json")
    for j in d or []:
        yield posting("breezy", (j.get("company") or {}).get("name") or b["slug"], j.get("name", ""), (j.get("location") or {}).get("name", ""),
                      j.get("url", ""), j.get("published_date", ""), "", ext_id=j.get("id", ""))


def _personio(b, f):
    status, body = f(f"https://{b['slug']}.jobs.personio.de/xml")
    if status != 200:
        return
    for pos in re.findall(r"<position>(.*?)</position>", body.decode("utf-8", "replace"), re.S):
        g = lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", pos, re.S) or [None, ""])[1]
        pid = g("id")
        yield posting("personio", b["slug"], g("name"), g("office"), f"https://{b['slug']}.jobs.personio.de/job/{pid}",
                      g("createdAt"), g("value"), ext_id=pid)


READERS = {"greenhouse": _gh, "lever": _lever, "ashby": _ashby, "smartrecruiters": _smart, "workable": _workable,
           "recruitee": _recruitee, "workday": _workday, "bamboohr": _bamboo, "breezy": _breezy, "personio": _personio}


def read_board(board: dict, fetch: Fetch = http_fetch) -> list[dict]:
    reader = READERS.get(board.get("ats"))
    if reader is None:
        return []
    try:
        return [p for p in reader(board, fetch) if p["title"]]
    except Exception:  # one odd board must never stop a sweep
        return []


def details(p: dict, fetch: Fetch = http_fetch) -> dict:
    """Fill in the description of a light posting (Greenhouse, Workday)."""
    if p.get("description"):
        return p
    try:
        if p["source"] == "greenhouse":
            slug, jid = p.get("board"), p.get("ext_id")
            if not (slug and jid):
                m = re.search(r"greenhouse\.io/([^/]+)/jobs/(\d+)", p["url"])
                slug, jid = (m.group(1), m.group(2)) if m else (None, None)
            if slug and jid:
                d = _json(fetch, f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{jid}")
                if d:
                    p["description"] = plain(d.get("content", ""))
        elif p["source"] == "workday":
            u = urllib.parse.urlsplit(p["url"])
            tenant = u.hostname.split(".")[0]
            site, path = u.path.strip("/").split("/", 1)
            d = _json(fetch, f"https://{u.hostname}/wday/cxs/{tenant}/{site}/{path}")
            info = (d or {}).get("jobPostingInfo") or {}
            p["description"] = plain(info.get("jobDescription", ""))
            if re.match(r"\d+ locations", p.get("location", ""), re.I):
                extra = info.get("additionalLocations") or []
                p["location"] = "; ".join([info.get("location", "")] + [x for x in extra if isinstance(x, str)])
            p["posted"] = p["posted"] or _date(info.get("startDate", ""))
        if p.get("description") and not p.get("salary_min"):
            p["salary_min"], p["salary_max"] = salary_range(p["description"])
    except Exception:
        pass
    return p


def slug_candidates(name: str) -> list[str]:
    """Likely board slugs for a company name, most likely first: 'Acme Corp
    Inc.' gives acme, acmecorp, acme-corp, acmecorpinc."""
    words = re.findall(r"[a-z0-9]+", name.lower().replace("&", " and "))
    legal = {"inc", "llc", "ltd", "plc", "sa", "co", "corp", "corporation", "lp", "llp"}
    generic = {"group", "holdings", "the", "company", "usa", "us", "international", "global"}
    core = [w for w in words if w not in legal | generic] or words
    named = [w for w in words if w not in legal or w == "corp"] or words
    out = []
    for cand in ("".join(core), "".join(named), "-".join(core), "".join(words), core[0] if core else ""):
        if cand and len(cand) > 1 and cand not in out:
            out.append(cand)
    return out


PROBES = {
    "greenhouse": lambda s: f"https://boards-api.greenhouse.io/v1/boards/{s}",
    "lever": lambda s: f"https://api.lever.co/v0/postings/{s}?mode=json&limit=1",
    "ashby": lambda s: f"https://api.ashbyhq.com/posting-api/job-board/{s}",
    "smartrecruiters": lambda s: f"https://api.smartrecruiters.com/v1/companies/{s}/postings?limit=1",
    "workable": lambda s: f"https://apply.workable.com/api/v1/widget/accounts/{s}",
}


WORKDAY_PODS = (1, 5, 3, 12, 10, 103, 108, 501, 102, 2, 104, 105)
SKIP_SITE = re.compile(r"agency|event|equest|internal|intern_|campus_only|referral|_(fr|uk|de|es|it|nl|pl|jp|cn|br|mx|in)$", re.I)


def probe_workday(slugs: list[str], fetch: Fetch = http_fetch) -> list[dict]:
    """Workday tenants and their career sites, found from the tenant's
    robots.txt: a real tenant lists one Sitemap line per public career site
    (an unknown tenant answers an error). Tries each slug on the common pods
    and stops at the first that answers."""
    for slug in slugs:
        for n in WORKDAY_PODS:
            host = f"{slug}.wd{n}.myworkdayjobs.com"
            status, body = fetch(f"https://{host}/robots.txt")
            if status != 200 or b"Sitemap" not in body:
                continue
            sites = re.findall(r"Sitemap:\s*https://[^/]+/([^/\s]+)/siteMap\.xml", body.decode("utf-8", "replace"))
            keep = [x for x in sites if not SKIP_SITE.search(x)] or sites[:1]
            return [{"ats": "workday", "slug": slug, "host": host, "site": x} for x in keep[:3]]
    return []


def probe(name: str, fetch: Fetch = http_fetch, known_boards: list[dict] | None = None, workday: bool = True) -> list[dict]:
    """Boards for a company found by name alone: its likely slugs tried on
    each system's public API (an answer with postings or a board name is a
    hit), and Workday tenants from the discovered boards whose tenant name is
    one of those slugs. For employers whose careers site blocks robots or
    renders by script, this is usually the way in."""
    hits = []
    for slug in slug_candidates(name)[:3]:
        for ats, url in PROBES.items():
            if any(h["ats"] == ats for h in hits):
                continue
            d = _json(fetch, url(slug))
            ok = (ats == "lever" and isinstance(d, list) and d) or (ats == "greenhouse" and isinstance(d, dict) and d.get("name")) \
                or (ats == "ashby" and isinstance(d, dict) and d.get("jobs") is not None) \
                or (ats == "smartrecruiters" and isinstance(d, dict) and d.get("totalFound")) \
                or (ats == "workable" and isinstance(d, dict) and d.get("jobs"))
            if ok:
                hits.append({"ats": ats, "slug": slug, "company": name})
        for b in known_boards or []:
            if b["ats"] == "workday" and b["slug"].lower() == slug and not any(h.get("host") == b["host"] for h in hits):
                hits.append(dict(b, company=name))
    if workday and not hits:
        hits += [dict(b, company=name) for b in probe_workday(slug_candidates(name)[:3], fetch)]
    return hits


# ---------------------------------------------------------------- careers pages
LD_RE = re.compile(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', re.S | re.I)


def _ld_items(obj):
    if isinstance(obj, list):
        for x in obj:
            yield from _ld_items(x)
    elif isinstance(obj, dict):
        if obj.get("@type") == "JobPosting" or (isinstance(obj.get("@type"), list) and "JobPosting" in obj["@type"]):
            yield obj
        for k in ("@graph", "itemListElement", "item"):
            if k in obj:
                yield from _ld_items(obj[k])


def read_page(url: str, company: str = "", fetch: Fetch = http_fetch) -> tuple[list[dict], list[dict], str]:
    """(postings from schema.org JobPosting data, ATS boards linked from the
    page, note). Honors robots.txt; a refusal or login wall is reported."""
    if not robots_allows(url, fetch):
        return [], [], "robots.txt disallows this page; not read"
    status, body = fetch(url)
    if status in (401, 403):
        return [], [], f"the site refused (HTTP {status}); open it in a browser and save the posting links instead"
    if status != 200:
        return [], [], f"HTTP {status or 'no answer'}"
    text = body.decode("utf-8", "replace")
    found = []
    for raw in LD_RE.findall(text):
        try:
            obj = json.loads(raw.strip())
        except ValueError:
            continue
        for j in _ld_items(obj):
            locs = j.get("jobLocation") or []
            locs = locs if isinstance(locs, list) else [locs]
            place = "; ".join(", ".join(x for x in ((l.get("address") or {}).get(k, "") for k in ("addressLocality", "addressRegion", "addressCountry")) if isinstance(x, str) and x)
                              for l in locs if isinstance(l, dict))
            org = j.get("hiringOrganization") or {}
            bs = j.get("baseSalary") or {}
            val = bs.get("value") if isinstance(bs, dict) else {}
            sal = None
            if isinstance(val, dict) and str(val.get("unitText", "YEAR")).upper() == "YEAR" and val.get("minValue"):
                sal = (float(val["minValue"]), float(val.get("maxValue") or val["minValue"]))
            found.append(posting("jsonld", (org.get("name") if isinstance(org, dict) else "") or company or urllib.parse.urlsplit(url).hostname,
                                 j.get("title", ""), place, j.get("url") or url, j.get("datePosted", ""), j.get("description", ""),
                                 remote=j.get("jobLocationType") == "TELECOMMUTE" or None, salary=sal, ext_id=str(j.get("identifier", ""))))
    boards = detect(text)
    for b in boards:
        b.setdefault("company", company)
    note = "" if found or boards else "no postings data and no known job system linked; the page may load jobs by script, so look for its job-system link in a browser"
    return found, boards, note


# ---------------------------------------------------------------- discovery
CC_QUERIES = {
    "greenhouse": [("boards.greenhouse.io/*", "prefix"), ("job-boards.greenhouse.io/*", "prefix")],
    "lever": [("jobs.lever.co/*", "prefix")],
    "ashby": [("jobs.ashbyhq.com/*", "prefix")],
    "workable": [("apply.workable.com/*", "prefix")],
    "smartrecruiters": [("jobs.smartrecruiters.com/*", "prefix")],
    "workday": [("myworkdayjobs.com", "domain")],
    "recruitee": [("recruitee.com", "domain")],
    "bamboohr": [("bamboohr.com", "domain")],
    "breezy": [("breezy.hr", "domain")],
}


def cc_indexes(fetch: Fetch = http_fetch, n: int = 4) -> list[str]:
    d = _json(fetch, "https://index.commoncrawl.org/collinfo.json")
    return [x["cdx-api"] for x in d[:n] if isinstance(x, dict) and x.get("cdx-api")] if isinstance(d, list) else []


def _cc_page(fetch: Fetch, apis: list[str], query: str, retries: int = 2) -> tuple[str, bytes] | None:
    """One page of an index query: the newest index that answers, each tried
    up to ``retries`` times with a growing wait (the index is often busy)."""
    for api in apis:
        for attempt in range(retries):
            status, body = fetch(f"{api}?{query}")
            if status == 200:
                return api, body
            if status == 404:  # no captures for this query in this crawl
                break
            time.sleep(2 * (attempt + 1))
    return None


def discover(systems: list[str] | None = None, pages: int = 3, fetch: Fetch = http_fetch, log=print) -> list[dict]:
    """Every board the recent Common Crawls saw on each job system: the list of
    companies that publish postings there, without knowing their names first.
    Falls back to older crawls when the newest index does not answer."""
    apis = cc_indexes(fetch)
    if not apis:
        log("Common Crawl index list not reachable; try again later")
        return []
    boards, seen = [], set()
    for ats in systems or list(CC_QUERIES):
        before = len(boards)
        for pattern, mode in CC_QUERIES.get(ats, []):
            for page in range(pages):
                got = _cc_page(fetch, apis, f"url={urllib.parse.quote(pattern)}&matchType={mode}&output=json&fl=url&filter=status:200&page={page}")
                if got is None:
                    log(f"{ats}: index did not answer for {pattern} page {page}")
                    break
                for line in got[1].decode("utf-8", "replace").splitlines():
                    try:
                        u = json.loads(line).get("url", "")
                    except ValueError:
                        continue
                    for b in detect(u):
                        if b["ats"] != ats:
                            continue
                        key = (b["ats"], b["slug"].lower(), b.get("site", "").lower())
                        if key not in seen:
                            seen.add(key)
                            boards.append(b)
        log(f"{ats}: {len(boards) - before} boards")
    return boards


# ---------------------------------------------------------------- fit
SENIOR_RE = re.compile(r"\b(senior|sr\.?|staff|principal|lead|head of|director|associate director|ad|vp|avp|svp|vice president|chief|architect|manager,? (?:sales|engineering) ii)\b", re.I)
YEARS_RE = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|–|to)?\s*(?:\d{1,2}\s*)?(?:years|yrs)(?:'|’)?\s+(?:of\s+)?(?:\w+\s+){0,4}?(?:experience|exp)", re.I)


def _has(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase.lower()) + r"(?![a-z0-9])", text) is not None


FOREIGN = re.compile(r"\b(uk|united kingdom|england|london|emea|europe|india|canada|can|ontario|toronto|vancouver|quebec|apac|asia|"
                     r"australia|new zealand|nz|germany|france|spain|italy|poland|ireland|netherlands|brazil|br|mexico|mx|"
                     r"colombia|argentina|chile|peru|japan|singapore|philippines|israel|portugal|sweden|romania|latam only)\b", re.I)
US_MARK = re.compile(r"\b(us|usa|u\.s\.|united states|america|anywhere in the us|nationwide|[A-Z]{2}\s*\d{5})\b|,\s*(fl|ny|ca|tx|ga|il|wa|ma|co|nc|va)\b", re.I)


def location_ok(p: dict, profile: dict) -> tuple[float, str]:
    """1.0 in a target place (a segment naming the place and no foreign
    country), 0.9 remote within the US, else 0. Segments are split on ; | /
    and ' or ', so 'Remote (US); Miami, FL' counts and 'France > Miami
    Building' does not."""
    loc = p.get("location") or ""
    places = [x.lower() for x in profile.get("locations", [])]
    segments = [x.strip() for x in re.split(r";|\||/| or |\n", loc) if x.strip()] or [""]
    for seg in segments:
        low = seg.lower()
        if any(_has(low, x) for x in places) and not FOREIGN.search(seg):
            return 1.0, "in the target area"
    if profile.get("remote", True):
        for seg in segments:
            low = seg.lower()
            remote_seg = "remote" in low or (p.get("remote") and len(segments) == 1)
            if remote_seg and not FOREIGN.search(seg) and (US_MARK.search(seg) or low in ("remote", "remote - remote", "fully remote", "")):
                return 0.9, "remote (US)"
    return 0.0, f"location '{loc or '?'}' is outside the target area"


def fit(p: dict, profile: dict, today: dt.date | None = None) -> tuple[float, list[str]]:
    """0-100 and the reasons. title fit x location x seniority x salary x
    (1 + bonuses - penalties) x freshness; a match on an avoided role, or a
    place outside the area, scores 0."""
    title = (p.get("title") or "").lower()
    desc = (p.get("description") or "").lower()
    why = []
    for kw in profile.get("avoid_roles", []):
        if _has(title, kw):
            return 0.0, [f"avoided role: '{kw}' in the title"]
    loc, lwhy = location_ok(p, profile)
    if not loc:
        return 0.0, [lwhy]
    why.append(lwhy)
    best, label = 0.0, ""
    for t in profile.get("targets", []):
        w = float(t.get("weight", 1.0))
        for kw in t.get("keywords", []):
            k = kw.lower()
            if _has(title, k):
                s = 1.0
            elif all(_has(title, x) for x in k.split()):
                s = 0.8
            elif desc and _has(desc, k):
                s = 0.3
            else:
                continue
            if s * w > best:
                best, label = s * w, f"{t.get('name')} ('{kw}')"
    if not best:
        return 0.0, ["the title matches no target role"]
    why.append(f"matches {label}")
    score = min(1.0, best)
    if SENIOR_RE.search(title):
        score *= 0.35
        why.append("senior title")
    years = [int(m.group(1)) for m in YEARS_RE.finditer(desc[:5000]) if int(m.group(1)) < 25]
    max_years = profile.get("max_years_required", 3)
    if years and min(years) > max_years:
        score *= 0.45
        why.append(f"asks {min(years)}+ years")
    for kw in profile.get("avoid_keywords", []):
        if desc and _has(desc, kw):
            score *= 0.8
            why.append(f"mentions '{kw}'")
    hi = p.get("salary_max") or p.get("salary_min")
    floor = profile.get("min_salary")
    lo = p.get("salary_min")
    if lo and floor and lo > floor * 2.2:
        score *= 0.55
        why.append(f"starts at ${lo:,.0f}: probably a senior level")
    if hi and floor:
        if hi >= floor:
            score *= 1.1
            why.append(f"pays up to ${hi:,.0f}")
        elif hi < floor * 0.85:
            score *= 0.4
            why.append(f"pays at most ${hi:,.0f}")
    bonus = sum(1 for kw in profile.get("bonus_keywords", []) if _has(desc or title, kw))
    if bonus:
        score *= 1 + min(0.3, 0.05 * bonus)
        why.append(f"{bonus} plus(es) such as {next(k for k in profile['bonus_keywords'] if _has(desc or title, k))}")
    if p.get("posted"):
        try:
            age = ((today or dt.date.today()) - dt.date.fromisoformat(p["posted"])).days
            if age > 120:
                score *= 0.6
                why.append(f"posted {age} days ago (may be stale)")
            elif age > 60:
                score *= 0.8
                why.append(f"posted {age} days ago")
        except ValueError:
            pass
    return round(min(100.0, 100 * score * loc), 1), why


# ---------------------------------------------------------------- sweep
def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def _company(co: dict, fetch: Fetch, known: list[dict] | None) -> tuple[list[dict], list[dict], str]:
    """(boards, postings, note) for one {name, careers}: the URL's own job
    system, else the page's posting data and linked systems, else a probe by
    name on each system's public API."""
    name, url = co.get("name", ""), co.get("careers") or co.get("url") or ""
    direct = detect(url) if url else []
    if direct:
        return [dict(b, company=name or b["slug"]) for b in direct], [], ""
    found, linked, note = read_page(url, name, fetch) if url else ([], [], "no careers URL")
    if not found and not linked and name:
        linked = probe(name, fetch, known)
        note = "" if linked else (note + "; " if note else "") + "no board found by name either"
    return [dict(b, company=name or b["slug"]) for b in linked], found, note


def boards_from_companies(companies: list[dict], fetch: Fetch = http_fetch, log=print,
                          known: list[dict] | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """For a list of {name, careers}: (boards found, postings read straight
    from the pages, notes on companies that could not be read). Companies are
    worked in parallel; requests to one host stay spaced."""
    boards, posts, notes = [], [], []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for co, (bs, ps, note) in zip(companies, ex.map(lambda co: _company(co, fetch, known), companies)):
            boards += bs
            posts += ps
            if note:
                notes.append(f"{co.get('name') or co.get('careers')}: {note}")
    return boards, posts, notes


def sweep(profile: dict, boards: list[dict], fetch: Fetch = http_fetch, min_score: float = 40.0, max_minutes: float = 30.0,
          extra_posts: list[dict] | None = None, log=print) -> tuple[list[dict], dict]:
    """Read every board, score every posting, keep those at or above
    min_score. Light first pass on big sweeps; descriptions fetched only for
    postings that survive it. Stops at max_minutes (Parkinson's law: a sweep
    that is not done by then reports what it has)."""
    light = len(boards) > 40
    deadline = time.monotonic() + max_minutes * 60
    stats = {"boards": len(boards), "boards_read": 0, "postings": 0, "kept": 0, "stopped_early": False}
    pre: list[dict] = list(extra_posts or [])
    terms = profile.get("workday_search") or [x for x in profile.get("locations", [])[:3]] + ["Remote"]
    uniq = {(b["ats"], b["slug"].lower(), b.get("site", "")): dict(b, light=light, search=terms) for b in boards}
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(read_board, b, fetch): b for b in uniq.values()}
        for fut in cf.as_completed(futs):
            if time.monotonic() > deadline:
                stats["stopped_early"] = True
                for f2 in futs:
                    f2.cancel()
                break
            rows = fut.result()
            stats["boards_read"] += 1
            stats["postings"] += len(rows)
            for p in rows:
                s, _ = fit(p, profile)
                if s >= min_score * 0.6:
                    pre.append(p)
            if stats["boards_read"] % 200 == 0:
                log(f"read {stats['boards_read']} of {len(uniq)} boards, {len(pre)} candidates")
    kept = []
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        for p in ex.map(lambda q: details(q, fetch), pre):
            s, why = fit(p, profile)
            if s >= min_score:
                kept.append(dict(p, score=s, why=why))
    seen, out = set(), []
    for p in sorted(kept, key=lambda x: (-x["score"], x["company"].lower(), x["title"])):
        k = (p["company"].lower(), p["title"].lower(), p["location"].lower())
        if k not in seen:
            seen.add(k)
            out.append(p)
    stats["kept"] = len(out)
    return out, stats


def render_matches(rows: list[dict], stats: dict, new_ids: set[str], header: str = "") -> str:
    lines = ["# Job matches", "", header or
             f"{stats['kept']} postings kept from {stats['postings']} read on {stats['boards_read']} of {stats['boards']} boards"
             + (" (stopped at the time limit)" if stats.get("stopped_early") else "") + f". {len(new_ids)} new since the last sweep (marked NEW).", "",
             "| Fit | Company | Role | Where | Pay | Posted | Why |", "|---|---|---|---|---|---|---|"]
    for p in rows:
        pay = f"${p['salary_min']:,.0f}-{p['salary_max']:,.0f}" if p.get("salary_min") else ""
        new = "NEW " if p["id"] in new_ids else ""
        lines.append(f"| {p['score']:g} | {p['company']} | {new}[{p['title']}]({p['url']}) | {p['location'] or ('remote' if p['remote'] else '')} | {pay} | {p.get('posted', '')} | {'; '.join(p['why'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="jobfeeds", description="job postings from public ATS feeds, scored for a profile")
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("detect", help="which job systems a URL or page uses")
    d.add_argument("url")
    r = sub.add_parser("board", help="read one board: <ats> <slug> [site host for workday]")
    r.add_argument("ats")
    r.add_argument("slug")
    r.add_argument("--site", default="")
    r.add_argument("--host", default="")
    disc = sub.add_parser("discover", help="enumerate every board on each job system from the Common Crawl index")
    disc.add_argument("--out", default="data/boards.jsonl")
    disc.add_argument("--system", action="append")
    disc.add_argument("--pages", type=int, default=3)
    sw = sub.add_parser("sweep", help="read boards, score postings, write matches")
    sw.add_argument("--profile", default="profile.json")
    sw.add_argument("--companies", default="data/companies.jsonl", help="{name, careers} per line")
    sw.add_argument("--boards", default="data/boards.jsonl")
    sw.add_argument("--out", default="data/matches.jsonl")
    sw.add_argument("--md", default="MATCHES.md")
    sw.add_argument("--min-score", type=float, default=40.0)
    sw.add_argument("--max-minutes", type=float, default=30.0)
    sw.add_argument("--limit-boards", type=int, default=0, help="read at most this many discovered boards (0 = all, -1 = none: only the company list)")
    rs = sub.add_parser("rescore", help="score the kept matches again after a profile change (no network)")
    rs.add_argument("--profile", default="profile.json")
    rs.add_argument("--out", default="data/matches.jsonl")
    rs.add_argument("--md", default="MATCHES.md")
    rs.add_argument("--min-score", type=float, default=40.0)
    pr = sub.add_parser("probe", help="find a company's boards by its name")
    pr.add_argument("name")
    pr.add_argument("--boards", default="data/boards.jsonl")
    a = ap.parse_args(argv)
    if a.cmd == "detect":
        found = detect(a.url)
        if not found:
            posts, found, note = read_page(a.url)
            print(f"{len(posts)} posting(s) in page data" + (f"; {note}" if note else ""))
        for b in found:
            print(json.dumps(b))
        return 0
    if a.cmd == "board":
        b = {"ats": a.ats, "slug": a.slug, "site": a.site, "host": a.host or f"{a.slug}.wd1.myworkdayjobs.com"}
        rows = read_board(b)
        for p in rows[:50]:
            print(f"{p['title']} · {p['location']} · {p['url']}")
        print(f"{len(rows)} posting(s)")
        return 0 if rows else 1
    if a.cmd == "rescore":
        profile = json.loads(Path(a.profile).read_text(encoding="utf-8"))
        rows = []
        for p in _read_jsonl(Path(a.out)):
            if p.get("remote") and p.get("location") and "remote" not in p["location"].lower():
                p["location"] += " (remote allowed)"
            sc, why = fit(p, profile)
            if sc >= a.min_score:
                rows.append(dict(p, score=sc, why=why))
        rows.sort(key=lambda x: (-x["score"], x["company"].lower(), x["title"]))
        stats = {"kept": len(rows), "postings": len(rows), "boards_read": 0, "boards": 0}
        _write_jsonl(Path(a.out), rows)
        Path(a.md).write_text(render_matches(rows, stats, set(), f"{len(rows)} postings kept after re-scoring the last sweep's matches against the current profile ({dt.date.today().isoformat()})."), encoding="utf-8")
        print(f"{len(rows)} matches kept after rescoring")
        return 0
    if a.cmd == "probe":
        hits = probe(a.name, known_boards=_read_jsonl(Path(a.boards)))
        for h in hits:
            print(json.dumps(h))
        return 0 if hits else 1
    if a.cmd == "discover":
        boards = discover(a.system, a.pages, log=lambda m: print(m, file=sys.stderr))
        old = _read_jsonl(Path(a.out))
        keys = {(b["ats"], b["slug"].lower(), b.get("site", "").lower()) for b in old}
        merged = old + [b for b in boards if (b["ats"], b["slug"].lower(), b.get("site", "").lower()) not in keys]
        _write_jsonl(Path(a.out), merged)
        print(f"{len(merged)} boards in {a.out} ({len(merged) - len(old)} new)")
        return 0
    if a.cmd == "sweep":
        profile = json.loads(Path(a.profile).read_text(encoding="utf-8"))
        known = _read_jsonl(Path(a.boards))
        boards, posts, notes = boards_from_companies(_read_jsonl(Path(a.companies)), known=known)
        boards += known[: a.limit_boards or None] if a.limit_boards >= 0 else []
        rows, stats = sweep(profile, boards, min_score=a.min_score, max_minutes=a.max_minutes, extra_posts=posts,
                            log=lambda m: print(m, file=sys.stderr))
        old = {p["id"] for p in _read_jsonl(Path(a.out))}
        new_ids = {p["id"] for p in rows} - old
        _write_jsonl(Path(a.out), rows)
        Path(a.md).write_text(render_matches(rows, stats, new_ids), encoding="utf-8")
        if notes:
            Path(a.md).with_name("UNREADABLE.md").write_text("# Careers pages that could not be read automatically\n\n"
                                                             + "\n".join(f"- {n}" for n in notes) + "\n", encoding="utf-8")
        print(f"{stats['kept']} matches ({len(new_ids)} new) from {stats['postings']} postings on {stats['boards_read']} boards -> {a.md}")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
