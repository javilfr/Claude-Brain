"""Lint for the brain's own instruction surface and for a session's behaviour.

Why: instruction files drift. A skill that names a command or flag that no
longer exists sends the model down a dead end at the worst moment; the same
rule repeated in four files is paid for four times; one stray import turns
"nothing to install" into a session-start failure. These are cheap to check
by script and expensive to discover in a live session.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import re
import sys
from pathlib import Path

from . import MODULES
from . import common as c

CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"```.*?\n(.*?)```", re.S)
CALL = re.compile(r"(?:^|[\s;&|(])(?:BRAIN|bin/brain|brain)\s+([a-z][a-z-]*)((?:\s+[^\s`]+)*)")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)")
SENTENCE = re.compile(r"(?<=[.!?])\s+")
# Marks of a user-role turn the owner did not type (helper reports, notices).
NOT_OWNER = ("[SYSTEM NOTIFICATION", "Another Claude session sent a message", "Stop hook feedback", "[Subagent hand-back]", "<task-notification>")
# Words that follow "brain" in prose, not commands.
PROSE_WORDS = {"is", "and", "or", "the", "repository", "repo", "itself", "works", "holds", "needs", "does", "has", "never", "learns",
               "attached", "not", "to", "in", "side", "only", "can", "will", "contract", "reads", "installs", "command", "commands"}


def instruction_files(root: Path) -> list[Path]:
    files = [root / "CLAUDE.md", root / "OWNER_GUIDE.md", root / "README.md", root / "NEEDS_YOU.md"]
    files += sorted((root / ".claude" / "skills").glob("*/SKILL.md"))
    files += sorted((root / ".claude" / "agents").glob("*.md"))
    files += sorted((root / "method").rglob("*.md"))
    files += sorted((root / "playbooks").glob("*.md"))
    files += sorted((root / "contract" / "template").rglob("*.md"))
    return [f for f in files if f.is_file()]


# ---------------------------------------------------------------- command tree
def command_tree() -> dict[str, dict]:
    """{command: {"flags": set, "sub": {subcommand: {"flags": set}}}} from the
    real argparse definitions, so the lint can never disagree with the code."""
    parser = argparse.ArgumentParser(prog="brain")
    sub = parser.add_subparsers(dest="command")
    for name in MODULES:
        try:
            importlib.import_module(f"engine.{name}").register(sub)
        except Exception:
            continue  # a module that fails to load is reported by `doctor`
    tree: dict[str, dict] = {}

    def flags(p: argparse.ArgumentParser) -> set[str]:
        return {o for a in p._actions for o in a.option_strings}

    for name, p in sub.choices.items():
        node = {"flags": flags(p), "sub": {}}
        for a in p._actions:
            if isinstance(a, argparse._SubParsersAction):
                for sname, sp in a.choices.items():
                    node["sub"][sname] = {"flags": flags(sp)}
        tree[name] = node
    return tree


def command_mentions(text: str) -> list[tuple[str, list[str]]]:
    """(command, following tokens) for every brain call written inside a code
    span or fenced block. Prose outside code is ignored."""
    chunks = [m.group(1) for m in CODE_SPAN.finditer(text)]
    for block in FENCE.findall(text):
        chunks += block.splitlines()
    out = []
    for chunk in chunks:
        for m in CALL.finditer(" " + chunk):
            out.append((m.group(1), m.group(2).split()))
    return out


def check_commands(root: Path, tree: dict | None = None) -> list[str]:
    tree = tree or command_tree()
    errs = []
    for f in instruction_files(root):
        rel = f.relative_to(root)
        for cmd, rest in command_mentions(c.read_text(f)):
            if cmd in PROSE_WORDS:
                continue
            if cmd not in tree:
                errs.append(f"{rel}: `brain {cmd}` does not exist")
                continue
            node = tree[cmd]
            flagset = set(node["flags"])
            if rest and node["sub"]:
                first = rest[0].strip("|,.;)")
                if first in node["sub"]:
                    flagset |= node["sub"][first]["flags"]
                elif re.fullmatch(r"[a-z][a-z-]*", first) and "|" not in rest[0] and not first.startswith("-"):
                    errs.append(f"{rel}: `brain {cmd} {first}` does not exist (have: {', '.join(sorted(node['sub']))})")
                    continue
                else:
                    for sp in node["sub"].values():
                        flagset |= sp["flags"]
            for tok in rest:
                if tok == "--":
                    break  # everything after belongs to the wrapped command
                flag = tok.split("=")[0].strip("[]|,.;)")
                if flag.startswith("--") and len(flag) > 2 and flag not in flagset:
                    errs.append(f"{rel}: `brain {cmd}` has no flag {flag}")
    return sorted(set(errs))


# ---------------------------------------------------------------- other checks
def check_imports(root: Path) -> list[str]:
    """Standard library only: an install at session start is the failure this
    brain was designed to avoid."""
    allowed = set(sys.stdlib_module_names) | {"engine"}
    errs = []
    files = sorted((root / "engine").glob("*.py")) + [root / "bin" / "brain"] + sorted((root / ".claude" / "hooks").glob("*.py"))
    for f in files:
        try:
            tree = ast.parse(c.read_text(f))
        except SyntaxError as e:
            errs.append(f"{f.relative_to(root)}: does not parse ({e.msg}, line {e.lineno})")
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module.split(".")[0]]
            for n in names:
                if n not in allowed:
                    errs.append(f"{f.relative_to(root)}: imports '{n}', which is not in the standard library")
    return sorted(set(errs))


def check_links(root: Path) -> list[str]:
    errs = []
    for f in instruction_files(root):
        for target in LINK.findall(c.read_text(f)):
            if re.match(r"^[a-z]+:", target) or target.startswith("<"):
                continue
            if not (f.parent / target).exists() and not (root / target).exists():
                errs.append(f"{f.relative_to(root)}: link to {target} does not resolve")
    return errs


def _sentences(text: str) -> set[str]:
    text = FENCE.sub(" ", text)
    out = set()
    for raw in SENTENCE.split(text.replace("\n", " ")):
        norm = " ".join(c.words(raw))
        if len(norm) >= 60:
            out.add(c.sha256_text(norm)[:16] + "|" + c.clip(" ".join(raw.split()), 90))
    return out


def check_duplicates(root: Path, min_files: int = 3) -> list[str]:
    """The same sentence in three or more instruction files is paid for each
    time and drifts apart when one copy is edited."""
    seen: dict[str, list[str]] = {}
    sample: dict[str, str] = {}
    for f in instruction_files(root):
        for item in _sentences(c.read_text(f)):
            h, text = item.split("|", 1)
            seen.setdefault(h, []).append(str(f.relative_to(root)))
            sample[h] = text
    return [f"repeated in {len(v)} files ({', '.join(sorted(v)[:4])}): {sample[h]}" for h, v in sorted(seen.items()) if len(set(v)) >= min_files]


def check_project_ids(root: Path) -> list[str]:
    ids = [l.strip().lower() for l in c.read_text(root / "evals" / "known_project_ids.txt").splitlines() if l.strip() and not l.startswith("#")]
    if not ids:
        return []
    errs = []
    scan = instruction_files(root) + sorted((root / "memory").glob("*.jsonl")) + sorted((root / "owner").glob("*.jsonl")) + sorted((root / "playbooks").glob("*.jsonl"))
    for f in scan:
        low = c.read_text(f).lower()
        for pid in ids:
            if re.search(r"(?<![a-z0-9])" + re.escape(pid) + r"(?![a-z0-9])", low):
                errs.append(f"{f.relative_to(root)}: names a project ({pid}); the brain holds no project names")
    return errs


def unscoped_absolutes(root: Path) -> list[str]:
    """Report only: absolute rules without a reason in always-loaded text.
    Current models follow these literally, and stacked cautions lower quality."""
    out = []
    for i, line in enumerate(c.read_text(root / "CLAUDE.md").splitlines(), 1):
        if re.search(r"\b(never|always)\b", line, re.I) and not re.search(r"\b(because|so that|so |since|: |; )", line, re.I):
            out.append(f"CLAUDE.md:{i}: absolute rule without a stated reason: {c.clip(line.strip(), 80)}")
    return out


def run(root: Path | None = None) -> tuple[list[str], list[str]]:
    """(errors, notes). Errors fail the lint; notes are reported only."""
    root = Path(root or c.BRAIN_ROOT)
    from . import budget
    errs = [f"budget: {e}" for e in budget.check(root)[0]]
    errs += check_commands(root)
    errs += check_imports(root)
    errs += check_links(root)
    errs += check_project_ids(root)
    notes = check_duplicates(root) + unscoped_absolutes(root)
    return errs, notes


# ---------------------------------------------------------------- transcript rules
def transcript_report(main: Path | None, subs: list[Path]) -> list[str]:
    """Behaviour checks on a recorded session: what the conversation actually
    spent tokens on. Each line names the rule it measures."""
    if main is None:
        return ["no session transcript found on this machine"]
    big, reads, models, single_reads, prev_single = 0, {}, set(), 0, False
    for row in c.iter_jsonl_stream(main):
        msg = row.get("message") or {}
        content = msg.get("content")
        if row.get("type") == "assistant":
            if msg.get("model"):
                models.add(msg["model"])
            uses = [b for b in content or [] if isinstance(b, dict) and b.get("type") == "tool_use"]
            for b in uses:
                if b.get("name") == "Read" and not (b.get("input") or {}).get("offset"):
                    path = (b.get("input") or {}).get("file_path", "")
                    reads[path] = reads.get(path, 0) + 1
            read_only = len(uses) == 1 and uses[0].get("name") in ("Read", "Grep", "Glob")
            if read_only and prev_single:
                single_reads += 1
            prev_single = read_only
        elif row.get("type") == "user" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    body = b.get("content")
                    size = len(body) if isinstance(body, str) else sum(len(str(x.get("text", ""))) for x in body or [] if isinstance(x, dict))
                    if size > 20000:
                        big += 1
    repeats = sum(n - 1 for n in reads.values() if n > 1)
    lines = [
        f"tool results over ~5,000 tokens in the main conversation: {big} (target 0; run builds and tests through `brain run`)",
        f"whole-file re-reads of a file already read: {repeats} (target 0; read a range, or search)",
        f"read-only calls made one at a time in a row: {single_reads} (send independent reads together)",
        f"models used by the main conversation: {len(models)} (target 1; a switch re-reads everything uncached)",
        f"helpers started: {len(subs)} (each starts cold; at most four at once)",
    ]
    try:
        from . import ledger
        s = ledger.summarise(main, subs, c.read_json(c.BRAIN_ROOT / "memory" / "models.json", {}) or {})
        share = s.get("cache_read_share")
        if isinstance(share, (int, float)):
            lines.append(f"input read from cache: {share:.0%} (target 80% or more)")
    except Exception:
        pass
    return lines


def skill_audit(main: Path | None, root: Path | None = None) -> list[str]:
    """Which skills fired, and which trigger phrases in the owner's messages
    were followed by no skill. A skill that never fires is dead weight in the
    listing; a missed trigger means its description needs work."""
    root = Path(root or c.BRAIN_ROOT)
    if main is None:
        return ["no session transcript found on this machine"]
    from .budget import frontmatter
    triggers: dict[str, list[str]] = {}
    for f in sorted((root / ".claude" / "skills").glob("*/SKILL.md")):
        desc = frontmatter(c.read_text(f)).get("description", "")
        triggers[f.parent.name] = [t.lower().rstrip("…. ") for t in re.findall(r"[\"“]([^\"”]{3,40})[\"”]", desc)]
    fired = {k: 0 for k in triggers}
    missed: dict[str, int] = {}
    pending: list[str] = []
    for row in c.iter_jsonl_stream(main):
        msg = row.get("message") or {}
        content = msg.get("content")
        if row.get("type") == "user":
            text = content if isinstance(content, str) else " ".join(str(b.get("text", "")) for b in content or [] if isinstance(b, dict) and b.get("type") == "text")
            if text.strip() and not text.lstrip().startswith("<") and not row.get("isMeta") and not any(m in text for m in NOT_OWNER):
                for name in pending:
                    missed[name] = missed.get(name, 0) + 1
                low = text.lower()
                pending = [name for name, ts in triggers.items()
                           if any(t and re.search(r"(?<![a-záéíóúñ])" + re.escape(t) + r"(?![a-záéíóúñ])", low) for t in ts)]
        elif row.get("type") == "assistant":
            for b in content or []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Skill":
                    name = str((b.get("input") or {}).get("skill", "")).split(":")[-1]
                    if name in fired:
                        fired[name] += 1
                    pending = [p for p in pending if p != name]
    lines = ["skills fired this session: " + (", ".join(f"{k}×{v}" for k, v in fired.items() if v) or "none")]
    for name, n in sorted(missed.items()):
        lines.append(f"trigger phrase for {name} appeared {n} time(s) with no skill call after it")
    never = [k for k, v in fired.items() if not v]
    lines.append(f"not used this session: {', '.join(never) if never else 'none'} (judge over several sessions, not one)")
    return lines[:14]


# ---------------------------------------------------------------- cli
def cmd_lint(args) -> int:
    if args.transcript:
        main, subs = c.transcript_paths()
        for l in transcript_report(main, subs):
            print(l)
        return 0
    errs, notes = run()
    for e in errs[:30]:
        print("error:", e)
    if len(errs) > 30:
        print(f"… {len(errs) - 30} more errors")
    for n in notes[: 0 if errs else 8]:
        print("note:", n)
    print(f"lint: {len(errs)} error(s), {len(notes)} note(s)" + ("" if errs else " — instruction surface is consistent with the engine"))
    return 1 if errs else 0


def cmd_skill_audit(args) -> int:
    main, _ = c.transcript_paths()
    for l in skill_audit(main):
        print(l)
    return 0


def register(sub) -> None:
    p = sub.add_parser("lint", help="check instruction files against the real commands, budgets and rules")
    p.add_argument("--transcript", action="store_true", help="report behaviour rules measured on this session's transcript")
    p.set_defaults(func=cmd_lint)
    p = sub.add_parser("skill-audit", help="which skills fired this session and which triggers were missed")
    p.set_defaults(func=cmd_skill_audit)
