# Handover: working on the brain itself

For the Claude session that opens this repository on its own. The owner's instruction for it, verbatim (2026-11-10): "Test, analyze, research and improve heavily in a new chat we will start right now with renewed context, prepare everything for new chat with only the brain repo in order to work on it until fully done."

## Update, end of 2026-11-10

The improvement session merged packages A, B, C, D, E, F, M, J and part of I (see the last section of `docs/BUILD_STATUS.md`). Open, in this order: G routing (`docs/plan/tickets.json` CB-218), I1 selection (CB-220; measure only once on `evals/hr_golden_2.jsonl`), H evaluation and radar (CB-219), the instruction surface and owner documents (CB-222, CB-223), then the independent review (CB-208). Each package's findings are rows in `docs/plan/IMPROVEMENT_PLAN.md` section 6, with full text in `docs/review/2026-11-10-audit/<area>.json`.

## Where things stood before that session

- Phase A is built: core file, ten skills, six agents, the engine (`bin/brain`, 22 modules, standard library only), the learning pipeline, the update radar, the evaluation system, and the HR department with its rack of 100 templates.
- Last gate before this handover: 407 tests OK; `doctor`, `lint`, `hr audit`, `items check`, `eval audit` exit 0.
- Nothing has been proven in a live session beyond: skills and agents load from the brain, and two helpers were hired and settled through `brain hr`.
- Evidence and open items: `docs/BUILD_STATUS.md`. Owner clauses and what answers each: `docs/REQUIREMENTS.md`. Binding spec and invariants: `docs/EXECUTION_PLAN.md` (sections 0, 1, 4). Decisions the owner can overturn: `docs/DECISIONS.md`.
- The learning inbox holds three unconsolidated records from the build session (one ledger, two settled hires). The learned zone is not locked (`VERSION.json`).

## What to do

The programme is tickets CB-200 to CB-209 in `docs/plan/tickets.json`; each has a goal, a reason, the files it owns and an acceptance command. `python3 bin/brain plan schedule docs/plan/tickets.json` gives the order; `python3 bin/brain plan packet docs/plan/tickets.json <id>` gives a brief (the full goal text is in the JSON). In short: baseline and first consolidation; live platform checks; a real end-to-end trial on a scratch project with hired helpers; the first paired evaluation of template briefs against plain briefs; better template selection measured on a new held-out set; a quality pass over all 100 templates; the open review items; a fourth research round; a red team and a final independent review; close out.

"Fully done" for this session means: every ticket's acceptance command exits 0, the full gate exits 0, each claim in `docs/BUILD_STATUS.md` matches a command result from the session, and whatever still cannot be proven without the owner or a two-repo chat is listed there plainly.

## How to work here

- This is a one-repository session, so `.claude/settings.json` hooks may load (a guard on the learned zone and a session-end capture). Whether they do is itself ticket CB-201. Nothing depends on them.
- Follow the brain's own rules while changing it: size the work, hire helpers through `brain hr hire` (at most four at once, each with an acceptance command), run commands through `brain run`, never weaken a test, commit after each ticket with the trailer `Brain-Bootstrap: <ticket ids>`, and push the session's branch. Do not push to `main`; the owner merges.
- A change to an invariant, to `CLAUDE.md`, to the contract schema or to a template's text is a kernel change: make it deliberately, test it, and say so in the commit. Learned files (`memory/`, `owner/`, `stats/`, `playbooks/`) change only through `brain learn`.
- Measure before claiming. No efficiency or quality claim on fewer than eight paired tasks. Pre-register comparisons with `brain eval prereg`. Keep held-out sets held out.
- Cost: the build session cost about $162 at list prices, 64% of it helpers. Prefer scripts and the lead's own work; use the brain's agents (they set cheaper models) and keep research to four agents at a time.
- Before the final message: update `docs/BUILD_STATUS.md`, mark tickets, `python3 bin/brain close`, commit and push.

## What needs the owner (unchanged)

`NEEDS_YOU.md`: protect `main` once GitHub's checks can run; GitHub's automatic checks do not start on this account (item 7); the weekly learning run; how learning changes get merged.
