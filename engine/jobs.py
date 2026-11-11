"""Job search with Claude: the uses catalog, a ranking for one person, job
discovery from public applicant-tracking feeds, posting fit, the funnel, and
the job-search project kit.

Why: a job search has hundreds of things Claude can help with, and their
value differs by orders of magnitude for a given person (a referral moves
offer odds several times more than a reworded bullet). Ranking them by
evidence, fit and cost, and re-ranking as the person's own funnel shows where
it leaks, puts effort where it pays. Postings are read only from public feeds
the employers publish for that purpose (ATS job-board APIs, schema.org
JobPosting data, sitemaps); nothing logs in, solves a CAPTCHA or ignores
robots.txt.

Personal data never lives in the brain: the profile, tracker and documents
belong to the job-search project (`brain jobs init`).
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

from . import common as c

KIT = Path(__file__).resolve().parents[1] / "kits" / "jobsearch"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,60}$")
FIELDS = ("id", "title", "category", "stage", "how", "impact", "evidence", "lever", "effort", "repeat", "fits", "avoid", "surface")


class JobsError(Exception):
    pass


# ---------------------------------------------------------------- catalog
def taxonomy(kit: Path | None = None) -> dict:
    t = c.read_json(Path(kit or KIT) / "taxonomy.json", None)
    if not isinstance(t, dict):
        raise JobsError("kits/jobsearch/taxonomy.json is missing or invalid")
    return t


def load_uses(kit: Path | None = None, files: list[Path] | None = None) -> list[dict]:
    root = Path(kit or KIT)
    paths = files or sorted((root / "uses").glob("*.jsonl"))
    out = []
    for p in paths:
        for i, row in enumerate(c.read_jsonl(p)):
            if isinstance(row, dict):
                row = dict(row)
                row["_src"] = f"{Path(p).name}:{i + 1}"
                out.append(row)
    return out


def _norm_words(text: str) -> set[str]:
    stop = {"a", "an", "the", "to", "for", "of", "and", "or", "in", "on", "with", "your", "you", "from", "by", "at", "as", "into", "each", "every"}
    return {w for w in re.findall(r"[a-z0-9]+", str(text).lower()) if w not in stop}


def validate(uses: list[dict], tax: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors: schema, enums, duplicate ids or titles.
    Warnings: near-duplicate titles (word overlap >= 0.8)."""
    errs, warns = [], []
    cats, stages, levers = set(tax["categories"]), set(tax["stages"]), {k for k in tax["levers"] if not k.startswith("_")}
    tags, repeats, grades, surfaces = set(tax["tags"]), set(tax["repeat"]), set(tax["evidence"]), set(tax["surfaces"])
    ids, titles = {}, {}
    for u in uses:
        where = u.get("_src", "?")
        uid = u.get("id")
        missing = [f for f in FIELDS if f not in u]
        if missing:
            errs.append(f"{where}: missing {', '.join(missing)}")
            continue
        if not isinstance(uid, str) or not ID_RE.match(uid):
            errs.append(f"{where}: bad id {uid!r} (lowercase words joined by hyphens)")
        elif uid in ids:
            errs.append(f"{where}: duplicate id {uid} (also {ids[uid]})")
        else:
            ids[uid] = where
        title = str(u["title"]).strip()
        if not 10 <= len(title) <= 140:
            errs.append(f"{where}: title must be 10-140 characters")
        key = " ".join(sorted(_norm_words(title)))
        if key in titles:
            errs.append(f"{where}: duplicate title (also {titles[key]})")
        titles.setdefault(key, where)
        if not 20 <= len(str(u["how"])) <= 400:
            errs.append(f"{where}: 'how' must be 20-400 characters")
        for f, allowed in (("category", cats), ("stage", stages), ("lever", levers), ("repeat", repeats), ("evidence", grades), ("surface", surfaces)):
            if u[f] not in allowed:
                errs.append(f"{where}: {f} {u[f]!r} is not in the taxonomy")
        if not (isinstance(u["impact"], int) and 1 <= u["impact"] <= 5):
            errs.append(f"{where}: impact must be an integer 1-5")
        if not (isinstance(u["effort"], int) and 1 <= u["effort"] <= 2400):
            errs.append(f"{where}: effort must be whole minutes, 1-2400")
        for f in ("fits", "avoid"):
            if not isinstance(u[f], list) or any(t not in tags for t in u[f]):
                errs.append(f"{where}: {f} must be a list of taxonomy tags")
    # Near duplicates: same category, word overlap of titles >= 0.8.
    by_cat: dict[str, list[tuple[str, set]]] = {}
    for u in uses:
        if isinstance(u.get("title"), str):
            by_cat.setdefault(u.get("category"), []).append((u.get("_src", "?"), _norm_words(u["title"])))
    for cat, rows in by_cat.items():
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i][1], rows[j][1]
                if a and b and len(a & b) / len(a | b) >= 0.8:
                    warns.append(f"{rows[j][0]}: near-duplicate of {rows[i][0]}")
    return errs, warns


# ---------------------------------------------------------------- profile
PROFILE_KEYS = ("tags", "targets", "avoid_roles", "locations", "min_salary", "hours_per_week", "funnel")


def load_profile(path: Path) -> dict:
    p = c.read_json(Path(path), None)
    if not isinstance(p, dict):
        raise JobsError(f"{path}: not a profile (JSON object expected)")
    p.setdefault("tags", [])
    return p


def funnel_of(profile: dict, tracker_rows: list[dict] | None = None) -> dict:
    """Counts at each funnel step, from the tracker when there is one, else
    from the profile's declared funnel."""
    steps = ("applied", "responded", "interviewed", "offered")
    if tracker_rows:
        order = {"applied": 0, "responded": 1, "screen": 1, "interview": 2, "interviewed": 2, "final": 2, "offer": 3, "offered": 3, "accepted": 3}
        counts = dict.fromkeys(steps, 0)
        for r in tracker_rows:
            reached = order.get(str(r.get("status", "")).strip().lower())
            if reached is None:
                continue
            for k in steps[: reached + 1]:
                counts[k] += 1
        return counts
    f = profile.get("funnel") if isinstance(profile.get("funnel"), dict) else {}
    return {k: int(f.get(k, 0) or 0) for k in steps}


# Benchmarks for the funnel; replaced by the figures in the evidence memo
# through kits/jobsearch/benchmarks.json when it exists.
BENCH = {"respond": 0.04, "interview": 0.5, "offer": 0.1}


def stage_weights(funnel: dict, kit: Path | None = None) -> tuple[dict, str]:
    """Where the search leaks. Each stage's weight is benchmark / observed
    conversion, shrunk toward 1 with a Beta prior of 10 pseudo-trials at the
    benchmark, clipped to [0.6, 2.5]. Without applications the search is at
    its start, so direction and materials come first."""
    bench = dict(BENCH)
    bench.update({k: v for k, v in (c.read_json(Path(kit or KIT) / "benchmarks.json", {}) or {}).get("funnel", {}).items() if isinstance(v, (int, float))})
    w = {s: 1.0 for s in ("direction", "materials", "discovery", "outreach", "application", "interview", "offer", "transition", "ongoing")}
    applied = funnel.get("applied", 0)
    if applied < 5:
        w.update(direction=1.8, materials=1.6, discovery=1.4, outreach=1.3, interview=0.9, offer=0.7, transition=0.5)
        return w, f"{applied} application(s): early search, so direction and materials first"

    def ratio(hits, n, b):
        k = 10.0
        post = (hits + k * b) / (n + k)
        return max(0.6, min(2.5, b / max(post, 1e-6)))

    r_resp = ratio(funnel.get("responded", 0), applied, bench["respond"])
    r_int = ratio(funnel.get("interviewed", 0), max(funnel.get("responded", 0), 1), bench["interview"])
    r_off = ratio(funnel.get("offered", 0), max(funnel.get("interviewed", 0), 1), bench["offer"])
    # Few responses: the materials, targeting and channel are the leak.
    w.update(materials=r_resp, outreach=r_resp, direction=(r_resp + 1) / 2, discovery=(r_resp + 1) / 2,
             application=(r_resp + 1) / 2, interview=max(r_int, r_off), offer=1.0 + 0.3 * (funnel.get("offered", 0) > 0))
    leak = max(("responses", r_resp), ("interviews", r_int), ("offers", r_off), key=lambda x: x[1])
    return w, f"funnel {applied}/{funnel.get('responded', 0)}/{funnel.get('interviewed', 0)}/{funnel.get('offered', 0)}: weakest step is {leak[0]} (x{leak[1]:.2f})"


# ---------------------------------------------------------------- rank
REPEAT_USES = {"once": 1, "weekly": 4, "daily": 10, "per_application": 8, "per_company": 6, "per_interview": 3, "per_offer": 1}


def score_use(u: dict, profile: dict, tax: dict, weights: dict) -> dict:
    """Expected value per hour, with every factor kept so the order can be
    explained. value = 1.6^impact x evidence x lever x fit x stage; cost =
    hours over the search (effort x expected repeats, capped by the person's
    hours a week). final = value^0.8 / cost^0.2: value dominates, but a
    two-minute task does not beat a two-hour one on cheapness alone."""
    tags = set(profile.get("tags", []))
    impact = 1.6 ** int(u["impact"])
    ev = float(tax["evidence"].get(u["evidence"], 0.5))
    lever = float(tax["levers"].get(u["lever"], 1.0))
    fits = set(u.get("fits", []))
    avoid = set(u.get("avoid", []))
    matched = fits & tags
    # Coverage, not count: a use written for "relocating regulated people"
    # fits half as well someone who is only one of the two. A use with no
    # audience fits everyone at 1.0.
    if not fits:
        fit = 1.0
    elif matched:
        fit = 0.8 + 0.6 * len(matched) / len(fits) + 0.05 * min(len(matched), 3)
    else:
        fit = 0.55  # written for someone else
    if avoid & tags:
        fit *= 0.08  # actively wrong for this person
    stage = float(weights.get(u["stage"], 1.0))
    value = impact * ev * lever * fit * stage
    reps = REPEAT_USES.get(u["repeat"], 1)
    hours = max(0.05, u["effort"] / 60.0) * reps
    hpw = profile.get("hours_per_week")
    if isinstance(hpw, (int, float)) and hpw > 0 and hours > hpw * 4:
        value *= 0.7  # more than a month of the person's search time
    final = value ** 0.8 / hours ** 0.2
    return {"id": u["id"], "score": round(final, 4), "value": round(value, 3), "hours": round(hours, 2),
            "factors": {"impact": round(impact, 2), "evidence": ev, "lever": lever, "fit": round(fit, 3), "stage": stage},
            "matched": sorted(matched)}


def rank(uses: list[dict], profile: dict, tax: dict, weights: dict, diversity: float = 0.92) -> list[dict]:
    """Uses ordered by score with a category-diversity pass (maximal marginal
    relevance): each further pick from a category already chosen in the last
    20 picks is discounted by ``diversity`` per earlier pick, so the top of the
    list covers the search instead of one corner of it. Ties break on id."""
    scored = {u["id"]: (u, score_use(u, profile, tax, weights)) for u in uses}
    pool = sorted(scored.values(), key=lambda x: (-x[1]["score"], x[0]["id"]))
    out, recent = [], []
    while pool:
        best_i, best_v = 0, -1.0
        for i, (u, s) in enumerate(pool[:60]):
            v = s["score"] * diversity ** recent[-20:].count(u["category"])
            if v > best_v + 1e-12:
                best_i, best_v = i, v
        u, s = pool.pop(best_i)
        recent.append(u["category"])
        out.append({**s, "rank": len(out) + 1, "title": u["title"], "category": u["category"], "stage": u["stage"],
                    "how": u["how"], "surface": u["surface"], "repeat": u["repeat"], "effort": u["effort"], "evidence_grade": u["evidence"]})
    return out


def render_ranked(rows: list[dict], basis: str, top: int | None = None) -> str:
    lines = ["# Ranked uses of Claude for this job search", "",
             f"Order: expected value per hour (`brain jobs rank`). {basis}.",
             "Score = (1.6^impact x evidence x lever x fit x stage)^0.8 / hours^0.2, then a diversity pass across categories.", "",
             "| # | Use | Category | Stage | How with Claude | Effort | Evidence | Score |", "|---|---|---|---|---|---|---|---|"]
    for r in rows[: top or len(rows)]:
        how = r["how"].replace("|", "/")
        lines.append(f"| {r['rank']} | {r['title']} | {r['category']} | {r['stage']} | {how} | {r['effort']} min, {r['repeat']} | {r['evidence_grade']} | {r['score']:.2f} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- kit
VENDORED = ("jobfeeds.py", "mddocx.py")


def init_project(project: Path, title: str = "Job search", update: bool = False) -> list[str]:
    """Install the job-search kit in a project: the brain's contract (family
    career, gate tools/check.py), the template files that are not there yet
    (nothing existing is overwritten), and fresh copies of the standalone
    tools. ``update`` only refreshes the tools."""
    from . import contract
    project = Path(project)
    made: list[str] = []
    if not update:
        if not c.is_managed(project):
            # The released manifest schema knows five families, so the
            # project is "knowledge" with kit "jobsearch"; routing reads the
            # kit and treats requests here as career work.
            made += contract.init(project, title, "knowledge", {"kit": "jobsearch",
                "gates": [{"id": "check", "kind": "command", "command": "python3 tools/check.py"}],
                "release": {"rule": "main-on-green", "branch": "main", "live_url": ""}})
        tpl = KIT / "template"
        for src in sorted(tpl.rglob("*")):
            if src.is_dir():
                continue
            rel = src.relative_to(tpl)
            dst = project / rel
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(src.read_bytes())
                made.append(str(rel))
        if not (project / "profile.json").exists():
            (project / "profile.json").write_bytes((tpl / "profile.example.json").read_bytes())
            made.append("profile.json")
    tools = project / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    for name in VENDORED:
        new = (here / name).read_bytes()
        dst = tools / name
        if not dst.exists() or dst.read_bytes() != new:
            dst.write_bytes(new)
            made.append(f"tools/{name}")
    return made


# ---------------------------------------------------------------- tracker
STATUSES = ("saved", "applied", "responded", "screen", "interview", "final", "offer", "accepted", "rejected", "withdrawn", "ghosted")


def track(project: Path, company: str, role: str, status: str, url: str = "", note: str = "", channel: str = "") -> dict:
    """Add or move one application. The key is company + role; a later status
    replaces the earlier one and the history keeps each change with its date."""
    if status not in STATUSES:
        raise JobsError(f"status must be one of {', '.join(STATUSES)}")
    path = Path(project) / "tracker.jsonl"
    rows = c.read_jsonl(path)
    key = f"{company.strip().lower()}|{role.strip().lower()}"
    row = next((r for r in rows if r.get("key") == key), None)
    if row is None:
        row = {"key": key, "company": company.strip(), "role": role.strip(), "history": []}
        rows.append(row)
    # A rejection after an interview still counts the interview in the funnel.
    order = {"applied": 0, "responded": 1, "screen": 1, "interview": 2, "final": 2, "offer": 3, "accepted": 3}
    if status in order and order[status] >= order.get(row.get("reached", ""), -1):
        row["reached"] = status
    row["status"] = status
    row["history"].append({"on": c.today(), "status": status})
    for k, v in (("url", url), ("note", note), ("channel", channel)):
        if v:
            row[k] = v
    c.write_text(path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))
    return row


def funnel_rows(rows: list[dict]) -> list[dict]:
    """Rows whose furthest stage counts for the funnel (``reached``)."""
    return [dict(r, status=r.get("reached") or r.get("status")) for r in rows]


def tracker_md(project: Path) -> str:
    rows = c.read_jsonl(Path(project) / "tracker.jsonl")
    f = funnel_of({}, funnel_rows(rows)) if rows else {"applied": 0, "responded": 0, "interviewed": 0, "offered": 0}
    _, basis = stage_weights(f)
    rate = lambda a, b: f"{a / b:.0%}" if b else "-"
    by_channel: dict[str, list[int]] = {}
    for r in funnel_rows(rows):
        ch = r.get("channel") or "unknown"
        cell = by_channel.setdefault(ch, [0, 0])
        if r["status"] in ("applied", "responded", "screen", "interview", "final", "offer", "accepted"):
            cell[0] += 1
        if r["status"] in ("responded", "screen", "interview", "final", "offer", "accepted"):
            cell[1] += 1
    lines = ["# Tracker", "", f"Funnel: {f['applied']} applied, {f['responded']} responded ({rate(f['responded'], f['applied'])}), "
             f"{f['interviewed']} interviewed ({rate(f['interviewed'], f['responded'])}), {f['offered']} offers ({rate(f['offered'], f['interviewed'])}).",
             f"Benchmarks: about {BENCH['respond']:.0%} of cold applications get a response; referrals do several times better. {basis}.", ""]
    if by_channel:
        lines += ["| Channel | Applied | Responded | Rate |", "|---|---|---|---|"]
        lines += [f"| {ch} | {a} | {r} | {rate(r, a)} |" for ch, (a, r) in sorted(by_channel.items())]
        lines.append("")
    lines += ["| Company | Role | Status | Since | Channel |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["history"][-1]["on"] if r.get("history") else "", reverse=True):
        role = f"[{r['role']}]({r['url']})" if r.get("url") else r["role"]
        lines.append(f"| {r['company']} | {role} | {r.get('status')} | {r['history'][-1]['on'] if r.get('history') else ''} | {r.get('channel', '')} |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- cli
def cmd_uses(args) -> int:
    tax = taxonomy()
    files = [Path(f) for f in args.file] if args.file else None
    uses = load_uses(files=files)
    errs, warns = validate(uses, tax)
    per = {}
    for u in uses:
        per[u.get("category")] = per.get(u.get("category"), 0) + 1
    print(f"uses: {len(uses)} in {len(files) if files else len(list((KIT / 'uses').glob('*.jsonl')))} file(s) · "
          + ", ".join(f"{k} {v}" for k, v in sorted(per.items(), key=lambda kv: str(kv[0]))))
    for e in errs[:25]:
        print(" - error:", e)
    for w in warns[: args.warnings]:
        print(" - near duplicate:", w)
    if len(errs) > 25:
        print(f" ... {len(errs) - 25} more errors")
    short = len(uses) < args.min
    if short:
        print(f"only {len(uses)} uses; {args.min} required")
    return 1 if errs or short or (args.strict and warns) else 0


def cmd_rank(args) -> int:
    tax = taxonomy()
    uses = load_uses()
    errs, _ = validate(uses, tax)
    if errs:
        print(f"the catalog has {len(errs)} error(s); run `brain jobs uses` first")
        return 1
    try:
        profile = load_profile(Path(args.profile))
    except JobsError as e:
        print(e)
        return 1
    tracker = funnel_rows(c.read_jsonl(Path(args.tracker))) if args.tracker and Path(args.tracker).is_file() else None
    weights, basis = stage_weights(funnel_of(profile, tracker))
    rows = rank(uses, profile, tax, weights)
    if args.out:
        out = Path(args.out)
        if out.suffix == ".json":
            c.write_json(out, {"basis": basis, "count": len(rows), "ranked": rows})
        else:
            c.write_text(out, render_ranked(rows, basis))
        print(f"ranked {len(rows)} uses into {out} · {basis}")
    for r in rows[: args.top]:
        print(f"{r['rank']:>4}. {r['title']} [{r['category']}] score {r['score']:.2f}")
    return 0


def cmd_init(args) -> int:
    project = Path(args.path).resolve()
    if not project.is_dir():
        print(f"not a folder: {project}")
        return 1
    if project == c.BRAIN_ROOT.resolve():
        print("refusing: the job-search kit holds personal data and never goes in the brain")
        return 1
    made = init_project(project, args.title, update=args.update)
    print(f"job-search kit in {project.name}: " + (f"{len(made)} file(s) added or refreshed" if made else "already complete"))
    for m in made[:30]:
        print("  +", m)
    if not args.update:
        print("next: fill profile.json, add employers to data/companies.jsonl, then `python3 tools/jobfeeds.py sweep`")
    return 0


def cmd_track(args) -> int:
    project = Path(args.project or ".").resolve()
    if args.company:
        try:
            row = track(project, args.company, args.role or "(unspecified)", args.status, args.url or "", args.note or "", args.channel or "")
        except JobsError as e:
            print(e)
            return 1
        print(f"{row['company']} · {row['role']}: {row['status']}")
    c.write_text(project / "TRACKER.md", tracker_md(project))
    print(tracker_md(project).splitlines()[2])
    return 0


def register(sub) -> None:
    p = sub.add_parser("jobs", help="job search: uses catalog, ranking, job discovery, posting fit, project kit")
    s = p.add_subparsers(dest="jobs_cmd")
    u = s.add_parser("uses", help="validate the uses catalog and count it")
    u.add_argument("--file", action="append", help="check only these files")
    u.add_argument("--min", type=int, default=0, help="fail below this many uses")
    u.add_argument("--warnings", type=int, default=10)
    u.add_argument("--strict", action="store_true", help="near duplicates fail too")
    u.set_defaults(func=cmd_uses)
    r = s.add_parser("rank", help="rank every use for one person's profile and funnel")
    r.add_argument("--profile", required=True)
    r.add_argument("--tracker", help="the project's tracker (jsonl) for the funnel")
    r.add_argument("--top", type=int, default=20)
    r.add_argument("--out", help="write the full ranking (.md or .json)")
    r.set_defaults(func=cmd_rank)
    i = s.add_parser("init", help="install the job-search kit in a project folder (never the brain)")
    i.add_argument("path")
    i.add_argument("--title", default="Job search")
    i.add_argument("--update", action="store_true", help="only refresh tools/jobfeeds.py and tools/mddocx.py")
    i.set_defaults(func=cmd_init)
    t = s.add_parser("track", help="record an application's status and rewrite TRACKER.md")
    t.add_argument("--project", default=".")
    t.add_argument("--company")
    t.add_argument("--role")
    t.add_argument("--status", default="applied", choices=STATUSES)
    t.add_argument("--url")
    t.add_argument("--note")
    t.add_argument("--channel", help="how it came: cold, referral, recruiter, outreach, agency, event, internal")
    t.set_defaults(func=cmd_track)
