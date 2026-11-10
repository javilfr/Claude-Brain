"""Lint for the brain's own instruction surface and for a session's behaviour.

Why: instruction files drift. A skill that names a command or flag that no
longer exists sends the model down a dead end at the worst moment; the same
rule repeated in four files is paid for four times; one stray import turns
"nothing to install" into a session-start failure. These are cheap to check
by script and expensive to discover in a live session.

Each rule has a short name (``RULES``). A rule's hits fail the lint unless the
rule is report-only (``REPORT_ONLY``) or is waiting for files to be fixed
(``NOTE_ONLY``): a new rule that fires on text another change owns is shipped
as a note, and becomes an error by deleting its name from ``NOTE_ONLY``.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import json
import re
import shlex
import sys
from pathlib import Path

from . import MODULES
from . import common as c

CODE_SPAN = re.compile(r"`([^`\n]+)`")
FENCE = re.compile(r"```.*?\n(.*?)```", re.S)
# A call is written `BRAIN x`, `brain x`, `"$BRAIN" x`, `${BRAIN} x`, or with the
# path to the script (`bin/brain x`, `python3 Claude-Brain/bin/brain x`).
CALL = re.compile(r"""(?:^|[\s;&|("'])(?:\$\{?BRAIN\}?|BRAIN|(?:[^\s`"'();&|]*/)?bin/brain|brain)["']?[ \t]+([a-z][a-z-]*)""")
FACT = re.compile(r"<!--\s*fact:\s*([A-Za-z0-9_-]+)\s*-->(.*?)<!--\s*/fact\s*-->", re.S)
QUOTED = re.compile(r"[\"“]([^\"”]{3,40})[\"”]")
TOKEN_NUMBER = re.compile(r"\b\d[\d,.]*\s*k?\s*tokens?\b", re.I)
HELPER_TOOLS = ("Agent", "Task", "Workflow")
HELPER_REPLY_TOKENS = 2000   # fallback; memory/models.json limits.helper_reply_tokens
# Rules whose hits are reported and never fail the lint.
REPORT_ONLY = frozenset({"reasons", "agent-tokens", "unnamed"})
# New rules that fire on today's files, which other work packages own. Each is
# an error as soon as its name is removed here (2026-11-10 plan, package E).
NOTE_ONLY = frozenset({"constants", "triggers"})
# A number written in a data file that must equal a constant in the code:
# (file, key path, engine module, attribute path).
CONSTANTS = (
    ("memory/models.json", "limits.recall_budget_tokens", "recall", "DEFAULT_BUDGET"),
    ("memory/models.json", "limits.max_parallel_helpers", "hr", "DEFAULT_CFG.hire.max_helpers"),
)
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


def command_texts(root: Path) -> list[tuple[str, str]]:
    """(label, text) of everything that may name a brain command: the
    instruction files, the handover note, the HR guidelines, and the text
    fields of the rack, memory, playbook and owner records. A stale command
    in a memory item misleads exactly like one in a skill."""
    out = [(str(f.relative_to(root)), c.read_text(f)) for f in instruction_files(root)]
    for rel in ("docs/NEXT_SESSION.md", "hr/GUIDELINES.md"):
        if (root / rel).is_file():
            out.append((rel, c.read_text(root / rel)))

    def strings(v) -> list[str]:
        if isinstance(v, str):
            return [v]
        if isinstance(v, dict):
            return [s for x in v.values() for s in strings(x)]
        return [s for x in v for s in strings(x)] if isinstance(v, list) else []

    for folder in ("hr/rack", "memory", "playbooks", "owner"):
        for f in sorted((root / folder).glob("*.jsonl")):
            for n, row in enumerate(c.read_jsonl(f), 1):
                text = "\n".join(strings(row))
                if "`" in text:
                    out.append((f"{f.relative_to(root)} ({row.get('id', n)})", text))
    return out


# ---------------------------------------------------------------- command tree
class _ParseError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    """The real parser, except that a usage error is raised, not printed."""

    def error(self, message):
        raise _ParseError(message)

    def exit(self, status=0, message=None):
        raise _ParseError("")


_PARSER: argparse.ArgumentParser | None = None


def real_parser() -> argparse.ArgumentParser:
    """The command line as ``bin/brain`` builds it: every module registers its
    own commands, so the lint can never disagree with the code."""
    global _PARSER
    if _PARSER is None:
        parser = _Parser(prog="brain")
        sub = parser.add_subparsers(dest="command")
        for name in MODULES:
            try:
                importlib.import_module(f"engine.{name}").register(sub)
            except Exception:
                continue  # a module that fails to load is reported by `doctor`
        _PARSER = parser
    return _PARSER


def _subparsers(p: argparse.ArgumentParser) -> dict:
    return next((a.choices for a in p._actions if isinstance(a, argparse._SubParsersAction)), {})


def command_tree() -> dict[str, dict]:
    """{command: {"flags": set, "sub": {subcommand: {"flags": set}}}} from the
    real argparse definitions."""
    def flags(p: argparse.ArgumentParser) -> set[str]:
        return {o for a in p._actions for o in a.option_strings}

    return {name: {"flags": flags(p), "sub": {sname: {"flags": flags(sp)} for sname, sp in _subparsers(p).items()}}
            for name, p in _subparsers(real_parser()).items()}


def _one_command(tokens: list[str]) -> list[str]:
    """The tokens of one call: a chain (`a && b`), a pipe, a redirect or a
    comment ends it. `add|list|check` is an alternation, not a pipe."""
    out: list[str] = []
    for i, t in enumerate(tokens):
        if t == "--":
            return out + tokens[i:]  # the wrapped command is not ours to read
        if t in ("&&", "||", "|", ";", "&", "<") or t.startswith(("#", "<<", "(")) or re.match(r"\d*>", t):
            break
        if t.endswith(";") or (t.endswith(")") and "(" not in t and "[" not in t):
            out.append(t[:-1])
            break
        out.append(t)
    return out


def command_mentions(text: str) -> list[tuple[str, list[str]]]:
    """(command, following tokens) for every brain call written inside a code
    span or fenced block. Prose outside code is ignored."""
    chunks = [m.group(1) for m in CODE_SPAN.finditer(text)]
    for block in FENCE.findall(text):
        chunks += block.splitlines()
    out = []
    for chunk in chunks:
        chunk = " " + chunk
        calls = list(CALL.finditer(chunk))
        for m, nxt in zip(calls, calls[1:] + [None]):  # what follows a call, up to the next call on the line
            out.append((m.group(1), _one_command(chunk[m.end():nxt.start() if nxt else len(chunk)].split())))
    return out


def _placeholder(tok: str) -> bool:
    """`<id>`, `N`, `ID:FOLLOWED`, `ok|partial|failed`, `…`: a slot, not a value."""
    return bool(re.search(r"[<>\[\]{}|…]|\.\.\.", tok)) or bool(re.fullmatch(r"[A-Z][A-Z0-9_:]*", tok))


def _argument_problem(cmd: str, rest: list[str]) -> str:
    """What the real parser says about the values in one mention: a value
    that is not among an option's choices, a value of the wrong type, or a
    required argument left out of a call that gives literal values. Slots
    (`<id>`, `N`) are given a valid sample first, so only literal text is
    judged; "" when it parses, when the mention is a bare name or names
    flags and slots only, or when it cannot be read as one call."""
    if "--" in rest:
        rest = rest[:rest.index("--")] + ["--", "x"]
    try:  # `<file to read first>` is one slot, however many words describe it
        tokens = shlex.split(re.sub(r"<[^<>]{1,80}>", "<slot>", " ".join(rest)))
    except ValueError:
        return ""
    tokens = [t.lstrip("[").rstrip("]") if ("[" in t or "]" in t) and "|" not in t else t for t in tokens]
    tokens = [t for t in tokens if t and t not in ("…", "...")]
    path, p = [cmd], _subparsers(real_parser())[cmd]
    while _subparsers(p):
        if not tokens or tokens[0] not in _subparsers(p):
            return ""  # the group's name, a slot or an alternation: nothing to parse
        p = _subparsers(p)[tokens[0]]
        path.append(tokens.pop(0))
    if not tokens or any(t in ("-h", "--help") for t in tokens):
        return ""
    opts = p._option_string_actions

    def sample(action) -> str:
        return str(next(iter(action.choices))) if action.choices else "1"

    argv: list[str] = []
    literal = False   # the mention gives at least one real value: it is a call, not a reference to a flag
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        name, eq, value = tok.partition("=")
        if tok == "--":
            argv += tokens[i:]
            break
        if name in opts:
            action = opts[name]
            if action.nargs != 0:
                values = [value] if eq else []
                many = action.nargs in ("+", "*")
                while not eq and i + 1 < len(tokens) and not tokens[i + 1].startswith("--") and (many or not values):
                    i += 1
                    values.append(tokens[i])
                literal = literal or any(not _placeholder(v) for v in values)
                argv += [name] + ([sample(action) if _placeholder(v) else v for v in values] or [sample(action)])
            else:
                argv.append(name)
        elif tok.startswith("--"):
            return ""  # an unknown flag is reported by name already
        else:
            literal = literal or not _placeholder(tok)
            argv.append("1" if _placeholder(tok) else tok)
        i += 1
    try:
        real_parser().parse_args(path + argv)
        return ""
    except _ParseError as e:
        msg = str(e)
    except Exception:
        return ""
    call = f"`brain {' '.join(path)}`"
    m = re.match(r"argument (\S+): invalid choice: (.+?) \(choose from (.*)\)$", msg)
    if m and m.group(2).strip("'\"") != "1":
        return f"{call}: {m.group(1).split('/')[-1]} cannot be '{m.group(2).strip(chr(39) + chr(34))}' (choose from {c.clip(m.group(3).replace(chr(39), ''), 90)})"
    m = re.match(r"argument (\S+): invalid (\w+) value: (.+)$", msg)
    if m and m.group(3).strip("'\"") != "1":
        return f"{call}: {m.group(1).split('/')[-1]} takes a number ({m.group(2)}), not '{m.group(3).strip(chr(39) + chr(34))}'"
    m = re.match(r"the following arguments are required: (.+)$", msg)
    if m and literal:
        return f"{call} needs {m.group(1)} (required), and this call leaves it out"
    return ""


def _command_problems(root: Path, tree: dict | None = None) -> tuple[list[str], list[str]]:
    """(names and flags that do not exist, argument problems)."""
    tree = tree or command_tree()
    errs, args = [], []
    for rel, text in command_texts(root):
        for cmd, rest in command_mentions(text):
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
            before = len(errs)
            for tok in rest:
                if tok == "--":
                    break  # everything after belongs to the wrapped command
                flag = tok.split("=")[0].strip("[]|,.;)")
                if flag.startswith("--") and len(flag) > 2 and flag not in flagset:
                    errs.append(f"{rel}: `brain {cmd}` has no flag {flag}")
            if len(errs) == before:
                problem = _argument_problem(cmd, rest)
                if problem:
                    args.append(f"{rel}: {problem}")
    return sorted(set(errs)), sorted(set(args))


def check_commands(root: Path, tree: dict | None = None) -> list[str]:
    """Every brain call written in code, checked against the real parser:
    the command, its subcommand and flags exist, and its literal values parse."""
    names, arguments = _command_problems(root, tree)
    return names + arguments


def unnamed_commands(root: Path, tree: dict | None = None) -> list[str]:
    """Report only: commands and subcommands that no instruction file names.
    Each is either a dead feature or a line a skill is missing."""
    tree = tree or command_tree()
    named: set[str] = set()
    for f in instruction_files(root):
        for cmd, rest in command_mentions(c.read_text(f)):
            node = tree.get(cmd)
            if node is None:
                continue
            named.add(cmd)
            for sub in (rest[0].strip("[](),.;").split("|") if rest and node["sub"] else []):
                named.add(f"{cmd} {sub}")
    every = [f"{cmd} {sub}" for cmd, node in tree.items() for sub in node["sub"]] + [cmd for cmd, node in tree.items() if not node["sub"]]
    return sorted(x for x in every if x not in named)


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


def _body_lines(path: Path) -> list[tuple[int, str]]:
    """(line number, line) of a file without its front matter."""
    lines = c.read_text(path).splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        start = next((i + 1 for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), 0)
    return list(enumerate(lines, 1))[start:]


def unscoped_absolutes(root: Path) -> list[str]:
    """Report only: absolute rules without a reason in CLAUDE.md, the skills
    and the agents. Current models follow these literally, and stacked
    cautions lower quality."""
    out = []
    files = [root / "CLAUDE.md"] + sorted((root / ".claude" / "skills").glob("*/SKILL.md")) + sorted((root / ".claude" / "agents").glob("*.md"))
    for f in files:
        for i, line in _body_lines(f):
            if re.search(r"\b(never|always)\b", line, re.I) and not re.search(r"\b(because|so that|so |since|: |; )", line, re.I):
                out.append(f"{f.relative_to(root)}:{i}: absolute rule without a stated reason: {c.clip(line.strip(), 80)}")
    return out


def agent_token_numbers(root: Path) -> list[str]:
    """Report only: a token number in an agent's own text. hr/GUIDELINES.md
    keeps numbers out of what a helper reads, because a budget in the prompt
    makes current models stop early; the brief carries the size."""
    out = []
    for f in sorted((root / ".claude" / "agents").glob("*.md")):
        for i, line in _body_lines(f):
            if TOKEN_NUMBER.search(line):
                out.append(f"{f.relative_to(root)}:{i}: a token number in agent text (hr/GUIDELINES.md keeps them out): {c.clip(line.strip(), 70)}")
    return out


def _dig(data, dotted: str):
    for key in dotted.split("."):
        data = data.get(key) if isinstance(data, dict) else getattr(data, key, None)
        if data is None:
            return None
    return data


def check_constants(root: Path) -> list[str]:
    """A number a data file states that the code holds as a constant must be
    the same number; the code is what runs."""
    out = []
    for rel, key, module, attr in CONSTANTS:
        stated = _dig(c.read_json(root / rel, {}) or {}, key)
        if stated is None:
            continue
        try:
            actual = _dig(importlib.import_module(f"engine.{module}"), attr)
        except Exception:
            continue
        if actual is not None and stated != actual:
            out.append(f"{rel} says {key} is {stated}, but engine/{module}.py {attr} is {actual}: the code is what runs; make them agree")
    return out


def skill_triggers(root: Path) -> dict[str, list[str]]:
    """The quoted trigger phrases of each skill's description, lower-cased."""
    from .budget import frontmatter
    out: dict[str, list[str]] = {}
    for f in sorted((root / ".claude" / "skills").glob("*/SKILL.md")):
        desc = frontmatter(c.read_text(f)).get("description", "")
        out[f.parent.name] = [t.lower().rstrip("…. ") for t in QUOTED.findall(desc)]
    return out


def _phrase_in(phrase: str, low: str) -> bool:
    return bool(phrase) and bool(re.search(r"(?<![a-záéíóúñ])" + re.escape(phrase) + r"(?![a-záéíóúñ])", low))


def check_triggers(root: Path) -> list[str]:
    """Every phrase a skill description promises to react to needs a case in
    ``evals/routing.jsonl``, or nothing checks that the phrase is sized as
    the skill expects."""
    cases = [" ".join(str(r.get("text", "")).lower().split()) for r in c.read_jsonl(root / "evals" / "routing.jsonl")]
    return [f'{skill}: trigger phrase "{t}" has no case in evals/routing.jsonl'
            for skill, phrases in skill_triggers(root).items() for t in phrases
            if t and not any(_phrase_in(t, case) for case in cases)]


# ---------------------------------------------------------------- marked facts
def _count_tests(root: Path) -> int:
    return sum(len(re.findall(r"^[ \t]*(?:async[ \t]+)?def test\w*\(", c.read_text(f), re.M)) for f in (root / "tests").rglob("test*.py"))


# A number a document may mark with its source: <!-- fact: name -->123<!-- /fact -->.
# Each function reads the value from the code, at no model cost.
FACTS = {
    "engine-modules": lambda root: len([f for f in (root / "engine").glob("*.py") if f.name != "__init__.py"]),
    "claude-md-bytes": lambda root: len((root / "CLAUDE.md").read_bytes()) if (root / "CLAUDE.md").is_file() else 0,
    "templates": lambda root: sum(len(c.read_jsonl(f)) for f in (root / "hr" / "rack").glob("*.jsonl")),
    # Counted from the code, not from a recorded run: run logs are shared by
    # every copy of the brain on a machine, so the last run may be another copy's.
    "tests": _count_tests,
}


def fact_files(root: Path) -> list[Path]:
    files = instruction_files(root) + sorted((root / "docs").rglob("*.md")) + [root / "hr" / "GUIDELINES.md"]
    return [f for f in dict.fromkeys(files) if f.is_file()]


def _fact_value(name: str, root: Path) -> int | None:
    try:
        return int(FACTS[name](root))
    except Exception:
        return None


def _marked_facts(text: str) -> list[re.Match]:
    """The fact markers of a document. One written inside code (a page that
    explains the marker) is an example, not a claim, and is left alone."""
    code = [m.span() for m in FENCE.finditer(text)] + [m.span() for m in CODE_SPAN.finditer(text)]
    return [m for m in FACT.finditer(text) if not any(a <= m.start() < b for a, b in code)]


def check_facts(root: Path) -> list[str]:
    """A marked number must equal the code's value. Numbers restated by hand
    in several documents drift apart; a marked one cannot."""
    out = []
    for f in fact_files(root):
        for m in _marked_facts(c.read_text(f)):
            name, shown, rel = m.group(1), m.group(2), f.relative_to(root)
            if name not in FACTS:
                out.append(f"{rel}: unknown fact '{name}' (known: {', '.join(sorted(FACTS))})")
                continue
            value = _fact_value(name, root)
            if value is not None and re.sub(r"[,\s]", "", shown) != str(value):
                out.append(f"{rel}: {name} is marked {c.clip(shown, 20)} but the code says {value}; run `brain lint --fix-facts`")
    return out


def fix_facts(root: Path) -> int:
    """Rewrite every marked number that differs from the code's value.
    Returns how many were changed."""
    changed = 0
    for f in fact_files(root):
        text = original = c.read_text(f)
        for m in reversed(_marked_facts(text)):   # from the end, so earlier positions stay valid
            value = _fact_value(m.group(1), root) if m.group(1) in FACTS else None
            if value is None or re.sub(r"[,\s]", "", m.group(2)) == str(value):
                continue
            new = f"{value:,}" if "," in m.group(2) else str(value)   # keep the document's way of writing thousands
            text = text[:m.start(2)] + new + text[m.end(2):]
            changed += 1
        if text != original:
            c.write_text(f, text)
    return changed


# ---------------------------------------------------------------- all rules
RULES = ("budget", "commands", "arguments", "imports", "links", "project-ids", "duplicates", "facts", "constants",
         "triggers", "reasons", "agent-tokens", "unnamed")


def run_rules(root: Path | None = None) -> dict[str, list[str]]:
    """Every rule's hits, by rule name, in the order of ``RULES``."""
    root = Path(root or c.BRAIN_ROOT)
    from . import budget
    tree = command_tree()
    names, arguments = _command_problems(root, tree)
    unnamed = unnamed_commands(root, tree)
    return {
        "budget": [f"budget: {e}" for e in budget.check(root)[0]],
        "commands": names,
        "arguments": arguments,
        "imports": check_imports(root),
        "links": check_links(root),
        "project-ids": check_project_ids(root),
        "duplicates": check_duplicates(root),
        "facts": check_facts(root),
        "constants": check_constants(root),
        "triggers": check_triggers(root),
        "reasons": unscoped_absolutes(root),
        "agent-tokens": agent_token_numbers(root),
        "unnamed": [f"no instruction file names `brain {x}`" for x in unnamed],
    }


def run(root: Path | None = None) -> tuple[list[str], list[str]]:
    """(errors, notes). Errors fail the lint; notes are reported only."""
    hits = run_rules(root)
    quiet = REPORT_ONLY | NOTE_ONLY
    return ([h for rule in RULES if rule not in quiet for h in hits[rule]],
            [h for rule in RULES if rule in quiet for h in hits[rule]])


# ---------------------------------------------------------------- transcript rules
def transcript_report(main: Path | None, subs: list[Path]) -> list[str]:
    """Behaviour checks on a recorded session: what the conversation actually
    spent tokens on. Each line names the rule it measures."""
    if main is None:
        return ["no session transcript found on this machine"]
    big, reads, models, single_reads, prev_single = 0, {}, set(), 0, False
    limits = (c.read_json(c.BRAIN_ROOT / "memory" / "models.json", {}) or {}).get("limits") or {}
    cap = limits.get("helper_reply_tokens") if isinstance(limits.get("helper_reply_tokens"), int) else HELPER_REPLY_TOKENS
    helper_calls, helper_replies, long_replies = set(), 0, 0
    for row in c.iter_jsonl_stream(main):
        msg = row.get("message") or {}
        content = msg.get("content")
        if row.get("type") == "assistant":
            if msg.get("model"):
                models.add(msg["model"])
            uses = [b for b in content or [] if isinstance(b, dict) and b.get("type") == "tool_use"]
            for b in uses:
                if b.get("name") in HELPER_TOOLS and b.get("id"):
                    helper_calls.add(b["id"])
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
                    if b.get("tool_use_id") in helper_calls:
                        helper_replies += 1
                        long_replies += size > cap * 4
    repeats = sum(n - 1 for n in reads.values() if n > 1)
    lines = [
        f"tool results over ~5,000 tokens in the main conversation: {big} (target 0; run builds and tests through `brain run`)",
        f"whole-file re-reads of a file already read: {repeats} (target 0; read a range, or search)",
        f"read-only calls made one at a time in a row: {single_reads} (send independent reads together)",
        f"models used by the main conversation: {len(models)} (target 1; a switch re-reads everything uncached)",
        f"helpers started: {len(subs)} (each starts cold; at most four at once)",
        f"helper replies over ~{cap:,} tokens: {long_replies} of {helper_replies} (target 0; ask for a short reply and a file for the rest)",
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
    triggers = skill_triggers(root)
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
                pending = [name for name, ts in triggers.items() if any(_phrase_in(t, low) for t in ts)]
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
NOTE_TITLES = {
    "constants": "a data file and the code disagree on a number",
    "triggers": "trigger phrases with no case in evals/routing.jsonl",
    "reasons": "absolute rules without a stated reason",
    "agent-tokens": "token numbers in agent text",
    "unnamed": "commands no instruction file names",
}
# The part of a hit that says where, for the one-line form.
NOTE_SHORT = {
    "triggers": re.compile(r'^(\S+): trigger phrase ("[^"]*")'),
    "reasons": re.compile(r"^(\S+:\d+):"),
    "agent-tokens": re.compile(r"^(\S+:\d+):"),
    "unnamed": re.compile(r"`brain ([^`]+)`"),
}


def _note_lines(hits: dict[str, list[str]], full: bool) -> list[str]:
    """One line per rule: its count and as many places as fit (fewer for a
    rule that only reports); every hit with ``full``."""
    out = []
    for rule in RULES:
        rows = hits.get(rule) or []
        if rule not in REPORT_ONLY | NOTE_ONLY or not rows:
            continue
        width = 150 if rule in REPORT_ONLY else 230
        if full:
            out += [f"note: {r}" for r in rows]
            continue
        if len(rows) == 1:
            out.append("note: " + c.clip(rows[0], width))
            continue
        line, shown = f"note: {NOTE_TITLES.get(rule, rule)} ({len(rows)}): ", 0
        for r in rows:
            m = NOTE_SHORT[rule].search(r) if rule in NOTE_SHORT else None
            piece = " ".join(m.groups()) if m else c.clip(r, 80)
            if shown and len(line) + len(piece) > width:
                break
            line += ("; " if shown else "") + piece
            shown += 1
        out.append(line + (f" (+{len(rows) - shown}: brain lint --all)" if shown < len(rows) else ""))
    return out


def cmd_lint(args) -> int:
    if args.transcript:
        main, subs = c.transcript_paths()
        for l in transcript_report(main, subs):
            print(l)
        return 0
    if args.fix_facts:
        print(f"lint: {fix_facts(c.BRAIN_ROOT)} marked number(s) rewritten from the code")
    hits = run_rules()
    quiet = REPORT_ONLY | NOTE_ONLY
    errs = [h for rule in RULES if rule not in quiet for h in hits[rule]]
    notes = sum(len(hits[rule]) for rule in RULES if rule in quiet)
    shown = errs if args.all else errs[:12]
    for e in shown:
        print("error:", e if args.all else c.clip(e, 240))
    if len(errs) > len(shown):
        print(f"… {len(errs) - len(shown)} more errors: brain lint --all")
    for line in _note_lines(hits, args.all) if not errs or args.all else []:
        print(line)
    print(f"lint: {len(errs)} error(s), {notes} note(s)" + ("" if errs else " — instruction surface is consistent with the engine"))
    return 1 if errs else 0


def cmd_skill_audit(args) -> int:
    main, _ = c.transcript_paths()
    for l in skill_audit(main):
        print(l)
    return 0


def register(sub) -> None:
    p = sub.add_parser("lint", help="check instruction files against the real commands, budgets and rules")
    p.add_argument("--transcript", action="store_true", help="report behaviour rules measured on this session's transcript")
    p.add_argument("--all", action="store_true", help="every error and every note in full, not the short form")
    p.add_argument("--fix-facts", action="store_true",
                   help="rewrite numbers marked <!-- fact: name -->N<!-- /fact --> in documents from the code, then lint")
    p.set_defaults(func=cmd_lint)
    p = sub.add_parser("skill-audit", help="which skills fired this session and which triggers were missed")
    p.set_defaults(func=cmd_skill_audit)
