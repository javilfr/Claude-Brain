"""Project state: one checkpoint file, the owner's status page, and handover.

``.brain/STATE.md`` is the only place a project's position is recorded. An
earlier project kept status in five files that ended up contradicting each
other; here everything else (``STATUS.md``, the handover note) is generated
from this file.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import common as c

FIELDS = ("contract", "stage", "tier", "item", "last_done", "next", "blockers", "session", "updated")
STAGES = ("intake", "requirements", "research", "plan", "build", "verify", "deliver", "learn", "done")
LEASE_MINUTES = 120  # another session that checkpointed this recently is probably still working
LOG_KEEP = 30


def state_path(project: Path) -> Path:
    return Path(project) / ".brain" / "STATE.md"


def read_state(project: Path) -> dict:
    """Parse STATE.md into fields, notes and log lines. Missing file gives defaults."""
    text = c.read_text(state_path(project))
    st = {k: "" for k in FIELDS}
    st.update({"notes": "", "log": []})
    section = "head"
    notes: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip().lower()
            continue
        if section == "head":
            m = re.match(r"^([a-z_]+):\s?(.*)$", line)
            if m and m.group(1) in FIELDS:
                st[m.group(1)] = m.group(2).strip()
        elif section == "notes":
            notes.append(line)
        elif section == "log" and line.startswith("- "):
            st["log"].append(line[2:])
    st["notes"] = "\n".join(notes).strip()
    st["next_list"] = [x.strip() for x in st["next"].split(";") if x.strip()]
    return st


def write_state(project: Path, st: dict) -> None:
    head = "\n".join(f"{k}: {st.get(k, '')}".rstrip() for k in FIELDS)
    log = "\n".join(f"- {l}" for l in st.get("log", [])[-LOG_KEEP:])
    text = (
        "# State\n\nThe single checkpoint for this project. Written by `brain checkpoint`; read by `brain boot`.\n\n"
        f"{head}\n\n## Notes\n\n{st.get('notes', '').strip()}\n\n## Log\n\n{log}\n"
    )
    c.write_text(state_path(project), text)


def lease_warning(st: dict) -> str:
    """A line of warning when a different session checkpointed recently."""
    other = st.get("session", "")
    if not other or other in ("none", c.session_id()):
        return ""
    try:
        import datetime as dt
        then = dt.datetime.fromisoformat(st.get("updated", "").replace("Z", "+00:00"))
        mins = (c.now() - then).total_seconds() / 60
    except ValueError:
        return ""
    if mins < LEASE_MINUTES:
        return f"another session ({other[:8]}) checkpointed {int(mins)} min ago: two chats on one project cause conflicts; continue in one"
    return ""


def checkpoint(project: Path, item: str | None = None, done: str | None = None, nxt: list[str] | None = None,
               stage: str | None = None, tier: int | None = None, note: str | None = None,
               blockers: str | None = None, clear_notes: bool = False) -> dict:
    st = read_state(project)
    st["contract"] = st["contract"] or str(c.CONTRACT_VERSION)
    if done:
        st["last_done"] = done
        st["log"].append(f"{c.today()} done: {c.clip(done, 120)}")
        if not item and st.get("item") == done:
            st["item"] = "none"
    if item is not None:
        st["item"] = c.clip(item, 160)
    if nxt is not None:
        st["next"] = "; ".join(c.clip(n, 100).replace(";", ",") for n in nxt[:3])
    if stage:
        st["stage"] = stage
        m = c.load_manifest(project)
        if m and m.get("stage") != stage:
            m["stage"] = stage
            c.write_json(Path(project) / ".brain" / "project.json", m)
    if tier is not None:
        st["tier"] = str(tier)
    if blockers is not None:
        st["blockers"] = c.clip(blockers, 160) or "none"
    if clear_notes:
        st["notes"] = ""
    if note:
        st["notes"] = (st["notes"] + "\n" if st["notes"] else "") + f"- {c.clip(note, 300)}"
    st["session"] = c.session_id()
    st["updated"] = c.now_iso()
    write_state(project, st)
    return st


# ---------------------------------------------------------------- owner files
def open_needs(project: Path) -> list[str]:
    """Titles of NEEDS_YOU items that have no RESOLVED line under them."""
    text = c.read_text(Path(project) / "NEEDS_YOU.md")
    out, title, resolved = [], None, False
    for line in text.splitlines() + ["## end"]:
        if line.startswith("## "):
            if title and not resolved:
                out.append(title)
            title, resolved = line[3:].strip(), False
            if title == "end":
                title = None
        elif "RESOLVED" in line.upper():
            resolved = True
    return out


def req_counts(project: Path) -> dict:
    rows = c.read_jsonl(Path(project) / ".brain" / "requirements.jsonl")
    out = {"total": len(rows), "done": 0, "open": 0, "dropped": 0}
    for r in rows:
        out[r.get("status", "open") if r.get("status") in ("done", "dropped") else "open"] += 1
    return out


def last_run(project: Path) -> dict:
    logs = sorted((Path(project) / ".brain" / "log").glob("*-*.json"))
    return c.read_json(logs[-1], {}) if logs else {}


def project_cost(project: Path) -> tuple[float, int]:
    total, n = 0.0, 0
    for f in (Path(project) / ".brain" / "log").glob("*-*.json"):
        rec = c.read_json(f, {}) or {}
        cost = (rec.get("totals") or {}).get("cost")
        if isinstance(cost, (int, float)):
            total += cost
            n += 1
    return total, n


def write_status(project: Path) -> str:
    """Generate the owner's STATUS.md (at most 40 lines) from state and logs."""
    project = Path(project)
    m, st = c.load_manifest(project), read_state(project)
    title = m.get("project", {}).get("title", project.name)
    rq, needs, run = req_counts(project), open_needs(project), last_run(project)
    cost, sessions = project_cost(project)
    lines = [f"# Status: {title}", "", f"Updated {st.get('updated') or c.now_iso()} · stage: {st.get('stage') or m.get('stage', 'intake')}", ""]
    lines += ["## Where things stand", "", f"- Working on: {st.get('item') or 'nothing yet'}", f"- Last finished: {st.get('last_done') or 'nothing yet'}"]
    if st["next_list"]:
        lines.append("- Next: " + "; ".join(st["next_list"]))
    if st.get("blockers") and st["blockers"] != "none":
        lines.append(f"- Blocked: {st['blockers']}")
    if rq["total"]:
        lines.append(f"- Requirements: {rq['done']} of {rq['total']} done with evidence, {rq['open']} open" + (f", {rq['dropped']} dropped" if rq["dropped"] else ""))
    lines += ["", "## Needs you", ""]
    lines += [f"- {n}" for n in needs[:8]] if needs else ["- Nothing right now."]
    if needs:
        lines.append("\nDetails and click steps are in `NEEDS_YOU.md`.")
    lines += ["", "## Cost", ""]
    if run.get("totals"):
        t = run["totals"]
        lines.append(f"- Last session: about ${t.get('cost', 0):.2f} at list prices, {int(t.get('out', 0)):,} output tokens, {run.get('helpers', 0)} helper(s)")
    if sessions:
        lines.append(f"- Project to date: about ${cost:.2f} at list prices over {sessions} recorded session(s)")
    if not run.get("totals") and not sessions:
        lines.append("- No session has been recorded yet.")
    lines.append("- On a subscription these are list-price equivalents, not charges.")
    recent = [l for l in st["log"][-5:]]
    if recent:
        lines += ["", "## Recent", ""] + [f"- {l}" for l in recent]
    text = "\n".join(lines[:40]).rstrip() + "\n"
    c.write_text(project / "STATUS.md", text)
    return text


def git(path: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=15).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def repo_cleanliness(path: Path) -> list[str]:
    """Reasons a repository is not ready to be left: uncommitted or unpushed work."""
    if not (Path(path) / ".git").exists():
        return []
    problems = []
    dirty = [l for l in git(path, "status", "--porcelain").splitlines() if l.strip()]
    if dirty:
        problems.append(f"{len(dirty)} uncommitted change(s)")
    branch = git(path, "rev-parse", "--abbrev-ref", "HEAD")
    upstream = git(path, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if not upstream:
        problems.append(f"branch {branch} has never been pushed")
    else:
        ahead = git(path, "rev-list", "--count", f"{upstream}..HEAD")
        if ahead and ahead != "0":
            problems.append(f"{ahead} commit(s) not pushed")
    return problems


def handover(project: Path, brain_root: Path | None = None) -> tuple[list[str], str]:
    """Write .brain/HANDOVER.md and return (problems, text). The note is what a
    fresh chat needs; the problems are what must be fixed before leaving."""
    project = Path(project)
    st, m = read_state(project), c.load_manifest(project)
    rq, needs = req_counts(project), open_needs(project)
    branch = git(project, "rev-parse", "--abbrev-ref", "HEAD")
    lines = [
        f"# Handover: {m.get('project', {}).get('title', project.name)}", "",
        f"Written {c.now_iso()} by session {c.session_id()[:8]}. A new chat needs both repositories attached and one message: **Continue**", "",
        f"- Stage: {st.get('stage')} · size: {st.get('tier')}", f"- In progress: {st.get('item') or 'none'}",
        f"- Last finished: {st.get('last_done') or 'none'}", "- Next: " + ("; ".join(st["next_list"]) or "see .brain/PLAN.md"),
        f"- Blockers: {st.get('blockers') or 'none'}", f"- Branch with the work: {branch or 'unknown'}",
        f"- Requirements: {rq['done']}/{rq['total']} done, {rq['open']} open", f"- Waiting on the owner: {len(needs)} item(s)",
    ]
    if st.get("notes"):
        lines += ["", "## Half-finished work and where it lives", "", st["notes"]]
    text = "\n".join(lines) + "\n"
    c.write_text(project / ".brain" / "HANDOVER.md", text)
    write_status(project)
    problems = [f"project: {p}" for p in repo_cleanliness(project)]
    problems += [f"brain: {p}" for p in repo_cleanliness(Path(brain_root or c.BRAIN_ROOT))]
    return problems, text


# ---------------------------------------------------------------- cli
def cmd_checkpoint(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    st = checkpoint(project, args.item, args.done, args.next, args.stage, args.tier, args.note, args.blockers, args.clear_notes)
    write_status(project)
    print(f"checkpoint: stage {st['stage']} · item: {st['item'] or 'none'} · next: {st['next'] or '-'}")
    return 0


def cmd_status(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    print(write_status(project).rstrip())
    return 0


def cmd_handover(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    problems, _ = handover(project)
    if problems:
        print("not ready to hand over yet (the note was written; fix these, then run handover again):")
        for p in problems:
            print(" -", p)
        return 1
    print("ready: both repositories are committed and pushed; .brain/HANDOVER.md is written")
    print("paste in a new chat with both repositories attached:  Continue")
    return 0


def register(sub) -> None:
    p = sub.add_parser("checkpoint", help="record where the project stands (the single state file)")
    c.add_project_arg(p)
    p.add_argument("--item", help="what is in progress now")
    p.add_argument("--done", help="what was just finished")
    p.add_argument("--next", action="append", help="up to three next items (repeat the flag)")
    p.add_argument("--stage", choices=STAGES)
    p.add_argument("--tier", type=int, choices=(1, 2, 3))
    p.add_argument("--note", help="half-finished work and where it lives")
    p.add_argument("--blockers")
    p.add_argument("--clear-notes", action="store_true")
    p.set_defaults(func=cmd_checkpoint)
    p = sub.add_parser("status", help="regenerate and print the owner's STATUS.md")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("handover", help="write the handover note and check both repositories are clean and pushed")
    c.add_project_arg(p)
    p.set_defaults(func=cmd_handover)
