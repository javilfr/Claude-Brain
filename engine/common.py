"""Shared helpers for every engine module. Standard library only.

Conventions every module follows:
- expose ``register(sub)`` that adds argparse sub-commands and sets ``func``;
- ``func(args) -> int`` (process exit code); print short output only;
- find the brain from this file's location, never from environment variables;
- all writes go through ``write_text``/``write_json``/``append_jsonl`` (atomic);
  they refuse to write into a project whose contract is newer than this brain;
- a command that needs a project asks ``need_project``; one that can work
  without asks ``resolve_project``; both decide through ``locate_project``.
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import re
import stat
from pathlib import Path

TYPE_CHECKING = False
if TYPE_CHECKING:  # annotations only; importing typing costs every call a few milliseconds
    from typing import Any, Iterable, Iterator

BRAIN_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_VERSION = 1

# Learned zone: changed only by the learning pipeline (engine/learn.py).
LEARNED_ZONE = ("memory/", "owner/", "stats/", "playbooks/", "learning/")
# Inside the learned zone, sessions may only append here.
INBOX_DIR = "learning/inbox/"

# (label, pattern). The label is what a refusal names; the value is never shown.
# Each pattern is specific to one credential format: a loose "password = ..."
# rule would fire on ordinary code and make the scan something people ignore.
SECRET_RULES = [
    ("API key (sk-)", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}")),  # not the tail of a word such as "task-..."
    ("GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("key or password assignment", re.compile(r"(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-/+]{20,}")),
    ("GitHub fine-grained token", re.compile(r"github_pat_[A-Za-z0-9_]{30,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("Stripe key", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("signed web token", re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{20,}")),
    ("password inside an address", re.compile(r"\b[a-z][a-z0-9+.-]{1,15}://[^/\s:@]+:[^@\s/]{6,}@[A-Za-z0-9.-]+")),
    ("npm token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}")),
    ("Telegram bot token", re.compile(r"\b\d{8,10}:AA[A-Za-z0-9_-]{30,}")),
    ("SendGrid key", re.compile(r"\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}")),
    ("Twilio key", re.compile(r"\b(?:SK|AC)[0-9a-f]{32}\b")),
    ("AWS secret key", re.compile(r"(?i)aws.{0,24}(?:secret|private).{0,24}['\"][A-Za-z0-9/+=]{40}['\"]")),
]
SECRET_PATTERNS = [pat for _label, pat in SECRET_RULES]
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


class StaleBrain(OSError):
    """A write into a project whose contract is newer than this brain knows
    was refused; the text is the one line to print (exit code 3). It is an
    OSError so that code which already skips an unwritable log keeps going."""


def stale_brain(project: Path | str) -> str:
    """One line when the project uses a newer contract than this brain, else
    "". An older brain cannot know what a newer contract's files mean, so it
    writes nothing there."""
    try:
        ver = json.loads((Path(project) / ".brain" / "project.json").read_text(encoding="utf-8")).get("contract")
    except (OSError, ValueError, AttributeError, RecursionError):
        return ""
    if isinstance(ver, int) and not isinstance(ver, bool) and ver > CONTRACT_VERSION:
        return (f"stale brain: {Path(project).name} uses contract v{clip(str(ver), 12)}, this brain knows v{CONTRACT_VERSION}; "
                "nothing was written. Update the brain, then run this again")
    return ""


def _refuse_stale(path: Path) -> None:
    """Every engine write passes here: raise ``StaleBrain`` when the file sits
    in a project (its .brain/ folder, or beside it) with a newer contract."""
    parts = path.parts
    if ".brain" in parts:
        project = Path(*parts[: parts.index(".brain")])
    elif (path.parent / ".brain" / "project.json").is_file():
        project = path.parent
    else:
        return
    line = stale_brain(project)
    if line:
        raise StaleBrain(line)


def _temp_beside(p: Path) -> tuple[int, str]:
    """A new temp file in ``p``'s folder, opened for writing. Created the way
    any new file is (mode 0666 less the umask): ``tempfile.mkstemp`` forces
    0600, which then became the mode of every file the engine wrote."""
    while True:
        tmp = str(p.parent / f".tmp-{os.getpid()}-{os.urandom(4).hex()}")
        try:
            return os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666), tmp
        except FileExistsError:
            continue


def write_text(path: Path | str, text: str) -> None:
    """Atomic write: temp file in the same directory, then rename. A file
    that is rewritten keeps its mode; a new one gets what the umask allows."""
    p = Path(path)
    _refuse_stale(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = _temp_beside(p)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        try:
            os.chmod(tmp, stat.S_IMODE(p.stat().st_mode))
        except OSError:
            pass  # no earlier file (or a file system without modes): the new file's own mode stands
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
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, ValueError, RecursionError):
        return default  # missing, not UTF-8, not JSON, or nested too deep to read


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
    _refuse_stale(p)
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
    import hashlib  # here, not at the top: most calls never hash anything
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path | str) -> str:
    import hashlib
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


def secret_kind(text: str) -> str:
    """The kind of credential the text seems to hold (a label, never the
    value), or ""."""
    for label, pat in SECRET_RULES:
        if pat.search(text or ""):
            return label
    return ""


def secret_problem(text: str) -> str:
    """One line to print when text holds something shaped like a credential,
    else "". It names the kind, never the value, and says what to do instead:
    chat and git history cannot be cleaned, so the engine refuses to store it."""
    label = secret_kind(text)
    if label:
        return (f"refused: this text holds what looks like a {label} (the value is not shown or stored). "
                "Ask for it through the secure credential form, or add a NEEDS_YOU item with the clicks to store it in the environment's settings")
    return ""


def redact_secrets(text: str) -> str:
    """The text with every credential-shaped run replaced by ``[redacted]``,
    for records that must keep the rest (a gate command, a log line)."""
    out = text or ""
    for _label, pat in SECRET_RULES:
        out = pat.sub("[redacted]", out)
    return out


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


def pick_named(name: str, folders: list[Path]) -> list[Path]:
    """The folders a spoken name can mean: the one whose name it is (case
    aside) alone when there is one, else every folder whose name contains it.
    One rule for `--project <name>` and for boot's `--name`, so 'shop' means
    shop even when shop-admin is attached too."""
    want = (name or "").strip().lower()
    if not want:
        return []
    exact = [p for p in folders if p.name.lower() == want]
    return exact or [p for p in folders if want in p.name.lower()]


def _names(folders: list[Path], limit: int = 6) -> str:
    more = f" and {len(folders) - limit} more" if len(folders) > limit else ""
    return ", ".join(p.name for p in folders[:limit]) + more


def locate_project(explicit: str | None = None, brain_root: Path | None = None) -> tuple[Path | None, str]:
    """(project, "") or (None, one line saying why not and what to do).

    The one place that decides which project a command means: --project, then
    BRAIN_PROJECT (each a path, or the name of a folder beside the brain), then
    the current directory (or a parent) if managed, then the only managed
    folder beside the brain. With several managed folders and nothing to
    choose by, the engine does not guess where to write: it names them."""
    root = Path(brain_root or BRAIN_ROOT).resolve()
    sibs = sibling_dirs(root)
    managed = [p for p in sibs if is_managed(p)]
    for cand in (explicit, os.environ.get("BRAIN_PROJECT")):
        if not cand:
            continue
        path = Path(str(cand)).expanduser()
        if not path.is_dir() and path.name == str(cand):  # a bare name, not a path
            hits = pick_named(str(cand), managed) or pick_named(str(cand), sibs)
            if len(hits) > 1:
                return None, f"'{cand}' fits {len(hits)} attached projects ({_names(hits)}): pass --project with the full name"
            if hits:
                path = hits[0]
        path = path.resolve()
        if is_managed(path):
            return path, ""
        if not path.is_dir():
            return None, f"no project folder '{cand}'" + (f" (attached: {_names(managed)})" if managed else "") + ": pass --project <path or folder name>"
        return None, f"{path.name} is not a managed project (no .brain/project.json): run `brain init <path>` if it is empty, else `brain adopt <path> --survey`"
    cur = Path.cwd().resolve()
    for p in (cur, *cur.parents):
        if p == root:
            break
        if is_managed(p):
            return p, ""
    if len(managed) == 1:
        return managed[0].resolve(), ""
    if managed:
        return None, f"{len(managed)} projects attached ({_names(managed)}): add --project <name> to this command (boot shows the one it used)"
    repos = [p for p in sibs if (p / ".git").exists()]
    if repos:
        return None, (f"no managed project: {_names(repos)} {'has' if len(repos) == 1 else 'have'} no contract yet; "
                      f"run `brain init <path>` on an empty repository, else `brain adopt <path> --survey`")
    return None, "no project attached (brain-only session): this command needs one; attach a project repository beside the brain, or pass --project <path>"


def resolve_project(explicit: str | None = None, brain_root: Path | None = None) -> Path | None:
    """The project a command may use (see ``locate_project``), or None: for
    commands that also work without one (run, close, recall, hire). A project
    on a newer contract than this brain is None here, so those commands carry
    on without it and write nothing there. A folder given with --project or
    BRAIN_PROJECT that is not managed is returned as it is; callers test
    ``is_managed``."""
    found, _why = locate_project(explicit, brain_root)
    if found is not None:
        return None if stale_brain(found) else found
    for cand in (explicit, os.environ.get("BRAIN_PROJECT")):
        if cand:
            path = Path(str(cand)).expanduser()
            return path.resolve() if path.is_dir() else None
    return None


# The types the contract declares for the keys the engine reads (the same
# types as contract/v1.schema.json, kept here so that reading a manifest needs
# no second file). A key of the wrong type used to surface as a traceback in
# whichever command touched it first. Unknown keys are not looked at.
MANIFEST_SHAPE: dict = {
    "project": {"id": str, "title": str, "created": str},
    "family": str, "types": [str], "stage": str, "tier": int,
    "commands": {"setup": str, "check_fast": str, "check_full": str, "run": str},
    "gates": [{"id": str, "kind": str, "command": str, "file": str}],
    "release": {"rule": str, "branch": str, "live_url": str, "live_expect": str},
    "paths": {"deliverables": [str], "evidence": str, "never_touch": [str]},
    "languages": [str], "risk": str,
    "privacy": {"share_lessons": str},
    "brain": {"last_seen": str, "min_contract": int},
}
_SHAPE_WORDS = {dict: "an object", list: "a list", str: "text", int: "a whole number"}


def _found(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true/false"
    return {dict: "an object", list: "a list", str: "text", int: "a number", float: "a decimal number"}.get(type(value), type(value).__name__)


def _shaped(value: Any, spec: Any, where: str, problems: list[str]) -> Any:
    """``value`` with every part of the wrong type left out (a section becomes
    empty, a list loses the entry, a key is dropped so its default applies);
    each such part adds one line to ``problems``."""
    want = dict if isinstance(spec, dict) else list if isinstance(spec, list) else spec
    if not isinstance(value, want) or (want is int and isinstance(value, bool)):
        problems.append(f'"{where}" must be {_SHAPE_WORDS[want]} (found {_found(value)})')
        if spec == [str] and isinstance(value, str) and value.strip():
            return [value.strip()]  # "languages": "es" plainly means ["es"]: read it, and still say it
        return None
    if isinstance(spec, dict):
        out = dict(value)
        for key, sub in spec.items():
            if key in out:
                got = _shaped(out[key], sub, f"{where}.{key}" if where else key, problems)
                if got is None:
                    del out[key]
                else:
                    out[key] = got
        return out
    if isinstance(spec, list):
        kept = []
        for i, v in enumerate(value):
            got = _shaped(v, spec[0], f"{where}[{i}]", problems)
            if got is not None:
                kept.append(got)
        return kept
    return value


def manifest_shape(data: dict) -> tuple[dict, list[str]]:
    """(usable copy, problems) of a parsed manifest. In the copy a wrong-typed
    section is empty rather than absent, so ``m["gates"]`` and
    ``m.get("release", {})`` both behave."""
    problems: list[str] = []
    out = _shaped(data, MANIFEST_SHAPE, "", problems) or {}
    for key, spec in MANIFEST_SHAPE.items():
        if key in data and key not in out and isinstance(spec, (dict, list)):
            out[key] = type(spec)()
    return out, problems


def load_manifest(project: Path, raw: bool = False) -> dict:
    """The project's manifest, with wrong-typed parts left out so no reader
    crashes on them (``manifest_problem`` is what says them out loud).
    ``raw=True`` gives the file as it is, for code that writes it back."""
    m = read_json(Path(project) / ".brain" / "project.json", {})
    if not isinstance(m, dict):
        return {}
    return m if raw else manifest_shape(m)[0]


def manifest_problem(project: Path) -> str:
    """One line when the manifest exists but cannot be used, else "". A broken
    manifest must be said out loud: silently treating it as empty would make
    gates and release rules disappear."""
    path = Path(project) / ".brain" / "project.json"
    if not path.is_file():
        return ""
    fix = "fix it or restore it from git before anything else"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as e:  # not JSON, not UTF-8, or nested beyond reading
        return f".brain/project.json is not valid JSON ({clip(str(e), 60)}); {fix}"
    except OSError as e:
        return f".brain/project.json cannot be read ({clip(str(e), 60)}); {fix}"
    ver = data.get("contract") if isinstance(data, dict) else None
    if not isinstance(ver, int) or isinstance(ver, bool):
        return f".brain/project.json has no integer 'contract'; {fix}"
    if ver > CONTRACT_VERSION:
        return ""  # a newer contract may have other shapes: that is `stale_brain`'s line, not this one
    problems = manifest_shape(data)[1]
    if problems:
        more = f" (and {len(problems) - 1} more: brain validate)" if len(problems) > 1 else ""
        return f".brain/project.json: {problems[0]}{more}; {fix}"
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
    """The managed, usable project for a command that needs one, or None
    after printing the one line that says why not and what to do next. A
    project on a newer contract raises ``StaleBrain`` instead."""
    proj, why = locate_project(getattr(args, "project", None))
    if proj is None:
        print(why)
        return None
    stale = stale_brain(proj)
    if stale:
        raise StaleBrain(stale)  # bin/brain prints the line and exits 3; no caller goes on to write
    problem = manifest_problem(proj)
    if problem:
        print(problem)
        return None
    return proj
