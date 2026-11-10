"""The learning pipeline: the only writer of the brain's learned zone.

Why it is built this way (MASTER_PLAN Part 6, ENGINE_SPEC, EXECUTION_PLAN 4.2):
- Sessions only append records to ``learning/inbox/``. ``consolidate`` turns
  pending inbox files into ONE delta (an ordered list of small operations) and
  ``apply`` executes it. Nothing else writes ``memory/``, ``owner/``,
  ``stats/``, ``playbooks/``, the manifest or the changelog.
- No operation replaces or deletes a file, and a delta that would retire too
  many items, shrink a file sharply, or rewrite most of an item's text is
  refused whole: a memory rewritten wholesale collapsed from 18k tokens to 122
  and fell below having no memory (round2/01 section 3.8).
- Credit comes only from external outcomes (gate exit codes, owner
  corrections), never from the model's opinion of its own memory (I-07):
  model-judged credit scored planted entries at 1.0. A ``used`` record says
  only whether an item was followed; whether it helped is read from the
  session's outcome records.
- Notes pass an admission gate before they become items (actionable,
  checkable, new, not about one project), and promotion to ``active`` needs
  two independent keys (round2/01 sections 3.4-3.5). Owner-stated items are
  never demoted, decayed or superseded by learning (I-08).
- Statistical learning lives in ``engine/mlearn.py``; this module hands it the
  new records in one ``ML_FOLD`` op and stores the state it returns in
  ``stats/ml.json``. The import is lazy so every other op works without it.
- Everything ``apply`` writes is a pure function of the files it starts from
  and the delta (time comes from the delta, not the clock), so CI can replay
  the recorded deltas on the base commit and demand byte-identical files
  (``verify``). A hand edit dressed up as learning then fails.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import json
import posixpath
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import common as c
from . import items as I
from .guard import zone_of

OPS = ("ADD", "INC_HELPFUL", "INC_HARMFUL", "EDIT_TEXT", "SET_STATUS", "MOVE_SCOPE", "LINK", "SUPERSEDE",
       "APPEND_STAT", "ML_FOLD", "MARK_INBOX")
KINDS = ("ledger", "outcome", "used", "note", "review", "correction", "lead", "hire")
FOLD_KINDS = ("outcome", "used", "review", "correction", "hire")   # inbox records mlearn learns from
# ML_FOLD also carries "promotion" records the consolidation itself makes, so
# a drift alarm can name the item promoted just before a shift.
ML_KINDS = FOLD_KINDS + ("promotion",)
DEFAULT_BUDGET = 400
SIMILAR = 0.6             # word Jaccard at or above which a note restates an item
CONTAINED = 0.8           # share of the shorter text's words found in the other
CONTAIN_MIN_WORDS = 4     # containment is meaningless for very short texts
MAX_EDIT_RATIO = 0.3      # EDIT_TEXT may change at most this share of an item
MIN_EDIT_CHARS = 40       # and may not leave fewer characters than this
PROMOTE_MULTIPLIER = 1.0  # default mlearn.item_score for probation -> active; memory/ml_config.json learning.promote_multiplier overrides (review item M18)


def promote_multiplier(root: Path) -> float:
    cfg = c.read_json(Path(root) / ML_CONFIG, {})
    v = ((cfg or {}).get("learning") or {}).get("promote_multiplier", PROMOTE_MULTIPLIER) if isinstance(cfg, dict) else PROMOTE_MULTIPLIER
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else PROMOTE_MULTIPLIER
DEMOTE_AFTER_DAYS = 90    # fallback when mlearn.retention is unavailable
RETIRE_AFTER_DAYS = 90 + 180
RETENTION_FLOOR = 0.15    # fallback for memory/ml_config.json retention.threshold
TRUST_NOTE = ("observed", "owner-stated", "external")
SIGNALS = ("gate-failed", "rework", "owner-correction", "token-outlier", "first-success")
# Evidence must point at an event a script can check: a gate, a test, an
# outcome record, an owner turn, a run record or a review.
EVIDENCE_RE = re.compile(r"^(gate|test|outcome|owner|run|review):\S")
ARCHIVE = "memory/archive.jsonl"
MANIFEST = "learning/manifest.jsonl"
CHANGELOG = "learning/CHANGELOG.md"
ML_STATE = "stats/ml.json"
ML_CONFIG = "memory/ml_config.json"
KNOWN_IDS = "evals/known_project_ids.txt"
LEDGER_FILE_RE = re.compile(r"^stats/ledger/\d{4}-\d{2}\.jsonl$")
# The only files an ADD may name: the item files of the learned zone. Every
# path a delta names must also be plain (relative, normal form, no '..'), so
# "memory/../evals/routing.jsonl" cannot pass for a memory file (I-06, I-09).
ITEM_FILE_RE = re.compile(r"^(?:memory/(?:items|facts)\.jsonl|owner/(?:standing|preferences)\.jsonl|"
                          r"playbooks/[a-z][a-z0-9-]{0,40}\.jsonl)$")
INBOX_FILE_RE = re.compile(r"^learning/inbox/[A-Za-z0-9][A-Za-z0-9_.-]{0,120}\.jsonl$")
# Owner evidence is written only by the script that found the owner's words in
# a turn he typed: the turn's timestamp and a hash of the normalised quote.
OWNER_EV_RE = re.compile(r"^owner:turn@[0-9A-Za-z:.+-]{1,40}#[0-9a-f]{12}$")
MIN_QUOTE = 12
# Turns that look typed but were injected by the harness or another agent.
NOT_OWNER_MARKERS = ("[SYSTEM NOTIFICATION", "Another Claude session sent a message", "Stop hook feedback",
                     "[Subagent hand-back]", "<task-notification>", "<system-reminder")
NEGATIVE_RE = re.compile(r"\b(never|don't|do not|must not|should not|shouldn't|avoid|no longer|cannot|can't|stop)\b", re.I)
# Words that carry polarity are removed before comparing meaning, so that
# "always X" and "never X" are recognised as the same subject.
POLARITY_WORDS = frozenset("always never do don does doesn not no avoid must should shouldn cannot can stop longer".split())
IMPERATIVE_RE = re.compile(r"\b(always|never|must|should|shall|do not|don't|avoid|make sure|ensure|remember to|you need to|"
                           r"need to|prefer|only when|only after)\b", re.I)
IMPERATIVE_START = frozenset(
    "use run add remove delete ignore install write set call send keep stop skip disable enable push commit "
    "read follow check prefer avoid never always do don't please make ensure execute open fetch upload "
    "pin record screenshot test verify measure split build ask list name mark log save cache retry rerun re-run "
    "limit cap batch start finish review compare translate back-translate quote cite reply give show tell include "
    "exclude put move replace try wait close checkpoint plan estimate delegate pass choose pick label tag sort "
    "group link copy deploy release lock profile pair state report confirm search load print drop".split())
# A condition first ("Before a release, run ...") is actionable when a verb follows.
CONDITION_START = frozenset("before after when whenever if once while for on".split())
# Path-like tokens: ./x, ~/x, /x/y, a/b/c, or a file name with an extension.
PATH_RE = re.compile(r"(?:^|[\s(\"'`])(?:\.{1,2}|~)?/[\w.-]+|\b[\w.-]+/[\w.-]+/[\w./-]*|"
                     r"\b[\w-]+\.(?:py|js|ts|tsx|jsx|mjs|json|jsonl|md|sh|ya?ml|toml|html|css|sql|go|rs|java|rb|txt|"
                     r"cfg|ini|lock|env|csv|xml)\b", re.I)

# Tests inject a stand-in for engine.mlearn here; None means import it lazily.
MLEARN = None


def plain_path_problem(rel) -> str:
    """Why ``rel`` is not a plain brain-relative path; empty when it is."""
    if not isinstance(rel, str) or not rel:
        return "empty path"
    if rel.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rel) or "\\" in rel or "\0" in rel:
        return "absolute or not a plain path"
    if any(part in ("", ".", "..") for part in rel.split("/")):
        return "has an empty, '.' or '..' segment"
    if posixpath.normpath(rel) != rel:
        return "not in normal form"
    return ""


def mlearn_module(optional: bool = False):
    """``engine.mlearn``, imported on first use so the rest of the pipeline
    works while it is absent. ``optional`` returns None instead of raising."""
    if MLEARN is not None:
        return MLEARN
    try:
        from . import mlearn
    except ImportError:
        if optional:
            return None
        raise
    return mlearn


def record_id(session: str, kind: str, key: str) -> str:
    """Stable id of an inbox record: the same event recorded twice gets the
    same id, so mlearn can fold idempotently per record."""
    return c.sha256_text(f"{session}\n{kind}\n{key}")[:16]


def record_key(rec: dict) -> str:
    """The per-kind part of a record's identity (one ledger row per session,
    one outcome per task class, one use per item, ...)."""
    kind = rec.get("kind")
    if kind == "outcome":
        return str(rec.get("task_class", ""))
    if kind in ("used", "correction"):
        return str(rec.get("item", "")) + ("|" + str((rec.get("evidence") or [""])[0]) if kind == "correction" else "")
    if kind == "note":
        return " ".join(str(rec.get("text", "")).split())
    if kind == "review":
        return f"{rec.get('task_class', '')}|{rec.get('round', '')}"
    if kind == "lead":
        return str(rec.get("url", ""))
    return ""


def with_id(rec: dict) -> dict:
    if rec.get("id"):
        return rec
    return {**rec, "id": record_id(str(rec.get("session", "")), str(rec.get("kind", "")), record_key(rec))}


# ---------------------------------------------------------------- inbox
def safe_session(sid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "-", str(sid))[:80] or "local"


def manifest_rows(root: Path) -> list[dict]:
    return c.read_jsonl(Path(root) / MANIFEST)


def consumed_inbox(root: Path) -> set[str]:
    return {f for row in manifest_rows(root) for f in row.get("inbox_files", [])}


def _session_files(root: Path, sid: str) -> list[Path]:
    inbox = Path(root) / c.INBOX_DIR
    s = safe_session(sid)
    return sorted(set(inbox.glob(f"*-{s}.jsonl")) | set(inbox.glob(f"*-{s}-n*.jsonl")))


def _writable_session_file(root: Path, sid: str) -> Path:
    """The session's inbox file that has not been consolidated yet, or a new
    one: a consolidated file is never rewritten, so CI sees inbox additions only."""
    consumed = consumed_inbox(root)
    files = _session_files(root, sid)
    for f in files:
        if f.relative_to(root).as_posix() not in consumed:
            return f
    base = f"{c.today()}-{safe_session(sid)}"
    name = f"{base}.jsonl" if not files else f"{base}-n{len(files) + 1}.jsonl"
    return Path(root) / c.INBOX_DIR / name


def pending_session_records(root: Path, sid: str) -> list[dict]:
    """This session's records that have not been consolidated yet."""
    root = Path(root)
    consumed = consumed_inbox(root)
    return [r for f in _session_files(root, sid) if f.relative_to(root).as_posix() not in consumed
            for r in c.read_jsonl(f) if r.get("session") == sid]


def replace_session_records(root: Path, sid: str, records: list[dict], kinds: tuple[str, ...]) -> Path | None:
    """Put ``records`` in the session's inbox file, replacing earlier records
    of the same kinds from this session. Returns None (writes nothing) when a
    consolidated file already holds such records: counting twice is worse
    than missing the tail of a session."""
    root = Path(root)
    consumed = consumed_inbox(root)
    for f in _session_files(root, sid):
        if f.relative_to(root).as_posix() in consumed and any(
                r.get("kind") in kinds and r.get("session") == sid for r in c.read_jsonl(f)):
            return None
    path = _writable_session_file(root, sid)
    keep = [r for r in c.read_jsonl(path) if not (r.get("kind") in kinds and r.get("session") == sid)]
    c.write_jsonl(path, keep + [with_id(r) for r in records])
    return path


def pending_inbox(root: Path) -> list[Path]:
    root = Path(root)
    consumed = consumed_inbox(root)
    return [p for p in sorted((root / c.INBOX_DIR).glob("*.jsonl")) if p.relative_to(root).as_posix() not in consumed]


def inbox_unreadable(root: Path) -> tuple[int, int]:
    """(unreadable lines, files holding them) among the pending inbox files."""
    lines = files = 0
    for p in pending_inbox(root):
        try:
            bad = c.read_jsonl_counted(p)[1]
        except OSError:
            bad = 1
        lines += bad
        files += bool(bad)
    return lines, files


def official_leads(root: Path) -> list[dict]:
    """Radar leads from official sources still waiting in the inbox. A lead
    never changes memory by itself: the model must confirm it at the source."""
    return [r for p in pending_inbox(root) for r in c.read_jsonl(p)
            if r.get("kind") == "lead" and r.get("trust") == "official"]


# ---------------------------------------------------------------- notes
def is_imperative(text: str) -> bool:
    first = (text.split() or [""])[0].lower().strip(".,:;!\"'")
    return first in IMPERATIVE_START or bool(IMPERATIVE_RE.search(text))


def actionable(text: str) -> bool:
    """A lesson must tell a future session what to do: an imperative verb
    first, a modal cue (should, must, never, ...), or a condition followed by
    a verb. Observations without an action are clutter in the store."""
    if is_imperative(text):
        return True
    ws = [w.lower().strip(".,:;!\"'") for w in text.split()]
    return bool(ws) and ws[0] in CONDITION_START and any(w in IMPERATIVE_START for w in ws[1:])


def known_project_ids(root: Path) -> list[str]:
    return [l.strip() for l in c.read_text(Path(root) / KNOWN_IDS).splitlines() if l.strip() and not l.startswith("#")]


def project_specific(text: str, ids: list[str]) -> bool:
    """True when the text names a path, a file or a known project: such a
    lesson belongs in that project's .brain/, not in the shared brain (I-05)."""
    if PATH_RE.search(text):
        return True
    return any(re.search(r"(?<![A-Za-z0-9_-])" + re.escape(pid) + r"(?![A-Za-z0-9_-])", text, re.I) for pid in ids)


def check_note(rec: dict) -> list[str]:
    """Problems with a note record; empty means it may enter the inbox."""
    errs = []
    text = rec.get("text", "")
    if not isinstance(text, str) or not text.strip():
        errs.append("text is empty")
    elif len(text) > I.MAX_TEXT:
        errs.append(f"text is {len(text)} characters (limit {I.MAX_TEXT})")
    if not rec.get("class"):
        errs.append("at least one --class is required")
    ev = rec.get("evidence") or []
    # For a fact read from an official page the source address is the
    # evidence: there is no gate or owner turn to point at, and the fact is
    # re-checked against that address when its re-check date comes round.
    sourced_fact = rec.get("trust") == "external" and str(rec.get("source", "")).startswith("https://")
    if not ev and not sourced_fact:
        errs.append("evidence is required (a gate, test, outcome or owner turn)")
    elif not all(isinstance(e, str) and EVIDENCE_RE.match(e) for e in ev):
        errs.append("each evidence must start with gate:, test:, outcome:, owner:, run: or review:")
    elif any(e.startswith("owner:") and not OWNER_EV_RE.match(e) for e in ev):
        errs.append("owner evidence must be verified against a turn the owner typed (learn note --quote)")
    if rec.get("trust") == "owner-stated" and not any(isinstance(e, str) and OWNER_EV_RE.match(e) for e in ev):
        errs.append("owner-stated needs the owner's own words, verified in this session's transcript (--quote)")
    if not I.SCOPE_RE.match(str(rec.get("scope", ""))):
        errs.append("scope must be global, project or family:<family>")
    trust = rec.get("trust")
    if trust not in TRUST_NOTE:
        errs.append(f"trust must be one of {', '.join(TRUST_NOTE)}")
    if rec.get("signal") and rec["signal"] not in SIGNALS:
        errs.append(f"signal must be one of {', '.join(SIGNALS)}")
    if trust == "external" and isinstance(text, str):
        if is_imperative(text):
            errs.append("external text cannot become a rule; state it as a fact with a source")
        elif not rec.get("source"):
            errs.append("an external fact needs a source")
    blob = " ".join([str(text), str(rec.get("source", ""))] + [str(e) for e in ev])
    if c.find_secrets(blob):
        errs.append("looks like it contains a secret")
    if c.EMAIL_PATTERN.search(blob):
        errs.append("contains an email address")
    return errs


# ---------------------------------------------------------------- owner words and evidence
def norm_quote(text: str) -> str:
    """Case-folded, whitespace collapsed: the form quotes are compared in."""
    return " ".join(str(text).casefold().split())


def owner_turns(transcript: Path | str) -> list[tuple[str, str]]:
    """(timestamp, text) of every turn the owner typed in a transcript: a
    ``user`` row whose content is a string or text blocks, not a tool result,
    not flagged ``isMeta`` or ``isSidechain``, and without a marker of text
    the harness or another agent injected."""
    out = []
    for row in c.iter_jsonl_stream(transcript):
        if row.get("type") != "user" or row.get("isMeta") or row.get("isSidechain"):
            continue
        msg = row.get("message") if isinstance(row.get("message"), dict) else {}
        if msg.get("role", "user") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list) and content and all(
                isinstance(b, dict) and b.get("type") in ("text", "image") for b in content):
            text = "\n".join(b["text"] for b in content if b.get("type") == "text" and isinstance(b.get("text"), str))
        else:
            continue
        if not text or any(m in text for m in NOT_OWNER_MARKERS):
            continue
        out.append((str(row.get("timestamp") or "unknown"), text))
    return out


def verify_owner_quote(quote: str, sid: str | None = None) -> tuple[str, str]:
    """(evidence, "") when ``quote`` occurs in a turn the owner typed in this
    session's transcript, else ("", one-line reason). The evidence names the
    turn and a hash of the quote, never the quote itself."""
    q = norm_quote(quote or "")
    if len(q) < MIN_QUOTE:
        return "", f"--quote must hold at least {MIN_QUOTE} characters of the owner's own words"
    main, _subs = c.transcript_paths(sid or c.session_id())
    if main is None or not Path(main).is_file():
        return "", "no transcript of this session is on disk, so the owner's words cannot be checked"
    for ts, text in owner_turns(main):
        if q in norm_quote(text):
            return f"owner:turn@{ts}#{c.sha256_text(q)[:12]}", ""
    return "", "the quote is not in any turn the owner typed in this session"


def project_words(project: Path | None) -> list[str]:
    """Names that identify the resolved project: its manifest id and title and
    its folder name. A brain note naming one belongs in that project (I-05)."""
    if project is None:
        return []
    meta = c.load_manifest(project).get("project") or {}
    names = [str(meta.get("id") or ""), str(meta.get("title") or ""), Path(project).name]
    return [n.strip() for n in names if len(n.strip()) >= 3]


def _gate_rows(project: Path, sid: str) -> list[dict]:
    return [r for r in c.read_jsonl(Path(project) / ".brain" / "log" / "gates.jsonl") if str(r.get("session", "")) == sid]


def _session_start(project: Path, sid: str) -> str:
    """When this session began: its open-session marker, else the first
    timestamp of its transcript; "" when neither is known."""
    marker = c.read_json(Path(project) / ".brain" / "log" / "open-session.json", {}) or {}
    if isinstance(marker, dict) and marker.get("session") == sid and marker.get("at"):
        return str(marker["at"])
    main, _ = c.transcript_paths(sid)
    if main is not None and Path(main).is_file():
        for row in c.iter_jsonl_stream(main):
            if isinstance(row.get("timestamp"), str) and row["timestamp"]:
                return row["timestamp"]
    return ""


RUN_LOG_RE = re.compile(r"^(\d{8})-(\d{6})-[0-9a-f]{4,64}\.log$")


def _session_run_logs(project: Path, sid: str) -> list[Path]:
    """Run logs written since this session began (``brain run`` names each log
    by its UTC start time)."""
    start = _session_start(project, sid)
    if not start:
        return []
    key = re.sub(r"[^0-9]", "", start)[:14]
    out = []
    for p in sorted((Path(project) / ".brain" / "log" / "run").glob("*.log")):
        m = RUN_LOG_RE.match(p.name)
        if m and m[1] + m[2] >= key:
            out.append(p)
    return out


EVIDENCE_HELP = (
    "Evidence must resolve to something this session did. Accepted forms: "
    "gate:<gate-id> [words] (a run of that gate by this session in the project's .brain/log/gates.jsonl); "
    "test:<name> (the name appears in the saved output of a gate run or run log of this session); "
    "run:<log-file> (a log in the project's .brain/log/run/ written since this session began); "
    "outcome:<record-id> (an outcome record of this session in the brain inbox); "
    "review:<file> (an existing file, stored as a hash of its content). "
    "Owner evidence comes only from --quote. With no managed project, only --quote and review: are accepted.")


def resolve_evidence(evidence: list[str], sid: str, project: Path | None, brain_root: Path | None = None,
                     cwd: Path | None = None) -> tuple[list[str], str]:
    """(evidence to store, "") when every item resolves to this session's own
    records, else ([], one-line reason). ``review:`` is stored as a content
    hash so no project path reaches the brain."""
    root = Path(brain_root or c.BRAIN_ROOT)
    out: list[str] = []
    for e in evidence:
        e = str(e).strip()
        kind, _, rest = e.partition(":")
        token = (rest.split() or [""])[0]
        if kind == "owner":
            return [], "owner evidence comes only from --quote, checked against the owner's typed turns"
        if kind == "review":
            base = [Path(token)] if Path(token).is_absolute() else \
                [b / token for b in ([project] if project else []) + [Path(cwd or Path.cwd())]]
            hit = next((b for b in base if b.is_file()), None)
            if hit is None:
                return [], f"{e!r}: no such file"
            out.append(f"review:sha256-{c.sha256_file(hit)[:12]}")
            continue
        if project is None:
            return [], f"{e!r}: with no managed project only --quote and review:<file> evidence can be checked"
        if kind == "gate":
            if not any(str(r.get("gate") or r.get("id") or "") == token for r in _gate_rows(project, sid)):
                return [], f"{e!r}: no run of gate {token!r} by this session in .brain/log/gates.jsonl"
        elif kind == "outcome":
            ids = {with_id(r)["id"] for f in _session_files(root, sid) for r in c.read_jsonl(f)
                   if r.get("kind") == "outcome" and r.get("session") == sid}
            if token not in ids:
                return [], f"{e!r}: no outcome record {token!r} of this session in the inbox"
        elif kind == "run":
            if "/" in token or not any(p.name == token for p in _session_run_logs(project, sid)):
                return [], f"{e!r}: no run log {token!r} written by this session in .brain/log/run/"
        elif kind == "test":
            logs = [Path(str(r["log"])) for r in _gate_rows(project, sid) if r.get("log")] + _session_run_logs(project, sid)
            if not token or not any(token in c.read_text(p) for p in logs if p.is_file()):
                return [], f"{e!r}: {token!r} is not in the output of any gate run or run log of this session"
        else:
            return [], f"{e!r}: unknown evidence kind"
        out.append(" ".join(e.split()))
    return out, ""


def note_item(rec: dict, day: str, kind: str = "rule", by_model: str = "") -> dict:
    """The memory item a note becomes. External notes become facts, never
    rules or pitfalls; ``kind`` "pitfall" is decided by the consolidation."""
    fact = rec.get("trust") == "external"
    kind = "fact" if fact else kind
    text = " ".join(str(rec["text"]).split())
    slug = "-".join(w for w in (re.sub(r"[^a-z0-9]", "", x) for x in c.words(text)) if w)[:40].strip("-") or "item"
    prefix = {"fact": "fact", "pitfall": "pit"}.get(kind, "lsn")
    item = I.normalise({
        "id": f"{prefix}-{slug}-{c.sha256_text(text)[:6]}",
        "type": kind,
        "scope": rec.get("scope", "global"),
        "class": list(rec.get("class") or []),
        "text": text,
        "evidence": list(rec.get("evidence") or []),
        "provenance": f"note:{safe_session(rec.get('session', 'local'))[:12]}",
        "trust": rec.get("trust", "observed"),
        "created": day,
        "status": "candidate",
        "sessions": 0,
    })
    if by_model:
        item["by_model"] = by_model
    if fact:
        item["source"] = str(rec.get("source", ""))
        item["verified_on"] = day
        item["recheck_days"] = 90
        item["valid_from"] = day
    return item


def _core(text: str) -> set[str]:
    return {w for w in c.words(text) if w not in POLARITY_WORDS}


def jaccard(a: str, b: str) -> float:
    x, y = _core(a), _core(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def containment(a: str, b: str) -> float:
    """Share of the shorter text's words that the longer one also has; 0 for
    texts too short for the measure to mean anything."""
    x, y = _core(a), _core(b)
    small = min(len(x), len(y))
    return len(x & y) / small if small >= CONTAIN_MIN_WORDS else 0.0


def restates(a: str, b: str) -> bool:
    return jaccard(a, b) >= SIMILAR or containment(a, b) >= CONTAINED


def negative(text: str) -> bool:
    return bool(NEGATIVE_RE.search(text))


def edit_ratio(old: str, new: str) -> float:
    """Share of an item's text an edit changes (0 = identical, 1 = unrelated)."""
    a, b = " ".join(old.split()), " ".join(new.split())
    return 1.0 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _live(row: dict, day: str) -> bool:
    vt = str(row.get("valid_to") or "")
    return row.get("status", "active") not in ("demoted", "retired") and not (vt and vt[:10] <= day)


# ---------------------------------------------------------------- workspace
def _item_files(root: Path) -> list[str]:
    root = Path(root)
    files = [f for f in I.BRAIN_FILES if (root / f).is_file()]
    files += [p.relative_to(root).as_posix() for p in sorted((root / "playbooks").glob("*.jsonl"))]
    return files


class Workspace:
    """An in-memory copy of the learned files a delta touches. Ops are
    applied here first; nothing reaches disk unless the whole delta passes."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.rows: dict[str, list[dict]] = {}
        self.orig: dict[str, str] = {}
        self.text: dict[str, str] = {}
        self.touched: set[str] = set()
        self.changed_ids: set[str] = set()
        self.retired: dict[str, int] = {}
        self.inbox_files: list[str] = []
        self.notes: list[str] = []
        self.votes = [0, 0]
        self.counts = {"APPEND_STAT": 0, "ML_FOLD": 0}
        cfg = c.read_json(self.root / ML_CONFIG, {})
        self.ml_cfg: dict = cfg if isinstance(cfg, dict) else {}
        for rel in _item_files(self.root):
            self._load_items(rel)

    # -- loading
    def _load_items(self, rel: str) -> None:
        if rel not in self.rows:
            self.orig[rel] = c.read_text(self.root / rel)
            self.rows[rel] = c.read_jsonl(self.root / rel)

    def _get_text(self, rel: str) -> str:
        if rel not in self.text:
            self.orig.setdefault(rel, c.read_text(self.root / rel))
            self.text[rel] = self.orig[rel]
        return self.text[rel]

    def _append(self, rel: str, row: dict) -> None:
        self.text[rel] = self._get_text(rel) + c.dump_jsonl([row])
        self.touched.add(rel)

    def ml_state(self) -> dict | None:
        """The mlearn state as it stands in this workspace; None if unreadable."""
        raw = self._get_text(ML_STATE)
        try:
            state = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            return None
        return state if isinstance(state, dict) else None

    def find(self, iid: str) -> tuple[str, dict] | tuple[None, None]:
        for rel, rows in self.rows.items():
            for r in rows:
                if r.get("id") == iid:
                    return rel, r
        return None, None

    def all_items(self) -> list[tuple[str, dict]]:
        return [(rel, r) for rel in sorted(self.rows) for r in self.rows[rel]]

    # -- ops
    def apply_op(self, op: dict, at: str) -> str:
        """Apply one op; returns an error string, or "" on success."""
        kind = op.get("op")
        day = at[:10]
        if kind == "ADD":
            rel, item = op.get("file", ""), op.get("item")
            bad = plain_path_problem(rel)
            if bad or not ITEM_FILE_RE.match(rel) or zone_of(rel) != "learned":
                return f"ADD: {rel!r} is not an item file" + (f" ({bad})" if bad else "")
            if not isinstance(item, dict):
                return "ADD: item missing"
            item = I.normalise(item)
            if item.get("trust") == "owner-stated" and not any(OWNER_EV_RE.match(str(e)) for e in item.get("evidence") or []):
                return f"ADD: {item.get('id')} is owner-stated without owner evidence verified against a typed turn"
            if self.find(item.get("id", ""))[0]:
                return f"ADD: id {item.get('id')} already exists"
            self._load_items(rel)
            self.rows[rel].append(item)
            self._touch_item(rel, item["id"])
            self.notes.append(f"learned ({item['status']}) {item['id']}: {c.clip(item['text'], 90)}")
            return ""
        if kind in ("INC_HELPFUL", "INC_HARMFUL"):
            rel, row = self.find(str(op.get("id", "")))
            if row is None:
                return f"{kind}: unknown item {op.get('id')}"
            n = op.get("n", 1)
            if not isinstance(n, int) or isinstance(n, bool) or n < 0:
                return f"{kind}: n must be a non-negative integer"
            field = "helpful" if kind == "INC_HELPFUL" else "harmful"
            row[field] = int(row.get(field, 0) or 0) + n
            self.votes[0 if field == "helpful" else 1] += n
            row["uses"] = int(row.get("uses", 0) or 0) + 1
            row["last_used"] = day
            ev = list(row.get("evidence") or [])
            sid = op.get("session")
            # Only a session that supported the item counts towards promotion.
            if sid and field == "helpful" and n > 0 and f"session:{sid}" not in ev:
                ev.append(f"session:{sid}")
                row["sessions"] = int(row.get("sessions", 0) or 0) + 1
            for e in op.get("evidence") or []:
                if e not in ev:
                    ev.append(e)
            row["evidence"] = ev
            self._touch_item(rel, row["id"])
            return ""
        if kind == "EDIT_TEXT":
            rel, row = self.find(str(op.get("id", "")))
            if row is None:
                return f"EDIT_TEXT: unknown item {op.get('id')}"
            new = " ".join(str(op.get("text", "")).split())
            if len(new) < MIN_EDIT_CHARS:
                return f"EDIT_TEXT: {row['id']} would keep {len(new)} characters (minimum {MIN_EDIT_CHARS})"
            ratio = edit_ratio(str(row.get("text", "")), new)
            if ratio > MAX_EDIT_RATIO:
                return (f"EDIT_TEXT: {row['id']} would change {ratio:.0%} of its text (limit {MAX_EDIT_RATIO:.0%}); "
                        "add a new item and SUPERSEDE the old one instead")
            row["text"] = new
            self._touch_item(rel, row["id"])
            self.notes.append(f"{row['id']}: text edited")
            return ""
        if kind == "SET_STATUS":
            return self._set_status(str(op.get("id", "")), op.get("status"), day)
        if kind == "MOVE_SCOPE":
            rel, row = self.find(str(op.get("id", "")))
            if row is None:
                return f"MOVE_SCOPE: unknown item {op.get('id')}"
            old = row.get("scope", "")
            row["scope"] = op.get("scope")
            self._touch_item(rel, row["id"])
            self.notes.append(f"{row['id']}: scope {old} -> {op.get('scope')}")
            return ""
        if kind == "LINK":
            rel_a, a = self.find(str(op.get("a", "")))
            rel_b, b = self.find(str(op.get("b", "")))
            rel_kind = op.get("rel", "conflicts")
            if a is None or b is None:
                return f"LINK: unknown item {op.get('a') if a is None else op.get('b')}"
            if rel_kind not in ("conflicts", "supersedes"):
                return "LINK: rel must be conflicts or supersedes"
            pairs = [(a, b), (b, a)] if rel_kind == "conflicts" else [(a, b)]
            for x, y in pairs:
                lst = list(x.get(rel_kind) or [])
                if y["id"] not in lst:
                    lst.append(y["id"])
                x[rel_kind] = lst
            self._touch_item(rel_a, a["id"])
            self._touch_item(rel_b, b["id"])
            self.notes.append(f"{a['id']} and {b['id']} disagree; neither is promoted until evidence separates them"
                              if rel_kind == "conflicts" else f"{a['id']} supersedes {b['id']}")
            return ""
        if kind == "SUPERSEDE":
            return self._supersede(str(op.get("old", "")), str(op.get("new", "")), day)
        if kind == "APPEND_STAT":
            rel = op.get("file", "")
            if plain_path_problem(rel) or not LEDGER_FILE_RE.match(rel) or not isinstance(op.get("row"), dict):
                return f"APPEND_STAT: bad file {rel!r} or row"
            self._append(rel, op["row"])
            self.counts["APPEND_STAT"] += 1
            return ""
        if kind == "ML_FOLD":
            return self._ml_fold(op.get("records"))
        if kind == "MARK_INBOX":
            rel = op.get("file", "")
            if plain_path_problem(rel) or not INBOX_FILE_RE.match(rel) or zone_of(rel) != "inbox":
                return f"MARK_INBOX: {rel!r} is not an inbox file"
            if rel not in self.inbox_files:
                self.inbox_files.append(rel)
            return ""
        return f"unknown op {kind!r}"

    def _touch_item(self, rel: str, iid: str) -> None:
        self.touched.add(rel)
        self.changed_ids.add(iid)

    def _supersede(self, old_id: str, new_id: str, day: str) -> str:
        """Close the old item's validity and link both; nothing is deleted, so
        the history stays readable and recall simply stops showing the old one."""
        rel_o, old = self.find(old_id)
        rel_n, new = self.find(new_id)
        if old is None or new is None:
            return f"SUPERSEDE: unknown item {old_id if old is None else new_id}"
        if old is new:
            return "SUPERSEDE: an item cannot supersede itself"
        if old.get("trust") == "owner-stated":
            return f"SUPERSEDE: {old_id} is owner-stated; only the owner can replace it"
        if old.get("type") != new.get("type"):
            return f"SUPERSEDE: {old_id} and {new_id} are of different types"
        if old.get("valid_to"):
            return f"SUPERSEDE: {old_id} was already superseded on {old['valid_to']}"
        old["valid_to"] = day
        old["superseded_by"] = list(old.get("superseded_by") or []) + [new_id]
        if old_id not in (new.get("supersedes") or []):
            new["supersedes"] = list(new.get("supersedes") or []) + [old_id]
        new.setdefault("valid_from", day)
        self._touch_item(rel_o, old_id)
        self._touch_item(rel_n, new_id)
        self.notes.append(f"{new_id} supersedes {old_id} (kept as history, no longer recalled)")
        return ""

    def _ml_fold(self, records) -> str:
        """Hand new outcome/used/review/correction records to ``mlearn.fold``
        and keep the state it returns (written with sorted keys so replays
        are byte-identical)."""
        if not isinstance(records, list) or not records or not all(
                isinstance(r, dict) and r.get("kind") in ML_KINDS and r.get("id") for r in records):
            return "ML_FOLD: records must be a non-empty list of outcome, used, review, correction or promotion records with ids"
        try:
            ml = mlearn_module()
            fold = ml.fold
        except (ImportError, AttributeError) as e:
            return f"ML_FOLD: engine.mlearn is not available ({e})"
        state = self.ml_state()
        if state is None:
            return f"ML_FOLD: {ML_STATE} is not a JSON object"
        try:
            # mlearn.config adds memory/models.json to the constants; both are
            # in the replayed tree, so the fold stays a pure function of it.
            cfg = ml.config(self.root) if hasattr(ml, "config") else self.ml_cfg
        except ValueError as e:
            return f"ML_FOLD: {e}"
        try:
            new = fold(state, records, cfg)
        except (ValueError, TypeError, KeyError) as e:
            return f"ML_FOLD: mlearn.fold failed ({type(e).__name__}: {e})"
        if not isinstance(new, dict):
            return "ML_FOLD: mlearn.fold did not return a state object"
        self.text[ML_STATE] = json.dumps(new, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        self.touched.add(ML_STATE)
        self.counts["ML_FOLD"] += len(records)
        return ""

    def _set_status(self, iid: str, status, day: str) -> str:
        rel, row = self.find(iid)
        if row is None:
            return f"SET_STATUS: unknown item {iid}"
        if status not in I.STATUS:
            return f"SET_STATUS: bad status {status!r}"
        old = row.get("status", "active")
        if status == "retired":
            self.rows[rel] = [r for r in self.rows[rel] if r is not row]
            self.retired[rel] = self.retired.get(rel, 0) + 1
            self.touched.add(rel)
            self._append(ARCHIVE, {**row, "status": "retired", "retired_on": day, "retired_from": rel})
        else:
            row["status"] = status
            self._touch_item(rel, iid)
        self.notes.append(f"{iid}: {old} -> {status}")
        return ""

    # -- checks and output
    def check(self, budget: int = DEFAULT_BUDGET) -> list[str]:
        """Whole-delta refusals: retire cap, shrink cap, item validity, budget."""
        errs = []
        for rel in sorted(self.touched):
            if rel in self.rows:
                n_orig = len([l for l in self.orig.get(rel, "").splitlines() if l.strip()])
                gone = self.retired.get(rel, 0)
                if gone and gone > max(1, n_orig // 10):
                    errs.append(f"{rel}: would retire {gone} of {n_orig} items (limit 10%)")
                if len(self.rows[rel]) > budget:
                    errs.append(f"{rel}: {len(self.rows[rel])} items exceeds the budget of {budget}")
                for r in self.rows[rel]:
                    if r.get("id") in self.changed_ids:
                        errs += [f"{rel}: {e}" for e in I.validate_item(I.normalise(r))]
            if rel == ML_STATE:
                continue  # statistics, not memory text: mlearn may legitimately compact it
            old, new = self.orig.get(rel, ""), self.new_text(rel)
            # Small files are governed by the retire cap (one item may go);
            # the shrink cap protects files large enough to be collapsed.
            if len(old.splitlines()) >= 10 and len(new) < 0.8 * len(old):
                errs.append(f"{rel}: would shrink by {100 - 100 * len(new) // len(old)}% (limit 20%)")
        return errs

    def new_text(self, rel: str) -> str:
        return c.dump_jsonl(self.rows[rel]) if rel in self.rows else self.text.get(rel, self.orig.get(rel, ""))

    def changelog_lines(self) -> list[str]:
        lines = list(self.notes)
        if any(self.votes):
            lines.append(f"{self.votes[0]} helpful and {self.votes[1]} harmful vote(s) recorded")
        if self.counts["APPEND_STAT"]:
            lines.append(f"{self.counts['APPEND_STAT']} ledger row(s) recorded")
        if self.counts["ML_FOLD"]:
            lines.append(f"{self.counts['ML_FOLD']} record(s) folded into the learning statistics")
        if self.inbox_files:
            lines.append(f"{len(self.inbox_files)} inbox file(s) consolidated")
        return lines


# ---------------------------------------------------------------- deltas
def ops_hash(ops: list[dict]) -> str:
    return c.sha256_text(json.dumps(ops, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def make_delta(ops: list[dict], at: str | None = None) -> dict:
    at = at or c.now_iso()
    return {"id": f"d-{at[:10].replace('-', '')}-{ops_hash(ops)[:10]}", "at": at, "ops": ops}


def canonical(delta: dict) -> str:
    return json.dumps(delta, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def apply_delta(delta: dict, brain_root: Path | None = None, budget: int = DEFAULT_BUDGET) -> tuple[bool, list[str]]:
    """Validate the whole delta in memory, then write. Returns (ok, lines)."""
    root = Path(brain_root or c.BRAIN_ROOT)
    ops = delta.get("ops")
    did, at = str(delta.get("id", "")), str(delta.get("at", ""))
    if not isinstance(ops, list) or not ops or not all(isinstance(o, dict) for o in ops):
        return False, ["delta has no list of operations"]
    if not re.match(r"^[a-z0-9][a-z0-9-]{2,80}$", did) or not re.match(r"^\d{4}-\d{2}-\d{2}T", at):
        return False, ["delta needs an id (lower-case, digits, dashes) and an ISO 'at' time"]
    if any(r.get("id") == did for r in manifest_rows(root)):
        return True, [f"delta {did} was already applied; nothing changed"]
    ws = Workspace(root)
    for i, op in enumerate(ops):
        err = ws.apply_op(op, at)
        if err:
            return False, [f"op {i + 1}: {err}"]
    errs = ws.check(budget)
    if errs:
        return False, errs

    written: dict[str, str] = {}
    for rel in sorted(ws.touched):
        text = ws.new_text(rel)
        c.write_text(root / rel, text)
        written[rel] = text
    for rel in sorted(r for r in ws.touched if r.startswith("playbooks/") and r.endswith(".jsonl")):
        md = rel[:-len(".jsonl")] + ".md"
        written[md] = I.render_markdown(root / rel)
        c.write_text(root / md, written[md])
    delta_rel = f"learning/deltas/{did}.json"
    written[delta_rel] = canonical({"id": did, "at": at, "ops": ops})
    c.write_text(root / delta_rel, written[delta_rel])
    log = ws.changelog_lines()
    old_log = c.read_text(root / CHANGELOG) or "# Learning changelog\n\nOne section per applied delta, written by `brain learn apply`.\n"
    written[CHANGELOG] = old_log + f"\n## {at[:10]} {did}\n\n" + "".join(f"- {l}\n" for l in log)
    c.write_text(root / CHANGELOG, written[CHANGELOG])
    entry = {"id": did, "at": at, "ops_sha256": ops_hash(ops), "ops_count": len(ops),
             "files": {rel: c.sha256_text(t) for rel, t in sorted(written.items())},
             "inbox_files": ws.inbox_files}
    c.write_text(root / MANIFEST, c.read_text(root / MANIFEST) + json.dumps(entry, sort_keys=True, ensure_ascii=False) + "\n")
    return True, [f"applied {did}: {len(ops)} op(s), {len(written)} file(s) written"] + log[:8]


# ---------------------------------------------------------------- consolidate
def _item_scorer(ws: Workspace):
    """``mlearn.item_score`` bound to the workspace's state, or None when the
    module or its state is missing (then the second promotion key is waived)."""
    ml = mlearn_module(optional=True)
    fn = getattr(ml, "item_score", None)
    state = ws.ml_state()
    if fn is None or not state:
        return None
    return lambda item: float(fn(state, item))


def _transitions(ws: Workspace, at: str, min_sessions: int) -> list[dict]:
    """Status moves earned by evidence, applied to ``ws`` and returned as ops.

    probation -> active needs two independent keys: support from at least
    ``min_sessions`` sessions AND (when mlearn has data) a lower-bound
    multiplier of at least 1.0. One owner statement is enough on its own.
    Conflicting items are never promoted; harm demotes, except what the owner
    stated (I-08)."""
    score = _item_scorer(ws)
    bar = promote_multiplier(ws.root)
    ops = []
    for _ in range(3):  # candidate -> probation -> active can happen in one pass
        moved = False
        for _rel, row in ws.all_items():
            it = I.normalise(row)
            st, h, x = it["status"], it["helpful"], it["harmful"]
            owner = it["trust"] == "owner-stated"
            new = None
            if not owner and x >= 3 and x > h and st not in ("demoted", "retired"):
                new = "demoted"
            elif owner and st in ("candidate", "probation"):
                new = "active"
            elif it["conflicts"]:
                new = None
            elif st == "candidate" and h >= 1:
                new = "probation"
            elif st == "probation" and it["sessions"] >= min_sessions and (
                    score is None or score(it) >= bar):
                new = "active"
            if new:
                op = {"op": "SET_STATUS", "id": it["id"], "status": new}
                ws.apply_op(op, at)
                ops.append(op)
                moved = True
        if not moved:
            break
    return ops


def _fail_pass_pairs(outcomes: list[dict]) -> dict[str, tuple[str, str]]:
    """Per task class, the first failed outcome followed later by a passing
    one: the evidence a pitfall needs (round2/01 section 3.7)."""
    pairs: dict[str, tuple[str, str]] = {}
    by_class: dict[str, list[dict]] = {}
    for o in outcomes:
        by_class.setdefault(str(o.get("task_class", "")), []).append(o)
    for cls, rows in sorted(by_class.items()):
        fail = None
        for o in sorted(rows, key=lambda r: (str(r.get("at", "")), str(r.get("id", "")))):
            if o.get("passed") is False and fail is None:
                fail = o
            elif o.get("passed") is True and fail is not None:
                pairs[cls] = (fail["id"], o["id"])
                break
    return pairs


def _pitfall_pair(rec: dict, pairs: dict[str, tuple[str, str]]) -> tuple[str, str] | None:
    """The fail/pass pair a gate-failed note is about, matched by class
    (``software`` matches outcomes of ``software.feature``)."""
    if rec.get("signal") != "gate-failed":
        return None
    tags = set(rec.get("class") or [])
    for cls, pair in sorted(pairs.items()):
        if cls in tags or cls.split(".")[0] in tags:
            return pair
    return None


def _note_ops(ws: Workspace, rec: dict, at: str, pairs: dict, by_model: str, ids: list[str]) -> tuple[list[dict], str]:
    """Ops for one note after the admission gate: a vote on an item it
    restates, a conflict link, or an ADD (a pitfall when a fail/pass pair
    backs it)."""
    errs = check_note(rec)
    if rec.get("scope") == "project":
        errs.append("project lessons stay in the project")
    if errs:
        return [], errs[0]
    text = " ".join(str(rec["text"]).split())
    fact = rec.get("trust") == "external"
    if not fact and not actionable(text):
        return [], "not actionable: say what to do (an imperative, or should/must/never)"
    if project_specific(text, ids):
        return [], "names a path, file or project: keep it in that project's .brain/"
    pair = None if fact else _pitfall_pair(rec, pairs)
    item = note_item(rec, at[:10], "pitfall" if pair else "rule", by_model)
    if pair:
        item["evidence"] += [f"outcome:{pair[0]}", f"outcome:{pair[1]}"]
    day = at[:10]
    best, best_sim = None, -1.0
    for _rel, row in ws.all_items():
        if (row.get("type") == "fact") != fact or not _live(row, day):
            continue
        other = str(row.get("text", ""))
        if not restates(item["text"], other):
            continue
        sim = jaccard(item["text"], other)
        if sim > best_sim or (sim == best_sim and row["id"] < best["id"]):
            best, best_sim = row, sim
    sid = str(rec.get("session", ""))
    if best is not None and negative(best["text"]) == negative(item["text"]):
        return [{"op": "INC_HELPFUL", "id": best["id"], "n": 1, "session": sid,
                 "evidence": list(rec.get("evidence") or [])}], ""
    item["sessions"] = 1 if sid else 0
    if sid:
        item["evidence"].append(f"session:{sid}")
    ops = [{"op": "ADD", "file": "memory/facts.jsonl" if fact else "memory/items.jsonl", "item": item}]
    if best is not None:
        ops.append({"op": "LINK", "a": item["id"], "b": best["id"], "rel": "conflicts"})
    return ops, ""


def _used_op(rec: dict, outcomes: list[dict]) -> dict | None:
    """Credit for a followed item, read from the same session's outcomes:
    every gate green on the first run is a helpful vote, a failed outcome a
    harmful one, anything else just records the use. Never from the model."""
    if rec.get("followed") is not True:
        return None
    sid = str(rec.get("session", ""))
    mine = [o for o in outcomes if str(o.get("session", "")) == sid]
    ev = [f"outcome:{o['id']}" for o in mine]
    if mine and all(o.get("passed") is True and o.get("first_pass", True) is True for o in mine):
        return {"op": "INC_HELPFUL", "id": rec.get("item"), "n": 1, "session": sid, "evidence": ev}
    if any(o.get("passed") is False for o in mine):
        return {"op": "INC_HARMFUL", "id": rec.get("item"), "n": 1, "session": sid, "evidence": ev}
    return {"op": "INC_HELPFUL", "id": rec.get("item"), "n": 0, "session": sid, "evidence": []}


def _record_problem(rec: dict) -> str:
    """Why a fold record cannot be used; empty when it can."""
    kind = rec.get("kind")
    if kind == "outcome" and (not rec.get("task_class") or not isinstance(rec.get("passed"), bool)):
        return "outcome needs task_class and passed (true or false)"
    if kind == "used" and (not isinstance(rec.get("item"), str) or not isinstance(rec.get("followed"), bool)):
        return "used needs item and followed (true or false)"
    if kind == "correction":
        ev = rec.get("evidence") or []
        if not ev or not all(OWNER_EV_RE.match(str(e)) for e in ev):
            return "correction needs owner evidence verified against a typed turn (learn correction --quote)"
        sizing = isinstance(rec.get("rule_tier"), int) and isinstance(rec.get("tier"), int)
        if not isinstance(rec.get("item"), str) and not sizing:
            return "correction needs an item, or a rule_tier and tier for a sizing correction"
    return ""


def build_consolidation(brain_root: Path | None = None, min_sessions: int = 2) -> tuple[dict | None, list[str]]:
    """One delta for every pending inbox file, plus a list of rejections.

    Returns (None, [reason]) when the new records cannot be folded into the
    learning statistics: consuming them without folding would lose them."""
    root = Path(brain_root or c.BRAIN_ROOT)
    files = pending_inbox(root)
    if not files:
        return None, []
    at = c.now_iso()
    ws = Workspace(root)
    ops: list[dict] = []
    rejected: list[str] = []
    ids = known_project_ids(root)

    def take(candidates: list[dict], label: str) -> None:
        for op in candidates:
            err = ws.apply_op(op, at)
            if err:
                rejected.append(f"{label}: {err}")
            else:
                ops.append(op)

    batch = []
    expected: dict[Path, int] = {}
    for f in files:
        try:
            recs, _bad = c.read_jsonl_counted(f)
        except OSError:
            rejected.append(f"{f.name}: cannot be read; left pending")
            continue
        expected[f] = len(recs)
        batch += [(f, n, with_id(rec)) for n, rec in enumerate(recs, 1)]
    done: dict[Path, int] = {}
    fold: list[dict] = []
    for f, n, rec in batch:
        if rec.get("kind") not in FOLD_KINDS:
            continue
        problem = _record_problem(rec)
        if problem:
            rejected.append(f"{f.name}:{n}: {problem}")
            continue
        if rec.get("kind") == "used" and "helped" in rec:
            rejected.append(f"{f.name}:{n}: 'helped' ignored; credit comes only from outcomes")
            rec = {k: v for k, v in rec.items() if k != "helped"}
        fold.append(rec)
    outcomes = [r for r in fold if r["kind"] == "outcome"]
    if fold:
        op = {"op": "ML_FOLD", "records": fold}
        err = ws.apply_op(op, at)
        if err:
            return None, [err]
        ops.append(op)
    pairs = _fail_pass_pairs(outcomes)
    models: dict[str, str] = {}  # session -> main model; the ledger row says it best
    for kind in ("outcome", "ledger"):
        models.update({str(r.get("session", "")): str(r["model"]) for _f, _n, r in batch
                       if r.get("kind") == kind and r.get("model")})
    good_ids = {r["id"] for r in fold}

    for f, n, rec in batch:
        label = f"{f.name}:{n}"
        kind = rec.get("kind")
        done[f] = done.get(f, 0) + 1
        if kind == "ledger":
            month = str(rec.get("at", at))[:7]
            take([{"op": "APPEND_STAT", "file": f"stats/ledger/{month}.jsonl", "row": rec}], label)
        elif kind == "used" and rec["id"] in good_ids:
            op = _used_op(rec, outcomes)
            if op:
                take([op], label)
        elif kind == "correction" and rec["id"] in good_ids and isinstance(rec.get("item"), str):
            take([{"op": "INC_HARMFUL", "id": rec["item"], "n": 1, "session": str(rec.get("session", "")),
                   "evidence": list(rec["evidence"])}], label)
        elif kind == "note":
            note_ops, err = _note_ops(ws, rec, at, pairs, models.get(str(rec.get("session", "")), ""), ids)
            if err:
                rejected.append(f"{label}: {err}")
            take(note_ops, label)
        elif kind not in KINDS:
            rejected.append(f"{label}: unknown kind {kind!r}")
    for f in files:
        # A file is handled only when every valid record in it was processed;
        # its unreadable lines are reported (inbox_unreadable), never silently dropped.
        if f not in expected or done.get(f, 0) != expected[f]:
            continue
        rel = f.relative_to(root).as_posix()
        take([{"op": "MARK_INBOX", "file": rel}], rel)
    moves = _transitions(ws, at, min_sessions)
    promos = [{"kind": "promotion", "id": record_id("", "promotion", f"{o['id']}|{at}"), "session": "", "at": at,
               "item": o["id"]} for o in moves if o["status"] == "active"]
    fold_op = next((o for o in ops if o["op"] == "ML_FOLD"), None)
    if promos and (fold_op is not None or mlearn_module(optional=True) is not None):
        if ws.apply_op({"op": "ML_FOLD", "records": promos}, at) == "":
            if fold_op is None:
                ops.insert(0, {"op": "ML_FOLD", "records": promos})
            else:
                fold_op["records"] = fold_op["records"] + promos
    return make_delta(ops + moves, at), rejected


# ---------------------------------------------------------------- decay
def build_decay(brain_root: Path | None = None) -> tuple[dict | None, list[str]]:
    """Demote items that have faded and retire long-demoted ones (within the
    retire cap per file); return stale facts as lines to print.

    Fading is ``mlearn.retention`` below the configured floor when that
    module is present (a usage-based forgetting curve: an item followed often
    fades slowly), else 90 days without use. Owner-stated items never fade (I-08)."""
    root = Path(brain_root or c.BRAIN_ROOT)
    at = c.now_iso()
    ws = Workspace(root)
    retention = getattr(mlearn_module(optional=True), "retention", None)
    floor = (ws.ml_cfg.get("retention") or {}).get("threshold", RETENTION_FLOOR)
    now = c.now()
    ops: list[dict] = []
    stale: list[str] = []
    for rel in sorted(ws.rows):
        to_retire = []
        for row in ws.rows[rel]:
            it = I.normalise(row)
            if it.get("verified_on") and not it.get("valid_to") and \
                    c.days_since(it["verified_on"]) > int(it.get("recheck_days", 90) or 90):
                stale.append(f"stale fact {it['id']}: verified {it['verified_on']}, re-check every {it.get('recheck_days', 90)} days")
            if it["trust"] == "owner-stated":  # what the owner said does not fade with disuse
                continue
            unused = c.days_since(it["last_used"] or it["created"])
            if it["status"] in ("candidate", "probation", "active") and it["importance"] < 3:
                faded = retention(it, now) < floor if retention else unused >= DEMOTE_AFTER_DAYS
                if faded:
                    ops.append({"op": "SET_STATUS", "id": it["id"], "status": "demoted"})
            elif it["status"] == "demoted" and unused >= RETIRE_AFTER_DAYS:
                to_retire.append((-unused, it["id"]))
        limit = max(1, len(ws.rows[rel]) // 10)
        ops += [{"op": "SET_STATUS", "id": iid, "status": "retired"} for _, iid in sorted(to_retire)[:limit]]
    return (make_delta(ops, at) if ops else None), stale


# ---------------------------------------------------------------- digest
def _iso_week(d: _dt.datetime) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _row_tokens(row: dict) -> int:
    return sum(int(m.get(k, 0) or 0) for m in (row.get("models") or {}).values() if isinstance(m, dict)
               for k in ("in", "cache_write", "cache_read", "out"))


def _median(xs: list[int]) -> float:
    s = sorted(xs)
    n = len(s)
    return float(s[n // 2]) if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _parse(at: str) -> _dt.datetime | None:
    try:
        d = _dt.datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def build_digest(brain_root: Path | None = None, weeks: int = 1) -> tuple[str, str]:
    """(relative path, text) of the weekly digest, at most 15 lines."""
    root = Path(brain_root or c.BRAIN_ROOT)
    now = c.now()
    start = now - _dt.timedelta(days=7 * weeks)
    before = start - _dt.timedelta(days=28)
    learned, retired = [], []
    for row in manifest_rows(root):
        d = _parse(row.get("at", ""))
        if not d or d < start or d > now:
            continue
        delta = c.read_json(root / "learning" / "deltas" / f"{row.get('id')}.json", {}) or {}
        for op in delta.get("ops", []):
            if op.get("op") == "ADD":
                learned.append(f"{op['item']['id']}: {c.clip(op['item'].get('text', ''), 80)}")
            elif op.get("op") == "SET_STATUS" and op.get("status") == "active":
                learned.append(f"{op['id']} is now active")
            elif op.get("op") == "SET_STATUS" and op.get("status") in ("retired", "demoted"):
                retired.append(f"{op['id']} ({op['status']})")
    now_t: dict[str, list[int]] = {}
    old_t: dict[str, list[int]] = {}
    for f in sorted((root / "stats" / "ledger").glob("*.jsonl")):
        for r in c.read_jsonl(f):
            d = _parse(r.get("at", ""))
            if not d:
                continue
            bucket = now_t if start <= d <= now else old_t if before <= d < start else None
            if bucket is not None:
                bucket.setdefault(r.get("task_class") or "unclassified", []).append(_row_tokens(r))
    eff = []
    for cls in sorted(set(now_t) | set(old_t)):
        a, b = now_t.get(cls, []), old_t.get(cls, [])
        if len(a) < 8 or len(b) < 8:
            eff.append(f"- {cls}: too few to compare ({len(a)} tasks now, {len(b)} before)")
        else:
            ma, mb = _median(a), _median(b)
            eff.append(f"- {cls}: median {ma / 1000:.0f}k tokens per task ({len(a)} tasks) vs {mb / 1000:.0f}k "
                       f"({len(b)} tasks), {100 * (ma - mb) / mb:+.0f}%")
    pairs = set()
    for _rel, row in Workspace(root).all_items():
        for other in row.get("conflicts") or []:
            pairs.add(tuple(sorted((row["id"], other))))

    def capped(lines: list[str], n: int) -> list[str]:
        return lines[:n] + ([f"- and {len(lines) - n} more"] if len(lines) > n else [])

    week = _iso_week(now)
    out = [f"# Learning digest {week}"]
    out += ["Learned:"] + (capped([f"- {l}" for l in learned], 3) or ["- nothing new"])
    out += ["Retired:"] + (capped([f"- {l}" for l in retired], 2) or ["- nothing"])
    out += ["Efficiency (tokens per recorded task, this period vs previous four weeks):"] + (capped(eff, 3) or ["- no recorded tasks"])
    out += ["Unsure:"] + (capped([f"- {a} conflicts with {b}" for a, b in sorted(pairs)], 2) or ["- nothing"])
    return f"learning/digest/{week}.md", "\n".join(out[:15]) + "\n"


# ---------------------------------------------------------------- verify
def _git(root: Path, *args: str) -> tuple[int, bytes]:
    try:
        p = subprocess.run(["git", *args], cwd=str(root), capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return 1, b""
    return p.returncode, p.stdout


def default_base(root: Path) -> str:
    return "origin/main" if _git(root, "rev-parse", "--verify", "--quiet", "origin/main")[0] == 0 else "HEAD"


ZONE_DIRS = ("memory", "owner", "stats", "playbooks", "learning")


def _tree_files(root: Path) -> dict[str, bytes]:
    out = {}
    for d in ZONE_DIRS:
        for p in sorted((root / d).rglob("*")) if (root / d).is_dir() else []:
            rel = p.relative_to(root).as_posix()
            # Kernel files are hand-written and state files are rewritten by their
            # own script (the radar); neither is produced by deltas.
            if p.is_file() and not p.name.startswith(".tmp-") and zone_of(rel) not in ("kernel", "state"):
                out[rel] = p.read_bytes()
    return out


def _append_only(rel: str) -> bool:
    return zone_of(rel) == "inbox" or rel.startswith("learning/digest/")


def _one_session(data: bytes) -> str:
    """The single session every line of an inbox file belongs to, or ""
    when a line is not a valid record or two sessions are mixed."""
    sessions = set()
    for line in data.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            return ""
        if not isinstance(rec, dict) or rec.get("kind") not in KINDS or not isinstance(rec.get("session"), str) \
                or not rec["session"] or not isinstance(rec.get("at"), str):
            return ""
        sessions.add(rec["session"])
    return sessions.pop() if len(sessions) == 1 else ""


def _session_rewrite_ok(rel: str, head: bytes, base: bytes, handled: set[str]) -> bool:
    """``close`` and the Stop hook replace a session's records in its own
    inbox file until that file is consolidated (S14). Such a rewrite is
    allowed only for an inbox file not yet marked handled whose old and new
    lines are all valid records of one and the same session."""
    if zone_of(rel) != "inbox" or rel in handled:
        return False
    sid = _one_session(head)
    return bool(sid) and _one_session(base) == sid


def verify(brain_root: Path | None = None, base: str | None = None) -> tuple[bool, list[str]]:
    """Replay the deltas added since ``base`` on the base files and compare."""
    root = Path(brain_root or c.BRAIN_ROOT)
    if _git(root, "rev-parse", "--git-dir")[0] != 0:
        return False, ["learn verify: not a git repository"]
    base = base or default_base(root)
    code, listing = _git(root, "ls-tree", "-r", "-z", "--name-only", base, "--", *ZONE_DIRS)
    if code != 0:
        return False, [f"learn verify: cannot read base {base}"]
    tmp = Path(tempfile.mkdtemp(prefix="brain-verify-"))
    try:
        for rel in [x for x in listing.decode("utf-8").split("\0") if x]:
            ok, data = _git(root, "show", f"{base}:{rel}")
            if ok == 0:
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_bytes(data)
        base_ids = {r.get("id") for r in manifest_rows(tmp)}
        new = [r.get("id") for r in manifest_rows(root) if r.get("id") not in base_ids]
        problems = []
        for did in new:
            delta = c.read_json(root / "learning" / "deltas" / f"{did}.json")
            if not isinstance(delta, dict):
                problems.append(f"learning/deltas/{did}.json: missing or unreadable")
                break
            ok, lines = apply_delta(delta, tmp)
            if not ok:
                problems.append(f"delta {did} is refused on replay: {lines[0]}")
                break
        if not problems:
            head, replay = _tree_files(root), _tree_files(tmp)
            handled = consumed_inbox(root)
            for rel in sorted(set(head) | set(replay)):
                h, r = head.get(rel), replay.get(rel)
                if _append_only(rel):
                    if r is not None and (h is None or not h.startswith(r)) and \
                            not (h is not None and _session_rewrite_ok(rel, h, r, handled)):
                        problems.append(f"{rel}: changed other than by appending")
                elif h != r:
                    problems.append(f"{rel}: {'not produced by any delta' if r is None else 'missing' if h is None else 'differs from the replayed deltas'}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not problems:
        return True, [f"learn verify: {len(new)} delta(s) replayed on {base}; learned zone matches"]
    locked = bool((c.read_json(root / "VERSION.json", {}) or {}).get("learned_zone_locked"))
    if locked:
        return False, [f"learn verify: {len(problems)} learned-zone file(s) do not match the deltas"] + problems[:12]
    return True, ["learn verify: bootstrap period (learned zone not locked); mismatches are warnings only"] + \
        [f"warning: {p}" for p in problems[:12]]


# ---------------------------------------------------------------- cli
def _managed_project(args, root: Path) -> Path | None:
    proj = c.resolve_project(getattr(args, "project", None), root)
    return proj if proj is not None and c.is_managed(proj) else None


def build_note(args, root: Path) -> tuple[dict | None, Path | None, str]:
    """(record, project, "") for ``learn note``, or (None, None, reason). Every
    check runs before anything is written, so a refused text is never stored
    anywhere in the brain: format, owner words (--quote), project names and
    paths (I-05), and evidence that resolves to this session's own records."""
    sid = c.session_id()
    rec = {"kind": "note", "session": sid, "at": c.now_iso(), "text": " ".join((args.text or "").split()),
           "class": list(args.cls or []), "scope": args.scope, "trust": args.trust,
           "evidence": [" ".join(str(e).split()) for e in (args.evidence or [])]}
    if args.signal:
        rec["signal"] = args.signal
    if args.source:
        rec["source"] = args.source
    if any(e.startswith("owner:") for e in rec["evidence"]):
        return None, None, "owner evidence comes only from --quote, checked against the owner's typed turns"
    if args.trust == "owner-stated" and not getattr(args, "quote", None):
        return None, None, "--trust owner-stated needs --quote with the owner's own words from this session"
    probe = dict(rec, evidence=rec["evidence"] + (["owner:turn@x#000000000000"] if getattr(args, "quote", None) else []))
    errs = check_note(probe)
    if errs:
        return None, None, "; ".join(errs)
    project = _managed_project(args, root)
    if args.scope != "project":
        names = known_project_ids(root) + project_words(project)
        if project_specific(rec["text"], names):
            return None, None, "names a path, file or project: record it with --scope project in that project's .brain/"
        if any(project_specific(e, names) for e in rec["evidence"] if not e.startswith("review:")):
            return None, None, "evidence names a path, file or project: name the gate, test or run instead"
    evidence, why = resolve_evidence(rec["evidence"], sid, project, root)
    if why:
        return None, None, why
    if getattr(args, "quote", None):
        owner_ev, why = verify_owner_quote(args.quote, sid)
        if why:
            return None, None, why
        evidence.append(owner_ev)
    rec["evidence"] = evidence
    errs = check_note(rec)
    if errs:
        return None, None, "; ".join(errs)
    return rec, project, ""


def cmd_note(args) -> int:
    root = Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT)
    rec, project, why = build_note(args, root)
    if rec is None:
        print("note refused: " + why)
        return 1
    if args.scope == "project":
        if project is None:
            print("no managed project found (attach one, or run: brain init <path>)")
            return 1
        item = note_item(rec, c.today())
        path = project / ".brain" / "memory" / "lessons.jsonl"
        if any(r.get("id") == item["id"] for r in c.read_jsonl(path)):
            print(f"already recorded as {item['id']}")
            return 0
        bad = I.validate_item(item)
        if bad:
            print("note refused: " + bad[0])
            return 1
        c.append_jsonl(path, item)
        print(f"project lesson {item['id']} recorded as a candidate in .brain/memory/lessons.jsonl")
        return 0
    path = _writable_session_file(root, rec["session"])
    c.append_jsonl(path, with_id(rec))
    print(f"note recorded in the inbox ({path.name}); it is reviewed at the next consolidation")
    return 0


CORRECTION_KINDS = ("sizing", "fact", "quality")


def project_salt(project: Path) -> str:
    """The project's own salt for hashing request words (``.brain/log/salt``),
    created once: hashes are not comparable across projects and no word
    leaves the project in clear (I-05)."""
    import secrets
    path = Path(project) / ".brain" / "log" / "salt"
    salt = c.read_text(path).strip()
    if not re.fullmatch(r"[0-9a-f]{32,128}", salt):
        salt = secrets.token_hex(16)
        c.write_text(path, salt + "\n")
    return salt


def hashed_words(text: str, salt: str) -> list[str]:
    """Sorted distinct salted hashes (12 hex) of a text's content words."""
    return sorted({c.sha256_text(f"{salt}\n{w}")[:12] for w in c.words(text or "")})


def cmd_correction(args) -> int:
    """An owner correction: the strongest learning signal there is (I-07), so
    it needs the owner's own words, verified in the transcript like a note."""
    root = Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT)
    sid = c.session_id()
    if args.kind == "sizing":
        if args.from_tier is None or args.to_tier is None or args.from_tier == args.to_tier:
            print("correction refused: --kind sizing needs --from-tier and a different --to-tier")
            return 2
    elif not args.item:
        print(f"correction refused: --kind {args.kind} needs --item (the id of the corrected item)")
        return 2
    if args.item and not I.ID_RE.match(args.item):
        print(f"correction refused: {args.item!r} is not an item id")
        return 2
    ev, why = verify_owner_quote(args.quote, sid)
    if why:
        print("correction refused: " + why)
        return 1
    rec = {"kind": "correction", "session": sid, "at": c.now_iso(), "correction": args.kind, "evidence": [ev]}
    if args.item:
        rec["item"] = args.item
    if args.kind == "sizing":
        rec["rule_tier"], rec["tier"] = args.from_tier, args.to_tier
        project = _managed_project(args, root)
        if args.request and project is not None:
            rec["words"] = hashed_words(args.request, project_salt(project))
    path = _writable_session_file(root, sid)
    c.append_jsonl(path, with_id(rec))
    print(f"owner correction ({args.kind}) recorded in the inbox ({path.name}); it counts at the next consolidation")
    return 0


def cmd_review(args) -> int:
    """Two independent review passes: record the counts, answer whether to run
    another round (capture-recapture, ``mlearn.review_stop``)."""
    root = Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT)
    sid = c.session_id()
    cls = args.cls or ""
    rnd = args.round
    if rnd is None:
        rnd = 1 + sum(1 for r in pending_session_records(root, sid) if r.get("kind") == "review" and r.get("task_class", "") == cls)
    try:
        ans = mlearn_module().review_stop(args.found_a, args.found_b, args.both, rounds=rnd)
    except (ValueError, ImportError, AttributeError) as e:
        print(f"review refused: {e}")
        return 2
    rec = {"kind": "review", "session": sid, "at": c.now_iso(), "task_class": cls, "round": rnd,
           "found_a": args.found_a, "found_b": args.found_b, "both": args.both}
    c.append_jsonl(_writable_session_file(root, sid), with_id(rec))
    print(f"review round {rnd}: about {max(0.0, ans['estimated_remaining']):g} defect(s) likely remain (a lower bound); "
          f"another round: {'yes' if ans['another_round'] else 'no'}")
    return 0


def cmd_consolidate(args) -> int:
    leads = official_leads(c.BRAIN_ROOT)
    bad_lines, bad_files = inbox_unreadable(c.BRAIN_ROOT)
    if bad_lines:
        print(f"inbox: {bad_lines} unreadable line(s) in {bad_files} file(s) skipped; the valid records are used")
    delta, rejected = build_consolidation(min_sessions=args.min_sessions)
    if delta is None:
        if rejected:
            print("consolidation refused, nothing written: " + rejected[0])
            return 1
        print("nothing to consolidate: the inbox has no pending files")
        return 0
    counts: dict[str, int] = {}
    for op in delta["ops"]:
        counts[op["op"]] = counts.get(op["op"], 0) + 1
    print(f"delta {delta['id']}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for r in rejected[:4]:
        print(f"rejected {r}")
    if len(rejected) > 4:
        print(f"rejected {len(rejected) - 4} more")
    for lead in leads[:2]:
        print(f"lead to confirm at its source: {c.clip(str(lead.get('title', '')), 60)} {lead.get('url', '')}")
    if len(leads) > 2:
        print(f"and {len(leads) - 2} more official lead(s)")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    ok, lines = apply_delta(delta)
    print("\n".join(lines[:6]))
    return 0 if ok else 1


def cmd_apply(args) -> int:
    delta = c.read_json(args.delta)
    if not isinstance(delta, dict):
        print(f"cannot read a delta from {args.delta}")
        return 1
    ok, lines = apply_delta(delta, budget=args.budget)
    print(("" if ok else "refused, nothing changed: ") + "\n".join(lines[:10]))
    return 0 if ok else 1


def cmd_decay(args) -> int:
    delta, stale = build_decay()
    for s in stale[:8]:
        print(s)
    if delta is None:
        print("decay: nothing to demote or retire")
        return 0
    ok, lines = apply_delta(delta)
    print("\n".join(lines[:6]))
    return 0 if ok else 1


def cmd_digest(args) -> int:
    rel, text = build_digest(weeks=args.weeks)
    c.write_text(c.BRAIN_ROOT / rel, text)
    print(text, end="")
    return 0


def cmd_verify(args) -> int:
    ok, lines = verify(base=args.base)
    print("\n".join(lines))
    return 0 if ok else 1


def status_lines(brain_root: Path | None = None) -> list[str]:
    root = Path(brain_root or c.BRAIN_ROOT)
    counts: dict[str, int] = {s: 0 for s in I.STATUS if s != "retired"}
    conflicts = 0
    for _rel, row in Workspace(root).all_items():
        it = I.normalise(row)
        counts[it["status"]] = counts.get(it["status"], 0) + 1
        conflicts += bool(it["conflicts"])
    archived = len(c.read_jsonl(root / ARCHIVE))
    pend = pending_inbox(root)
    recs = sum(len(c.read_jsonl(p)) for p in pend)
    bad_lines, _bad_files = inbox_unreadable(root)
    rows = manifest_rows(root)
    last = rows[-1] if rows else None
    return [
        "items: " + ", ".join(f"{v} {k}" for k, v in counts.items()) + f"; {archived} archived",
        f"items in a conflict: {conflicts}",
        f"inbox: {len(pend)} file(s) pending ({recs} record(s)"
        + (f", {bad_lines} unreadable line(s)" if bad_lines else "")
        + f"); {len(official_leads(root))} unhandled official lead(s)",
        f"last delta: {last['id']} at {last['at']} ({last['ops_count']} op(s))" if last else "last delta: none yet",
        f"deltas applied: {len(rows)}",
    ]


def cmd_status(args) -> int:
    print("\n".join(status_lines()))
    return 0


def register(sub) -> None:
    p = sub.add_parser("learn", help="the learning pipeline (only writer of the learned zone)")
    s = p.add_subparsers(dest="learn_cmd")

    n = s.add_parser("note", help="record a lesson candidate with evidence", description=EVIDENCE_HELP)
    n.add_argument("--text", required=True)
    n.add_argument("--class", dest="cls", action="append", default=[], required=True)
    n.add_argument("--evidence", action="append", default=[],
                   help="gate:<id>, test:<name>, run:<log>, outcome:<id> or review:<file> (repeatable)")
    n.add_argument("--quote", help="the owner's own words from a turn he typed in this session (checked in the transcript)")
    n.add_argument("--scope", default="global")
    n.add_argument("--trust", default="observed", choices=TRUST_NOTE,
                   help="owner-stated needs --quote; external needs --source and must be a fact")
    n.add_argument("--signal", choices=SIGNALS)
    n.add_argument("--source", help="where an external fact comes from")
    c.add_project_arg(n)
    n.set_defaults(func=cmd_note)

    k = s.add_parser("correction", help="record an owner correction (needs --quote of his words)")
    k.add_argument("--kind", required=True, choices=CORRECTION_KINDS)
    k.add_argument("--quote", required=True, help="the owner's own words from a turn he typed in this session")
    k.add_argument("--item", help="id of the corrected memory item (fact, quality)")
    k.add_argument("--from-tier", type=int, choices=(0, 1, 2, 3), help="sizing: the tier the work was given")
    k.add_argument("--to-tier", type=int, choices=(0, 1, 2, 3), help="sizing: the tier the owner says it was")
    k.add_argument("--request", help="sizing: the request text; only salted word hashes are kept, in the project")
    c.add_project_arg(k)
    k.set_defaults(func=cmd_correction)

    r = s.add_parser("review", help="record two review passes and say whether to run another round")
    r.add_argument("--found-a", type=int, required=True, help="defects found by reviewer A")
    r.add_argument("--found-b", type=int, required=True, help="defects found by reviewer B")
    r.add_argument("--both", type=int, required=True, help="defects both found")
    r.add_argument("--class", dest="cls", help="task class reviewed")
    r.add_argument("--round", type=int, help="review round (default: next for this session and class)")
    r.set_defaults(func=cmd_review)

    k = s.add_parser("consolidate", help="turn pending inbox files into one delta and apply it")
    k.add_argument("--dry-run", action="store_true")
    k.add_argument("--min-sessions", type=int, default=2)
    k.set_defaults(func=cmd_consolidate)

    a = s.add_parser("apply", help="apply a delta file (all or nothing)")
    a.add_argument("delta")
    a.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="items allowed per file")
    a.set_defaults(func=cmd_apply)

    s.add_parser("decay", help="demote faded items and retire long-demoted ones; flag stale facts").set_defaults(func=cmd_decay)

    d = s.add_parser("digest", help="write the weekly digest (15 lines at most)")
    d.add_argument("--weeks", type=int, default=1)
    d.set_defaults(func=cmd_digest)

    v = s.add_parser("verify", help="CI: replay recorded deltas on the base and compare")
    v.add_argument("--base", help="git ref (default origin/main, else HEAD)")
    v.set_defaults(func=cmd_verify)

    s.add_parser("status", help="what the brain has learned so far").set_defaults(func=cmd_status)
    p.set_defaults(func=cmd_status)
