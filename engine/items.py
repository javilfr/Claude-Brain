"""Memory items: one schema for rules, pitfalls, facts, preferences and playbook lines.

Files (JSONL, one item per line):
  brain:   memory/items.jsonl, memory/facts.jsonl, owner/standing.jsonl,
           owner/preferences.jsonl, playbooks/<family>.jsonl
  project: .brain/memory/*.jsonl   (scope "project")

Optional fields (round2/01 sections 3.6, 3.7, 3.15):
  valid_from, valid_to  ISO dates; facts are bi-temporal, a superseded item
                        gets ``valid_to`` and stays on disk as history;
  superseded_by         ids of the items that replaced this one;
  by_model              model that wrote the lesson, because memory written
                        by a stronger model can mislead a weaker one.
A ``pitfall`` is a rule learned from a failure that was later fixed; like a
rule it can never come from text that was merely read.
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

from . import common as c

TYPES = ("rule", "pitfall", "fact", "preference", "standing", "playbook")
TRUST = ("owner-stated", "observed", "derived", "seed", "external")
STATUS = ("candidate", "probation", "active", "demoted", "retired")
FAMILIES = ("software", "data", "knowledge", "language", "operations", "career")
MAX_TEXT = 400
ID_RE = re.compile(r"^[a-z]{2,8}-[a-z0-9][a-z0-9-]{1,60}$")
SCOPE_RE = re.compile(r"^(global|project|family:(%s))$" % "|".join(FAMILIES))
MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,60}$")

# Prior (helpful, harmful) pseudo-counts by trust: what you stated starts strong.
PRIOR = {"owner-stated": (8, 0), "observed": (2, 1), "seed": (2, 1), "derived": (1, 1), "external": (1, 1)}

DEFAULTS = {
    "class": [], "evidence": [], "provenance": "", "importance": 2, "helpful": 0, "harmful": 0,
    "uses": 0, "sessions": 0, "projects": 0, "last_used": "", "status": "active",
    "supersedes": [], "conflicts": [],
}

BRAIN_FILES = ("memory/items.jsonl", "memory/facts.jsonl", "owner/standing.jsonl", "owner/preferences.jsonl")


def confidence(item: dict) -> float:
    """Mean of a Beta posterior over 'this item helps', from counters and trust."""
    a0, b0 = PRIOR.get(item.get("trust", "derived"), (1, 1))
    h = max(0, int(item.get("helpful", 0) or 0))
    x = max(0, int(item.get("harmful", 0) or 0))
    return round((h + a0 + 1) / (h + x + a0 + b0 + 2), 3)


def normalise(item: dict) -> dict:
    out = dict(DEFAULTS)
    out.update({k: v for k, v in item.items() if not k.startswith("_")})
    return out


def _date(v) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def validate_item(item: dict) -> list[str]:
    """Problems with one item; empty list means valid."""
    errs: list[str] = []
    iid = str(item.get("id", ""))
    if not ID_RE.match(iid):
        errs.append(f"bad id {iid!r}")
    if item.get("type") not in TYPES:
        errs.append(f"{iid}: type must be one of {TYPES}")
    if not SCOPE_RE.match(str(item.get("scope", ""))):
        errs.append(f"{iid}: scope must be global, project or family:<{'|'.join(FAMILIES)}>")
    text = item.get("text", "")
    if not isinstance(text, str) or not text.strip():
        errs.append(f"{iid}: text is empty")
    elif len(text) > MAX_TEXT:
        errs.append(f"{iid}: text is {len(text)} characters (limit {MAX_TEXT})")
    if item.get("trust") not in TRUST:
        errs.append(f"{iid}: trust must be one of {TRUST}")
    if item.get("status", "active") not in STATUS:
        errs.append(f"{iid}: status must be one of {STATUS}")
    if item.get("importance", 2) not in (1, 2, 3):
        errs.append(f"{iid}: importance must be 1, 2 or 3")
    for k in ("class", "evidence", "supersedes", "conflicts", "superseded_by"):
        if not isinstance(item.get(k, []), list):
            errs.append(f"{iid}: {k} must be a list")
    for k in ("helpful", "harmful", "uses", "sessions", "projects"):
        v = item.get(k, 0)
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            errs.append(f"{iid}: {k} must be a non-negative integer")
    if not item.get("created"):
        errs.append(f"{iid}: created date missing")
    for k in ("valid_from", "valid_to"):
        if item.get(k) is not None and _date(item[k]) is None:
            errs.append(f"{iid}: {k} must be an ISO date (YYYY-MM-DD)")
    vf, vt = _date(item.get("valid_from")), _date(item.get("valid_to"))
    if vf and vt and vt < vf:
        errs.append(f"{iid}: valid_to is before valid_from")
    if "by_model" in item and not MODEL_RE.match(str(item["by_model"])):
        errs.append(f"{iid}: by_model must be a model id or alias")
    if item.get("type") == "fact" and item.get("trust") == "external" and not item.get("source"):
        errs.append(f"{iid}: an external fact needs a source")
    # Text that was only read (web pages, project files, tool output) can supply
    # facts, never rules: this is the defence against planted instructions.
    if item.get("trust") == "external" and item.get("type") != "fact":
        errs.append(f"{iid}: external-trust text cannot be a {item.get('type')}")
    if item.get("type") != "fact" and not item.get("provenance") and not item.get("evidence"):
        errs.append(f"{iid}: needs evidence or provenance")
    blob = " ".join(str(item.get(k, "")) for k in ("text", "provenance", "source")) + " ".join(map(str, item.get("evidence", [])))
    if c.find_secrets(blob):
        errs.append(f"{iid}: looks like it contains a secret")
    if c.EMAIL_PATTERN.search(blob):
        errs.append(f"{iid}: contains an email address")
    return errs


def brain_item_files(brain_root: Path | None = None) -> list[Path]:
    root = Path(brain_root or c.BRAIN_ROOT)
    files = [root / f for f in BRAIN_FILES]
    files += sorted((root / "playbooks").glob("*.jsonl"))
    return [f for f in files if f.is_file()]


def project_item_files(project: Path | None) -> list[Path]:
    if not project:
        return []
    return sorted((Path(project) / ".brain" / "memory").glob("*.jsonl"))


def load_items(brain_root: Path | None = None, project: Path | None = None, include_inactive: bool = False) -> list[dict]:
    """All items with ``_file`` and ``_confidence`` added. Demoted and retired
    items are left out unless asked for."""
    out = []
    root = Path(brain_root or c.BRAIN_ROOT)
    for f in brain_item_files(root) + project_item_files(project):
        for raw in c.read_jsonl(f):
            it = normalise(raw)
            if not include_inactive and it["status"] in ("demoted", "retired"):
                continue
            try:
                it["_file"] = str(f.relative_to(root))
            except ValueError:
                it["_file"] = str(f)
            it["_confidence"] = confidence(it)
            out.append(it)
    return out


def check_files(files: list[Path]) -> list[str]:
    errs: list[str] = []
    seen: dict[str, str] = {}
    for f in files:
        raw_lines = [l for l in c.read_text(f).splitlines() if l.strip()]
        rows = c.read_jsonl(f)
        if len(rows) != len(raw_lines):
            errs.append(f"{f.name}: {len(raw_lines) - len(rows)} line(s) are not valid JSON objects")
        for it in rows:
            errs += [f"{f.name}: {e}" for e in validate_item(normalise(it))]
            iid = it.get("id", "")
            if iid in seen:
                errs.append(f"{f.name}: duplicate id {iid} (also in {seen[iid]})")
            seen[iid] = f.name
    return errs


def render_markdown(jsonl_path: Path, title: str | None = None) -> str:
    """Readable view of an item file, grouped by first class tag."""
    rows = [normalise(r) for r in c.read_jsonl(jsonl_path)]
    rows = [r for r in rows if r["status"] in ("active", "probation")]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault((r["class"] or ["general"])[0], []).append(r)
    name = title or jsonl_path.stem.replace("-", " ").title()
    lines = [f"# {name}", "", f"Generated from `{jsonl_path.name}` by the learning pipeline. Do not edit by hand.", ""]
    for g in sorted(groups):
        lines += [f"## {g.replace('-', ' ').capitalize()}", ""]
        for r in sorted(groups[g], key=lambda r: (-r["importance"], r["id"])):
            flag = " (on probation)" if r["status"] == "probation" else ""
            lines.append(f"- {r['text']}{flag} `{r['id']}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- cli
def cmd_check(args) -> int:
    proj = c.resolve_project(getattr(args, "project", None))
    files = brain_item_files() + project_item_files(proj if proj and c.is_managed(proj) else None)
    errs = check_files(files)
    n = sum(len(c.read_jsonl(f)) for f in files)
    if errs:
        print(f"items: {len(errs)} problem(s) in {n} items")
        for e in errs[:40]:
            print(" -", e)
        return 1
    print(f"items: {n} items in {len(files)} files, all valid")
    return 0


def register(sub) -> None:
    p = sub.add_parser("items", help="check memory items against the schema")
    s = p.add_subparsers(dest="items_cmd")
    k = s.add_parser("check", help="validate every item file")
    c.add_project_arg(k)
    k.set_defaults(func=cmd_check)
    p.set_defaults(func=cmd_check)
