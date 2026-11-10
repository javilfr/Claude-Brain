"""The learning pipeline: the only writer of the brain's learned zone.

Why it is built this way (MASTER_PLAN Part 6, ENGINE_SPEC):
- Sessions only append records to ``learning/inbox/``. ``consolidate`` turns
  pending inbox files into ONE delta (an ordered list of small operations) and
  ``apply`` executes it. Nothing else writes ``memory/``, ``owner/``,
  ``stats/``, ``playbooks/``, the manifest or the changelog.
- No operation replaces or deletes a file, and a delta that would retire too
  many items or shrink a file sharply is refused whole, because a memory that
  is rewritten wholesale can collapse (the ACE result in Part 6.2).
- Everything ``apply`` writes is a pure function of the files it starts from
  and the delta (time comes from the delta, not the clock), so CI can replay
  the recorded deltas on the base commit and demand byte-identical files
  (``verify``). A hand edit dressed up as learning then fails.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import common as c
from . import items as I
from .guard import zone_of

OPS = ("ADD", "INC_HELPFUL", "INC_HARMFUL", "EDIT_TEXT", "SET_STATUS", "MOVE_SCOPE", "LINK",
       "APPEND_STAT", "ROUTE_OUTCOME", "MARK_INBOX")
DEFAULT_BUDGET = 400
SIMILAR = 0.6
DEMOTE_AFTER_DAYS = 90
RETIRE_AFTER_DAYS = 90 + 180
TRUST_NOTE = ("observed", "owner-stated", "external")
SIGNALS = ("gate-failed", "rework", "owner-correction", "token-outlier", "first-success")
# Evidence must point at an event a script can check: a gate, a test, an
# outcome record, an owner turn, a run record or a review.
EVIDENCE_RE = re.compile(r"^(gate|test|outcome|owner|run|review):\S")
ARCHIVE = "memory/archive.jsonl"
MANIFEST = "learning/manifest.jsonl"
CHANGELOG = "learning/CHANGELOG.md"
LEDGER_FILE_RE = re.compile(r"^stats/ledger/\d{4}-\d{2}\.jsonl$")
NEGATIVE_RE = re.compile(r"\b(never|don't|do not|must not|should not|shouldn't|avoid|no longer|cannot|can't|stop)\b", re.I)
# Words that carry polarity are removed before comparing meaning, so that
# "always X" and "never X" are recognised as the same subject.
POLARITY_WORDS = frozenset("always never do don does doesn not no avoid must should shouldn cannot can stop longer".split())
IMPERATIVE_RE = re.compile(r"\b(always|never|must|should|shall|do not|don't|avoid|make sure|ensure|remember to|you need to|prefer)\b", re.I)
IMPERATIVE_START = frozenset(
    "use run add remove delete ignore install write set call send keep stop skip disable enable push commit "
    "read follow check prefer avoid never always do don't please make ensure execute open fetch upload".split())


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
    c.write_jsonl(path, keep + records)
    return path


def pending_inbox(root: Path) -> list[Path]:
    root = Path(root)
    consumed = consumed_inbox(root)
    return [p for p in sorted((root / c.INBOX_DIR).glob("*.jsonl")) if p.relative_to(root).as_posix() not in consumed]


# ---------------------------------------------------------------- notes
def is_imperative(text: str) -> bool:
    first = (text.split() or [""])[0].lower().strip(".,:;!\"'")
    return first in IMPERATIVE_START or bool(IMPERATIVE_RE.search(text))


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
    if not ev:
        errs.append("evidence is required (a gate, test, outcome or owner turn)")
    elif not all(isinstance(e, str) and EVIDENCE_RE.match(e) for e in ev):
        errs.append("each evidence must start with gate:, test:, outcome:, owner:, run: or review:")
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


def note_item(rec: dict, day: str) -> dict:
    """The memory item a note becomes. External notes become facts, never rules."""
    fact = rec.get("trust") == "external"
    text = " ".join(str(rec["text"]).split())
    slug = "-".join(w for w in (re.sub(r"[^a-z0-9]", "", x) for x in c.words(text)) if w)[:40].strip("-") or "item"
    item = I.normalise({
        "id": f"{'fact' if fact else 'lsn'}-{slug}-{c.sha256_text(text)[:6]}",
        "type": "fact" if fact else "rule",
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
    if fact:
        item["source"] = str(rec.get("source", ""))
        item["verified_on"] = day
        item["recheck_days"] = 90
    return item


def _core(text: str) -> set[str]:
    return {w for w in c.words(text) if w not in POLARITY_WORDS}


def jaccard(a: str, b: str) -> float:
    x, y = _core(a), _core(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def negative(text: str) -> bool:
    return bool(NEGATIVE_RE.search(text))


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
        self.counts = {"APPEND_STAT": 0, "ROUTE_OUTCOME": 0}
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
            rel, item = str(op.get("file", "")), op.get("item")
            if zone_of(rel) != "learned" or not rel.endswith(".jsonl") or rel in (ARCHIVE, MANIFEST) \
                    or rel.startswith(("stats/", "learning/")):
                return f"ADD: {rel!r} is not an item file"
            if not isinstance(item, dict):
                return "ADD: item missing"
            item = I.normalise(item)
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
            if not isinstance(n, int) or n < 0:
                return f"{kind}: n must be a non-negative integer"
            field = "helpful" if kind == "INC_HELPFUL" else "harmful"
            row[field] = int(row.get(field, 0) or 0) + n
            self.votes[0 if field == "helpful" else 1] += n
            row["uses"] = int(row.get("uses", 0) or 0) + 1
            row["last_used"] = day
            ev = list(row.get("evidence") or [])
            sid = op.get("session")
            if sid and f"session:{sid}" not in ev:
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
            row["text"] = str(op.get("text", ""))
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
        if kind == "APPEND_STAT":
            rel = str(op.get("file", ""))
            if not LEDGER_FILE_RE.match(rel) or not isinstance(op.get("row"), dict):
                return f"APPEND_STAT: bad file {rel!r} or row"
            self._append(rel, op["row"])
            self.counts["APPEND_STAT"] += 1
            return ""
        if kind == "ROUTE_OUTCOME":
            if not op.get("task_class") or not isinstance(op.get("passed"), bool):
                return "ROUTE_OUTCOME: task_class and passed are required"
            rel = "stats/routing.json"
            table = json.loads(self._get_text(rel) or "{}")
            arm = table.setdefault(str(op["task_class"]), {}).setdefault(
                f"{op.get('model', '')}|{op.get('effort', '')}", {"pass": 0, "fail": 0, "tokens": 0})
            arm["pass" if op["passed"] else "fail"] += 1
            arm["tokens"] += int(op.get("tokens", 0) or 0)
            self.text[rel] = json.dumps(table, indent=2, sort_keys=True) + "\n"
            self.touched.add(rel)
            self.counts["ROUTE_OUTCOME"] += 1
            return ""
        if kind == "MARK_INBOX":
            rel = str(op.get("file", ""))
            if zone_of(rel) != "inbox":
                return f"MARK_INBOX: {rel!r} is not an inbox file"
            if rel not in self.inbox_files:
                self.inbox_files.append(rel)
            return ""
        return f"unknown op {kind!r}"

    def _touch_item(self, rel: str, iid: str) -> None:
        self.touched.add(rel)
        self.changed_ids.add(iid)

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
        if self.counts["ROUTE_OUTCOME"]:
            lines.append(f"{self.counts['ROUTE_OUTCOME']} routing outcome(s) recorded")
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
def _transitions(ws: Workspace, at: str, min_sessions: int) -> list[dict]:
    """Status moves earned by evidence, applied to ``ws`` and returned as ops.
    Conflicting items are never promoted; harm demotes regardless."""
    ops = []
    for _ in range(3):  # candidate -> probation -> active can happen in one pass
        moved = False
        for _rel, row in ws.all_items():
            it = I.normalise(row)
            st, h, x = it["status"], it["helpful"], it["harmful"]
            new = None
            if x >= 3 and x > h and st not in ("demoted", "retired"):
                new = "demoted"
            elif it["conflicts"]:
                new = None
            elif st == "candidate" and (h >= 1 or it["trust"] == "owner-stated"):
                new = "probation"
            elif st == "probation" and h >= 3 and it["sessions"] >= min_sessions:
                new = "active"
            if new:
                op = {"op": "SET_STATUS", "id": it["id"], "status": new}
                ws.apply_op(op, at)
                ops.append(op)
                moved = True
        if not moved:
            break
    return ops


def _note_ops(ws: Workspace, rec: dict, at: str) -> tuple[list[dict], str]:
    """Ops for one note: a vote on a near-duplicate, a conflict link, or an ADD."""
    errs = check_note(rec)
    if rec.get("scope") == "project":
        errs.append("project lessons stay in the project")
    if errs:
        return [], errs[0]
    item = note_item(rec, at[:10])
    fact = item["type"] == "fact"
    best, best_sim = None, 0.0
    for _rel, row in ws.all_items():
        if (row.get("type") == "fact") != fact:
            continue
        sim = jaccard(item["text"], str(row.get("text", "")))
        if sim > best_sim or (sim == best_sim and best is not None and row["id"] < best["id"]):
            best, best_sim = row, sim
    sid = str(rec.get("session", ""))
    if best is not None and best_sim >= SIMILAR and negative(best["text"]) == negative(item["text"]):
        return [{"op": "INC_HELPFUL", "id": best["id"], "n": 1, "session": sid,
                 "evidence": list(rec.get("evidence") or [])}], ""
    item["sessions"] = 1 if sid else 0
    if sid:
        item["evidence"].append(f"session:{sid}")
    ops = [{"op": "ADD", "file": "memory/facts.jsonl" if fact else "memory/items.jsonl", "item": item}]
    if best is not None and best_sim >= SIMILAR:
        ops.append({"op": "LINK", "a": item["id"], "b": best["id"], "rel": "conflicts"})
    return ops, ""


def build_consolidation(brain_root: Path | None = None, min_sessions: int = 2) -> tuple[dict | None, list[str]]:
    """One delta for every pending inbox file, plus a list of rejections."""
    root = Path(brain_root or c.BRAIN_ROOT)
    files = pending_inbox(root)
    if not files:
        return None, []
    at = c.now_iso()
    ws = Workspace(root)
    ops: list[dict] = []
    rejected: list[str] = []

    def take(candidates: list[dict], label: str) -> None:
        for op in candidates:
            err = ws.apply_op(op, at)
            if err:
                rejected.append(f"{label}: {err}")
            else:
                ops.append(op)

    for f in files:
        rel = f.relative_to(root).as_posix()
        for n, rec in enumerate(c.read_jsonl(f), 1):
            label = f"{f.name}:{n}"
            kind = rec.get("kind")
            if kind == "ledger":
                month = str(rec.get("at", at))[:7]
                take([{"op": "APPEND_STAT", "file": f"stats/ledger/{month}.jsonl", "row": rec}], label)
            elif kind == "outcome":
                take([{"op": "ROUTE_OUTCOME", "task_class": rec.get("task_class"), "model": rec.get("model", ""),
                       "effort": rec.get("effort", ""), "passed": rec.get("passed"),
                       "tokens": rec.get("tokens", 0)}], label)
            elif kind == "used":
                helped = rec.get("helped")
                op = "INC_HARMFUL" if helped is False else "INC_HELPFUL"
                take([{"op": op, "id": rec.get("item"), "n": 1 if isinstance(helped, bool) else 0,
                       "session": str(rec.get("session", "")), "evidence": []}], label)
            elif kind == "note":
                note_ops, err = _note_ops(ws, rec, at)
                if err:
                    rejected.append(f"{label}: {err}")
                take(note_ops, label)
            else:
                rejected.append(f"{label}: unknown kind {kind!r}")
        take([{"op": "MARK_INBOX", "file": rel}], rel)
    ops += _transitions(ws, at, min_sessions)
    return make_delta(ops, at), rejected


# ---------------------------------------------------------------- decay
def build_decay(brain_root: Path | None = None) -> tuple[dict | None, list[str]]:
    """Demote long-unused items and retire long-demoted ones (within the
    retire cap per file); return stale facts as lines to print."""
    root = Path(brain_root or c.BRAIN_ROOT)
    at = c.now_iso()
    ws = Workspace(root)
    ops: list[dict] = []
    stale: list[str] = []
    for rel in sorted(ws.rows):
        to_retire = []
        for row in ws.rows[rel]:
            it = I.normalise(row)
            if it.get("verified_on") and c.days_since(it["verified_on"]) > int(it.get("recheck_days", 90) or 90):
                stale.append(f"stale fact {it['id']}: verified {it['verified_on']}, re-check every {it.get('recheck_days', 90)} days")
            if it["trust"] == "owner-stated":  # what the owner said does not fade with disuse
                continue
            unused = c.days_since(it["last_used"] or it["created"])
            if it["status"] in ("candidate", "probation", "active") and it["importance"] < 3 and unused >= DEMOTE_AFTER_DAYS:
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
            if p.is_file() and not p.name.startswith(".tmp-") and zone_of(rel) != "kernel":
                out[rel] = p.read_bytes()
    return out


def _append_only(rel: str) -> bool:
    return zone_of(rel) == "inbox" or rel.startswith("learning/digest/")


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
            for rel in sorted(set(head) | set(replay)):
                h, r = head.get(rel), replay.get(rel)
                if _append_only(rel):
                    if r is not None and (h is None or not h.startswith(r)):
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
def cmd_note(args) -> int:
    rec = {"kind": "note", "session": c.session_id(), "at": c.now_iso(), "text": " ".join((args.text or "").split()),
           "class": args.cls, "scope": args.scope, "trust": args.trust, "evidence": args.evidence}
    if args.signal:
        rec["signal"] = args.signal
    if args.source:
        rec["source"] = args.source
    errs = check_note(rec)
    if errs:
        print("note refused: " + "; ".join(errs))
        return 1
    if args.scope == "project":
        proj = c.need_project(args)
        if proj is None:
            return 1
        item = note_item(rec, c.today())
        path = proj / ".brain" / "memory" / "lessons.jsonl"
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
    path = _writable_session_file(c.BRAIN_ROOT, rec["session"])
    c.append_jsonl(path, rec)
    print(f"note recorded in the inbox ({path.name}); it is reviewed at the next consolidation")
    return 0


def cmd_consolidate(args) -> int:
    delta, rejected = build_consolidation(min_sessions=args.min_sessions)
    if delta is None:
        print("nothing to consolidate: the inbox has no pending files")
        return 0
    counts: dict[str, int] = {}
    for op in delta["ops"]:
        counts[op["op"]] = counts.get(op["op"], 0) + 1
    print(f"delta {delta['id']}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    for r in rejected[:5]:
        print(f"rejected {r}")
    if len(rejected) > 5:
        print(f"rejected {len(rejected) - 5} more")
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
    rows = manifest_rows(root)
    last = rows[-1] if rows else None
    return [
        "items: " + ", ".join(f"{v} {k}" for k, v in counts.items()) + f"; {archived} archived",
        f"items in a conflict: {conflicts}",
        f"inbox: {len(pend)} file(s) pending ({recs} record(s))",
        f"last delta: {last['id']} at {last['at']} ({last['ops_count']} op(s))" if last else "last delta: none yet",
        f"deltas applied: {len(rows)}",
    ]


def cmd_status(args) -> int:
    print("\n".join(status_lines()))
    return 0


def register(sub) -> None:
    p = sub.add_parser("learn", help="the learning pipeline (only writer of the learned zone)")
    s = p.add_subparsers(dest="learn_cmd")

    n = s.add_parser("note", help="record a lesson candidate with evidence")
    n.add_argument("--text", required=True)
    n.add_argument("--class", dest="cls", action="append", default=[], required=True)
    n.add_argument("--evidence", action="append", default=[], required=True)
    n.add_argument("--scope", default="global")
    n.add_argument("--trust", default="observed", choices=TRUST_NOTE)
    n.add_argument("--signal", choices=SIGNALS)
    n.add_argument("--source", help="where an external fact comes from")
    c.add_project_arg(n)
    n.set_defaults(func=cmd_note)

    k = s.add_parser("consolidate", help="turn pending inbox files into one delta and apply it")
    k.add_argument("--dry-run", action="store_true")
    k.add_argument("--min-sessions", type=int, default=2)
    k.set_defaults(func=cmd_consolidate)

    a = s.add_parser("apply", help="apply a delta file (all or nothing)")
    a.add_argument("delta")
    a.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="items allowed per file")
    a.set_defaults(func=cmd_apply)

    s.add_parser("decay", help="demote and retire unused items; flag stale facts").set_defaults(func=cmd_decay)

    d = s.add_parser("digest", help="write the weekly digest (15 lines at most)")
    d.add_argument("--weeks", type=int, default=1)
    d.set_defaults(func=cmd_digest)

    v = s.add_parser("verify", help="CI: replay recorded deltas on the base and compare")
    v.add_argument("--base", help="git ref (default origin/main, else HEAD)")
    v.set_defaults(func=cmd_verify)

    s.add_parser("status", help="what the brain has learned so far").set_defaults(func=cmd_status)
    p.set_defaults(func=cmd_status)
