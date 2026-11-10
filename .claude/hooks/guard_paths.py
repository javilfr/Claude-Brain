#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|MultiEdit): block direct edits to the brain's
learned zone once VERSION.json locks it; the learning pipeline writes there.

A hook that fails closed would stop every edit on any bug, so this one fails
open: bad input, missing fields or any error exit 0. Exit 2 (with one line on
stderr, which Claude reads) only for a learned-zone path in a locked brain.
"""
import json
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        path = (data.get("tool_input") or {}).get("file_path")
        if not isinstance(path, str) or not path:
            return 0
        version = json.loads((BRAIN / "VERSION.json").read_text(encoding="utf-8"))
        if not version.get("learned_zone_locked"):
            return 0
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = Path(data.get("cwd") or ".") / p
        rel = p.resolve().relative_to(BRAIN).as_posix()
        sys.path.insert(0, str(BRAIN))
        sys.dont_write_bytecode = True
        from engine.guard import zone_of
        if zone_of(rel) == "learned":
            print(f"{rel} is in the learned zone: change it through `brain learn` (note, then consolidate)", file=sys.stderr)
            return 2
    except Exception:  # fail open, always
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
