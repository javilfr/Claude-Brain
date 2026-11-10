# Models

Model facts (prices, roles, escalation order, limits) live in `memory/models.json` with a `verified_on` date. Playbooks name roles, not model ids, so a new release changes one file. When `boot` warns the file is past its re-check period, verify against current documentation before relying on it.

## Roles

| Role | Default | Used for |
|---|---|---|
| Lead | Opus 5.5, medium | Running the session and talking to the owner |
| Deep lead | Fable 5.2, high (low or medium when hard but well specified) | New-project architecture, a root cause nobody can find, synthesis across many inputs |
| Reviewer | Opus 5.5, high, fresh context | Defects against the ledger |
| Red team | Fable 5.2, high, one bounded call | A one-way decision |
| Builder | Sonnet 5.5, medium, with a real check | Implementation; failures re-run one step up |
| Writer | Opus 5.5, medium | Prose, translation, long-form |
| Scout | Haiku 5.5, low | Bulk reading and extraction, inputs under 100K tokens |

## Fable versus Opus

On Anthropic's coding benchmark, Opus 5.5 at medium solved 93.1% of tasks at $0.22 per solved task; Opus at high 95.5% at $0.30; Fable 5.2 at high 96.3% at $1.39. So the escalation order is Opus medium, Opus high, then Fable. Fable at low (94.6%, $0.39) suits a task that is hard but well specified. Fable leading Sonnet helpers cost 19% more than Opus for about the same score: Fable earns the lead seat when planning itself is the hard part.

The owner picks the session model; the brain does not switch it, because a switch discards the cache. A helper with no model set inherits the lead's, so every agent file sets model and effort.

## Effort

Effort, not prompt text, controls depth, time and cost. Medium is the default; high helps hard coding and long agentic work; on research it bought little. Low is not safe everywhere: Opus at low scored 34 points lower than medium on a defect-search benchmark. Sonnet at low sometimes reports code done without a real check, so builders run at medium. xhigh and max only for a named hard problem.

## Briefs to any tier

Say: the goal, the constraints, who the output is for and why, what "done" means and how it is checked, which actions are approved, and for design the specific patterns to avoid. Do not say: "think step by step", "verify twice", "be maximally thorough", "always use a subagent", "minimise tool calls", unscoped "never" rules, hard sentence-length rules, token budgets or context countdowns, or "treat that answer as done". On Fable 5.2 these lower quality or raise cost; cautious notes pile up and are followed too literally.

For Sonnet and Haiku helpers, do include the run-a-real-check instruction: both sometimes report work done without one at lower effort.

## Fable 5.2's narrow limits

On accelerator kernel optimisation and LLM architecture it performs at about Opus 5.5's level, and it declines most cybersecurity and research-biology tasks. Route those to Opus from the start: a safety fallback leaves the session on the fallback model and loses the cache. Tell the owner if one happens.
