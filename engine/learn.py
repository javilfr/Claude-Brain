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
- The owner's authority cannot be claimed by writing a file. A record acts
  as his words only when its quote is found again in a transcript on disk at
  the moment it is consolidated; otherwise it waits for his yes
  (``learn confirm``). Operations on what is his are accepted only in a delta
  this process built after checking his words, never from a delta file, and
  the same rules are applied when CI replays the history (2026-11-10 audit:
  one forged inbox line had become an active owner rule).
- Only what a session's note created fades with disuse or is demoted by
  outcomes, a little per run, and it can be restored. In a simulated year
  the old decay retired half of the shipped knowledge, the rule against
  skipping tests included, with no way back.
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

OPS = ("ADD", "INC_HELPFUL", "INC_HARMFUL", "EDIT_TEXT", "SET_STATUS", "MOVE_SCOPE", "LINK", "UNLINK", "SUPERSEDE",
       "OWNER_CONFIRM", "RESTORE", "REVERIFY", "APPEND_STAT", "ML_FOLD", "MARK_INBOX")
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
PROMOTE_MULTIPLIER = 1.0  # mlearn.item_score needed for probation -> active
DEMOTE_AFTER_DAYS = 90    # fallback when mlearn.retention is unavailable
RETIRE_FURTHER_DAYS = 180  # a demoted lesson is retired this long after its demotion
RETIRE_AFTER_DAYS = DEMOTE_AFTER_DAYS + RETIRE_FURTHER_DAYS  # for demotions recorded before ``demoted_on`` existed
CANDIDATE_GRACE_DAYS = 180  # a candidate nobody was ever shown is not forgotten before this
RETENTION_FLOOR = 0.15    # fallback for memory/ml_config.json retention.threshold
MAX_VOTE_EVIDENCE = 20    # session:/outcome: entries kept per item; the counters hold the totals
EVIDENCE_HEAD = 8         # an item's first entries (what the note brought) are always kept
HARM_MIN_USES = 8         # demotion from outcomes needs this many followed uses,
HARM_MIN_WEEKS = 3        # harm in this many different weeks,
HARM_Z = 1.2816           # and a lower bound (10th percentile) on the harm share above one half
NEAR_SHOW = 0.3           # word overlap from which ``learn note`` shows an existing item as close
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
                     "[Subagent hand-back]", "<task-notification>", "<system-reminder",
                     "This session is being continued from a previous conversation")
# Row flags the client sets on text the owner did not type: injected context,
# helper conversations, and the summary a compaction writes in his voice.
NOT_TYPED_FLAGS = ("isMeta", "isSidechain", "isCompactSummary", "isVisibleInTranscriptOnly")
PROOF_KEYS = ("session", "turn", "start", "len", "sha")
# Deltas built in this process by a command that verified the owner's words
# (by the hash of their ops). Only these, and the replay in ``verify``, may
# carry owner-level operations; a delta read from a file never can.
_TRUSTED: set[str] = set()
# "stop" forbids only before a gerund ("stop pushing"); "stop and ask" tells you to ask.
NEGATIVE_RE = re.compile(r"\b(never|don't|do not|must not|should not|shouldn't|avoid|no longer|cannot|can't|"
                         r"stop\s+\w+ing|nunca|no\s+se\s+debe)\b", re.I)
# Where a subordinate clause starts: polarity is read from the main clause, so
# "run it twice because the cache cannot be trusted" is not a prohibition.
CLAUSE_SPLIT_RE = re.compile(r"[,;:.]\s+|\s+(?:because|since|so that|so|when|whenever|if|unless|until|before|after|"
                             r"while|although|though|to avoid|in case)\b", re.I)
SUBORDINATE_START = frozenset("because since so when whenever if unless until before after while although though once "
                              "for on in during with without".split())
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
# The looser test (learning-10): the whitelist above refused a quarter of the
# brain's own seed lessons. A clause that opens with one of these words, or is
# a noun phrase tied to a copula or a past tense, describes; anything else
# that opens a clause is taken as an instruction or a norm.
DESCRIBES_START = frozenset(
    "it its there here is are was were be been being am has have had we i you he she they what which who why how "
    "yesterday today and but or so because then also".split())
DETERMINER_START = frozenset("a an the this that these those my our your his her their some many most several few".split())
COPULA = frozenset("is are was were be been am has have had seems seemed looks looked became becomes "
                   "es son era fue fueron está están".split())
PAST_IRREGULAR = frozenset("broke went took came got saw fell lost ran found made gave kept had did said".split())
SPANISH_CUE_RE = re.compile(r"\b(siempre|nunca|antes de|después de|hay que|debe[ns]?|no\s+\w+(?:es|as|en|an)\b)", re.I)
# File names that belong to the platform or to every project of a kind, not to
# one project: naming them does not make a lesson project-specific (learning-07).
GENERIC_FILES = frozenset(
    "claude.md skill.md agents.md readme.md settings.json .mcp.json package.json package-lock.json pyproject.toml "
    "requirements.txt tsconfig.json state.md status.md needs_you.md plan.md decisions.md handover.md project.json".split())
NUMBER_WORDS = frozenset(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand million billion half "
    "once twice double triple uno dos tres cuatro cinco seis siete ocho nueve diez cien mil".split())
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


def shown_ids(project: Path | None, sid: str) -> set[str]:
    """Ids recall showed this session, from the project's injection log
    (``.brain/log/recall.jsonl``): the proof a ``used`` record needs before a
    candidate can be credited (learning-02)."""
    if project is None:
        return set()
    out: set[str] = set()
    for row in c.read_jsonl(Path(project) / ".brain" / "log" / "recall.jsonl"):
        if str(row.get("session", "")) == sid and isinstance(row.get("ids"), list):
            out.update(str(i) for i in row["ids"])
    return out


def project_votes(project: Path, sid: str, records: list[dict]) -> list[dict]:
    """Apply this session's ``used`` records for lessons that live in the
    project's own ``.brain/memory/`` to those files, and return the records
    that still go to the brain (learning-03). A project lesson never leaves
    its project, so its credit is kept there too: the same rules as in the
    brain (credit from this session's outcomes, only when recall showed it,
    one vote per session), probation to active on two supporting sessions,
    and demotion only on the lower-bound case."""
    files: dict[Path, list[dict]] = {}
    frozen: set[Path] = set()  # a file with an unreadable line is never rewritten: that would drop the line
    for p in I.project_item_files(project):
        try:
            files[p], bad = c.read_jsonl_counted(p)
        except OSError:
            continue
        if bad:
            frozen.add(p)
    where = {str(r.get("id")): (p, r) for p, rows in files.items() for r in rows}
    mine = [r for r in records if r.get("kind") == "outcome"]
    good = bool(mine) and all(o.get("passed") is True and o.get("first_pass", True) is True for o in mine)
    bad = any(o.get("passed") is False for o in mine)
    keep, changed = [], set()
    day = c.today()
    for rec in records:
        hit = where.get(str(rec.get("item"))) if rec.get("kind") == "used" else None
        if hit is None:
            keep.append(rec)
            continue
        path, row = hit
        voted = [v for v in row.get("voted") or [] if isinstance(v, str)]
        if path in frozen or rec.get("shown") is not True or sid in voted:
            continue  # not shown this session, or this session already counted
        row["last_used"] = day
        row["voted"] = (voted + [sid])[-MAX_VOTE_EVIDENCE:]
        changed.add(path)
        if rec.get("followed") is not True:
            continue
        row["uses"] = int(row.get("uses", 0) or 0) + 1
        if good:
            row["helpful"] = int(row.get("helpful", 0) or 0) + 1
            row["sessions"] = int(row.get("sessions", 0) or 0) + 1
        elif bad:
            row["harmful"] = int(row.get("harmful", 0) or 0) + 1
            week = _iso_week(c.now())
            weeks = [w for w in row.get("harm_weeks") or [] if isinstance(w, str)]
            row["harm_weeks"] = (weeks + [week] if week not in weeks else weeks)[-8:]
        it = I.normalise(row)
        if it["status"] in ("candidate", "probation", "active") and harm_case(it):
            row["status"] = "demoted"
        elif it["status"] == "candidate" and it["helpful"] >= 1:
            row["status"] = "probation"
        elif it["status"] == "probation" and it["sessions"] >= 2:
            row["status"] = "active"
    for path in changed:
        c.write_jsonl(path, files[path])
    return keep


def replace_session_records(root: Path, sid: str, records: list[dict], kinds: tuple[str, ...],
                            project: Path | None = None) -> Path | None:
    """Put ``records`` in the session's inbox file, replacing earlier records
    of the same kinds from this session. Returns None (writes nothing) when a
    consolidated file already holds such records: counting twice is worse
    than missing the tail of a session.

    Each ``used`` record is marked ``shown`` true or false from the project's
    injection log, here and not by the caller's word. ``project`` defaults to
    the project the commands resolve (``common.resolve_project``)."""
    root = Path(root)
    if any(r.get("kind") == "used" for r in records):
        if project is None:
            project = c.resolve_project(None, root)
        managed = project is not None and c.is_managed(Path(project))
        shown = shown_ids(Path(project), sid) if managed else set()
        records = [{**r, "shown": str(r.get("item", "")) in shown} if r.get("kind") == "used" and managed else r
                   for r in records]
        if managed:
            records = project_votes(Path(project), sid, records)
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


def _clause_words(clause: str) -> list[str]:
    return [w for w in (x.lower().strip(".,:;!?\"'()`") for x in clause.split()) if w]


def _clause_tells(clause: str) -> bool:
    """True when one clause reads as an instruction or a norm."""
    ws = _clause_words(clause)
    if not ws:
        return False
    if ws[0] in IMPERATIVE_START or IMPERATIVE_RE.search(clause) or SPANISH_CUE_RE.search(clause):
        return True
    if ws[0] in DESCRIBES_START or ws[0] in CONDITION_START or len(ws) < 2:
        return False
    # After "the", "a", "this" a description is likelier, so look further.
    wide = ws[0] in DETERMINER_START
    if any(w in COPULA for w in ws[1:6 if wide else 5]):
        return False  # "Builds are slow on Mondays"
    return not any(w in PAST_IRREGULAR or re.fullmatch(r"[a-záéíóúñ]{2,}ed", w)
                   for w in ws[1:4 if wide else 2])  # "Tests failed twice"


def actionable(text: str) -> bool:
    """A lesson must tell a future session what to do. It does when one of its
    clauses opens with a verb or states a norm ("Helpers write their detail
    to a file"), or carries a cue (should, must, never, siempre, hay que).
    A plain observation ("The build was slow on Tuesday") does not."""
    if is_imperative(text):
        return True
    ws = _clause_words(text)
    if ws and ws[0] in CONDITION_START and any(w in IMPERATIVE_START for w in ws[1:]):
        return True
    return any(_clause_tells(part) for part in re.split(r"[,;:.]\s+|\s+[-–—]\s+", text))


def known_project_ids(root: Path) -> list[str]:
    return [l.strip() for l in c.read_text(Path(root) / KNOWN_IDS).splitlines() if l.strip() and not l.startswith("#")]


def project_specific(text: str, ids: list[str]) -> bool:
    """True when the text names a path, a file or a known project: such a
    lesson belongs in that project's .brain/, not in the shared brain (I-05).
    Platform and ecosystem file names (CLAUDE.md, package.json) are not one
    project's, so they do not count."""
    plain = " ".join(w for w in text.split() if w.lower().strip(".,:;!?\"'()`") not in GENERIC_FILES)
    if PATH_RE.search(plain):
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


def owner_turns(transcript: Path | str, sid: str | None = None) -> list[tuple[str, str]]:
    """(timestamp, text) of every turn the owner typed in a transcript.

    A ``user`` row counts only when its content is a string or text blocks
    (not a tool result), it carries none of the flags of injected text
    (``NOT_TYPED_FLAGS``: a compaction summary is written in his voice but is
    not his), it belongs to this session when ``sid`` is given, and its
    ``origin`` says a human typed it. Rows without ``origin`` are accepted
    only in a transcript where no user row has one (an older client), and
    never when they hold a marker of harness or agent text."""
    rows: list[tuple[str, str, object]] = []
    any_origin = False
    for row in c.iter_jsonl_stream(transcript):
        if row.get("type") != "user":
            continue
        any_origin = any_origin or "origin" in row
        if any(row.get(k) for k in NOT_TYPED_FLAGS):
            continue
        if sid and isinstance(row.get("sessionId"), str) and row["sessionId"] != sid:
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
        rows.append((str(row.get("timestamp") or "unknown"), text, row.get("origin")))
    if any_origin:
        rows = [r for r in rows if isinstance(r[2], dict) and r[2].get("kind") == "human"]
    return [(ts, text) for ts, text, _origin in rows]


def owner_proof(quote: str, sid: str | None = None, whole_line: bool = False) -> tuple[dict | None, str]:
    """(proof, "") when ``quote`` occurs in a turn the owner typed in this
    session's transcript, else (None, one-line reason). The proof says which
    turn and where in it, plus a hash of the quote: enough for a script to
    check it again later, never the words themselves. ``whole_line`` also
    accepts a short reply ("no 2") when it is a whole line of what he typed."""
    q = norm_quote(quote or "")
    sid = sid or c.session_id()
    short = len(q) < MIN_QUOTE
    if short and not (whole_line and len(q) >= 2):
        return None, f"--quote must hold at least {MIN_QUOTE} characters of the owner's own words"
    main, _subs = c.transcript_paths(sid)
    if main is None or not Path(main).is_file():
        return None, "no transcript of this session is on disk, so the owner's words cannot be checked"
    for ts, text in owner_turns(main, sid):
        norm = norm_quote(text)
        if short and q not in [norm_quote(line) for line in text.splitlines()]:
            continue
        start = norm.find(q)
        if start >= 0:
            return {"session": sid, "turn": ts, "start": start, "len": len(q), "sha": c.sha256_text(q)[:12]}, ""
    return None, "the quote is not in any turn the owner typed in this session"


def proof_evidence(proof: dict) -> str:
    return f"owner:turn@{proof['turn']}#{proof['sha']}"


def proof_ok(proof) -> bool:
    """A proof of the right shape whose evidence string is well formed."""
    return isinstance(proof, dict) and all(k in proof for k in PROOF_KEYS) \
        and all(isinstance(proof[k], str) and proof[k] for k in ("session", "turn", "sha")) \
        and all(isinstance(proof[k], int) and not isinstance(proof[k], bool) and proof[k] >= 0 for k in ("start", "len")) \
        and bool(OWNER_EV_RE.match(proof_evidence(proof)))


def reverify_owner(rec: dict) -> bool | None:
    """Check a record's owner proof against the transcript again.

    True: the transcript of the record's session is on disk and a turn the
    owner typed at that time holds, at that place, text with that hash.
    False: the transcript is on disk and says otherwise, or the record has no
    usable proof. None: no transcript on disk, so nothing can be said. Only
    True lets a record act with the owner's authority (learning-01)."""
    proof = rec.get("proof")
    ev = rec.get("evidence")
    if not proof_ok(proof) or proof["session"] != rec.get("session") or not isinstance(ev, list) \
            or proof_evidence(proof) not in ev or proof["len"] < MIN_QUOTE:
        return False
    main, _subs = c.transcript_paths(proof["session"])
    if main is None or not Path(main).is_file():
        return None
    for ts, text in owner_turns(main, proof["session"]):
        if ts == proof["turn"]:
            span = norm_quote(text)[proof["start"]:proof["start"] + proof["len"]]
            if len(span) == proof["len"] and c.sha256_text(span)[:12] == proof["sha"]:
                return True
    return False


def verify_owner_quote(quote: str, sid: str | None = None) -> tuple[str, str]:
    """(evidence, "") when ``quote`` occurs in a turn the owner typed in this
    session's transcript, else ("", one-line reason). The evidence names the
    turn and a hash of the quote, never the quote itself."""
    proof, why = owner_proof(quote, sid)
    return (proof_evidence(proof), "") if proof else ("", why)


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


def main_clause(text: str) -> str:
    """The clause that carries the instruction: the first one that does not
    open with a subordinating word ("Before a release, run the gate" -> "run
    the gate")."""
    parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(text) if p and p.strip()]
    for part in parts:
        if (_clause_words(part) or [""])[0] not in SUBORDINATE_START:
            return part
    return parts[0] if parts else text


def negative(text: str) -> bool:
    """Whether a lesson forbids. Read from its main clause only, so a reason
    ("because the cache cannot be trusted") does not flip it (learning-14)."""
    return bool(NEGATIVE_RE.search(main_clause(text)))


def fact_keys(text: str) -> set[str]:
    """The numbers and identifiers a fact states. Two facts about the same
    subject with different keys disagree; with the same keys they are one
    fact read twice (learning-07)."""
    keys = set(re.findall(r"\d+(?:[.,]\d+)*", text))
    for raw in text.split():
        w = raw.strip(".,:;!?\"'()").lower()
        if w in NUMBER_WORDS or w.startswith(("--", "`")) or re.search(r"[a-z0-9][_/][a-z0-9]|[a-z]\.[a-z]", w):
            keys.add(w.strip("`"))
    return keys


def says_the_same(a: str, b: str, fact: bool) -> bool:
    """Two texts about the same subject agree: the same polarity and, for
    facts, the same numbers and names."""
    return negative(a) == negative(b) and (not fact or fact_keys(a) == fact_keys(b))


def learned(row: dict) -> bool:
    """True for a rule or pitfall a session's note created. Only these fade
    with disuse or are demoted by outcomes; shipped knowledge (seed, derived,
    the owner's) and facts are not judged that way (redteam-01, redteam-11)."""
    return str(row.get("provenance") or "").startswith("note:") and row.get("trust") == "observed" \
        and row.get("type") in ("rule", "pitfall")


def owner_level(rel: str | None, row: dict) -> bool:
    """What only the owner may change: anything he stated, his standing
    instructions, and every item under owner/ (I-08)."""
    return row.get("trust") == "owner-stated" or row.get("type") == "standing" or str(rel or "").startswith("owner/")


def harm_lower_bound(harmful: int, uses: int) -> float:
    """Wilson lower bound (10th percentile) of the share of followed uses that
    ended in a failed session."""
    if uses <= 0:
        return 0.0
    p, z2 = harmful / uses, HARM_Z * HARM_Z
    centre = p + z2 / (2 * uses)
    margin = HARM_Z * ((p * (1 - p) / uses + z2 / (4 * uses * uses)) ** 0.5)
    return (centre - margin) / (1 + z2 / uses)


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
    applied here first; nothing reaches disk unless the whole delta passes.

    ``owner_ok`` says whether this delta may carry owner-level operations: it
    is true only for a delta built in this process by a command that verified
    the owner's words, and for the replay in ``verify``."""

    def __init__(self, root: Path, owner_ok: bool = False):
        self.root = Path(root)
        self.owner_ok = owner_ok
        self.rows: dict[str, list[dict]] = {}
        self.orig: dict[str, str] = {}
        self.text: dict[str, str] = {}
        self.touched: set[str] = set()
        self.changed_ids: set[str] = set()
        self.retired: dict[str, int] = {}
        self.inbox_files: list[str] = []
        self.notes: list[str] = []
        self.owner_notes: list[str] = []   # what now counts as his words, or waits for them: printed first
        self.helped: set[str] = set()      # items that got a helpful vote in this delta
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

    def archived(self, iid: str) -> dict | None:
        """The newest archive row of a retired item, or None."""
        hits = [r for r in map(_loads, self._get_text(ARCHIVE).splitlines()) if r and r.get("id") == iid]
        return hits[-1] if hits else None

    def live_count(self, rel: str) -> int:
        """Items of a file that count against its budget: all but the demoted."""
        return sum(1 for r in self.rows.get(rel, []) if r.get("status", "active") != "demoted")

    def live_conflicts(self, row: dict, day: str) -> list[str]:
        """The item's conflicts that still stand: a link to an item that was
        demoted, retired or superseded no longer blocks anything."""
        out = []
        for other in row.get("conflicts") or []:
            _rel, o = self.find(str(other))
            if o is not None and _live(o, day):
                out.append(str(other))
        return out

    # -- the promotion rules, per operation
    def authorised(self, op: dict) -> bool:
        return self.owner_ok and proof_ok(op.get("owner"))

    def rule_problem(self, op: dict) -> str:
        """Why the promotion rules refuse this operation; "" when they allow it.

        A delta nobody verified (``learn apply`` on a file) may add only
        candidates with trust observed or external, and may not edit, move,
        link, supersede, restore or change the status of anything that is the
        owner's. Owner-level operations carry an ``owner`` proof and are
        accepted only in a delta this process built after checking his words,
        and in the replay of such a delta (redteam-04)."""
        kind = op.get("op")
        auth = self.authorised(op)
        if "owner" in op and not auth:
            return (f"{kind}: owner-level changes come only from a command that checked the owner's words "
                    "(brain learn confirm or reject with --quote), never from a delta file")

        def owned(iid) -> str:
            rel, row = self.find(str(iid))
            return str(iid) if row is not None and owner_level(rel, row) else ""

        theirs = "is the owner's: only brain learn confirm or reject with --quote \"<his words>\" can change it"
        if kind == "ADD":
            item = op.get("item")
            if not isinstance(item, dict):
                return ""
            it = I.normalise(item)
            rel = str(op.get("file", ""))
            if plain_path_problem(rel) or not ITEM_FILE_RE.match(rel):
                return ""  # not an item file at all: refused as such below
            if auth:
                return "" if proof_evidence(op["owner"]) in it["evidence"] else \
                    f"ADD: {it.get('id')}: the owner proof does not match the item's evidence"
            if it["status"] != "candidate" or it["trust"] not in ("observed", "external") \
                    or it["type"] in ("standing", "preference") or rel.startswith("owner/"):
                return (f"ADD: {it.get('id')} must enter as a candidate with trust observed or external, outside owner/ "
                        f"(it is {it['status']}, {it['trust']}, {it['type']}); the owner's words enter through "
                        "brain learn note --quote")
            # A new item starts from nothing: credit, sessions and rank are
            # earned afterwards, and it is a lesson from a note like any other.
            if any(it[k] for k in ("helpful", "harmful", "uses")) or it["sessions"] not in (0, 1) \
                    or it["importance"] > 2 or it["supersedes"] or not str(it["provenance"]).startswith("note:"):
                return (f"ADD: {it.get('id')} must start as a note does: provenance note:<session>, no votes or uses, "
                        "at most one session, importance 1 or 2, superseding nothing")
            return ""
        if kind == "OWNER_CONFIRM":
            return "" if auth else "OWNER_CONFIRM: needs the owner's words, checked by brain learn confirm --quote"
        if kind == "INC_HARMFUL":
            hit = owned(op.get("id"))
            return f"INC_HARMFUL: {hit} is the owner's; harm votes never lower what he said (I-08)" if hit else ""
        if auth:
            return ""
        if kind == "RESTORE":
            rel, row = self.find(str(op.get("id", "")))
            if row is None:
                row = self.archived(str(op.get("id", "")))
                rel = (row or {}).get("retired_from")
            if row is not None and (owner_level(rel, row) or row.get("corrected")):
                return (f"RESTORE: {row.get('id')} is the owner's, or he withdrew it; bringing it back needs his words: "
                        "add --quote \"<his words>\"")
        if kind in ("EDIT_TEXT", "MOVE_SCOPE", "SET_STATUS"):
            hit = owned(op.get("id"))
            if hit:
                return f"{kind}: {hit} {theirs}"
        if kind in ("LINK", "UNLINK"):
            hit = owned(op.get("a")) or owned(op.get("b"))
            if hit:
                return f"{kind}: {hit} {theirs}"
        if kind == "SUPERSEDE":
            _rel, old = self.find(str(op.get("old", "")))
            hit = owned(op.get("new")) or (owned(op.get("old")) if old is not None and old.get("trust") != "owner-stated" else "")
            if hit:
                return f"SUPERSEDE: {hit} {theirs}"
        if kind == "SET_STATUS":
            _rel, row = self.find(str(op.get("id", "")))
            status = op.get("status")
            if row is not None and status in I.STATUS:
                old = row.get("status", "active")
                iid = row.get("id")
                if row.get("awaiting_owner") and status in ("probation", "active"):
                    return (f"SET_STATUS: {iid} is waiting for the owner; only brain learn confirm {iid} "
                            "--quote \"<his words>\" can put it to use")
                if old == "demoted" and status in ("candidate", "probation", "active"):
                    return f"SET_STATUS: {iid} is demoted; bring it back with: brain learn restore {iid} --reason \"<why>\""
                if status == "active" and old not in ("probation", "active"):
                    return f"SET_STATUS: {iid} can become active only from probation (it is {old})"
        return ""

    # -- ops
    def apply_op(self, op: dict, at: str) -> str:
        """Apply one op; returns an error string, or "" on success."""
        kind = op.get("op")
        day = at[:10]
        broken = self.rule_problem(op)
        if broken:
            return "promotion rules: " + broken
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
            if item.get("awaiting_owner"):
                self.owner_notes.append(f"waiting for the owner, not in use: {item['id']}: {c.clip(item['text'], 90)}")
            elif item.get("trust") == "owner-stated":
                self.owner_notes.append(f"recorded as the owner's words: {item['id']}: {c.clip(item['text'], 90)}")
            else:
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
            if not op.get("seen"):  # shown by recall but not followed refreshes the date only
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
            row["evidence"] = _capped_evidence(ev)
            if field == "helpful" and n > 0:
                self.helped.add(row["id"])
            if field == "harmful" and n > 0:
                weeks = [w for w in row.get("harm_weeks") or [] if isinstance(w, str)]
                week = _iso_week(_dt.date.fromisoformat(day))
                row["harm_weeks"] = (weeks + [week] if week not in weeks else weeks)[-8:]
                if op.get("correction"):
                    row["corrected"] = day
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
            return self._set_status(str(op.get("id", "")), op.get("status"), day, by_owner=self.authorised(op))
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
            self.notes.append(f"{a['id']} and {b['id']} disagree; neither is promoted until the owner settles it "
                              f"(brain learn confirm <the one he means> --quote)"
                              if rel_kind == "conflicts" else f"{a['id']} supersedes {b['id']}")
            return ""
        if kind == "UNLINK":
            ida, idb = str(op.get("a", "")), str(op.get("b", ""))
            found = [(rel, row, other) for (rel, row), other in ((self.find(ida), idb), (self.find(idb), ida))
                     if row is not None]
            if not found:
                return f"UNLINK: unknown items {ida} and {idb}"
            for rel, row, other in found:
                if other in (row.get("conflicts") or []):
                    row["conflicts"] = [x for x in row["conflicts"] if x != other]
                    self._touch_item(rel, row["id"])
            self.notes.append(f"{ida} and {idb}: conflict cleared")
            return ""
        if kind == "SUPERSEDE":
            return self._supersede(str(op.get("old", "")), str(op.get("new", "")), day)
        if kind == "OWNER_CONFIRM":
            rel, row = self.find(str(op.get("id", "")))
            if row is None:
                return f"OWNER_CONFIRM: unknown item {op.get('id')}"
            old = row.get("status", "active")
            row.update(trust="owner-stated", status="active")
            for gone in ("awaiting_owner", "demoted_on", "corrected"):
                row.pop(gone, None)
            ev = list(row.get("evidence") or [])
            if proof_ok(op.get("owner")) and proof_evidence(op["owner"]) not in ev:
                ev.append(proof_evidence(op["owner"]))
            row["evidence"] = ev
            self._touch_item(rel, row["id"])
            self.owner_notes.append(f"recorded as the owner's words ({old} -> active): {row['id']}: "
                                    f"{c.clip(str(row.get('text', '')), 90)}")
            return ""
        if kind == "RESTORE":
            return self._restore(str(op.get("id", "")), op.get("reason"), day)
        if kind == "REVERIFY":
            rel, row = self.find(str(op.get("id", "")))
            if row is None:
                return f"REVERIFY: unknown item {op.get('id')}"
            if row.get("type") != "fact":
                return f"REVERIFY: {row['id']} is not a fact"
            row["verified_on"] = day
            sid = op.get("session")
            ev = list(row.get("evidence") or [])
            if sid and f"session:{sid}" not in ev:  # a second session read the same thing at the source
                ev.append(f"session:{sid}")
                row["sessions"] = int(row.get("sessions", 0) or 0) + 1
                row["evidence"] = _capped_evidence(ev)
            self._touch_item(rel, row["id"])
            self.notes.append(f"{row['id']}: re-verified on {day}")
            return ""
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

    def _set_status(self, iid: str, status, day: str, by_owner: bool = False) -> str:
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
            if status == "demoted":
                row["demoted_on"] = day  # retirement counts from here, not from the last use
                if by_owner:
                    row["corrected"] = day  # he withdrew it: no vote revives it, only his words
            else:
                row.pop("demoted_on", None)
            self._touch_item(rel, iid)
        self.notes.append(f"{iid}: {old} -> {status}")
        return ""

    def _restore(self, iid: str, reason, day: str) -> str:
        """Bring a demoted or retired item back (redteam-01, learning-06). A
        learned lesson returns on probation and earns its way up again;
        shipped knowledge returns as it was. Nothing is removed from the
        archive: it is the history."""
        if not isinstance(reason, str) or len(reason.split()) < 2:
            return f"RESTORE: {iid} needs a reason of a few words"
        rel, row = self.find(iid)
        if row is not None:
            old = row.get("status", "active")
            if old != "demoted":
                return f"RESTORE: {iid} is {old}, not demoted or retired"
        else:
            arch = self.archived(iid)
            if arch is None:
                return f"RESTORE: unknown item {iid}"
            rel = str(arch.get("retired_from", ""))
            if plain_path_problem(rel) or not ITEM_FILE_RE.match(rel):
                return f"RESTORE: {iid} has no item file to return to"
            old = "retired"
            row = {k: v for k, v in arch.items() if k not in ("retired_on", "retired_from")}
            self._load_items(rel)
            self.rows[rel].append(row)
        row["status"] = "candidate" if row.get("awaiting_owner") else "probation" if learned(row) else "active"
        for gone in ("demoted_on", "corrected", "harm_weeks"):
            row.pop(gone, None)
        row["last_used"] = day  # the forgetting curve starts again from the restore
        self._touch_item(rel, iid)
        self.notes.append(f"{iid}: restored ({old} -> {row['status']}): {c.clip(' '.join(reason.split()), 120)}")
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
                if self.live_count(rel) > budget:
                    errs.append(f"{rel}: {self.live_count(rel)} items exceeds the budget of {budget}; run: brain learn decay")
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
        lines = self.owner_notes + self.notes
        if any(self.votes):
            lines.append(f"{self.votes[0]} helpful and {self.votes[1]} harmful vote(s) recorded")
        if self.counts["APPEND_STAT"]:
            lines.append(f"{self.counts['APPEND_STAT']} ledger row(s) recorded")
        if self.counts["ML_FOLD"]:
            lines.append(f"{self.counts['ML_FOLD']} record(s) folded into the learning statistics")
        if self.inbox_files:
            lines.append(f"{len(self.inbox_files)} inbox file(s) consolidated")
        return lines


def _loads(line: str) -> dict | None:
    try:
        row = json.loads(line)
    except json.JSONDecodeError:
        return None
    return row if isinstance(row, dict) else None


def _capped_evidence(ev: list) -> list:
    """An item's evidence with its vote trail bounded: the first entries (what
    the note brought) stay, and of the session:/outcome: entries added by
    later votes only the newest are kept. The counters hold the totals, so a
    row stays small however often its item is followed (learning-09)."""
    head, tail = ev[:EVIDENCE_HEAD], ev[EVIDENCE_HEAD:]
    votes = [e for e in tail if str(e).startswith(("session:", "outcome:"))]
    drop = set(votes[:-MAX_VOTE_EVIDENCE]) if len(votes) > MAX_VOTE_EVIDENCE else set()
    return head + [e for e in tail if e not in drop]


def _iso_week(d) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


# ---------------------------------------------------------------- deltas
def ops_hash(ops: list[dict]) -> str:
    return c.sha256_text(json.dumps(ops, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def make_delta(ops: list[dict], at: str | None = None) -> dict:
    at = at or c.now_iso()
    return {"id": f"d-{at[:10].replace('-', '')}-{ops_hash(ops)[:10]}", "at": at, "ops": ops}


def trusted_delta(ops: list[dict], at: str | None = None) -> dict:
    """A delta built by a command of this process that checked the owner's
    words. Only such a delta may carry owner-level operations: the mark lives
    in this process, so a file handed to ``learn apply`` can never have it."""
    _TRUSTED.add(ops_hash(ops))
    return make_delta(ops, at)


def canonical(delta: dict) -> str:
    return json.dumps(delta, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def apply_delta(delta: dict, brain_root: Path | None = None, budget: int = DEFAULT_BUDGET,
                replay: bool = False) -> tuple[bool, list[str]]:
    """Validate the whole delta in memory, then write. Returns (ok, lines).
    ``replay`` is for ``verify``: a recorded delta is replayed with the same
    rules, and its owner-level operations must carry a well-formed proof."""
    root = Path(brain_root or c.BRAIN_ROOT)
    ops = delta.get("ops")
    did, at = str(delta.get("id", "")), str(delta.get("at", ""))
    if not isinstance(ops, list) or not ops or not all(isinstance(o, dict) for o in ops):
        return False, ["delta has no list of operations"]
    if not re.match(r"^[a-z0-9][a-z0-9-]{2,80}$", did) or not re.match(r"^\d{4}-\d{2}-\d{2}T", at):
        return False, ["delta needs an id (lower-case, digits, dashes) and an ISO 'at' time"]
    if any(r.get("id") == did for r in manifest_rows(root)):
        return True, [f"delta {did} was already applied; nothing changed"]
    ws = Workspace(root, owner_ok=replay or ops_hash(ops) in _TRUSTED)
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


def harm_case(it: dict) -> bool:
    """The lower-bound case that demotes a learned lesson on outcomes alone:
    enough followed uses, harm in several different weeks, and a harm share
    whose 10th percentile is above one half. Three red sessions in a row are
    usually one outside cause (a registry down), not three verdicts (redteam-11)."""
    weeks = [w for w in it.get("harm_weeks") or [] if isinstance(w, str)]
    return it["uses"] >= HARM_MIN_USES and len(set(weeks)) >= HARM_MIN_WEEKS \
        and harm_lower_bound(it["harmful"], it["uses"]) > 0.5


def _transitions(ws: Workspace, at: str, min_sessions: int) -> list[dict]:
    """Status moves earned by evidence, applied to ``ws`` and returned as ops.

    probation -> active needs two independent keys: support from at least
    ``min_sessions`` sessions AND (when mlearn has data) a lower-bound
    multiplier of at least 1.0. A fact has no votes: it moves on the number of
    sessions that read it at its source. Nothing here touches what is the
    owner's or waits for him (I-08); only a learned lesson is demoted by
    outcomes, on a lower-bound case, and any item by a correction whose quote
    was verified. A conflict blocks promotion while the other side is live."""
    score = _item_scorer(ws)
    day = at[:10]
    ops = []
    # One move per item per consolidation: a candidate that earns probation
    # today can become active at a later one, when it has been on probation
    # in between; and a lesson demoted now is not revived by the same batch.
    for rel, row in ws.all_items():
        it = I.normalise(row)
        st, h = it["status"], it["helpful"]
        if it.get("awaiting_owner") or owner_level(rel, it) or st == "retired":
            continue
        op = None
        if st == "demoted":
            if it["id"] in ws.helped and not it.get("corrected") and not ws.live_conflicts(row, day):
                op = {"op": "RESTORE", "id": it["id"], "reason": "a helpful vote after its demotion"}
        elif it.get("corrected") or (learned(it) and it["importance"] < 3 and harm_case(it)):
            op = {"op": "SET_STATUS", "id": it["id"], "status": "demoted"}
        elif ws.live_conflicts(row, day):
            op = None
        elif it["type"] == "fact":
            if st == "candidate" and (it["sessions"] >= 2 or it["supersedes"]):
                op = {"op": "SET_STATUS", "id": it["id"], "status": "probation"}
            elif st == "probation" and it["sessions"] >= max(2, min_sessions):
                op = {"op": "SET_STATUS", "id": it["id"], "status": "active"}
        elif st == "candidate" and h >= 1:
            op = {"op": "SET_STATUS", "id": it["id"], "status": "probation"}
        elif st == "probation" and it["sessions"] >= min_sessions and (
                score is None or score(it) >= PROMOTE_MULTIPLIER):
            op = {"op": "SET_STATUS", "id": it["id"], "status": "active"}
        if op and ws.apply_op(op, at) == "":
            ops.append(op)
    return ops


def _fixed_in_session(outcomes: list[dict]) -> dict[str, list[dict]]:
    """Per session, its outcomes whose gate log shows a red run followed by a
    green run of the same gate: the evidence a pitfall needs (round2/01
    section 3.7). A failure in one session and a pass in another prove
    nothing about each other: they may be different projects (learning-13)."""
    out: dict[str, list[dict]] = {}
    for o in sorted(outcomes, key=lambda r: (str(r.get("at", "")), str(r.get("id", "")))):
        red: set[str] = set()
        fixed = False
        for g in o.get("gate_runs") if isinstance(o.get("gate_runs"), list) else []:
            if not isinstance(g, dict) or not isinstance(g.get("exit"), int) or isinstance(g.get("exit"), bool):
                continue
            if g["exit"] != 0:
                red.add(str(g.get("gate", "")))
            elif str(g.get("gate", "")) in red:
                fixed = True
        if fixed:
            out.setdefault(str(o.get("session", "")), []).append(o)
    return out


def _pitfall_outcome(rec: dict, fixed: dict[str, list[dict]]) -> str | None:
    """The fail-then-fix outcome of the note's own session that a gate-failed
    note is about, matched by class (``software`` matches ``software.feature``)."""
    if rec.get("signal") != "gate-failed":
        return None
    tags = set(rec.get("class") or [])
    for o in fixed.get(str(rec.get("session", "")), []):
        cls = str(o.get("task_class", ""))
        if cls in tags or cls.split(".")[0] in tags:
            return str(o["id"])
    return None


def _support_ops(ws: Workspace, rel: str, row: dict, rec: dict, verified: bool) -> tuple[list[dict], str]:
    """What a note does to an existing item it restates or confirms."""
    sid = str(rec.get("session", ""))
    iid = row["id"]
    if rec.get("trust") == "owner-stated":
        if verified and not owner_level(rel, row):
            return [{"op": "OWNER_CONFIRM", "id": iid, "owner": rec["proof"]}], ""
        if not verified:
            return [], (f"the owner's words were not found again in a transcript on disk; it restates {iid}: "
                        f"brain learn confirm {iid} --quote \"<his words>\"")
    if row.get("type") == "fact":
        return [{"op": "REVERIFY", "id": iid, "session": sid}], ""
    # One session confirms an item once: the same note delivered twice, or a
    # second note from the session that wrote the item, is not a second voice.
    again = bool(sid) and f"session:{sid}" in (row.get("evidence") or [])
    return [{"op": "INC_HELPFUL", "id": iid, "n": 0 if again else 1, "session": sid,
             "evidence": [] if again else list(rec.get("evidence") or [])}], ""


def nearest_items(ws: Workspace, text: str, fact: bool, day: str, limit: int = 2) -> list[tuple[float, str, dict]]:
    """The existing items closest to ``text`` (candidates included), best
    first: what ``learn note`` shows so the lead confirms one or rewords."""
    out = []
    for rel, row in ws.all_items():
        if (row.get("type") == "fact") != fact or not _live(row, day):
            continue
        other = str(row.get("text", ""))
        sim = max(jaccard(text, other), 0.75 * containment(text, other))
        if sim >= NEAR_SHOW:
            out.append((round(sim, 3), rel, row))
    out.sort(key=lambda t: (-t[0], t[2].get("id", "")))
    return out[:limit]


def _note_ops(ws: Workspace, rec: dict, at: str, fixed: dict, by_model: str, ids: list[str]) -> tuple[list[dict], str]:
    """Ops for one note after the admission gate: support for an item it
    restates or names (``confirms``), or an ADD, with a conflict link or a
    SUPERSEDE when it contradicts what is there. A note that claims the
    owner's authority gets it only when its quote is found again in a
    transcript on disk right now; otherwise it is added as a candidate that
    waits for him and is never shown as a rule (learning-01, redteam-02)."""
    errs = check_note(rec)
    if rec.get("scope") == "project":
        errs.append("project lessons stay in the project")
    if errs:
        return [], errs[0]
    text = " ".join(str(rec["text"]).split())
    fact = rec.get("trust") == "external"
    if not fact and not actionable(text):
        return [], "not actionable: say what to do (start with a verb, or use should, must or never)"
    if project_specific(text, ids):
        return [], "names a path, file or project: keep it in that project's .brain/"
    day = at[:10]
    sid = str(rec.get("session", ""))
    claim = rec.get("trust") == "owner-stated"
    verified = claim and reverify_owner(rec) is True
    if rec.get("confirms") is not None:
        rel, row = ws.find(str(rec["confirms"]))
        if row is None or (row.get("type") == "fact") != fact or row.get("valid_to"):
            return [], f"confirms {rec['confirms']}: no such {'fact' if fact else 'lesson'} in memory"
        return _support_ops(ws, rel, row, rec, verified)
    pit = None if fact else _pitfall_outcome(rec, fixed)
    item = note_item(rec, day, "pitfall" if pit else "rule", by_model)
    if pit:
        item["evidence"].append(f"outcome:{pit}")

    def same(row: dict) -> bool:
        return says_the_same(item["text"], str(row.get("text", "")), fact)

    # The item this note is about: one that says the same before one that
    # says the opposite, a live one before a demoted one it would revive,
    # then the closest in words.
    best, best_key = None, None
    for rel, row in ws.all_items():
        if (row.get("type") == "fact") != fact or row.get("valid_to") or row.get("status") == "retired" \
                or not restates(item["text"], str(row.get("text", ""))):
            continue
        demoted = row.get("status", "active") == "demoted"
        if demoted and not same(row):
            continue  # an opposite that is out of use is no conflict
        key = (same(row), not demoted, jaccard(item["text"], str(row.get("text", ""))), [-ord(ch) for ch in row["id"]])
        if best_key is None or key > best_key:
            best, best_key = (rel, row), key
    if best is not None and same(best[1]):
        return _support_ops(ws, best[0], best[1], rec, verified)
    item["sessions"] = 1 if sid else 0
    if sid:
        item["evidence"].append(f"session:{sid}")
    against_owner = best is not None and owner_level(*best)
    add = {"op": "ADD", "file": "memory/facts.jsonl" if fact else "memory/items.jsonl", "item": item}
    if claim and verified and not against_owner:
        item["status"] = "active"
        add["owner"] = rec["proof"]
    elif claim:
        item.update(trust="observed", awaiting_owner=True)
    ops = [add]
    if best is None:
        return ops, ""
    if fact:
        if against_owner:
            return [], f"changes a fact that is the owner's ({best[1]['id']}): only he can replace it"
        return ops + [{"op": "SUPERSEDE", "old": best[1]["id"], "new": item["id"]}], ""
    if against_owner or item.get("awaiting_owner"):
        # One-sided: the owner's item is not touched, and a claim nobody
        # checked cannot hold up the lesson it contradicts.
        item["conflicts"] = [best[1]["id"]]
    else:
        ops.append({"op": "LINK", "a": item["id"], "b": best[1]["id"], "rel": "conflicts"})
    return ops, ""


def _used_op(ws: Workspace, rec: dict, outcomes: list[dict]) -> tuple[dict | None, str]:
    """(op, note) for a recalled item. Credit is read from the same session's
    outcomes, never from the model: every gate green on the first run is a
    helpful vote, a failed outcome a harmful one, anything else just records
    the use. Facts and what is the owner's take no votes from outcomes; a
    candidate is credited only when the injection log proved recall showed
    it (``shown``, written by the script that recorded the use)."""
    sid = str(rec.get("session", ""))
    iid = rec.get("item")
    neutral = {"op": "INC_HELPFUL", "id": iid, "n": 0, "session": sid, "evidence": []}
    if rec.get("followed") is not True:
        return ({**neutral, "seen": True} if rec.get("shown") is True else None), ""
    rel, row = ws.find(str(iid))
    if row is None or row.get("awaiting_owner"):
        return neutral, ""
    mine = [o for o in outcomes if str(o.get("session", "")) == sid]
    ev = [f"outcome:{o['id']}" for o in mine]
    votes = row.get("type") != "fact" and not owner_level(rel, row)
    if mine and all(o.get("passed") is True and o.get("first_pass", True) is True for o in mine):
        if not votes:
            return neutral, ""
        if row.get("status") == "candidate" and rec.get("shown") is not True:
            return neutral, f"no credit for {iid}: a candidate is credited only in a session where recall showed it"
        return {"op": "INC_HELPFUL", "id": iid, "n": 1, "session": sid, "evidence": ev}, ""
    if any(o.get("passed") is False for o in mine):
        if not votes:
            return {**neutral, "failed": True}, ""  # listed for the owner in the digest, not voted on
        return {"op": "INC_HARMFUL", "id": iid, "n": 1, "session": sid, "evidence": ev}, ""
    return neutral, ""


def _shape_problem(rec: dict) -> str:
    """Why a record cannot be read at all; empty when its fields have the
    types the rest of the consolidation relies on (learning-08)."""
    if not isinstance(rec.get("kind"), str) or not rec["kind"]:
        return "kind must be a string"
    for k in ("session", "at", "id", "text", "item", "confirms", "signal", "source", "scope", "trust"):
        if k in rec and not isinstance(rec[k], str):
            return f"{k} must be a string"
    for k in ("evidence", "class"):
        if k in rec and not (isinstance(rec[k], list) and all(isinstance(x, str) for x in rec[k])):
            return f"{k} must be a list of strings"
    if "id" in rec and not rec["id"]:
        return "id must not be empty"
    return ""


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


def build_consolidation(brain_root: Path | None = None, min_sessions: int = 2,
                        budget: int = DEFAULT_BUDGET) -> tuple[dict | None, list[str]]:
    """One delta for every pending inbox file, plus a list of rejections.

    One bad record costs that record: it is rejected with its file and line
    and the rest is applied. A record delivered twice counts once. A lesson
    that does not fit in a full file is rejected alone. Returns (None,
    [reason]) only when the new records cannot be folded into the learning
    statistics: consuming them without folding would lose them."""
    root = Path(brain_root or c.BRAIN_ROOT)
    files = pending_inbox(root)
    if not files:
        return None, []
    at = c.now_iso()
    ws = Workspace(root, owner_ok=True)  # this process checks every owner claim itself, below
    ops: list[dict] = []
    rejected: list[str] = []
    ids = known_project_ids(root)

    def take(candidates: list[dict], label: str) -> None:
        for op in candidates:
            rel = op.get("file", "")
            if op["op"] == "ADD" and ws.live_count(rel) >= budget:
                rejected.append(f"{label}: not added, memory is full: {rel} holds {ws.live_count(rel)} items "
                                f"(limit {budget}); run: brain learn decay")
                return
            err = ws.apply_op(op, at)
            if err:
                rejected.append(f"{label}: {err}")
                return  # the ops of one record stand or fall in order
            ops.append(op)

    state = ws.ml_state() or {}
    folded = {str(x) for x in state.get("seen") or []} if isinstance(state.get("seen"), list) else set()
    ledger_ids: dict[str, set[str]] = {}
    batch = []
    expected: dict[Path, int] = {}
    done: dict[Path, int] = {}
    seen: set[str] = set()
    twice = 0
    for f in files:
        try:
            recs, _bad = c.read_jsonl_counted(f)
        except OSError:
            rejected.append(f"{f.name}: cannot be read; left pending")
            continue
        expected[f] = len(recs)
        for n, rec in enumerate(recs, 1):
            problem = _shape_problem(rec)
            if problem:
                rejected.append(f"{f.name}:{n}: {problem}")
                done[f] = done.get(f, 0) + 1
                continue
            rec = with_id(rec)
            if rec["id"] in seen or (rec["kind"] in FOLD_KINDS and rec["id"] in folded):
                twice += 1
                done[f] = done.get(f, 0) + 1
                continue
            seen.add(rec["id"])
            batch.append((f, n, rec))
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
    fixed = _fixed_in_session(outcomes)
    models: dict[str, str] = {}  # session -> main model; the ledger row says it best
    for kind in ("outcome", "ledger"):
        models.update({str(r.get("session", "")): str(r["model"]) for _f, _n, r in batch
                       if r.get("kind") == kind and r.get("model")})
    good_ids = {r["id"] for r in fold}

    def handle(label: str, rec: dict) -> None:
        nonlocal twice
        kind = rec.get("kind")
        if kind == "ledger":
            rel = f"stats/ledger/{str(rec.get('at', at))[:7]}.jsonl"
            if rel not in ledger_ids:
                ledger_ids[rel] = {str(r.get("id")) for r in map(_loads, ws._get_text(rel).splitlines()) if r}
            if rec["id"] in ledger_ids[rel]:
                twice += 1
                return
            ledger_ids[rel].add(rec["id"])
            take([{"op": "APPEND_STAT", "file": rel, "row": rec}], label)
        elif kind == "used" and rec["id"] in good_ids:
            op, why = _used_op(ws, rec, outcomes)
            if why:
                rejected.append(f"{label}: {why}")
            if op:
                take([op], label)
        elif kind == "correction" and rec["id"] in good_ids and isinstance(rec.get("item"), str):
            rel, row = ws.find(rec["item"])
            if row is not None and owner_level(rel, row):
                rejected.append(f"{label}: {rec['item']} is the owner's and takes no harm votes; if he withdrew it: "
                                f"brain learn reject {rec['item']} --quote \"<his words>\"")
                return
            op = {"op": "INC_HARMFUL", "id": rec["item"], "n": 1, "session": str(rec.get("session", "")),
                  "evidence": list(rec["evidence"])}
            if reverify_owner(rec) is True:
                op["correction"] = True  # his words, found again: this alone demotes
            take([op], label)
        elif kind == "note":
            note_ops, err = _note_ops(ws, rec, at, fixed, models.get(str(rec.get("session", "")), ""), ids)
            if err:
                rejected.append(f"{label}: {err}")
            take(note_ops, label)
        elif kind not in KINDS:
            rejected.append(f"{label}: unknown kind {kind!r}")

    for f, n, rec in batch:
        label = f"{f.name}:{n}"
        done[f] = done.get(f, 0) + 1
        try:
            handle(label, rec)
        except Exception as e:  # one record must never stop the consolidation of the rest
            rejected.append(f"{label}: could not be processed ({type(e).__name__}: {c.clip(str(e), 60)})")
    if twice:
        rejected.append(f"{twice} record(s) delivered twice, counted once")
    for f in files:
        # A file is handled only when every valid record in it was processed;
        # its unreadable lines are reported (inbox_unreadable), never silently dropped.
        if f not in expected or done.get(f, 0) != expected[f]:
            continue
        rel = f.relative_to(root).as_posix()
        take([{"op": "MARK_INBOX", "file": rel}], rel)
    moves = _transitions(ws, at, min_sessions)
    promos = [{"kind": "promotion", "id": record_id("", "promotion", f"{o['id']}|{at}"), "session": "", "at": at,
               "item": o["id"]} for o in moves if o.get("status") == "active"]
    fold_op = next((o for o in ops if o["op"] == "ML_FOLD"), None)
    if promos and (fold_op is not None or mlearn_module(optional=True) is not None):
        if ws.apply_op({"op": "ML_FOLD", "records": promos}, at) == "":
            if fold_op is None:
                ops.insert(0, {"op": "ML_FOLD", "records": promos})
            else:
                fold_op["records"] = fold_op["records"] + promos
    ops += moves
    return (trusted_delta(ops, at) if any("owner" in o for o in ops) else make_delta(ops, at)), rejected


# ---------------------------------------------------------------- decay
def build_decay(brain_root: Path | None = None) -> tuple[dict | None, list[str]]:
    """Demote learned lessons that have faded and retire long-demoted ones;
    return lines to print (facts due a re-check, how many demotions wait).

    Only what a session's note created fades (redteam-01, learning-06):
    shipped knowledge, everything under owner/ and playbooks/, and what the
    owner stated (I-08) are never touched, and a fact that is overdue is
    reported as stale, not demoted. Fading is ``mlearn.retention`` below the
    configured floor when that module is present (an item followed often
    fades slowly), else 90 days without use. Per run at most a tenth of a
    file's live items is demoted, the least retained first, and a demoted
    lesson is retired 180 days after its demotion."""
    root = Path(brain_root or c.BRAIN_ROOT)
    at = c.now_iso()
    ws = Workspace(root)
    retention = getattr(mlearn_module(optional=True), "retention", None)
    floor = (ws.ml_cfg.get("retention") or {}).get("threshold", RETENTION_FLOOR)
    now = c.now()
    ops: list[dict] = []
    lines: list[str] = []
    waiting = 0
    for rel in sorted(ws.rows):
        fade, to_retire = [], []
        for row in ws.rows[rel]:
            it = I.normalise(row)
            if it.get("verified_on") and not it.get("valid_to") and it["status"] != "demoted" and \
                    c.days_since(it["verified_on"]) > int(it.get("recheck_days", 90) or 90):
                lines.append(f"stale fact {it['id']}: verified {it['verified_on']}, re-check every "
                             f"{it.get('recheck_days', 90)} days, then: brain learn reverify {it['id']} --source <url>")
            if not learned(it) or owner_level(rel, it) or rel.startswith("playbooks/"):
                continue
            unused = c.days_since(it["last_used"] or it["created"])
            if it["status"] in ("candidate", "probation", "active") and it["importance"] < 3:
                if it["status"] == "candidate" and not it["uses"] and c.days_since(it["created"]) < CANDIDATE_GRACE_DAYS:
                    continue  # nobody was ever shown it: too early to call it forgotten
                kept = float(retention(it, now)) if retention else None
                if (kept < floor) if kept is not None else unused >= DEMOTE_AFTER_DAYS:
                    fade.append((kept if kept is not None else -unused, it["id"]))
            elif it["status"] == "demoted":
                since = c.days_since(it["demoted_on"]) if it.get("demoted_on") else unused - DEMOTE_AFTER_DAYS
                if since >= RETIRE_FURTHER_DAYS:
                    to_retire.append((-since, it["id"]))
        cap = max(1, ws.live_count(rel) // 10)
        ops += [{"op": "SET_STATUS", "id": iid, "status": "demoted"} for _, iid in sorted(fade)[:cap]]
        waiting += max(0, len(fade) - cap)
        limit = max(1, len(ws.rows[rel]) // 10)
        ops += [{"op": "SET_STATUS", "id": iid, "status": "retired"} for _, iid in sorted(to_retire)[:limit]]
    if waiting:
        lines.append(f"decay: {waiting} more faded item(s) wait for the next run (at most a tenth of a file is demoted per run)")
    return (make_delta(ops, at) if ops else None), lines


# ---------------------------------------------------------------- digest
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


def awaiting_owner(brain_root: Path | None = None) -> list[dict]:
    """Items that claim the owner's words and wait for his yes or no. A claim
    nobody answered fades like any unused lesson and is then no longer asked."""
    return [row for _rel, row in Workspace(Path(brain_root or c.BRAIN_ROOT)).all_items()
            if row.get("awaiting_owner") and row.get("status", "active") == "candidate"]


def build_digest(brain_root: Path | None = None, weeks: int = 1) -> tuple[str, str]:
    """(relative path, text) of the weekly digest, at most 15 lines.

    It opens with what only the owner can judge, in numbered plain sentences
    he can answer with "no 2": what the brain now treats as his instruction,
    what it stopped using, and what waits for his yes or no (redteam-17).
    Nothing inside one container can prove a record came from him, so this
    page is the outside check on owner-level memory."""
    root = Path(brain_root or c.BRAIN_ROOT)
    now = c.now()
    start = now - _dt.timedelta(days=7 * weeks)
    before = start - _dt.timedelta(days=28)
    ws = Workspace(root)
    day = c.today()
    learned_lines, his, stopped, question = [], [], [], []
    for row in manifest_rows(root):
        d = _parse(row.get("at", ""))
        if not d or d < start or d > now:
            continue
        delta = c.read_json(root / "learning" / "deltas" / f"{row.get('id')}.json", {}) or {}
        for op in delta.get("ops", []):
            kind, iid = op.get("op"), str(op.get("id", ""))
            if kind == "ADD" and isinstance(op.get("item"), dict):
                it = op["item"]
                if it.get("trust") == "owner-stated":
                    his.append(str(it.get("id")))
                elif not it.get("awaiting_owner"):
                    learned_lines.append((str(it.get("id")), f"{it.get('id')}: {c.clip(str(it.get('text', '')), 80)}"))
            elif kind == "OWNER_CONFIRM":
                his.append(iid)
            elif kind == "SET_STATUS" and op.get("status") == "active":
                learned_lines.append((iid, f"{iid} is now active"))
            elif kind == "SET_STATUS" and op.get("status") in ("retired", "demoted"):
                stopped.append(iid)
            elif kind == "SUPERSEDE":
                stopped.append(str(op.get("old", "")))
            elif kind == "INC_HARMFUL" or op.get("failed"):
                _rel, target = ws.find(iid)
                if target is not None and not learned(target):
                    question.append(iid)

    def in_use(iid: str) -> bool:
        _rel, row = ws.find(iid)
        return row is not None and _live(row, day)

    def sentence(iid: str) -> str:
        _rel, row = ws.find(iid)
        row = row or ws.archived(iid) or {}
        return f"{c.clip(str(row.get('text') or 'an item no longer on file'), 90)} [{iid}]"

    def uniq(ids: list[str]) -> list[str]:
        return list(dict.fromkeys(i for i in ids if i))

    his = [i for i in uniq(his) if in_use(i) and (ws.find(i)[1] or {}).get("trust") == "owner-stated"]
    stopped = [i for i in uniq(stopped) if not in_use(i) and not (ws.find(i)[1] or ws.archived(i) or {}).get("awaiting_owner")]
    waiting = [str(r.get("id")) for r in awaiting_owner(root)]
    question = [i for i in uniq(question) if in_use(i)]
    learned_lines = [line for iid, line in learned_lines if in_use(iid)]

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
    for _rel, row in ws.all_items():
        if _live(row, day):
            for other in ws.live_conflicts(row, day):
                pairs.add(tuple(sorted((row["id"], other))))

    def capped(lines: list[str], n: int) -> list[str]:
        return lines[:n] + ([f"- and {len(lines) - n} more"] if len(lines) > n else [])

    week = _iso_week(now)
    out = [f"# Learning digest {week}"]
    number = 0

    def numbered(title: str, ids: list[str], empty: str, cap: int = 2) -> None:
        nonlocal number
        if not ids:
            if empty:
                out.append(f"{title}: {empty}")
            return
        out.append(f"{title}:" if len(ids) <= cap else f"{title} ({len(ids)}, first {cap}):")
        for iid in ids[:cap]:
            number += 1
            out.append(f"{number}. {sentence(iid)}")

    numbered("What I now treat as your instruction", his, "nothing new")
    numbered("What I stopped using", stopped, "nothing")
    numbered("Did you say this? Answer yes or no", waiting, "")
    if question:
        out.append(c.clip("In question (followed in sessions that failed; nothing changed): " + ", ".join(question[:6]), 200))
    for title, lines in (("Learned:", capped([f"- {l}" for l in learned_lines], 3) or ["- nothing new"]),
                         ("Efficiency (tokens per recorded task, this period vs previous four weeks):",
                          capped(eff, 3) or ["- no recorded tasks"]),
                         ("Unsure:", capped([f"- {a} conflicts with {b}" for a, b in sorted(pairs)], 2) or ["- nothing"])):
        room = 15 - len(out)
        if room >= 2:
            out += [title] + lines[:room - 1]
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
            # own script (the radar); neither is produced by deltas. The digest is
            # a report regenerated from the manifest (learn digest --write), so
            # writing it again in the same week is not a change to memory.
            if p.is_file() and not p.name.startswith(".tmp-") and zone_of(rel) not in ("kernel", "state") \
                    and not rel.startswith("learning/digest/"):
                out[rel] = p.read_bytes()
    return out


def _append_only(rel: str) -> bool:
    return zone_of(rel) == "inbox"


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
        broken = []      # deltas the promotion rules refuse: never legitimate, locked or not
        owner_ops = 0
        for did in new:
            delta = c.read_json(root / "learning" / "deltas" / f"{did}.json")
            if not isinstance(delta, dict):
                problems.append(f"learning/deltas/{did}.json: missing or unreadable")
                break
            ok, lines = apply_delta(delta, tmp, replay=True)
            if not ok:
                problems.append(f"delta {did} is refused on replay: {lines[0]}")
                if "promotion rules:" in lines[0]:
                    broken.append(problems[-1])
                break
            owner_ops += sum(1 for op in delta.get("ops", []) if isinstance(op, dict) and "owner" in op)
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
        return True, [f"learn verify: {len(new)} delta(s) replayed on {base}; learned zone matches"
                      + (f"; {owner_ops} owner-level change(s), listed in the digest for him" if owner_ops else "")]
    if broken:
        return False, ["learn verify: a recorded delta breaks the promotion rules; it was not made by brain learn"] + broken
    locked = bool((c.read_json(root / "VERSION.json", {}) or {}).get("learned_zone_locked"))
    if locked:
        return False, [f"learn verify: {len(problems)} learned-zone file(s) do not match the deltas"] + problems[:12]
    return True, ["learn verify: bootstrap period (learned zone not locked); mismatches are warnings only"] + \
        [f"warning: {p}" for p in problems[:12]]


# ---------------------------------------------------------------- cli
def _root(args) -> Path:
    return Path(getattr(args, "brain_root", None) or c.BRAIN_ROOT)


def _managed_project(args, root: Path) -> Path | None:
    proj = c.resolve_project(getattr(args, "project", None), root)
    return proj if proj is not None and c.is_managed(proj) else None


def build_note(args, root: Path) -> tuple[dict | None, Path | None, str]:
    """(record, project, "") for ``learn note``, or (None, None, reason). Every
    check runs before anything is written, so a refused text is never stored
    anywhere in the brain: format, the admission gate (it must say what to
    do), owner words (--quote), project names and paths (I-05), and evidence
    that resolves to this session's own records."""
    sid = c.session_id()
    rec = {"kind": "note", "session": sid, "at": c.now_iso(), "text": " ".join((args.text or "").split()),
           "class": list(args.cls or []), "scope": args.scope, "trust": args.trust,
           "evidence": [" ".join(str(e).split()) for e in (args.evidence or [])]}
    if args.signal:
        rec["signal"] = args.signal
    if args.source:
        rec["source"] = args.source
    confirms = getattr(args, "confirms", None)
    if confirms:
        rec["confirms"] = confirms
    if any(e.startswith("owner:") for e in rec["evidence"]):
        return None, None, "owner evidence comes only from --quote, checked against the owner's typed turns"
    if args.trust == "owner-stated" and not getattr(args, "quote", None):
        return None, None, "--trust owner-stated needs --quote with the owner's own words from this session"
    probe = dict(rec, evidence=rec["evidence"] + (["owner:turn@x#000000000000"] if getattr(args, "quote", None) else []))
    errs = check_note(probe)
    if errs:
        return None, None, "; ".join(errs)
    if args.trust != "external" and not actionable(rec["text"]):
        return None, None, "not actionable: say what to do (start with a verb, or use should, must or never), then note it again"
    project = _managed_project(args, root)
    if args.scope != "project":
        names = known_project_ids(root) + project_words(project)
        if project_specific(rec["text"], names):
            return None, None, "names a path, file or project: record it with --scope project in that project's .brain/"
        if any(project_specific(e, names) for e in rec["evidence"] if not e.startswith("review:")):
            return None, None, "evidence names a path, file or project: name the gate, test or run instead"
        if confirms:
            _rel, row = Workspace(root).find(confirms)
            if row is None or (row.get("type") == "fact") != (args.trust == "external"):
                return None, None, f"--confirms {confirms}: no such {'fact' if args.trust == 'external' else 'lesson'} in memory"
    evidence, why = resolve_evidence(rec["evidence"], sid, project, root)
    if why:
        return None, None, why
    if getattr(args, "quote", None):
        proof, why = owner_proof(args.quote, sid)
        if why:
            return None, None, why
        evidence.append(proof_evidence(proof))
        rec["proof"] = proof
    rec["evidence"] = evidence
    errs = check_note(rec)
    if errs:
        return None, None, "; ".join(errs)
    return rec, project, ""


def cmd_note(args) -> int:
    root = _root(args)
    rec, project, why = build_note(args, root)
    if rec is None:
        print("note refused: " + why)
        return 1
    if args.scope == "project":
        if project is None:
            print("no managed project found (attach one, or run: brain init <path>)")
            return 1
        # A project lesson never leaves the project and its evidence was just
        # checked, so it is usable at once: on probation, or active when the
        # owner's words back it (learning-03). The file is the project's own,
        # so trust stays "observed" whoever said it.
        item = note_item(rec, c.today())
        item["status"] = "active" if rec["trust"] == "owner-stated" else "probation"
        item["trust"] = "external" if rec["trust"] == "external" else "observed"
        path = project / ".brain" / "memory" / "lessons.jsonl"
        if any(r.get("id") == item["id"] for r in c.read_jsonl(path)):
            print(f"already recorded as {item['id']}")
            return 0
        bad = I.validate_item(item)
        if bad:
            print("note refused: " + bad[0])
            return 1
        c.append_jsonl(path, item)
        print(f"project lesson {item['id']} recorded ({'active' if item['status'] == 'active' else 'on probation'}) "
              "in .brain/memory/lessons.jsonl")
        return 0
    path = _writable_session_file(root, rec["session"])
    rec = with_id(rec)
    # The same text noted again in this session replaces the earlier note
    # (same record id), so "note, see what is close, note again with
    # --confirms" leaves one record, not a near-duplicate lesson.
    earlier = c.read_jsonl(path)
    if any(r.get("id") == rec["id"] for r in earlier):
        c.write_jsonl(path, [r for r in earlier if r.get("id") != rec["id"]] + [rec])
    else:
        c.append_jsonl(path, rec)
    fact = rec["trust"] == "external"
    if rec.get("confirms"):
        print(f"note recorded ({path.name}): it counts for {rec['confirms']} at the next consolidation")
        return 0
    ws = Workspace(root)
    near = nearest_items(ws, rec["text"], fact, c.today())
    hit = next((row for _sim, _rel, row in near if restates(rec["text"], str(row.get("text", "")))), None)
    if hit is not None:
        if says_the_same(rec["text"], str(hit.get("text", "")), fact):
            what = f"it restates {hit['id']} and counts for it at the next consolidation"
        elif fact:
            what = f"it differs from {hit['id']} and replaces it at the next consolidation"
        else:
            what = (f"it says the opposite of {hit['id']}: neither moves up until the owner settles it "
                    "(brain learn confirm <the one he means> --quote)")
        print(f"note recorded ({path.name}): {what}")
        return 0
    future = note_item(rec, c.today())["id"]
    if rec["trust"] == "owner-stated":
        print(f"note recorded ({path.name}): it becomes {future}, his instruction if consolidated in this session; "
              "later it waits for his yes (brain learn confirm)")
    else:
        pit = f"; pit-{future.split('-', 1)[1]} if its gate went red then green" if rec.get("signal") == "gate-failed" else ""
        print(f"note recorded ({path.name}): it becomes {future} (a candidate{pit}) at the next consolidation")
    for _sim, _rel, row in near:
        print(f"close to {row['id']} ({row.get('status', 'active')}): {c.clip(str(row.get('text', '')), 100)}")
    if near:
        print("if it is the same lesson, note it again with --confirms <that id>")
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
    root = _root(args)
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
    proof, why = owner_proof(args.quote, sid)
    if why:
        print("correction refused: " + why)
        return 1
    rec = {"kind": "correction", "session": sid, "at": c.now_iso(), "correction": args.kind,
           "evidence": [proof_evidence(proof)], "proof": proof}
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


def _owner_command(args, name: str, ops_for) -> int:
    """Shared body of confirm, reject and restore: find the item, check the
    owner's words in this session's transcript when they are given or needed,
    build the delta in this process and apply it. ``ops_for(ws, rel, row,
    proof)`` returns (ops, refusal)."""
    root = _root(args)
    iid = str(args.id)
    ws = Workspace(root)
    rel, row = ws.find(iid)
    if row is None:
        row = ws.archived(iid) if name == "restore" else None
        rel = (row or {}).get("retired_from")
    if row is None:
        print(f"{name} refused: no item {iid} in memory (brain learn status lists what waits for the owner)")
        return 1
    proof = None
    quote = getattr(args, "quote", None)
    if quote:
        # A short answer ("no 2", "yes") counts when it is a whole line he typed.
        proof, why = owner_proof(quote, c.session_id(), whole_line=True)
        if why:
            print(f"{name} refused: {why}")
            return 1
    ops, why = ops_for(ws, rel, row, proof)
    if why:
        print(f"{name} refused: {why}")
        return 1
    delta = trusted_delta(ops) if proof else make_delta(ops)
    ok, lines = apply_delta(delta, root)
    print(("" if ok else f"{name} refused, nothing changed: ") + "\n".join(lines[1:5] if ok and len(lines) > 1 else lines[:2]))
    return 0 if ok else 1


def cmd_confirm(args) -> int:
    """The owner said yes: the item becomes his instruction, and whatever it
    conflicted with is set aside (learning-01, learning-14)."""
    def ops_for(ws, rel, row, proof):
        if proof is None:
            return [], "confirm needs --quote with the owner's own words from this session"
        if row.get("trust") == "owner-stated" and row.get("status", "active") == "active":
            return [], f"{row['id']} is already his instruction"
        ops = [{"op": "OWNER_CONFIRM", "id": row["id"], "owner": proof}]
        for other in ws.live_conflicts(row, c.today()):
            ops += [{"op": "SET_STATUS", "id": other, "status": "demoted", "owner": proof},
                    {"op": "UNLINK", "a": row["id"], "b": other, "owner": proof}]
        return ops, ""
    return _owner_command(args, "confirm", ops_for)


def cmd_reject(args) -> int:
    """The owner said no. A claim that was only waiting for him is retired
    without more proof; anything else is his to withdraw, in his words."""
    def ops_for(ws, rel, row, proof):
        if row.get("awaiting_owner"):
            return [{"op": "SET_STATUS", "id": row["id"], "status": "retired"}], ""
        if proof is None:
            return [], (f"{row['id']} is in use; withdrawing it needs --quote with the owner's own words "
                        "(a short answer such as \"no 2\" counts when it is a whole line he typed)")
        if row.get("status") == "demoted":
            return [], f"{row['id']} is already out of use"
        return [{"op": "SET_STATUS", "id": row["id"], "status": "demoted", "owner": proof}], ""
    return _owner_command(args, "reject", ops_for)


def cmd_restore(args) -> int:
    """Bring back an item that was demoted or retired."""
    def ops_for(ws, rel, row, proof):
        op = {"op": "RESTORE", "id": str(args.id), "reason": " ".join(str(args.reason or "").split())}
        if proof:
            op["owner"] = proof
        return [op], ""
    return _owner_command(args, "restore", ops_for)


def cmd_reverify(args) -> int:
    """A fact was read again at its source: move its re-check date (learning-07)."""
    root = _root(args)
    if not str(args.source or "").startswith("https://"):
        print("reverify refused: --source must be the https address where the fact was read again")
        return 2
    ok, lines = apply_delta(make_delta([{"op": "REVERIFY", "id": str(args.id), "session": c.session_id(),
                                         "source": args.source}]), root)
    print(lines[1] if ok and len(lines) > 1 else ("" if ok else "reverify refused: ") + lines[0])
    return 0 if ok else 1


def cmd_review(args) -> int:
    """Two independent review passes: record the counts, answer whether to run
    another round (capture-recapture, ``mlearn.review_stop``)."""
    root = _root(args)
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


LEADS_SHOWN = 5


def cmd_consolidate(args) -> int:
    root = _root(args)
    leads = official_leads(root)
    bad_lines, bad_files = inbox_unreadable(root)
    if bad_lines:
        print(f"inbox: {bad_lines} unreadable line(s) in {bad_files} file(s) skipped; the valid records are used")
    delta, rejected = build_consolidation(root, min_sessions=args.min_sessions)
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
    for r in rejected[:3]:
        print(f"rejected {r}")
    if len(rejected) > 3:
        print(f"rejected {len(rejected) - 3} more")
    # Every official lead is shown before its file is marked handled: a lead
    # that scrolls away unseen is lost (learning-07).
    for lead in leads[:LEADS_SHOWN]:
        print(f"lead to confirm at its source: {c.clip(str(lead.get('title', '')), 60)} {lead.get('url', '')}")
    if len(leads) > LEADS_SHOWN:
        names = sorted({p.name for p in pending_inbox(root) for r in c.read_jsonl(p)
                        if r.get("kind") == "lead" and r.get("trust") == "official"})
        print(f"and {len(leads) - LEADS_SHOWN} more official lead(s): read {', '.join(names[:3])} in learning/inbox/")
    if args.dry_run:
        print("dry run: nothing written")
        return 0
    ok, lines = apply_delta(delta, root)
    print("\n".join(lines[:4]))
    waiting = len(awaiting_owner(root)) if ok else 0
    if waiting:
        print(f"{waiting} item(s) wait for the owner's yes or no: brain learn status")
    return 0 if ok else 1


def cmd_apply(args) -> int:
    delta = c.read_json(args.delta)
    if not isinstance(delta, dict):
        print(f"cannot read a delta from {args.delta}")
        return 1
    ok, lines = apply_delta(delta, _root(args), budget=args.budget)
    print(("" if ok else "refused, nothing changed: ") + "\n".join(lines[:10]))
    return 0 if ok else 1


def cmd_decay(args) -> int:
    root = _root(args)
    delta, lines = build_decay(root)
    stale = [l.split(":", 1)[0][len("stale fact "):] for l in lines if l.startswith("stale fact ")]
    if len(stale) > 1:  # one line however many are due
        more = f" and {len(stale) - 6} more" if len(stale) > 6 else ""
        print(f"{len(stale)} stale facts, re-check each at its source, then brain learn reverify <id> --source <url>: "
              f"{', '.join(stale[:6])}{more}")
        lines = [l for l in lines if not l.startswith("stale fact ")]
    for line in lines[:4]:
        print(line)
    if delta is None:
        print("decay: nothing to demote or retire")
        return 0
    ok, out = apply_delta(delta, root)
    print("\n".join(out[:6]))
    return 0 if ok else 1


def cmd_digest(args) -> int:
    """Print the digest. It is a report, so it writes its file only with
    --write: a reporting command must leave the brain clean (owner-docs-12)."""
    root = _root(args)
    rel, text = build_digest(root, weeks=args.weeks)
    if getattr(args, "write", False):
        c.write_text(root / rel, text)
    print(text, end="")
    return 0


def cmd_verify(args) -> int:
    ok, lines = verify(_root(args), base=args.base)
    print("\n".join(lines))
    return 0 if ok else 1


def status_lines(brain_root: Path | None = None) -> list[str]:
    root = Path(brain_root or c.BRAIN_ROOT)
    counts: dict[str, int] = {s: 0 for s in I.STATUS if s != "retired"}
    conflicts = 0
    ws = Workspace(root)
    day = c.today()
    live_ids = set()
    waiting = []
    for _rel, row in ws.all_items():
        it = I.normalise(row)
        counts[it["status"]] = counts.get(it["status"], 0) + 1
        conflicts += bool(_live(row, day) and ws.live_conflicts(row, day))
        live_ids.add(it["id"])
        if it.get("awaiting_owner") and it["status"] == "candidate":
            waiting.append(it["id"])
    archived = len({r.get("id") for r in c.read_jsonl(root / ARCHIVE)} - live_ids)
    pend = pending_inbox(root)
    recs = sum(len(c.read_jsonl(p)) for p in pend)
    bad_lines, _bad_files = inbox_unreadable(root)
    rows = manifest_rows(root)
    last = rows[-1] if rows else None
    out = [
        "items: " + ", ".join(f"{v} {k}" for k, v in counts.items()) + f"; {archived} archived",
        f"items in a conflict: {conflicts}",
        f"inbox: {len(pend)} file(s) pending ({recs} record(s)"
        + (f", {bad_lines} unreadable line(s)" if bad_lines else "")
        + f"); {len(official_leads(root))} unhandled official lead(s)",
        f"last delta: {last['id']} at {last['at']} ({last['ops_count']} op(s))" if last else "last delta: none yet",
        f"deltas applied: {len(rows)}",
    ]
    if waiting:
        out.append(c.clip(f"awaiting the owner: {len(waiting)} (not in use; brain learn confirm <id> --quote \"<his words>\", "
                          f"or brain learn reject <id>): {', '.join(waiting[:4])}", 300))
    return out


def cmd_status(args) -> int:
    print("\n".join(status_lines(_root(args))))
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
    n.add_argument("--confirms", metavar="ID", help="this note is one more confirmation of that existing item, in other words")
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

    k = s.add_parser("confirm", help="the owner said yes: make an item his instruction (needs --quote of his words)")
    k.add_argument("id")
    k.add_argument("--quote", required=True, help="his own words from a turn he typed in this session")
    k.set_defaults(func=cmd_confirm)

    k = s.add_parser("reject", help="the owner said no: retire a waiting claim, or withdraw an item with --quote")
    k.add_argument("id")
    k.add_argument("--quote", help="his own words from this session; needed unless the item only waits for him")
    k.set_defaults(func=cmd_reject)

    k = s.add_parser("restore", help="bring back a demoted or retired item")
    k.add_argument("id")
    k.add_argument("--reason", required=True, help="why it applies again, in a few words")
    k.add_argument("--quote", help="the owner's words; needed for an item that is his or that he withdrew")
    k.set_defaults(func=cmd_restore)

    k = s.add_parser("reverify", help="a fact was read again at its source: move its re-check date")
    k.add_argument("id")
    k.add_argument("--source", required=True, help="the https address where it was read again")
    k.set_defaults(func=cmd_reverify)

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

    a = s.add_parser("apply", help="apply a delta file (all or nothing; never owner-level changes)")
    a.add_argument("delta")
    a.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="items allowed per file")
    a.set_defaults(func=cmd_apply)

    s.add_parser("decay", help="demote faded lessons and retire long-demoted ones; flag stale facts").set_defaults(func=cmd_decay)

    d = s.add_parser("digest", help="print the weekly digest (15 lines at most)")
    d.add_argument("--weeks", type=int, default=1)
    d.add_argument("--write", action="store_true", help="also keep it as learning/digest/<week>.md")
    d.set_defaults(func=cmd_digest)

    v = s.add_parser("verify", help="CI: replay recorded deltas on the base and compare")
    v.add_argument("--base", help="git ref (default origin/main, else HEAD)")
    v.set_defaults(func=cmd_verify)

    s.add_parser("status", help="what the brain has learned so far").set_defaults(func=cmd_status)
    p.set_defaults(func=cmd_status)
