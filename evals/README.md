# Evaluations

How the brain proves a change helped. Spec: `docs/EXECUTION_PLAN.md` 4.4; method: `docs/research/round2/07-evaluation.md`.

Tiers:
- **0 Contract** (`brain eval contract`): the unit suite. Free; must be 100% before anything else.
- **1 Replay**: the deterministic modules run on recorded artefacts (`recall_golden.jsonl`, `routing.jsonl`, `fixtures/`). Free; shows instructions are followed, not that they help.
- **2 Live paired benchmark**: both arms run the tasks in `tasks/`, `brain eval grade` scores each produced folder, `brain eval record` logs the trial in `runs/<run>.jsonl`, `brain eval compare` gives the verdict.

Other parts: `brain eval audit` (every grader passes its reference and fails its null solution), `brain ablate` (does an always-loaded rule earn its place), `seeded_defects/` with `brain eval defects score` (reviewer catch rate).

Rules that stop self-deception:
1. Pre-register first: `brain eval prereg` writes `prereg/<change>.json`; commit it before the first trial. `compare` refuses a run that starts earlier or uses other tasks.
2. Held-out tasks (`split: heldout`) are never shown while editing or used for tuning; tune on `dev` only. Retire a held-out task once it has chosen between three or more candidates.
3. Run an A/A comparison (same brain in both arms) before the first A/B; it must not ship and it measures the noise.
4. Report n every time. Fewer than 8 paired tasks is always "not proven; keep the old version" (I-16).
5. Infrastructure errors are re-run, never counted as failures (`--infra-error` rows are dropped and counted).
6. Interleave the arms in time, same model and effort, a clean folder per trial.
7. A task that every arm always passes or always fails says nothing; replace it rather than lowering the bar.
