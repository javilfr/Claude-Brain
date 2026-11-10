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
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import common as c

# Inside the learned directories but hand-written.
KERNEL_FILES = ("memory/models.json", "memory/ml_config.json", "memory/radar_sources.json",
                "learning/PROMOTION_RULES.md")
STATE_DIRS = ("learning/radar/",)


def zone_of(relative_path: str) -> str:
    """"inbox", "state", "learned" or "kernel" for a path relative to the brain root."""
    rel = str(relative_path).replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    rel = rel.lstrip("/")
    if rel.startswith(c.INBOX_DIR):
        return "inbox"
    if rel.startswith(STATE_DIRS):
        return "state"
    if rel in KERNEL_FILES:
        return "kernel"
    if rel.startswith(c.LEARNED_ZONE):
        return "learned"
    return "kernel"


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
    d = s.add_parser("diff", help="CI: zones, secrets, project ids and learned-zone replay")
    d.add_argument("--base", help="git ref (default origin/main, else HEAD)")
    d.set_defaults(func=cmd_diff)
