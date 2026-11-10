"""Content-addressed cache for derived work (repo maps, summaries, indexes).

Why: anything computed purely from files should be paid for once per change
of its inputs, not once per session. The key is a SHA-256 of everything the
result depends on (tool name, version, parameters, input content hashes), so
a hit is exact and carries no quality risk.

Where entries live: ``<project>/.brain/cache`` when a project is given, else a
directory under the system temp folder. Never inside the brain's tracked tree:
a cache there would leak project-derived data into the shared brain.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from . import common as c

TEMP_CACHE_NAME = "claude-brain-cache"


def key(*parts: Any) -> str:
    """SHA-256 over the JSON form of the inputs; dict order does not matter."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    return c.sha256_text(blob)


def _inside_brain(path: Path) -> bool:
    try:
        path.resolve().relative_to(c.BRAIN_ROOT.resolve())
        return True
    except ValueError:
        return False


def default_dir(project: Path | str | None = None) -> Path:
    """The project's cache, or a temp cache when there is no project (or the
    'project' is the brain itself, which must stay free of derived data)."""
    if project:
        cand = Path(project) / ".brain" / "cache"
        if not _inside_brain(cand):
            return cand
    return Path(tempfile.gettempdir()) / TEMP_CACHE_NAME


def _resolve_dir(cache_dir: Path | str | None) -> Path:
    d = Path(cache_dir) if cache_dir else default_dir()
    return default_dir() if _inside_brain(d) else d


def _entry_path(k: str, cache_dir: Path | str | None) -> Path:
    if len(k) < 3 or not all(ch in "0123456789abcdef" for ch in k):
        raise ValueError(f"not a cache key: {k!r}")
    return _resolve_dir(cache_dir) / k[:2] / f"{k}.json"


def get(k: str, cache_dir: Path | str | None = None) -> Any:
    """The stored value, or None on a miss (or an unreadable entry)."""
    entry = c.read_json(_entry_path(k, cache_dir))
    if not isinstance(entry, dict) or "value" not in entry:
        return None
    return entry["value"]


def put(k: str, value: Any, cache_dir: Path | str | None = None) -> Path:
    """Store a JSON-serialisable value atomically; returns the entry path."""
    path = _entry_path(k, cache_dir)
    c.write_json(path, {"key": k, "created": c.now_iso(), "value": value})
    return path


def prune(days: int, cache_dir: Path | str | None = None) -> int:
    """Delete entries created more than ``days`` ago; returns how many."""
    root = _resolve_dir(cache_dir)
    removed = 0
    if not root.is_dir():
        return 0
    for path in sorted(root.glob("??/*.json")):
        entry = c.read_json(path)
        created = entry.get("created", "") if isinstance(entry, dict) else ""
        if c.days_since(created) > days:
            try:
                path.unlink()
                removed += 1
            except OSError:
                continue
    return removed
