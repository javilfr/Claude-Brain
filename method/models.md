# Models

Model ids, prices, the default model and effort for each role, the escalation order and limits live in `memory/models.json`, with a `verified_on` date; each agent file sets its own model and effort. A new release changes that file, the agent files and the facts that name models. When `boot` warns the file is past its re-check period, verify against current documentation before relying on it.

## What each role is for

| Role | Used for |
|---|---|
| Lead | Running the session and talking to the owner |
| Deep lead | New-project architecture, a root cause nobody can find, synthesis across many inputs |
| Reviewer | Defects against the ledger, in a fresh context |
| Red team | One bounded call at a one-way decision |
| Builder | Implementation with a real check; failures re-run one step up |
| Writer | Prose, translation, long-form |
| Researcher | Sourced questions |
| Scout | Bulk reading and extraction, inputs under 100K tokens |

## Fable versus Opus

On Anthropic's coding benchmark, Opus 5.5 at medium solved 93.1% of tasks at $0.22 per solved task; Opus at high 95.5% at $0.30; Fable 5.2 at high 96.3% at $1.39. So the escalation order is Opus medium, Opus high, then Fable. Fable at low (94.6%, $0.39) suits a task that is hard but well specified. Fable leading Sonnet helpers cost 19% more than Opus for about the same score: Fable earns the lead seat when planning itself is the hard part.

The owner picks the session model; the brain does not switch it, because a switch discards the cache. A helper with no model set inherits the lead's, so every agent file sets model and effort; the per-call model overrides the file, which is how a reviewer runs on a different model from the author.

## Effort

Effort, not prompt text, controls depth, time and cost. Medium is the default; high helps hard coding and long agentic work; on research it bought little. Low is not safe everywhere: Opus at low scored 34 points lower than medium on a defect-search benchmark. Sonnet at low sometimes reports code done without a real check, so builders run at medium. xhigh and max only for a named hard problem. Sources disagree on whether changing effort mid-session keeps the cache (ticket CB-112 measures it), so set effort per agent rather than changing it mid-task.

## Briefs to any tier

Say: the goal, the constraints, who the output is for and why, what "done" means and how it is checked, which actions are approved, and for design the specific patterns to avoid. Leave out "think step by step", "verify twice", "be maximally thorough", "always use a subagent", "minimise tool calls", unscoped "never" rules, hard sentence-length rules, token budgets, context countdowns and "treat that answer as done". On Fable 5.2 these lower quality or raise cost; cautious notes pile up and are followed too literally.

For Sonnet and Haiku helpers, do include the run-a-real-check instruction: both sometimes report work done without one at lower effort.

## Fable 5.2's narrow limits

On accelerator kernel optimisation and LLM architecture it performs at about Opus 5.5's level. It declines penetration testing, exploit and binary-analysis work and most research biology; finding vulnerabilities in source code is allowed. Route the declined kinds to Opus from the start, because a safety fallback leaves the session on the fallback model and loses the cache. Opus 5.5 can fall back on such work too. Tell the owner if a fallback happens.
