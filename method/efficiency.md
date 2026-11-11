# Efficiency

The evidence behind the cost rules in `CLAUDE.md` and brain-build. Read it when a cost decision is unclear.

## Where the money goes

Measured on a real session at list prices: cached re-reads were 91% of tokens but 7% of cost; cache writes 36% of cost; output, including thinking, 57%. One output token costs as much as about 200 cached-input tokens on Fable 5.2. So attack output first, then cache writes, then turns, then helpers. The unit that matters is cost per finished task: a cheap attempt that fails pays twice.

- Healthy sessions read about 80% or more of input from cache; lower means something broke it. Always-loaded text that changes mid-project (a date, a status line) rewrites the cache on every request.
- Each avoided turn saves a re-read and a wait, so independent read-only calls go out together.
- Running cheap first and re-running only failures at higher effort solved about 97% of tasks at about $0.17 each, against 95.3% at $0.29 for everything at high: about 40% less for a higher pass rate. It works only when each item has a check that can fail.

## Time: Parkinson's law

Work expands to fill the time available, so no time budget in the brain is a generous fixed number. One algorithm (`engine/timebox.py`) sets each one from evidence and gives it two marks: a **target** (what to aim for) and a **stop** (where a decision is made instead of more waiting).

- **Target** = the median of the recent observed durations (the last 20). **Stop** = their conformal 90th percentile times a safety factor. Old, slower runs age out, so budgets shrink as the work gets faster.
- **No evidence yet**: the estimate is the target and twice it the stop; with no estimate, the old fixed value, which is also the cap: evidence can only tighten a budget below what was allowed before.
- **A run that hits the stop** is censored, not a duration: each consecutive one doubles the next stop (up to the cap); the first run that finishes resets it.
- **At the stop**: deliver what is there, split or re-size the rest, or report what is left and why. Never quietly extend.

Where it applies:

| Budget | Before | Now |
|---|---|---|
| `brain run`, gates, helper checks | 3600 s fixed | the default until 5 successful runs, then 3 x their 90th percentile (never under 120 s; a killed healthy build costs a whole re-run). Failures do not shorten it. `--timeout` overrides. |
| `brain req verify` checks | 600 s fixed | the same rule, capped at 600 s |
| live check after `brain release` | 120 s fixed | learned from earlier deployments, at least 30 s, capped at 120 s |
| radar requests | 6 s per source | learned from that source's own latency, 1.5 s to 6 s |
| a size 0 or 1 request (`brain boot`) | none | 3/6 and 20/40 minutes (target/stop), calibrated by `mlearn` from closed sessions; `brain close --tier` records the timebox as the estimate so the calibration learns |
| a plan ticket (`plan schedule`, `plan packet`) | `est`, often the cautious 80th percentile | target = calibrated median, stop = calibrated 80th percentile (or twice `est`) |
| a helper (`hr hire`) | tokens only | a time wage per size (8, 20, 45, 90 minutes, stop twice that) in the brief's `<timebox>`, tightened by the minutes settled hires really took; `hr settle` flags OVER TIMEBOX |

Not applied, on purpose: eval graders keep their fixed timeout (a learned limit could fail a valid trial and bias a measurement), and the 120-minute checkpoint lease stays fixed (it guards against two sessions writing at once; shortening it trades safety, not effort). `brain timebox` shows the learned budgets.

## Helpers

Multi-agent work used about 15 times the tokens of a chat in Anthropic's measurements; it pays only for bulky, parallel work. Every helper starts with a cold cache.

## Output

Short reports. Edits, not whole-file rewrites. No restating. No "think step by step" lines: effort sets depth. Very large single writes timed out in earlier projects, and a 2.6 MB paste ended a session, so large content lives in files and the conversation carries paths.

## Quiet-machine gates

A release was once blocked by a 2,652 ms load time against a 2,600 ms budget, measured while other agents shared the processor. Re-run a failed timing check alone before calling it red.

## Fast mode

It costs double and, on a subscription, is billed from usage credits. It stays off unless the owner asks.
