"""Enforce the size caps on always-loaded text.

Every byte of ``CLAUDE.md`` and every agent and skill description is paid for
on every request and by most helpers, in every project. The caps are checked
here and in CI so the brain cannot quietly grow.
"""
from __future__ import annotations

import re
from pathlib import Path

from . import common as c

LIMITS = {"claude_md": 6000, "stub": 2000, "description": 300, "agents": 6, "skills": 12, "skill_lines": 500}
VOLATILE = [re.compile(r"\b20\d\d-\d\d-\d\d\b"), re.compile(r"(?i)last updated|as of today|current ticket|in progress:")]


def frontmatter(text: str) -> dict:
    """Read simple ``key: value`` YAML front matter (enough for agent and skill files)."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    out: dict = {}
    key = None
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip().strip("'\"")
        elif key and line.startswith((" ", "\t")) and line.strip():
            out[key] = (out[key] + " " + line.strip()).strip().lstrip(">|").strip()
    return out


def check(brain_root: Path | None = None) -> tuple[list[str], dict]:
    root = Path(brain_root or c.BRAIN_ROOT)
    errs: list[str] = []
    info: dict = {}
    claude = c.read_text(root / "CLAUDE.md")
    info["claude_md_bytes"] = len(claude.encode())
    if not claude:
        errs.append("CLAUDE.md is missing")
    if info["claude_md_bytes"] > LIMITS["claude_md"]:
        errs.append(f"CLAUDE.md is {info['claude_md_bytes']} bytes (limit {LIMITS['claude_md']})")
    for pat in VOLATILE:
        hit = pat.search(claude)
        if hit:
            errs.append(f"CLAUDE.md contains volatile text ({hit.group(0)!r}); it would break the cache when it changes")
    stub = c.read_text(root / "contract" / "template" / "CLAUDE.stub.md")
    info["stub_bytes"] = len(stub.encode())
    if info["stub_bytes"] > LIMITS["stub"]:
        errs.append(f"project stub is {info['stub_bytes']} bytes (limit {LIMITS['stub']})")
    desc_chars = 0
    agents = sorted((root / ".claude" / "agents").glob("*.md"))
    skills = sorted((root / ".claude" / "skills").glob("*/SKILL.md"))
    info["agents"], info["skills"] = len(agents), len(skills)
    if len(agents) > LIMITS["agents"]:
        errs.append(f"{len(agents)} agents (limit {LIMITS['agents']}): a new archetype needs evidence; specialists belong in the project")
    if len(skills) > LIMITS["skills"]:
        errs.append(f"{len(skills)} skills (limit {LIMITS['skills']})")
    for f in agents + skills:
        text = c.read_text(f)
        fm = frontmatter(text)
        label = f.parent.name if f.name == "SKILL.md" else f.stem
        d = fm.get("description", "")
        desc_chars += len(d) + len(fm.get("name", label))
        if not d:
            errs.append(f"{label}: no description")
        elif len(d) > LIMITS["description"]:
            errs.append(f"{label}: description is {len(d)} characters (limit {LIMITS['description']})")
        if f.name == "SKILL.md":
            if fm.get("model"):
                errs.append(f"{label}: a skill must not set 'model' (it switches models and discards the cache)")
            if len(text.splitlines()) > LIMITS["skill_lines"]:
                errs.append(f"{label}: longer than {LIMITS['skill_lines']} lines")
        else:
            for need in ("model", "effort", "tools"):
                if not fm.get(need):
                    errs.append(f"agent {label}: '{need}' must be set explicitly (an unset model inherits the lead's)")
    info["always_loaded_tokens"] = c.est_tokens(claude) + c.est_tokens(stub) + desc_chars // 4
    return errs, info


def cmd_budget(args) -> int:
    errs, info = check()
    print(f"always-loaded: CLAUDE.md {info['claude_md_bytes']} B, project stub {info['stub_bytes']} B, "
          f"{info['agents']} agents, {info['skills']} skills · about {info['always_loaded_tokens']} tokens in total")
    for e in errs:
        print(" -", e)
    return 1 if errs else 0


def register(sub) -> None:
    p = sub.add_parser("budget", help="check the size caps on always-loaded text")
    p.set_defaults(func=cmd_budget)
