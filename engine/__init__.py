"""Claude Brain engine. Python standard library only."""

# Every module that contributes commands to `bin/brain`. One list, used by the
# command line, the self-test and the lint.
MODULES = ["detect", "contract", "state", "req", "gate", "budget", "items", "recall", "route",
           "schedule", "repomap", "ledger", "learn", "guard", "mlearn", "radar", "evals", "hr", "lint", "doctor"]

# Which module registers each command, so that one call loads one module and
# not all twenty. It is a short cut, never a gate: a command missing here is
# found by loading everything. tests/test_r4_b2.py compares this table with
# what the modules really register, so a new command must be added here too.
COMMANDS = {
    "detect": "detect", "boot": "detect",
    "init": "contract", "adopt": "contract", "validate": "contract", "migrate": "contract",
    "checkpoint": "state", "resume": "state", "status": "state", "handover": "state",
    "req": "req", "done": "req",
    "run": "gate", "gate": "gate", "release": "gate",
    "budget": "budget", "items": "items", "recall": "recall", "route": "route",
    "plan": "schedule", "map": "repomap",
    "ledger": "ledger", "close": "ledger", "learn": "learn", "guard": "guard", "ml": "mlearn",
    "radar": "radar", "eval": "evals", "ablate": "evals", "hr": "hr",
    "lint": "lint", "skill-audit": "lint", "doctor": "doctor",
}
