"""Update radar: a deterministic script that watches a fixed list of sources.

Why a script and not a model: the owner wants the brain to notice new models,
prices and research quickly, but only a few tokens may be spent on it. The
script fetches the sources with conditional requests (a 304 costs nothing), keeps
a small state file, and prints at most ``max_lines`` short lines. A model only
ever reads those lines.

What a line means: a *lead*. It is never a fact and never changes memory;
before anything is remembered the model opens the official URL and checks the
claim (see ``brain-learn``). Fetched text is data: it is parsed with regular
expressions or an XML/JSON parser, stripped of tags and control characters,
cut to 200 characters, never executed and never followed. Only hosts on the
allowlist in ``memory/radar_sources.json`` are contacted, and a redirect to
another host is refused. Every failure degrades to silence (invariant I-14).

Files: ``memory/radar_sources.json`` (kernel, read-only here),
``learning/radar/state.json`` (rewritten only by this module) and the inbox
file ``learning/inbox/<date>-radar.jsonl`` (append-only ``lead`` records).
"""
from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from typing import Any, Callable

from . import common as c

SOURCES_FILE = "memory/radar_sources.json"
STATE_FILE = "learning/radar/state.json"      # tracked: content hash and seen ids, changes only with news
CHECKED_FILE = "learning/radar/checked.json"  # git-ignored: when each source was last asked, and how it answered
VOLATILE = ("last_checked", "last_status", "etag", "last_modified")


def read_state(root: Path) -> dict:
    """Tracked state with this machine's check times merged in."""
    state = c.read_json(Path(root) / STATE_FILE, {})
    state = state if isinstance(state, dict) else {}
    checked = c.read_json(Path(root) / CHECKED_FILE, {})
    for sid, v in (checked.items() if isinstance(checked, dict) else ()):
        if isinstance(v, dict):
            state.setdefault(sid, {})
            if isinstance(state[sid], dict):
                state[sid].update({k: x for k, x in v.items() if k in VOLATILE})
    return state


def write_state(root: Path, state: dict) -> None:
    """Split the state: timestamps change every check and would dirty the brain
    tree every day (review M20), so they go to a git-ignored file; the tracked
    file is rewritten only when a source's content or seen ids changed."""
    tracked = {sid: {k: x for k, x in v.items() if k not in VOLATILE} for sid, v in state.items() if isinstance(v, dict)}
    volatile = {sid: {k: x for k, x in v.items() if k in VOLATILE} for sid, v in state.items() if isinstance(v, dict)}
    if c.read_json(Path(root) / STATE_FILE, None) != tracked:
        c.write_json(Path(root) / STATE_FILE, tracked)
    c.write_json(Path(root) / CHECKED_FILE, volatile)
USER_AGENT = "brain-radar/1.0"
MAX_BYTES = 2_000_000          # response size cap: read no more than this
REQUEST_TIMEOUT = 6.0          # seconds per request
MAX_REDIRECTS = 3
WORKERS = 8
TITLE_LIMIT = 200
TEXT_LIMIT = 4000              # per-item text kept for keyword matching only
DEFAULT_SEEN_CAP = 300
DEFAULT_SOURCE_LINES = 3
TRUST_RANK = {"official": 0, "research": 1, "community": 2}
REDIRECT_CODES = (301, 302, 303, 307, 308)

Fetch = Callable[[str, dict, float], "tuple[int, dict, bytes]"]


# ---------------------------------------------------------------- network
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand redirects back to the caller, which checks the host first."""

    def redirect_request(self, *args, **kwargs):  # noqa: D401 - urllib hook
        return None


def default_fetch(url: str, headers: dict, timeout: float) -> tuple[int, dict, bytes]:
    """GET with urllib (environment proxy settings apply), never following redirects.

    Reads at most ``MAX_BYTES`` of the response and, for gzip, decompresses at
    most the same amount, so a hostile server cannot make us hold a large body.
    """
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers=headers)
    try:
        resp = opener.open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        resp = e
    try:
        hdrs = {k.lower(): v for k, v in resp.headers.items()}
        raw = resp.read(MAX_BYTES)
    finally:
        resp.close()
    if hdrs.get("content-encoding", "").lower() == "gzip" and raw:
        raw = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(raw, MAX_BYTES)
    return resp.getcode(), hdrs, raw


class _Refused(Exception):
    """A URL that the allowlist or the redirect rule does not permit."""


def _host(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def _get(url: str, headers: dict, fetch: Fetch, allow: frozenset, timeout: float) -> tuple[int, dict, bytes]:
    """Fetch ``url`` through ``fetch``, enforcing https, the host allowlist and
    the rule that a redirect may only stay on the original host."""
    origin = _host(url)
    for _ in range(MAX_REDIRECTS + 1):
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or _host(url) not in allow:
            raise _Refused("host not allowed")
        status, hdrs, body = fetch(url, headers, timeout)
        hdrs = {str(k).lower(): v for k, v in (hdrs or {}).items()}
        if status in REDIRECT_CODES and hdrs.get("location"):
            url = urllib.parse.urljoin(url, hdrs["location"])
            if _host(url) != origin:
                raise _Refused("redirect to another host")
            continue
        return status, hdrs, body or b""
    raise _Refused("too many redirects")


# ---------------------------------------------------------------- text hygiene
_TAG = re.compile(r"<[^>]*>")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f`]")
_URL_OK = re.compile(r"^https?://[^\s<>\"'`]{1,300}$")


def clean(text: Any, limit: int = TITLE_LIMIT) -> str:
    """Make fetched text safe to print: decode entities, drop tags, control
    characters and backticks, collapse whitespace, cut to ``limit``."""
    s = html.unescape(str(text if text is not None else ""))
    s = _TAG.sub(" ", s)
    s = _CONTROL.sub(" ", s)
    return c.clip(s, limit)


def _md_plain(text: str) -> str:
    """Markdown to plain text: links keep their label, emphasis and heading marks go."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    t = re.sub(r"^\s*(?:[-*+]\s+|#{1,6}\s+)", "", t)
    return re.sub(r"[*_]{1,3}", "", t).strip()


def _iso_date(value: Any) -> str:
    """Best-effort ISO date (YYYY-MM-DD) from ISO, RFC 2822 or 'Month D, YYYY'."""
    s = clean(value, 40)
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return dt.datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    try:
        return email.utils.parsedate_to_datetime(s).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return s[:10]


def _item(raw_id: Any, date: Any, title: Any, url: str, text: Any, fallback_url: str) -> dict | None:
    """Normalise one parsed candidate; None when it has no usable title or id."""
    title = clean(title)
    raw_id = str(raw_id or "").strip()[:300]
    if not title or not raw_id:
        return None
    url = str(url or "").strip()
    return {
        "raw_id": raw_id,
        "date": _iso_date(date) if date else "",
        "title": title,
        "url": url if _URL_OK.match(url) else fallback_url,
        "text": clean(text, TEXT_LIMIT).lower(),
    }


# ---------------------------------------------------------------- parsers
def _hits(text: str, keywords: list[str]) -> int:
    low = text.lower()
    return sum(1 for k in keywords if k in low)


def parse_relnotes_md(body: str, src: dict) -> list[dict]:
    """Release notes: one entry per dated heading ('### November 9, 2026')."""
    out = []
    pat = re.compile(r"^#{2,4}[ \t]+([A-Z][a-z]+ \d{1,2}, \d{4})[ \t]*$", re.M)
    marks = list(pat.finditer(body))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        block = [ln for ln in (_md_plain(x) for x in body[m.end():end].splitlines()) if ln]
        title = " — ".join(block[:2])
        raw_id = m.group(1) + "-" + hashlib.sha1("\n".join(block).encode()).hexdigest()[:6]
        it = _item(raw_id, m.group(1), title, src["url"].removesuffix(".md"), " ".join(block), src["url"])
        if it:
            out.append(it)
    return out[: int(src.get("limit", 6))]


def parse_changelog_md(body: str, src: dict) -> list[dict]:
    """Changelog: one entry per version heading; the title carries the bullet
    that matches the source keywords best (the first bullet if none does)."""
    out = []
    kws = [k.lower() for k in src.get("keywords", [])]
    pat = re.compile(r"^##[ \t]+\[?v?(\d+\.\d+\.\d+[^\]\n]*?)\]?[ \t]*(?:-.*)?$", re.M)
    marks = list(pat.finditer(body))
    for i, m in enumerate(marks[: int(src.get("limit", 15))]):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        bullets = [_md_plain(x) for x in body[m.end():end].splitlines() if re.match(r"\s*[-*]\s+", x)]
        best = max(bullets, key=lambda b: _hits(b, kws), default="")  # max keeps the first on ties
        it = _item(m.group(1), "", f"v{m.group(1)}: {best}".rstrip(": "), "", " ".join(bullets), src["url"])
        if it:
            out.append(it)
    return out


def parse_llms_txt(body: str, src: dict) -> list[dict]:
    """llms.txt index: every ``- [title](url)`` line is a page; a new link is a new page."""
    out, seen = [], set()
    for title, url in re.findall(r"^\s*[-*]\s+\[([^\]]+)\]\((https?://[^)\s]+)\)", body, re.M):
        if url in seen:
            continue
        seen.add(url)
        it = _item(url, "", title, url, title, src["url"])
        if it:
            out.append(it)
    return out


def parse_sitemap(body: str, src: dict) -> list[dict]:
    """Sitemap: url + lastmod, kept only for the configured path parts, newest first."""
    wanted = src.get("path_filter") or []
    rows = []
    for loc, mod in re.findall(r"<loc>\s*([^<]+?)\s*</loc>(?:\s*<lastmod>\s*([^<]*?)\s*</lastmod>)?", body):
        loc = html.unescape(loc)
        if not wanted or any(p in urllib.parse.urlsplit(loc).path for p in wanted):
            rows.append((loc, mod))
    rows.sort(key=lambda r: (r[1], r[0]), reverse=True)
    out = []
    for loc, mod in rows[: int(src.get("limit", 25))]:
        slug = urllib.parse.urlsplit(loc).path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
        it = _item(loc, mod, slug, loc, slug, src["url"])
        if it:
            out.append(it)
    return out


def parse_status_json(body: str, src: dict) -> list[dict]:
    """Statuspage 'unresolved incidents' document."""
    out = []
    for inc in json.loads(body).get("incidents", []):
        it = _item(inc.get("id"), inc.get("created_at"), "Incident: " + str(inc.get("name", "")),
                   inc.get("shortlink") or "", inc.get("name"), src["url"])
        if it:
            out.append(it)
    return out


def parse_hf_papers(body: str, src: dict) -> list[dict]:
    """Hugging Face daily papers API; ``min_points`` filters on upvotes."""
    out = []
    floor = int(src.get("min_points", 0))
    for e in json.loads(body):
        p = e.get("paper") or {}
        pid = str(p.get("id") or "")
        if not re.fullmatch(r"[\w.\-]+", pid) or int(p.get("upvotes") or 0) < floor:
            continue
        text = " ".join([str(p.get("summary") or ""), str(p.get("ai_summary") or ""), " ".join(p.get("ai_keywords") or [])])
        it = _item(pid, e.get("publishedAt") or p.get("publishedAt"), e.get("title") or p.get("title"),
                   "https://huggingface.co/papers/" + pid, text, src["url"])
        if it:
            out.append(it)
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(body: str, src: dict) -> list[dict]:
    """RSS 2.0 or Atom (also used for the arXiv API, which answers in Atom)."""
    if "<!ENTITY" in body:  # entity expansion tricks: refuse rather than parse
        raise ValueError("entity declaration")
    root = ET.fromstring(body)
    out = []
    for node in root.iter():
        if _local(node.tag) not in ("item", "entry"):
            continue
        f: dict[str, str] = {}
        for ch in node:
            name = _local(ch.tag)
            if name == "link":
                href = ch.get("href") or (ch.text or "")
                if "link" not in f or ch.get("rel") == "alternate":
                    f["link"] = href.strip()
            elif name not in f:
                f[name] = ch.text or ""
        link = f.get("link", "")
        it = _item(f.get("guid") or f.get("id") or link, f.get("pubDate") or f.get("published") or f.get("updated"),
                   f.get("title"), link, " ".join([f.get("description", ""), f.get("summary", "")]), src["url"])
        if it:
            out.append(it)
    return out[: int(src.get("limit", 25))]


def parse_hn_algolia(body: str, src: dict) -> list[dict]:
    """Hacker News Algolia search; ``min_points`` filters on points."""
    out = []
    floor = int(src.get("min_points", 0))
    for h in json.loads(body).get("hits", []):
        oid = str(h.get("objectID") or "")
        if not re.fullmatch(r"\d+", oid) or int(h.get("points") or 0) < floor:
            continue
        it = _item(oid, h.get("created_at"), h.get("title"), "https://news.ycombinator.com/item?id=" + oid,
                   h.get("title"), src["url"])
        if it:
            out.append(it)
    return out


PARSERS: dict[str, Callable[[str, dict], list[dict]]] = {
    "relnotes_md": parse_relnotes_md,
    "changelog_md": parse_changelog_md,
    "llms_txt": parse_llms_txt,
    "sitemap": parse_sitemap,
    "status_json": parse_status_json,
    "hf_papers": parse_hf_papers,
    "feed": parse_feed,
    "arxiv_atom": parse_feed,
    "hn_algolia": parse_hn_algolia,
}


# ---------------------------------------------------------------- relevance
def relevance(item: dict, src: dict) -> tuple[int, list[str]] | None:
    """(score, matched keywords) when the item is worth a line, else None.

    A keyword in the title counts 2, elsewhere in the item's text 1. An empty
    keyword list means every new item qualifies. Official sources need one
    match (score >= 1); research and community sources need score >= 2, so a
    stray word in a summary is not enough.
    """
    kws = [k.lower() for k in src.get("keywords", [])]
    if not kws:
        return 0, []
    title = item["title"].lower()
    score, matched = 0, []
    for k in kws:
        if k in title:
            score += 2
        elif k in item["text"]:
            score += 1
        else:
            continue
        matched.append(k)
    need = 1 if src.get("trust") == "official" else 2
    return (score, matched) if score >= need else None


def _stable_id(source_id: str, raw_id: str) -> str:
    return hashlib.sha1(f"{source_id}\0{raw_id}".encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------- one source
def _due(prev: dict, src: dict, when: dt.datetime) -> bool:
    last = prev.get("last_checked")
    if not last:
        return True
    try:
        d = dt.datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except ValueError:
        return True
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    gap = (when - d).total_seconds()
    return gap < 0 or gap >= float(src.get("interval_hours", 1)) * 3600


def _check(src: dict, prev: dict, fetch: Fetch, allow: frozenset, stamp: str, timeout: float) -> dict:
    """Fetch and parse one source. Returns {state, new, error}; never raises."""
    state = dict(prev)
    state["last_checked"] = stamp
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"}
    if prev.get("etag"):
        headers["If-None-Match"] = prev["etag"]
    if prev.get("last_modified"):
        headers["If-Modified-Since"] = prev["last_modified"]
    try:
        status, hdrs, raw = _get(src["url"], headers, fetch, allow, timeout)
    except _Refused as e:
        state["last_status"] = "refused"
        return {"state": state, "new": [], "error": str(e)}
    except Exception as e:  # network trouble of any kind must not escape
        state["last_status"] = "error"
        reason = "timeout" if isinstance(e, TimeoutError) or "timed out" in str(e).lower() else type(e).__name__
        return {"state": state, "new": [], "error": f"fetch {reason}"}
    state["last_status"] = str(status)
    if status == 304:
        return {"state": state, "new": [], "error": None}
    if status != 200:
        return {"state": state, "new": [], "error": f"http {status}"}
    raw = raw[:MAX_BYTES]
    if hdrs.get("etag"):
        state["etag"] = hdrs["etag"]
    if hdrs.get("last-modified"):
        state["last_modified"] = hdrs["last-modified"]
    digest = hashlib.sha256(raw).hexdigest()
    if digest == prev.get("hash"):
        return {"state": state, "new": [], "error": None}
    parser = PARSERS.get(src.get("kind", ""))
    try:
        if parser is None:
            raise ValueError("unknown kind")
        items = parser(raw.decode("utf-8", "replace"), src)
    except Exception:  # a parser failure is data trouble, never a crash
        return {"state": state, "new": [], "error": "parse failed"}
    state["hash"] = digest
    for it in items:
        it["id"] = _stable_id(src["id"], it["raw_id"])
    old = [i for i in prev.get("seen", []) if isinstance(i, str)]
    known = set(old)
    fresh = [it for it in items if it["id"] not in known]
    cap = max(int(src.get("seen_cap", DEFAULT_SEEN_CAP)), len(items))
    state["seen"] = list(dict.fromkeys([it["id"] for it in items] + old))[:cap]
    if "seen" not in prev:  # first run: remember the present, report nothing
        state["last_status"] = "baseline"
        fresh = []
    return {"state": state, "new": fresh, "error": None}


# ---------------------------------------------------------------- run
def _line(it: dict) -> str:
    return " · ".join([it["source"], it["date"] or "-", it["title"], it["url"],
                       "why: " + (", ".join(it["matched"]) or "new")])


def _write_leads(root: Path, items: list[dict], when: dt.datetime) -> None:
    """Append one ``lead`` record per relevant new item (no bodies), skipping ids
    already in today's file so a forced re-run cannot duplicate them."""
    if not items:
        return
    path = root / "learning" / "inbox" / f"{when.strftime('%Y-%m-%d')}-radar.jsonl"
    have = {r.get("id") for r in c.read_jsonl(path)}
    at = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    for it in items:
        if it["id"] in have:
            continue
        c.append_jsonl(path, {"kind": "lead", "session": c.session_id(), "at": at, "id": it["id"],
                              "source": it["source"], "trust": it["trust"], "date": it["date"],
                              "title": it["title"], "url": it["url"], "matched": it["matched"]})


def run(brain_root: Path | str | None = None, force: bool = False, max_lines: int = 12,
        max_seconds: float = 20, trust: str | None = None, fetch: Fetch | None = None,
        now: dt.datetime | None = None) -> dict:
    """Check the due sources and report what is new.

    Returns ``lines`` (what to show), ``new`` (the same items as dicts),
    ``checked``/``skipped`` (source counts), ``errors`` (short strings) and
    ``seconds``. ``fetch(url, headers, timeout) -> (status, headers, body)`` can
    be injected so tests never touch the network. Never raises.
    """
    t0 = time.monotonic()
    root = Path(brain_root or c.BRAIN_ROOT)
    when = now or c.now()
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    result: dict = {"lines": [], "new": [], "checked": 0, "skipped": 0, "errors": [], "seconds": 0.0}
    try:
        _run(root, force, max_lines, max_seconds, trust, fetch or default_fetch, when, t0, result)
    except Exception as e:  # last line of defence: the radar degrades to silence
        result["errors"].append(f"radar: {type(e).__name__}")
    result["seconds"] = round(time.monotonic() - t0, 2)
    return result


def _start_daemon_checks(due: list[dict], state: dict, fetch: Fetch, allow: frozenset, stamp: str,
                         timeout: float) -> dict[str, cf.Future]:
    """Run the checks on daemon threads, at most WORKERS at a time. A thread
    pool is joined when the interpreter exits, so one slow source held `boot`
    open for its full request timeout after the radar had given up (review
    M15: measured 6.1 s to exit for a 1 s budget). Daemon threads are not."""
    import threading
    futs = {s["id"]: cf.Future() for s in due}
    gate = threading.Semaphore(WORKERS)

    def work(s: dict) -> None:
        fut = futs[s["id"]]
        with gate:
            if not fut.set_running_or_notify_cancel():
                return
            try:
                fut.set_result(_check(s, state.get(s["id"], {}), fetch, allow, stamp, timeout))
            except BaseException as e:  # reported as "failed" by the caller
                fut.set_exception(e)

    for s in due:
        threading.Thread(target=work, args=(s,), daemon=True, name=f"radar-{s['id']}").start()
    return futs


def _run(root: Path, force: bool, max_lines: int, max_seconds: float, trust: str | None,
         fetch: Fetch, when: dt.datetime, t0: float, result: dict) -> None:
    cfg = c.read_json(root / SOURCES_FILE, None)
    if not isinstance(cfg, dict) or not isinstance(cfg.get("sources"), list):
        result["errors"].append("sources file missing or invalid")
        return
    allow = frozenset(str(h).lower() for h in cfg.get("allowlist", []))
    sources = [s for s in cfg["sources"] if isinstance(s, dict) and s.get("id") and s.get("url")]
    ids = {s["id"] for s in sources}
    if trust:
        sources = [s for s in sources if s.get("trust") == trust]
    state_path = root / STATE_FILE
    state = read_state(root)
    state = {k: v for k, v in state.items() if k in ids and isinstance(v, dict)} if isinstance(state, dict) else {}
    stamp = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    timeout = min(REQUEST_TIMEOUT, max(1.0, float(max_seconds)))

    due = []
    for s in sources:
        if force or _due(state.get(s["id"], {}), s, when):
            due.append(s)
        else:
            result["skipped"] += 1
    if not due:
        return

    futs = _start_daemon_checks(due, state, fetch, allow, stamp, timeout)
    cf.wait(list(futs.values()), timeout=max(0.0, max_seconds - (time.monotonic() - t0)))

    candidates: list[tuple[int, dict, int]] = []
    leads: list[dict] = []  # every relevant new item; max_lines caps only what is printed
    for order, s in enumerate(due):
        fut = futs[s["id"]]
        if not fut.done() or fut.cancelled():
            result["errors"].append(f"{s['id']}: timeout")
            continue
        try:
            res = fut.result()
        except Exception:
            result["errors"].append(f"{s['id']}: failed")
            continue
        result["checked"] += 1
        state[s["id"]] = res["state"]
        if res["error"]:
            result["errors"].append(c.clip(f"{s['id']}: {res['error']}", 80))
        picked = []
        for it in res["new"]:
            rel = relevance(it, s)
            if rel:
                picked.append({"id": it["id"], "source": s["id"], "trust": s.get("trust", "community"),
                               "date": it["date"], "title": it["title"], "url": it["url"],
                               "matched": rel[1][:4], "_score": rel[0]})
        picked.sort(key=lambda x: x["id"])
        picked.sort(key=lambda x: x["date"], reverse=True)
        picked.sort(key=lambda x: -x["_score"])
        leads += [{k: v for k, v in p.items() if k != "_score"} for p in picked]
        candidates += [(order, p, 0) for p in picked[: int(s.get("max_lines", DEFAULT_SOURCE_LINES))]]

    # Global order: trust, then score, then newest date; ties keep source order.
    pool = [p for _, p, _ in sorted(candidates, key=lambda t: (t[0], t[1]["id"]))]
    pool.sort(key=lambda p: p["date"], reverse=True)
    pool.sort(key=lambda p: -p["_score"])
    pool.sort(key=lambda p: TRUST_RANK.get(p["trust"], 9))
    chosen = pool[: max(0, int(max_lines))]
    for p in chosen:
        p.pop("_score", None)
    result["new"] = chosen
    result["lines"] = [_line(p) for p in chosen]

    try:
        write_state(root, state)
        _write_leads(root, leads, when)
    except OSError as e:
        result["errors"].append(f"write failed: {type(e).__name__}")


def due_lines(max_seconds: float = 4, max_lines: int = 2, trust: str | None = "official",
              brain_root: Path | str | None = None) -> list[str]:
    """Lines from the sources that are due, for session start.

    Called from ``boot``, so it must never break or slow it: it returns [] on
    any exception, and when ``BRAIN_NO_NETWORK`` is set it does not even try.
    """
    if os.environ.get("BRAIN_NO_NETWORK"):
        return []
    try:
        return list(run(brain_root, max_lines=max_lines, max_seconds=max_seconds, trust=trust)["lines"])
    except Exception:
        return []


# ---------------------------------------------------------------- cli
def cmd_radar(args) -> int:
    if os.environ.get("BRAIN_NO_NETWORK"):
        print("radar: network use is switched off (BRAIN_NO_NETWORK is set); nothing checked")
        return 0
    res = run(force=args.force, max_lines=args.max, trust=args.trust)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    for ln in res["lines"]:
        print(ln)
    if not res["lines"]:
        print("radar: nothing new")
    print(f"radar: {res['checked']} checked, {res['skipped']} skipped, {len(res['new'])} new, "
          f"{res['seconds']}s, {len(res['errors'])} errors")
    for e in res["errors"][:3]:
        print(f"  {e}")
    return 0


def register(sub) -> None:
    p = sub.add_parser("radar", help="check official and research sources for what is new (leads, not facts)")
    p.add_argument("--force", action="store_true", help="ignore the re-check intervals")
    p.add_argument("--max", type=int, default=12, help="most lines to print (default 12)")
    p.add_argument("--trust", choices=sorted(TRUST_RANK), help="only sources of this trust level")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_radar)
