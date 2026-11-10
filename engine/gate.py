"""Run commands without flooding the conversation, record gate results, and
release only on what the release itself saw pass.

Why: build and test output is the biggest avoidable source of tokens, and an
earlier project pushed to ``main`` twice without a green check. ``run`` keeps
the full output in a file and prints only what is needed; ``gate`` records
each exit code; ``release --push`` runs every gate itself on the commit being
released and pushes only on those exit codes, so a stored record, a command
that cannot fail or a test switched off in the same change cannot release.
"""
from __future__ import annotations

import datetime as _dt
import fnmatch
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from . import common as c
from .state import git, is_bookkeeping

ERROR_RE = re.compile(r"(error|fail(ed|ure)?|exception|traceback|assert|✗|✖|not ok|panic|fatal|cannot find|undefined)", re.I)
MAX_LINES = 12     # lines of output shown for a failure; the rest stays in the log file
OUTPUT_LINES = 15  # what one command may print by default (I-04)
# Marks that a change switched tests off instead of fixing them.
SKIP_RE = re.compile(
    r"^\+.*(\.skip\(|\bxit\(|\bxdescribe\(|\bxtest\(|\.only\(|test\.todo\("
    r"|@(?:unittest\.)?skip|@pytest\.mark\.(?:skip|xfail)|\bpytest\.(?:skip|xfail)\("
    r"|\.skipTest\(|\bSkipTest\b|@(?:unittest\.)?expectedFailure"
    r"|\bt\.Skip(?:f|Now)?\(|#\[ignore|@Disabled\b|@Ignore\b|--passWithNoTests)")
STUB_RE = re.compile(r"^\+.*\b(TODO|FIXME|XXX)\b|^\+.*raise NotImplementedError")
_TEST_DEF = r"\s*(?:(?:async\s+)?def\s+test\w*\s*\(|(?:it|test)\s*\(\s*['\"`]|func\s+Test\w*\s*\(|#\[(?:\w+::)?test\]|@Test\b)"
TEST_GONE_RE = re.compile(r"^-(?!-)" + _TEST_DEF)
TEST_NEW_RE = re.compile(r"^\+(?!\+)" + _TEST_DEF)
TEST_FILE_RE = re.compile(r"(?:^|/)(?:tests?|__tests__|spec)/|(?:^|/)test_[^/]+$|_test\.\w+$|\.(?:test|spec)\.\w+$")
# Exit 0 with a failure summary in the last lines means the exit code was lost
# on the way. Summary shapes only: a test whose title says "2 failed attempts"
# must not hold every release.
SUSPECT_RE = re.compile(
    r"^(?:--- )?FAIL(?:ED)?\b|^\W*FAILED\b|^\W*[1-9]\d* (?:failed|failing|failures?|errors?)\b"
    r"|(?:[:;,]|\bpassed)\s*[1-9]\d* (?:failed|failures?|errors?)\b|\b(?:errors|failures)=[1-9]"
    r"|^not ok\b|\bNO TESTS RAN\b|\bno tests ran\b|\bRan 0 tests\b")
# How many tests a run reported, whatever the runner (the last match counts).
COUNT_RES = (re.compile(r"\bRan (\d+) tests?\b"), re.compile(r"\b(\d+) (?:passed|passing)\b"),
             re.compile(r"^# tests (\d+)\b"), re.compile(r"^1\.\.(\d+)\s*$"))
_QUOTED = re.compile(r"'[^']*'|\"(?:\\.|[^\"\\])*\"")
# `|| true` and the like at the very end: the exit code of the whole command is then always 0.
_MASK_OR = re.compile(r"\|\|\s*(true|:|exit\s+0|(?:echo|printf)\b[^;&|\n]*?)[\s);]*$")
_MASK_END = re.compile(r"[;\n]\s*(?:true|:|exit\s+0)\s*;?\s*$")
_PIPE = re.compile(r"(?<![|>])\|(?!\|)")
BOX_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX])\]")
FOOTER_RE = re.compile(rb"\n?\[exit -?\d+ in [\d.]+s\]\n$")
NOT_A_FAILURE = (124, 125, 130, 143)  # stopped by brain, not failed by the check

# Tunable (EXECUTION_PLAN section 0.8): the `gate` group of memory/ml_config.json overrides these.
DEFAULT_CFG = {
    "run_timeout": 540,   # seconds for `brain run`: under the ten minutes a tool call may last
    "gate_timeout": 900,  # seconds for a gate without its own "timeout"
    "log_cap_mb": 20,     # a stored log keeps its first and last half of this
    "log_stop_mb": 1024,  # a command that prints more than this is stopped
    "keep_logs": 60,      # run logs kept per folder
    "kill_grace": 2.0,    # seconds between asking a process group to stop and killing it
}
SCAN_BYTES = 4 << 20   # where the first error lines are looked for
TAIL_BYTES = 256 << 10
LINE_BYTES = 1 << 16


def cfg_of(brain_root: Path | None = None) -> dict:
    out = dict(DEFAULT_CFG)
    user = (c.read_json(Path(brain_root or c.BRAIN_ROOT) / "memory" / "ml_config.json", {}) or {}).get("gate")
    if isinstance(user, dict):
        out.update({k: v for k, v in user.items() if k in out and isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0})
    return out


def log_dir(project: Path | None) -> Path:
    if project:
        return Path(project) / ".brain" / "log" / "run"
    import tempfile
    return Path(tempfile.gettempdir()) / "brain-run"


# ---------------------------------------------------------------- running
def shell_argv(command: str) -> tuple[list[str], bool]:
    """(argv, pipefail): bash with pipefail when there is one, so a pipe
    cannot hide the exit code of the command in front of it."""
    bash = shutil.which("bash")
    if bash:
        return [bash, "-o", "pipefail", "-c", command], True
    return [shutil.which("sh") or "/bin/sh", "-c", command], False


def _new_log(project: Path | None, command: str):
    """A log file no other run has: two runs of one command in one second
    used to share a name and overwrite each other."""
    d = log_dir(project)
    d.mkdir(parents=True, exist_ok=True)
    stem = f"{c.now().strftime('%Y%m%d-%H%M%S')}-{c.sha256_text(command)[:8]}"
    for n in range(1 << 16):
        path = d / (f"{stem}.log" if n == 0 else f"{stem}{n:02x}.log")
        try:
            return path, os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o644), "ab")
        except FileExistsError:
            continue
    raise OSError(f"no free log name in {d}")


def _group_running(proc) -> bool:
    """True while a process of the command's group still runs. A zombie does
    not count: a dead child waiting for a slow init must not cost the grace."""
    proc.poll()  # reap the shell itself
    try:
        os.killpg(proc.pid, 0)
    except OSError:
        return False
    if not os.path.isdir("/proc/self"):
        return True  # no /proc here: a zombie cannot be told from a runner
    want = str(proc.pid).encode()
    for name in os.listdir("/proc"):
        if name.isdigit():
            try:
                with open(f"/proc/{name}/stat", "rb") as f:
                    rest = f.read().rsplit(b")", 1)[-1].split()  # state, parent, group, ...
            except OSError:
                continue
            if len(rest) > 2 and rest[2] == want and rest[0] not in (b"Z", b"X"):
                return True
    return False


def _kill_group(proc, grace: float) -> None:
    """Stop the command and everything it started (one process group): ask
    first, then kill what is still running after ``grace`` seconds."""
    if not hasattr(os, "killpg"):
        proc.kill()
    else:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(proc.pid, sig)
            except OSError:
                break
            end = time.time() + grace
            while _group_running(proc) and time.time() < end:
                time.sleep(0.03)
            if not _group_running(proc):
                break
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _wait(proc, logf, timeout: int, cfg: dict) -> tuple[int, str, int]:
    """(exit code, why it was stopped or "", signal brain received or 0)."""
    got: list[int] = []
    old = {}
    for name in ("SIGTERM", "SIGINT", "SIGHUP"):
        sig = getattr(signal, name, None)
        try:
            old[sig] = signal.signal(sig, lambda s, _f: got.append(s))
        except (ValueError, OSError, TypeError):
            pass  # not the main thread: the caller's own handling stays
    deadline, stop_at = time.time() + timeout, int(cfg["log_stop_mb"]) << 20
    code, why = None, ""
    try:
        while code is None:
            try:
                code = proc.wait(timeout=0.25)
            except subprocess.TimeoutExpired:
                pass
            if got:
                code, why = 128 + got[0], f"stopped by signal {got[0]}"
            elif code is None and time.time() >= deadline:
                code, why = 124, f"timed out after {timeout}s"
            elif code is None and os.fstat(logf.fileno()).st_size > stop_at:
                code, why = 125, f"stopped: it printed more than {cfg['log_stop_mb']} MB"
        if why and proc.returncode is None:
            _kill_group(proc, float(cfg["kill_grace"]))
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)
    return (128 - code if code < 0 else code), why, (got[0] if got else 0)


def _text(raw: bytes) -> str:
    s = raw.decode("utf-8", "replace").rstrip("\r\n")
    return s.rsplit("\r", 1)[-1] if "\r" in s else s  # a progress bar: its last state


def digest_log(src, code: int, tail: int = 6, start: int = 0, end: int | None = None) -> dict:
    """lines, shown, tests and suspect for the output saved in a log (a path,
    or the open file itself) between two byte offsets. The file is streamed,
    so memory stays flat however much a command printed."""
    if not hasattr(src, "read"):
        with open(src, "rb") as f:
            return digest_log(f, code, tail, start, end)
    f = src
    size = os.fstat(f.fileno()).st_size if end is None else end
    n, last = 0, b"\n"
    hits: dict[int, str] = {}
    f.seek(start)
    left = size - start
    while left > 0:
        chunk = f.read(min(1 << 20, left))
        if not chunk:
            break
        n, last, left = n + chunk.count(b"\n"), chunk[-1:], left - len(chunk)
    if size > start and last != b"\n":
        n += 1
    t0 = max(start, size - TAIL_BYTES)
    f.seek(t0)
    pieces = f.read(size - t0).split(b"\n")
    if pieces and pieces[-1] == b"":
        pieces.pop()
    if t0 > start and len(pieces) > 1:
        pieces = pieces[1:]  # the first piece may be half a line
    tail_lines = [_text(p[:LINE_BYTES]) for p in pieces[-200:]]
    if code != 0:  # the first failures are usually the cause
        f.seek(start)
        i, pos, found, want_next, fresh = 0, start, 0, False, True
        limit = min(size, start + SCAN_BYTES)
        while pos < limit and (found < 3 or want_next):
            raw = f.readline(LINE_BYTES)
            if not raw:
                break
            pos += len(raw)
            if fresh:
                text = _text(raw)
                if want_next:
                    hits[i], want_next = text, False
                if found < 3 and ERROR_RE.search(text):
                    hits[i], found, want_next = text, found + 1, True
            fresh = raw.endswith(b"\n")
            i += fresh
    head_lines = []
    if code == 0:
        f.seek(start)
        head_lines = [_text(l) for l in f.read(min(4096, size - start)).split(b"\n")[:20]]
    if code == 0:
        shown = tail_lines[-3:]
    else:
        keep = dict(hits)
        last_n = tail_lines[-tail:] if tail > 0 else []
        for j, text in enumerate(last_n):
            keep[n - len(last_n) + j] = text
        idx = sorted(keep)
        if len(idx) > MAX_LINES:
            idx = idx[: MAX_LINES // 2] + idx[-MAX_LINES // 2:]
        shown, prev = [], None
        for i in idx:
            if prev is not None and i != prev + 1:
                shown.append("  …")
            shown.append(keep[i])
            prev = i
    tests = None
    for line in head_lines + tail_lines:
        for pat in COUNT_RES:
            m = pat.search(line)
            if m:
                tests = int(m.group(1))
    suspect = ""
    if code == 0:
        suspect = next((c.clip(l, 100) for l in tail_lines[-20:] if SUSPECT_RE.search(l)), "")
    return {"lines": n, "shown": [l[:240] for l in shown],  # truncated, not re-spaced: output is shown as it was
            "tests": tests, "suspect": suspect}


def _cap_log(path: Path, cap: int) -> None:
    """Keep the first and last half of ``cap`` bytes of an oversized log."""
    size = os.path.getsize(path)
    if size <= cap:
        return
    half, tmp = cap // 2, path.with_name(path.name + ".part")
    with open(path, "rb") as src, open(tmp, "wb") as dst:
        for begin, count in ((0, half), (size - half, half)):
            src.seek(begin)
            while count > 0:
                chunk = src.read(min(1 << 20, count))
                if not chunk:
                    break
                dst.write(chunk)
                count -= len(chunk)
            if begin == 0:
                dst.write(f"\n[brain: {(size - cap) >> 20} MB of output cut here; the first and last {half >> 20} MB are kept]\n".encode())
    os.replace(tmp, path)


def _prune_logs(d: Path, keep: int) -> None:
    """Drop all but the newest ``keep`` logs. A log touched in the last hour
    stays: it may belong to a command that is still running."""
    def mtime(p: Path) -> int:
        try:
            return p.stat().st_mtime_ns
        except OSError:
            return 0
    aged = sorted((mtime(p), p.name, p) for p in d.glob("*.log"))
    old_enough = (time.time() - 3600) * 1e9
    for when, _name, p in aged[:-keep]:
        if when < old_enough:
            try:
                p.unlink()
            except OSError:
                pass


def run_filtered(command: str, cwd: Path, project: Path | None, tail: int = 6, timeout: int | None = None) -> dict:
    """Run a shell command; save all output; return a short digest.

    The command reads nothing from the caller (stdin is /dev/null), writes
    stdout and stderr to one log in the order they happened, and runs in its
    own process group, which is stopped as a whole on a timeout or when brain
    itself is told to stop. A result comes back in every case."""
    cfg = cfg_of()
    timeout = int(timeout) if timeout else int(cfg["run_timeout"])
    log, f = _new_log(project, command)
    header = ("$ " + c.redact_secrets(command).replace("\n", "\\n") + "\n").encode("utf-8", "replace")
    start, why, sig, ours = time.time(), "", 0, True
    # The digest is read through a handle opened now, not through the name
    # later: whatever happens to the name meanwhile, this is our output.
    with f, open(log, "rb") as own:
        f.write(header)
        f.flush()
        try:
            proc = subprocess.Popen(shell_argv(command)[0], cwd=str(cwd), stdin=subprocess.DEVNULL, stdout=f,
                                    stderr=subprocess.STDOUT, start_new_session=True)
        except OSError as e:
            code, why = 127, f"could not start: {c.clip(str(e), 120)}"
        else:
            code, why, sig = _wait(proc, f, timeout, cfg)
        secs = time.time() - start
        try:
            if why:
                f.write(f"\n[{why}]\n".encode())
                f.flush()
            r = digest_log(own, code, tail, len(header))
            own.seek(-1, os.SEEK_END)
            f.write((b"" if own.read(1) == b"\n" else b"\n") + f"[exit {code} in {secs:.1f}s]\n".encode())
            f.flush()
        except OSError as e:  # the disk is full: the exit code still stands
            r = {"lines": 0, "shown": [f"[the saved output could not be read: {c.clip(str(e), 100)}]"], "tests": None, "suspect": ""}
        try:
            ours = os.fstat(own.fileno()).st_ino == os.stat(log).st_ino
        except OSError:
            ours = False
    try:
        if ours:
            _cap_log(log, int(cfg["log_cap_mb"]) << 20)
            _prune_logs(log.parent, int(cfg["keep_logs"]))
        else:
            r["shown"].append("[the log file was replaced or removed meanwhile; these lines are what is left of the output]")
    except OSError:
        pass
    try:  # relative, so the line is short and means the same on another machine
        ref = str(log.relative_to(Path(project))) if project else str(log)
    except ValueError:
        ref = str(log)
    r.update({"exit": code, "seconds": round(secs, 1), "log": str(log), "log_ref": ref})
    if sig:
        r["stopped"] = sig
    return r


def digest_head(r: dict) -> str:
    word = "ok" if r["exit"] == 0 else f"FAILED (exit {r['exit']})"
    return f"{word} in {r['seconds']}s · {r['lines']} lines · full output: {r.get('log_ref') or r['log']}"


def print_digest(command: str, r: dict, where: str = "") -> None:
    print(where + digest_head(r))
    for l in r["shown"]:
        print("  " + l)
    if r["exit"] == 0 and r.get("suspect"):
        print(f"note: exit 0, but the output reports failures: {r['suspect']}")
    if r["exit"] == 141:
        print("note: exit 141 means a later command in the pipe stopped reading early (`| head`, `grep -q`); let it read everything")


# ---------------------------------------------------------------- gates
def gates_path(project: Path) -> Path:
    return Path(project) / ".brain" / "log" / "gates.jsonl"


def releases_path(project: Path) -> Path:
    return Path(project) / ".brain" / "log" / "releases.jsonl"


def head_commit(project: Path) -> str:
    """The current commit, or "" before the first one."""
    return git(project, "rev-parse", "--verify", "--quiet", "HEAD")


def status_paths(project: Path) -> list[str]:
    """Every path `git status` lists; a rename gives both of its names."""
    out = []
    for l in git(project, "status", "--porcelain").splitlines():
        if l.strip():
            out += [p.strip().strip('"') for p in l[3:].split(" -> ")]
    return out


def dirty_paths(project: Path) -> list[str]:
    return [p for p in status_paths(project) if not is_bookkeeping(p)]


def tree_dirty(project: Path) -> bool:
    return bool(dirty_paths(project))


def same_work(project: Path, commit: str, head: str) -> bool:
    """True when nothing but bookkeeping changed between a gated commit and
    HEAD (committing the gate log itself must not turn a green gate stale).
    Renames are listed under both names: a work file moved into ``.brain/``
    is a change to the work."""
    if not commit or not head:
        return False
    if commit == head:
        return True
    if subprocess.run(["git", "-C", str(project), "merge-base", "--is-ancestor", commit, head], capture_output=True).returncode != 0:
        return False
    changed = [l for l in git(project, "diff", "--name-only", "--no-renames", commit, head).splitlines() if l.strip()]
    return all(is_bookkeeping(l) for l in changed)


def _section(m: dict, key: str) -> dict:
    v = m.get(key)
    return v if isinstance(v, dict) else {}


def gates_of(m: dict) -> list[dict]:
    g = m.get("gates")
    return [x for x in g if isinstance(x, dict)] if isinstance(g, list) else []


def gate_id_problem(m: dict) -> str:
    """Why the gates cannot be told apart, or "". Records are found by gate
    id, so two gates with one id would answer for each other."""
    raw = m.get("gates")
    seen: set[str] = set()
    for g in raw if isinstance(raw, list) else []:
        gid = g.get("id") if isinstance(g, dict) else None
        if not isinstance(gid, str) or not gid.strip():
            return "a gate has an empty id; give every gate its own id in .brain/project.json"
        if gid in seen:
            return f"two gates share the id {gid}; give each gate its own id in .brain/project.json"
        seen.add(gid)
    return ""


def masked_command(command: str, pipefail: bool | None = None) -> str:
    """Why a gate command cannot fail as written, or ""."""
    bare = _QUOTED.sub("''", command or "")
    m = _MASK_OR.search(bare)
    if m:
        return f"`|| {c.clip(m.group(1), 30)}` hides a failure"
    if _MASK_END.search(bare):
        return "it ends in `; true` or `exit 0`, so its exit code is always 0"
    if re.search(r"--pass-?with-?no-?tests\b", bare, re.I):
        return "`--passWithNoTests` passes when no test runs"
    if pipefail is None:
        pipefail = shell_argv("")[1]
    if not pipefail and _PIPE.search(bare):
        return "it pipes into another command and there is no bash here, so a failure before the pipe is hidden"
    return ""


def checklist_state(project: Path, g: dict) -> tuple[int, str]:
    """(0 or 1, what was found): green only when the file exists, has at
    least one box and none of them is unchecked."""
    rel = str(g.get("file") or "").strip()
    path = Path(project) / rel
    if not rel or not path.is_file():
        return 1, f"checklist file {rel or '(none set)'} not found"
    boxes = [m.group(1) for m in map(BOX_RE.match, c.read_text(path).splitlines()) if m]
    todo = sum(b == " " for b in boxes)
    if todo:
        return 1, f"{todo} unchecked box(es) in {rel}"
    if not boxes:
        return 1, f"no checkbox (`- [ ]`) found in {rel}"
    return 0, f"{len(boxes)} box(es) ticked in {rel}"


def owner_confirmation(project: Path, gid: str, head: str, rows: list[dict]) -> dict | None:
    """The latest confirmation of an owner gate, if it still covers the work."""
    for rec in reversed(rows):
        if rec.get("gate") == gid and rec.get("kind") == "owner" and rec.get("exit") == 0 and str(rec.get("evidence", "")).startswith("owner:turn@"):
            return rec if same_work(project, str(rec.get("commit") or ""), head) else None
    return None


def confirm_gate(project: Path, gid: str, quote: str | None) -> int:
    """`brain gate confirm <id> --quote "<his words>"`: an owner gate turns
    green only on words the owner typed in this session, for this commit."""
    owners = [g.get("id") for g in gates_of(c.load_manifest(project)) if g.get("kind") == "owner"]
    if gid not in owners:
        print(f"no owner gate named {gid} in .brain/project.json" + (f" (owner gates: {', '.join(map(str, owners))})" if owners else ""))
        return 1
    if dirty_paths(project) or not head_commit(project):
        print("commit the work first: a confirmation is tied to the commit he approved")
        return 1
    from . import learn  # loaded only here: `brain run` must stay quick
    evidence, why = learn.verify_owner_quote(quote or "")
    if not evidence:
        print(f"not confirmed: {why}")
        return 1
    head = head_commit(project)
    c.append_jsonl(gates_path(project), {"gate": gid, "kind": "owner", "at": c.now_iso(), "session": c.session_id(), "commit": head,
                                         "dirty": False, "exit": 0, "evidence": evidence, "note": "confirmed by the owner"})
    print(f"gate {gid}: confirmed by the owner for {head[:7]}; it holds until the work changes")
    return 0


def run_gates(project: Path, only: str | None = None, keep_going: bool = False) -> tuple[int, list[dict]]:
    """Run or evaluate each gate in manifest order and record what happened.
    After the first red command gate the rest are not run unless
    ``keep_going``; they come back marked ``_skipped`` and are not recorded."""
    m, cfg = c.load_manifest(project), cfg_of()
    results: list[dict] = []
    worst, stopped, rows = 0, False, None
    for g in gates_of(m):
        gid, kind = g.get("id"), g.get("kind")
        if only and gid != only:
            continue
        rec = {"gate": gid, "kind": kind, "at": c.now_iso(), "session": c.session_id(),
               "commit": head_commit(project), "dirty": tree_dirty(project)}
        record = True
        if stopped:
            rec.update({"exit": None, "note": "not run", "_skipped": True})
            record = False
        elif kind == "checklist":
            rec["exit"], rec["note"] = checklist_state(project, g)
        elif kind == "owner":
            rows = c.read_jsonl(gates_path(project)) if rows is None else rows
            ok = owner_confirmation(project, gid, rec["commit"], rows)
            if ok:  # the confirmation is the record; it is not written again
                rec.update({"exit": 0, "evidence": ok["evidence"], "note": f"confirmed by the owner on {str(ok.get('commit'))[:7]}"})
                record = False
            else:
                rec.update({"exit": None, "note": f'waits for the owner: brain gate confirm {gid} --quote "<his words>"'})
        elif kind != "command":
            rec.update({"exit": None, "note": f"unknown gate kind {kind!r}"})
        elif not (g.get("command") or "").strip():
            rec.update({"exit": None, "note": "no command set in .brain/project.json yet"})
        else:
            own = g.get("timeout")
            r = run_filtered(g["command"], project, project,
                             timeout=own if isinstance(own, int) and not isinstance(own, bool) and own > 0 else int(cfg["gate_timeout"]))
            rec.update({"command": c.redact_secrets(g["command"]), "exit": r["exit"], "seconds": r["seconds"], "log": r["log_ref"]})
            if r["tests"] is not None:
                rec["tests"] = r["tests"]
            if r["suspect"]:
                rec["suspect"] = r["suspect"]
            rec["_digest"] = r
            stopped = bool(r.get("stopped")) or (r["exit"] != 0 and not keep_going)
        if isinstance(rec["exit"], int):
            worst = worst or rec["exit"]
        results.append(rec)
        if record:
            c.append_jsonl(gates_path(project), {k: v for k, v in rec.items() if not k.startswith("_")})
        if rec.get("_digest", {}).get("stopped"):
            break  # brain itself was told to stop
    return worst, results


def _latest(rows: list[dict]) -> dict:
    out: dict = {}
    for rec in rows:
        if not rec.get("_skipped"):
            out[rec.get("gate")] = rec
    return out


def green_at_head(project: Path, fresh: list[dict] | None = None) -> tuple[bool, list[str]]:
    """True when every gate is met for the current work: command gates exit 0
    on this commit with a clean tree, checklists fully ticked, owner gates
    confirmed. With ``fresh`` (the results of a run the caller just made) only
    those results count for command gates, which is what `release --push`
    uses; without it the latest stored record per gate is read, which is
    enough for a report."""
    m = c.load_manifest(project)
    problem = gate_id_problem(m)
    if problem:
        return False, [problem]
    head = head_commit(project)
    rows = c.read_jsonl(gates_path(project))
    latest = _latest(rows if fresh is None else fresh)
    gates = gates_of(m)
    why = []
    if not any(g.get("kind") == "command" and (g.get("command") or "").strip() for g in gates):
        why.append("no command gate is defined, so nothing proves this commit works")
    for g in gates:
        gid, kind = g["id"], g.get("kind")
        if kind == "command":
            if not (g.get("command") or "").strip():
                continue
            rec = latest.get(gid)
            if not rec:
                why.append(f"gate {gid} did not run (an earlier gate was red)" if fresh is not None else f"gate {gid} has never run")
            elif rec.get("exit") != 0:
                why.append(f"gate {gid} failed (exit {rec.get('exit')})" if fresh is not None else f"gate {gid} last exited {rec.get('exit')}")
            elif rec.get("command") not in (None, c.redact_secrets(g["command"])):
                why.append(f"gate {gid}'s command changed since it last ran")
            elif not same_work(project, rec.get("commit", ""), head):
                why.append(f"gate {gid} passed on a different commit ({str(rec.get('commit'))[:7]}); the work has changed since")
            elif rec.get("dirty"):
                why.append(f"gate {gid} ran with uncommitted changes")
        elif kind == "checklist":
            code, note = checklist_state(project, g)
            if code:
                why.append(f"gate {gid} (checklist): {note}")
        elif kind == "owner":
            if not owner_confirmation(project, gid, head, rows):
                why.append(f'gate {gid} (owner) is not confirmed for this work: brain gate confirm {gid} --quote "<his words>"')
        else:
            why.append(f"gate {gid} has an unknown kind ({kind})")
    return (not why), why


# ---------------------------------------------------------------- detectors
def _never_touch(path: str, entries: list[str]) -> bool:
    p = path.removeprefix("./")
    for e in entries:
        e = e.removeprefix("./")
        if p.rstrip("/") == e.rstrip("/") or p.startswith(e.rstrip("/") + "/") or fnmatch.fnmatch(p, e):
            return True
    return False


def _json_lines(text: str) -> list[dict]:
    out = []
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            out.append(row)
    return out


def detect(project: Path, base: str | None = None, results: list[dict] | None = None, suspects: bool = True) -> tuple[list[str], list[str]]:
    """(holds, notes) for the change being gated, against the release branch.

    A hold is a way to be green without the work being green: tests switched
    off or removed, a gate command changed or made unable to fail, protected
    files changed, an exit 0 whose output reports failures, fewer tests than
    the last green run. `release` refuses on a hold unless the owner's reason
    is given. A note (a stub, a TODO) is only shown."""
    m = c.load_manifest(project)
    branch = _section(m, "release").get("branch") or "main"
    base = base or f"origin/{branch}"
    has_base = bool(git(project, "rev-parse", "--verify", "--quiet", base))
    span = f"{base}...HEAD"
    holds, notes = [], []
    diff = git(project, "diff", "--unified=0", "--no-renames", span, "--", ".", ":(exclude).brain").splitlines() if has_base else []
    skips = [l for l in diff if SKIP_RE.search(l)]
    if skips:
        holds.append(f"{len(skips)} added line(s) skip or isolate tests, e.g. {c.clip(skips[0][1:].strip(), 80)}")
    gone, new = [l for l in diff if TEST_GONE_RE.search(l)], sum(1 for l in diff if TEST_NEW_RE.search(l))
    deleted = [f for f in git(project, "diff", "--diff-filter=D", "--name-only", span).splitlines()
               if TEST_FILE_RE.search(f) and not f.startswith(".brain/")] if has_base else []
    parts = ([f"{len(gone) - new} test(s) removed, e.g. {c.clip(gone[0][1:].strip(), 60)}"] if len(gone) > new else []) \
        + ([f"{len(deleted)} test file(s) deleted, e.g. {deleted[0]}"] if deleted else [])
    if parts:
        holds.append("tests removed: " + "; ".join(parts))
    stubs = [l for l in diff if STUB_RE.search(l)]
    if stubs:
        notes.append(f"{len(stubs)} added line(s) are TODO or unimplemented stubs, e.g. {c.clip(stubs[0][1:].strip(), 80)}")
    now = {g["id"]: str(g.get("command") or "") for g in gates_of(m) if g.get("kind") == "command" and isinstance(g.get("id"), str)}
    for gid, command in now.items():
        reason = masked_command(command)
        if reason:
            holds.append(f"gate {gid} cannot fail as written: {reason}")
    if has_base:
        try:
            old = json.loads(git(project, "show", f"{base}:.brain/project.json") or "{}")
        except ValueError:
            old = {}
        for g in gates_of(old if isinstance(old, dict) else {}):
            gid, was = g.get("id"), str(g.get("command") or "")
            if g.get("kind") != "command" or not was.strip():
                continue
            if not now.get(gid, "").strip():
                holds.append(f"gate {gid} was removed since the last release on {branch}")
            elif now[gid] != was:
                holds.append(f"gate {gid}'s command changed since the last release on {branch} (was: {c.clip(c.redact_secrets(was), 60)})")
    never = _section(m, "paths").get("never_touch")
    never = [e.strip() for e in never if isinstance(e, str) and e.strip()] if isinstance(never, list) else []
    if never:
        changed = set(git(project, "diff", "--name-only", "--no-renames", span).splitlines()) if has_base else set()
        hit = sorted(f for f in changed | set(status_paths(project)) if f and _never_touch(f, never))
        if hit:
            holds.append(f"paths.never_touch: {len(hit)} protected file(s) changed, e.g. {', '.join(hit[:3])}")
    latest = _latest(c.read_jsonl(gates_path(project)) if results is None else results)
    before = None
    for gid in now:
        rec = latest.get(gid) or {}
        if rec.get("exit") != 0:
            continue
        if suspects and rec.get("suspect"):
            holds.append(f"gate {gid} exited 0 but its output reports failures: {c.clip(rec['suspect'], 80)}")
        if isinstance(rec.get("tests"), int) and has_base:
            if before is None:  # the test count of each gate's last green run on the release branch
                before = {r.get("gate"): r["tests"] for r in _json_lines(git(project, "show", f"{base}:.brain/log/gates.jsonl"))
                          if r.get("exit") == 0 and isinstance(r.get("tests"), int)}
            if rec["tests"] < before.get(gid, 0):
                holds.append(f"gate {gid} ran {rec['tests']} test{'' if rec['tests'] == 1 else 's'}; its last green run on {branch} ran {before[gid]}")
    return holds, notes


def diff_detectors(project: Path, base: str | None = None) -> list[str]:
    """Every detector line for the change against the release branch."""
    holds, notes = detect(project, base)
    return holds + notes


def never_failed(project: Path, m: dict) -> list[str]:
    """`id:hash` of each command gate with no red run on record: a check that
    has never been seen to fail may be unable to."""
    rows = c.read_jsonl(gates_path(project))
    out = []
    for g in gates_of(m):
        command = c.redact_secrets(str(g.get("command") or ""))
        if g.get("kind") != "command" or not command.strip():
            continue
        if not any(r.get("gate") == g.get("id") and r.get("command") == command and isinstance(r.get("exit"), int)
                   and r["exit"] != 0 and r["exit"] not in NOT_A_FAILURE for r in rows):
            out.append(f"{g.get('id')}:{c.sha256_text(command)[:8]}")
    return out


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
def _inside_managed(here: Path) -> bool:
    root = Path(c.BRAIN_ROOT).resolve()
    for p in (here, *here.parents):
        if p == root:
            return False
        if c.is_managed(p):
            return True
    return False


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
    here = Path.cwd().resolve()
    project = c.resolve_project(args.project)
    if project is not None and not c.is_managed(project):
        project = None
    where = ""
    if args.cwd:
        cwd = Path(args.cwd).expanduser().resolve()
    elif project is not None and not _inside_managed(here):
        # Typed from outside any project (the folder holding both repositories,
        # or the brain): the one project in play is where the command belongs.
        cwd, where = project.resolve(), f"in {project.name}: "
    else:
        cwd = here
    # The log goes into the project only when the command ran inside it.
    if project is not None and not args.project and project.resolve() not in (cwd, *cwd.parents):
        project = None
    if not cwd.is_dir():
        print(f"no such folder: {cwd}")
        return 2
    r = run_filtered(command, cwd, project, args.tail, args.timeout)
    print_digest(command, r, where)
    return r["exit"]


def _fit(lines: list[str], room: int) -> list[str]:
    if len(lines) <= room:
        return lines
    head = max(1, (room - 1) // 2)
    return lines[:head] + ["…"] + lines[len(lines) - max(1, room - 1 - head):]


def result_lines(results: list[dict], room: int = OUTPUT_LINES) -> list[str]:
    """What a gate run prints: the digest of the first red gate, one line for
    each other gate, within ``room`` lines where the gate count allows."""
    lines, skipped, first = [], [], None
    for rec in results:
        gid, d = rec["gate"], rec.get("_digest")
        if rec.get("_skipped"):
            skipped.append(str(gid))
        elif d is None:
            lines.append(f"gate {gid}: " + (rec.get("note") or "") if rec["exit"] is None else
                         f"gate {gid}: {'ok' if rec['exit'] == 0 else 'FAILED'} · {rec.get('note')}")
        elif d["exit"] != 0 and first is None:
            lines.append(f"gate {gid}: " + digest_head(d))
            first = (len(lines), d["shown"])
        elif d["exit"] != 0:
            lines.append(f"gate {gid}: FAILED (exit {d['exit']}) in {d['seconds']}s · full output: {d['log_ref']}")
        elif d["suspect"]:
            lines.append(f"gate {gid}: exit 0, but its output reports failures ({d['suspect']}) · full output: {d['log_ref']}")
        else:
            lines.append(f"gate {gid}: ok in {d['seconds']}s · {d['lines']} lines" + (f" · {d['tests']} tests" if d["tests"] is not None else ""))
    if skipped:
        lines.append(f"not run after the first red gate: {', '.join(skipped)} (--keep-going runs all)")
    if first:
        at, shown = first
        lines[at:at] = ["  " + l for l in _fit(shown, max(3, room - len(lines)))]
    return lines


def _age(at: str) -> str:
    try:
        then = _dt.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return ""
    mins = int((c.now() - (then if then.tzinfo else then.replace(tzinfo=_dt.timezone.utc))).total_seconds() // 60)
    if mins < 0:
        return ""
    return f" ({mins} min ago)" if mins < 120 else f" ({mins // 60} h ago)" if mins < 2880 else f" ({mins // 1440} d ago)"


def show_last(project: Path, only: str | None) -> int:
    """`brain gate --last`: the recorded result of each gate's last run and
    the failing lines of the first red one, read from disk. Nothing is run."""
    latest = _latest(c.read_jsonl(gates_path(project)))
    recs = [latest[g.get("id")] for g in gates_of(c.load_manifest(project)) if g.get("id") in latest and (not only or g.get("id") == only)]
    if not recs:
        print("no gate has run yet" + (f" with the id {only}" if only else "") + ": brain gate")
        return 1
    head, shown, lines = head_commit(project), False, []
    for rec in recs:
        gid, code = rec.get("gate"), rec.get("exit")
        if not isinstance(code, int):
            lines.append(f"gate {gid}: {rec.get('note') or 'not run'}")
            continue
        commit = str(rec.get("commit") or "")
        fresh = "this work" if same_work(project, commit, head) and not rec.get("dirty") else "the work has changed since"
        detail = rec.get("log") if code != 0 and rec.get("log") else rec.get("note")
        lines.append(f"gate {gid}: exit {code} at {str(rec.get('at', ''))[:16]}{_age(rec.get('at', ''))} on {commit[:7] or 'no commit'}, {fresh}"
                     + (f" · {detail}" if detail else ""))
        if code != 0 and rec.get("log") and not shown:
            shown = True
            log = Path(project) / str(rec["log"])
            if log.is_file():
                with open(log, "rb") as f:
                    start = len(f.readline())
                    f.seek(max(0, os.path.getsize(log) - 64))
                    foot = FOOTER_RE.search(f.read())
                end = os.path.getsize(log) - (len(foot.group(0)) if foot else 0)
                lines += ["  " + l for l in _fit(digest_log(log, code, 6, start, max(start, end))["shown"], OUTPUT_LINES - len(recs) - 1)]
            else:
                lines.append("  its output is not on this machine (run logs are not committed): brain gate")
    print("\n".join(lines))
    return 1 if any(r.get("exit") != 0 for r in recs if isinstance(r.get("exit"), int)) or not any(isinstance(r.get("exit"), int) for r in recs) else 0


def cmd_gate(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    target = getattr(args, "target", None)
    if args.id == "confirm" and target:
        return confirm_gate(project, target, getattr(args, "quote", None))
    if getattr(args, "last", False):
        return show_last(project, args.id)
    m = c.load_manifest(project)
    problem = gate_id_problem(m)
    if problem:
        print(problem)
        return 1
    if args.id == "confirm" and not any(g.get("id") == "confirm" for g in gates_of(m)):
        print('usage: brain gate confirm <owner-gate-id> --quote "<words he typed in this chat>"')
        return 1
    worst, results = run_gates(project, args.id, keep_going=bool(getattr(args, "keep_going", False)))
    if not results:
        print(f"no gate {'named ' + args.id if args.id else 'defined'} in .brain/project.json")
        return 1
    holds, notes = detect(project, results=results, suspects=False)
    extra = [f"check this before calling it done: {d}" for d in (holds + notes)[:4]]
    if len(holds + notes) > 4:
        extra.append(f"… and {len(holds + notes) - 4} more: brain release lists what holds a release")
    if any(r.get("dirty") for r in results if r["exit"] == 0):
        extra.append("note: ran with uncommitted changes; a release needs them committed")
    if not any(isinstance(r["exit"], int) for r in results):
        extra.append("no gate ran, so nothing is proven: set gates[].command in .brain/project.json")
        worst = 1
    print("\n".join(result_lines(results, OUTPUT_LINES - len(extra)) + extra))
    return 1 if worst else 0


def sync_record(project: Path, branch: str) -> str:
    """Commit the bookkeeping and fast-forward the release branch to it with a
    plain push, so the branch holds the record of its own release. Returns ""
    when the release branch holds HEAD, else what is missing."""
    from .state import push_bookkeeping
    msg = push_bookkeeping(project)
    head = head_commit(project)
    if any(is_bookkeeping(p) for p in status_paths(project)):
        return c.clip(msg, 140)
    remote = git(project, "rev-parse", "--verify", "--quiet", f"origin/{branch}")
    if remote == head:
        return ""
    if not remote:
        return c.clip(msg, 140) or f"origin/{branch} is not known here"
    if not same_work(project, remote, head):
        return "more than bookkeeping differs from " + branch  # only a release may push that
    try:
        pushed = subprocess.run(["git", "-C", str(project), "push", "origin", f"HEAD:{branch}"], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return "the push timed out"
    return "" if pushed.returncode == 0 else "push failed: " + c.clip(pushed.stderr, 140)


def accept_release(project: Path, branch: str, commit: str, push: bool) -> int:
    """`brain release --accept [commit]`: record that the owner accepted a
    release, so "Go back" knows which one to return to."""
    rows = c.read_jsonl(releases_path(project))
    released = [str(r.get("commit")) for r in rows if r.get("commit") and not r.get("accepted")]
    if not released:
        print("no release is recorded yet, so there is nothing to accept: brain release --push")
        return 1
    full = released[-1]
    if commit:
        full = git(project, "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
        if full not in released:
            print(f"{commit} is not a recorded release; they are listed in .brain/log/releases.jsonl")
            return 1
    if not any(r.get("accepted") and r.get("commit") == full for r in rows):
        c.append_jsonl(releases_path(project), {"at": c.now_iso(), "accepted": True, "commit": full, "branch": branch, "session": c.session_id()})
    saved = "`brain checkpoint --push` saves it"
    if push:
        missing = sync_record(project, branch)
        saved = f"saved on {branch}" if not missing else f"not on {branch} yet ({missing})"
    print(f"recorded: the owner accepted release {full[:7]}; Go back returns to it ({saved})")
    return 0


def cmd_release(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    m = c.load_manifest(project)
    rel = _section(m, "release")
    rule, branch = rel.get("rule", "none"), rel.get("branch") or "main"
    if getattr(args, "accept", None) is not None:
        return accept_release(project, branch, args.accept, bool(args.push))
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
        tip = git(project, "rev-parse", "--verify", "--quiet", f"origin/{branch}") or head_commit(project)
        return live_report(project, rel, tip, args.live_wait)
    reason = getattr(args, "accept_skips", None)
    if reason is not None:
        reason = " ".join(str(reason).split())
        problem = c.secret_problem(reason) or ("" if len(reason) >= 8 else
                                               '--accept-skips needs the reason in words: --accept-skips "<what he agreed to, and why>"')
        if problem:
            print(problem)
            return 1
    problem = gate_id_problem(m)
    if problem:
        print("refusing to release: " + problem)
        return 1
    dirty = dirty_paths(project)
    if dirty:
        print(f"refusing: uncommitted changes ({', '.join(dirty[:3])}{f', +{len(dirty) - 3} more' if len(dirty) > 3 else ''}). "
              "Commit them (build outputs belong in .gitignore), then release.")
        return 1
    git(project, "fetch", "origin", branch)
    remote = git(project, "rev-parse", "--verify", "--quiet", f"origin/{branch}")
    if remote:
        if subprocess.run(["git", "-C", str(project), "merge-base", "--is-ancestor", f"origin/{branch}", "HEAD"]).returncode != 0:
            print(f"refusing: origin/{branch} has commits this branch lacks. Merge origin/{branch} into this branch, run the gates again, then release. (Never force-push.)")
            return 1
    head = head_commit(project)
    if remote and same_work(project, remote, head):
        # Only bookkeeping differs from the release branch: there is no work to gate or release.
        if not args.push:
            print(f"nothing to release: {branch} already holds this work ({head[:7]})")
            return 0
        missing = sync_record(project, branch)
        print(f"already released: {branch} holds this work; bookkeeping synced" if not missing else
              f"already released: {branch} holds this work; bookkeeping not synced ({missing})")
        return 1 if missing else 0
    fresh = None
    if args.push:
        # A release trusts only what it sees: the gates run here, on this commit.
        fresh = run_gates(project)[1]
        ok, why = green_at_head(project, fresh)
        if ok and head_commit(project) != head:
            ok, why = False, ["the commit changed while the gates ran"]
    else:
        ok, why = green_at_head(project)
        if not ok and args.run_gates:
            fresh = run_gates(project)[1]
            ok, why = green_at_head(project, fresh)
    if not ok:
        print("refusing to release: not every gate is green on this commit")
        for w in why[:5]:
            print(" -", w)
        red = next((r["_digest"] for r in fresh or [] if r.get("_digest") and r["exit"] != 0), None)
        if red:
            print("\n".join([f"   full output: {red['log_ref']}"] + ["   " + l for l in _fit(red["shown"], 7)]))
        elif fresh is None:
            print("next: `brain release --push` runs the gates itself; `brain gate --last` shows a recorded failure")
        return 1
    holds, _notes = detect(project, results=fresh)
    if holds and not reason:
        print(f"refusing to release: {len(holds)} thing(s) can make a release green without the work being green")
        for h in holds[:8]:
            print(" -", h)
        print('fix them, or after the owner\'s yes: brain release --push --accept-skips "<what he agreed to, and why>"')
        return 1
    if not args.push:
        print(f"ready to release {head[:7]} to {branch}: gates are green on this commit and it fast-forwards. Run again with --push to push.")
        return 0
    push = subprocess.run(["git", "-C", str(project), "push", "origin", f"HEAD:{branch}"], capture_output=True, text=True)
    if push.returncode != 0:
        print("push failed:", c.clip(push.stderr, 300))
        return 1
    record = {"at": c.now_iso(), "commit": head, "branch": branch, "session": c.session_id()}
    if holds:
        record.update({"accept_skips": reason, "held": [c.clip(h, 160) for h in holds]})
    told = {k for r in c.read_jsonl(releases_path(project)) for k in (r.get("never_failed") or [])}
    unproven = [k for k in never_failed(project, m) if k not in told]
    if unproven:
        record["never_failed"] = unproven
    c.append_jsonl(releases_path(project), record)
    missing = sync_record(project, branch)
    print(f"released {head[:7]} to {branch} (fast-forward, gates green)"
          + (f"; the release record is on {branch}" if not missing else f"; its record is not on {branch} yet ({missing}): brain checkpoint --push"))
    if holds:
        print(f"released with {len(holds)} accepted hold(s), reason on record: {c.clip(reason, 120)}")
    if unproven:
        print(f"note: gate {', '.join(k.split(':')[0] for k in unproven)} has never been seen to fail; a check that cannot fail proves nothing")
    if rel.get("live_url"):
        return live_report(project, rel, head_commit(project) if not missing else head, args.live_wait)
    print("no live address is set (release.live_url), so the deployment itself was not checked")
    return 0


def register(sub) -> None:
    p = sub.add_parser("run", help="run a command; keep the full output in a file, print only the result")
    c.add_project_arg(p)
    p.add_argument("--tail", type=int, default=6)
    p.add_argument("--timeout", type=int, default=None, help=f"seconds before the command and all it started are stopped (default {DEFAULT_CFG['run_timeout']})")
    p.add_argument("--cwd", help="where to run (default: here, or the one detected project when typed outside any project)")
    p.add_argument("cmd", nargs="...")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("gate", help="run the project's gates and record each exit code",
                       usage='brain gate [id] [--keep-going] [--last] | brain gate confirm <owner-gate-id> --quote "<his words>"')
    c.add_project_arg(p)
    p.add_argument("id", nargs="?", help="one gate; or `confirm` followed by an owner gate's id")
    p.add_argument("target", nargs="?", help="with `confirm`: the owner gate to confirm")
    p.add_argument("--all", action="store_true", help="every gate in order (the default)")
    p.add_argument("--keep-going", action="store_true", help="run the remaining gates after one is red")
    p.add_argument("--last", action="store_true", help="show the recorded result and failing lines of the last run; run nothing")
    p.add_argument("--quote", help="with `confirm`: words the owner typed in this session")
    p.set_defaults(func=cmd_gate)
    p = sub.add_parser("release", help="run the gates on this commit and push to the release branch only if all are green; never force")
    c.add_project_arg(p)
    p.add_argument("--push", action="store_true", help="run every gate here, then push (without it: report only)")
    p.add_argument("--run-gates", action="store_true", help="without --push: run the gates when the record is not green on this commit")
    p.add_argument("--accept-skips", metavar="REASON", help="release although tests were switched off or removed, a gate changed or protected files changed: the owner's reason, kept in the release log")
    p.add_argument("--accept", nargs="?", const="", metavar="COMMIT", help="record that the owner accepted a release (default: the latest)")
    p.add_argument("--check-live", action="store_true", help="only re-check the live address; push nothing")
    p.add_argument("--live-wait", type=int, default=120, help="seconds to wait for the live address (bounded)")
    p.set_defaults(func=cmd_release)
