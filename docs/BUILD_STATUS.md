# Build status

Where the brain stands after the build session of 2026-11-10. Ticket state is in `docs/plan/tickets.json`; this file is the evidence behind it.

## Done and checked in the build session

| Area | What exists | Check and result |
|---|---|---|
| Core | `CLAUDE.md`, 10 skills, 6 agents, `bin/brain` with 21 engine modules (about 9,500 lines, standard library only) | `brain doctor`: healthy · `brain lint`: 0 errors |
| Always-loaded cost | `CLAUDE.md` 5,356 bytes; project stub 1,150 bytes; descriptions | `brain budget`: about 2,534 tokens in total (cap 3,200) |
| Orientation | `brain boot` | 757 bytes for "Continue" in this session (cap 1,500) |
| Contract v1 | init, adopt, validate, migrate with manifest backup; frozen schema pinned by hash; three frozen fixtures | `tests/test_core.py`, `tests/test_fixtures.py` |
| State and release | one state file; checkpoint that pushes; resume; handover; gates as exit codes; release only on green, fast-forward only | `tests/test_core.py`, `tests/test_hygiene.py` |
| Requirements ledger | strict loader, implied lines, evidence required | `tests/test_core.py::ReqTests` |
| Token ledger | real usage by model and helper from session records | `tests/test_ledger.py`; this session measured below |
| Learning pipeline | inbox, verified evidence, admission gate, delta operations, replay check, supersede, decay, digest | `tests/test_learn.py`, `tests/test_guard.py` |
| Statistical learning | routing bandit, calibration, drift alarms, memory credit, flakiness, forgetting, review stopping, sizing in shadow | `tests/test_mlearn.py` |
| Recall | built-in full-text search, three items by default, silence allowed | `tests/test_recall.py` with the 60-query labelled set: recall@5 0.781, MRR 0.853 |
| Scheduler | critical path plus annealing; skips finished tickets | `tests/test_schedule.py`: annealing matched brute force on 25 of 25 small plans |
| Update radar | 10 sources, conditional requests, leads only | `tests/test_radar.py`; live: 10 of 10 sources in 0.96 s |
| Evaluation | task and run formats, paired statistics, pre-registration, ablation, 12 tasks, 6 seeded defects | `tests/test_evals.py`; `brain eval audit`: 12 sound, 0 broken |
| Lint | commands and flags named in instructions exist; budgets; imports; links | `tests/test_lint.py` |
| End to end | bootstrap → requirement → failing gate → fix → release → close → lesson → consolidate | `tests/test_rehearsal.py` |

**Full gate, last run:** `python3 -m unittest discover -s tests -t .` → 406 tests, OK; `doctor`, `lint`, `hr audit`, `items check`, `eval audit` all exit 0. (Before the HR work: 358 tests, with and without `BRAIN_NO_NETWORK=1`.)

## HR department (added later the same day, at the owner's request)

| Area | What exists | Check and result |
|---|---|---|
| Rack | 100 templates in ten groups, as data that is never always-loaded | `brain hr audit`: 100 templates, sound |
| Guidelines and schema | `hr/GUIDELINES.md`, `hr/template.schema.json`, from four research memos | audit enforces the limits and wording rules |
| Engine | hire, settle, staff, rack, audit, report; settled hires feed the learner | `tests/test_hr.py`: 48 tests |
| Selection accuracy | 200 labelled requests, half never used for tuning | held-out: right template first 78%, in top three 86% (before tuning: 73% and 83%). **Overstated:** on a fresh set written in CB-204 the same selector scores 46% and 63% |
| Real use in this session | two helpers hired through the engine | settled: 54,250 of a 200,000 wage with its check passed; 81,995 of 200,000 with no check |
| Review | fresh-context review of HR (`docs/review/2026-11-10-hr-review.md`) | 2 must-fix, 10 should-fix, 13 minor: both must-fix and all should-fix items fixed with a test each; minor items fixed except those listed below |

Found by using it and by the review, and fixed: wages that swung back down after being raised; a pass that could be recorded without the check running; briefs that pointed at a check nobody had given; long task descriptions that matched no template; the helper cap not applying without a project; one malformed template stopping every hire.

Open for HR:

- Selection is word-based: on a fresh held-out set (CB-204) about one request in three does not surface the right template in the top three. The lead sees the closest candidates and can name one.
- No template runs on the cheapest agent (scout): work that needs commands cannot, and pure reading is usually done by the lead. Four read-only templates run on the reviewer agent at the Sonnet tier instead.
- Wage bands other than medium are starting assumptions until hires of those sizes are settled.
- A wage is a budget that is tracked and settled, not a hard limit: Claude Code has no per-helper token cap, and writing a budget into a brief changes how current models spend.
- A helper with command access could still tamper with files on the same machine; the seal makes that detectable for the check, not impossible in general.
- Template wording has not been tested against real tasks yet. Templates that do badly are flagged by `brain hr report`; rewriting one is a reviewed change.
- Review minor items left: `staff` treats tickets as parallel unless told otherwise; forged inbox records are not distinguishable from real ones; template fields `needs` and `pitfalls` are shown and rendered, `risk` only raises the hire's risk.

## Mutation spot-checks (does a test fail when the rule is broken?)

Each was done in a scratch copy by making the breaking change and running the named tests.

| Invariant | Breaking change | Result |
|---|---|---|
| I-12 | release ignores a missing green gate | caught (`test_rehearsal`) |
| I-12 | release skips the fast-forward check | caught (`test_core`) |
| I-03 | budget cap changed | caught (`test_core`) |
| I-15 | an enum value removed from the frozen schema | caught (`test_fixtures`); the schema hash is now pinned as well |
| I-07 | an external-trust rule allowed | caught (`test_core`, `test_learn`) |
| I-04 | boot byte cap removed | caught (`test_core`); a second test now asserts the 1,500-byte figure itself |
| I-07, I-08, I-10, I-11, I-16 | each broken in `mlearn` | caught (`test_mlearn`, reported by its builder) |

The final reviewer ran 24 further mutations and found three that slipped through (forcing push, boot cap, unseeded scheduler). Tests were added for all three: `test_release_never_uses_a_forcing_push`, `test_boot_never_exceeds_its_byte_cap_whatever_the_state_holds`, `test_same_seed_same_schedule_where_annealing_runs`.

## Reviews and what they changed

| Review | Found | Outcome |
|---|---|---|
| Audit of the instruction surface (`docs/research/round2/10-audit.md`) | 6 blocking, about 17 should-fix | All blocking and should-fix items applied |
| Final fresh-context review (`docs/review/2026-11-10-final-review.md`) | 7 blocking, 22 should-fix, 22 minor | All 7 blocking fixed, each with a reproducing test. All 22 should-fix items addressed (S20 by correcting the spec; S9's flakiness score is exposed as a command but not yet consulted by `release`). Minor: about half fixed; the rest listed below |

Blocking items from the final review, all fixed: a model could label its own note as stated by the owner (now verified against what the owner typed); a crafted path could write outside the learned zone; a checkpoint could push ungated work to the release branch; a corrupt ledger line was silently dropped; the test suite depended on the brain's own recorded state; the CI check would have been red by construction; this file was missing.

## Open, with reasons

| Item | Why open |
|---|---|
| GitHub's automatic checks do not start on this account | Every run ends as failed within about four seconds, before any step. `NEEDS_YOU.md` item 7. Until fixed, nothing is enforced on GitHub; the same checks pass inside a session |
| Learned zone not locked | By decision D-08: lock at tag `brain-v1.0.0` after the live checks |
| The brain is on its working branch, not `main` | `NEEDS_YOU.md` item 1 |
| No measured comparison against the earlier way of working | Needs live sessions (CB-109). No efficiency claim is made until then |
| Duplicated wording between memory items and method files | Harmless while both are on demand; five items overlap the always-loaded file. Left in place because the labelled recall set refers to item ids |
| Minor review items not fixed | M6 (success output mixes the last lines of both streams), M8 (repo map lists generated files), M15 (radar thread shutdown may add seconds at exit; not measured), M16 (logs outside a project go to a temporary folder), M17 (`close` options are declared by the model), M18 (two tunables still inline), M19 (lead field names), M20 (radar state changes the brain tree daily), M22 (routing examples mention trips) |
| Gate and release do not consult the flakiness score automatically | It is available as `brain ml flaky`; wiring it into `release` waits for real data |

## Needs a live session (cannot be closed from inside the build session)

| Ticket | Check |
|---|---|
| CB-101 | The brain's `CLAUDE.md`, skills and agents load beside a project and `boot` runs from the first message. Partly seen: the skills and agents appeared live in the build session |
| CB-102 | A quick question gets an answer with zero process steps |
| CB-103 | "New project: …" on an empty repo: contract installed, at most three questions, first item started |
| CB-104 | End a session mid-item; "Continue" in a new chat resumes the same item |
| CB-105 | Helpers honour model, effort and skip-handbook settings (visible in the ledger) |
| CB-106 | Whether hooks installed through the cloud environment load in two-repo sessions |
| CB-107 | Whether a skill's own hooks fire after it is used |
| CB-108 | Pushing to both repositories from one session, with branch protection on the brain |
| CB-109 | An A/A run, then the first paired benchmark with and without the brain |
| CB-110 | A first real project end to end |
| CB-111 | The plugin manifest loads on desktop |
| CB-112 | Whether an effort change keeps the prompt cache |

## What the build itself cost (measured by `brain ledger`)

- About 131 minutes, 30 helpers, about 198 million tokens, about $123 at list prices (a subscription pays no per-token charge; this is the list-price equivalent).
- Helpers were 73% of the cost. The first ten analysts ran on the session's model because nothing set theirs; later helpers used the brain's own agents or an explicit cheaper model. That is the reason every brain agent file sets its model.
- The main conversation read 99% of its input from cache. Three tool results exceeded 5,000 tokens.
- This was a deliberately heavy session: two research rounds of ten agents each were asked for by name. It is not a baseline for normal work.

## Improvement session, 2026-11-10 (tickets CB-200 to CB-209)

### CB-200 Baseline (all commands run in this session)

| Check | Result |
|---|---|
| `python3 -m unittest discover -s tests -t .` | Ran 407 tests in 31.9s, OK |
| `brain doctor` | brain is healthy (always-loaded budget about 2,550 tokens) |
| `brain lint` | 0 errors, 0 notes |
| `brain hr audit` | 100 templates in 10 groups; scout 0, researcher 17, builder 48, writer 19, reviewer 15, redteam 1; rack is sound |
| `brain lint --transcript` | 0 oversized results, 0 re-reads, cache read 82% |
| `brain items check` | 141 items in 9 files, all valid |
| `brain eval audit` | 12 tasks, 12 sound |
| `brain learn consolidate` | first real delta `d-20261110-a431e755f2`: 1 ledger row, 2 records folded into statistics, 1 inbox file consolidated |
| `brain learn verify` | 1 delta replayed on origin/main; learned zone matches |

### CB-202 End-to-end trial on a scratch project

A command-line tip splitter, built in a scratch repository with a local bare remote, by the brain's own flow: `boot`, `init`, `validate`, three ledger lines, plan and tickets, `plan schedule`, `hr staff`, two helpers hired with `hr hire` (both Sonnet builders, plain briefs: no template fit), `hr settle` (both checks passed; used 4,478 of 60,000 and 4,294 of 20,000 tokens), `req verify`, `release --run-gates --push` (pushed on green), `checkpoint`, `resume`, `boot` in work mode. Ledger for the whole session at that point: $5.72, helpers 38%; the two Sonnet helpers together cost $0.09, cache read 98%.

What was wrong, and the fix (each with a test):

| # | Problem met in the trial | Fix |
|---|---|---|
| 1 | `boot` looked only at folders beside the brain and ignored `BRAIN_PROJECT`; it had no `--project` while every other command does | `boot --project` and `BRAIN_PROJECT` (engine/detect.py) |
| 2 | "a command-line tip calculator … with tests" routed to knowledge: the typo tolerance read `tests` as `tesis` | a word any vocabulary knows exactly is never read as a slip for another, except singular/plural (engine/route.py); routing set unchanged at 107/107 size, 105/107 class |
| 3 | `req add` refused a second line quoting the same sentence, while the plan skill says to split sentences into checkable lines | a repeat is now the same words with the same "passes when" (engine/req.py) |
| 4 | Every ledger line stores a check command, but nothing ran them; the lead re-ran each by hand | new `brain req verify`: runs each open line's check, marks it done with the result on exit 0 (engine/req.py; skills brain-build, brain-verify, brain-plan updated) |
| 5 | `init` always recorded `main` as the release branch; on a `master` repo `release` created a new `main` | `init` records the remote's default branch (engine/contract.py) |
| 6 | "Helpers only when they pay" was never enforced: without `--material-tokens` every hire passed | for `--size S` the material is estimated from the input and owned files; a small job is refused with the reason (engine/hr.py) |
| 7 | "New project:" requests said "no task verb; answer or acknowledge" | reason now names the family default |

Observed, not changed: the default wage band (M, 60,000) was about 13 times what a small item used; wages calibrate from settled hires, so this should correct itself with data. No rack template fits "write a small module with tests"; noted for CB-204/CB-205.

### CB-204 Template selection, measured honestly

- A helper wrote `evals/hr_golden_2.jsonl` (100 requests, a quarter in Spanish, one first-choice per template) without running the selector; it was committed (28d64d3) before any change.
- Baseline on it: top-1 46/100, top-3 63/100. The earlier held-out set (78 and 86) had been looked at during tuning and overstated accuracy.
- Tried, measured on the old held-out set only: prefix matching for inflection and typos (no change), adding the role line (+1 top-3, -4 top-1 on dev), adding the labelled requests as example phrasings per template (top-3 86 → 90).
- One final measurement on the new set, with examples from both old sets: top-1 46 → 54, top-3 63 → 65. The rule set in the ticket keeps a change only for at least +3 top-3 points, so **nothing was kept**. A test now holds the new set's floor (0.42 / 0.59).
- What would help: matching on meaning rather than words, which the standard library cannot do well; or showing the lead the top three (already done) and letting outcomes (`brain hr report`) steer. Recorded as unproven, not fixed.
- Also found: no template fits "write a labelled evaluation set" (the selector offered `owner-computer-guide`); `hr hire --template none` now gives a plain brief on purpose.

### CB-201 Live platform checks (one-repository cloud session, 2026-11-10)

| Question | Observed in this session | Verdict |
|---|---|---|
| Does the PreToolUse hook in `.claude/settings.json` fire? | With `learned_zone_locked` set to true for one probe, a Write to `memory/_hook_probe.txt` was refused by the hook with its own message; the file was not created. The lock was then restored (VERSION.json unchanged in git) | **fires** in a one-repository session |
| Does the Stop hook fire? | Not observable inside one turn: this session ran as a single long turn. Its trace is a `ledger` record for the session in `learning/inbox/`; check at the next turn | open |
| Do a skill's frontmatter hooks fire? | No brain skill declares hooks (`grep hooks: .claude/skills/*/SKILL.md` finds none) | nothing to check; not used |
| Do helpers honour model? | Six helpers: transcripts show claude-sonnet-5-5 for the three hired on Sonnet, claude-opus-5-5 for the three hired on Opus | **honoured** |
| Do helpers honour effort? | Helper context prefix records `effortValue` high for the reviewer (hired high) and medium for builders and writers (hired medium) | **honoured** |
| Do helpers skip the handbook (`omitClaudeMd: true`)? | No helper prefix (2.2–11 KB) contains the brain's CLAUDE.md text | **honoured** |
| Does changing effort mid-session keep the prompt cache? | This session cannot change its own effort | not testable here; needs the owner to switch effort in a live chat (CB-112 stays open) |

These are observations, not facts from an official page, so none was recorded through `brain learn note --trust external`.
