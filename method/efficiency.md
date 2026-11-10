# Efficiency

The evidence behind the cost rules in `CLAUDE.md` and brain-build. Read it when a cost decision is unclear.

## Where the money goes

Measured on a real session at list prices: cached re-reads were 91% of tokens but 7% of cost; cache writes 36% of cost; output, including thinking, 57%. One output token costs as much as about 200 cached-input tokens on Fable 5.2. So attack output first, then cache writes, then turns, then helpers. The unit that matters is cost per finished task: a cheap attempt that fails pays twice.

- Healthy sessions read about 80% or more of input from cache; lower means something broke it. Always-loaded text that changes mid-project (a date, a status line) rewrites the cache on every request.
- Each avoided turn saves a re-read and a wait, so independent read-only calls go out together.
- Running cheap first and re-running only failures at higher effort solved about 97% of tasks at about $0.17 each, against 95.3% at $0.29 for everything at high: about 40% less for a higher pass rate. It works only when each item has a check that can fail.

## Helpers

Multi-agent work used about 15 times the tokens of a chat in Anthropic's measurements; it pays only for bulky, parallel work. Every helper starts with a cold cache.

## Output

Short reports. Edits, not whole-file rewrites. No restating. No "think step by step" lines: effort sets depth. Very large single writes timed out in earlier projects, and a 2.6 MB paste ended a session, so large content lives in files and the conversation carries paths.

## Quiet-machine gates

A release was once blocked by a 2,652 ms load time against a 2,600 ms budget, measured while other agents shared the processor. Re-run a failed timing check alone before calling it red.

## Fast mode

It costs double and, on a subscription, is billed from usage credits. It stays off unless the owner asks.
