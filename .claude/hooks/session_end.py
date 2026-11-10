#!/usr/bin/env python3
"""Stop hook: keep this session's real token use on disk after every turn,
quietly, because a session can die without `brain close`.

The capture goes to ``learning/inbox/.live/``, which git ignores: rewriting a
tracked file after every turn left the tree dirty after every turn. It is
provisional. `brain close` writes the tracked record and removes the live
file, and a later boot that finds the session unclosed reads it.

It never blocks and never prints: it always exits 0, and it does nothing when
``stop_hook_active`` is set (Claude is already continuing because of a stop
hook). Capture is keyed by session id, so running after every turn simply
refreshes the same file.
"""
import contextlib
import io
import json
import sys
from pathlib import Path

BRAIN = Path(__file__).resolve().parents[2]


def main() -> int:
    try:
        data = json.loads(sys.stdin.read() or "{}")
        if not isinstance(data, dict) or data.get("stop_hook_active"):
            return 0
        sid, transcript = data.get("session_id"), data.get("transcript_path")
        if not isinstance(sid, str) or not sid or not isinstance(transcript, str) or not Path(transcript).is_file():
            return 0
        sys.path.insert(0, str(BRAIN))
        sys.dont_write_bytecode = True
        from engine import common as c
        from engine import ledger
        main_path = Path(transcript)
        subs = c.helper_transcripts(main_path)
        project = c.resolve_project(None, BRAIN)
        if project is not None and not c.is_managed(project):
            project = None
        with contextlib.redirect_stdout(io.StringIO()):
            ledger.capture(BRAIN, sid, main_path, subs, project, live=True)
    except Exception:  # never block the session
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
