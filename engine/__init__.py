"""Claude Brain engine. Python standard library only."""

# Every module that contributes commands to `bin/brain`. One list, used by the
# command line, the self-test and the lint.
MODULES = ["detect", "contract", "state", "req", "gate", "budget", "items", "recall", "route",
           "schedule", "repomap", "ledger", "learn", "guard", "mlearn", "radar", "evals", "lint", "doctor"]
