# Final review 2: invariants, requirements and the improvement-session status (CB-208)

Reviewer: fresh-context reviewer (contract h-20261110-444f19). Read-only: nothing in the repository was changed apart from this file.

**What was reviewed.** Commits `19fb016..62027dc`. HEAD moved four times while the review ran (8c90bd4, a2f612a, 090d392, 62027dc), so the committed state at 62027dc is the one reviewed. The working tree also held uncommitted changes I did not write (`engine/learn.py`, `engine/radar.py`, `tests/test_radar.py`, the session inbox file, `.gitattributes`, `docs/review/2026-11-10-redteam.md`). I did **not** review those changes.

**Gate at 62027dc** (a clean `git archive` copy in the scratchpad): `python3 -m unittest discover -s tests -t .` gave "Ran 427 tests in 36.6s, OK". `doctor` reported "brain is healthy", `lint` 0 errors and 0 notes, `hr audit` "rack is sound", `eval audit` 12 sound, `items check` 141 valid. In the live tree, `learn verify` reported "1 delta(s) replayed on origin/main; learned zone matches", and `guard diff --base 19fb016` exited 0 ("52 kernel, 5 learned, 2 inbox, 1 state").

Severity: **blocking** / **should-fix** / **minor**. Confidence is given as high, medium or low.

---

## 1. Invariants (EXECUTION_PLAN section 1)

| ID | Verdict | Evidence |
|---|---|---|
| I-01 | holds | `brain lint`: 0 errors. The only imports added in `engine/` are `subprocess`, `os` and `threading`: `git diff 19fb016..HEAD -- engine bin \| grep '^+.*import'` |
| I-02 | holds for the test; live behaviour not checkable here; at risk (see B1) | `tests/test_rehearsal.py` passes inside the full suite. The official page says Project cloud threads do not load skills or agents (B1) |
| I-03 | holds | `brain budget`: CLAUDE.md 5,499 B, stub 1,150 B, 6 agents, 10 skills, about 2,569 tokens. The longest description is 269 chars (`.claude/skills/brain-handover/SKILL.md`) |
| I-04 | holds for the default outputs I checked; one new command has no cap (S8) | `boot "Continue"`: 881 B, 7 lines. `ledger`: 6 lines. `hr hire --dry-run`: 5 lines. `req verify` prints one line per ledger line (13 lines for 12 ledger lines), and `ledger --helpers` printed 49 lines |
| I-05 | holds | `guard diff` exits 0. The added lines hold no `/home/...` or `/tmp/...` paths and no email addresses (grep over `git diff 19fb016..62027dc`). The hire and ledger inbox records carry family and class only |
| I-06 | holds | `learn verify` and `guard diff` both pass. The 5 changed learned files all come from delta `d-20261110-a431e755f2`. `learning/radar/*` is the "state" zone (`engine/guard.py:31`), and inbox files were only appended to |
| I-07 | holds | The three `note` records (inbox, `trust: external`) each carry an official `source` URL. Hire records move only on sealed checks (`sealed: true`) |
| I-08 | holds | `tests/test_learn.py` and `tests/test_mlearn.py` pass. The M18 change (`engine/learn.py:908-911`) does not touch the owner-item paths |
| I-09 | holds | `memory/ml_config.json` is in `KERNEL_FILES` (`engine/guard.py:29`), so the new tunables (`promotion.multiplier`, `hr.auto_template`) cannot be changed by learning. S4 is a doc error about this |
| I-10 | holds | `hr hire --model` sets `explored=False, propensity=1.0` (`engine/hr.py`, the `if model:` block in `hire`). It is not an exploration. See M9 |
| I-11 | holds | Routing set: tier 107/107 at both 19fb016 and HEAD (script over `evals/routing.jsonl`). `tests/test_route.py` passes |
| I-12 | holds | `tests/test_core.py::GateTests` pass. `default_branch()` changes only the branch that `init` records |
| I-13 | holds per the tests | Radar results are still gathered in `due` order. `hr staff` uses `schedule(..., anneal=False)` |
| I-14 | holds | `tests/test_radar.py`: 46 tests OK at HEAD. My exit-time run with a slow fetch on a 4 s budget took 4.09 s at HEAD (12.08 s at 19fb016) |
| I-15 | holds | `git diff --stat 19fb016..62027dc -- contract evals/fixtures` is empty, and `test_fixtures` passes |
| I-16 | holds as a mechanism; one substantive concern (S2) | `brain eval compare` reports 8 pairs for both runs. Only 5 of the 8 template-arm pairs actually contained a template |
| I-17 | holds | `hr audit`: 100 templates, sound. The rack's "token" hits are design tokens or secrets (grep). This review's own brief contains no wage. `hr/rack/*` is the kernel zone. M6 is a related minor item |

## 2. Requirements (docs/REQUIREMENTS.md)

| # | Verdict | Evidence or reason |
|---|---|---|
| R-01 | holds | `eval audit`: 12 tasks, 12 sound |
| R-02 | **broken as stated** (B1) | "met" rests on fact-two-repo-loading. `docs/research/round4/02-facts-recheck.md:40-45` and my own fetch of https://code.claude.com/docs/en/claude-projects: "Cloud threads load each repository's CLAUDE.md instructions but not its skills, .mcp.json servers, or .claude/settings.json"; agents and commands are "Not loaded" |
| R-03 | holds | `test_learn`, `test_guard` and `learn verify` pass |
| R-04 | holds | `test_core.ContractTests` OK |
| R-05 | holds | The schema is unchanged and `test_fixtures` passes |
| R-06, R-19, R-20, R-22, R-27 | hold | The files exist, and `plan` and `lint` run |
| R-07 | holds; content partly stale (S6) | `memory/facts.jsonl` has 18 lines. The recheck found 5 of them changed |
| R-08, R-09, R-21 | not checkable here | They depend on earlier sessions and external sites |
| R-10 | holds | Tier 107/107 |
| R-11 | holds | About 2,569 tokens; `boot` is 881 B |
| R-12, R-15 | not checkable here (live) | |
| R-13, R-14, R-16, R-24, R-26 | hold per the tests | `test_schedule`: 18 tests OK. Full suite OK |
| R-17 | holds | `docs/research/01..10` exist |
| R-18 | holds | |
| R-23 | holds; the count is stale (M1) | It says "358" tests; there are now 427 |
| R-25 | holds; the counts are stale (M1) | It says "42 tests"; `test_radar` now has 46. It says "under a second"; CB-207's forced run reports 4.5 s |
| R-28 | holds; the count is stale (M1) | It says "48 tests"; `test_hr` now has 57 |
| R-29 | **broken** (B2) | `REQUIREMENTS.md:47` says "met, with that measured accuracy" (78% first, 86% top three). This session measured 46/63 on a fresh set (reproduced) and switched automatic template use off (`hr.auto_template` False) |
| R-30 | holds; one clause is stale (M1) | "only the medium band rests on measurements": the inbox now holds settled S (4,294 of 20,000) and L (67,307 of 200,000) hires |
| R-31 | holds | About 2,569 tokens (it says "about 2,550") |
| R-32, R-34 | hold | `hr audit` passes and the commands exist |
| R-33 | holds | `compose_brief`; `test_hr.Briefs` OK |
| R-35 | holds | `docs/research/round3/`, `round4/`, `hr/GUIDELINES.md` |

## 3. BUILD_STATUS improvement-session claims a command cannot reproduce, or that differ

Claims that differ from what a command shows:
1. **CB-206 M18:** "with the code default until that key is added through `brain learn`" (`BUILD_STATUS.md:191`). `memory/ml_config.json` is a kernel file (`engine/guard.py:29`), and no delta can write it. Only a kernel (owner) edit can add the key. The same wording is in `engine/learn.py:908-909`. **should-fix**, high confidence.
2. **"Open, with reasons", line 84** still lists M6, M8, M15, M18, M19 and M20 as "Minor review items not fixed", which contradicts the CB-206 table. Line 25 still says "Full gate, last run: … 406 tests"; the suite now has 427. **should-fix**, high confidence.
3. **Commit 16a4c01** ("a wrong figure still fails"): partly false. The new regex `\b6\b[^.\n]{0,40}\bcrossings\b` passes a wrong figure. Reproduce with `brain eval setup know-memo-facts D`, then a memo with "within 6 hours there are 9 crossings per day": `brain eval grade` printed "know-memo-facts: pass". **should-fix**, high confidence.
4. **CB-207:** "10 sources checked, 12 new items". `learning/inbox/2026-11-10-radar.jsonl` holds 22 leads, all stamped `2026-11-10T22:00:27Z`. The 12 is the cap on printed lines. The "4.5 s" is unconfirmed. **minor**.
5. **Commit 090d392**, "pricing fact corrected": it only appends an inbox note, and `fact-prices` in `memory/facts.jsonl` is unchanged until consolidation. CB-207's own text ("wait in the inbox") is accurate. **minor**.
6. **CB-205** "Brief length … 42 of 200 renders above the 350-word note (31 before), largest 380": the method is not stated. My render (100 templates × {check, sonnet} and {no check, opus}) gives 30 of 200 above 350, largest 383. **unconfirmed**, minor.
7. **CB-205** "(`docs/research/round4/01-data-templates.md`, 14 links)": I count 18 unique URLs. **minor**.
8. **CB-206 M15** "measured 8.1 s exit": the before-figure depends on how slow the server is. My run gives 12.08 s at 19fb016. The after-figure of 4.1 s is confirmed (4.09 s). **minor**.
9. **CB-202** "routing set unchanged at 107/107 size, 105/107 class": confirmed. The 105 counts rows where every labelled field (class and family) matches; there are 76 class labels and 53 family labels. The wording "class" understates that. **minor**.

Not reproducible now (point-in-time; I could not confirm them):
- CB-200 "`brain lint --transcript` … cache read 82%".
- CB-202 "$5.72, helpers 38%; the two Sonnet helpers together cost $0.09, cache read 98%", and "pushed on green" in the scratch project.
- CB-204, the variants that were tried and dropped ("86 → 90", "46 → 54, 63 → 65", "+1 top-3, -4 top-1").
- CB-205 "13 of the reasons are the helper's own reasoning": the notes list exists (`h-20261110-ccd091-notes.md`), but I did not count it.

Confirmed by command or transcript:
- CB-200 baseline at 19fb016: 407 tests OK, budget about 2,550, hr audit counts as stated, 141 items, 12 tasks.
- CB-202 settlements: 4,478 of 60,000 and 4,294 of 20,000.
- CB-204: 46/63 on the new set, 78/86 on the old one. The new set has 100 rows, 100 distinct first choices and 24 rows with Spanish markers. Its writer never ran the selector (its transcript shows only reads of the rack, `when` fields and the old set).
- CB-203 pre-registrations: committed at 21:54:39, before the first trial at 21:55:00. Both arms started in the same second.
- CB-203 verdicts reproduced: "not-proven · p 0.227" and "revert · P(B worse) 0.91". The selector chose a template for 5 of 8 tasks (scratch `eval/ab.json`).
- CB-201 PreToolUse refusal: transcript at 21:47:49, "memory/_hook_probe.txt is in the learned zone".
- CB-201 Stop hook: `stop_hook_summary` at 22:01:33.593Z, plus the inbox ledger record at 22:01:33Z.
- CB-201 helpers: their models, `effortValue` and the absence of CLAUDE.md text in every prefix.
- CB-201 effort and cache wording: matches the official caching page (fetched).
- CB-207 Haiku prices: match the official page.
- CB-205: 180,968 of 60,000 tokens; third pitfalls went from 16 to 0.

## 4. Findings

### Blocking
- **B1. fact-two-repo-loading was found wrong for Project cloud threads, and nothing that rests on it was updated.** The recheck memo (`docs/research/round4/02-facts-recheck.md:40-45`) and my own fetch of the claude-projects page say Project cloud threads load CLAUDE.md but not skills, agents, commands or settings. EXECUTION_PLAN section 2 (bullet 1), REQUIREMENTS R-02 ("met") and the BUILD_STATUS CB-207 summary (`BUILD_STATUS.md:216`, which mentions only hooks) still present the old fact, and no `learn note` records the correction. If the owner works in Project threads, `hr hire`'s named agents and every brain skill would be absent. Confidence: medium-high on the fact. Whether it is blocking depends on which session type the owner uses, which is unknown here.
- **B2. R-29 still says "met" with 78%/86%.** This session showed those figures were overstated (46/63 on a fresh set) and turned automatic selection off (`REQUIREMENTS.md:47`). The same stale figures are in `hr/GUIDELINES.md:71` and `engine/hr.py:640-641`. Under the evidence rule (EXECUTION_PLAN 0.6) the status is now false. High confidence.

### Should-fix
- **S1. "automatically chosen templates did worse than plain briefs on 6 of 8 tasks"** (`.claude/skills/brain-build/SKILL.md:16`; `engine/hr.py` DEFAULT_CFG comment). In 3 of the 8 pairs (data-csv-total, ops-idempotent-dirs, sw-add-slugify) no template was chosen, and the two briefs were identical apart from paths (scratch `eval/ab.json`, diff of `tplB/` against `plainC/` briefs). Two of the 6 losses (+93 and +29 tokens) are therefore noise between identical briefs. High confidence.
- **S2. I-16 substance.** Only 5 of the 8 pairs exposed the change, which is fewer than the 8 that I-16 requires before any claim. The verdict was still used to change the behaviour that had shipped (auto-template on → off). Most token differences (13–645 tokens) are inside the A/A noise (up to 613 tokens, about 5%, on lang-es-glossary). The one quality signal is the translation that was never written. The pre-registration was followed to the letter, so this is a judgement call for the lead. Medium confidence.
- **S3 = §3 item 2** (stale "Open" table and gate count). **S4 = §3 item 1** (the M18 wording). **S5 = §3 item 3** (the grader still passes a wrong figure).
- **S6. Facts the recheck found wrong are still served from memory.** Of the 5 changed facts, notes were recorded only for prices and for effort and cache. `fact-two-repo-loading`, `fact-claudemd-cost` and `fact-fable-limits` remain active and uncorrected in `memory/facts.jsonl`. EXECUTION_PLAN section 2 bullet 5 still calls effort and cache "contested … CB-112 measures it", and CB-112 is still `live` in `docs/plan/tickets.json`. Medium-high confidence.
- **S7. `tests/test_hr.py::ReviewFindings::test_cap_counts_this_sessions_contracts_with_or_without_a_project` is not hermetic.** It is pre-existing: it was already present at 19fb016. The CLI resolves a managed sibling of the brain as the project and writes hire contracts into its `.brain/log/hr/`. Once 4 are open there, the test fails: "Lists differ: [1, 1, 1, 1] != [0, 0, 0, 0]". I reproduced this with a brain copy next to a scratch managed project, where CB-205's acceptance command then exited 1. In the real two-repo layout, running the suite would write contracts into the owner's project. High confidence.
- **S8. I-04 for `req verify`.** There is no line cap: it prints 1 line per ledger line, plus up to 3 per failure (13 lines for 12 ledger lines in a scratch project). `ledger --helpers` printed 49 lines, but that is behind a flag. Medium confidence that this breaks I-04, since "by default" is open to reading.

### Minor
- **M1.** Stale counts in REQUIREMENTS: R-23 (358), R-25 (42 tests, "under a second"), R-28 (48 tests), R-30 ("only the medium band").
- **M6.** Template-review finding G:52, the owner pronouns ("because he has no terminal", `hr/rack/support.jsonl`), was neither fixed nor listed in the CB-205 open items.
- **M7.** Nine templates changed only their `pitfalls` without a `version` bump. No rule requires a bump, so this matters only if `version` is meant to track text changes.
- **M8.** Commits 53d92d4 and fded650 lack the `Brain-Bootstrap:` trailer (EXECUTION_PLAN 0.5).
- **M9.** `hr hire --model` lets the lead put any model (haiku included) on a high-risk task. Its outcome is folded as an on-policy observation with propensity 1.0.
- **M10.** A plain scout brief tells the scout to write notes to a file, but the scout has no Write tool (`.claude/agents/scout.md:4`).
- **M11.** On the token metric, `eval compare` counted the failed lang-es-glossary template trial as a B win because it used fewer tokens. This is by design (the pass guard blocks only "ship"), but the "2 wins" includes a failure.
- **M12.** The acceptance commands for CB-201 (`grep -q 'CB-201' docs/BUILD_STATUS.md`) and CB-207 (`test -d docs/research/round4`) prove nothing about the work they mark done.
- **M13.** `ledger --helpers` labels its output "asked … effort X", but X is read from the helper's prefix, which is the served effort, not the requested one.
- **M14.** The CB-204 set writer read the templates' `when` text, which quotes trigger phrases. Any leakage would overstate accuracy, not understate it.
- **M15.** `detect --project` / `BRAIN_PROJECT` that names a missing folder silently falls back to scanning siblings.

## 5. Keep
- The pre-registration was committed before the trials (21:54:39 vs 21:55:00), and both arms of each task ran in the same second.
- The fresh held-out set and the honest 46/63 baseline, with a floor test.
- The radar daemon-thread exit (4.09 s on a 4 s budget) and the split of check times into the ignored `checked.json` (the tracked state has no `last_checked`).
- The `KNOWN`-word slip rule (`tests` no longer reads as `tesis`; routing unchanged).
- `req verify`, `eval setup`, `hr hire --template none` and `--model`.
- The researcher and redteam briefs that name the check as the lead's.
- Stop and PreToolUse hooks now observed in transcripts. The cache facts were recorded through `learn note` with official URLs.

END OF FINDINGS
