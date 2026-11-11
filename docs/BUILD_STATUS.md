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
| Selection accuracy | 200 labelled requests, half never used for tuning | held-out: right template first 78%, in top three 86% (before tuning: 73% and 83%) |
| Real use in this session | two helpers hired through the engine | settled: 54,250 of a 200,000 wage with its check passed; 81,995 of 200,000 with no check |
| Review | fresh-context review of HR (`docs/review/2026-11-10-hr-review.md`) | 2 must-fix, 10 should-fix, 13 minor: both must-fix and all should-fix items fixed with a test each; minor items fixed except those listed below |

Found by using it and by the review, and fixed: wages that swung back down after being raised; a pass that could be recorded without the check running; briefs that pointed at a check nobody had given; long task descriptions that matched no template; the helper cap not applying without a project; one malformed template stopping every hire.

Open for HR:

- Selection is word-based, so about one request in seven does not surface the right template in the top three. The lead sees the closest candidates and can name one.
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
| Audit of the instruction surface (`docs/research/round2/10-audit.md`) | 6 blocking, about 17 should-fix | All blocking items and all should-fix items but one applied. C2 (a stop before one-way steps) was missing, as the 2026-11-11 red team found; it was applied then |
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

## Baseline of the improvement session (2026-11-10, CB-200)

Every number below is from a command run in this session, before any change to the brain.

| Check | Result |
|---|---|
| Full gate `python3 -m unittest discover -s tests -t .` | 407 tests, OK, 30.4 s |
| `brain doctor` | healthy; always-loaded budget about 2,550 tokens; model facts verified 0 days ago |
| `brain lint` | 0 errors, 0 notes |
| `brain hr audit` | 100 templates in 10 groups, sound (scout 0, researcher 17, builder 48, writer 19, reviewer 15, redteam 1) |
| `brain items check` | 141 items in 9 files, all valid |
| `brain eval audit` | 12 tasks, 12 sound, 0 broken |
| `brain budget` | `CLAUDE.md` 5,423 B, project stub 1,150 B, 6 agents, 10 skills, about 2,550 tokens |
| `brain lint --transcript` | 0 results over 5,000 tokens, 0 re-reads, 1 model, 0 helpers, 93% input from cache |
| `brain learn consolidate` (first real delta) | `d-20261110-a431e755f2`: APPEND_STAT 1, MARK_INBOX 1, ML_FOLD 1; 1 ledger row, 2 records folded, 1 inbox file |
| `brain learn verify` | 1 delta replayed on `origin/main`; learned zone matches |
| `brain learn status` | 141 active items, 0 candidates, 0 in conflict; inbox empty |

Difference from the handover: it said three inbox records were pending; consolidation found one inbox file holding the ledger row and the two settled hires (three records in one file).

## End-to-end trial on a scratch project (2026-11-10, CB-202)

A Python unit converter (km/miles, kg/lb, C/F, with tests) in a scratch repository with a local bare remote, run as a live lead would: boot, init, six-line requirements ledger, tickets, `plan schedule`, `hr staff`, two hires through `hr hire`, settle, gate, release, checkpoint, resume, handover.

| Step | Result |
|---|---|
| Helpers | T1 (convert.py): plain brief on sonnet, used 4,647 of a 60,000 wage, check passed. T2 (tests, 10 tests): plain brief on sonnet, used 3,817 of 20,000, check passed |
| Gate and release | `gate --all` exit 0; `release --push` fast-forwarded the remote's `master` to the gated commit |
| Requirements | 6 of 6 done, each with a log from `req verify` |
| Handover | refused while the brain had uncommitted changes; ready once they were committed and pushed |
| Session so far (`brain ledger`) | main model 13.9M tokens read from cache (99%), helpers 43% of cost, $5.98 in total at list prices including the CB-205 reviewer still running |

Found and fixed, each with a test:

1. `boot` and `detect` looked only at the folders beside the brain, ignoring `--project`, `BRAIN_PROJECT` and the current repository, which every other command honours. Run from inside the project, boot said "no project attached".
2. "a command-line unit converter in Python … with tests" was routed to long-form writing: "tests" matched "tesis" within one edit and won the tie. Exact matches now outweigh one-edit matches, and programming words were added.
3. A tickets file written from memory (`minutes`, `depends`, `check`) was rejected by `plan schedule` and silently read by `hr staff` as "no acceptance command". Everyday names now map to `est`, `deps`, `accept`, and the plan skill names the fields.
4. There was no way to force a plain brief once a template matched. `--template none` now does; the paired evaluation in CB-203 needs it.
5. Each requirement already held its check, yet the lead had to run them one by one and copy the results. `brain req verify` runs them and records passes as evidence.

Found and left for the ticket that owns them:

- Selection (CB-204): `hr staff` picked no template for "Conversion core: convert.py with a convert function …", although `hr rack --search` puts `cli-script-builder` first for similar wording.
- Templates (CB-205): `cli-script-builder` requires a dry-run flag and a "second run changes nothing" check, which mean nothing for a tool that changes no files. The rack has no template for writing unit tests for an existing module.
- Wages: both small items used under a fifth of their wage (0.08 and 0.19). The learner adjusts bands from settled hires; two are not enough to move them.
- `init` writes no root `.gitignore`, so `__pycache__/` was committed in the trial. Left open: it changes what the frozen contract installs.
- `brain close` was not run for the trial on its own, because this session closes once at its end and a second close of the same session would be skipped as already consolidated.

## Live platform checks in a one-repository session (2026-11-10, CB-201)

Observations from this session, not confirmed by an official page, so none was recorded as a fact through `brain learn note`.

| Question | Observation | How it was seen |
|---|---|---|
| Does the `PreToolUse` hook in `.claude/settings.json` fire on an edit? | Yes | The hook was made to append to a marker file, one `Write` was made, the marker read `fired`; the hook was then restored byte for byte (`git status` clean) |
| Does `guard_paths` block an edit to `memory/`? | Not while the zone is unlocked, as designed | A `Write` to `memory/_hook_probe.txt` went through (file removed at once); the hook exits 0 unless `VERSION.json` sets `learned_zone_locked` (decision D-08) |
| Does the `Stop` hook (`session_end`) fire? | Not observable inside one turn | It runs when a turn ends; check at the start of the next turn that this session's ledger row reached `learning/inbox/` before `close` |
| Do a skill's own frontmatter hooks fire? | Nothing to test | No skill in `.claude/skills/` declares `hooks:` |
| Do helpers honour model and effort? | Yes for the values passed on the call | Each helper transcript's messages carry the requested model (reviewer `claude-opus-5-5`; both builders `claude-sonnet-5-5`); each `.meta.json` records the requested effort. The model was also passed on each call, so this does not prove the agent file's own `model:` line alone |
| Do helpers skip `CLAUDE.md` (`omitClaudeMd: true`)? | Consistent with yes | None of the three helper transcripts contains the `CLAUDE.md` text ("Evidence before claims", "Contents of …"), which the main transcript carries |
| Does changing effort mid-session keep the prompt cache? | Not tested | Effort is changed by the person (`/effort`), not by the lead; it needs a session where the owner does so, then `brain ledger` before and after |

## Progress on CB-204, CB-205 and CB-206 (2026-11-10, in progress)

**CB-204, selection.** A new held-out set, `evals/hr_golden_2.jsonl` (100 requests: 60 English, 40 Spanish, 10 per group, written by a helper who saw only each template's id, group, name and role line), was committed alone in `1ad621a` before any change. The selector as it stands:

| Set | Top-1 | Top-3 |
|---|---|---|
| dev (tuned on) | 1.00 | 1.00 |
| old held-out | 0.78 | 0.86 |
| new held-out | **0.32** | **0.35** |

The old held-out figure overstated real accuracy: its requests share the selector's own wording. Improving selection on dev and the old set, then measuring once on the new set, is the next step. Caveat for that measurement: the new set was written from the role lines, so a change that weights role lines more would be partly informed by knowing that.

**CB-205, templates.** The fresh-context review is `docs/review/2026-11-10-template-review.md`: 46 rubric rows, 30 met, 16 wrong. The headline findings are 61 method lines with no reason; 18 templates on agents without Bash that require `{check}`; 16 third pitfalls never rendered; 30 briefs rendering above 350 words; the hygiene line keyed only on the base agent; and three near-duplicate pairs. The trial adds two more: `cli-script-builder` asks side-effect-free tools for a dry run, and no template writes unit tests for an existing module. None is fixed yet. The reviewer used 220,287 tokens of a 200,000 wage.

**CB-206, open review items.** Fixed, each with a test: M6 (a success digest shows one stream), M8 (the repo map skips `.brain/log/` and files git ignores), M15 (measured 6.08 s for a 1 s radar budget when a request hangs; daemon threads bring it to 1.08 s), M18 (promotion bar read from `ml_config.json` `learning.promote_multiplier`, default unchanged at 1.0), M20 (radar check times, status and validators moved to the untracked `learning/radar/checks.json`; the tracked state changes only when new items are seen). Still open: M19 lead field names, the `staff` parallel default, forged inbox records, a use for the scout tier.

**Full gate at this point:** 417 tests OK; `doctor`, `lint`, `hr audit` exit 0.

## CB-204 result: selection (2026-11-11)

Changes in `hr.select`: word scores blended with character-trigram similarity (weight 0.25; trigrams catch inflection, accents and dictation slips), and a stricter admission rule (word admission needs two shared words; trigram admission needs a score of 0.2 or more and one shared word). Tuned on dev, the old held-out set and a new 20-request negative set (`evals/hr_negatives.jsonl`, requests no template fits).

| Set | Before | After |
|---|---|---|
| dev, top-1 / top-3 | 1.00 / 1.00 | 0.94 / 0.99 |
| old held-out, top-1 / top-3 | 0.78 / 0.86 | 0.80 / 0.91 |
| negatives given a template (lower is better) | 14 of 20 | 12 of 20 |
| **new held-out, top-1 / top-3** | **0.32 / 0.35** | **0.45 / 0.55** |

Verdict: kept. Top-3 on the new held-out set rose 20 points, against a bar of 3.

How clean the measurement is: the new set was looked at three times, not once. First 0.45 / 0.58 with the configuration fixed in advance. Then twice more while the admission rule was settled, each time prompted by evidence outside the set: an existing fixture test, then a false pick seen in the trial. Each change made the new-set number worse, not better, so the set did not steer the tuning. The test floors are 0.42 and 0.52.

Still weak: on requests worded the way the owner dictates, the right template is in the top three only about half the time, and 12 of 20 vague requests still get a template. Two things keep the harm small. The lead sees the candidates and the closest list, and can name a template or use `--template none`. And small items are done by the lead without a hire.

One test input was changed. The fixture test that a weak fit is "offered, not chosen" used a long review request that now rightly matches `code-reviewer` (trigram 0.31, two words). It now uses a request that is weak on both measures; the behaviour it checks is unchanged.

## CB-203 result: first paired evaluation (2026-11-11)

Both comparisons were pre-registered and committed before the first trial (`evals/prereg/aa-plain-brief.json`, `evals/prereg/hr-template-vs-plain.json`). The 8 dev tasks were used, and the 4 held-out tasks were not touched. Every trial ran in a clean folder, with the task's grader as its acceptance command. `brain hr settle` measured tokens and `brain eval grade` graded the result independently. Runs: `evals/runs/aa.jsonl`, `evals/runs/ab.jsonl`.

| Comparison | Pass | Tokens | `brain eval compare` |
|---|---|---|---|
| A/A: plain brief vs plain brief | 8/8 and 8/8 | within 2% (5 wins, 3 losses) | **not proven**, as an A/A must be; this is the noise level |
| A/B: plain brief vs brief with the automatically chosen template | plain 8/8, template 6/8 | 17,409 vs 32,805 (+80%) | **revert** (7 of 8 worse; P(template worse) 0.98; sequential test accepts "not better") |

Why the templates lost: the automatic pick was the wrong kind of helper on 7 of 8 tasks. `ticket-slicer` was chosen for two sizing questions, `copy-editor` for a code fix, `coverage-analyst` for adding a function, and `source-harvester` for a memo. The read-only reviewers `back-translation-checker` (translation) and `rubric-mapper` (an idempotency fix) did not do the work at all: they reviewed it and failed.

What changed because of it:

1. `brain hr hire` writes a plain brief by default and lists the closest templates. A template is used only when the lead names it (`--template <id>`); `--template auto` keeps the old behaviour. `hr staff` reports "plain (closest: …)". The build skill says to name a template only when it is clearly the same kind of work.
2. Selection demotes read-only templates for a request that asks for something to be made or changed (factor 0.6). This was tuned on dev, the old held-out set and the negatives only; the new held-out set was not looked at again. Dev top-1/top-3 0.94/0.98, old held-out 0.81/0.92.
3. A plain helper given a command check now gets the builder agent. It was getting the researcher, which has no shell to run its check.

What this does not show: whether a correctly chosen template beats a plain brief. These tasks are small, and the template arm mostly ran the wrong template. That needs a run where the lead names a matching template, on tasks bulky enough for method lines to matter.

## CB-206 close (2026-11-11)

All items on the list are handled:

| Item | Outcome |
|---|---|
| M6 success output mixes streams | fixed, tested |
| M8 repo map lists generated files | fixed, tested |
| M15 radar thread shutdown | measured 6.08 s for a 1 s budget; fixed (1.08 s), tested in a subprocess |
| M18 tunables inline | promotion bar configurable; the recall floor already was; tested |
| M19 lead-record field names | the spec now describes what the code writes (`id` formula, `matched`); the code, its tests and consolidation agree |
| M20 radar state dirties the tree | per-run fields untracked; tested |
| `staff` parallel default | parallel only when the schedule overlaps tickets; tested |
| a use for the scout tier | `--agent scout` for file lookups, documented in the build skill; tested |
| forged inbox records | **accepted risk, not fixed.** Anything that can write the inbox can write a valid-looking record: the model, a helper, or a person with the repository. A signature would need a key the model cannot read, and none exists in this environment. What limits the harm: pass counts move only on records whose check this engine ran under a seal (I-17); owner-stated notes need the owner's words in the session transcript; every inbox change arrives as a commit the owner can see; and `learn verify` replays deltas against `main` |

## CB-207 result: research round four (2026-11-11)

- **Radar** (`brain radar --force`): 10 sources checked in 0.72 s, 12 new items. The four official leads are about the enterprise Compliance API (security-posture data); none touches models, Claude Code, skills or agents. Consolidation listed them and marked them handled.
- **Facts re-verified** against today's official pages (`docs/research/round4/01-facts-recheck.md`; every URL fetched this session). 12 of 18 confirmed. 4 corrected through a delta (`d-20261111-facts-recheck`): the long-context premium is Haiku-only and cache reads are 2.5%, 5%, 5% and 10% of input; MCP changes break the cache only for tools that are not deferred; Opus alone is 0.827 at $200 at medium, 0.850 at $236 at high; Fable's deep-research gain is 3.3 points, high over low. 2 have no official page: `fact-two-repo-loading` now says loading from both repositories is observed, not documented; `fact-cost-shape` is a local measurement. All four `models.json` entries match the pricing page.
- **New facts**, recorded through `learn note --trust external` and consolidated as candidates. Changing effort mid-session keeps the cache in Claude Code on these models (API key or subscription; not on Bedrock, Vertex or gateways), which closes the open question CB-112 from the official page. Skill descriptions share a budget of 1% of the context window; on overflow the least-invoked lose their descriptions first, and every name stays. MCP tools are deferred by default. Cache-read shares by model.
- **Persona prompts:** the general guide still says a one-sentence role "focuses Claude's behavior and tone". The Fable 5.2 and Opus 5.5 guides have no persona section; the Fable guide shows that ownership framing changed results at about 1.5 times the output. The brain's rule stands unchanged: one role line, no "expert" persona.
- **Pointer versus pasted brief:** measured, `docs/research/round4/02-pointer-vs-inline-brief.md`. The pointer stays.
- Found while recording: the rehearsal test counted every candidate item in the copied brain, so it would have gone red the first time the brain learned a candidate fact. It now checks that the session adds exactly one.

## CB-208 result: red team and final independent review (2026-11-11)

**Red team** (`docs/review/2026-11-11-redteam.md`). It ran on Opus 5.5 at high effort, because Fable 5.2 hit this account's usage limit. 3 blocking, 2 should-fix:

| Finding | Outcome |
|---|---|
| Learning never reaches `main`; parallel consolidations conflict | **Confirmed by simulation:** two branches consolidating from the same base conflicted in `stats/ml.json`, `learning/manifest.jsonl` and `learning/CHANGELOG.md`. Fixed with a single writer: `learn consolidate` refuses with a project attached, or on a branch behind `origin/main`. Radar leads now go to a per-session inbox file, so working sessions only ever add files that cannot conflict. Tested |
| Owner rules can be rewritten (I-08) | Fixed: editing, moving, demoting or retiring an owner-stated item needs owner evidence verified against a typed turn. Tested |
| No stop before one-way steps | Fixed in `CLAUDE.md` and brain-start: such a step waits for the owner's yes in `NEEDS_YOU.md` while the rest continues (D-14). Tested by text |
| Evaluation hires skew wages | Confirmed: the M band was already at 0.40x. `hr hire --eval` hires no longer train wages or template records (tested). The trials already folded stay in the wage window until 30 real medium hires replace them; until then, medium wages read low. A wage is a tracked budget, not a limit |
| All enforcement is warn-only | Unchanged; it depends on `NEEDS_YOU.md` items 2 and 7 (GitHub checks and branch protection) and on the lock in decision D-08 |

**Final review** (`docs/review/2026-11-11-final-review.md`, 52 rows: 41 met, 9 partly, 2 not met at the time). The reviewer reproduced each finding with commands.

| Finding | Outcome |
|---|---|
| D1 blocking: `learn apply` trusted every field of a hand-written delta (I-07, I-08, R-03 not met) | Fixed. By hand, a delta may only curate. Adding items, credit, statistics and promotion come only from consolidating verified records; the time stamp is set to now; pasted owner evidence is refused. All five of the reviewer's attack deltas are refused. Tested |
| D2 blocking: a CLI test wrote eight contracts into the project beside the brain | Fixed: `BRAIN_PROJECT=none` means no project, and the HR and note tests use it. Tested |
| D3 the rehearsal used the live network | Fixed: it runs with `BRAIN_NO_NETWORK=1` |
| D4 the boot radar ran on every boot (a regression from M20) | Fixed: it reads check times where the radar writes them. Tested |
| D5 live checks had no steps | Each of CB-101 to CB-112 now has exact steps; CB-105 and CB-107 are observed, CB-109 (HR part) and CB-112 done |
| D6 stale figures in `docs/REQUIREMENTS.md` | Fixed in CB-209 |
| D7, D8 output caps | Fixed: a bare group prints its short usage, and radar output fits in `--max`. Tested |
| D9 release ignored a failed fetch | Fixed: release refuses when origin cannot be reached or the fetch fails. Tested |
| D11 "explain … and then rebuild it" was sized as an answer | Fixed. Tested |
| D10, D12, D13 | Left: no project ids exist yet to list; a weak acceptance check in this session's own hire (noted); `mlearn.sizing_hint` is exposed but unused (the sizing model runs in shadow, as designed) |

Remaining hole, stated plainly: someone with write access to the repository can still commit a hand-made delta together with the manifest and learned files. `learn verify` replays deltas through the engine, which refuses unauthorised owner changes, but not every hand-written op. Only branch protection with the check running (`NEEDS_YOU.md` items 2 and 7) closes this.

## State at close of the improvement session (2026-11-11, CB-209)

**Full gate at close:** `python3 -m unittest discover -s tests -t .` gives 436 tests, OK (407 at the start). `brain doctor`, `brain lint`, `brain hr audit`, `brain items check`, `brain eval audit` and `brain learn verify` all exit 0. All ten tickets CB-200 to CB-209 are done.

What is true now, each line backed by a section above:
- Boot finds the project the same way every other command does. Routing no longer mistakes "tests" for "thesis", or a question followed by work for a plain question.
- `brain req verify` runs each requirement's check and records the evidence.
- HR writes a plain brief by default and suggests templates (D-15). Selection on a fresh held-out set is 0.45 first and 0.55 in the top three (it was 0.32 and 0.35). Read-only templates are demoted for making requests. Evaluation hires do not train wages.
- The learning pipeline protects owner items. By hand it may only curate. It has a single writer, and the radar no longer dirties the tree or holds up exit.
- Work runs to completion unless the owner says stop, with a yes required before any step that cannot be undone (D-14).
- 22 facts, re-verified against official pages.

Still unproven, or waiting on the owner:
- Everything that needs a two-repository chat: the live checks CB-101 to CB-104, CB-106, CB-108, CB-110 and CB-111, each with exact steps in `docs/plan/tickets.json`.
- Whether a correctly named template beats a plain brief. That needs a paired run on bulkier tasks where the lead names a matching template.
- GitHub enforcement: checks do not start on this account and `main` is unprotected (`NEEDS_YOU.md` items 2 and 7). Until then, someone with write access can commit a hand-made delta.
- Wages for medium hires read low until 30 real medium hires replace the evaluation trials folded before `--eval` existed.
- `main` was reverted by another session at 01:09 UTC (`NEEDS_YOU.md` item 8). This session's branch has not been merged, and its inbox has not been consolidated, because the single-writer rule refuses while the branch is behind `origin/main`.

What this session cost (`brain ledger` at close): see the last commit's session record; about 40 helpers, most of them the 35 small evaluation trials on Sonnet.

## CB-214: Parkinson's law for time (2026-11-11, brain 0.10.0)

Owner request: apply Parkinson's law (work expands to fill the time available) with algorithmic logic wherever it applies. Decision D-16; rule and table in `method/efficiency.md`.

**One algorithm, `engine/timebox.py`.** Target = median of the last 20 observed durations; stop = their conformal 90th percentile times a safety factor; under 5 observations, the slowest times 3 or the estimate times 2; a run that hits the stop is censored and doubles the next stop; every stop is capped at the old fixed value, so evidence can only tighten a budget.

| Where | Before | Now | Evidence |
|---|---|---|---|
| `brain run`, gates, `hr settle` checks | 3600 s | default until 5 successes, then 3 x q90, floor 120 s; failures not counted | `tests/test_timebox.py` Commands |
| `brain req verify` | 600 s | same rule, cap 600 s | `engine/req.py` |
| live check after release | 120 s | learned per address, 30–120 s | `test_the_live_wait_is_learned_and_capped` |
| radar requests | 6 s each | per-source latency, 1.5–6 s, kept in the untracked checks file | `tests/test_radar.py` (47 OK) |
| size 0 / 1 request at boot | none | 3/6 and 20/40 min, mlearn-calibrated; `close --tier` records it as the estimate | `brain boot "Quick: …"` prints the line |
| plan tickets | `est` only | target = calibrated median, stop = calibrated p80 or 2 x est; in `plan packet` | `test_ticket_box_and_packet` |
| helpers | token wage only | time wage 8/20/45/90 min per size, stop 2x, learned from settled minutes; `<timebox>` in the brief; OVER TIMEBOX on settle | `test_helper_time_wage_tightens_with_evidence` |

Left fixed on purpose: eval graders (a tight limit could fail a valid trial) and the 120-minute checkpoint lease (a safety guard, not effort).

**Gate:** `python3 -m unittest discover -s tests -t .` 453 tests OK (436 before; 17 new). `brain doctor`, `lint`, `hr audit`, `items check`, `eval audit`, `learn verify` exit 0. `CLAUDE.md` 5988 bytes (limit 6000).

## CB-215: job-search expertise (2026-11-11, brain 0.11.0)

Owner request: make the brain a complete expert in using Claude for a job search. Decision D-17.

| Piece | Where | Evidence |
|---|---|---|
| Career family and routing (resume, interview, offer, search classes; a job-search project routes ambiguous requests to career) | `engine/route.py` | `tests/test_jobs.py` Routing, Kit |
| `brain-career` skill and definition of done for job-search documents | `.claude/skills/brain-career/`, `method/dod/job-application.md` | `brain lint` 0 errors; budget within caps |
| 1,145 uses of Claude across 23 categories and 9 stages, schema-validated, no duplicate or near-duplicate titles | `kits/jobsearch/uses/`, `taxonomy.json` | `brain jobs uses --min 1000 --strict` exit 0 |
| Ranking per person: (1.6^impact x evidence grade x lever effect x audience fit x funnel-stage weight)^0.8 / hours^0.2, with a category-diversity pass; lever effects and funnel benchmarks set from the evidence memo; stage weights move to the funnel step that leaks (Beta-shrunk) | `engine/jobs.py`, `kits/jobsearch/benchmarks.json` | Ranking tests |
| Evidence memo: funnel rates by channel, hidden market, ATS myths, AI in applications, negotiation, ghost jobs; graded A-D; 25 ranked levers | `docs/research/job-search-evidence.md` | 73 source links; gaps listed in its section 12 |
| Job discovery from public feeds only: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Recruitee, Workday, BambooHR, Breezy, Personio; schema.org JobPosting on robots-allowed pages; company probe by name; Workday tenants and sites from robots.txt sitemaps; every board per system from the Common Crawl index (falls back to older crawls) | `engine/jobfeeds.py` (standalone, vendored into projects) | Feed tests with a fake fetch; live: 13,208 postings on 73 boards in 8.5 minutes; with Workday tenants found from robots.txt, 15,674 postings on 134 boards in 16.7 minutes |
| Posting fit 0-100 with reasons: target titles, avoided roles, place by segment (foreign remote rejected), seniority, years asked, pay floor, senior-pay signal, pluses, staleness; `rescore` re-applies a changed profile offline | `engine/jobfeeds.py` `fit` | Fit tests; the first live run let 'Remote - Mexico' and a French 'Miami Building' through, fixed and covered by tests |
| Markdown to ATS-friendly Word | `engine/mddocx.py` | Rendered through LibreOffice and inspected |
| Project kit with daily GitHub Action, gate, tracker and funnel | `kits/jobsearch/template/`, `brain jobs init`, `brain jobs track` | Kit test |

Not proven: `discover` against the live Common Crawl index (it returned 504 Gateway Time-out all session); the Action has not run on GitHub (Actions do not start on this account yet, NEEDS_YOU item 7). Four playbook notes that named file paths were refused by `learn note` by design; those lines live in the skill instead.

**Gate:** 474 tests OK (453 before; 21 new). doctor, lint, hr audit, items check, eval audit, learn verify, `jobs uses --strict` exit 0.
