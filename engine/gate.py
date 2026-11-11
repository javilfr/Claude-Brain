"""Run commands without flooding the conversation, record gate results, and
release only on a recorded green gate.

Why: build and test output is the biggest avoidable source of tokens, and an
earlier project pushed to ``main`` twice without a green check. ``run`` keeps
the full output in a file and prints only what is needed; ``gate`` records
each exit code; ``release`` refuses to push unless the gates passed on the
exact commit being released.
"""
from __future__ import annotations

import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import common as c
from .state import git, is_bookkeeping

ERROR_RE = re.compile(r"(error|fail(ed|ure)?|exception|traceback|assert|✗|✖|not ok|panic|fatal|cannot find|undefined)", re.I)
MAX_LINES = 12  # lines of output shown for a failure; the rest stays in the log file
# Marks that a change switched tests off instead of fixing them.
SKIP_RE = re.compile(r"^\+.*(\.skip\(|\bxit\(|\bxdescribe\(|@unittest\.skip|@pytest\.mark\.skip|\.only\(|test\.todo\()")
STUB_RE = re.compile(r"^\+.*\b(TODO|FIXME|XXX)\b|^\+.*raise NotImplementedError")


def log_dir(project: Path | None) -> Path:
    if project:
        return Path(project) / ".brain" / "log" / "run"
    import tempfile
    return Path(tempfile.gettempdir()) / "brain-run"


def run_filtered(command: str, cwd: Path, project: Path | None, tail: int = 6, timeout: int = 3600) -> dict:
    """Run a shell command; save all output; return a short digest."""
    start = time.time()
    try:
        proc = subprocess.run(command, shell=True, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, errors="replace")
        code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        streams = (proc.stdout or "", proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        code = 124
        streams = None
        out = ((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")) + f"\n[timed out after {timeout}s]"
    secs = time.time() - start
    d = log_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    log = d / f"{c.now().strftime('%Y%m%d-%H%M%S')}-{c.sha256_text(command)[:8]}.log"
    c.write_text(log, f"$ {command}\n[exit {code} in {secs:.1f}s]\n{out}")
    lines = out.splitlines()
    if code == 0:
        # One stream only: the tail of stdout and stderr glued together can
        # put a stray "FAILED" from stderr under an "ok" (review item M6).
        main = streams[0] if streams and streams[0].strip() else (streams[1] if streams else out)
        shown = main.splitlines()[-3:]
    else:
        hits = [i for i, l in enumerate(lines) if ERROR_RE.search(l)]
        keep = set()
        for i in hits[:3]:  # the first failures are usually the cause
            keep.update(range(i, min(len(lines), i + 2)))
        keep.update(range(max(0, len(lines) - tail), len(lines)))
        idx = sorted(keep)
        if len(idx) > MAX_LINES:
            idx = idx[: MAX_LINES // 2] + idx[-MAX_LINES // 2:]
        shown, prev = [], None
        for i in idx:
            if prev is not None and i != prev + 1:
                shown.append("  …")
            shown.append(lines[i])
            prev = i
    return {"exit": code, "seconds": round(secs, 1), "log": str(log), "lines": len(lines), "shown": [l[:240] for l in shown]}  # truncated, not re-spaced: output is shown as it was


def print_digest(command: str, r: dict) -> None:
    word = "ok" if r["exit"] == 0 else f"FAILED (exit {r['exit']})"
    print(f"{word} in {r['seconds']}s · {r['lines']} lines · full output: {r['log']}")
    for l in r["shown"]:
        print("  " + l)


# ---------------------------------------------------------------- gates
def gates_path(project: Path) -> Path:
    return Path(project) / ".brain" / "log" / "gates.jsonl"


def head_commit(project: Path) -> str:
    return git(project, "rev-parse", "HEAD")


def tree_dirty(project: Path) -> bool:
    return any(l.strip() and not is_bookkeeping(l[3:]) for l in git(project, "status", "--porcelain").splitlines())


def same_work(project: Path, commit: str, head: str) -> bool:
    """True when nothing but bookkeeping changed between a gated commit and
    HEAD (committing the gate log itself must not turn a green gate stale)."""
    if not commit or not head:
        return False
    if commit == head:
        return True
    if subprocess.run(["git", "-C", str(project), "merge-base", "--is-ancestor", commit, head], capture_output=True).returncode != 0:
        return False
    changed = [l for l in git(project, "diff", "--name-only", commit, head).splitlines() if l.strip()]
    return all(is_bookkeeping(l) for l in changed)


def diff_detectors(project: Path, base: str | None = None) -> list[str]:
    """Cheap detectors for a false 'done': tests switched off or stubs added in
    the change being gated. Looks at the diff against the release branch."""
    m = c.load_manifest(project)
    base = base or f"origin/{m.get('release', {}).get('branch', 'main')}"
    diff = git(project, "diff", "--unified=0", f"{base}...HEAD") if git(project, "rev-parse", "--verify", "--quiet", base) else ""
    out = []
    skips = [l for l in diff.splitlines() if SKIP_RE.search(l)]
    stubs = [l for l in diff.splitlines() if STUB_RE.search(l)]
    if skips:
        out.append(f"{len(skips)} added line(s) skip or isolate tests, e.g. {c.clip(skips[0][1:].strip(), 80)}")
    if stubs:
        out.append(f"{len(stubs)} added line(s) are TODO or unimplemented stubs, e.g. {c.clip(stubs[0][1:].strip(), 80)}")
    return out


def run_gates(project: Path, only: str | None = None) -> tuple[int, list[dict]]:
    m = c.load_manifest(project)
    results = []
    worst = 0
    for g in m.get("gates", []):
        if only and g.get("id") != only:
            continue
        rec = {"gate": g.get("id"), "kind": g.get("kind"), "at": c.now_iso(), "session": c.session_id(),
               "commit": head_commit(project), "dirty": tree_dirty(project)}
        if g.get("kind") != "command":
            rec["exit"] = None
            rec["note"] = "manual gate: needs a person"
        elif not (g.get("command") or "").strip():
            rec["exit"] = None
            rec["note"] = "no command set in .brain/project.json yet"
        else:
            r = run_filtered(g["command"], project, project)
            log = Path(r["log"])
            try:  # relative, so the record means the same on another machine
                log_ref = str(log.relative_to(Path(project)))
            except ValueError:
                log_ref = log.name
            rec.update({"command": g["command"], "exit": r["exit"], "seconds": r["seconds"], "log": log_ref})
            rec["_digest"] = r
            worst = worst or r["exit"]
        results.append(rec)
        c.append_jsonl(gates_path(project), {k: v for k, v in rec.items() if not k.startswith("_")})
    return worst, results


def green_at_head(project: Path) -> tuple[bool, list[str]]:
    """True when every command gate's latest record is exit 0, on the current
    commit, with a clean tree at the time. This is what 'green' means."""
    m = c.load_manifest(project)
    head = head_commit(project)
    latest: dict[str, dict] = {}
    for rec in c.read_jsonl(gates_path(project)):
        latest[rec.get("gate")] = rec
    why = []
    command_gates = [g for g in m.get("gates", []) if g.get("kind") == "command"]
    if not any((g.get("command") or "").strip() for g in command_gates):
        why.append("no command gate is defined, so nothing proves this commit works")
    for g in command_gates:
        if not (g.get("command") or "").strip():
            continue
        rec = latest.get(g["id"])
        if not rec:
            why.append(f"gate {g['id']} has never run")
        elif rec.get("exit") != 0:
            why.append(f"gate {g['id']} last exited {rec.get('exit')}")
        elif not same_work(project, rec.get("commit", ""), head):
            why.append(f"gate {g['id']} passed on a different commit ({str(rec.get('commit'))[:7]}); the work has changed since")
        elif rec.get("dirty"):
            why.append(f"gate {g['id']} ran with uncommitted changes")
    return (not why), why


def check_live(url: str, expect: str = "", wait_seconds: int = 120, every: float = 20.0) -> tuple[bool, str]:
    """Bounded check that the live address answers and, when ``expect`` is
    given, that the page contains it (for example the commit id, if the app
    shows one). It gives up after ``wait_seconds``: a deployment that has not
    appeared by then needs a person, not a day of polling."""
    deadline = time.time() + max(0, wait_seconds)
    last = "no attempt made"
    while True:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "brain-release-check"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read(2_000_000).decode("utf-8", errors="replace")
                status = resp.status or 200  # non-HTTP handlers report no status
                if not 200 <= status < 400:
                    last = f"status {status}"
                elif expect and expect not in body:
                    last = f"answered {status} but the page does not contain {expect!r} yet (old version still served?)"
                else:
                    return True, f"live address answered {status}" + (f" and contains {expect!r}" if expect else "")
        except (urllib.error.URLError, OSError, ValueError) as e:
            last = c.clip(str(e), 120)
        if time.time() + every > deadline:
            return False, f"not confirmed after {wait_seconds}s: {last}"
        time.sleep(every)


def live_report(project: Path, rel: dict, head: str, wait_seconds: int) -> int:
    expect = (rel.get("live_expect") or "").replace("{commit}", head[:7])
    live, msg = check_live(rel["live_url"], expect, wait_seconds)
    print(("live check: " if live else "LIVE CHECK FAILED: ") + msg)
    if not live:
        print("tell the owner this first, with click steps; do not keep polling")
        return 4
    return 0


# ---------------------------------------------------------------- cli
def cmd_run(args) -> int:
    parts = list(args.cmd)
    if parts and parts[0] == "--":
        parts = parts[1:]
    if not parts:
        print("usage: brain run -- <command>")
        return 2
    # One argument is a shell line as typed; several are an argument list
    # whose quoting must survive the trip through the shell.
    command = parts[0] if len(parts) == 1 else shlex.join(parts)
    cwd = Path(args.cwd).resolve() if args.cwd else Path.cwd().resolve()
    project = c.resolve_project(args.project)
    if project is not None and not c.is_managed(project):
        project = None
    # The command runs where it was typed. Its log goes into the project only
    # when that is where we are; otherwise to a temporary folder.
    if project is not None and not args.project and project.resolve() not in (cwd, *cwd.parents):
        project = None
    r = run_filtered(command, cwd, project, args.tail, args.timeout)
    print_digest(command, r)
    return r["exit"]


def cmd_gate(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    worst, results = run_gates(project, args.id)
    if not results:
        print(f"no gate {'named ' + args.id if args.id else 'defined'} in .brain/project.json")
        return 1
    for rec in results:
        if rec["exit"] is None:
            print(f"gate {rec['gate']}: {rec['note']}")
        else:
            print(f"gate {rec['gate']}: ", end="")
            print_digest(rec["command"], rec["_digest"])
    for d in diff_detectors(project):
        print("check this before calling it done:", d)
    if any(r.get("dirty") for r in results if r["exit"] == 0):
        print("note: ran with uncommitted changes; commit and run again before a release")
    return 1 if worst else 0


def cmd_release(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    m = c.load_manifest(project)
    rel = m.get("release", {})
    rule, branch = rel.get("rule", "none"), rel.get("branch", "main")
    if rule == "none":
        print("this project has no release rule (release.rule is 'none' in .brain/project.json)")
        return 0
    if rule == "pr":
        print("release rule is 'pr': open a pull request when the owner asks for one; nothing pushed")
        return 0
    if args.check_live:
        if not rel.get("live_url"):
            print("no live address is set (release.live_url in .brain/project.json)")
            return 1
        return live_report(project, rel, head_commit(project), args.live_wait)
    if tree_dirty(project):
        print("refusing: uncommitted changes. Commit, run `brain gate --all`, then release.")
        return 1
    ok, why = green_at_head(project)
    if not ok and args.run_gates:
        worst, _ = run_gates(project)
        ok, why = green_at_head(project)
    if not ok:
        print("refusing to release: no recorded green gate for this commit")
        for w in why:
            print(" -", w)
        return 1
    # A failed fetch would compare against a stale origin/<branch> (final
    # review 2026-11-11, D9). ls-remote exit 2 means the branch does not exist
    # yet (a first release); anything else non-zero means the remote is unreachable.
    probe = subprocess.run(["git", "-C", str(project), "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}"],
                           capture_output=True, text=True)
    if probe.returncode not in (0, 2):
        print(f"refusing to release: could not reach origin to compare with {branch} ({c.clip(probe.stderr.strip(), 120)}). Try again when the remote is reachable.")
        return 1
    if probe.returncode == 0:
        f = subprocess.run(["git", "-C", str(project), "fetch", "origin", branch], capture_output=True, text=True)
        if f.returncode != 0:
            print(f"refusing to release: fetching origin/{branch} failed ({c.clip(f.stderr.strip(), 120)}), so the fast-forward check would use a stale copy")
            return 1
    remote = git(project, "rev-parse", "--verify", "--quiet", f"origin/{branch}")
    if remote:
        if subprocess.run(["git", "-C", str(project), "merge-base", "--is-ancestor", f"origin/{branch}", "HEAD"]).returncode != 0:
            print(f"refusing: origin/{branch} has commits this branch lacks. Merge origin/{branch} into this branch, run the gates again, then release. (Never force-push.)")
            return 1
    head = head_commit(project)
    if not args.push:
        print(f"ready to release {head[:7]} to {branch}: gates are green on this commit and it fast-forwards. Run again with --push to push.")
        return 0
    push = subprocess.run(["git", "-C", str(project), "push", "origin", f"HEAD:{branch}"], capture_output=True, text=True)
    if push.returncode != 0:
        print("push failed:", c.clip(push.stderr, 300))
        return 1
    print(f"released {head[:7]} to {branch} (fast-forward, gates green)")
    c.append_jsonl(Path(project) / ".brain" / "log" / "releases.jsonl", {"at": c.now_iso(), "commit": head, "branch": branch, "session": c.session_id()})
    if rel.get("live_url"):
        return live_report(project, rel, head, args.live_wait)
    print("no live address is set (release.live_url), so the deployment itself was not checked")
    return 0


def register(sub) -> None:
    p = sub.add_parser("run", help="run a command; keep the full output in a file, print only the result")
    c.add_project_arg(p)
    p.add_argument("--tail", type=int, default=6)
    p.add_argument("--timeout", type=int, default=3600)
    p.add_argument("--cwd")
    p.add_argument("cmd", nargs="...")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("gate", help="run the project's gates and record each exit code")
    c.add_project_arg(p)
    p.add_argument("id", nargs="?")
    p.add_argument("--all", action="store_true", help="run every gate (the default)")
    p.set_defaults(func=cmd_gate)
    p = sub.add_parser("release", help="push to the release branch only on a recorded green gate; never force")
    c.add_project_arg(p)
    p.add_argument("--push", action="store_true", help="actually push (without it: report only)")
    p.add_argument("--run-gates", action="store_true", help="run the gates first if they are not green on this commit")
    p.add_argument("--check-live", action="store_true", help="only re-check the live address; push nothing")
    p.add_argument("--live-wait", type=int, default=120, help="seconds to wait for the live address (bounded)")
    p.set_defaults(func=cmd_release)
