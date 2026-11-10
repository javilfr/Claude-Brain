# Efficiency

Measured on a real session at list prices: cached re-reads were 91% of tokens but 7% of cost; cache writes 36% of cost; output, including thinking, 57%. One output token costs as much as about 200 cached-input tokens on Fable 5.2. So attack output first, then cache writes, then turns, then helpers. The unit that matters is cost per finished task: a cheap attempt that fails pays twice.

## The ten rules

1. **One model per session.** Switching model, including through a skill that names another model, forces a full re-read at full price. Change effort instead; that keeps the cache on these models.
2. **Always-loaded text is small and never changes mid-project.** It is paid on every request; a date or status line in it rewrites the cache.
3. **Most input is read from cache.** Healthy sessions read about 80% or more of input from cache; lower means something broke it.
4. **Every work item has a check before work starts.** Without a check that can fail, cheaper attempts and escalation cannot work.
5. **Independent read-only calls go out together.** Each avoided turn saves a re-read and a wait.
6. **Bulk output never enters the conversation raw.** Run builds and tests through `BRAIN run -- <cmd>`; it keeps the full log in a file and prints the result and failing lines.
7. **Start at the routed model and effort; escalate only on a failed check.** Running cheap first and re-running only failures stronger saved about 40% at the same pass rate.
8. **Delegate only self-contained, bulky, checkable work**, with a full brief and a reply cap. Each helper starts cold.
9. **Search memory before planning or researching** (`BRAIN recall`). A stored playbook or decision is cheaper than rediscovery.
10. **Checkpoint at each item boundary.** Sessions end without warning; the state file is the only continuity.

## The delegation test

Delegate when the step is self-contained, its raw material is large next to what you need back, and its result can be checked. Multi-agent work used about 15 times the tokens of a chat in Anthropic's measurements; it pays only for bulky, parallel work. A helper replies in under about 2,000 tokens and writes detail to a file.

## Output discipline

Short reports. Edits, not whole-file rewrites. No restating. No "think step by step" lines: effort sets depth.

## Large files

Write long content in parts of about 1,500 words per write; very large single writes timed out before, and a 2.6 MB paste ended a session. Large content lives in files; the conversation carries paths.

## Quiet-machine gates

Timing and performance checks run when no helpers are working. A release was once blocked by a 2,652 ms load time against a 2,600 ms budget, measured while other agents shared the processor. Re-run a failed timing check alone before calling it red.

## Fast mode

It costs double and, on a subscription, is billed from usage credits. It stays off unless the owner asks.
