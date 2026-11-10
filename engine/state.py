"""Project state: one checkpoint file, the owner's status page, and handover.

``.brain/STATE.md`` is the only place a project's position is recorded. An
earlier project kept status in five files that ended up contradicting each
other; here everything else (``STATUS.md``, the handover note) is generated
from this file.

Continuity between chats (decision D-17): a new chat is a fresh clone on a
new branch cut from the default branch, and the last chat's state sits on its
own remote branch. ``newer_checkpoints`` finds it, ``adopt_checkpoint`` takes
it by fast-forward only, and a checkpoint that may not go to the release
branch is pushed to a side branch so that it is on the remote all the same.
"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import tempfile
from pathlib import Path

from . import common as c

FIELDS = ("contract", "stage", "tier", "item", "last_done", "next", "blockers", "session", "updated")
STAGES = ("intake", "requirements", "research", "plan", "build", "verify", "deliver", "learn", "done")
LEASE_MINUTES = 120  # another session that checkpointed this recently is probably still working
LOG_KEEP = 30
NOTES_KEEP = 8       # older notes are in git history; the file must not grow without bound
FETCH_SECONDS = 6    # the one bounded fetch of branch heads (I-01)
PUSH_SECONDS = 120
SIDE_BRANCH = "brain/wip"   # where a checkpoint goes when the release branch may not take it

# Contract files that record the work but are not the work. An allow-list:
# anything else under .brain/ (the manifest, ext/, a script someone put there)
# changes what "green" means and must be committed by its author.
BOOK_FILES = frozenset({
    "STATUS.md", "NEEDS_YOU.md", ".brain/STATE.md", ".brain/PLAN.md", ".brain/DECISIONS.md", ".brain/REQUIREMENTS.md",
    ".brain/requirements.jsonl", ".brain/CHECKLIST.md", ".brain/HANDOVER.md", ".brain/.gitignore"})
BOOK_DIRS = (".brain/log/", ".brain/memory/")
BOOK_SUFFIXES = (".json", ".jsonl", ".md", ".log", ".txt")   # what the engine writes in those folders
BOOK_NAMES = ("salt", ".gitkeep")
RECORD_DIRS = ("learning/inbox/", "learning/radar/")   # what a working session may commit in the brain


class StateError(ValueError):
    """A checkpoint that must not be written; the message is the line to print."""


# ---------------------------------------------------------------- git
def _run(path: Path, *args: str, timeout: int = 15) -> tuple[int, str, str]:
    """(exit code, stdout, stderr) of a git command. Never raises: a timeout
    is code 124, a missing git 127. No prompt can hang it."""
    try:
        r = subprocess.run(["git", "-C", str(path), *args], capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"no answer in {timeout} s"
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)


def git(path: Path, *args: str) -> str:
    """Output of a read-only git command. Only trailing whitespace is removed:
    porcelain status lines begin with a significant space."""
    return _run(path, *args)[1].rstrip()


def is_repo(path: Path) -> bool:
    return (Path(path) / ".git").exists()


def current_branch(path: Path) -> str:
    return git(path, "rev-parse", "--abbrev-ref", "HEAD")


def changed_files(path: Path) -> list[str]:
    """Every path with an uncommitted change: untracked files one by one,
    both sides of a rename, names as they are on disk (no quoting)."""
    base = ("-c", "core.quotepath=off", "status", "--porcelain", "--untracked-files=all", "-z")
    code, out, _ = _run(path, *base, "--no-renames")
    if code != 0:   # an older git without --no-renames for status
        code, out, _ = _run(path, *base)
    return [e[3:] for e in out.split("\0") if len(e) > 3] if code == 0 else []


def unpushed_count(path: Path) -> int:
    """Commits on HEAD that no branch on the remote holds."""
    n = git(path, "rev-list", "--count", "HEAD", "--not", "--remotes=origin")
    return int(n) if n.isdigit() else 0


def remote_is_local(repo: Path) -> bool:
    """True when origin is a folder on this machine (tests, CI, a local mirror)."""
    url = git(repo, "config", "--get", "remote.origin.url")
    if not url:
        return False
    return url.startswith("file://") or ("://" not in url and ":" not in url.split("/", 1)[0])


def push_off() -> str:
    """The switch that forbids pushing to a remote on the network, or ""."""
    return next((k for k in ("BRAIN_NO_PUSH", "BRAIN_NO_NETWORK") if os.environ.get(k)), "")


def may_push(repo: Path) -> str:
    """Why this repository must not push now, or "". A local remote is always allowed."""
    if remote_is_local(repo):
        return ""
    flag = push_off()
    return f"pushing is switched off here ({flag} is set)" if flag else ""


def _push_problem(code: int, err: str, branch: str) -> str:
    """One line for a failed push: the fix where it is known, never the address."""
    low = err.lower()
    if code == 124:
        return f"no answer from the remote in {PUSH_SECONDS} s; run the same command again"
    if "rejected" in low or "fetch first" in low or "non-fast-forward" in low:
        return f"the remote has commits this branch lacks: git pull --rebase origin {branch}, then run the same command again"
    lines = [l.strip() for l in err.splitlines() if l.strip() and not l.startswith(("To ", "hint:"))]
    return c.clip(" ".join(lines) or "git push failed", 140)


def _commit_problem(err: str) -> str:
    low = err.lower()
    if any(s in low for s in ("identity unknown", "no email was given", "empty ident", "auto-detect email", "tell me who you are")):
        return "git has no author identity here: git config user.email <address> && git config user.name <name>, then run the same command again"
    return "could not commit (" + c.clip(err, 100) + ")"


def _staged_secret(repo: Path, paths: list[str]) -> tuple[str, str] | None:
    """(file, kind) of the first staged added line that looks like a
    credential, else None. The value is never returned."""
    _code, out, _ = _run(repo, "diff", "--cached", "--unified=0", "--no-renames", "--no-color", "--", *paths)
    cur = ""
    for line in out.splitlines():
        if line.startswith("+++ "):
            cur = line[6:] if line.startswith("+++ b/") else line[4:]
        elif line.startswith("+") and c.find_secrets(line[1:]):
            return cur, next((label for label, pat in c.SECRET_RULES if pat.search(line)), "credential")
    return None


# ---------------------------------------------------------------- the state file
def state_path(project: Path) -> Path:
    return Path(project) / ".brain" / "STATE.md"


def parse_state(text: str) -> dict:
    """Fields, notes and log lines of a STATE.md text. Empty text gives defaults."""
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


def read_state(project: Path) -> dict:
    """Parse STATE.md. A missing file gives defaults; a damaged byte costs one
    character, not the file (``state_problem`` says when something is wrong)."""
    try:
        text = state_path(project).read_bytes().decode("utf-8", "replace")
    except OSError:
        text = ""
    return parse_state(text)


def state_problem(project: Path) -> str:
    """One line when STATE.md cannot be trusted, else "". A damaged state must
    be said out loud: read as an empty one, the next checkpoint would replace
    stage, item, notes and log with blanks."""
    restore = "restore it (git checkout HEAD -- .brain/STATE.md)"
    try:
        raw = state_path(project).read_bytes()
    except FileNotFoundError:
        return f".brain/STATE.md is missing: {restore}, or checkpoint to start a new one"
    except OSError as e:
        return f".brain/STATE.md cannot be read ({type(e).__name__}): {restore}"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return f".brain/STATE.md has a damaged byte: {restore}, or repair the line by hand"
    if re.search(r"(?m)^(<<<<<<<|>>>>>>>)( |$)", text):
        return f".brain/STATE.md holds merge conflict markers: keep one side by hand, or {restore}"
    if not re.search(r"(?m)^updated:\s*\S", text):
        return f".brain/STATE.md is empty or cut short (no 'updated:' line): {restore}, or delete it to start a new one"
    return ""


def write_state(project: Path, st: dict) -> None:
    head = "\n".join(f"{k}: {st.get(k, '')}".rstrip() for k in FIELDS)
    log = "\n".join(f"- {l}" for l in st.get("log", [])[-LOG_KEEP:])
    text = (
        "# State\n\nThe single checkpoint for this project. Written by `brain checkpoint`; read by `brain boot`.\n\n"
        f"{head}\n\n## Notes\n\n{st.get('notes', '').strip()}\n\n## Log\n\n{log}\n"
    )
    c.write_text(state_path(project), text)


@contextlib.contextmanager
def _locked(project: Path):
    """Hold an exclusive lock on the project's .brain folder (no lock file), so
    two checkpoints at once cannot lose each other's note. Without ``fcntl``
    or the folder, it does nothing."""
    try:
        import fcntl
        fd = os.open(str(Path(project) / ".brain"), os.O_RDONLY)
    except (ImportError, OSError):
        yield
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def lease_warning(st: dict) -> str:
    """A line of warning when a different session checkpointed recently. A
    session that handed over has released the lease (session ``none``)."""
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


def _same_item(a: str | None, b: str | None) -> bool:
    """Equal, or one is the bare id that starts the other ("T-2" and "T-2 search page")."""
    a, b = " ".join((a or "").split()).lower(), " ".join((b or "").split()).lower()
    if not a or not b or "none" in (a, b):
        return False
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    return " " not in short and long.startswith(short) and long[len(short)] in " :·"


_ID = r"[A-Za-z]{1,6}-?\d{1,4}[a-z]?"
_PLAN_LINE = re.compile(rf"^\s*(?:[-*+]|\d+[.)])?\s*(?:\[[ xX]\]\s*)?\**\s*({_ID})\**\s*[·:—–|-]\s*\**\s*(.+?)\s*$")


def plan_titles(project: Path) -> dict[str, str]:
    """``id -> "id · title"`` for the lines of ``.brain/PLAN.md`` that start
    with an item id, so a status never shows a bare "P2"."""
    out: dict[str, str] = {}
    for line in c.read_text(Path(project) / ".brain" / "PLAN.md").splitlines():
        m = _PLAN_LINE.match(line.lstrip("| "))
        if not m:
            continue
        title = re.split(r"\*\*|\s\|", m.group(2))[0].strip(" *|·:—–-")
        if title:
            out.setdefault(m.group(1).lower(), f"{m.group(1)} · {c.clip(title, 60)}")
    return out


def checkpoint(project: Path, item: str | None = None, done: str | None = None, nxt: list[str] | None = None,
               stage: str | None = None, tier: int | None = None, note: str | None = None,
               blockers: str | None = None, clear_notes: bool = False) -> dict:
    """Record the position. Raises ``StateError`` (nothing written) when a text
    holds something shaped like a credential, or when the existing file is
    damaged: a checkpoint must never replace a state it could not read."""
    for text in (item, done, note, blockers, *(nxt or [])):
        problem = c.secret_problem(text or "")
        if problem:
            raise StateError(problem)
    with _locked(project):
        if state_path(project).exists():
            problem = state_problem(project)
            if problem:
                raise StateError("checkpoint refused, nothing written: " + problem)
        st = read_state(project)
        st["contract"] = st["contract"] or str(c.CONTRACT_VERSION)
        if any(x and re.fullmatch(_ID, x.strip()) for x in (item, done, *(nxt or []))):
            titles = plan_titles(project)   # a bare id is stored with what it is

            def named(x: str | None) -> str | None:
                return titles.get(x.strip().lower(), x) if x else x
            item, done, nxt = named(item), named(done), ([named(n) for n in nxt] if nxt is not None else None)
        if done:
            st["last_done"] = c.clip(done, 160)
            st["log"].append(f"{c.today()} done: {c.clip(done, 120)}")
            if not item and _same_item(st.get("item"), done):
                st["item"] = "none"
        if item is not None:
            st["item"] = c.clip(item, 160)
        if nxt is not None:
            st["next"] = "; ".join(c.clip(n, 100).replace(";", ",") for n in nxt[:3] if n.strip())
        elif done or item:
            # What was finished or is now in progress is no longer "next".
            st["next"] = "; ".join(n for n in st["next_list"] if not _same_item(n, done) and not _same_item(n, item))
        if stage:
            # The stage lives here only. The manifest is configuration (commands,
            # gates, release rule): a checkpoint must not edit it, or every
            # checkpoint would make a green gate look stale.
            st["stage"] = stage
        if tier is not None:
            st["tier"] = str(tier)
        if blockers is not None:
            st["blockers"] = c.clip(blockers, 160) or "none"
        if clear_notes:
            st["notes"] = ""
        if note:
            notes = [l for l in st["notes"].splitlines() if l.strip()]
            line = f"- {c.clip(note, 300)}"
            if not notes or notes[-1] != line:
                notes.append(line)
            st["notes"] = "\n".join(notes[-NOTES_KEEP:])
        st["session"] = c.session_id()
        st["updated"] = c.now_iso()
        write_state(project, st)
    st["next_list"] = [x.strip() for x in st["next"].split(";") if x.strip()]
    return st


def notes_tail(notes: str, limit: int) -> str:
    """The newest notes that fit in ``limit`` characters, newest first, with a
    count of the older ones left out. The newest note is what a resume needs,
    so it comes first and is never the part a later clip removes."""
    items = [" ".join(l.split()) for l in notes.splitlines() if l.strip()]
    if not items:
        return ""
    room = max(40, limit - 24)   # the label and the count of older notes
    kept: list[str] = []
    used = 0
    for n in reversed(items):
        if kept and used + len(n) + 1 > room:
            break
        kept.append(c.clip(n, room))
        used += len(kept[-1]) + 1
    older = len(items) - len(kept)
    return ("newest first: " if len(kept) > 1 else "") + " ".join(kept) + (f" (+{older} older)" if older else "")


# ---------------------------------------------------------------- bookkeeping and pushes
def is_bookkeeping(path: str) -> bool:
    """Contract files that record the work but are not the work (an allow-list).
    The manifest, the project's own tools and anything else under ``.brain/``
    are work: changing a gate command, a project tool or a script changes what
    "green" means, so it must not ride along as bookkeeping. Inside the log
    and memory folders only the record file types count, so a program moved
    there is still a program."""
    path = path.strip().strip('"')
    if path in BOOK_FILES:
        return True
    # "old -> new" is a status line for a rename: one side may be work.
    if " -> " in path or not path.startswith(BOOK_DIRS) or ".." in path.split("/"):
        return False
    name = path.rsplit("/", 1)[-1]
    return not name or name in BOOK_NAMES or name.endswith(BOOK_SUFFIXES)   # "" is the folder itself


def _release(project: Path) -> dict:
    rel = c.load_manifest(project).get("release")
    return rel if isinstance(rel, dict) else {}


def release_branch_block(project: Path, branch: str) -> str:
    """Why a plain push of this branch is not allowed, or "".

    On the branch a project releases from, work reaches the remote only
    through `brain release` (rule main-on-green, on a green gate) or through a
    pull request (rule pr). A checkpoint may still push there when everything
    not yet on the remote is bookkeeping. Renames are not followed: a file
    moved into a bookkeeping folder is still a deleted work file."""
    rel = _release(project)
    rule = rel.get("rule")
    if rule not in ("main-on-green", "pr") or branch != (rel.get("branch") or "main"):
        return ""
    how = ("`brain release` pushes there on a green gate" if rule == "main-on-green"
           else "work reaches it through a pull request (git switch -c <name>, push that branch, open one)")
    if not git(project, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"):
        return f"{branch} is the release branch and has never been released; {how}"
    ahead = [l for l in git(project, "diff", "--name-only", "--no-renames", f"origin/{branch}", "HEAD").splitlines() if l.strip()]
    work = [f for f in ahead if not is_bookkeeping(f)]
    if work:
        return f"{branch} is the release branch and {len(work)} changed file(s) are not released yet (e.g. {work[0]}); {how}"
    return ""


class PushResult(str):
    """The line to print, plus what happened. ``status``: ``pushed`` (the
    current branch is on the remote), ``side`` (the same commit is on the
    remote under another branch name), ``local`` (saved here only) or
    ``failed``. ``branch`` is the remote branch that holds the state, or ""."""
    status = "local"
    branch = ""

    def __new__(cls, text: str, status: str = "local", branch: str = ""):
        self = super().__new__(cls, text)
        self.status, self.branch = status, branch
        return self

    @property
    def on_remote(self) -> bool:
        return self.status in ("pushed", "side")


def write_checklist(project: Path) -> list[str]:
    """Open work as a short checklist file. An unattended run keeps going while
    this has open items and no blocker, so a progress report is never mistaken
    for completion."""
    st = read_state(project)
    items = []
    if st.get("item") and st["item"] != "none":
        items.append(f"[ ] in progress: {st['item']}")
    items += [f"[ ] next: {n}" for n in st["next_list"]]
    for r in c.read_jsonl(Path(project) / ".brain" / "requirements.jsonl"):
        if r.get("status", "open") == "open":
            items.append(f"[ ] {r.get('id')}: {c.clip(r.get('quote', ''), 90)}")
    text = "# Checklist\n\nGenerated by `brain checkpoint`. Work continues while any line is open and nothing blocks it.\n\n" + ("\n".join(f"- {i}" for i in items) if items else "- nothing open") + "\n"
    _write_if_changed(Path(project) / ".brain" / "CHECKLIST.md", text)
    return items


def _write_if_changed(path: Path, text: str) -> bool:
    """Write a generated file only when its content differs, so asking for a
    status never dirties the tree."""
    if c.read_text(path, None) == text:
        return False
    c.write_text(path, text)
    return True


def _others_note(project: Path, others: list[str]) -> str:
    if not others:
        return ""
    note = f"; {len(others)} other uncommitted change(s) left for their author ({', '.join(others[:3])}{', …' if len(others) > 3 else ''})"
    if ".brain/project.json" in others and _run(project, "cat-file", "-e", "HEAD:.brain/project.json")[0] != 0:
        note += " — the contract itself is not committed, so a new chat cannot resume: git add -A && git commit -m 'chore(brain): contract', then checkpoint --push again"
    return note


def _push_side(project: Path) -> tuple[str, str]:
    """Push HEAD to the side branch (plain push; a session-named branch when
    the shared one cannot fast-forward). Returns (branch, "") or ("", why)."""
    sid = re.sub(r"[^A-Za-z0-9]", "", c.session_id())[:8] or "local"
    why = ""
    for name in (SIDE_BRANCH, f"{SIDE_BRANCH}-{sid}"):
        code, _, err = _run(project, "push", "-q", "origin", f"HEAD:refs/heads/{name}", timeout=PUSH_SECONDS)
        if code == 0:
            _run(project, "update-ref", f"refs/remotes/origin/{name}", "HEAD")   # true by the push just made
            return name, ""
        why = _push_problem(code, err, name)
        if code == 124:
            break
    return "", why


def push_bookkeeping(project: Path) -> PushResult:
    """Commit the bookkeeping files (explicit paths, never the folder) and push,
    so the next cloud session can see them: unpushed work is invisible to a new
    container. Real work is committed by its author. Where the release branch
    may not take the push, the same commit goes to a side branch instead. The
    result says where the state is; ``.status`` says whether the remote has it."""
    project = Path(project)
    if not is_repo(project):
        return PushResult("NOT PUSHED: the project is not a git repository (git init, add a remote), so a new chat cannot see this checkpoint")
    changed = changed_files(project)
    books = [f for f in changed if is_bookkeeping(f)]
    others = [f for f in changed if not is_bookkeeping(f)]
    if books:
        code, out, err = _run(project, "add", "-A", "--", *books)
        hit = _staged_secret(project, books) if code == 0 else None
        if hit:
            _run(project, "reset", "-q", "--", *books)
            return PushResult(f"NOT PUSHED, nothing committed: {hit[0]} holds what looks like a {hit[1]} (never shown); "
                              "remove it from the file, then run the same command again", "failed")
        if code == 0:
            code, out, err = _run(project, "commit", "-q", "-m", "chore(brain): checkpoint", "--", *books)
        if code != 0:
            return PushResult("NOT PUSHED: " + _commit_problem(err or out), "failed")
    saved = "checkpoint committed; " if books else ""
    if not git(project, "remote"):
        return PushResult(saved + "NOT PUSHED: the project has no remote (git remote add origin <address>)")
    branch = current_branch(project)
    if branch in ("", "HEAD"):
        return PushResult(saved + "NOT PUSHED: not on a branch (git switch -c <name>, then checkpoint --push again)")
    off = may_push(project)
    if off:
        return PushResult(saved + "NOT PUSHED: " + off)
    note = _others_note(project, others)
    blocked = release_branch_block(project, branch)
    if blocked:
        side, why = _push_side(project)
        if not side:
            return PushResult(f"{saved}PUSH FAILED: {why} ({branch} itself was not tried: {c.clip(blocked, 90)})", "failed")
        return PushResult(f"checkpoint saved to origin/{side}; not pushed to {branch}: {blocked}{note}", "side", side)
    code, _, err = _run(project, "push", "-q", "-u", "origin", branch, timeout=PUSH_SECONDS)
    if code != 0:
        return PushResult(saved + "PUSH FAILED: " + _push_problem(code, err, branch), "failed")
    return PushResult(f"checkpoint pushed to {branch}{note}", "pushed", branch)


# ---------------------------------------------------------------- the brain's own records
def _session_note(root: Path) -> Path | None:
    """A small file inside the brain checkout's git folder: never committed,
    gone with the container, private to this checkout."""
    d = git(root, "rev-parse", "--absolute-git-dir")
    return Path(d) / "brain-session.json" if d else None


def remember_repaired(sid: str, brain_root: Path | None = None) -> None:
    """Note that this session wrote the records of an earlier, unclosed session
    (boot does that), so ``push_brain_records`` treats that file as its own."""
    path = _session_note(Path(brain_root or c.BRAIN_ROOT))
    if not path or not sid:
        return
    data = c.read_json(path, {})
    if not isinstance(data, dict) or data.get("session") != c.session_id():
        data = {"session": c.session_id(), "repaired": []}
    if sid not in data.setdefault("repaired", []):
        data["repaired"].append(sid)
        c.write_json(path, data)


def _own_sessions(root: Path) -> set[str]:
    path = _session_note(root)
    data = c.read_json(path, {}) if path else {}
    extra = data.get("repaired", []) if isinstance(data, dict) and data.get("session") == c.session_id() else []
    return {c.session_id(), *[str(x) for x in extra]}


def _own_record(root: Path, rel: str, sids: set[str]) -> bool:
    """True for the radar's state and leads, and for an inbox file in which no
    record names another session. Anything else in the inbox is left alone."""
    if rel.startswith("learning/radar/"):
        return True
    path = root / rel
    if not rel.endswith(".jsonl") or not path.is_file():
        return False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}-radar\.jsonl", path.name):
        return True
    rows = c.read_jsonl(path)
    return bool(rows) and all(str(r.get("session") or "") in sids | {""} for r in rows)


def _unpushed_files(root: Path) -> list[str]:
    """Files changed by commits that no branch on the remote holds."""
    out = git(root, "log", "--format=", "--name-only", "--no-renames", "HEAD", "--not", "--remotes=origin")
    return sorted({l.strip() for l in out.splitlines() if l.strip()})


def _brain_block(root: Path) -> tuple[str, str]:
    """(kind, reason) why the brain must not push now, or ("", ""). Kinds:
    ``off`` and ``scratch`` (commit nothing either), ``others`` (commit the
    records, leave the push to a person)."""
    if remote_is_local(root):
        return "", ""
    flag = push_off()
    if flag:
        return "off", f"{flag} is set"
    here = root.resolve()
    if here.is_relative_to(Path(tempfile.gettempdir()).resolve()) or "scratchpad" in here.parts:
        return "scratch", "this checkout of the brain is a scratch copy (under a temp folder) and never pushes to the real remote"
    others = [f for f in _unpushed_files(root) if not f.startswith(RECORD_DIRS)]
    if others:
        return "others", (f"{len(others)} file(s) outside the inbox are in unpushed commits here (e.g. {others[0]}); "
                          "push the branch yourself once they are reviewed")
    return "", ""


def brain_push_block(brain_root: Path | None = None) -> str:
    """Why ``push_brain_records`` would not push from this checkout, or ""."""
    return _brain_block(Path(brain_root or c.BRAIN_ROOT))[1]


def push_brain_records(brain_root: Path | None = None) -> str:
    """Commit and push what this session recorded in the brain: its own inbox
    file(s) and the radar's state, by explicit path. Nothing else that sits in
    the inbox, nothing else in the brain. It pushes to a local remote always;
    to a remote on the network only from a real checkout, with pushing not
    switched off, and when the push would carry no other local commit. The
    line returned says what went where ("" when there was nothing to do)."""
    root = Path(brain_root or c.BRAIN_ROOT)
    if not is_repo(root):
        return ""
    sids = _own_sessions(root)
    changed = [f for f in changed_files(root) if f.startswith(RECORD_DIRS)]
    own = [f for f in changed if _own_record(root, f, sids)]
    foreign = [f for f in changed if f not in own]
    left = (f"; left alone: {', '.join(Path(f).name for f in foreign[:3])}{', …' if len(foreign) > 3 else ''} "
            "(not written by this session)") if foreign else ""
    has_remote = bool(git(root, "remote"))
    kind, reason = _brain_block(root) if has_remote else ("", "")
    earlier = has_remote and not own and any(f.startswith(RECORD_DIRS) for f in _unpushed_files(root))
    if not own and not earlier:
        return ("brain records: nothing of this session to commit" + left) if foreign else ""
    if kind in ("off", "scratch"):
        return f"brain records left uncommitted, not pushed: {reason}{left}"
    if own:
        code, out, err = _run(root, "add", "--", *own)
        hit = _staged_secret(root, own) if code == 0 else None
        if hit:
            _run(root, "reset", "-q", "--", *own)
            return (f"brain records not committed: {Path(hit[0]).name} holds what looks like a {hit[1]} (never shown); "
                    "remove that line, then run the same command again")
        if code == 0:
            code, out, err = _run(root, "commit", "-q", "-m", "learn: session records", "--", *own)
        if code != 0:
            _run(root, "reset", "-q", "--", *own)
            return "brain records not committed: " + _commit_problem(err or out)
    if not has_remote:
        return "brain records committed; no remote to push to" + left
    if kind == "others":
        return f"brain records committed; not pushed: {reason}{left}"
    branch = current_branch(root)
    if branch in ("", "HEAD"):
        return "brain records committed; not pushed: the brain is not on a branch (git switch -c <name>)" + left
    code, _, err = _run(root, "push", "-q", "-u", "origin", branch, timeout=PUSH_SECONDS)
    if code != 0:
        return "brain records committed; PUSH FAILED: " + _push_problem(code, err, branch) + left
    what = f"{len(own)} file(s)" if own else "committed earlier"
    return f"brain records pushed to {branch} ({what})" + left


# ---------------------------------------------------------------- continuity between chats
def _fetch_heads(repo: Path) -> None:
    """The one bounded fetch of the remote's branch heads. Skipped when
    ``BRAIN_NO_NETWORK`` is set; any failure is silence. No --depth: adopting
    by fast-forward needs the ancestry."""
    if not os.environ.get("BRAIN_NO_NETWORK"):
        _run(repo, "fetch", "-q", "--no-tags", "origin", "+refs/heads/*:refs/remotes/origin/*", timeout=FETCH_SECONDS)


def _remote_branches(repo: Path, limit: int) -> list[str]:
    """Names of the remote's branches as this checkout knows them, newest commit first."""
    refs = git(repo, "for-each-ref", "--sort=-committerdate", f"--count={limit + 1}", "--format=%(refname)",
               "refs/remotes/origin").splitlines()
    return [n for n in (r.removeprefix("refs/remotes/origin/") for r in refs) if n and n != "HEAD"]


def newer_checkpoints(project: Path, limit: int = 12) -> list[dict]:
    """Remote branches whose ``.brain/STATE.md`` is newer than this checkout's,
    newest first: ``{ref, branch, updated, item, last_done, stage}``.

    A new chat starts on a new branch cut from the default branch while the
    last chat pushed its state to its own, so the newest state is usually not
    in the checkout. This makes at most one bounded fetch of the remote's
    branch heads (skipped when ``BRAIN_NO_NETWORK`` is set or there is no
    remote; any failure is silence) and then reads only local objects."""
    project = Path(project)
    if not is_repo(project) or not git(project, "remote"):
        return []
    _fetch_heads(project)
    mine = read_state(project).get("updated", "")
    out = []
    for name in _remote_branches(project, limit):
        code, text, _ = _run(project, "show", f"refs/remotes/origin/{name}:.brain/STATE.md")
        if code != 0 or not text:
            continue
        st = parse_state(text)
        if st["updated"] and st["updated"] > mine:
            out.append({"ref": f"origin/{name}", "branch": name, "updated": st["updated"], "item": st["item"],
                        "last_done": st["last_done"], "stage": st["stage"]})
    out.sort(key=lambda d: d["updated"], reverse=True)
    return out


def ahead_branches(repo: Path, limit: int = 12) -> list[dict]:
    """Remote branches that hold everything in this checkout plus more commits
    (so taking one is a fast-forward), newest first: ``{ref, branch, commits}``.
    This is how a chat with only the brain attached finds the last chat's
    work: the brain has no state file, its commits are its position. Same one
    bounded fetch as ``newer_checkpoints``."""
    repo = Path(repo)
    if not is_repo(repo) or not git(repo, "remote"):
        return []
    _fetch_heads(repo)
    out = []
    for name in _remote_branches(repo, limit):
        ref = f"refs/remotes/origin/{name}"
        n = git(repo, "rev-list", "--count", f"HEAD..{ref}")
        if n.isdigit() and int(n) > 0 and _run(repo, "merge-base", "--is-ancestor", "HEAD", ref)[0] == 0:
            out.append({"ref": f"origin/{name}", "branch": name, "commits": int(n)})
    return out


def _adopt(repo: Path, branch: str | None, found: list[str], nothing: str, conflict_hint: str = "") -> tuple[bool, str]:
    """Fast-forward ``repo`` to ``branch`` on the remote, or to the first of
    ``found``. Never merges, never forces; a refusal says the next step."""
    if branch:
        name = branch.removeprefix("origin/")
        if not git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{name}"):
            have = [r.removeprefix("origin/") for r in found][:4]
            return False, (f"no branch '{name}' on the remote" + (f" (newer work is on: {', '.join(have)})" if have else "")
                           + "; run `brain resume --adopt` with no name to take the newest")
        ref = f"origin/{name}"
    elif not found:
        return True, nothing
    else:
        ref = found[0]
    has_head = bool(git(repo, "rev-parse", "--verify", "--quiet", "HEAD"))
    if has_head and _run(repo, "merge-base", "--is-ancestor", "HEAD", ref)[0] != 0:
        mine = git(repo, "rev-list", "--count", f"{ref}..HEAD") or "some"
        return False, (f"cannot fast-forward to {ref}: this branch has {mine} commit(s) that branch lacks. "
                       f"Next: git merge {ref}{conflict_hint}, then `brain resume`")
    code, out, err = _run(repo, "merge", "--ff-only", "-q", ref, timeout=60)
    if code != 0:
        why = next((l.strip() for l in (err or out).splitlines() if l.strip()), "git refused")
        return False, (f"cannot fast-forward to {ref}: {c.clip(why, 110)}. "
                       "Next: commit or discard the local changes in the way (git status), then `brain resume --adopt` again")
    return True, f"adopted {ref}: fast-forwarded to {git(repo, 'rev-parse', '--short', 'HEAD')}"


def adopt_checkpoint(project: Path, branch: str | None = None) -> tuple[bool, str]:
    """Bring this checkout up to the newest checkpoint on the remote (or to
    ``branch``) by fast-forward only, so nothing here can be lost. Returns
    (ok, one line); a refusal says the next step."""
    project = Path(project)
    return _adopt(project, branch, [f["ref"] for f in newer_checkpoints(project)],
                  "nothing newer on the remote: this checkout holds the latest checkpoint",
                  " (in a conflict on .brain/STATE.md keep theirs)")


def adopt_brain(brain_root: Path | None = None, branch: str | None = None) -> tuple[bool, str]:
    """The same for the brain itself, in a chat with no project attached."""
    root = Path(brain_root or c.BRAIN_ROOT)
    return _adopt(root, branch, [a["ref"] for a in ahead_branches(root)],
                  "nothing ahead on the remote: this checkout holds the brain's latest work")


# ---------------------------------------------------------------- resume
def last_gate(project: Path) -> str:
    rows = c.read_jsonl(Path(project) / ".brain" / "log" / "gates.jsonl")
    if not rows:
        return "no gate has run"
    r = rows[-1]
    if r.get("exit") is None:
        return f"gate {r.get('gate')}: {r.get('note') or 'not run'}"
    where = f" on {str(r.get('commit'))[:7]}" if r.get("commit") else ""
    return f"gate {r.get('gate')} exit {r.get('exit')} at {str(r.get('at', ''))[:16]}{where}"


def resume_lines(project: Path) -> list[str]:
    """What a session needs to carry on after its context was compacted: at
    most twelve lines of at most 240 characters, all read from disk."""
    project = Path(project)
    st = read_state(project)
    head = f"project {c.clip(project.name, 40)}"
    flight: list[str] = []
    if is_repo(project):
        ahead = unpushed_count(project)
        head += f" · branch {current_branch(project) or '?'}" + (f" · {ahead} commit(s) not pushed" if ahead else "")
        flight = [f for f in changed_files(project) if not is_bookkeeping(f)]
    lines = [head + f" · stage {st.get('stage') or '?'} · size {st.get('tier') or '?'}"]
    problem = state_problem(project)
    if problem:
        lines.append("PROBLEM: " + problem)
    lines.append(f"item: {c.clip(st.get('item') or 'none', 120)} · last done: {c.clip(st.get('last_done') or 'none', 100)}")
    if st["next_list"]:
        lines.append("next: " + "; ".join(st["next_list"]))
    if st.get("blockers") and st["blockers"] != "none":
        lines.append("blockers: " + st["blockers"])
    if st.get("notes"):
        lines.append("notes: " + notes_tail(st["notes"], 220))
    marks = owner_marks(project)
    if marks:
        lines.append(marks)
    tail = []
    if flight:
        tail.append("uncommitted work: " + ", ".join(flight[:5]) + (f" (+{len(flight) - 5})" if len(flight) > 5 else ""))
    tail.append(last_gate(project))
    open_reqs = [r for r in c.read_jsonl(project / ".brain" / "requirements.jsonl") if r.get("status", "open") == "open"]
    room = 12 - len(lines) - len(tail)
    show = min(4, len(open_reqs), room if len(open_reqs) <= room else room - 1)
    for r in open_reqs[:max(show, 0)]:
        lines.append(f"open {r.get('id')}: {c.clip(r.get('quote', ''), 80)}" + (f" → {c.clip(r['passes_when'], 60)}" if r.get("passes_when") else ""))
    if len(open_reqs) > max(show, 0):
        lines.append(f"… {len(open_reqs) - max(show, 0)} more open requirement(s): brain req list --open")
    return [c.clip(l, 240) for l in (lines + tail)[:12]]


# ---------------------------------------------------------------- owner files
_MARK = r"^\s*(?:[-*>|]\s*)*\**\s*"
RESOLVED_RE = re.compile(_MARK + r"(RESOLVED|RESUELTO|RESUELTA|HECHO|LISTO)\b", re.I)
APPLIED_RE = re.compile(_MARK + r"(APPLIED|APLICAD[AO])\b", re.I)
APPLIED_INLINE = re.compile(r"\((?:applied|aplicad[ao])\b[^)]*\)|\b(?:APPLIED|APLICAD[AO])\b")
OVERTURNED_START = re.compile(_MARK + r"(OVERTURNED|REVERTIDA|ANULADA)\b[\s:]*(D-?\d+|\d+)?", re.I)
OVERTURNED_ANY = re.compile(r"\b(?:OVERTURNED|REVERTIDA|ANULADA)\b")   # inside a line: upper case only
_ROW_ID = re.compile(r"^\|\s*((?:[A-Za-z]{1,3}-?)?\d+)\s*\|")


def _needs_items(project: Path) -> list[dict]:
    """NEEDS_YOU items: ``{title, resolved, applied}``. An item is resolved by
    a line that starts with RESOLVED (or RESUELTO, RESUELTA, HECHO, LISTO):
    the word inside a sentence does not count."""
    items: list[dict] = []
    cur = None
    for line in c.read_text(Path(project) / "NEEDS_YOU.md").splitlines():
        if line.startswith("## "):
            cur = {"title": line[3:].strip(), "resolved": False, "applied": False}
            items.append(cur)
        elif cur is not None:
            if RESOLVED_RE.match(line):
                cur["resolved"] = True
                cur["applied"] = cur["applied"] or bool(APPLIED_INLINE.search(line))
            elif cur["resolved"] and APPLIED_RE.match(line):
                cur["applied"] = True
    return items


def open_needs(project: Path) -> list[str]:
    """Titles of NEEDS_YOU items that have no RESOLVED line under them."""
    return [i["title"] for i in _needs_items(project) if not i["resolved"]]


def overturned(project: Path) -> list[str]:
    """Ids of decisions the owner reversed in ``.brain/DECISIONS.md`` that
    carry no applied mark (``APPLIED <date>`` on the next line, or
    ``(applied <date>)`` on the same one). The mark is OVERTURNED, REVERTIDA
    or ANULADA at the start of a line, or in capitals anywhere on it; the
    word inside `code` (the file's own instructions) does not count."""
    lines = c.read_text(Path(project) / ".brain" / "DECISIONS.md").splitlines()
    out: list[str] = []
    last_row = ""
    for i, raw in enumerate(lines):
        line = re.sub(r"`[^`]*`", "", raw)
        row = _ROW_ID.match(line)
        if row:
            last_row = row.group(1)
        start = OVERTURNED_START.match(line)
        if not start and not OVERTURNED_ANY.search(line):
            continue
        after = next((l for l in lines[i + 1:] if l.strip()), "")
        if APPLIED_INLINE.search(line) or APPLIED_RE.match(after):
            continue
        ident = (start.group(2) if start and start.group(2) else None) or (row.group(1) if row else last_row) or f"line {i + 1}"
        if ident not in out:
            out.append(ident)
    return out


def owner_marks(project: Path) -> str:
    """One line naming what the owner marked and nobody has applied yet, or ""."""
    def some(ids: list[str]) -> str:
        return ", ".join(ids[:5]) + (f" (+{len(ids) - 5})" if len(ids) > 5 else "")
    parts = []
    ov = overturned(project)
    if ov:
        parts.append(f"OVERTURNED {some(ov)} in .brain/DECISIONS.md")
    answered = [(re.match(r"\d+", i["title"]) or [c.clip(i["title"], 30)])[0] for i in _needs_items(project)
                if i["resolved"] and not i["applied"]]
    if answered:
        parts.append(f"RESOLVED {some(answered)} in NEEDS_YOU.md")
    return ("owner marks to apply: " + "; ".join(parts) + " (apply each, then write APPLIED <date> under it)") if parts else ""


def req_counts(project: Path) -> dict:
    from . import req
    try:
        rows = req.load(project)
    except req.LedgerError:
        return {"total": 0, "done": 0, "open": 0, "dropped": 0, "broken": True}
    out = {"total": len(rows), "done": 0, "open": 0, "dropped": 0}
    for r in rows:
        out[r.get("status", "open") if r.get("status") in ("done", "dropped") else "open"] += 1
    return out


def _run_records(project: Path) -> list[dict]:
    """The project's session run records, oldest first by their own time (not
    by file name; the open-session marker is not one of them)."""
    rows = []
    for f in (Path(project) / ".brain" / "log").glob("[0-9]*-*.json"):
        rec = c.read_json(f, {})
        if isinstance(rec, dict) and rec.get("session"):
            rows.append(rec)
    return sorted(rows, key=lambda r: str(r.get("at", "")))


def last_run(project: Path) -> dict:
    rows = _run_records(project)
    return rows[-1] if rows else {}


def project_cost(project: Path) -> tuple[float, int]:
    """(list-price cost, sessions) over the run records whose usage is known."""
    total, n = 0.0, 0
    for rec in _run_records(project):
        cost = (rec.get("totals") or {}).get("cost")
        if isinstance(cost, (int, float)) and rec.get("usage") != "unknown":
            total += cost
            n += 1
    return total, n


# ---------------------------------------------------------------- STATUS.md
STAGE_WORDS = {
    "en": {"intake": "getting started", "requirements": "writing down what you asked", "research": "researching",
           "plan": "planning", "build": "building", "verify": "checking", "deliver": "publishing",
           "learn": "wrapping up", "done": "finished"},
    "es": {"intake": "empezando", "requirements": "anotando lo que pediste", "research": "investigando",
           "plan": "planificando", "build": "en construcción", "verify": "comprobando", "deliver": "publicando",
           "learn": "cerrando", "done": "terminado"},
}
MONTHS = {"en": "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(),
          "es": "ene feb mar abr may jun jul ago sep oct nov dic".split()}
LABELS = {
    "en": {
        "open": "Open it", "look": "Look at", "published": "last published", "not_published": "not published yet",
        "last_pub": "Last published", "nothing_open": "Nothing to open yet.",
        "stand": "Where things stand", "working": "Working on", "finished": "Last finished", "next": "Next",
        "blocked": "Blocked", "nothing_yet": "nothing yet",
        "requests": "Your requests: {done} of {total} done with evidence, {open} open", "n_dropped": ", {n} dropped",
        "reversed": "Reversed by you, not applied yet", "dropped": "Dropped (will not be done)", "no_reason": "no reason given",
        "more": "… {n} more", "more_dropped": "… {n} more in .brain/REQUIREMENTS.md",
        "needs": "Needs you", "needs_none": "Nothing right now.", "needs_details": "Details and click steps are in `NEEDS_YOU.md`.",
        "cost": "Cost", "last_session": "Last session: about ${cost} at list prices, {out} output tokens, {helpers} helper(s)",
        "last_unknown": "Last session: usage was not recorded",
        "to_date": "Project to date: about ${cost} at list prices over {n} recorded session(s)",
        "no_session": "No session has been recorded yet.",
        "list_price": "On a subscription these are list-price equivalents, not charges.",
        "recent": "Recent", "updated": "Updated", "done_word": "done", "rest": "the rest is in STATUS.md (or: brain status --full)",
    },
    "es": {
        "open": "Ábrelo", "look": "Mira", "published": "última publicación", "not_published": "aún sin publicar",
        "last_pub": "Última publicación", "nothing_open": "Todavía no hay nada que abrir.",
        "stand": "Cómo va", "working": "Trabajando en", "finished": "Lo último terminado", "next": "Siguiente",
        "blocked": "Bloqueado por", "nothing_yet": "nada todavía",
        "requests": "Tus peticiones: {done} de {total} hechas con evidencia, {open} abiertas", "n_dropped": ", {n} descartadas",
        "reversed": "Decisiones que cambiaste, aún sin aplicar", "dropped": "Descartado (no se hará)", "no_reason": "sin motivo anotado",
        "more": "… {n} más", "more_dropped": "… {n} más en .brain/REQUIREMENTS.md",
        "needs": "Te necesita", "needs_none": "Nada por ahora.", "needs_details": "Los detalles y los pasos están en `NEEDS_YOU.md`.",
        "cost": "Coste", "last_session": "Última sesión: unos ${cost} a precio de lista, {out} tokens de salida, {helpers} ayudante(s)",
        "last_unknown": "Última sesión: no se registró el uso",
        "to_date": "Proyecto hasta hoy: unos ${cost} a precio de lista en {n} sesión(es) registrada(s)",
        "no_session": "Aún no se ha registrado ninguna sesión.",
        "list_price": "Con suscripción son equivalentes a precio de lista, no cargos.",
        "recent": "Reciente", "updated": "Actualizado", "done_word": "hecho", "rest": "el resto está en STATUS.md (o: brain status --full)",
    },
}


def owner_language(manifest: dict) -> str:
    """``en`` or ``es``: the language of the files the owner reads, from the
    manifest's first ``languages`` entry."""
    langs = manifest.get("languages")
    langs = [langs] if isinstance(langs, str) else langs
    first = str(langs[0]).lower() if isinstance(langs, list) and langs else "en"
    return "es" if first.startswith("es") else "en"


def _when(iso: str, lang: str, clock: bool = True) -> str:
    """"8 Nov 2026, 10:00 UTC" from an ISO time; "" when it does not parse."""
    import datetime as dt
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    return f"{d.day} {MONTHS[lang][d.month - 1]} {d.year}" + (f", {d:%H:%M} UTC" if clock else "")


def _status(project: Path) -> tuple[str, list[str]]:
    """(the text of STATUS.md, the lines of the short view). The page opens
    with the project and its stage in plain words and what there is to open;
    its labels are in the owner's language."""
    project = Path(project)
    m, st = c.load_manifest(project), read_state(project)
    lang = owner_language(m)
    L = LABELS[lang]
    meta = m.get("project") if isinstance(m.get("project"), dict) else {}
    paths = m.get("paths") if isinstance(m.get("paths"), dict) else {}
    stage = st.get("stage") or str(m.get("stage") or "intake")
    title = f"{c.clip(str(meta.get('title') or project.name), 80)}: {STAGE_WORDS[lang].get(stage, stage)}"
    rel = _release(project)
    releases = c.read_jsonl(project / ".brain" / "log" / "releases.jsonl")
    last = releases[-1] if releases else {}
    pub = _when(last.get("at", ""), lang, clock=False)
    url = str(rel.get("live_url") or "").strip()
    things = [str(x) for x in paths.get("deliverables") or [] if x] if isinstance(paths.get("deliverables"), list) else []
    if url:
        opener = f"{L['open']}: {url} ({L['published'] + ' ' + pub if pub else L['not_published']})"
    elif things:
        opener = f"{L['look']}: {', '.join(things[:4])}" + (f" ({L['published']} {pub})" if pub else "")
    elif pub:
        opener = f"{L['last_pub']}: {pub} ({str(last.get('commit', ''))[:7]} → {last.get('branch', '')})"
    else:
        opener = L["nothing_open"]

    def have(v: str) -> str:
        return v if v and v != "none" else L["nothing_yet"]
    stand = [f"{L['working']}: {have(st.get('item', ''))}", f"{L['finished']}: {have(st.get('last_done', ''))}"]
    if st["next_list"]:
        stand.append(f"{L['next']}: " + "; ".join(st["next_list"]))
    if st.get("blockers") and st["blockers"] != "none":
        stand.append(f"{L['blocked']}: {st['blockers']}")
    rq, needs = req_counts(project), open_needs(project)
    if rq["total"]:
        stand.append(L["requests"].format(**rq) + (L["n_dropped"].format(n=rq["dropped"]) if rq["dropped"] else ""))
    reversed_ = overturned(project)
    if reversed_:
        stand.append(f"{L['reversed']}: {', '.join(reversed_[:5])}")
    dropped = [r for r in c.read_jsonl(project / ".brain" / "requirements.jsonl") if r.get("status") == "dropped"]
    drop_lines = [f"{r.get('id')} “{c.clip(str(r.get('quote', '')), 60)}”: {c.clip(str(r.get('reason') or L['no_reason']), 70)}"
                  for r in dropped[:5]]
    if len(dropped) > 5:
        drop_lines.append(L["more_dropped"].format(n=len(dropped) - 5))
    run = last_run(project)
    cost, sessions = project_cost(project)
    money = []
    if run.get("usage") == "unknown":
        money.append(L["last_unknown"])
    elif run.get("totals"):
        t = run["totals"]
        money.append(L["last_session"].format(cost=f"{t.get('cost', 0):.2f}", out=f"{int(t.get('out', 0)):,}", helpers=run.get("helpers", 0)))
    if sessions:
        money.append(L["to_date"].format(cost=f"{cost:.2f}", n=sessions))
    if not money:
        money.append(L["no_session"])
    recent = [l.replace(" done: ", f" {L['done_word']}: ", 1) for l in st["log"][-5:]]
    updated = _when(st.get("updated", ""), lang)

    def page(with_recent: bool, max_needs: int) -> list[str]:
        out = [f"# {title}", "", opener, "", f"## {L['stand']}", ""] + [f"- {l}" for l in stand]
        if drop_lines:
            out += ["", f"## {L['dropped']}", ""] + [f"- {l}" for l in drop_lines]
        out += ["", f"## {L['needs']}", ""]
        out += [f"- {n}" for n in needs[:max_needs]] if needs else [f"- {L['needs_none']}"]
        if len(needs) > max_needs:
            out.append("- " + L["more"].format(n=len(needs) - max_needs))
        if needs:
            out += ["", L["needs_details"]]
        out += ["", f"## {L['cost']}", ""] + [f"- {l}" for l in money] + [f"- {L['list_price']}"]
        if with_recent and recent:
            out += ["", f"## {L['recent']}", ""] + [f"- {l}" for l in recent]
        if updated:
            out += ["", f"{L['updated']} {updated}"]
        return out
    lines = page(True, 6)
    if len(lines) > 40:
        lines = page(False, 6)
    if len(lines) > 40:
        lines = page(False, 3)
    short = [title, opener] + stand
    short.append(f"{L['needs']}: {len(needs)} ({'; '.join(c.clip(n, 40) for n in needs[:3])}{'; …' if len(needs) > 3 else ''})"
                 if needs else f"{L['needs']}: {L['needs_none']}")
    if dropped:
        short.append(f"{L['dropped']}: {len(dropped)}")
    short += money
    if len(needs) > 3 or dropped or recent:
        short.append("… " + L["rest"])
    return "\n".join(lines[:40]).rstrip() + "\n", [c.clip(l, 200) for l in short[:14]]


def write_status(project: Path) -> str:
    """Generate the owner's STATUS.md (at most 40 lines) from state and logs.
    The file is touched only when its content changed."""
    text, _short = _status(project)
    _write_if_changed(Path(project) / "STATUS.md", text)
    return text


def status_link(project: Path) -> str:
    """Where STATUS.md can be opened on GitHub for the branch that holds the
    state ("" when the remote is elsewhere). Between releases the newest page
    is on the chat's branch, not on the repository's front page."""
    m = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", git(project, "config", "--get", "remote.origin.url"))
    branch = current_branch(project)
    if not m or branch in ("", "HEAD"):
        return ""
    if release_branch_block(project, branch):
        branch = SIDE_BRANCH
    return f"https://github.com/{m.group(1)}/{m.group(2)}/blob/{branch}/STATUS.md"


def session_cost_line() -> str:
    """This chat's list-price cost so far, from its transcript; "" when unknown."""
    try:
        from . import ledger
        main, subs = c.transcript_paths()
        if main is None or not main.is_file():
            return ""
        s = ledger.summarise(main, subs, c.read_json(c.BRAIN_ROOT / "memory" / "models.json", {}))
        return f"this chat so far: about ${s['totals']['cost']:.2f} at list prices, {s['helpers']} helper(s)"
    except Exception:  # a status must never fail on the ledger
        return ""


def brain_status_lines(brain_root: Path | None = None) -> list[str]:
    """Where the brain itself stands, for a chat with no project attached: at
    most twelve lines."""
    root = Path(brain_root or c.BRAIN_ROOT)
    ver = c.read_json(root / "VERSION.json", {})
    head = f"brain: {root.name} · version {ver.get('brain', '?') if isinstance(ver, dict) else '?'}"
    lines: list[str] = []
    if is_repo(root):
        branch = current_branch(root)
        head += f" · branch {branch}"
        base = next((b for b in ("origin/main", "main") if git(root, "rev-parse", "--verify", "--quiet", b)), "")
        if base and branch != "main":
            head += f" · {git(root, 'rev-list', '--count', f'{base}..HEAD') or '?'} commit(s) not on main"
        dirty = changed_files(root)
        if dirty:
            lines.append(f"uncommitted: {len(dirty)} change(s) ({', '.join(dirty[:3])}{', …' if len(dirty) > 3 else ''})")
        ahead = unpushed_count(root)
        if ahead:
            lines.append(f"not pushed: {ahead} commit(s)")
    try:
        from . import detect
        lines += detect.ticket_lines(root)
    except Exception:
        pass
    needs = open_needs(root)
    nums = [(re.match(r"\d+", n) or [c.clip(n, 20)])[0] for n in needs]
    lines.append(f"needs you: {', '.join(nums[:12])} (NEEDS_YOU.md)" if needs else "needs you: nothing open")
    try:
        from . import learn
        pending = len(learn.pending_inbox(root))
    except Exception:
        pending = len(list((root / "learning" / "inbox").glob("*.jsonl")))
    if pending:
        lines.append(f"learning: {pending} inbox file(s) waiting for consolidation")
    cost = session_cost_line()
    if cost:
        lines.append(cost)
    return [c.clip(l, 220) for l in [head] + lines][:12]


# ---------------------------------------------------------------- leaving a repository
def repo_cleanliness(path: Path) -> list[str]:
    """Reasons a repository is not ready to be left: uncommitted work, or
    commits that no branch on the remote holds."""
    if not is_repo(path):
        return []
    problems = []
    dirty = changed_files(path)
    if dirty:
        problems.append(f"{len(dirty)} uncommitted change(s) ({', '.join(dirty[:3])}{', …' if len(dirty) > 3 else ''})")
    branch = current_branch(path)
    if not git(path, "for-each-ref", "--count=1", "--format=%(refname)", "refs/remotes/origin"):
        problems.append(f"branch {branch} has never been pushed" if branch and branch != "HEAD" else "no commit has been pushed yet")
    else:
        ahead = unpushed_count(path)
        if ahead:
            problems.append(f"{ahead} commit(s) not pushed")
    return problems


def handover(project: Path, brain_root: Path | None = None, details: dict | None = None) -> tuple[list[str], str]:
    """Write .brain/HANDOVER.md and return (problems, text). The note is what a
    fresh chat needs; the problems are what must be fixed before leaving.
    ``details``, when given, receives ``push`` (the project's PushResult),
    ``brain`` (the brain's line) and ``branch`` (the remote branch to name)."""
    project = Path(project)
    info = details if details is not None else {}
    m = c.load_manifest(project)
    damaged = state_problem(project)
    st = read_state(project)
    if not damaged and st.get("session") not in ("", "none"):
        # Release the lease: the next chat must not be warned about "another
        # session". A later checkpoint by this chat simply takes it again.
        with _locked(project):
            st = read_state(project)
            st["session"] = "none"
            write_state(project, st)
    rq, needs = req_counts(project), open_needs(project)
    repo = is_repo(project)
    branch = current_branch(project) if repo else ""
    where = "none: detached HEAD (git switch -c <name>)" if branch == "HEAD" else (branch or "unknown")
    if repo and branch != "HEAD" and release_branch_block(project, branch):
        where += f" (kept on the remote as {SIDE_BRANCH} until it is released)"
    meta = m.get("project") if isinstance(m.get("project"), dict) else {}
    lines = [
        f"# Handover: {c.clip(str(meta.get('title') or project.name), 80)}", "",
        f"Written at the checkpoint of {st.get('updated') or c.now_iso()}. A new chat needs both repositories attached and one message: **Continue**", "",
        f"- Stage: {st.get('stage')} · size: {st.get('tier')}", f"- In progress: {st.get('item') or 'none'}",
        f"- Last finished: {st.get('last_done') or 'none'}", "- Next: " + ("; ".join(st["next_list"]) or "see .brain/PLAN.md"),
        f"- Blockers: {st.get('blockers') or 'none'}", f"- Branch with the work: {where}",
        f"- Requirements: {rq['done']}/{rq['total']} done, {rq['open']} open", f"- Waiting on the owner: {len(needs)} item(s)",
    ]
    if st.get("notes"):
        lines += ["", "## Half-finished work and where it lives", "", st["notes"]]
    text = "\n".join(lines) + "\n"
    _write_if_changed(project / ".brain" / "HANDOVER.md", text)
    write_status(project)
    write_checklist(project)
    problems = [f"project: {damaged}"] if damaged else []
    info["branch"] = branch
    if not repo:
        problems.append("project: not a git repository, so nothing can be pushed (git init, add a remote, commit)")
    else:
        # The note itself is bookkeeping: commit and push it here, otherwise
        # writing it would make the repository "not clean" and handover could never pass.
        pushed = push_bookkeeping(project)
        info["push"] = pushed
        if pushed.on_remote:
            info["branch"] = pushed.branch
        if pushed.status == "failed":
            problems.append(f"project: {pushed}")
        problems += [f"project: {p}" for p in repo_cleanliness(project)]
    brain_msg = push_brain_records(brain_root)
    info["brain"] = brain_msg
    if "FAILED" in brain_msg or "not committed" in brain_msg:
        problems.append(f"brain: {brain_msg}")
    problems += [f"brain: {p}" for p in repo_cleanliness(Path(brain_root or c.BRAIN_ROOT))]
    return problems, text


# ---------------------------------------------------------------- cli
def _checkpoint_line(st: dict) -> str:
    return c.clip(f"checkpoint: stage {st['stage']} · item: {st['item'] or 'none'} · next: {st['next'] or '-'}", 240)


def _checkpoint_brain(args) -> int:
    """`checkpoint` with only the brain attached: there is no state file to
    write, but --push still puts this session's records on the remote."""
    root = Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT)
    said = "no project attached: the position was not recorded (the brain's own is docs/plan/tickets.json)"
    if not args.push:
        print(said + "; `checkpoint --push` pushes this session's records")
        return 1
    lines = [said] if any(x is not None and x is not False for x in
                          (args.item, args.done, args.next, args.note, args.blockers, args.stage, args.tier)) else []
    msg = push_brain_records(root)
    lines.append(msg or "brain records: nothing new to push")
    left = repo_cleanliness(root)
    if left:
        lines.append("brain: " + "; ".join(left))
    print("\n".join(lines))
    return 1 if "FAILED" in msg or "not committed" in msg else 0


def cmd_checkpoint(args) -> int:
    if _brain_only(args):
        return _checkpoint_brain(args)
    project = c.need_project(args)
    if not project:
        return 1
    try:
        st = checkpoint(project, args.item, args.done, args.next, args.stage, args.tier, args.note, args.blockers, args.clear_notes)
    except StateError as e:
        print(e)
        return 1
    write_status(project)
    write_checklist(project)
    print(_checkpoint_line(st))
    if args.push:
        msg = push_bookkeeping(project)
        print(msg)
        brain_msg = push_brain_records(getattr(args, "brain_root", None))
        if brain_msg:
            print(brain_msg)
        if not msg.on_remote or "FAILED" in brain_msg or "not committed" in brain_msg:
            return 1
    return 0


def _brain_only(args) -> bool:
    """True when no project is attached and none was named: status and
    handover then report on the brain itself."""
    if getattr(args, "project", None) or os.environ.get("BRAIN_PROJECT"):
        return False
    root = getattr(args, "brain_root", None)
    proj = c.resolve_project(None, root)
    if proj is not None and c.is_managed(proj):
        return False
    from . import detect
    return detect.detect(root)["mode"] == "brain-only"


def cmd_resume(args) -> int:
    adopt = getattr(args, "adopt", None)
    if _brain_only(args):
        root = Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT)
        if adopt is not None:
            ok, line = adopt_brain(root, adopt or None)
            print(line)
            if not ok:
                return 1
        print("\n".join(brain_status_lines(root)[:11]))
        return 0
    if adopt is not None:
        target = c.resolve_project(getattr(args, "project", None))
        if target is None:
            from . import detect
            found = detect.detect().get("project")
            target = Path(found) if found else None
        if target is None:
            print("no project repository found to adopt into (attach one, or pass --project <path>)")
            return 1
        ok, line = adopt_checkpoint(target, adopt or None)
        print(line)
        if not ok:
            return 1
        if line.startswith("adopted") and c.is_managed(target) and not c.manifest_problem(target):
            from . import detect   # boot left the stale checkout alone: open the session now
            for l in detect.open_session(Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT), target):
                print(l)
    project = c.need_project(args)
    if not project:
        return 1
    for l in resume_lines(project):
        print(l)
    return 0


def cmd_status(args) -> int:
    if _brain_only(args):
        print("\n".join(brain_status_lines(getattr(args, "brain_root", None))))
        return 0
    project = c.need_project(args)
    if not project:
        return 1
    text, short = _status(project)
    _write_if_changed(project / "STATUS.md", text)
    if args.full:
        print(text.rstrip())
        return 0
    link = status_link(project)
    extra = [x for x in (session_cost_line(), f"page: {link}" if link else "") if x]
    print("\n".join(short[:15 - len(extra)] + extra))
    return 0


def _wants_close(args) -> bool:
    return bool(getattr(args, "outcome", None) or getattr(args, "cls", None) or getattr(args, "request", None)
                or getattr(args, "tier", None) is not None)


def _close_session(args, project: Path | None, brain_root: Path | None) -> tuple[bool, str]:
    """Run `brain close` with the options given to handover (the same call, so
    its rules stay in one place) and return (ok, one line)."""
    import argparse
    import io
    from . import ledger
    argv = ["close"]
    if project is not None:
        argv += ["--project", str(project)]
    for flag, val in (("--outcome", getattr(args, "outcome", None)), ("--tier", getattr(args, "tier", None)),
                      ("--request", getattr(args, "request", None)), ("--note", getattr(args, "note", None))):
        if val is not None:
            argv += [flag, str(val)]
    for cls in getattr(args, "cls", None) or []:
        argv += ["--class", cls]
    parser = argparse.ArgumentParser(prog="brain")
    ledger.register(parser.add_subparsers(dest="command"))
    buf = io.StringIO()
    try:
        ns = parser.parse_args(argv)
        if brain_root is not None:
            ns.brain_root = brain_root
        with contextlib.redirect_stdout(buf):
            code = int(ns.func(ns) or 0)
    except SystemExit:
        return False, "session NOT recorded: `brain close` did not accept these options (run it by hand to see why)"
    out = [l.strip() for l in buf.getvalue().splitlines() if l.strip()]
    pick = next((l for l in out if l.startswith(("cost:", "no transcript"))), out[0] if out else "")
    return code == 0, ("session recorded: " if code == 0 else "session NOT recorded: ") + c.clip(pick, 150)


def _print_handover(out: list[str], problems: list[str], note: str) -> int:
    if problems:
        print("\n".join(out[:2] + [f"not ready to hand over yet ({note}fix these, then run handover again):"]
                        + [" - " + c.clip(p, 300) for p in problems[:6]]))
        return 1
    print("\n".join(out[-6:]))
    return 0


def cmd_handover(args) -> int:
    brain_root = getattr(args, "brain_root", None)
    if _brain_only(args):
        return _handover_brain(args, brain_root)
    project = c.need_project(args)
    if not project:
        return 1
    out: list[str] = []
    problems: list[str] = []
    if getattr(args, "note", None) or getattr(args, "item", None):
        try:
            out.append(_checkpoint_line(checkpoint(project, item=args.item, note=args.note)))
        except StateError as e:
            print(e)
            return 1
    if _wants_close(args):
        ok, line = _close_session(args, project, brain_root)
        out.append(line)
        if not ok:
            problems.append(line)
    info: dict = {}
    found, _ = handover(project, brain_root, info)
    problems += found
    if out:   # called with the new options: say where each thing went
        if info.get("push"):
            out.append(f"project: {info['push']}")
        if info.get("brain"):
            out.append(f"brain: {info['brain']}")
    if not problems:
        out = out[-4:] + ["ready: both repositories are committed and pushed; .brain/HANDOVER.md is written",
                          f"paste in a new chat with both repositories attached:  Continue (branch {info.get('branch') or 'unknown'})"]
    return _print_handover(out, problems, "the note was written; ")


def _handover_brain(args, brain_root: Path | None) -> int:
    """Hand over a chat that has only the brain attached: the brain alone must
    be committed and pushed."""
    root = Path(brain_root or c.BRAIN_ROOT)
    out: list[str] = []
    problems: list[str] = []
    if getattr(args, "note", None) or getattr(args, "item", None):
        out.append("no project attached: --note and --item were not stored (the brain's own note is docs/NEXT_SESSION.md)")
    if _wants_close(args):
        ok, line = _close_session(args, None, brain_root)
        out.append(line)
        if not ok:
            problems.append(line)
    if not is_repo(root):
        problems.append("brain: not a git repository, so nothing can be pushed")
    msg = push_brain_records(root)
    if "FAILED" in msg or "not committed" in msg:
        problems.append(f"brain: {msg}")
    elif msg:
        out.append(f"brain: {msg}")
    problems += [f"brain: {p}" for p in repo_cleanliness(root)]
    if not problems:
        out = out[-4:] + ["ready: the brain is committed and pushed",
                          f"paste in a new chat with only Claude-Brain attached:  Continue (branch {current_branch(root) or 'unknown'})"]
    return _print_handover(out, problems, "")


def register(sub) -> None:
    p = sub.add_parser("checkpoint", help="record where the project stands (the single state file)")
    c.add_project_arg(p)
    p.add_argument("--item", help="what is in progress now")
    p.add_argument("--done", help="what was just finished (it leaves the next list)")
    p.add_argument("--next", action="append", help="up to three next items (repeat the flag); --next '' empties the list")
    p.add_argument("--stage", choices=STAGES)
    p.add_argument("--tier", type=int, choices=(1, 2, 3))
    p.add_argument("--note", help="half-finished work and where it lives")
    p.add_argument("--blockers")
    p.add_argument("--clear-notes", action="store_true")
    p.add_argument("--push", action="store_true",
                   help="also commit the bookkeeping files and push them, and this session's own records in the brain "
                        "repository; exit 0 only when the state is on the remote")
    p.set_defaults(func=cmd_checkpoint)
    p = sub.add_parser("resume", help="restate where the work stands after the context was compacted (at most 12 lines)")
    c.add_project_arg(p)
    p.add_argument("--adopt", nargs="?", const="", metavar="BRANCH",
                   help="first fast-forward to the newest checkpoint on another remote branch (or to BRANCH); never merges or forces")
    p.set_defaults(func=cmd_resume)
    p = sub.add_parser("status", help="regenerate and print the owner's STATUS.md (with no project attached: the brain's own status)")
    c.add_project_arg(p)
    p.add_argument("--full", action="store_true", help="print the whole file")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("handover", help="end a chat: write the handover note, push, and check both repositories are clean "
                                        "(with no project attached: the brain alone)")
    c.add_project_arg(p)
    p.add_argument("--note", help="checkpoint first: half-finished work and where it lives")
    p.add_argument("--item", help="checkpoint first: what is in progress now")
    p.add_argument("--outcome", choices=("ok", "partial", "failed"), help="also close the session (as `brain close` does) with this outcome")
    p.add_argument("--class", dest="cls", action="append", default=[], help="task class for the close (repeatable)")
    p.add_argument("--request", help="the owner's request, for the close (only salted word hashes are kept)")
    p.add_argument("--tier", type=int, choices=(0, 1, 2, 3), help="size of the work, for the close")
    p.set_defaults(func=cmd_handover)
