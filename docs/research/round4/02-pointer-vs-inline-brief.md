# Pointer to a brief file versus the brief pasted in (CB-207, measured 2026-11-11)

Question: does delegating with a one-line pointer to the brief file ("Follow the brief at …") cost or save tokens, compared with pasting the same brief into the delegation message?

Method: identical plain briefs from `brain hr hire`, builder on Sonnet 5.5 at medium effort, clean task folders, the task grader as the acceptance command. Helper usage was measured by `brain hr settle` from the helper transcripts (output-equivalent tokens at the helper's own price). The pointer trials are the plain arms of the CB-203 runs (`evals/runs/aa.jsonl`, `evals/runs/ab.jsonl`); the pasted trials are in `evals/runs/inline.jsonl`.

| Task | Pointer (helper tokens) | Pasted (helper tokens) | Tool calls |
|---|---|---|---|
| route-question | 1,666 · 1,753 · 1,721 | 1,475 · 1,465 | pointer 3, pasted 2 |
| sw-fix-median | 2,163 · 2,159 · 2,157 | 1,981 | pointer 4, pasted 3 |

All trials passed.

Reading:
- On the helper side, a pasted brief saves one file read: about 190 output-equivalent tokens per hire (11% on these small tasks).
- On the lead side, pasting means the lead writes the whole brief as output: about 300 to 400 words, roughly 400 to 550 output tokens at the lead's model. For an Opus 5.5 lead that is twice the Sonnet output price. Those tokens also stay in the lead's context and are re-read from cache on every later turn of the session. The pointer costs the lead about 40 output tokens.
- Net: the pointer is cheaper per hire for an Opus lead with Sonnet helpers, and the gap grows with session length. The brain keeps the pointer. A pasted brief would win only where lead output is cheaper than helper input and the session is short, which is not how the brain is set up.

Limits: n = 3 pasted against 6 pointer trials on two tiny tasks. This settles the direction of each component, not a precise number. No efficiency claim is drawn from it beyond "the pointer is not a loss" (I-16 needs eight paired tasks for a claim).
