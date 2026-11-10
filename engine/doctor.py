"""Self-test: is this brain healthy on this machine?

Runs in a few seconds with nothing but Python. Used at the start of a repair
("Repair the brain") and in CI. With ``--project`` it looks at the attached
project instead: its contract files and its git setup, one line per problem,
each with the step that fixes it. It only reads.
"""
from __future__ import annotations

import importlib
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from . import common as c

def checks() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    out.append(("python", sys.version_info >= (3, 10), f"{sys.version_info.major}.{sys.version_info.minor}"))
    try:
        sqlite3.connect(":memory:").execute("create virtual table t using fts5(a)")
        out.append(("full-text search", True, f"sqlite {sqlite3.sqlite_version} with FTS5"))
    except sqlite3.Error as e:
        out.append(("full-text search", True, f"FTS5 unavailable ({e}); the pure-Python fallback will be used"))
    bad = []
    from . import MODULES
    for name in (m for m in MODULES if m != "doctor"):
        try:
            mod = importlib.import_module(f"engine.{name}")
            if not hasattr(mod, "register"):
                bad.append(f"{name} (no register)")
        except Exception as e:  # report any import failure, whatever its type
            bad.append(f"{name} ({type(e).__name__})")
    out.append(("engine modules", not bad, "all load" if not bad else "problems: " + ", ".join(bad)))
    ver = c.read_json(c.BRAIN_ROOT / "VERSION.json", None)
    out.append(("version file", isinstance(ver, dict) and ver.get("contract") == c.CONTRACT_VERSION, str((ver or {}).get("brain", "missing"))))
    models = c.read_json(c.BRAIN_ROOT / "memory" / "models.json", {}) or {}
    age = c.days_since(models.get("verified_on", ""))
    out.append(("model facts", bool(models.get("models")), f"verified {age} days ago" + (" — due for a re-check" if age > int(models.get("recheck_days", 90)) else "")))
    from . import items
    errs = items.check_files(items.brain_item_files())
    out.append(("memory items", not errs, "valid" if not errs else f"{len(errs)} problem(s); run: brain items check"))
    from . import budget
    berrs, info = budget.check()
    out.append(("always-loaded budget", not berrs, f"about {info['always_loaded_tokens']} tokens" if not berrs else "; ".join(berrs[:2])))
    from . import contract
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "sample"
        proj.mkdir()
        contract.init(proj, "Sample", "software")
        again = contract.init(proj, "Sample", "software")
        verrs = contract.validate(proj)
        out.append(("contract template", not verrs and not again, "installs, validates and is idempotent" if not verrs and not again else "; ".join(verrs[:2]) or "second init changed files"))
    return out


# ---------------------------------------------------------------- project preflight
MAX_PROJECT_LINES = 8
MACHINE_READ = (".brain/project.json", ".brain/STATE.md", ".brain/requirements.jsonl")


def _git(project: Path, *args: str) -> tuple[int, str]:
    """(exit code, output) of a read-only git command; 127 when git cannot run."""
    try:
        r = subprocess.run(["git", "-C", str(project), *args], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return 127, ""
    return r.returncode, r.stdout.strip()


def _contract_problems(project: Path, at: str) -> list[tuple[str, str]]:
    again = f"run `brain init {at}` again: it adds what is missing and overwrites nothing"
    stale = c.stale_brain(project)
    if stale:
        return [("this brain is older than the project's contract", "update the brain (attach its newest version); it writes nothing to this project until then")]
    out: list[tuple[str, str]] = []
    broken = c.manifest_problem(project)
    if broken:
        what, _, fix = broken.partition("; ")
        out.append((what, fix))
    else:
        from . import contract
        errs = contract.validate(project)
        for e in errs[:3]:
            if e.startswith("missing ") or "pointer block" in e:
                out.append((e, again))
            elif ": " in e and ("own id" in e or "brain migrate" in e):
                out.append(tuple(e.split(": ", 1)))  # the message already carries its fix
            else:
                out.append((e, "correct .brain/project.json, then run `brain validate`"))
        if len(errs) > 3:
            out.append((f"{len(errs) - 3} more contract problem(s)", "run `brain validate` for the list"))
    for rel in MACHINE_READ:
        try:
            text = (project / rel).read_bytes().decode("utf-8")
        except OSError:
            continue  # a missing file is validate's line
        except UnicodeDecodeError:
            out.append((f"{rel} holds a damaged byte and cannot be read as text", f"restore the last good copy: `git -C {at} checkout -- {rel}`"))
            continue
        if any(l.startswith(("<<<<<<< ", ">>>>>>> ")) for l in text.splitlines()):
            out.append((f"{rel} has merge conflict markers", "keep one side, delete the marker lines, then run `brain validate`"))
    return out


def _git_problems(project: Path, at: str) -> tuple[list[tuple[str, str]], str]:
    """(problems, a few words on the branch for the ok line)."""
    if _git(project, "--version")[0] == 127:
        return [("git is not installed on this machine", "nothing can be committed or pushed from here; use a session that has git")], ""
    if not (project / ".git").exists():
        return [(f"{project.name} is not a git repository, so nothing reaches a new chat",
                 f"attach the project's own repository, or run `git -C {at} init -b work` and add a remote")], ""
    out: list[tuple[str, str]] = []
    if _git(project, "var", "GIT_AUTHOR_IDENT")[0] != 0:
        out.append(("git has no author identity, so every commit fails",
                    "run `git config --global user.email <address>` and `git config --global user.name <name>`"))
    has_origin = "origin" in _git(project, "remote")[1].split()
    if not has_origin:
        out.append(("no remote 'origin', so nothing can be pushed and a new chat will not see this work",
                    f"attach the project's GitHub repository, or run `git -C {at} remote add origin <url>`"))
    code, branch = _git(project, "symbolic-ref", "-q", "--short", "HEAD")
    if code != 0:
        out.append(("HEAD is detached (not on a branch), so commits made now are easy to lose",
                    f"run `git -C {at} switch -c <new-branch>`, or `git -C {at} switch <branch>` to return to one"))
        return out, ""
    rel = c.load_manifest(project).get("release", {})
    rule, release_branch = rel.get("rule", "none"), rel.get("branch", "main")
    on_release = rule in ("main-on-green", "pr") and branch == release_branch
    if on_release:
        how = "`brain release` moves green work" if rule == "main-on-green" else "a pull request moves reviewed work"
        out.append((f"work is on the release branch ({branch}) under rule '{rule}', and unreleased work must not be pushed there",
                    f"work on another branch: `git -C {at} switch -c work`; {how} to {branch}"))
    upstream = ""
    if has_origin:
        code, upstream = _git(project, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        push = "run `brain release --push` once the gates are green" if on_release and rule == "main-on-green" else "run `brain checkpoint --push`"
        if code != 0:
            upstream = ""
            out.append((f"branch {branch} has never been pushed, so a new chat cannot see it", push))
        else:
            ahead = _git(project, "rev-list", "--count", f"{upstream}..HEAD")[1]
            if ahead not in ("", "0"):
                out.append((f"{ahead} commit(s) on {branch} are not pushed", push))
    return out, f"branch {branch}" + (f", pushed to {upstream}" if upstream else "")


def project_checks(project: Path) -> tuple[list[tuple[str, str]], str]:
    """Preflight of a managed project: ([(problem, fix)], one ok line). Reads
    only; every problem comes with the command or step that fixes it."""
    project = Path(project)
    at = os.path.relpath(project)
    at = str(project) if at.count("..") > 2 else at
    problems = _contract_problems(project, at)
    git_problems, branch = _git_problems(project, at)
    problems += git_problems
    ver = c.load_manifest(project).get("contract")
    return problems, f"ok   project {project.name}: contract v{ver} valid, git ready on {branch}"


def cmd_doctor(args) -> int:
    if getattr(args, "project", None) is not None:
        project, why = c.locate_project(args.project or None)
        if project is None:
            print(why)
            return 1
        problems, ok_line = project_checks(project)
        if len(problems) > MAX_PROJECT_LINES:
            rest = len(problems) - (MAX_PROJECT_LINES - 1)
            problems = problems[:MAX_PROJECT_LINES - 1] + [(f"{rest} more problem(s)", "fix the ones above, then run `brain doctor --project` again")]
        for what, fix in problems:
            print(f"FAIL {what}: {fix}")
        if not problems:
            print(ok_line)
        return 1 if problems else 0
    results = checks()
    for name, ok, detail in results:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    failed = [n for n, ok, _ in results if not ok]
    print("brain is healthy" if not failed else f"{len(failed)} check(s) failed")
    return 1 if failed else 0


def register(sub) -> None:
    p = sub.add_parser("doctor", help="self-test of the brain on this machine; with --project, a preflight of the project instead")
    p.add_argument("--project", nargs="?", const="", metavar="PATH",
                   help="check the attached project (or the one named): contract files and git setup, one line per problem with its fix")
    p.set_defaults(func=cmd_doctor)
