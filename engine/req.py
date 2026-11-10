"""The requirements ledger.

Every sentence of a request becomes a line: the owner's exact words, what will
satisfy them ("passes when"), and at the end a pointer to evidence. ``check``
exits non-zero while any line is unfinished, so "done" cannot be claimed on a
feeling. Stored as ``.brain/requirements.jsonl``; ``.brain/REQUIREMENTS.md`` is
a generated view for reading.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import common as c


def path(project: Path) -> Path:
    return Path(project) / ".brain" / "requirements.jsonl"


class LedgerError(Exception):
    """The ledger file has a line that cannot be read."""


def load(project: Path) -> list[dict]:
    """Read the ledger strictly. A line that does not parse (a half-written
    file, a merge conflict between two chats) stops everything: skipping it
    would let `check` pass with a requirement missing, and the next write
    would delete that requirement for good."""
    rows = []
    try:
        text = path(project).read_text(encoding="utf-8")
    except FileNotFoundError:
        return rows
    except UnicodeDecodeError as e:
        raise LedgerError(f"requirements.jsonl is not readable text ({c.clip(str(e), 60)})")
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise LedgerError(f"requirements.jsonl line {n} is not valid JSON; repair it (or restore the file from git) before going on")
        if not isinstance(row, dict) or not row.get("id"):
            raise LedgerError(f"requirements.jsonl line {n} is not a requirement (no id)")
        rows.append(row)
    return rows


def guarded(func):
    """Turn a broken ledger into one clear line and exit code 2."""
    def run(args):
        try:
            return func(args)
        except LedgerError as e:
            print(f"requirements: {e}")
            return 2
    return run


def save(project: Path, rows: list[dict]) -> None:
    c.write_jsonl(path(project), rows)
    render(project, rows)


def render(project: Path, rows: list[dict]) -> None:
    out = ["# Requirements", "", "Generated from `requirements.jsonl` by `brain req`. Each line is the owner's own words, the test for it, and the evidence.", "",
           "| Id | Owner's words | Passes when | Status | Evidence |", "|---|---|---|---|---|"]
    for r in rows:
        ev = "; ".join(r.get("evidence", [])) or (r.get("reason", "") if r.get("status") == "dropped" else "")
        cell = lambda s: c.clip(str(s), 220).replace("|", "\\|")
        if r.get("implied"):
            r = dict(r, quote="(implied) " + r.get("quote", "") + (f" — assumed: {r['assumption']}" if r.get("assumption") else ""))
        out.append(f"| {r['id']} | {cell(r.get('quote', ''))} | {cell(r.get('passes_when', ''))} | {r.get('status', 'open')} | {cell(ev)} |")
    c.write_text(Path(project) / ".brain" / "REQUIREMENTS.md", "\n".join(out) + "\n")


def next_id(rows: list[dict]) -> str:
    nums = [int(r["id"][2:]) for r in rows if str(r.get("id", "")).startswith("R-") and r["id"][2:].isdigit()]
    return f"R-{(max(nums) + 1 if nums else 1):03d}"


def find(rows: list[dict], rid: str) -> dict | None:
    rid = rid.upper()
    return next((r for r in rows if r.get("id") == rid), None)


def problems(rows: list[dict]) -> list[str]:
    """Why the ledger does not yet allow 'done'."""
    out = []
    for r in rows:
        status = r.get("status", "open")
        if status == "dropped":
            if not r.get("reason"):
                out.append(f"{r['id']}: dropped without a reason")
            continue
        if not r.get("passes_when"):
            out.append(f"{r['id']}: no 'passes when' (how will this be checked?)")
        if status != "done":
            out.append(f"{r['id']}: open — {c.clip(r.get('quote', ''), 70)}")
        elif not r.get("evidence"):
            out.append(f"{r['id']}: marked done with no evidence")
    return out


# ---------------------------------------------------------------- cli
def cmd_add(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    quote = " ".join(args.quote.split())
    if any(r.get("quote") == quote for r in rows):
        print("already in the ledger (same words); nothing added")
        return 0
    row = {"id": next_id(rows), "quote": quote, "passes_when": (args.passes_when or "").strip(),
           "check": (args.check or "").strip(), "status": "open", "evidence": [], "added": c.today()}
    if args.implied:
        # Not the owner's words: something the request needs in order to hold.
        # Kept apart so an assumption is never mistaken for an instruction.
        row["implied"] = True
        if args.assumption:
            row["assumption"] = args.assumption.strip()
    rows.append(row)
    save(project, rows)
    print(f"{row['id']} added" + ("" if row["passes_when"] else " (no 'passes when' yet)"))
    return 0


def cmd_set(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    r = find(rows, args.id)
    if not r:
        print(f"no requirement {args.id}")
        return 1
    if args.passes_when:
        r["passes_when"] = args.passes_when.strip()
    if args.check:
        r["check"] = args.check.strip()
    save(project, rows)
    print(f"{r['id']} updated")
    return 0


RUNNABLE = ("python", "python3", "pytest", "npm", "npx", "node", "make", "bash", "sh", "test", "grep", "ls",
            "cargo", "go", "uv", "pnpm", "yarn", "deno", "bun", "curl", "git", "diff", "cmp", "jq")
CHECK_TIMEOUT = 600  # seconds for one line's check


def runnable(check: str) -> bool:
    """A check is run when it starts like a command; prose methods such as
    'screenshot on the phone' are evidence the lead attaches by hand."""
    import shlex
    import shutil
    try:
        first = shlex.split(check)[0] if check.strip() else ""
    except ValueError:
        return False
    return bool(first) and (first in RUNNABLE or first.startswith("./") or shutil.which(first) is not None)


def run_line_check(project: Path, r: dict) -> tuple[bool, str] | None:
    """Run a line's check in the project folder. None when it is not runnable."""
    import subprocess
    chk = (r.get("check") or "").strip()
    if not runnable(chk):
        return None
    try:
        p = subprocess.run(chk, shell=True, cwd=project, capture_output=True, text=True, timeout=CHECK_TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, f"check timed out after {CHECK_TIMEOUT}s: {c.clip(chk, 120)}"
    tail = (p.stdout + p.stderr).strip().splitlines()[-1:] or [""]
    return p.returncode == 0, f"check exit {p.returncode} on {c.today()}: {c.clip(chk, 120)} · {c.clip(tail[0], 80)}"


def cmd_evidence(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    r = find(rows, args.id)
    if not r:
        print(f"no requirement {args.id}")
        return 1
    for e in args.evidence:
        e = c.clip(e, 240)
        if e not in r.setdefault("evidence", []):
            r["evidence"].append(e)
    if args.done:
        if not r.get("passes_when"):
            print(f"{r['id']}: cannot mark done without a 'passes when'")
            return 1
        # A line whose check is a command is done only when that command passes
        # now: typed evidence alone let a wrong claim through in the first live trial.
        ran = run_line_check(project, r)
        if ran is not None:
            ok, line = ran
            if not ok:
                print(f"{r['id']}: not marked done; its check failed — {line}")
                save(project, rows)
                return 1
            r["evidence"] = [e for e in r["evidence"] if not e.startswith("check exit ")] + [line]
        r["status"] = "done"
        r["done"] = c.today()
    save(project, rows)
    print(f"{r['id']}: {len(r['evidence'])} evidence item(s), status {r['status']}")
    return 0


def cmd_drop(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    r = find(rows, args.id)
    if not r:
        print(f"no requirement {args.id}")
        return 1
    r["status"], r["reason"] = "dropped", args.reason.strip()
    save(project, rows)
    print(f"{r['id']} dropped: {r['reason']}")
    return 0


def cmd_list(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    shown = [r for r in rows if not args.open or r.get("status", "open") == "open"]
    if not shown:
        print("ledger is empty" if not rows else "no open requirements")
        return 0
    for r in shown[: args.limit]:
        print(f"{r['id']} [{r.get('status', 'open')}] {c.clip(r.get('quote', ''), 90)}" + (f" → {c.clip(r['passes_when'], 70)}" if r.get("passes_when") else ""))
    if len(shown) > args.limit:
        print(f"… {len(shown) - args.limit} more (see .brain/REQUIREMENTS.md)")
    return 0


def cmd_check(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    probs = problems(rows)
    if getattr(args, "run", False):
        for r in rows:
            if r.get("status") == "done":
                ran = run_line_check(project, r)
                if ran is not None and not ran[0]:
                    probs.append(f"{r['id']}: marked done but its check now fails — {ran[1]}")
    done = sum(r.get("status") == "done" for r in rows)
    if probs:
        print(f"requirements: {done}/{len(rows)} done with evidence; not finished:")
        for p in probs[:20]:
            print(" -", p)
        if len(probs) > 20:
            print(f" … {len(probs) - 20} more")
        return 1
    if not rows:
        # At project size an empty ledger proves nothing: the request's
        # sentences were never written down, so "done" cannot be checked.
        from .state import read_state
        tier = read_state(project).get("tier") or str(c.load_manifest(project).get("tier", ""))
        stage = read_state(project).get("stage") or ""
        if tier in ("2", "3") and stage in ("build", "verify", "deliver", "learn", "done"):
            print("requirements: the ledger is empty at project size; add the request's sentences with `brain req add` before calling anything done")
            return 1
        print("requirements: ledger is empty (fine for an answer or a small task)")
        return 0
    print(f"requirements: all {len(rows)} line(s) done with evidence or dropped with a reason")
    return 0


def register(sub) -> None:
    p = sub.add_parser("req", help="the requirements ledger: add, list, evidence, drop, check")
    s = p.add_subparsers(dest="req_cmd")
    a = s.add_parser("add", help="add a line with the owner's exact words")
    c.add_project_arg(a)
    a.add_argument("--quote", required=True)
    a.add_argument("--passes-when", dest="passes_when")
    a.add_argument("--check", help="command or method that verifies it")
    a.add_argument("--implied", action="store_true", help="not the owner's words: a need the request implies")
    a.add_argument("--assumption", help="with --implied: what was assumed and why")
    a.set_defaults(func=guarded(cmd_add))
    a = s.add_parser("set", help="set 'passes when' or the check for a line")
    c.add_project_arg(a)
    a.add_argument("id")
    a.add_argument("--passes-when", dest="passes_when")
    a.add_argument("--check")
    a.set_defaults(func=guarded(cmd_set))
    a = s.add_parser("evidence", help="attach evidence; --done marks the line done")
    c.add_project_arg(a)
    a.add_argument("id")
    a.add_argument("evidence", nargs="+")
    a.add_argument("--done", action="store_true")
    a.set_defaults(func=guarded(cmd_evidence))
    a = s.add_parser("drop", help="drop a line with a reason")
    c.add_project_arg(a)
    a.add_argument("id")
    a.add_argument("--reason", required=True)
    a.set_defaults(func=guarded(cmd_drop))
    a = s.add_parser("list")
    c.add_project_arg(a)
    a.add_argument("--open", action="store_true")
    a.add_argument("--limit", type=int, default=15)
    a.set_defaults(func=guarded(cmd_list))
    a = s.add_parser("check", help="exit non-zero while any line is unfinished")
    c.add_project_arg(a)
    a.add_argument("--run", action="store_true", help="also re-run the check of every done line that is a command")
    a.set_defaults(func=guarded(cmd_check))
    p.set_defaults(func=guarded(cmd_list), project=None, open=False, limit=15)
