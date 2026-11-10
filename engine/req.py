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
    passes = (args.passes_when or "").strip()
    # One sentence may hold several checkable needs (the plan skill splits it),
    # so a repeat is the same words with the same 'passes when'.
    if any(r.get("quote") == quote and r.get("passes_when", "") == passes for r in rows):
        print("already in the ledger (same words and same 'passes when'); nothing added")
        return 0
    row = {"id": next_id(rows), "quote": quote, "passes_when": passes,
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
        r["status"] = "done"
        r["done"] = c.today()
    save(project, rows)
    print(f"{r['id']}: {len(r['evidence'])} evidence item(s), status {r['status']}")
    return 0


def cmd_verify(args) -> int:
    """Run each open line's check in the project; a line whose check exits 0
    gets that result as evidence and is marked done. Lines with no runnable
    check are listed for evidence by hand (a screenshot, a source)."""
    from . import gate
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    head = (gate.head_commit(project) or "")[:8] or "no commit"
    failed = manual = passed = 0
    for r in rows:
        if r.get("status") == "dropped" or not r.get("passes_when"):
            continue
        if r.get("status") == "done" and not getattr(args, "all", False):
            continue
        cmd = (r.get("check") or "").strip()
        if not cmd:
            manual += 1
            print(f"{r['id']}: no check command; attach evidence by hand")
            continue
        res = gate.run_filtered(cmd, project, project, timeout=args.timeout)
        if res["exit"] == 0:
            passed += 1
            ev = f"check exited 0 on {head} ({c.today()}): {c.clip(cmd, 120)}"
            if ev not in r.setdefault("evidence", []):
                r["evidence"].append(ev)
            r["status"], r["done"] = "done", c.today()
            print(f"{r['id']}: done (check exited 0)")
        else:
            failed += 1
            if r.get("status") == "done":
                # --all: a line once done whose check now fails is open again (CB-208).
                r["status"] = "open"
                r.setdefault("evidence", []).append(f"check exited {res['exit']} on {head} ({c.today()}): reopened")
            print(f"{r['id']}: check exited {res['exit']}; open · log: {res['log']}")
            for l in res["shown"][-3:]:
                print(f"  {l}")
    save(project, rows)
    print(f"verify: {passed} done, {failed} failed, {manual} need evidence by hand")
    return 1 if failed else 0


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
    p = sub.add_parser("req", help="the requirements ledger: add, list, evidence, verify, drop, check")
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
    a = s.add_parser("verify", help="run each open line's check; mark it done with the result when it exits 0")
    c.add_project_arg(a)
    a.add_argument("--timeout", type=int, default=600)
    a.add_argument("--all", action="store_true", help="re-run lines already done too, and reopen any whose check now fails")
    a.set_defaults(func=guarded(cmd_verify))
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
    a.set_defaults(func=guarded(cmd_check))
    p.set_defaults(func=guarded(cmd_list), project=None, open=False, limit=15)
