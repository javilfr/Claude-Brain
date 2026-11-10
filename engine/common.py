"""Shared helpers for every engine module. Standard library only.

Conventions every module follows:
- expose ``register(sub)`` that adds argparse sub-commands and sets ``func``;
- ``func(args) -> int`` (process exit code); print short output only;
- find the brain from this file's location, never from environment variables;
- all writes go through ``write_text``/``write_json``/``append_jsonl`` (atomic).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable, Iterator

BRAIN_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VERSION = 1

# Learned zone: changed only by the learning pipeline (engine/learn.py).
LEARNED_ZONE = ("memory/", "owner/", "stats/", "playbooks/", "learning/")
# Inside the learned zone, sessions may only append here.
INBOX_DIR = "learning/inbox/"

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+]{20,}"),
]
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


# ---------------------------------------------------------------- time
def now() -> _dt.datetime:
    """Current UTC time; ``BRAIN_NOW`` (ISO) overrides it for tests."""
    fixed = os.environ.get("BRAIN_NOW")
    if fixed:
        d = _dt.datetime.fromisoformat(fixed.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)
    return _dt.datetime.now(_dt.timezone.utc)


def now_iso() -> str:
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return now().strftime("%Y-%m-%d")


def days_since(date_str: str) -> int:
    """Days from an ISO date/datetime to now; a large number if unparsable."""
    try:
        d = _dt.datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return 10 ** 6
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return max(0, (now() - d).days)


# ---------------------------------------------------------------- files
def read_text(path: Path | str, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (FileNotFoundError, IsADirectoryError, UnicodeDecodeError):
        return default


def write_text(path: Path | str, text: str) -> None:
    """Atomic write: temp file in the same directory, then rename."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path | str, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        return default


def write_json(path: Path | str, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def read_jsonl_counted(path: Path | str) -> tuple[list[dict], int]:
    """(objects, unreadable line count) of a JSONL file. Each line is decoded
    on its own with ``errors="replace"``, so one bad byte costs one line, not
    the whole file. A line is unreadable when it is not valid UTF-8 or not a
    JSON object; blank lines are not counted. A missing file is ([], 0)."""
    try:
        raw = Path(path).read_bytes()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
        return [], 0
    out: list[dict] = []
    bad = 0
    for bline in raw.splitlines():
        if not bline.strip():
            continue
        try:
            line = bline.decode("utf-8")
        except UnicodeDecodeError:
            bad += 1
            line = bline.decode("utf-8", "replace")
            # A line with a replaced byte may still be a record (inside a
            # string); it is kept, but the line is counted as damaged.
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                out.append(obj)
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            bad += 1
            continue
        if isinstance(obj, dict):
            out.append(obj)
        else:
            bad += 1
    return out, bad


def read_jsonl(path: Path | str) -> list[dict]:
    """Read a JSONL file; blank and malformed lines are skipped (decoding is
    per line, so an undecodable byte loses only its own line)."""
    return read_jsonl_counted(path)[0]


def dump_jsonl(rows: Iterable[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


def write_jsonl(path: Path | str, rows: Iterable[dict]) -> None:
    write_text(path, dump_jsonl(rows))


def append_jsonl(path: Path | str, row: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def iter_jsonl_stream(path: Path | str) -> Iterator[dict]:
    """Stream large JSONL (session transcripts) without loading it whole."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except FileNotFoundError:
        return


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
    except FileNotFoundError:
        return ""
    return h.hexdigest()


# ---------------------------------------------------------------- text
def est_tokens(text: str) -> int:
    """Cheap token estimate (about 4 characters per token)."""
    return int(math.ceil(len(text) / 4)) if text else 0


def clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: max(0, limit - 1)].rstrip() + "…"


_WORD = re.compile(r"[a-záéíóúüñ0-9][a-záéíóúüñ0-9_+#.-]*", re.IGNORECASE)
STOPWORDS = frozenset(
    "a an and are as at be by for from has have i in is it its me my of on or our so "
    "that the their them then there these this to was we were will with you your "
    "el la los las un una y o de del en que por para con es al lo se su".split()
)


def words(text: str) -> list[str]:
    """Lower-case content words (English and Spanish stop-words removed)."""
    return [w.strip(".-").lower() for w in _WORD.findall(text or "") if w.lower() not in STOPWORDS and len(w.strip(".-")) > 1]


def find_secrets(text: str) -> list[str]:
    """Names of secret patterns found in text (never the secret itself)."""
    hits = []
    for i, pat in enumerate(SECRET_PATTERNS):
        if pat.search(text or ""):
            hits.append(f"secret-pattern-{i}")
    return hits


# ---------------------------------------------------------------- projects
def is_managed(path: Path) -> bool:
    return (path / ".brain" / "project.json").is_file()


def is_empty_repo(path: Path) -> bool:
    """A repository with nothing but git data, a README, a licence or .gitignore."""
    allowed = {".git", "readme.md", "readme", "license", "license.md", ".gitignore", ".gitattributes"}
    try:
        names = [n.name.lower() for n in path.iterdir()]
    except OSError:
        return False
    return all(n in allowed for n in names)


def sibling_dirs(brain_root: Path | None = None) -> list[Path]:
    root = Path(brain_root or BRAIN_ROOT)
    out = []
    try:
        for p in sorted(root.parent.iterdir()):
            if p.is_dir() and p.resolve() != root.resolve() and not p.name.startswith("."):
                out.append(p)
    except OSError:
        pass
    return out


def resolve_project(explicit: str | None = None, brain_root: Path | None = None) -> Path | None:
    """The project to act on: --project, then BRAIN_PROJECT, then the current
    directory (or a parent) if managed, then the single managed sibling."""
    for cand in (explicit, os.environ.get("BRAIN_PROJECT")):
        if cand:
            return Path(cand).expanduser().resolve()
    cur = Path.cwd().resolve()
    root = Path(brain_root or BRAIN_ROOT).resolve()
    for p in (cur, *cur.parents):
        if p == root:
            break
        if is_managed(p):
            return p
    managed = [p for p in sibling_dirs(root) if is_managed(p)]
    if len(managed) == 1:
        return managed[0].resolve()
    return None


def load_manifest(project: Path) -> dict:
    m = read_json(Path(project) / ".brain" / "project.json", {})
    return m if isinstance(m, dict) else {}


def manifest_problem(project: Path) -> str:
    """One line when the manifest exists but cannot be used, else "". A broken
    manifest must be said out loud: silently treating it as empty would make
    gates and release rules disappear."""
    path = Path(project) / ".brain" / "project.json"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return f".brain/project.json is not valid JSON ({clip(str(e), 60)}); fix it or restore it from git before anything else"
    if not isinstance(data, dict) or not isinstance(data.get("contract"), int):
        return ".brain/project.json has no integer 'contract'; fix it or restore it from git before anything else"
    return ""


# ---------------------------------------------------------------- sessions
def session_id() -> str:
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("BRAIN_SESSION_ID") or "local"


def transcript_paths(sid: str | None = None, home: Path | None = None) -> tuple[Path | None, list[Path]]:
    """(main transcript, sub-agent transcripts) for a session, if on disk.

    Claude Code stores them under ~/.claude/projects/<cwd-slug>/<session>.jsonl
    and <session>/subagents/agent-*.jsonl. ``BRAIN_TRANSCRIPT`` overrides the
    main path (used by tests and by hooks that receive ``transcript_path``).
    """
    sid = sid or session_id()
    override = os.environ.get("BRAIN_TRANSCRIPT")
    main: Path | None = Path(override) if override else None
    if main is None:
        base = Path(home or Path.home()) / ".claude" / "projects"
        hits = sorted(base.glob(f"*/{sid}.jsonl")) if base.is_dir() else []
        main = hits[0] if hits else None
    return main, (helper_transcripts(main) if main is not None else [])


def helper_transcripts(main: Path) -> list[Path]:
    """Every helper transcript of the session whose main transcript is ``main``.

    Helpers started with the Agent tool are in <session>/subagents/agent-*.jsonl;
    helpers started by a workflow are one level down, in
    <session>/subagents/workflows/<run>/agent-*.jsonl, beside a journal.jsonl
    that is not a transcript. Both count: a ledger that saw only the first kind
    reported one helper in a session that had started seventeen.
    """
    subdir = main.parent / main.stem / "subagents"
    return sorted(subdir.rglob("agent-*.jsonl")) if subdir.is_dir() else []


# ---------------------------------------------------------------- cli
def add_project_arg(p) -> None:
    p.add_argument("--project", help="project path (default: detected)")


def need_project(args) -> Path | None:
    proj = resolve_project(getattr(args, "project", None))
    if proj is None or not is_managed(proj):
        print("no managed project found (attach one, or run: brain init <path>)")
        return None
    problem = manifest_problem(proj)
    if problem:
        print(problem)
        return None
    return proj
