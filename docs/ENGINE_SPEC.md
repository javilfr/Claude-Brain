# Engine spec (for people and agents changing `engine/`)

The engine is the set of deterministic scripts behind `bin/brain`. Design is in `docs/MASTER_PLAN.md` (Parts 3.6, 4, 6). This file fixes the conventions that keep the modules consistent.

## Rules for every module

- Python standard library only. No installs, no network. Target Python 3.10+.
- Import helpers from `engine/common.py`; do not re-implement file I/O, time, token estimates, project detection or secret scanning.
- Expose `register(sub)` which adds argparse sub-commands and sets `func`; `func(args) -> int` is the exit code. `bin/brain` loads every module in its `MODULES` list.
- Find the brain through `common.BRAIN_ROOT` (derived from the file's own location). Functions that read or write brain files take an optional `brain_root` argument so tests can point them at a temporary copy.
- Output is short: a command prints at most about 15 lines by default, and offers `--json` where another script may consume it. Output is what the model must then read, so every extra line costs tokens.
- Deterministic: anything random takes a `--seed`; time comes from `common.now()` (overridable with `BRAIN_NOW`).
- Fail clearly: a wrong input prints one line saying what is wrong and returns a non-zero code. No tracebacks for expected errors.
- Tests live in `tests/test_<module>.py` using `unittest`, run with `python3 -m unittest discover -s tests -t .` from the brain root. Tests use temporary directories and never touch the real learned zone.

## Files the engine owns

| Path | Written by | Notes |
|---|---|---|
| `memory/items.jsonl`, `memory/facts.jsonl`, `owner/*.jsonl`, `playbooks/*.jsonl` | `learn apply` only | Item schema in `engine/items.py` |
| `playbooks/*.md` | rendered by `learn apply` from the `.jsonl` | Never edited by hand |
| `memory/models.json` | kernel change | Prices, roles, escalation order, limits |
| `stats/ledger/YYYY-MM.jsonl`, `stats/routing.json` | `learn apply` | Append-only ledger; routing outcome counts |
| `learning/inbox/*.jsonl` | any session, append-only | The only brain path a working session may write |
| `learning/manifest.jsonl`, `learning/CHANGELOG.md`, `learning/deltas/`, `learning/digest/` | `learn apply`, `learn digest` | Audit trail |
| `<project>/.brain/**` | contract, state, req, gate, ledger modules | See `contract/v1.schema.json` |

## Inbox record shape (`learning/inbox/<date>-<session>.jsonl`)

One JSON object per line, each with `kind`, `session`, `at`, and:

- `kind: "ledger"` — `family`, `task_class`, `tier`, `models` (per model: `in`, `cache_write`, `cache_read`, `out`, `cost`), `helpers`, `cache_read_share`, `wall_minutes`.
- `kind: "outcome"` — `task_class`, `model`, `effort`, `passed` (bool), `tokens`, `evidence` (gate id and exit code).
- `kind: "note"` — a lesson candidate: `text` (400 characters at most), `class` (list), `scope`, `trust` (`observed`, `owner-stated` or `external`), `evidence` (list, must name an outcome, a gate or an owner turn), `signal` (`gate-failed`, `rework`, `owner-correction`, `token-outlier`, `first-success`).
- `kind: "used"` — `item` (id), `followed` (bool), `helped` (bool or null).

Records never contain project names, file contents or secrets; `family` is the only project attribute that leaves the project.

## Delta operations (`learn apply`)

`ADD`, `INC_HELPFUL`, `INC_HARMFUL`, `EDIT_TEXT`, `SET_STATUS`, `MOVE_SCOPE`, `LINK`, `APPEND_STAT`, `ROUTE_OUTCOME`, `MARK_INBOX`. No operation replaces or deletes a file. Retiring an item moves it to `memory/archive.jsonl`. A delta that would retire more than 10% of a file's items or shrink a file by more than 20% is refused.
