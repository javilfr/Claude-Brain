# Improvement plan, 2026-11-10

For the Claude session that executes it. The owner's instruction, verbatim: "Start running, quickly do comprehensive improve plan with ultra code and make it the best ever through comprehensive analysis, stop after very detailed plan you will create now to improve the brain is executed and very implemented."

This plan continues the programme CB-200 to CB-209 (`docs/plan/tickets.json`, `docs/NEXT_SESSION.md`) and replaces its middle with what a full analysis found. It is generated: sections 1 to 5 are written by the lead, section 6 is produced from the analysts' findings by a script, so every row traces to evidence.

## 1. What "done" means for this plan

1. Every finding marked **do** or **part** in section 6 is implemented with a test that failed before the change, or is recorded in section 7 as refuted (it did not reproduce) or not done (with the reason).
2. The full gate exits 0 on the merged result: `python3 -m unittest discover -s tests -t .`, `python3 bin/brain doctor`, `python3 bin/brain lint`, `python3 bin/brain hr audit`, `python3 bin/brain items check`, `python3 bin/brain eval audit`, `python3 bin/brain learn verify`.
3. No existing test was skipped, deleted or weakened. A test changed because it asserted behaviour a finding proved wrong is named in section 7 with the finding.
4. `docs/BUILD_STATUS.md`, `docs/REQUIREMENTS.md`, `NEEDS_YOU.md` and `OWNER_GUIDE.md` say what is now true, and what is still unproven is listed plainly.
5. Everything is committed and pushed on `claude/optimistic-newton-sh6lcx`. `main` is not pushed: the owner merges.

## 2. How the analysis was done

Seventeen independent analysts, each with a fresh context, in three lanes. Each worked in its own copy of the brain, ran real commands, and had to attach a command and its output (or a file and line, or a fetched page) to every finding. Their full reports are in `docs/review/2026-11-10-audit/<area>.json`.

| Lane | Analysts |
|---|---|
| Engine | core and contract; quality path (requirements, gates, ledger, guard, lint, hooks); learning and recall; statistical learners, routing and scheduler; radar, repo map and evaluation; HR engine; test-suite strength by mutation |
| Surface | instruction surface (twelve owner messages walked through); owner documents and their truth; templates, groups 1 to 5; templates, groups 6 to 10; a new held-out selection set written blind |
| Live | a first real two-repository project run end to end; a red team with a simulated year of use; speed, output size and scale; research on the platform today; research on models, prompting and delegation |

The lead added three findings of its own from running the session (`lead.json`). A finding is not trusted because an analyst wrote it: the implementer must first make the failure happen in a test. A finding that cannot be made to fail is recorded as refuted.

## 3. What the analysis found

The engine is fast, quiet and careful where it was tested: writes are atomic, release refuses a dirty tree, a stale gate and a forcing push, the note gate refused every forged owner statement tried directly, boot stays under its cap, and the ledger's arithmetic matches an independent recomputation to the cent. The defects sit at the seams the build session could not test: between two chats, between claims and proof, between the brain and a copy of it, and between a year of use and day one.

| # | Theme | What was seen | Reports |
|---|---|---|---|
| T1 | **A new chat cannot find the last chat's work.** | Sessions save state on their own branch; a new chat opens the default branch; boot looks nowhere else. After a handover that said "ready", a fresh clone booted as an empty project. On a project sitting on its release branch, `checkpoint --push` pushed nothing and exited 0. After a release, `main` never holds the record of that release | core, e2e-trial, owner-docs, instructions |
| T2 | **"Done" accepts claims.** | `req check` passed on evidence "looks good to me", on a path that does not exist, on an empty string, on a ledger holding one sentence of many, and on a ledger with every line dropped. A gate is green on exit 0 when its command ends in `|| true` or a pipe, when its output says FAILED, when a test was skipped or deleted in the same commit, or when another gate shares its id. Owner and checklist gates never hold a release. A hand-written line in the gate log releases | quality-path, redteam, core, e2e-trial |
| T3 | **Owner authority can be forged, and memory rots.** | One line dropped into the inbox becomes an active owner rule at the next consolidation. The quote check accepts turns the owner did not type (compaction summaries). A hand-written delta passes `learn apply` and the replay check. In a simulated year, decay retired 75 of the 141 shipped items, including six of ten owner preferences and the rule against skipping tests, and a retired item cannot be restored | redteam |
| T4 | **Pushes go further than asked.** | `checkpoint --push` in any copy of the brain commits and pushes whatever is in the inbox, plus any unpushed local commits, to the real remote, ignoring `BRAIN_NO_NETWORK`. This happened during the audit. Under rule `pr` it pushes ungated work to the release branch. "Bookkeeping" includes the manifest and project tools. No secret scan runs before the engine commits; the scanner misses 13 of 20 common key formats | quality-path, redteam, core, e2e-trial, owner-docs, lead |
| T5 | **The brain alone is a second-class mode.** | With no project attached, seven commands the core rules depend on exit 1, "Status" and "Hand over" have no support, and the skill sends the lead to an earlier session's tickets rather than the owner's message. This session's own request was sized "1 small task, data" | instructions, owner-docs, lead |
| T6 | **Process weight and noise.** | A three-item project needed 36 process commands, three required reads and five help look-ups around 11 build commands; about 18 would have done. Ending a session takes an order-sensitive ritual of three commands that leaves a false "unclosed session" behind. A third of boot's output on "Continue" is recall matched on the trigger word. The session-end hook dirties the tree after every turn | e2e-trial, core, instructions, lead |
| T7 | **Spanish is half-supported.** | Recall returns nothing for a Spanish request and three items for its translation. A project created with `--language es` gets English status files. `RESUELTO` is not read as resolved. The guide gives Spanish for three of nine phrases | e2e-trial, owner-docs |
| T8 | **HR hires agents that cannot do the job, and records work nobody did.** | A researcher with no shell for a code task with a test command; a read-only reviewer for a build ticket. A brief that was never delegated is settled as a pass or a fail for its template | e2e-trial, instructions |
| T9 | **Fragile on bad input.** | A manifest section of the wrong type crashes boot, status, checkpoint and handover with a traceback. One bad byte in `STATE.md` is read as a fresh project and the next checkpoint overwrites the real state. `brain run` on a timeout leaves children running and loses stderr; commands inherit stdin; 300 MB of output takes 1.1 GB of memory | core, quality-path |
| T10 | **Documents drift.** | Numbers are restated by hand in five documents and disagree (21 or 22 modules, 406 or 407 tests, 5,356 or 5,423 bytes). A resolved owner item is still shown as open | owner-docs |
| T11 | **Measurement was blind in one eye.** | The token ledger did not count helpers started by a workflow: it said $3.42 when the truth was $13.14 (fixed, CB-210). The ledger's "tokens" are 93% cache reads, 35 times the unit HR wages use | lead, quality-path |

Themes from the analysts still running when this version was written (learning, learners and routing, radar and evaluation, HR engine, mutation testing, both template reviews, the held-out set, performance, both research memos) are added to section 6 as their reports arrive, and to this table in the final version.

## 4. Decisions made for this plan (recorded in `docs/DECISIONS.md` as D-14 to D-17)

| # | Decision | Why |
|---|---|---|
| D-14 | This session runs many helpers at once through workflows, above the usual cap of four. | The owner asked for it by name ("ultra code"). D-04's cap stays the default for normal work |
| D-15 | Helpers in this session get hand-written briefs, not `brain hr hire`. | HR's cap is four open contracts and its selection has the defect in T8, which this plan fixes. HR was exercised for real by the end-to-end analyst |
| D-16 | Blocking and should-fix findings are done now; minor ones when small; ideas only when they remove a whole class of defect or a whole ritual. Everything else is listed as later, with its reason. | "Do the least that meets the bar" applies to the brain's own improvement too |
| D-17 | A new chat finds the last chat's state by looking at the other remote branches the clone already has, and adopting the newest by fast-forward only. Nothing is pushed to the release branch to carry state. | The release rule stays the only way onto `main`; a fast-forward cannot lose work |

## 5. How the work is carried out

**Packages by file ownership.** Twelve packages, A to L (section 6). A file has one owner, so parallel work cannot collide. A finding that names files in several packages belongs to the package of its main file; the other owners are told in their brief.

**Isolation.** Each package is built in its own git worktree under the session scratch folder, on its own branch cut from the lead's HEAD. Pushes from worktrees and scratch copies are blocked. The lead merges each branch into `claude/optimistic-newton-sh6lcx`, runs the full gate on the merged tree, and commits with the trailer `Brain-Bootstrap: <ticket>`.

**Rules for every implementer.**
1. Test first: write the test that shows the failure, see it fail, then fix, then see it pass. A finding whose failure cannot be produced is reported as refuted, not fixed blind.
2. New tests go in `tests/test_r4_<package>.py`. An existing test is changed only when it asserts the behaviour a finding proved wrong; say which and why. Never skip, delete or weaken a test.
3. Standard library only. No new always-loaded text. Keep every command's current flags working (`brain lint` checks the instruction files against them).
4. Touch only the package's files. A small new function in another package's module is allowed when unavoidable; append it, change nothing existing there, and report it.
5. Every new output line is paid for in tokens: one line where one will do, a next step in every refusal.
6. The learned zone (`memory/`, `owner/`, `stats/`, `playbooks/`) is changed only through `brain learn`, by the lead.
7. Acceptance for a package: its new tests pass, the whole suite passes in its worktree, `brain doctor` and `brain lint` exit 0.

**Rounds.**

| Round | Packages | Starts when |
|---|---|---|
| 0 (lead) | CB-200 baseline; CB-201 live checks; CB-210 ledger fix; shared secret scan (`common.secret_problem`) so the other packages can call it | done before round 1 |
| 1 | A continuity and state; B contract and common; C run, gate and release; D requirements; E ledger, guard, lint, hooks | the six first-wave reports are in |
| 2 | F learning and recall; G routing, learners, scheduler; H radar, map, evaluation; I HR engine and selection (CB-204); J templates (CB-205); second pass on A to E for findings from later reports | the remaining reports are in and round 1 is merged |
| 3 | K instruction surface (after the engine, so the wording names commands that exist); L owner documents; research facts recorded through `brain learn` (CB-207); paired evaluation pre-registered and run if the harness allows (CB-203) | round 2 is merged |
| 4 | Fresh-context review of the whole diff against this plan and the invariants, with reproductions; fixes; close out (CB-208, CB-209) | round 3 is merged |

**Order inside a round** follows severity: blocking, then should-fix, then minor, then chosen ideas. An implementer that runs out of room stops at a green state and reports what is left; the lead re-issues the rest.

**What only the owner can do** stays in `NEEDS_YOU.md` as click steps: merging this branch to `main`, the GitHub checks, protecting `main`, the weekly run.

## 6. Work packages (generated from the findings)

Findings in: 170 from 10 analyst report(s) (core, e2e-trial, instructions, lead, learning, owner-docs, quality-path, quality2, redteam, research-platform). Decisions: 144 do, 2 do in part, 0 reproduce first, 24 later.

Each row is one finding. The full text (evidence, reproduction, proposed fix, acceptance) is in `docs/review/2026-11-10-audit/<area>.json` under the same id. Decision: **do**, **part** (the named part now), **check** (reproduce first), **later** (with the reason).

### Package A: Continuity and state (CB-212)

Owns: `engine/state.py`, `engine/detect.py`. New tests go in `tests/test_r4_a.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| core-01 | blocking | M | do | A new chat never sees the last checkpoint: after a 'ready' handover on the session branch, boot from main resumes as if nothing had happened |  |
| e2e-trial-01 | blocking | M | do | On a new project that sits on its release branch, no checkpoint reaches the remote before the first green release, and `checkpoint --push` still exits 0 |  |
| e2e-trial-02 | blocking | M | do | A new chat that opens the default branch does not see state saved on the working branch; handover's line to paste omits the branch |  |
| owner-docs-01 | blocking | M | do | "Continue" in a new chat resumes an old checkpoint and handover still says ready: state is pushed to the last chat's branch, a new chat starts from main, and boot does not look |  |
| core-04 | should-fix | M | do | checkpoint --push commits and pushes more than bookkeeping: ungated work goes straight to main under the 'pr' rule, a changed manifest and .brain/ext tools ride along as 'chore(brain): checkpoint', and the new… |  |
| core-05 | should-fix | S | do | A damaged STATE.md is silently treated as a fresh project and then overwritten: one bad byte wipes stage, item, notes and log at the next checkpoint |  |
| core-07 | should-fix | M | do | Boot's byte cap drops lines blindly from the end with no notice: in a realistic busy state the second-session WARNING, the size line and all recall lines disappear |  |
| core-08 | should-fix | S | do | checkpoint --push exits 0 when nothing reached the remote, turns a slow push into a traceback, and its failure lines give no next step; handover says 'ready' for a project that is not a git repository |  |
| core-10 | should-fix | S | do | Boot and resume show the oldest notes and hide the newest, and resume does not say which project, branch or unpushed commits it is talking about |  |
| core-12 | should-fix | S | do | Boot misreports two recorded facts in the normal flow: it resumes 'at the recorded size 2' after a checkpoint set size 3, and it warns about 'another session' right after a clean handover |  |
| core-13 | should-fix | S | do | On 'Continue' half of boot's output is recall matched against the trigger word, not against the recorded work |  |
| e2e-trial-04 | should-fix | S | do | `checkpoint --done X` leaves X in `next`, so the checklist keeps an open line for finished work |  |
| e2e-trial-11 | should-fix | S | do | `checkpoint --push` also commits and pushes the brain repository, from any copy and without saying so (already ticketed as CB-211; measurement and fix details) |  |
| instructions-04 | should-fix | S | do | A third of boot's output is recall matched on the trigger words, repeating loaded rules or returning unrelated items |  |
| instructions-05 | should-fix | M | do | Boot never shows the owner's OVERTURNED and RESOLVED marks, so every resume must read two files in full or miss his override |  |
| owner-docs-04 | should-fix | S | do | An OVERTURNED decision is never surfaced by any script, so "the next chat applies it" depends on the lead reading the whole decisions file; three files give three different instructions |  |
| owner-docs-05 | should-fix | S | do | RESOLVED is matched as a substring: an open item whose text contains "resolved" vanishes from STATUS.md and from boot's count, and "RESUELTO" or "Hecho" is ignored |  |
| owner-docs-06 | should-fix | M | do | In a chat with only the brain attached, "Status" and "Hand over" have no engine support (exit 1), the brain's own open owner items are not shown, and the handover note and ticket states are kept by hand |  |
| owner-docs-08 | should-fix | M | do | Generated STATUS.md does not say what to open, starts with a machine timestamp and a stage name, and stays in English for a project created with --language es (the field is never read) |  |
| owner-docs-11 | should-fix | S | do | Three engine commands commit and push whatever is in learning/inbox to the origin of whichever copy of the brain they run from; today test records reached the real branch that way |  |
| quality-path-06 | should-fix | S | do | Pushes ignore BRAIN_NO_NETWORK, and `push_brain_records` commits and pushes every inbox file it finds (this caused a real unintended push during the audit) |  |
| quality-path-11 | should-fix | S | do | `checkpoint --push` commits the manifest and project tools as bookkeeping while saying it left them, and a gate script elsewhere under .brain/ can change without making the gate stale |  |
| quality-path-12 | should-fix | S | do | Under release rule `pr` (or `none`), `checkpoint --push` on the release branch pushes ungated work straight to main |  |
| redteam-06 | should-fix | S | do | Moving a file under .brain/ hides the change from the staleness and release-branch checks; with rule 'pr', checkpoint --push sends ungated work to main |  |
| redteam-10 | should-fix | S | do | One long --done text and the next session's boot shows no item, next steps, blockers, warnings or recall |  |
| redteam-12 | should-fix | S | do | checkpoint --push commits whatever sits in the brain's inbox and pushes the brain's whole current branch, including main and other local commits, from any copy |  |
| e2e-trial-13 | minor | M | do | Files the owner reads are in English with bare ids although the project was created with `--language es`; the option is stored and never read |  |
| core-15 | idea | M | do | Idea: one end-of-session command and one start-of-session command, so order-dependent rituals stop producing bugs and tokens |  |
| core-17 | idea | L | later | Idea: make checkpoints merge-safe (append-only events, generated views) so two chats or two session branches never conflict on bookkeeping | a change to how state is stored; wait for evidence that two chats really collide |
| e2e-trial-16 | idea | S | do | Idea: one call to end a session |  |
| instructions-20 | idea | S | do | Idea: answer "Status" with one command |  |
| learning-17 | idea | S | do | Idea: let boot and close run the loop's housekeeping, so learning does not wait for someone to remember |  |
| owner-docs-16 | idea | M | later | Idea: a command that writes and closes NEEDS_YOU items, so every item has the same checked shape | useful, not urgent; NEEDS_YOU items are few and hand-written well today |
| owner-docs-18 | idea | S | later | Idea: cost he can act on, as a comparison rather than dollars he is not charged | needs three recorded sessions per project before it can say anything |
| redteam-20 | idea | S | do | Idea: one boot line for the health of the learning loop |  |

### Package B: Contract, common and doctor (CB-213)

Owns: `engine/common.py`, `engine/contract.py`, `engine/doctor.py`, `engine/budget.py`, `engine/cache.py`, `bin/brain`, `contract/`. New tests go in `tests/test_r4_b.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| core-06 | should-fix | S | do | Boot, status, checkpoint and handover crash with a Python traceback when a manifest section is null or the wrong type |  |
| core-09 | should-fix | M | do | Boot and the other commands disagree about the project: with two projects every command after boot says 'no managed project found', an exact --name loses to a substring, and in a brain-only session resume/chec… |  |
| core-11 | should-fix | S | do | 'stale-brain' mode says 'write nothing to .brain/' but checkpoint, status and boot itself write there |  |
| quality-path-10 | should-fix | S | do | The secret scanner misses 13 of 20 common credential formats |  |
| redteam-07 | should-fix | M | do | No secret scan before the brain commits and pushes; a key written into a note, evidence, NEEDS_YOU or a helper brief reaches the remote, and the patterns miss 13 of 19 common formats |  |
| research-platform-05 | should-fix | S | do | `brain adopt` on a repository that relies on AGENTS.md silently switches its instructions off |  |
| core-14 | minor | M | do | Smaller slips, each reproduced: adopt accepts the brain itself, STATUS.md cost lines are wrong, an open owner item with the word 'unresolved' vanishes, the total token cap is not enforced by `brain budget`, a … |  |
| core-16 | idea | L | part | Idea: one project context with a health check that every command goes through, plus a seeded fuzz test that no core command ever tracebacks on malformed contract files | fuzz test only; rest deferred: the refactor is large; its fuzz test is done under package B, the single project context is deferred |
| core-18 | idea | M | part | Idea: make the contract's dormant keys real (paths.never_touch, privacy.share_lessons, owner and checklist gates) or mark them reserved | validate names reserved keys; never_touch is implemented under quality2-05; rest deferred: implemented only as: reserved keys are named by … |
| core-19 | idea | M | do | Idea: `brain doctor --project`: a preflight of the attached project and git setup that prints the fix for each problem, run by boot when something changed |  |
| e2e-trial-15 | idea | S | do | Idea: let `init` finish the set-up in one call |  |
| instructions-15 | idea | L | later | Idea: let the brain be its own managed project, so brain work uses the same ledger, checkpoint, resume and handover as any project | a change to the kernel's shape (the brain as its own managed project); this programme gives brain-only chats a working path instead (method… |
| instructions-19 | idea | S | do | Idea: with several projects attached, say so instead of "no managed project found" |  |

### Package C: Run, gate and release (CB-214)

Owns: `engine/gate.py`. New tests go in `tests/test_r4_c.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| core-02 | blocking | M | do | Release reports 'gates green' while a declared gate failed: two gates sharing one id mask each other, validate accepts the manifest, and owner/checklist gates never hold a release |  |
| quality2-01 | blocking | M | do | The recommended release path never runs the 'tests switched off' detectors, and the detectors are advisory and miss common markers |  |
| redteam-05 | blocking | M | do | A release can be green without the work being green: forged gate record, gates ending in `/ tail` or `// true`, duplicate gate ids |  |
| e2e-trial-03 | should-fix | M | do | After a release, main never holds the record of that release: "Continue" from main repeats the release item, and a second release duplicates the release log |  |
| e2e-trial-08 | should-fix | S | do | `brain run` runs where it was typed, not in the detected project: from the documented stance the project's tests fail to import, from the brain folder the brain's own tests run and report ok; same-second logs … |  |
| quality-path-03 | should-fix | M | do | A gate is green on exit 0 even when the command cannot fail, a pipe hides the failure, or the output says FAILED; the detectors miss removed tests and common skip markers |  |
| quality-path-04 | should-fix | M | do | Release prints 'gates green' and pushes while `owner` and `checklist` gates are unmet |  |
| quality-path-05 | should-fix | M | do | `brain run` and gates: stderr lost and children left running on timeout, caller's stdin inherited, whole output held in memory, no record when killed, one-hour default above the tool's limit |  |
| quality-path-07 | should-fix | S | do | `brain gate` exits 0 when no gate ran |  |
| quality-path-14 | should-fix | S | do | `brain gate` prints 60 lines for five failing gates and keeps running after the first failure; a release refusal names no file (I-04) |  |
| quality2-05 | should-fix | M | do | Every project manifest carries paths.never_touch and paths.evidence, and no code reads either |  |
| e2e-trial-20 | idea | S | do | Idea: shorter digests with paths relative to the project |  |
| instructions-16 | idea | S | do | Idea: a `gate --last` that answers "why is the build red?" from the recorded run without running the build again |  |
| quality-path-16 | idea | S | do | Idea: a test-count ratchet in gate records |  |
| quality-path-17 | idea | M | later | Idea: seal gate records the way HR seals checks, and keep red results out of git's reach | protects against a lead that forges records; lower value than the items done now |
| quality-path-19 | idea | M | later | Idea: a detached gate runner for checks longer than a tool call | needs a real project whose gate outlasts a tool call |
| quality2-06 | idea | M | later | Idea: clean-room gates for release (run the gates in a detached worktree at HEAD and use that run's exit codes) | release running its own gates at HEAD is done under redteam-05; the detached-worktree variant is deferred |
| quality2-07 | idea | S | do | Idea: prove once that each gate can fail |  |
| redteam-18 | idea | M | later | Idea: show the owner a project's commands the first time, and whenever they change outside a brain session | needs a brain-side store of project command hashes; wait for a second project |

### Package D: Requirements ledger and the done report (CB-215)

Owns: `engine/req.py`. New tests go in `tests/test_r4_d.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| quality-path-01 | blocking | M | do | `req check` passes on evidence that is empty, free text or points at nothing; the stored `check` command is never run |  |
| e2e-trial-06 | should-fix | M | do | `req evidence --done` accepts any text: a path that does not exist closed a requirement before its code existed, the stored check is never run, and a line cannot be reopened |  |
| quality-path-02 | should-fix | M | do | Nothing checks that the ledger holds the request: empty ledger, one line of many, all lines dropped and a rewritten 'passes when' all pass |  |
| quality2-02 | should-fix | M | do | Dropping requirements is invisible to the owner: a ledger with every line dropped passes, and STATUS.md shows a count at best |  |
| redteam-08 | should-fix | M | do | `req check` passes on evidence that proves nothing, never runs the stored check, and the status page then tells the owner 'done with evidence' |  |
| e2e-trial-17 | idea | M | later | Idea: fold evidence into the checkpoint that finishes an item | depends on typed evidence (package D) proving itself first |
| quality-path-15 | idea | M | do | Idea: one `brain done` command that produces the done report from tool results |  |
| quality2-08 | idea | M | later | Idea: evidence that goes stale | depends on typed evidence proving itself first |

### Package E: Token ledger, guard, lint and hooks (CB-216)

Owns: `engine/ledger.py`, `engine/guard.py`, `engine/lint.py`, `.claude/hooks`, `.claude/settings.json`, `.github/`. New tests go in `tests/test_r4_e.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| core-03 | should-fix | M | do | A session that ran 'checkpoint --push' then 'close' is reported as unclosed by the next boot, and its real token ledger is replaced by an 'unrecorded' stub; close never pushes what it writes |  |
| e2e-trial-10 | should-fix | S | do | `brain close` as the skill writes it records `tier: null`, so the sizing learner gets no label from normal sessions |  |
| lead-01 | should-fix | S | do | The token ledger did not see helpers started by a workflow (fixed: CB-210) |  |
| lead-02 | should-fix | M | do | The session-end hook rewrites a tracked inbox file after every turn, so the tree is dirty after every turn and each turn ends with a request to commit |  |
| learning-04 | should-fix | S | do | `close --used` credits items recall never showed; one claim promotes a candidate straight to active |  |
| quality-path-08 | should-fix | M | do | After the lock, one edit removes it: the hook passes every kernel file including VERSION.json, `guard diff` exits 0 on an unlock, and Bash writes are not guarded (I-09) |  |
| quality-path-09 | should-fix | S | do | Hook commands fail closed when the script path does not resolve: python3 exits 2, which blocks every edit and blocks stopping |  |
| quality-path-13 | should-fix | M | do | Lint gaps: invalid option values, missing required options and two call forms pass; repeated sentences only note although the spec says fail; one transcript rule is missing; handover, memory items and HR templ… |  |
| quality2-03 | should-fix | M | do | What the ledger feeds the learners is in units that do not mean work: tokens is 93% cache reads and minutes counts idle time |  |
| research-platform-09 | should-fix | S | do | omitClaudeMd may not keep both repositories' CLAUDE.md out of a helper in a two-repo session, and the ledger cannot show it |  |
| quality2-04 | minor | S | do | Ledger pricing blind spots: an unknown model is silently priced at the fallback rate; fast mode is ignored |  |
| research-platform-12 | minor | S | do | No hook restates the project's position after compaction in sessions where the brain's hooks do load |  |
| instructions-18 | idea | M | do | Idea: extend the lint to the gaps found here |  |
| quality-path-18 | idea | M | later | Idea: ledger units and accuracy notes (output-equivalent tokens, fallback-priced models, tiered and fast prices, active minutes) | done under quality2-03 and quality2-04 (same point, measured) |
| quality-path-20 | idea | S | do | Idea: generated facts in status documents, checked by lint |  |
| quality2-09 | idea | M | later | Idea: incremental session ledger with cache-break detection | 0.085 s per turn today; revisit when a session's transcripts pass 100 MB |
| redteam-15 | idea | S | later | Idea: a command hook that makes the release rule structural | hooks load only in one-repository chats, so this guard would be absent in normal two-repository work; the engine-side checks are done inste… |

### Package F: Learning pipeline (CB-217)

Owns: `engine/learn.py`, `learning/`, `tests/test_rehearsal.py`. New tests go in `tests/test_r4_f.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| learning-01 | blocking | M | do | A hand-written inbox line becomes an active, top-ranked owner-stated rule and passes verify |  |
| learning-02 | blocking | M | do | The loop does not close: a noted lesson stays an invisible candidate and is then forgotten |  |
| redteam-01 | blocking | M | do | A year of normal use retires half of the brain's shipped knowledge, and a retired item cannot be restored |  |
| redteam-02 | blocking | M | do | One forged line in the inbox becomes an active, permanent owner rule; a project's test script can plant it and the normal loop pushes it to the brain's main |  |
| redteam-03 | blocking | S | do | The --quote check accepts turns the owner did not type (compaction summaries, turns from other sessions) |  |
| redteam-04 | blocking | L | do | A hand-written delta rewrites, adds and retires the owner's instructions through `learn apply`, the replay check passes, and the locked-zone hook does not protect its own lock |  |
| learning-03 | should-fix | M | do | Project-scoped lessons are written as candidates and can never be recalled |  |
| learning-06 | should-fix | M | do | Forgetting wipes out curated memory, is uncapped, and cannot be undone |  |
| learning-07 | should-fix | M | do | A changed fact confirms the stale fact; facts cannot be superseded or re-verified through the pipeline |  |
| learning-08 | should-fix | M | do | One malformed inbox record crashes consolidation; duplicated records are counted twice; a re-run digest breaks verify |  |
| learning-09 | should-fix | S | do | At 400 items the whole pipeline deadlocks; item rows grow without bound |  |
| learning-10 | should-fix | M | do | The admission gate refuses 28% of the brain's own seed lessons, and only after `learn note` said "recorded" |  |
| learning-13 | should-fix | S | do | The pitfall rule cannot fire for a fail-then-fix inside one session and can fire across unrelated sessions |  |
| learning-14 | should-fix | M | do | Conflicts are detected by keyword, can never be cleared, and harm votes lower an owner item's rank |  |
| redteam-09 | should-fix | S | do | The brain's own test suite goes red after the first real lesson is consolidated, and again after the first decay |  |
| redteam-11 | should-fix | M | do | Three red sessions in a row demote the rules that were followed, including facts and the release rule |  |
| redteam-14 | should-fix | L | do | Learning dead ends: lessons noted once are never shown again, the routing learner can never start, and one item over 400 stops every later consolidation |  |
| owner-docs-12 | minor | S | do | After "What did you learn?" the next "Hand over" cannot pass: the digest command writes a file in the brain that no command commits |  |
| core-20 | idea | M | do | Idea: a two-container continuity rehearsal in the test suite, so CB-104 ('Continue in a new chat resumes the same item') is checked on every change instead of waiting for a live session |  |
| learning-18 | idea | M | later | Idea: let proven family lessons graduate into the playbooks the lead actually reads | no learned family lesson has three supporting sessions yet; revisit after real use |
| redteam-16 | idea | M | do | Idea: keep the year-in-a-minute simulation as a standing gate |  |
| redteam-17 | idea | M | do | Idea: a weekly owner digest as the outside check on owner-level memory |  |
| redteam-19 | idea | M | later | Idea: compact the learning history once a year | nothing to compact yet; revisit when the learning history is a year old |

### Package M: Recall and memory items (CB-224)

Owns: `engine/recall.py`, `engine/items.py`, `evals/recall_golden.jsonl`, `tests/test_recall.py`. New tests go in `tests/test_r4_m.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| e2e-trial-09 | should-fix | M | do | Recall works only in English: the owner's Spanish request returns nothing while its translation returns three items |  |
| learning-11 | should-fix | M | do | Recall returns noise instead of silence, and owner standing items take slots they do not earn |  |
| learning-12 | should-fix | S | do | The golden recall test measures a configuration nobody runs and reads the brain's live learned state |  |
| redteam-13 | should-fix | S | do | A file in the project's .brain/memory/ can present itself as an owner standing instruction in boot |  |
| learning-16 | idea | M | do | Idea: make recall work for Spanish and dictated requests |  |
| learning-20 | idea | M | do | Idea: mark what was only read, and give the owner a one-step undo for a single lesson |  |

### Package G: Routing, statistical learners and scheduler (CB-218)

Owns: `engine/mlearn.py`, `engine/route.py`, `engine/schedule.py`, `memory/ml_config.json`, `evals/routing.jsonl`, `evals/schedule_cases`, `evals/owner_phrases.jsonl`. New tests go in `tests/test_r4_g.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| instructions-02 | should-fix | M | do | A trigger followed by a task is sized by a stray word, and 17 of the 52 trigger phrases in the skill descriptions route as a plain answer |  |
| instructions-10 | should-fix | S | do | brain-plan's parallel step: the tickets file format is not given, and the scheduler prices a helper's cold start at zero, so parallel work looks free |  |
| learning-05 | should-fix | S | do | The promotion score rates a perfectly followed item below neutral, and promotion depends on batching |  |
| owner-docs-09 | should-fix | M | do | Phrases the owner is told to type are not recognised by route or by any skill, and his real opening message today was sized "1 small task, data" |  |
| instructions-17 | idea | M | do | Idea: a scripted walk-through of the owner's phrases as a regression test |  |
| learning-15 | idea | L | later | Idea: credit items by comparing sessions where they were shown with sessions where they were not | needs many recorded sessions per task class before the comparison means anything |
| owner-docs-15 | idea | M | do | Idea: one source for owner phrases |  |

### Package H: Radar, repo map and evaluation (CB-219)

Owns: `engine/radar.py`, `engine/repomap.py`, `engine/evals.py`, `evals/`, `memory/radar_sources.json`, `memory/models.json`. New tests go in `tests/test_r4_h.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| learning-19 | idea | S | do | Idea: a `brain eval recall` command that reports recall, precision, silence and token cost under production settings |  |

### Package I: HR engine and selection (CB-220)

Owns: `engine/hr.py`, `hr/GUIDELINES.md`, `hr/template.schema.json`, `evals/hr_golden`. New tests go in `tests/test_r4_i.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| e2e-trial-05 | should-fix | M | do | HR assigns agents that cannot do the work: a researcher with no shell for a code task with a test command, a read-only reviewer for a build ticket, and Opus at ten times the wage when the task is worded in Spa… |  |
| e2e-trial-07 | should-fix | M | do | Settling a hire nobody worked records a pass or fail for the template, and a failed settle is final but prints as if it had been run again |  |
| instructions-09 | should-fix | S | do | A brief that is written but never delegated is settled by `close` as a failed hire against its template |  |
| e2e-trial-12 | minor | S | do | The tickets file has two undocumented shapes: `hr staff` ignores `check` and reports "no acceptance command" |  |
| owner-docs-13 | minor | S | do | "HR report" tells him to say "Consolidate" for hires that are already folded in |  |
| e2e-trial-19 | idea | S | do | Idea: show what a template adds to the done condition before the lead delegates |  |

### Package J: The 100 templates (CB-221)

Owns: `hr/rack`. New tests go in `tests/test_r4_j.py`.

No findings yet.

### Package K: Instruction surface (CB-222)

Owns: `CLAUDE.md`, `.claude/skills`, `.claude/agents`, `method/`, `.claude-plugin`. New tests go in `tests/test_r4_k.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| instructions-01 | blocking | S | do | With the brain alone, the core rules name commands that cannot run, and brain-start sends the lead to an earlier session's tickets instead of the owner's message |  |
| instructions-03 | should-fix | S | do | `close` leaves both repositories uncommitted, the core rules run it after the last push, and two skills prescribe hand commits the engine already makes |  |
| instructions-06 | should-fix | M | do | Research hires: the skill and rule 4 disagree, and `hr hire` either refuses or puts a research question on a builder with no web tools and no date |  |
| instructions-07 | should-fix | S | do | "Continue on your own at most three times in a row" has no reason, no unit, and refers to a re-prompt mechanism that does not exist |  |
| instructions-08 | should-fix | M | do | brain-new leaves the contract uncommitted and the release rule unset, and "Ship it" under rule `none` has no instruction |  |
| lead-03 | should-fix | S | do | A copy of the brain made with cp -a keeps the real remote: an auditor's scratch copy pushed three test records to this branch |  |
| research-platform-01 | should-fix | M | do | Workflows and ultracode have no rule in the brain: workflow agents default to the session's model and a 65K-token start |  |
| research-platform-02 | should-fix | S | do | The plugin manifest fails the platform's own validator: the name 'claude-brain' is reserved |  |
| research-platform-03 | should-fix | M | do | Brain skills declare no hooks, although skill-frontmatter hooks are the documented way to get the guard and session capture into a two-repo session |  |
| research-platform-04 | should-fix | M | do | NEEDS_YOU item 5 and CB-106 point at an undocumented route; the documented one is a hooks-only plugin turned on for the claude.ai account |  |
| research-platform-11 | should-fix | M | do | Cloud sessions now carry tools for environment changes, credentials, schedules and adding a repository; the brain still hands the owner click lists |  |
| e2e-trial-14 | minor | M | do | Process weight on a three-item project: 36 process commands, 3 required reads and 5 help look-ups around 11 build commands, and several output lines mislead |  |
| instructions-12 | minor | S | do | The size-0 row forbids scripts that three skills run at size 0, brain-create runs its full pass for a list of names, and the project stub says boot always comes first |  |
| instructions-13 | minor | S | do | All six agent files set a token cap that the guidelines forbid and the briefs contradict, and builder.md relies on a `brain run` path no brief gives |  |
| instructions-14 | minor | S | do | "Go back" is offered to the owner, but its steps sit in a file nothing points to and "the last release he accepted" is recorded nowhere |  |
| e2e-trial-18 | idea | S | do | Idea: a small-project lane stated in one place |  |
| research-platform-14 | idea | S | later | Idea: bound helpers with maxTurns, and keep the Haiku scout under its 100K price step with autoCompactWindow | a turn cap set without settled-hire data would cut helpers short; revisit from `brain hr report` |
| research-platform-15 | idea | S | later | Idea: a project agent named Explore, because the built-in one runs on Opus under a Fable lead | needs a pre-registered comparison first |
| research-platform-18 | idea | S | later | Idea: let brain-start inject the boot output itself and save one round trip per session | needs a live test in one- and two-repository sessions first |

### Package L: Owner documents and status files (CB-223)

Owns: `OWNER_GUIDE.md`, `NEEDS_YOU.md`, `README.md`, `docs/`, `GUIA.md`, `VERSION.json`. New tests go in `tests/test_r4_l.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| owner-docs-02 | should-fix | S | do | The guide says a red cross means do not merge, NEEDS_YOU says every push shows a red cross, and the pull-request undo story has no instance: he cannot follow both, and learning only counts what reaches main |  |
| owner-docs-03 | should-fix | S | do | NEEDS_YOU.md: the clicks for protecting main create a ruleset that is disabled by default and may need a paid plan; the resolved item is shown first with stale steps; the real blocker is last |  |
| owner-docs-07 | should-fix | M | do | Numbers are restated by hand in five documents and have drifted; nothing checks them (lint covers neither docs/ nor numbers) |  |
| owner-docs-10 | should-fix | S | do | OWNER_GUIDE.md has no answer for a chat that dies, where to see the result, how to merge on GitHub, or how to stop at once, and gives Spanish for three of nine phrases |  |
| research-platform-07 | should-fix | S | do | Cloud sessions on 1M-token models compact only near 900K tokens and get no idle compaction; one environment variable bounds it |  |
| owner-docs-14 | minor | M | do | Five smaller statements that are untrue or that a new lead would misread |  |
| research-platform-08 | minor | S | do | A workflow runs only two agents at a time on the 4-CPU cloud VM |  |
| research-platform-13 | minor | S | do | The owner guide does not warn that the brain does not work inside a Project |  |
| owner-docs-17 | idea | M | later | Idea: a Spanish edition of the guide, checked for parity | a second guide to keep in step; the guide gets Spanish phrases now, a full Spanish edition waits for the owner to ask |
| owner-docs-19 | idea | M | later | Idea: a first-project walkthrough in the guide, then frozen as a rehearsal | needs the first real project (CB-110) |
| research-platform-16 | idea | S | later | Idea: offer Opus 5.5 with Fable 5.2 as advisor as a third way to start a chat | needs a live test of the advisor command first |
| research-platform-17 | idea | S | later | Idea: one phrase for unattended runs, `/goal` with the requirements check as its condition | needs a live test in a cloud session first |
| research-platform-19 | idea | M | later | Idea: a brain-first layout, starting on the brain alone so its hooks load and letting Claude add the project | needs a live test; listed under 'Needs a live session' |

### Package Z: Facts and lessons recorded through the learning pipeline (the lead) (CB-207)

Owns: `memory/facts.jsonl`, `memory/items.jsonl`, `owner/`, `playbooks/`. New tests go in `tests/test_r4_z.py`.

| Id | Severity | Size | Decision | Finding | Why later or in part |
|---|---|---|---|---|---|
| research-platform-06 | should-fix | S | do | The cache-breakers fact is partly stale, and CB-112 can be closed from the docs |  |
| instructions-11 | minor | S | do | Review rounds are stated three ways, and the review-stopping learner needs two reviewers that the method forbids |  |
| research-platform-10 | minor | S | do | Smaller stale statements, and no platform fact carries the URL it was checked against |  |

