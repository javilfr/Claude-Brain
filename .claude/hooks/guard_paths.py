#!/usr/bin/env python3
"""PreToolUse hook (Edit, Write, MultiEdit, NotebookEdit, Bash): once
VERSION.json locks the learned zone, keep a session out of what it must not
change. The rules are in ``engine/guard.py`` (``hook_decision``):

- a learned-zone path: refused (exit 2, one line on stderr, which Claude
  reads); the learning pipeline writes there;
- the lock's own files (VERSION.json, this folder, .claude/settings.json,
  engine/guard.py): refused, or one edit would remove the lock;
- any other kernel path: the owner is asked (the PreToolUse "ask" decision
  on stdout, exit 0), because learning must never change its own rules;
- a shell command that appears to write one of the refused paths: refused.
  That check matches patterns; it is not a shell parser.

A hook that fails closed would stop every edit on any bug, so this one fails
open: bad input, missing fields or any error exit 0 with no output. While the
brain is unlocked it does nothing at all.
"""
import json
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        tool_input = data.get("tool_input") or {}
        if not any(isinstance(tool_input.get(k), str) and tool_input.get(k) for k in ("file_path", "notebook_path", "command")):
            return 0
        version = json.loads((BRAIN / "VERSION.json").read_text(encoding="utf-8"))
        if not version.get("learned_zone_locked"):
            return 0
        sys.path.insert(0, str(BRAIN))
        sys.dont_write_bytecode = True
        from engine.guard import hook_decision
        decision, reason = hook_decision(tool_input, data.get("cwd") or ".", BRAIN)
        if decision == "deny":
            print(reason, file=sys.stderr)
            return 2
        if decision == "ask":
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                                     "permissionDecisionReason": reason}}))
    except Exception:  # fail open, always
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
