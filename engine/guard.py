"""Zone guard: which brain paths a session may edit directly, and the CI
check over a diff.

Why: the owner wants the brain to change only through its own learning
pipeline. Four zones make that checkable (MASTER_PLAN 6.4, EXECUTION_PLAN 4.3):
- inbox   ``learning/inbox/``: any session may append records here;
- state   ``learning/radar/``: bookkeeping a script rewrites in a working
  session (radar etags and seen ids); allowed like the inbox, but rewrites
  are fine and the manifest replay ignores it, because it is not memory;
- learned ``memory/``, ``owner/``, ``stats/``, ``playbooks/``, ``learning/``:
  written only by ``brain learn apply``;
- kernel  everything else (engine, method, CLAUDE.md) plus the hand-written
  files inside the learned directories (prices and roles, learning
  constants, radar sources, the promotion rules page): changes need the
  owner, because learning must never change its own rules (I-09).
Until VERSION.json sets ``learned_zone_locked`` the brain is being built, so
every rule here downgrades to a warning.

Once it is locked, the PreToolUse hook (``.claude/hooks/guard_paths.py``)
asks ``hook_decision`` about each edit and each shell command: a learned-zone
path is refused, a kernel path is put to the owner, and the files that hold
the lock itself (``LOCK_FILES``, ``LOCK_DIRS``) are refused outright, because
a lock that one edit can remove protects nothing. ``guard diff`` fails on a
change that sets the lock back.
"""
from __future__ import annotations

import json
import os
import posixpath
import re
import shlex
import subprocess
from pathlib import Path

from . import common as c

# Inside the learned directories but hand-written.
KERNEL_FILES = ("memory/models.json", "memory/ml_config.json", "memory/radar_sources.json",
                "learning/PROMOTION_RULES.md")
STATE_DIRS = ("learning/radar/",)
# The lock on the learned zone and what enforces it. In a locked brain a
# session never changes these; the owner does, outside a session.
LOCK_FILES = ("VERSION.json", ".claude/settings.json", "engine/guard.py")
LOCK_DIRS = (".claude/hooks/",)
_KERNEL_FOLDED = tuple(k.casefold() for k in KERNEL_FILES)


def normalise_rel(relative_path: str) -> str | None:
    """The canonical brain-relative form of a path (``posixpath.normpath``),
    or None when it escapes the brain root through ``..`` or is empty. A
    leading ``/`` or ``./`` is read as the brain root, as before; the
    normalisation is what stops ``memory/../evals/x`` passing for ``memory/``."""
    rel = str(relative_path).replace("\\", "/").lstrip("/")
    if not rel or "\0" in rel:
        return None
    rel = posixpath.normpath(rel)
    if rel in (".", "..") or rel.startswith("../"):
        return None
    return rel


def zone_of(relative_path: str) -> str:
    """"inbox", "state", "learned" or "kernel" for a path relative to the brain root."""
    rel = normalise_rel(relative_path)
    if rel is None:
        return "kernel"  # outside the brain, or not a plain path: the strictest zone
    rel = rel.casefold()  # some disks ignore case: MEMORY/items.jsonl is then memory/items.jsonl
    if rel.startswith(c.INBOX_DIR):
        return "inbox"
    if rel.startswith(STATE_DIRS):
        return "state"
    if rel in _KERNEL_FOLDED:
        return "kernel"
    if rel.startswith(c.LEARNED_ZONE):
        return "learned"
    return "kernel"


def is_lock_file(relative_path: str) -> bool:
    """True for the files that hold or enforce the lock on the learned zone."""
    rel = normalise_rel(relative_path)
    if rel is None:
        return False
    rel = rel.casefold()
    return rel in tuple(f.casefold() for f in LOCK_FILES) or (rel + "/").startswith(tuple(d.casefold() for d in LOCK_DIRS))


def locked(brain_root: Path | None = None) -> bool:
    data = c.read_json(Path(brain_root or c.BRAIN_ROOT) / "VERSION.json", {}) or {}
    return bool(data.get("learned_zone_locked"))


def check_path(path: str, mode: str = "work", brain_root: Path | None = None) -> tuple[int, str]:
    """(exit code, one-line reason) for a direct edit of ``path``."""
    root = Path(brain_root or c.BRAIN_ROOT).resolve()
    p = Path(path).expanduser()
    p = (p if p.is_absolute() else Path.cwd() / p).resolve()
    try:
        rel = p.relative_to(root).as_posix()
    except ValueError:
        return 0, "outside the brain: allowed"
    zone = zone_of(rel)
    if mode == "bootstrap" or not locked(root):
        return 0, f"warning: {zone} zone edit allowed only because the brain is in its bootstrap period"
    if zone == "inbox":
        return 0, "inbox: allowed (append records only)"
    if zone == "state":
        return 0, "state: allowed (rewritten by its own script, not part of memory)"
    if zone == "kernel":
        return 2, "kernel change: needs the owner"
    if mode == "learn":
        return 0, "learned zone: allowed in learn mode"
    return 2, "learned zone: change it through `brain learn` (note, then consolidate/apply)"


# ---------------------------------------------------------------- hook (locked brain)
LEARNED_REASON = "is in the learned zone: change it through `brain learn` (note, then consolidate)"
LOCK_REASON = "is part of the lock on the learned zone: only the owner changes it, outside a session"
WRITERS = frozenset("rm rmdir unlink mv tee truncate shred touch chmod chown patch".split())   # every path named is written
COPIERS = frozenset("cp install ln rsync".split())                                              # the last path named is written
GIT_WRITERS = frozenset("checkout restore rm mv apply clean stash reset".split())
INTERPRETERS = frozenset("python python3 node perl ruby".split())
SHELLS = frozenset("sh bash zsh dash".split())
WRAPPERS = frozenset("sudo command env nohup time exec nice xargs".split())
CODE_WRITES = re.compile(r"write_text|write_bytes|\.write\(|open\([^)]*,\s*['\"][wax+]|unlink|rename|remove|rmtree|dump\(|truncate|writeFile")
_OPERATOR = re.compile(r"[<>|&;()]+")


def _rel_in_brain(path: str, cwd: str | Path, root: Path) -> str | None:
    """A path as the brain-relative posix form, or None when it is outside the brain."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path(cwd or ".") / p
    try:
        return p.resolve().relative_to(root).as_posix()
    except (ValueError, OSError, RuntimeError):
        return None


def _protected(rel: str, parents: bool = False) -> str:
    """"lock", "learned" or "" for a brain-relative path. With ``parents`` a
    folder that holds protected files counts too (``rm -rf memory``, ``git
    checkout .``)."""
    if is_lock_file(rel):
        return "lock"
    if zone_of(rel) == "learned" or (rel + "/").casefold() in c.LEARNED_ZONE:
        return "learned"
    if parents:
        below = "" if rel == "." else rel.casefold() + "/"
        if any(x.casefold().startswith(below) for x in LOCK_FILES + LOCK_DIRS):
            return "lock"
        if any(x.startswith(below) for x in c.LEARNED_ZONE):
            return "learned"
    return ""


def _shell_tokens(command: str) -> list[str]:
    try:
        lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        return list(lex)
    except ValueError:  # unbalanced quotes: split on spaces and operators, and judge what is left
        return re.findall(r"[<>|&;()]+|[^\s<>|&;()]+", command)


def bash_write_targets(command: str, cwd: str | Path, brain_root: Path | None = None) -> list[tuple[str, str]]:
    """(brain-relative path, "learned" | "lock") for each protected path a
    shell command appears to write.

    This is a pattern check, not a shell parser. It sees: a redirect whose
    target is a protected path; ``rm``, ``mv``, ``tee``, ``truncate`` and
    their kind naming one; ``cp`` and its kind with one as the destination;
    ``sed -i`` and ``perl -i``; ``dd of=``; ``git checkout|restore|rm|mv|
    apply|clean|stash|reset`` naming one; ``sh -c`` text, checked the same
    way; inline code (``-c``, ``-e`` or a here-document) of a script
    interpreter that names one beside a write call; and a ``cd`` earlier in
    the command. It does not see a path built from a variable it cannot
    resolve (only ``$CLAUDE_PROJECT_DIR``, ``$HOME``, ``$PWD`` and ``~``
    are), a write made by a script file, ``find -delete``, or ``git reset
    --hard``. It can refuse a command that only reads when the read is
    written in one of those forms. It lowers the chance of an accident;
    ``learn verify`` in CI is what holds the zone."""
    root = Path(brain_root or c.BRAIN_ROOT).resolve()
    here = Path(cwd or ".")
    hits: list[tuple[str, str]] = []

    def check(token: str, parents: bool = False, base: Path | None = None) -> None:
        known = {"CLAUDE_PROJECT_DIR": str(root), "HOME": str(Path.home()), "PWD": str(here)}
        t = re.sub(r"\$\{?(CLAUDE_PROJECT_DIR|HOME|PWD)\}?", lambda m: known[m.group(1)], token)
        if not t or "$" in t or "`" in t:
            return
        rel = _rel_in_brain(t, base or here, root)
        kind = _protected(rel, parents) if rel is not None else ""
        if kind and (rel, kind) not in hits:
            hits.append((rel, kind))

    def check_code(code: str) -> None:
        if CODE_WRITES.search(code):
            for word in re.findall(r"[\w.$~{}/*-]+", code):
                if "/" in word or "." in word:
                    check(word)

    tokens = _shell_tokens(command)
    segments: list[tuple[list[str], list[str]]] = [([], [])]   # (words, redirect targets) per simple command
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if _OPERATOR.fullmatch(tok):
            if ">" in tok:  # a redirect: the next word is written, unless it is a file descriptor
                target = tokens[i + 1] if i + 1 < len(tokens) else ""
                if target and not re.fullmatch(r"\d+|-", target):
                    segments[-1][1].append(target)
                i += 1
            elif "<" not in tok:
                segments.append(([], []))
        else:
            segments[-1][0].append(tok)
        i += 1
    scripted = False
    for seg, targets in segments:
        for t in targets:
            check(t)
        while seg and (re.fullmatch(r"\w+=.*", seg[0]) or os.path.basename(seg[0]) in WRAPPERS):
            seg = seg[1:]
        if not seg:
            continue
        cmd, args = os.path.basename(seg[0]), seg[1:]
        paths = [a for a in args if not a.startswith("-")]
        inline = next((args[n + 1] for n, a in enumerate(args[:-1]) if re.fullmatch(r"-[A-Za-z]*[ce]", a)), None)
        if cmd == "cd" and paths:
            here = here / os.path.expanduser(paths[0])
        elif cmd in WRITERS:
            for a in paths:
                check(a, parents=cmd in ("rm", "rmdir", "mv", "chmod", "chown"))
        elif cmd in COPIERS and len(paths) > 1:
            check(paths[-1])
        elif cmd in ("sed", "perl") and any(re.match(r"-[A-Za-z]*i|--in-place", a) for a in args):
            for a in paths:
                check(a)
        elif cmd == "dd":
            for a in args:
                if a.startswith("of="):
                    check(a[3:])
        elif cmd == "git":
            base = here
            if "-C" in args[:-1]:
                n = args.index("-C")
                base, args = here / args[n + 1], args[:n] + args[n + 2:]
            words = [a for a in args if not a.startswith("-")]
            if words and words[0] in GIT_WRITERS:
                for a in words[1:]:
                    check(a, parents=True, base=base)
        elif cmd in SHELLS and inline is not None:
            hits += [h for h in bash_write_targets(inline, here, root) if h not in hits]
        if cmd in INTERPRETERS:
            scripted = True
            if inline is not None:
                check_code(inline)
    if scripted and "<<" in command:
        check_code(command.split("<<", 1)[1])
    return hits


def hook_decision(tool_input: dict, cwd: str | Path, brain_root: Path | None = None) -> tuple[str, str]:
    """("allow" | "ask" | "deny", one-line reason) for one tool call in a
    LOCKED brain; the hook does not call this while the brain is unlocked.
    ``file_path`` (Edit, Write, MultiEdit) and ``notebook_path`` are judged
    by zone; ``command`` (Bash) by ``bash_write_targets``."""
    root = Path(brain_root or c.BRAIN_ROOT).resolve()
    path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if isinstance(path, str) and path:
        rel = _rel_in_brain(path, cwd, root)
        if rel is None:
            return "allow", ""
        if is_lock_file(rel):
            return "deny", f"{rel} {LOCK_REASON}"
        zone = zone_of(rel)
        if zone == "learned":
            return "deny", f"{rel} {LEARNED_REASON}"
        if zone == "kernel":
            return "ask", f"kernel change: needs the owner ({rel})"
        return "allow", ""
    command = tool_input.get("command")
    if isinstance(command, str) and command.strip():
        hits = bash_write_targets(command, cwd, root)
        if hits:
            rel, kind = hits[0]
            what = "the brain folder, which holds files that are" if rel == "." else f"{rel}, which is"
            more = f" (and {len(hits) - 1} more)" if len(hits) > 1 else ""
            reason = LOCK_REASON if kind == "lock" else LEARNED_REASON
            return "deny", (f"this command appears to write {what} {reason.split(' ', 1)[1]}{more}. "
                            "A pattern check decided this; a command that only reads passes when written without a write form")
    return "allow", ""


# ---------------------------------------------------------------- diff (CI)
def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return p.returncode, p.stdout.decode("utf-8", "replace")


def _added_lines(root: Path, base: str) -> dict[str, list[str]]:
    """Added lines per changed file, tracked (vs base) and untracked."""
    out: dict[str, list[str]] = {}
    _, diff = _git(root, "diff", "-U0", "--no-color", base)
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else None
            if current is not None:
                out.setdefault(current, [])
        elif current and line.startswith("+"):
            out[current].append(line[1:])
    _, names = _git(root, "diff", "--name-only", base)
    for rel in names.splitlines():
        out.setdefault(rel, [])
    _, untracked = _git(root, "ls-files", "--others", "--exclude-standard")
    for rel in untracked.splitlines():
        out[rel] = c.read_text(root / rel).splitlines()
    return out


def _locked_at(root: Path, ref: str) -> bool:
    code, text = _git(root, "show", f"{ref}:VERSION.json")
    try:
        data = json.loads(text) if code == 0 else {}
    except json.JSONDecodeError:
        return False
    return isinstance(data, dict) and bool(data.get("learned_zone_locked"))


def check_diff(brain_root: Path | None = None, base: str | None = None) -> tuple[bool, list[str]]:
    from . import learn  # learn imports zone_of from here; import late to avoid a cycle

    root = Path(brain_root or c.BRAIN_ROOT)
    if _git(root, "rev-parse", "--git-dir")[0] != 0:
        return False, ["guard diff: not a git repository"]
    base = base or learn.default_base(root)
    added = _added_lines(root, base)
    zones: dict[str, int] = {"kernel": 0, "learned": 0, "inbox": 0, "state": 0}
    for rel in added:
        zones[zone_of(rel)] += 1
    lines = [f"changed files: {zones['kernel']} kernel, {zones['learned']} learned, {zones['inbox']} inbox, "
             f"{zones['state']} state (base {base})"]
    ok = True
    if _locked_at(root, base) and not locked(root):
        # Without this, unlocking turned every later check into a warning and the diff passed.
        ok = False
        lines.append(f"VERSION.json: this change unlocks the learned zone (it was locked at {base}); "
                     "only the owner unlocks it: restore learned_zone_locked to true")
    for rel, rows in sorted(added.items()):
        hits = c.find_secrets("\n".join(rows))
        if hits:
            ok = False
            lines.append(f"secret-like text added in {rel} ({', '.join(hits)})")
    ids_file = root / "evals" / "known_project_ids.txt"
    ids = [l.strip() for l in c.read_text(ids_file).splitlines() if l.strip() and not l.startswith("#")]
    for pid in ids:
        pat = re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(pid) + r"(?![A-Za-z0-9_-])", re.I)
        for rel, rows in sorted(added.items()):
            if rel != "evals/known_project_ids.txt" and any(pat.search(r) for r in rows):
                ok = False
                lines.append(f"project id {pid!r} appears in {rel}")
    if zones["kernel"]:
        lines.append("kernel files changed: merging needs the owner's override label")
    v_ok, v_lines = learn.verify(root, base)
    ok = ok and v_ok
    lines += v_lines
    return ok, lines


# ---------------------------------------------------------------- cli
def cmd_path(args) -> int:
    code, reason = check_path(args.path, args.mode)
    print(reason)
    return code


def cmd_diff(args) -> int:
    ok, lines = check_diff(base=args.base)
    print("\n".join(lines[:15]))
    return 0 if ok else 1


def register(sub) -> None:
    p = sub.add_parser("guard", help="zone rules for brain files")
    s = p.add_subparsers(dest="guard_cmd")
    k = s.add_parser("path", help="may this path be edited directly?")
    k.add_argument("path")
    k.add_argument("--mode", choices=("work", "learn", "bootstrap"), default="work")
    k.set_defaults(func=cmd_path)
    d = s.add_parser("diff", help="CI: zones, secrets, project ids, learned-zone replay; fails on an unlock")
    d.add_argument("--base", help="git ref (default origin/main, else HEAD)")
    d.set_defaults(func=cmd_diff)
