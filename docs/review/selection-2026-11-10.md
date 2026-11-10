# hr.select selection review, 2026-11-10 (CB-204)

## Pre-registration (written 2026-11-10 22:45 UTC, after the baseline measurement of the new set and before any change to engine/hr.py)

- Hypothesis: a lexical-only change to `hr.select` in `engine/hr.py` (no edit to `hr/rack`) raises top-3 on the new held-out set by 3 or more points.
- Task set (fixed for both arms, paired by request): `evals/hr_golden_2.jsonl`, 100 new requests, one per template, English and Spanish, dictated style, some typos. Also run unchanged: `evals/hr_golden.jsonl` (100 dev, 100 heldout) as a regression guard.
- Arms: A = `engine/hr.py` as of commit a8da8a2. B = A plus the change.
- Tuning data: dev and the old set only. The new set is never used to choose a change. Caveat: its baseline misses were printed once before registration; no change may be derived from them.
- Metric: top-3 hit rate (any expected id in the first three). Top-1 also reported. Class = template group of the expected template. Cost = selection compute only (no tokens; ms per request).
- Decision rule: accept only if (1) new-set top-3 rises by >= 3 points (3 requests of 100); (2) no class has a lower top-3 on the new set; (3) old-set top-3 and top-1 (dev and heldout) are not lower in any class; (4) `python3 -m unittest tests.test_hr` and `python3 bin/brain hr audit` pass. Otherwise block and keep A.
- Grader audit: `brain eval audit` (12 tasks sound), plus the selection scorer run against the new set with a reference selector (expected ids, must score 100/100) and a null selector (nothing, must score 0/100).

## Grader audit (before the arms were run)

- `python3 bin/brain eval audit`: 12 tasks, 12 sound, 0 broken (that harness covers the live-benchmark tasks, not this deterministic scorer).
- Selection scorer on `evals/hr_golden_2.jsonl`: reference selector (expected ids) 100/100 top-1 and top-3; null selector (nothing) 0/100. The scorer passes its reference and fails its null.
- Every `expect` id exists in the rack; each of the 100 templates is expected exactly once.

## Change B (engine/hr.py only; no `hr/rack` keyword edits, so no keyword changes to list)

1. Accent folding of request and template words (`diseño` and `diseno` meet).
2. Light Spanish suffix stemming (`refactoriza` and `refactorizar` meet).
3. Coverage over words the whole rack knows (`known_coverage`): an extra accept path when it is 0.2 or more, only for racks of 20+ templates (so the small test rack keeps the old floor).
4. Leading-verb role prior: review/audit/verify/revisa in the first four words multiplies builder and writer templates by 0.7; write/build/create/escribe the same for reviewer and redteam.
5. Unrelated fix: `brain hr report` no longer calls records already folded into learning "pending" (test added).

Tuned on dev and the old heldout only; changes 3 and 4 were kept to fix old-set and coordinator-supplied dev cases.

## Paired results (same requests, both arms; top-3 hits, top-1 hits per group of 10)

| Set | A top-1 / top-3 | B top-1 / top-3 |
|---|---|---|
| new (hr_golden_2) | 87 / 90 | 99 / 100 |
| old dev | 100 / 100 | 100 / 100 |
| old heldout | 78 / 86 | 80 / 88 |

New set per group top-3 A to B: build 8 to 10, data 9 to 10, language 7 to 10, planning 9 to 10, quality-ops 9 to 10, review 10 to 10, support 9 to 10, writing 9 to 10, design and discovery 10 to 10. Old heldout: data 9 to 10, quality-ops 8 to 9 (top-1 7 to 8), all others equal. No group dropped in top-1 or top-3 on any set.

Cost: no tokens in selection. Time per request A about 10 ms, B about 50 ms (accent folding on every word; not cached).

## Verdict: ACCEPT

Rule (1): +10 points on the new set (needs +3). (2) and (3): no class dropped on any set. (4): `python3 -m unittest tests.test_hr` 51 tests OK; `python3 bin/brain hr audit` rack is sound.

## Caveats

- n = 100 on the new set, 10 per group; one request per template. One run per arm (deterministic, so no noise estimate).
- The new set was written by the same agent that read the rack keywords, so it is probably easier than real owner speech; a 100/100 is not a forecast of live accuracy. Its baseline misses (10) were printed once before the pre-registration; no change was derived from them, but the Spanish fixes are in the same family, so the set is not fully unseen.
- Old heldout gain (+2) is small and is also tuning data. Remaining old-heldout misses are semantic (planning group 4/10) and untouched.
- The verb prior and known_coverage floor (0.2) are hand-set constants.
