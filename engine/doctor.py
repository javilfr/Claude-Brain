"""Self-test: is this brain healthy on this machine?

Runs in a few seconds with nothing but Python. Used at the start of a repair
("Repair the brain") and in CI.
"""
from __future__ import annotations

import importlib
import sqlite3
import sys
import tempfile
from pathlib import Path

from . import common as c

MODULES = ["detect", "contract", "state", "req", "gate", "budget", "items", "recall", "route",
           "schedule", "repomap", "ledger", "learn", "guard"]


def checks() -> list[tuple[str, bool, str]]:
    out: list[tuple[str, bool, str]] = []
    out.append(("python", sys.version_info >= (3, 10), f"{sys.version_info.major}.{sys.version_info.minor}"))
    try:
        sqlite3.connect(":memory:").execute("create virtual table t using fts5(a)")
        out.append(("full-text search", True, f"sqlite {sqlite3.sqlite_version} with FTS5"))
    except sqlite3.Error as e:
        out.append(("full-text search", True, f"FTS5 unavailable ({e}); the pure-Python fallback will be used"))
    bad = []
    for name in MODULES:
        try:
            mod = importlib.import_module(f"engine.{name}")
            if not hasattr(mod, "register"):
                bad.append(f"{name} (no register)")
        except Exception as e:  # report any import failure, whatever its type
            bad.append(f"{name} ({type(e).__name__})")
    out.append(("engine modules", not bad, "all load" if not bad else "problems: " + ", ".join(bad)))
    ver = c.read_json(c.BRAIN_ROOT / "VERSION.json", None)
    out.append(("version file", isinstance(ver, dict) and ver.get("contract") == c.CONTRACT_VERSION, str((ver or {}).get("brain", "missing"))))
    models = c.read_json(c.BRAIN_ROOT / "memory" / "models.json", {}) or {}
    age = c.days_since(models.get("verified_on", ""))
    out.append(("model facts", bool(models.get("models")), f"verified {age} days ago" + (" — due for a re-check" if age > int(models.get("recheck_days", 90)) else "")))
    from . import items
    errs = items.check_files(items.brain_item_files())
    out.append(("memory items", not errs, "valid" if not errs else f"{len(errs)} problem(s); run: brain items check"))
    from . import budget
    berrs, info = budget.check()
    out.append(("always-loaded budget", not berrs, f"about {info['always_loaded_tokens']} tokens" if not berrs else "; ".join(berrs[:2])))
    from . import contract
    with tempfile.TemporaryDirectory() as tmp:
        proj = Path(tmp) / "sample"
        proj.mkdir()
        contract.init(proj, "Sample", "software")
        again = contract.init(proj, "Sample", "software")
        verrs = contract.validate(proj)
        out.append(("contract template", not verrs and not again, "installs, validates and is idempotent" if not verrs and not again else "; ".join(verrs[:2]) or "second init changed files"))
    return out


def cmd_doctor(args) -> int:
    results = checks()
    for name, ok, detail in results:
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {detail}")
    failed = [n for n, ok, _ in results if not ok]
    print("brain is healthy" if not failed else f"{len(failed)} check(s) failed")
    return 1 if failed else 0


def register(sub) -> None:
    p = sub.add_parser("doctor", help="self-test of the brain on this machine")
    p.set_defaults(func=cmd_doctor)
