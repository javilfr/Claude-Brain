"""The requirements ledger and the done report.

Every sentence of a request becomes a line: the owner's exact words, what will
satisfy them ("passes when"), and at the end evidence. Evidence is typed and
the engine resolves it itself (a green gate, a passing run log, a path that
exists, a commit, an address that answers, the owner's words in the
transcript, or the line's stored check run by ``req verify``); any other text
is kept as a note, which proves nothing. ``check`` exits non-zero while any
line is unfinished, so "done" cannot be claimed on a feeling, and ``brain
done`` gives one verdict from tool results. Stored as
``.brain/requirements.jsonl``; ``.brain/REQUIREMENTS.md`` is a generated view.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from . import common as c

BUILD_ON = ("build", "verify", "deliver", "learn", "done")  # stages from which a claim no longer closes a line
PROOF_KINDS = ("gate", "run", "test", "path", "commit", "url", "owner", "check")  # prefixes only the engine writes
NOTE = "note: "
CHECK_OK = "check: exit 0 @"
FORMS = "gate:<id>, run:<log>, test:<name>, a path or path:line, commit:<sha>, url:<address> or owner:<quote>"
MIN_SENTENCE_WORDS = 4  # a request sentence with fewer content words is not held against the ledger


def path(project: Path) -> Path:
    return Path(project) / ".brain" / "requirements.jsonl"


class LedgerError(Exception):
    """The ledger file has a line that cannot be read."""


def load(project: Path) -> list[dict]:
    """Read the ledger strictly. A line that does not parse (a half-written
    file, a merge conflict between two chats) stops everything: skipping it
    would let `check` pass with a requirement missing, and the next write
    would delete that requirement for good."""
    rows = []
    try:
        text = path(project).read_text(encoding="utf-8")
    except FileNotFoundError:
        return rows
    except UnicodeDecodeError as e:
        raise LedgerError(f"requirements.jsonl is not readable text ({c.clip(str(e), 60)})")
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise LedgerError(f"requirements.jsonl line {n} is not valid JSON; repair it (or restore the file from git) before going on")
        if not isinstance(row, dict) or not row.get("id"):
            raise LedgerError(f"requirements.jsonl line {n} is not a requirement (no id)")
        rows.append(row)
    return rows


def guarded(func):
    """Turn a broken ledger into one clear line and exit code 2."""
    def run(args):
        try:
            return func(args)
        except LedgerError as e:
            print(f"requirements: {e}")
            return 2
    return run


def save(project: Path, rows: list[dict]) -> None:
    c.write_jsonl(path(project), rows)
    render(project, rows)
    try:
        # The owner's page shows the requirement counts, so a change here
        # regenerates it. It is a view: failing to write it must not make a
        # ledger write that has already happened look like it failed.
        from .state import write_status
        write_status(project)
    except (ImportError, OSError, ValueError, TypeError, KeyError, AttributeError):
        pass


def render(project: Path, rows: list[dict]) -> None:
    out = ["# Requirements", "", "Generated from `requirements.jsonl` by `brain req`. Each line is the owner's own words, the test for it, and the evidence.", "",
           "| Id | Owner's words | Passes when | Status | Evidence |", "|---|---|---|---|---|"]
    cell = lambda s: c.clip(str(s), 220).replace("|", "\\|")
    for r in rows:
        status = r.get("status", "open")
        ev = r.get("reason", "") if status == "dropped" else "; ".join(evidence_of(r))
        if status == "done" and not verified(r):
            status = "done (not verified)"
        was = r.get("passes_when_was")
        passes = str(r.get("passes_when") or "") + (f" (was: {was[0]})" if isinstance(was, list) and was else "")
        quote = r.get("quote", "")
        if r.get("implied"):
            quote = "(implied) " + quote + (f" — assumed: {r['assumption']}" if r.get("assumption") else "")
        out.append(f"| {r['id']} | {cell(quote)} | {cell(passes)} | {status} | {cell(ev)} |")
    c.write_text(Path(project) / ".brain" / "REQUIREMENTS.md", "\n".join(out) + "\n")


def next_id(rows: list[dict]) -> str:
    nums = [int(r["id"][2:]) for r in rows if str(r.get("id", "")).startswith("R-") and r["id"][2:].isdigit()]
    return f"R-{(max(nums) + 1 if nums else 1):03d}"


def find(rows: list[dict], rid: str) -> dict | None:
    rid = rid.upper()
    return next((r for r in rows if r.get("id") == rid), None)


# ---------------------------------------------------------------- what a line's state is
def evidence_of(r: dict) -> list[str]:
    """The line's evidence items, blanks left out (a hand-edited row may hold
    one string where a list belongs)."""
    ev = r.get("evidence") or []
    return [str(e) for e in (ev if isinstance(ev, list) else [ev]) if str(e).strip()]


def has_check(r: dict) -> bool:
    return bool(str(r.get("check") or "").strip())


def verified(r: dict) -> bool:
    """True when the line holds evidence the engine resolved itself. A line
    with a stored check is proved by that check and nothing else, at any
    stage: the check is the line's own definition of proof."""
    ev = evidence_of(r)
    if has_check(r):
        return any(e.startswith(CHECK_OK) for e in ev)
    return any(e.partition(":")[0] in PROOF_KINDS for e in ev)


def standing(r: dict) -> str:
    """verified, done but not verified, open or dropped."""
    status = r.get("status", "open")
    if status == "done":
        return "verified" if verified(r) else "done but not verified"
    return "dropped" if status == "dropped" else "open"


def summary(rows: list[dict]) -> str:
    """'2 verified, 1 done but not verified, 1 open, 1 dropped' (zero counts left out)."""
    states = [standing(r) for r in rows]
    parts = [f"{states.count(s)} {s}" for s in ("verified", "done but not verified", "open", "dropped") if s in states]
    return ", ".join(parts) or "nothing recorded"


def size_and_stage(project: Path) -> tuple[str, str]:
    from .state import read_state
    st = read_state(project)
    return str(st.get("tier") or c.load_manifest(project).get("tier", "") or ""), str(st.get("stage") or "")


def strict_now(project: Path) -> bool:
    """At project size from the build stage on, a line is done only on
    evidence the engine checked. Before that a note may close a line, and
    `check` reports it as not verified once the build starts."""
    tier, stage = size_and_stage(project)
    return tier in ("2", "3") and stage in BUILD_ON


def work_recorded(project: Path) -> bool:
    """Something has been done on this project: a checkpoint names an item or
    a finished one, or a gate or release is on record."""
    from .state import read_state
    st = read_state(project)
    if any((st.get(k) or "none") != "none" for k in ("item", "last_done")):
        return True
    log = Path(project) / ".brain" / "log"
    return any(c.read_jsonl(log / name) for name in ("gates.jsonl", "releases.jsonl"))


def problems(rows: list[dict], strict: bool = False) -> list[str]:
    """Why the lines do not yet allow 'done'. A done line with a stored check
    that has not passed on record is always a problem; with ``strict``, so is
    a line closed on a note."""
    out = []
    for r in rows:
        status = r.get("status", "open")
        if status == "dropped":
            if not r.get("reason"):
                out.append(f"{r['id']}: dropped without a reason")
            continue
        if not r.get("passes_when"):
            out.append(f"{r['id']}: no 'passes when' (how will this be checked?)")
        if status != "done":
            out.append(f"{r['id']}: open — {c.clip(r.get('quote', ''), 70)}")
        elif not evidence_of(r):
            out.append(f"{r['id']}: marked done with no evidence")
        elif (strict or has_check(r)) and not verified(r):
            fix = (f"its check has not passed on record; run `brain req verify {r['id']}`" if has_check(r)
                   else f"its evidence is a note; attach evidence the engine can check, or set a check and run `brain req verify {r['id']}`")
            out.append(f"{r['id']}: done but not verified: {fix}")
    return out


# ---------------------------------------------------------------- the request itself
def request_path(project: Path) -> Path:
    return Path(project) / ".brain" / "log" / "request.jsonl"


def sentences(text: str) -> list[str]:
    """The sentences of a request: split at sentence ends, line breaks and
    semicolons, list markers removed, anything without a word left out."""
    out = []
    for part in re.split(r"(?<=[.!?])\s+|\s*[\n;]\s*", text or ""):
        part = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", part).strip()
        if c.words(part):
            out.append(c.clip(part, 2000))
    return out


def record_request(project: Path, text: str) -> int:
    """Store the sentences of the owner's request in the project
    (``.brain/log/request.jsonl``), each once; returns how many were new.
    `check` then holds the ledger against them. Anything shaped like a
    credential is stored as ``[redacted]``. Project data stays in the project."""
    have = {" ".join(str(r.get("text", "")).casefold().split()) for r in c.read_jsonl(request_path(project))}
    new = 0
    for s in sentences(c.redact_secrets(text or "")):
        key = " ".join(s.casefold().split())
        if key in have:
            continue
        have.add(key)
        c.append_jsonl(request_path(project), {"at": c.now_iso(), "session": c.session_id(), "text": s})
        new += 1
    return new


def uncovered(project: Path, rows: list[dict]) -> list[str]:
    """Stored request sentences that no ledger line holds. A line counts for a
    sentence when its quote is drawn from it or contains it (four fifths of
    the shorter one's content words are shared); the sentence is held when
    such lines, whatever their status, carry at least half of its content
    words. Words, not exact text, because the owner dictates and a quote may
    fix his spelling."""
    quotes = [set(c.words(str(r.get("quote", "")))) for r in rows]
    out = []
    for rec in c.read_jsonl(request_path(project)):
        text = str(rec.get("text", ""))
        want = set(c.words(text))
        if len(want) < MIN_SENTENCE_WORDS:
            continue
        held: set[str] = set()
        for q in quotes:
            if q and len(q & want) >= 0.8 * min(len(q), len(want)):
                held |= q & want
        if len(held) < 0.5 * len(want):
            out.append(text)
    return out


def ledger_problems(project: Path, rows: list[dict], strict_mode: bool | None = None) -> list[str]:
    """Everything that stops 'done' for this project: what only the project
    knows (its size, its stage, the stored request) first, then the lines.
    ``strict_mode`` overrides the stage rule (``brain done`` is always strict)."""
    tier, stage = size_and_stage(project)
    out = []
    if tier in ("2", "3"):
        missing = uncovered(project, rows)
        for n, s in enumerate(missing[:3]):
            out.append(f"request sentence not in the ledger: “{c.clip(s, 100)}”" + ("" if n else " (add it with `brain req add --quote`; if it is not wanted, add it and drop it with a reason)"))
        if len(missing) > 3:
            out.append(f"… {len(missing) - 3} more sentence(s) of the request are missing too (.brain/log/request.jsonl)")
        if rows and all(r.get("status") == "dropped" for r in rows):
            out.append("every line is dropped, so nothing of the request is left: reopen what still stands (`brain req reopen <id> --reason …`) or tell the owner")
        if not rows and not missing and (strict_mode or stage in BUILD_ON or work_recorded(project)):
            out.append("the ledger is empty at project size; add the request's sentences with `brain req add` before calling anything done")
    return out + problems(rows, strict_now(project) if strict_mode is None else strict_mode)


def dropped_lines(rows: list[dict], limit: int = 3) -> list[str]:
    """One line per dropped requirement, with its reason: a drop narrows the
    request, so it is said every time, not counted."""
    gone = [r for r in rows if r.get("status") == "dropped"]
    out = [f"dropped {r['id']} “{c.clip(r.get('quote', ''), 60)}”: {c.clip(r.get('reason') or 'no reason given', 80)}" for r in gone[:limit]]
    if len(gone) > limit:
        out.append(f"… {len(gone) - limit} more dropped (all in .brain/REQUIREMENTS.md)")
    return out


def status_lines(project: Path) -> list[str]:
    """What the owner's status page says about requirements: one line of
    counts that keeps 'verified' apart from 'done but not verified', then up
    to five dropped lines with their reasons. Empty for an empty ledger."""
    try:
        rows = load(project)
    except LedgerError:
        return ["- Requirements: the ledger cannot be read (`brain req check` says why)"]
    if not rows:
        return []
    gone = [r for r in rows if r.get("status") == "dropped"]
    out = [f"- Requirements: {summary(rows)} (of {len(rows)})"]
    out += [f"- Dropped: {r['id']} “{c.clip(r.get('quote', ''), 70)}” — {c.clip(r.get('reason') or 'no reason given', 90)}" for r in gone[:5]]
    if len(gone) > 5:
        out.append(f"- … {len(gone) - 5} more dropped: see `.brain/REQUIREMENTS.md`")
    return out


# ---------------------------------------------------------------- evidence the engine resolves
def _log_text(log: Path, limit: int) -> str:
    """The start of a run log; a cap, because a log can be hundreds of megabytes."""
    try:
        with open(log, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit)
    except OSError:
        return ""


def _log_exit(log: Path) -> int | None:
    """The exit code in the header `brain run` writes under the command."""
    m = re.search(r"^\[exit (-?\d+) in ", _log_text(log, 65536), re.M)
    return int(m[1]) if m else None


def _path_evidence(project: Path, text: str) -> tuple[str, str]:
    """(evidence, "") for a file or folder inside the project, optionally
    ``path:line``; ("", why) when the file is there but the line is not;
    ("", "") when there is no such path. A name is also looked for under the
    manifest's ``paths.evidence``. A file is stored with a hash of its
    content, so the record still means something when the file changes."""
    root = Path(project).resolve()
    paths = c.load_manifest(project).get("paths")
    ev_dir = paths.get("evidence") if isinstance(paths, dict) else ""
    bases = [root] + ([root / ev_dir] if isinstance(ev_dir, str) and ev_dir.strip() else [])
    name, _, line = text.rpartition(":")
    for cand, want in [(text, None)] + ([(name, int(line))] if name and re.fullmatch(r"[0-9]{1,7}", line) else []):
        for base in bases:
            try:
                hit = (base / cand).resolve()
                if not hit.exists() or root not in hit.parents:
                    continue
                rel = hit.relative_to(root).as_posix()
                if hit.is_dir():
                    return f"path:{rel}/", ""
                if want is not None:
                    with open(hit, "rb") as f:
                        have = sum(1 for _ in f)
                    if not 1 <= want <= have:
                        return "", f"{rel} has no line {want} (it has {have})"
                return f"path:{rel}" + (f":{want}" if want is not None else "") + f" #{c.sha256_file(hit)[:12]}", ""
            except (OSError, ValueError):  # a name too long or otherwise not a path: free text
                continue
    return "", ""


def _gate_evidence(project: Path, gid: str) -> tuple[str, str]:
    """A gate proves a line only when its latest run is green, was made by
    this session, on a clean tree, and the work has not changed since."""
    from . import gate
    recs = [r for r in c.read_jsonl(gate.gates_path(project)) if str(r.get("gate") or "") == gid]
    again = f"run `brain gate {gid}` and attach it again"
    if not recs:
        return "", f"no run of gate {gid!r} is recorded; {again}"
    r = recs[-1]
    commit = str(r.get("commit") or "")
    if r.get("exit") != 0:
        return "", f"gate {gid} last exited {r.get('exit')}; fix it, then {again}"
    if str(r.get("session", "")) != c.session_id():
        return "", f"the last run of gate {gid} was not by this session; {again}"
    if r.get("dirty"):
        return "", f"gate {gid} ran with uncommitted changes; commit, then {again}"
    if not gate.same_work(project, commit, gate.head_commit(project)):
        return "", f"gate {gid} passed on {commit[:7] or 'no commit'} and the work has changed since; {again}"
    return f"gate:{gid} exit 0 @{commit[:7]}", ""


def _run_evidence(project: Path, token: str) -> tuple[str, str]:
    from . import gate
    log = gate.log_dir(project) / Path(token).name
    if not log.is_file():
        return "", f"no run log {Path(token).name!r} in .brain/log/run/ (`brain run -- <command>` writes one)"
    code = _log_exit(log)
    if code != 0:
        return "", f"run log {log.name} ended with exit {code}, which proves nothing; fix the cause and run it again"
    return f"run:{log.name} exit 0 #{c.sha256_file(log)[:12]}", ""


def _test_evidence(project: Path, name: str) -> tuple[str, str]:
    from . import gate
    if len(name) >= 3:
        for log in sorted(gate.log_dir(project).glob("*.log"), reverse=True)[:30]:
            if _log_exit(log) == 0 and name in _log_text(log, 4_000_000):
                return f"test:{name} in {log.name}", ""
    return "", f"{name!r} is not in the output of any passing run in .brain/log/run/; run it with `brain run -- <command>` so its name is printed"


def _commit_evidence(project: Path, token: str) -> tuple[str, str]:
    from .state import git
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", token):
        return "", "commit: takes a commit id (7 to 40 hex characters, from `git log`)"
    full = git(project, "rev-parse", "--verify", "--quiet", token + "^{commit}")
    if not full:
        return "", f"no commit {token} in this project"
    return f"commit:{full[:12]} {c.clip(git(project, 'log', '-1', '--format=%s', full), 60)}".rstrip(), ""


def _url_evidence(url: str) -> tuple[str, str]:
    from . import gate
    if not re.fullmatch(r"https?://\S+", url):
        return "", "url: takes an http or https address"
    if os.environ.get("BRAIN_NO_NETWORK"):
        return f"{NOTE}url:{url} (not checked: the network is switched off)", ""
    ok, msg = gate.check_live(url, wait_seconds=0)  # one bounded try, no polling
    if not ok:
        return "", f"{url} did not answer ({msg})"
    return f"url:{url} {msg.replace('live address ', '')} on {c.today()}", ""


def _owner_evidence(quote: str) -> tuple[str, str]:
    from . import learn
    ev, why = learn.verify_owner_quote(quote)
    return (f'{ev} "{c.clip(quote, 80)}"', "") if ev else ("", f"owner: {why}")


def resolve(project: Path, text: str) -> tuple[str, str]:
    """(what to store, "") for one evidence item, or ("", why it is refused).

    A typed item (``gate:``, ``run:``, ``test:``, ``path:``, ``commit:``,
    ``url:``, ``owner:``) must resolve or it is refused: a pointer at nothing
    is worse than no pointer. Untyped text that names an existing path is
    path evidence. Anything else is kept as a note, which proves nothing."""
    e = " ".join(str(text).split())
    if not e:
        return "", "evidence is empty; give " + FORMS
    kind, sep, rest = e.partition(":")
    kind, rest = kind.strip().lower(), rest.strip()
    token = (rest.split() or [""])[0]
    if re.match(r"https?://", e):
        return _url_evidence(e.split()[0])
    if sep and kind == "check":
        return "", "check: evidence is written only by `brain req verify <id>`, which runs the line's stored check"
    if sep and kind == "note":
        return (NOTE + c.clip(rest, 230), "") if rest else ("", "evidence is empty; give " + FORMS)
    if sep and kind in ("gate", "run", "test", "path", "file", "commit", "url", "owner"):
        if not rest:
            return "", f"{kind}: needs a value"
        if kind == "gate":
            return _gate_evidence(project, token)
        if kind == "run":
            return _run_evidence(project, token)
        if kind == "test":
            return _test_evidence(project, token)
        if kind == "commit":
            return _commit_evidence(project, token)
        if kind == "url":
            return _url_evidence(token)
        if kind == "owner":
            return _owner_evidence(rest)
        found = _path_evidence(project, rest)
        if not any(found) and token != rest:
            found = _path_evidence(project, token)
        if not any(found):
            return "", f"no such path in the project: {c.clip(rest, 80)}"
    else:
        found = _path_evidence(project, e)
        if not any(found):
            return NOTE + c.clip(e, 230), ""
    stored, why = found
    if stored.startswith("path:.brain/log/run/"):  # the path `brain run` prints: it has to be a passing run
        return _run_evidence(project, stored.split()[0])
    return stored, why


# ---------------------------------------------------------------- cli
def _secret(*texts) -> str:
    """The refusal line when any of the texts holds a credential, else ""."""
    return c.secret_problem(" \n ".join(str(t) for t in texts if t))


def _history(value) -> list:
    return list(value) if isinstance(value, list) else []


def _parse_line(text: str) -> dict:
    """One ledger line from ``words :: passes when :: check`` (the last two
    optional) or from a JSON object with the same names as the flags."""
    text = text.strip()
    if text.startswith("{"):
        try:
            d = json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("is not valid JSON")
        if not isinstance(d, dict):
            raise ValueError("is not a JSON object")
        return {"quote": str(d.get("quote") or ""), "passes_when": str(d.get("passes_when") or d.get("passes-when") or ""),
                "check": str(d.get("check") or ""), "implied": bool(d.get("implied")), "assumption": str(d.get("assumption") or "")}
    parts = [p.strip() for p in re.split(r"\s+::\s+", f" {text} ", maxsplit=2)] + ["", ""]
    return {"quote": parts[0], "passes_when": parts[1], "check": parts[2], "implied": False, "assumption": ""}


def cmd_add(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    specs = []
    if args.quote:
        specs.append({"quote": args.quote, "passes_when": args.passes_when or "", "check": args.check or "", "implied": False, "assumption": args.assumption or ""})
    lines = list(args.line or [])
    if args.from_file:
        try:
            lines += [l for l in Path(args.from_file).read_text(encoding="utf-8").splitlines() if l.strip() and not l.lstrip().startswith("#")]
        except (OSError, UnicodeDecodeError) as e:
            print(f"cannot read {args.from_file} ({c.clip(str(e), 60)}); nothing added")
            return 1
    for n, line in enumerate(lines, 1):
        try:
            specs.append(_parse_line(line))
        except ValueError as e:
            print(f"line {n} {e}; nothing added")
            return 1
    if not specs:
        print('nothing to add: give --quote "<his words>", or several lines at once with --line "<his words> :: <passes when> :: <check>" or --from <file>')
        return 1
    for n, s in enumerate(specs, 1):
        s["quote"] = " ".join(s["quote"].split())
        if not s["quote"]:
            print(f"line {n} has no words before the first ' :: '; nothing added")
            return 1
        bad = _secret(s["quote"], s["passes_when"], s["check"], s["assumption"])
        if bad:
            print(f"{bad} (nothing added)")
            return 1
    added, bare = [], []
    for s in specs:
        if any(r.get("quote") == s["quote"] for r in rows):
            continue
        row = {"id": next_id(rows), "quote": s["quote"], "passes_when": s["passes_when"].strip(),
               "check": s["check"].strip(), "status": "open", "evidence": [], "added": c.today()}
        if args.implied or s["implied"]:
            # Not the owner's words: something the request needs in order to hold.
            # Kept apart so an assumption is never mistaken for an instruction.
            row["implied"] = True
            if s["assumption"].strip():
                row["assumption"] = s["assumption"].strip()
        rows.append(row)
        added.append(row["id"])
        if not row["passes_when"]:
            bare.append(row["id"])
    if not added:
        print("already in the ledger (same words); nothing added")
        return 0
    save(project, rows)
    if len(specs) == 1:
        print(f"{added[0]} added" + (" (no 'passes when' yet)" if bare else ""))
        return 0
    skipped = len(specs) - len(added)
    print(f"{added[0]} to {added[-1]} added ({len(added)} line(s))" + (f"; {skipped} already in the ledger" if skipped else "")
          + (f"; no 'passes when' yet: {', '.join(bare[:6])}" + (" …" if len(bare) > 6 else "") if bare else ""))
    return 0


def cmd_set(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    r = find(rows, args.id)
    if not r:
        print(f"no requirement {args.id}")
        return 1
    bad = _secret(args.passes_when, args.check)
    if bad:
        print(bad)
        return 1
    if r.get("status") == "done" and (args.passes_when or args.check is not None):
        print(f"{r['id']} is done: changing its test now would move the goal after the fact. `brain req reopen {r['id']} --reason \"…\"` first")
        return 1
    was = ""
    if args.passes_when and args.passes_when.strip() != r.get("passes_when", ""):
        if r.get("passes_when"):
            # A rewritten test is kept: the first wording is what was agreed.
            r["passes_when_was"] = _history(r.get("passes_when_was")) + [r["passes_when"]]
            was = f" (passes-when was: {c.clip(r['passes_when'], 90)})"
        r["passes_when"] = args.passes_when.strip()
    if args.check is not None and args.check.strip() != r.get("check", ""):
        if r.get("check"):
            r["check_was"] = _history(r.get("check_was")) + [r["check"]]
            was += f" (check was: {c.clip(r['check'], 90)})"
        r["check"] = args.check.strip()
        r["evidence"] = [e for e in evidence_of(r) if not e.startswith("check: ")]  # a result of the old command
    save(project, rows)
    print(f"{r['id']} updated{was}")
    return 0


def cmd_evidence(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    r = find(rows, args.id)
    if not r:
        print(f"no requirement {args.id}")
        return 1
    if not args.evidence and not args.done:
        print(f"{r['id']}: nothing given; attach evidence ({FORMS}) or pass --done")
        return 1
    ev, notes = evidence_of(r), 0
    for raw in args.evidence:
        bad = _secret(raw)
        if bad:
            print(bad)
            return 1
        stored, why = resolve(project, raw)
        if why:
            print(f"{r['id']}: refused, nothing stored: {why}")
            return 1
        notes += stored.startswith(NOTE)
        if stored not in ev:
            ev.append(stored)
    if args.done:
        if not r.get("passes_when"):
            print(f"{r['id']}: cannot mark done without a 'passes when'")
            return 1
        if not ev:
            print(f"{r['id']}: cannot mark done with no evidence; attach {FORMS}")
            return 1
        if (has_check(r) or strict_now(project)) and not verified(dict(r, evidence=ev)):
            if has_check(r):
                why = f"this line has a stored check, and only that check closes it: run `brain req verify {r['id']}`"
            else:
                note = next((e for e in ev if e.partition(":")[0] not in PROOF_KINDS), "")
                why = (f"“{c.clip(note.removeprefix(NOTE), 90)}” is a note, and a note is not evidence at project size. "
                       f"Give {FORMS}; or set a check and run `brain req verify {r['id']}`")
            print(f"{r['id']}: not marked done, nothing stored: {why}")
            return 1
        r["status"], r["done"] = "done", c.today()
        r.pop("reason", None)  # a line closed after a drop is no longer dropped for that reason
    r["evidence"] = ev
    save(project, rows)
    print(f"{r['id']}: {len(ev)} evidence item(s), status {r.get('status', 'open')}" + (f" ({notes} kept as a note, which proves nothing)" if notes else ""))
    return 0


def cmd_verify(args) -> int:
    """Run stored checks and let their exit codes decide: exit 0 records
    ``check: exit 0 @<commit> <log>`` and closes the line; anything else
    leaves it open, and reopens a line that was done."""
    project = c.need_project(args)
    if not project:
        return 1
    from . import gate
    rows = load(project)
    if args.id:
        r = find(rows, args.id)
        if not r:
            print(f"no requirement {args.id}")
            return 1
        if r.get("status") == "dropped":
            print(f"{r['id']} is dropped; `brain req reopen {r['id']} --reason \"…\"` first")
            return 1
        if not has_check(r):
            print(f"{r['id']} has no check; set one with `brain req set {r['id']} --check \"<command>\"`, or attach evidence ({FORMS})")
            return 1
        targets = [r]
    else:
        targets = [r for r in rows if r.get("status") != "dropped"]
    stamp = (gate.head_commit(project)[:7] or "no-commit") + ("+uncommitted" if gate.tree_dirty(project) else "")
    ran: dict[str, dict] = {}
    passed, failed, unset, nocheck = [], [], [], []
    for r in targets:
        command = str(r.get("check") or "").strip()
        if not command:
            nocheck.append(r["id"])
            continue
        if command not in ran:  # lines that share a command share one run
            ran[command] = gate.run_filtered(command, project, project, timeout=args.timeout)
        res = ran[command]
        r["evidence"] = [e for e in evidence_of(r) if not e.startswith("check: ")]
        if res["exit"] == 0:
            r["evidence"].append(f"{CHECK_OK}{stamp} {Path(res['log']).name}")
            if r.get("passes_when"):
                r["status"], r["done"] = "done", c.today()
                passed.append(r["id"])
            else:
                unset.append(r["id"])
        else:
            if r.get("status") == "done":
                r["status"], r["reopened"] = "open", f"{c.today()} (was done): its check exited {res['exit']}"
                r.pop("done", None)
            failed.append(r["id"])
            if len(failed) <= 6:
                print(f"{r['id']}: check FAILED (exit {res['exit']}), the line is open · full output: .brain/log/run/{Path(res['log']).name}")
    if ran:
        save(project, rows)
    if not ran:
        print("verify: no line has a check; set one with `brain req set <id> --check \"<command>\"`")
        return 0
    print(f"verify: {len(passed)} passed and done, {len(failed)} failed" + (f" ({', '.join(failed[6:12])} not shown above)" if len(failed) > 6 else "")
          + (f"; passed but still open for lack of a 'passes when': {', '.join(unset[:5])}" if unset else "")
          + (f"; {len(nocheck)} line(s) have no check" if nocheck else ""))
    return 1 if failed else 0


def cmd_drop(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    r = find(rows, args.id)
    if not r:
        print(f"no requirement {args.id}")
        return 1
    bad = _secret(args.reason)
    if bad:
        print(bad)
        return 1
    r["status"], r["reason"] = "dropped", args.reason.strip()
    save(project, rows)
    print(f"{r['id']} dropped: {r['reason']}")
    return 0


def cmd_reopen(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    r = find(rows, args.id)
    if not r:
        print(f"no requirement {args.id}")
        return 1
    bad = _secret(args.reason)
    if bad:
        print(bad)
        return 1
    was = r.get("status", "open")
    if was == "open":
        print(f"{r['id']} is already open")
        return 0
    # The old evidence proved the old claim; kept, it would close the line
    # again without a new look. Git history still has it.
    r["status"], r["evidence"] = "open", []
    r["reopened"] = f"{c.today()} (was {was}): {args.reason.strip()}"
    r.pop("done", None)
    r.pop("reason", None)
    save(project, rows)
    print(f"{r['id']} reopened (was {was})" + ("; its evidence was cleared" if was == "done" else ""))
    return 0


def cmd_list(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    shown = [r for r in rows if not args.open or r.get("status", "open") == "open"]
    if not shown:
        print("ledger is empty" if not rows else "no open requirements")
        return 0
    for r in shown[: args.limit]:
        tag = "done, not verified" if standing(r) == "done but not verified" else r.get("status", "open")
        print(f"{r['id']} [{tag}] {c.clip(r.get('quote', ''), 90)}" + (f" → {c.clip(r['passes_when'], 70)}" if r.get("passes_when") else ""))
    if len(shown) > args.limit:
        print(f"… {len(shown) - args.limit} more (see .brain/REQUIREMENTS.md)")
    return 0


def cmd_check(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rows = load(project)
    probs = ledger_problems(project, rows)
    if not rows and not probs:
        print("requirements: ledger is empty (fine for an answer or a small task)")
        return 0
    if len(probs) == 1:
        print(f"requirements: {summary(rows)}; not finished: {probs[0]}")
    elif probs:
        print(f"requirements: {summary(rows)}; not finished:")
        for p in probs[:8]:
            print(" -", p)
        if len(probs) > 8:
            print(f" … {len(probs) - 8} more (brain req list --open)")
    else:
        soft = [r["id"] for r in rows if standing(r) == "done but not verified"]
        print(f"requirements: ok, all {len(rows)} line(s) are done or dropped with a reason ({summary(rows)})"
              + (f"; {', '.join(soft[:5])}{' …' if len(soft) > 5 else ''} done on a note only, which `brain done` and the build stage refuse" if soft else ""))
    for line in dropped_lines(rows):
        print(line)
    return 1 if probs else 0


def cmd_intake(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    text = " ".join(args.request)
    new = record_request(project, text)
    missing = len(uncovered(project, load(project))) if size_and_stage(project)[0] in ("2", "3") else 0
    print(f"intake: {new} new sentence(s) of the request stored" + (" (a credential in it was left out)" if c.secret_problem(text) else "")
          + (f"; {missing} still need a ledger line (`brain req check` names them)" if missing else ""))
    return 0


# ---------------------------------------------------------------- the done report
def done_report(project: Path) -> dict:
    """One verdict from tool results: the strict requirement check, the gates
    on the current work, the tree and push state, and what waits for the
    owner. Reads only; nothing is written."""
    from . import gate, state
    rows = load(project)
    order = {"open": 0, "done but not verified": 1, "verified": 2}
    lines = sorted((r for r in rows if r.get("status") != "dropped"), key=lambda r: order[standing(r)])
    reasons = ledger_problems(project, rows, True)
    gates = c.load_manifest(project).get("gates")
    has_gate = any(isinstance(g, dict) and g.get("kind") == "command" and str(g.get("command") or "").strip() for g in (gates if isinstance(gates, list) else []))
    gate_why = [] if not has_gate else gate.green_at_head(project)[1]
    tree = state.repo_cleanliness(project)
    needs = state.open_needs(project)
    reasons += gate_why + tree
    return {"done": not reasons, "reasons": reasons,
            "requirements": [{"id": r["id"], "state": "not done" if standing(r) == "open" else standing(r), "quote": r.get("quote", ""),
                              "evidence": next((e for e in evidence_of(r) if not e.startswith(NOTE)), "")} for r in lines],
            "dropped": sum(r.get("status") == "dropped" for r in rows),
            "gates": "no command gate is defined" if not has_gate else "green on this commit" if not gate_why else gate_why[0],
            "tree": tree, "needs_you": len(needs)}


def cmd_done(args) -> int:
    project = c.need_project(args)
    if not project:
        return 1
    rep = done_report(project)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False))
        return 0 if rep["done"] else 1
    reqs = rep["requirements"]
    shown = reqs if len(reqs) <= 8 else reqs[:7]
    for r in shown:
        print(f"{r['state']}: {r['id']} {c.clip(r['quote'], 70)}" + (f" · {c.clip(r['evidence'], 60)}" if r["state"] == "verified" and r["evidence"] else ""))
    rest = [r["state"] for r in reqs[len(shown):]]
    if rest:
        print(f"… {len(rest)} more: " + ", ".join(f"{rest.count(s)} {s}" for s in ("not done", "done but not verified", "verified") if s in rest) + " (brain req list)")
    print(("requirements: none recorded · " if not reqs and not rep["dropped"] else "") + f"gates: {c.clip(rep['gates'], 70)} · tree: {c.clip('; '.join(rep['tree']), 60) or 'clean and pushed'}"
          + (f" · dropped: {rep['dropped']} (brain req check lists them)" if rep["dropped"] else ""))
    waits = f"{rep['needs_you']} item(s) wait for the owner in NEEDS_YOU.md" if rep["needs_you"] else ""
    if rep["done"]:
        print("DONE" + (f" · {waits}" if waits else ""))
        return 0
    more = len(rep["reasons"]) - 1
    print(f"NOT DONE: {c.clip(rep['reasons'][0], 150)}" + (f" (+{more} more)" if more else "") + (f" · {waits}" if waits else ""))
    return 1


def register(sub) -> None:
    p = sub.add_parser("req", help="the requirements ledger: add, list, evidence, verify, drop, reopen, check")
    s = p.add_subparsers(dest="req_cmd")
    a = s.add_parser("add", help="add a line with the owner's exact words (several with --line or --from)")
    c.add_project_arg(a)
    a.add_argument("--quote", help="his exact words")
    a.add_argument("--passes-when", dest="passes_when")
    a.add_argument("--check", help="command that verifies it; `req verify` runs it")
    a.add_argument("--implied", action="store_true", help="not the owner's words: a need the request implies")
    a.add_argument("--assumption", help="with --implied: what was assumed and why")
    a.add_argument("--line", action="append", help='one more line as "<his words> :: <passes when> :: <check>"; repeat the flag')
    a.add_argument("--from", dest="from_file", help="a file with one such line (or one JSON object) per row")
    a.set_defaults(func=guarded(cmd_add))
    a = s.add_parser("set", help="set 'passes when' or the check for a line that is not done")
    c.add_project_arg(a)
    a.add_argument("id")
    a.add_argument("--passes-when", dest="passes_when")
    a.add_argument("--check", help='command that verifies it ("" removes it)')
    a.set_defaults(func=guarded(cmd_set))
    a = s.add_parser("evidence", help=f"attach evidence the engine can check ({FORMS}); other text is kept as a note; --done marks the line done")
    c.add_project_arg(a)
    a.add_argument("id")
    a.add_argument("evidence", nargs="*")
    a.add_argument("--done", action="store_true")
    a.set_defaults(func=guarded(cmd_evidence))
    a = s.add_parser("verify", help="run the stored check of one line or of every line; exit 0 closes a line, anything else leaves it open")
    c.add_project_arg(a)
    a.add_argument("id", nargs="?")
    a.add_argument("--timeout", type=int, default=900, help="seconds allowed for each check")
    a.set_defaults(func=guarded(cmd_verify))
    a = s.add_parser("drop", help="drop a line with a reason")
    c.add_project_arg(a)
    a.add_argument("id")
    a.add_argument("--reason", required=True)
    a.set_defaults(func=guarded(cmd_drop))
    a = s.add_parser("reopen", help="put a done or dropped line back to open, with a reason")
    c.add_project_arg(a)
    a.add_argument("id")
    a.add_argument("--reason", required=True)
    a.set_defaults(func=guarded(cmd_reopen))
    a = s.add_parser("list")
    c.add_project_arg(a)
    a.add_argument("--open", action="store_true")
    a.add_argument("--limit", type=int, default=15)
    a.set_defaults(func=guarded(cmd_list))
    a = s.add_parser("check", help="exit non-zero while any line is unfinished or the request is not all in the ledger")
    c.add_project_arg(a)
    a.set_defaults(func=guarded(cmd_check))
    a = s.add_parser("intake", help="store the sentences of the owner's request, so `check` can hold the ledger against them")
    c.add_project_arg(a)
    a.add_argument("request", nargs="+")
    a.set_defaults(func=guarded(cmd_intake))
    p.set_defaults(func=guarded(cmd_list), project=None, open=False, limit=15)
    d = sub.add_parser("done", help="one verdict from tool results: requirements, gates, tree and push state (at most 10 lines)")
    c.add_project_arg(d)
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=guarded(cmd_done))
