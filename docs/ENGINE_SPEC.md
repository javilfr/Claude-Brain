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

Zones (`engine/guard.py`): `inbox` (append only, see S14 below), `state` (`learning/radar/`, rewrites allowed, ignored by `learn verify`), `learned` (the five directories, `learn apply` only), `kernel` (everything else, plus the hand-written files named above and `learning/PROMOTION_RULES.md`). `zone_of` normalises the path first (`posixpath.normpath`); a path that escapes the brain root is `kernel`.

Paths in a delta: every `file` an op names must be plain (relative, already in normal form, no `.`/`..`/empty segment, no backslash). `ADD` accepts only `memory/items.jsonl`, `memory/facts.jsonl`, `owner/standing.jsonl`, `owner/preferences.jsonl` and `playbooks/<family>.jsonl`; `APPEND_STAT` only `stats/ledger/YYYY-MM.jsonl`; `MARK_INBOX` only `learning/inbox/<name>.jsonl`. Anything else refuses the whole delta. An `ADD` of an owner-stated item needs verified owner evidence (below).

Seeded item files are canonical (one object per line, keys sorted, as `learn apply` writes them) and `playbooks/*.md` are rendered from them, so the first delta changes only the lines it adds or edits.

## Inbox record shape (`learning/inbox/<date>-<session>.jsonl`)

One JSON object per line. Every record has `kind`, `session`, `at` and a stable `id`: the first 16 hex characters of sha256 of `session`, `kind` and a per-kind key (shown below), so the same event recorded twice has the same id and `mlearn.fold` is idempotent per record.

- `kind: "ledger"` (key: none, one per session) — `family`, `task_class`, `classes`, `tier`, `outcome`, `model` (main conversation's alias), `models` (per model: `in`, `cache_write`, `cache_read`, `out`, `cost`), `helpers`, `cache_read_share`, `wall_minutes`. A session that ended without `close` and whose transcript is gone gets `unrecorded: true` and `started` instead of usage. `close` with no transcript on disk still writes the ledger and outcome records from the gate log, with `usage: "unknown"`, `models: {}` and null `cache_read_share`/`wall_minutes`, clears the open-session marker and exits 0.
- `kind: "outcome"` (key: `task_class`) — judged only by this session's gate exit codes: `task_class`, `family`, `tier`, `risk`, `model` (alias), `model_id`, `effort`, `has_check` (a command gate with a non-empty command ran), `passed` (every gate's last run green), `first_pass` (every gate's first run green), `rework` (red runs before the last), `tokens`, `cost`, `minutes` (split evenly across classes; all null with `usage: "unknown"` when there was no transcript), `est_tokens`, `est_minutes` (null when not estimated), `explored`, `propensity`, `gate_runs` (`gate`, `exit`, `commit` as a 12-hex hash), `evidence`; with `close --request "<text>"`, also `rule_tier` (the tier `route.classify` gives the request) and `words` (sorted distinct `sha256(salt + "\n" + word)[:12]` of its content words; the salt is created once in the project at `.brain/log/salt`, so hashes are not comparable across projects; the text itself is never stored). `mlearn.fold` feeds `words`/`rule_tier`/`tier` to the sizing learner as weak labels, shadow only.
- `kind: "used"` (key: `item`) — `item` (id), `followed` (bool). There is no `helped` field: whether an item helped is derived from the session's outcomes (I-07); a `helped` field found in the inbox is ignored and reported.
- `kind: "note"` (key: the text) — a lesson candidate: `text` (400 characters at most), `class` (list), `scope`, `trust` (`observed`, `owner-stated` or `external`), `evidence` (list, see below), `signal` (`gate-failed`, `rework`, `owner-correction`, `token-outlier`, `first-success`), `source` for external facts.
- `kind: "review"` (key: `task_class` and `round`) — `task_class`, `round`, `found_a`, `found_b`, `both`, optional `blocking`. Written by `brain learn review --found-a N --found-b N --both N [--class C] [--round R]`, which prints `mlearn.review_stop`'s answer in one line.
- `kind: "correction"` (key: `item` and first evidence) — an owner correction: `correction` (`sizing`, `fact` or `quality`), `evidence` (verified owner evidence only), `item` (fact, quality), or `rule_tier`/`tier` and optional salted `words` (sizing). Written by `brain learn correction --kind K --quote "<his words>" [--item ID] [--from-tier N --to-tier N] [--request TEXT]`. Consolidation turns a correction with an item into `INC_HARMFUL`; every valid correction is folded (a sizing one is a strong sizing label).

Evidence (`learn note`), checked by script before anything is written; `learn note --help` prints the same list:

- `gate:<gate-id> [words]` — a run of that gate by this session in the resolved project's `.brain/log/gates.jsonl`.
- `test:<name>` — `<name>` occurs in the saved output of a gate run (its `log`) or a run log of this session.
- `run:<log-file>` — a log in the project's `.brain/log/run/` whose name time (UTC) is at or after this session's start (its open-session marker, else the first transcript timestamp).
- `outcome:<record-id>` — an outcome record of this session in the brain inbox.
- `review:<file>` — an existing file (absolute, or relative to the project or the current directory); stored as `review:sha256-<12 hex>` of its content so no path reaches the brain.
- `owner:` — never typed by the model. `--quote "<his words>"` is case-folded and whitespace-collapsed (at least 12 characters) and must occur in a turn the owner typed in this session's main transcript (`common.transcript_paths`): a `user` row whose content is a string or text blocks, not a tool result, not `isMeta`/`isSidechain`, and without `[SYSTEM NOTIFICATION`, `Another Claude session sent a message`, `Stop hook feedback`, `[Subagent hand-back]`, `<task-notification>` or `<system-reminder`. It is stored as `owner:turn@<turn timestamp>#<sha256-12 of the normalised quote>`; the quote is not stored. No transcript or no match: one-line refusal, exit 1.
- With no managed project resolved, only `--quote` and `review:` are accepted. `--trust owner-stated` requires `--quote`.
- A brain-bound note (scope `global` or `family:*`) whose text or evidence (other than `review:`) names a path or file, an id from `evals/known_project_ids.txt`, or the resolved project's manifest id, title or folder name is refused at `learn note` time and never written.

At consolidation a note whose `owner:` evidence is not in the verified form, or an owner-stated note without it, is rejected, and so is a correction without it.
- `kind: "lead"` (key: `url`) — written by the radar for every relevant new item (`--max`/`max_lines` caps only the printed lines): `source`, `trust` (`official`, `research`, `community`), `title`, `url`, `date`, `matched` (the relevance words that selected it; the review called this `keywords`). The record id is the radar's own item id, a hash of the source id and the feed's own item id (`_stable_id`). A lead never changes memory; `learn status` counts unhandled official ones and consolidation lists them, then marks them handled with the rest of the file. `brain radar` and boot's radar do nothing when `BRAIN_NO_NETWORK` is set (`brain radar` prints one line saying so and exits 0).

Reading the inbox: each line is decoded on its own (`common.read_jsonl_counted`, `errors="replace"`), so a bad byte costs one line. `learn status` and `learn consolidate` report the number of unreadable lines; a file is marked handled only when every valid record read from it was processed, and a file that cannot be read stays pending.

Rewrites (`learn verify`): an inbox file may only grow, except that a file not yet marked handled in the manifest may be rewritten when every old and new line is a valid record (`kind`, `session`, `at`) of one and the same session — what `close` and the Stop hook do when they re-record a session.

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

## Gate flakiness (`brain ml flaky <gate-key>`)

Prints `mlearn.flaky`'s estimate for one gate in one line (`--json` available), so the gate skill can decide to re-run a red gate once on the same commit. `gate` and `release` do not consult it automatically yet.

## Unclosed sessions (`engine/ledger.py`)

`mark_open(project)` writes `.brain/log/open-session.json` `{session, at}` and returns the previous marker when it belonged to another session; capture (`close` or the Stop hook) clears this session's marker; `repair_unclosed(project, marker)` captures the earlier session from its transcript if it is still on disk, else appends a `ledger` record with `unrecorded: true`, and returns one line for boot.

## HR records

- `kind: "hire"` (written by `brain hr settle`, folded by `mlearn.fold` through `hr.fold_hire`): `id`, `session`, `at`, `template`, `group`, `base_agent`, `size`, `model`, `effort`, `task_class`, `family`, `risk`, `has_check`, `explored`, `propensity`, `wage_tokens`, `band_tokens`, `actual_tokens` (all in output-equivalent tokens), `passed` (true or false only when the script ran the contract's check; otherwise null), `sealed` (true when the check that ran was the one fingerprinted at hire time; only sealed results move a template's pass record). No project name, path or task text.
- Contracts and briefs live in the project: `<project>/.brain/log/hr/<contract>.json` and `.md`. With no managed project they go to a per-session temporary folder. Check fingerprints (seals) are kept in a separate per-session temporary folder, outside the project.
- `hr/` (templates, schema, guidelines) is kernel zone.

