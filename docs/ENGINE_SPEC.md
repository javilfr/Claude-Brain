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
| `memory/models.json`, `memory/ml_config.json`, `memory/radar_sources.json` | kernel change | Prices and roles; learning constants (*tunable*); radar sources |
| `stats/ledger/YYYY-MM.jsonl` | `learn apply` (`APPEND_STAT`) | Append-only ledger |
| `stats/ml.json` | `learn apply` (`ML_FOLD`, via `mlearn.fold`) | All statistical learning state; JSON with sorted keys |
| `learning/inbox/*.jsonl` | any session, append-only | Zone `inbox` |
| `learning/radar/**` | `brain radar` | Zone `state`: rewritten in a working session, not part of manifest replay |
| `learning/manifest.jsonl`, `learning/CHANGELOG.md`, `learning/deltas/`, `learning/digest/` | `learn apply`, `learn digest` | Audit trail |
| `<project>/.brain/**` | contract, state, req, gate, ledger, recall modules | See `contract/v1.schema.json`; `.brain/log/recall.jsonl` is the injection log, `.brain/log/open-session.json` the unclosed-session marker |

Zones (`engine/guard.py`): `inbox` (append only), `state` (`learning/radar/`, rewrites allowed, ignored by `learn verify`), `learned` (the five directories, `learn apply` only), `kernel` (everything else, plus the hand-written files named above and `learning/PROMOTION_RULES.md`).

## Inbox record shape (`learning/inbox/<date>-<session>.jsonl`)

One JSON object per line. Every record has `kind`, `session`, `at` and a stable `id`: the first 16 hex characters of sha256 of `session`, `kind` and a per-kind key (shown below), so the same event recorded twice has the same id and `mlearn.fold` is idempotent per record.

- `kind: "ledger"` (key: none, one per session) — `family`, `task_class`, `classes`, `tier`, `outcome`, `model` (main conversation's alias), `models` (per model: `in`, `cache_write`, `cache_read`, `out`, `cost`), `helpers`, `cache_read_share`, `wall_minutes`. A session that ended without `close` and whose transcript is gone gets `unrecorded: true` and `started` instead of usage.
- `kind: "outcome"` (key: `task_class`) — judged only by this session's gate exit codes: `task_class`, `family`, `tier`, `risk`, `model` (alias), `model_id`, `effort`, `has_check` (a command gate with a non-empty command ran), `passed` (every gate's last run green), `first_pass` (every gate's first run green), `rework` (red runs before the last), `tokens`, `cost`, `minutes` (split evenly across classes), `est_tokens`, `est_minutes` (null when not estimated), `explored`, `propensity`, `gate_runs` (`gate`, `exit`, `commit` as a 12-hex hash), `evidence`.
- `kind: "used"` (key: `item`) — `item` (id), `followed` (bool). There is no `helped` field: whether an item helped is derived from the session's outcomes (I-07); a `helped` field found in the inbox is ignored and reported.
- `kind: "note"` (key: the text) — a lesson candidate: `text` (400 characters at most), `class` (list), `scope`, `trust` (`observed`, `owner-stated` or `external`), `evidence` (list, must name an outcome, a gate or an owner turn), `signal` (`gate-failed`, `rework`, `owner-correction`, `token-outlier`, `first-success`), `source` for external facts.
- `kind: "review"` (key: `task_class` and `round`) — `task_class`, `round`, `found_a`, `found_b`, `both`, optional `blocking`.
- `kind: "correction"` (key: `item` and first evidence) — an owner correction naming an item: `item`, `evidence` (each `owner:...`).
- `kind: "lead"` (key: `url`) — written by the radar: `source`, `trust` (`official`, `research`, `community`), `title`, `url`, `date`, `keywords`. A lead never changes memory; `learn status` counts unhandled official ones and consolidation lists them, then marks them handled with the rest of the file.

Records never contain project names, paths, file contents, commands, commit ids or secrets; `family` is the only project attribute that leaves the project.

## Consolidation (`learn consolidate`)

One delta per run: one `ML_FOLD` op with the new `outcome`, `used`, `review` and `correction` records (plus `promotion` records for items that became active), `APPEND_STAT` for ledger rows, item ops for notes, uses and corrections, `MARK_INBOX` per file, then status moves. If the records cannot be folded (no `engine.mlearn`), nothing is written and the inbox stays pending.

- Credit (I-07): a followed item gets `INC_HELPFUL` when every outcome of that session passed on the first run, `INC_HARMFUL` when one failed, and only a recorded use otherwise. An owner correction is `INC_HARMFUL`.
- Admission gate for notes: actionable (an imperative, a modal cue such as should/must/never, or a condition followed by a verb); checkable (evidence prefix); new (word Jaccard >= 0.6 or containment >= 0.8 against a live item of the same kind becomes support for it, or a conflict link if the polarity is opposite); not project-specific (no path-like token or file name, no id from `evals/known_project_ids.txt`).
- Pitfalls: a `gate-failed` note becomes `type: "pitfall"` only when the batch holds a failed outcome followed by a passing one in a class the note names; both outcome ids join its evidence.
- Promotion: candidate -> probation on one helpful vote; probation -> active on support from >= 2 sessions AND, when `stats/ml.json` has data, `mlearn.item_score` >= 1.0. One owner-stated record is enough alone. Conflicting items are not promoted; harm (>= 3, more than help) demotes, never an owner-stated item (I-08).
- `learn decay` demotes when `mlearn.retention(item, now)` < `retention.threshold` (fallback: 90 days unused), retires items demoted for a further 180 days, never touches owner-stated items, and does not flag superseded facts as stale.

## Delta operations (`learn apply`)

`ADD`, `INC_HELPFUL`, `INC_HARMFUL`, `EDIT_TEXT`, `SET_STATUS`, `MOVE_SCOPE`, `LINK`, `SUPERSEDE`, `APPEND_STAT`, `ML_FOLD`, `MARK_INBOX`. No operation replaces or deletes a file. Retiring an item moves it to `memory/archive.jsonl`. A delta that would retire more than 10% of a file's items or shrink a file by more than 20% (`stats/ml.json` excepted) is refused whole.

- `SUPERSEDE {old, new}`: sets `valid_to` (the delta's date, exclusive) and `superseded_by` on the old item, `supersedes` and `valid_from` on the new one; both stay on disk. Refused for an owner-stated old item, items of different types, or an item already superseded.
- `EDIT_TEXT {id, text}`: refused when 1 - `difflib.SequenceMatcher` ratio exceeds 0.3 or the new text is under 40 characters (add a new item and `SUPERSEDE` instead).
- `ML_FOLD {records}`: `stats/ml.json` = `mlearn.fold(state, records, mlearn.config(root))`, written with sorted keys. If `engine.mlearn` cannot be imported the delta fails with one line and nothing is written.

## Recall (`brain recall`)

FTS5 with `tokenize='porter unicode61'`, columns text / class tags / id words weighted 1.0 / 0.5 / 0.5, query = distinct non-stop words quoted and joined with OR; a pure-Python port of the same stemmer and of FTS5's `bm25()` is used when FTS5 is missing. Score = BM25 share x confidence x recency x importance x `mlearn.item_score` (1.0 without `stats/ml.json`; owner-stated items always 1.3). Items covering less than `recall.floor` (default 0.15) of the query's IDF weight are dropped, so a weak best match returns nothing. Items outside `valid_from`/`valid_to` are excluded. Default k = 3, budget 300 tokens, greedy coverage packing. Each call from a managed project appends `{at, session, query_sha, ids}` to `.brain/log/recall.jsonl`. Regression: `tests/test_recall.py` on `evals/recall_golden.jsonl`.

## Unclosed sessions (`engine/ledger.py`)

`mark_open(project)` writes `.brain/log/open-session.json` `{session, at}` and returns the previous marker when it belonged to another session; capture (`close` or the Stop hook) clears this session's marker; `repair_unclosed(project, marker)` captures the earlier session from its transcript if it is still on disk, else appends a `ledger` record with `unrecorded: true`, and returns one line for boot.
