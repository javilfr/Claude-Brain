# Round 4, 04: role lines and method instructions in prompts for strong models

Researched 2026-11-10. Contract h-20261110-83742f. Facts age (CB-207): each claim carries a model and a date.

## Answer (confidence: medium-high on the Anthropic guidance, medium on the studies)

1. Anthropic's current docs say a role line "focuses Claude's behavior and tone" and that "even a single sentence makes a difference". They give no accuracy figure for it. Their own example is "You are a helpful coding assistant specializing in Python." It is not an "expert" claim. (Source A1.)
2. Independent studies on other model families (2024-2025) find that persona or expert lines do not reliably raise factual accuracy. Low-knowledge personas hurt, and a mismatched expert persona can trigger refusals. These studies did not test Claude models. Applying them to Claude is an inference. (Sources S1, S2.)
3. Anthropic's current model pages warn against the detailed-method side more clearly than the role side. For Opus 5, verification and double-check instructions cause over-verification. Step-by-step plans are worse than "think thoroughly". Long standing rules pile up caution on Fable 5.2. (Sources A2, A3, A4.)
4. For a one-line role in a helper brief: it is cheap and fine for tone and focus, but it should not be expected to improve accuracy. The task, the done condition and the scope carry the weight. Keep it short, true and matched to the task. Do not add "world-class" or "expert" claims or "double-check" lines. See the last section.

## A. Anthropic documentation (primary, read 2026-11-10)

Page versions: pages show no dated changelog. The best-practices page lists Fable 5.2, Opus 5.5, Sonnet 5.5, Haiku 5.5 among "current models" (A1). The API-version string in its examples is `2026-10-21` (A1).

A1. Prompting best practices. https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices
Applies to: all current models listed on the page.
- Role: "Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference". Example system line: "You are a helpful coding assistant specializing in Python." (section "Give Claude a role").
- Aggressive wording: "Claude Opus 4.5 and Claude Opus 4.6 are also more responsive to the system prompt than previous models... The fix is to soften any aggressive language. Where you might have said 'CRITICAL: You MUST use this tool when...,' you can use more normal prompting such as 'Use this tool when...' instead." Also "Remove over-prompting." (Models: Opus 4.5 and 4.6, plus later "4.6 models" in the migration list.)
- Method: "Prefer general instructions over prescriptive steps. A prompt such as 'think thoroughly' often produces better reasoning than a hand-written step-by-step plan. Claude's reasoning frequently exceeds what a human would prescribe." (section on thinking).
- Self-check: "Ask Claude to self-check. Append something like 'Before you finish, verify your answer against [test criteria].' This catches errors reliably, especially for coding and math. Claude Opus 5 is the exception: it verifies its own work well without explicit instruction, and verification instructions carried over from prompts tuned for earlier models can cause over-verification, adding tokens and latency. On Claude Opus 5, remove these instructions rather than rewriting them."
- Verbosity: "Claude Opus 5 is an exception on verbosity: its default user-facing responses run longer than prior models', and raising or lowering effort does not reliably change visible response length. Prompt explicitly for conciseness instead." Fable 5.1 "has the opposite tendency during agentic work: it writes fewer user-facing updates."
- Subagents: "Claude Opus 5 also delegates to subagents more readily than prior models"; "Claude Opus 4.6 has a strong tendency to use subagents". The page advises explicit guidance on when delegation is warranted.

A2. Prompting Claude Opus 5. https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
Applies to: Claude Opus 5 only. Opus 5.5 says its page builds on this one ("remain a reasonable starting point", A5). Whether every Opus 5 behaviour holds on Opus 5.5 is unconfirmed.
- Over-verification: "If your prompt contains explicit verification instructions ('include a final verification step for any non-trivial task,' 'use a subagent to verify'), remove them: instructions like these cause over-verification on Claude Opus 5, and removing them reduces wasted tokens with no loss in quality."
- Re-checks: "Avoid instructing re-checks it already performs ('double-check your answer,' 're-verify before responding'); like verification instructions, these compound with the model's own behavior and add cost without improving results."
- Scope: "Claude Opus 5 can also expand the scope of a task, adding steps that weren't requested". Suggested fix: "Deliver what was asked, at the scope intended."
- Verbosity: "Claude Opus 5's default user-facing responses run longer than prior Opus models'... To control response length, prompt for it explicitly." Written files are "often longer than on prior models".
- Subagents: "Delegate to a subagent only for large tasks that are genuinely independent and parallelizable... do not use subagents to verify or double-check your own work."
- Literal reading of review prompts: "If your review prompt says 'only report high-severity issues' or 'be conservative,' the model might follow that instruction literally and report less".

A3. Prompting Claude Fable 5.2. https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2
Applies to: Fable 5.2 and Mythos 5.2.
- Instructions are followed closely and accumulate: "Cautious instructions build up wherever context carries over: memory, notes, instruction files, and messages between agents. Claude Fable 5.2 follows these instructions closely, so it might ask for approvals it doesn't need or hold back routine work." Rule listing "sending messages to people outside this conversation" made it hold back "roughly half of its routine requests".
- Style rules: "a hard limit such as 'one instruction per sentence, in 20 words or fewer' can make its prose choppy."
- Think-less lines: "an instruction to answer directly without deliberating didn't stop the model from thinking at medium and above"; effort "barely changes how long the model's replies are. To change the length and tone of a reply, use your prompt."
- Role-like framing has measured effects: the single sentence "This codebase is yours: what it's for and how it's built are your call" raised merging of repeated code from under a tenth to about half of tries, with about 1.5 times the output tokens and unrequested changes. This is a framing sentence, not an "expert" line, but it shows that one line of identity or ownership can shift behaviour and cost on Fable 5.2.
- Subagents: a description that stated cost first made the model "delegate about a third less often... Task success was the same."
- Reports: the model "uses subagents to review its own work" at `xhigh` and `max` (an over-verification risk).

A4. Prompting Claude Sonnet 5.5. https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5
Applies to: Sonnet 5.5, the helper model in memory/models.json (`builder` and `researcher` roles).
- Verification is not always automatic here: "At low effort, though, it sometimes reports a change as done without running a check that exercises it." A paragraph requiring a real check made skipped checks "rare, with no measurable change in task quality and only a slightly higher cost per task". Opposite of Opus 5.
- Over-verification at high effort: at `xhigh` and `max` "it can start its own rounds of review and verification, sometimes with subagents". A stop line "stopped the model from launching reviewer subagents and cut session cost by about a third, with no change in quality" (at `max` effort, coding tasks).
- Scope: "The model tends to add tests, documentation, and small supporting files... even when you don't ask". Fix: "Don't add features, tests, files, docs or refactors that weren't asked for."
- "Asking the model in the system prompt to think less doesn't reliably reduce its thinking."
- A one-line method hint did help: "Think the problem through before you answer." brought accuracy "close to what the model reaches at xhigh" on JSON reasoning tasks at high effort.

A5. Prompting Claude Opus 5.5. https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5
Applies to: Opus 5.5.
- "To get less thinking, lower the effort level first. Lowering effort reduces thinking, and with it cost and latency, more reliably than prompt instructions do."
- Think-carefully lines in chat prompts: "consider removing them for Claude Opus 5.5... removing such a line made replies start sooner, with no clear decline in the quality of the reply."
- Warning on "treat that answer as done" lines: they may make the model "less likely to point out a mistake in an earlier answer".
- Instructions naming a specific behaviour work: "responsive to instructions that name the specific kinds of early stop you want it to avoid".

No Anthropic page I read measures an "You are an expert X" line on accuracy. Absence of a number is not evidence of no effect.

## B. Studies (2024-2026)

S1. Zheng et al., "When 'A Helpful Assistant' Is Not Really Helpful: Personas in System Prompts Do Not Improve Performances of Large Language Models", Findings of EMNLP 2024 (v1 Nov 2023, v3 9 Oct 2024). https://arxiv.org/abs/2311.10054 ; https://aclanthology.org/2024.findings-emnlp.888/ (peer reviewed)
- Quote: "adding personas in system prompts does not improve model performance across a range of questions" and "the effect of each persona can be largely random". Persona gender, type and domain still affect accuracy, and automatically picking the best persona was no better than random.
- Models: "4 popular families" of open-weight LLMs per the arXiv page I read. Names were not shown on the page. Claude models were not confirmed among them. Per a search summary, 162 roles and factual questions (MMLU-style); I did not verify those counts in the paper.
- Date applies: models of 2023-2024, not Claude 4.x or 5.x.

S2. Basil et al. (Mollick, Mollick et al.), "Prompting Science Report 4: Playing Pretend: Expert Personas Don't Improve Factual Accuracy", Wharton Generative AI Lab, 5 Dec 2025 (arXiv v1). https://arxiv.org/abs/2512.05858 ; https://gail.wharton.upenn.edu/research-and-insights/playing-pretend-expert-personas/ (arXiv preprint and lab report; not shown as peer reviewed)
- Quotes: "persona prompts generally did not improve accuracy relative to a no-persona baseline"; "Expert personas showed no consistent benefit across models, with few exceptions"; "Low-knowledge personas often reduced accuracy." Report: "practitioners should focus on task-specific instructions rather than persona assignment." Personas "may serve other purposes", such as tone.
- Models (lab page): GPT-4o (2024-08-06), GPT-4o-mini, o3-mini, o4-mini (2025-04-16), Gemini 2.0 Flash, Gemini 2.5 Flash. No Claude model.
- Tasks: GPQA Diamond (198 questions) and MMLU-Pro (300 questions). Page: no expert persona reliably improved GPQA for any model; on MMLU-Pro most showed no gain for five of six models, with nine significant negative differences. Mismatched expert personas made Gemini 2.5 Flash often refuse.
- Contrary evidence: the exception is Gemini 2.0 Flash (abstract). A secondary summary (themoonlight.io, rebuttal paper "The Arrival of AGI? When Expert Personas Exceed Expert Benchmarks") claims the design was too insensitive and reports gains such as +14.9% for a chemistry expert on Gemini 2.0 Flash. I did not read that paper; treat it as contested and unconfirmed.

Limits of S1 and S2: both measure accuracy on multiple-choice factual questions. They say nothing about verbosity, over-verification, or agentic work, and neither tested a model from the Claude family.

## C. What each lever does, by evidence

| Lever | Accuracy | Verbosity | Over-verification | Evidence |
|---|---|---|---|---|
| One-line role or persona | No reliable gain on factual QA (other model families, 2023-2025). Wrong or low-knowledge persona can hurt or cause refusals. | Tone and focus shift, per Anthropic (unquantified). | Not measured. | S1, S2, A1 |
| "Expert"/"world-class" claim | No consistent benefit (S2). | Not measured. | Not measured. | S2 |
| Step-by-step method plan | Anthropic: general instruction often reasons better than a hand-written plan. | Not measured. | Not measured. | A1 |
| "Verify / double-check" lines | Help on earlier models, "especially for coding and math". Sonnet 5.5 at low effort: needed to stop skipped checks. | Extra tokens | Opus 5: causes over-verification, no quality gain. | A1, A2, A4 |
| Strict or absolute rules | Followed closely. | Fable 5.2: can make prose choppy. | Fable 5.2: caution accumulates, holds back routine work. | A3 |
| Explicit length instruction | n/a | Works. Effort does not change reply length reliably on Opus 5 or Fable 5.2. | n/a | A1, A2, A3 |
| Explicit scope or stop line | n/a | Cuts additions. | Sonnet 5.5: cut session cost by about a third at max effort. | A4 |

## D. What this means for a one-line role statement in a helper brief

Inference, not a quoted fact: the evidence supports the following. Treat as estimates, to be tested on this repo's own helpers.

1. Keep the role line. It is cheap and Anthropic says a single sentence focuses behaviour and tone (A1). Do not rely on it for correctness; the studies found no reliable accuracy gain from persona lines (S1, S2), although those studies did not test Claude.
2. Make it a job description, not a credential. A line such as "You are a research helper for this repo; report facts with sources" matches Anthropic's own example. Avoid "world-class expert in X". Do not name a domain that does not match the task, because S2 saw refusals and accuracy loss from mismatched personas.
3. Put the weight on the task, the done condition and the scope. Anthropic's tested wording is of that kind: "Deliver what was asked, at the scope intended" (A2) and "When the work the user asked for is done and checked, stop and report. Don't add features, tests, files, docs or refactors that weren't asked for." (A4).
4. Do not paste "double-check" or "use a subagent to verify" into briefs for Opus (A2). For Sonnet 5.5 helpers at low effort, one real-check line is supported (A4). Match the line to the helper's model and effort from memory/models.json, not a single default.
5. Prefer a short outcome statement over a hand-written method (A1). Ask for length explicitly, because effort does not reliably control it (A2, A3).
6. Be careful with one-line framing that changes ownership or authority ("this codebase is yours"). On Fable 5.2 it changed behaviour and cost (A3).
7. If the role line is kept in CLAUDE.md or a brief carried by every helper, remember that CLAUDE.md is paid on every request (memory/facts.jsonl, fact-claudemd-cost). One line is negligible; accumulated rules are not.

## E. Not checked or unconfirmed

- Whether Opus 5's over-verification guidance holds unchanged on Opus 5.5, Fable 5.2 or Sonnet 5.5: unconfirmed (the Opus 5.5 page does not repeat it; the Fable 5.2 page notes self-review with subagents at xhigh/max).
- Names of the four model families in S1 and the 162/2,410 figures: not confirmed from the paper itself.
- The rebuttal paper on S2 (arXiv 2603.20225 appeared in search): not read.
- Studies that test Claude models on persona prompts: none found. Other positive-persona papers (for example 2023 role-play prompting work): not checked.
- Page dates: the Anthropic pages show no publication dates; "2026-11-10" is the read date only.
- Older Claude 4.x-only pages (Opus 4.7, 4.8, Sonnet 4.6, Haiku 4.5, Haiku 5.5, Sonnet 5): not read.
- Two search summaries (watts.it.com, distl.com.au) were seen in results and not used.

END OF MEMO
