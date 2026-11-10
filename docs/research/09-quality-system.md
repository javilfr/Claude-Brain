# 09 — Quality system for the Claude Brain (analyst 9 of 10)

Lens: "absolutely highest quality work with absolute attention to detail (focus a lot on accuracy, creativity and extreme attention to detail)", achieved without wasting tokens.

Claim tags: `[source: URL]` external source; `[local-doc]` the bundled Claude API reference at `/tmp/claude-0/bundled-skills/2.1.322/abe77d722f7cc0e8bbf4058a7be92fb3/claude-api/shared/model-migration.md` (section named in the text); `[sample-repo]` the read-only Travel Journal company repo; `[inference]` my own reasoning. Where a number reached me only through a search summary and I did not open the primary paper, it is marked "(secondary)". Nothing in this report was measured by me on the Brain itself; every threshold proposed here is a starting value to be tuned by the Brain's own evals.

---

## PART A — Independent extraction of message 2

Each item quotes the owner's words. Type: R = requirement, C = constraint, P = preference, I = implied expectation, A = ambiguity, X = impossible as literally written, needs honest reframing.

### A.1 What the thing is

1. R — "I essentially used this repo as a brain to create everything in my travel journal in the best possible way." The sample repo is the reference pattern and the quality bar ("best possible way"). The new repo must keep what worked there.
2. R — "I want now to create a repo that will act as that (essentially a mega complex orchestrator)". Deliverable is a repository, and its role is orchestrator. A: "mega complex" describes capability, but complexity itself costs tokens and conflicts with item 17. Reframe: complex in what it can do, small in what it loads per task.
3. R — "but to build anything I will ever need from now on." Universal scope: not one product. X: "anything … ever" cannot be guaranteed. Reframe: a general intake-to-delivery method with deliverable types, plus an explicit way to add a new type when one is missing, plus honest "cannot do, here is why" reporting.
4. C — "When using it I will always use two repos in a chat, one of them the Claude brain". Two-repo sessions are the only supported mode. I: the Brain must detect and bind to whichever second repo is attached, including an empty one.
5. C/X — "which will be only modified by its own machine learning systems as it improves by learning with everything I use it for". (a) The owner will not hand-edit the Brain; (b) the Brain must improve from every use; (c) changes to the Brain must come from a defined learning mechanism, not ad hoc edits during project work. X: there is no weight training available in Claude Code. Reframe honestly: "machine learning systems" = a file-based learning loop (lessons, evals, measured prompt/skill revisions, scorecards) run by Claude, with gates so the Brain does not degrade itself. A: the first build necessarily writes the Brain by hand (the lead does); "only modified by its own systems" can only start after bootstrap. A: does "learning with everything I use it for" include storing project content in the Brain? Privacy and repo-size consequences; default should be distilled lessons, not raw project data.
6. R — "the other repo will be where the project will be built". Product code and artefacts live only in the project repo.
7. R — "which can also hold files and tools to complement the Claude brain functionality that are specific to that project". A project-side extension layer (project CLAUDE.md, agents, skills, hooks, project definition-of-done overrides, project ledger). I: a defined contract and precedence order between Brain rules and project rules.
8. R/X — "both will always be worked together from now on so the project must be built to work perfectly with it forever." Forward and backward compatibility between Brain versions and project repos. X: "perfectly … forever" cannot be promised. Reframe: versioned contract, a compatibility check at session start, and a migration step when the contract version changes.

### A.2 What to produce now

9. R — "Now you will create a super long, super detailed plan on how to build this". A plan document is the first deliverable. P: long and detailed. A: tension with token efficiency (item 17); resolve by making the plan a file that is read in sections, never loaded whole at runtime.
10. R — "based on very comprehensive research about Claude fable 5.2 and opus 5.5 (the main models ai will use it with)". Research on both models is mandatory input, and the Brain must be tuned for both. A: "ai" is almost certainly "I". I: cheaper tiers may be used for sub-tasks, but the main loop targets these two.
11. R — "and also using everything we learned with the sample repo I attached". Lessons from the sample repo must be extracted and carried over explicitly (traceably, not by impression).
12. C — "(obviously having present that the current Claude brain's scope for creating stuff is much bigger)". Nothing travel-journal-specific may be baked into the Brain core.
13. R/X — "Also you must look at all your memory in detail and all our chats". X: a session has no access to past chats beyond what is in attached repos, memory files and this conversation. Reframe: mine every available trace (the sample repo's status logs, lessons, NEEDS_YOU, owner briefs, handover notes, decisions) and say plainly which history could not be read.
14. R/X — "and consider everything I have ever asked you to build on Claude or any question I have ever asked you can be successfully processed to completion." The Brain must handle both build requests and plain questions, end to end. X: the full history is not available (item 13). Reframe: derive a request catalogue from what is visible, plus a broad taxonomy of deliverable types, and make "answer to a question" a first-class deliverable with its own definition of done.
15. R — "considering also all our previous builds in Claude". Same as 13/14: previous builds are a requirements source. Only the Travel Journal build is observable here; that must be stated.

### A.3 Efficiency

16. R (flagged by the owner as top priority) — "Also VERY IMPORTANT, you MUST MAKE THIS THE MOST EFFICIENT CLAUDE TOOL EVER". X: an unverifiable superlative. Reframe: measured token and time budgets per task type, a baseline, and a published scoreboard that must improve.
17. R — "it should be much more efficient in tokens". Token cost per delivered task is a primary metric.
18. R — "through plugins and algorithms". Use Claude Code plugins/skills/MCP/hooks and deterministic code (scripts, retrieval, caching, routing) in place of model tokens where possible.
19. X — "and quantum logic". No quantum computation is available or relevant. Honest reframing options: say so directly; if a meaning is wanted, the nearest real ideas are probabilistic routing, keeping several candidate approaches open and collapsing late, and search/annealing-style heuristics. Do not label ordinary code "quantum".
20. R — "and many other thing you must research to see how you can make this super efficient token wise". Open-ended research mandate on efficiency; the plan must show the research, not just assert techniques.
21. R — "and super fast". Wall-clock speed is a separate metric from tokens (parallelism buys speed and costs tokens; the two can conflict).

### A.4 Quality

22. R — "while delivering the absolutely highest quality work". Efficiency must not be bought with quality. Quality is the constraint; efficiency is optimised inside it.
23. R — "with absolute attention to detail". Nothing in a request may be dropped; small defects count.
24. R — "(focus a lot on accuracy, creativity and extreme attention to detail)". Three named quality dimensions. A: accuracy and creativity pull in different directions; the system must say when each dominates.

### A.5 Process

25. R — "Create now the super long and super detailed plan … and then start building until completion once you have a full plan based on extremely extensive research." Order: research, then full plan, then build, without stopping to ask. A: "completion" is undefined; needs a written definition of done for the Brain itself. I: no approval gate between plan and build.
26. R — "Make sure you analyze this prompt by 10 independent agents". Exactly ten analysts, independent (no shared drafts). This report is one of them.
27. R — "and extract everything I said in full detail". A requirements ledger with nothing omitted; the owner expects to be able to check his sentences against it.
28. R — "and you can execute to perfection by planning perfectly and researching and analyzing heavily everything". X: "perfection" is not attainable; reframe as evidence-linked acceptance checks for every ledger row and honest reporting of any row not met.

### A.6 Implied by context (not in his words, but binding)

29. I — The owner "prefers clicking/reading files, never shell commands" (context note). Every artefact he must act on is a file or link.
30. I — Max subscription: the scarce resources are usage limits and time, not dollars per token; efficiency should be reported in tokens and in sessions-to-done.
31. I — The sample repo is read-only in this chat (message 1: "we will not modify or touch this repo at all").
32. A — Who approves Brain self-modifications? "only modified by its own machine learning systems" implies no owner review, but an unreviewed self-editing rule base is a one-way-door risk. Proposed default: self-edits go through the Brain's own eval gate and are logged in a file the owner can read and revert.
33. A — Output languages: the sample repo scaffolds English, Spanish and Japanese; the owner did not state languages for the Brain. Default: English working language, deliverable language per request.

Items needing honest reframing in the plan's first page: 3, 5, 8, 13, 14, 16, 19, 28.

---

## PART B — The quality system

### B.0 Design principles (what the evidence says, in one page)

1. **External checks beat self-reflection.** Models asked to re-examine their own reasoning without new information flip right answers to wrong about as often as the reverse; one reported case is GPT-3.5 on GSM8K going 75.9% to 74.7% after self-correction (secondary). [source: https://arxiv.org/abs/2310.01798] A 2026 preprint finds Self-Refine and Reflexion never reliably beat plain repeated sampling at equal token cost (small models only, preprint, secondary). [source: https://arxiv.org/pdf/2607.28576] So the cheapest reliable verifier is something executable: a test, a build, a link check, a screenshot.
2. **A reviewer must not be the author, and should not share the author's context.** LLM evaluators recognise and favour their own generations, and the bias scales with self-recognition. [source: https://arxiv.org/abs/2404.13076] Claude Code's own guidance: review "in a fresh subagent that never saw your conversation. It isn't swayed by the reasoning that produced the code." [source: https://code.claude.com/docs/en/best-practices] Anthropic's Fable guidance: "Separate fresh-context verifier sub-agents tend to outperform self-critique." [local-doc, Fable 5.1 long-running agent recommendations] Chain-of-Verification shows the same mechanism: answering verification questions without access to the draft ("factored") avoids copying the draft's errors. [source: https://arxiv.org/abs/2309.11495]
3. **Rules that cannot have exceptions go in hooks, not prose.** "If something has to happen every time, make it a hook, a deny rule, or a managed setting. CLAUDE.md is for guidelines." Also: keep the enforced set small; "if you ever find yourself at forty of them, most are probably preferences." [source: https://code.claude.com/docs/en/best-practices]
4. **On the current models, verification prose is often counter-productive.** Claude Opus 5 "verifies its own work without being told", and instructions such as "double-check your answer" or "use a subagent to verify" cause over-verification; the guidance is to delete them. For Opus 5.5, re-test those instructions rather than carry them over. [local-doc, Migrating to Claude Opus 5 → Over-verification; Migrating to Claude Opus 5.5 → Behavioral shifts] For Fable-class models, prescriptive step-by-step scaffolding "reduce[s] output quality"; state goal and constraints. [local-doc, Fable 5.1 long-running agent recommendations] Consequence: the Brain's quality system must be mostly artefacts and deterministic gates, with very little "be careful" text.
5. **Every review asked to find problems finds some.** "A reviewer that's asked to find problems will always find something. If you fix every finding, you end up with extra abstraction layers and tests for cases that can't happen." [source: https://code.claude.com/docs/en/best-practices] So reviews need a severity bar, a stop rule and a cap on rounds.
6. **Multi-agent work costs about 15 times a chat and about 4 times a single agent; token spend explained 80% of performance variance in one Anthropic analysis.** [source: https://www.anthropic.com/engineering/multi-agent-research-system] Quality bought with agents is real but expensive, so it must be rationed by risk.
7. **Short checklists at pause points work.** The WHO surgical checklist (19 items at three pause points) was associated with deaths falling from 1.5% to 0.8% and complications from 11.0% to 7.0% across 7,688 patients in eight hospitals. [source: https://news.harvard.edu/gazette/story/2009/01/surgical-safety-checklist-drops-deaths-and-complications-by-more-than-one-third/] Gawande's two formats: DO-CONFIRM (work from skill, then pause and confirm) and READ-DO (read each step, do it). [source: https://www.stevegrossi.com/on/the-checklist-manifesto] The often-quoted "five to nine items" limit is practitioner advice I could not trace to a primary statement.

### B.1 Accuracy

#### B.1.1 Grounding and citation discipline

- **Rule G1 — pinned docs, never memory, for any library/API/CLI.** The sample repo already has it: "never use a library API from memory — query the pinned docs". [sample-repo, CLAUDE.md §7] Anthropic's own migration guide applies the same rule to itself: "Verify type and method names against the SDK source before writing them into customer code." [local-doc, Per-SDK Syntax Reference] Evidence that memory is unsafe: across 576,000 generated code samples and 16 models, hallucinated package names were common (about 5% for commercial models, about 22% for open models, secondary), and 43% of hallucinated names recurred on all ten repeats of a prompt, which makes them exploitable. [source: https://www.darkreading.com/application-security/ai-code-tools-widely-hallucinate-packages]
  - Mechanism: a per-project `docs-pin.json` (package → version → local snapshot path or URL), produced from the lockfile by a script. Deterministic detector: a pre-commit script that resolves every newly added import and dependency against the lockfile and the registry; an unresolved name fails the gate. Cost: zero model tokens. [inference]
- **Rule G2 — every factual claim in a research or analysis deliverable carries a tag**: `[source: URL]`, `[file: path:line]`, `[computed: script]` or `[inference]`. Untagged factual sentences fail a regex lint in research deliverables. [inference]
- **Rule G3 — citations are checked mechanically, then semantically.** Fabricated references remain a live failure: studies report 18% of GPT-4 citations fabricated (2023), 5.4% of 500 (2024), and 19.9% of 176 for GPT-4o in a 2025 mental-health study; rates vary with topic obscurity (all secondary). [source: https://arxiv.org/pdf/2406.14765] [source: https://mental.jmir.org/2025/1/e80371] Opus 5.5 is reported as "much less likely than Claude Opus 5 to state a figure or cite a source the inputs don't support", which lowers but does not remove the risk. [local-doc, Opus 5.5 capability improvements]
  - Step 1 (deterministic): every URL returns a 2xx/3xx and every DOI resolves (`lychee` or a 30-line script).
  - Step 2 (cheap model, fresh context): for each claim–source pair, fetch the source and answer "does this passage support this sentence: yes / partly / no", quoting the supporting span. This is the pattern Anthropic uses: a separate citation pass after research, and judge criteria "factual accuracy (do claims match sources?)" and "citation accuracy (do cited sources match the claims?)". [source: https://www.anthropic.com/engineering/multi-agent-research-system]
  - Step 3: numbers are compared as strings against the quoted span; a mismatch is a hard fail. [inference]
- **Rule G4 — source quality order**: primary source, then official documentation, then peer-reviewed or first-party engineering posts, then secondary summaries, flagged as such. Anthropic's human reviewers found early agents "favored SEO-optimized content farms over authoritative sources". [source: https://www.anthropic.com/engineering/multi-agent-research-system]

#### B.1.2 Claim verification methods, ranked by cost per caught error [inference, built on the sources cited]

| Rank | Method | Use when | Evidence |
|---|---|---|---|
| 1 | Executable check (test, typecheck, build, schema validation, link check, recomputation script) | Anything that can be run | Self-correction without external feedback does not help. [source: https://arxiv.org/abs/2310.01798] "Ask Claude for evidence: the command it ran and its output". [source: https://code.claude.com/docs/en/best-practices] |
| 2 | Retrieval check against the pinned source | APIs, facts with a canonical source | Rule G1/G3 |
| 3 | Factored Chain-of-Verification by a fresh-context cheap model | Factual prose with no executable check | FactScore 55.9 to 71.4 on long-form (secondary); cost is extra generations. [source: https://arxiv.org/abs/2309.11495] |
| 4 | Self-consistency: N independent short answers, compare | A single decisive number, classification or decision | GSM8K 56.5% to 74.4% in the original paper, with diminishing returns as N grows. [source: https://arxiv.org/abs/2203.11171] Debate at equal budget is contested: one analysis has 9-response debate at 83.0% vs self-consistency 88.2%; a 2026 study finds debate slightly ahead on harder tasks. [source: https://arxiv.org/abs/2310.01798] [source: https://preview.aclanthology.org/ingest-acl/2026.acl-srw.1/] |
| 5 | Independent verifier agent on a different model | High-stakes deliverables | Self-preference bias. [source: https://arxiv.org/abs/2404.13076] |
| 6 | Same-context self-review | Never as a gate; it is what the model does anyway | [local-doc, Opus 5 over-verification] |

Disagreement is the signal. When two independent short answers differ, escalate that single item; do not re-verify the whole deliverable. [inference]

#### B.1.3 Judge reliability (what an LLM reviewer can and cannot be trusted with)

- Judges favour their own model's text. [source: https://arxiv.org/abs/2404.13076] Mitigation: reviewer model differs from author model where possible (author Fable 5.2 → reviewer Opus 5.5, or the reverse) and author identity is withheld. [inference] The sample repo already withholds author identity from its design critic. [sample-repo, .claude/agents/design-critic.md]
- Rubric scoring has position bias: models over-select the score option listed first, and the order of criteria shifts scores; balanced permutation improves agreement with humans. [source: https://arxiv.org/abs/2602.02219] Cheap mitigation: binary criteria ("passes when …") instead of a 1–5 scale, which removes the option list entirely. Practitioner guidance (Hamel Husain, via Simon Willison's notes) prefers pass/fail plus a written critique over Likert scales; one 2026 paper reports best human alignment on a 0–5 scale, so this is consensus practice, not settled science. [source: https://simonwillison.net/2024/Oct/30/llm-as-a-judge] [source: https://arxiv.org/html/2601.03444v1]
- Anthropic found "a single LLM call with a single prompt" outputting a score and a pass/fail was more consistent with human judgement than multiple judges, and that about 20 representative cases are enough to see large effects. [source: https://www.anthropic.com/engineering/multi-agent-research-system] Consequence: one reviewer with a good rubric, not a panel, is the default.
- A judge must be validated: measure its true-positive and true-negative rate on labelled cases, because with 90% passing work a judge that always says "pass" scores 90% accuracy and catches nothing (secondary). [source: https://tianpan.co/blog/2025/10/04/llm-as-judge-evaluation] The Brain should keep a small set of **seeded-defect cases** per rubric and re-run it whenever the reviewer prompt or model changes. [inference]
- Review recall depends on phrasing: with "only report high-severity issues" the model finds bugs and then declines to report them. Recommended: "Report every issue you find … include your confidence level and an estimated severity so a downstream filter can rank them", and filter afterwards. [local-doc, Opus 4.7 → Code review; carried into Opus 4.8]

#### B.1.4 Tests and executable checks

- **Reproduce before fix.** Claude Code's own example of a good prompt: "write a failing test that reproduces it, then fix it". [source: https://code.claude.com/docs/en/best-practices] Deterministic proof: the test's commit shows red before the fix and green after; the ledger stores both outputs. [inference]
- **Tests written independently of the implementation.** AgentCoder separates the test designer from the programmer so tests come from the requirement, not from the code; it reports 96.3% pass@1 on HumanEval with GPT-4 (secondary). [source: https://arxiv.org/abs/2312.13010] CodeT ranks candidates by agreement with generated tests (+18.8 points pass@1 on HumanEval). [source: https://arxiv.org/abs/2207.10397] AlphaCodium's test-driven flow moved GPT-4 from 19% to 44% pass@5 on its validation set. [source: https://www.arxiv.org/pdf/2401.08500] Brain rule: for standard tier and above, acceptance tests are derived from the ledger row before or separately from the code, and the implementer may not edit them without a logged reason. [inference]
- **Property and differential tests for anything with an invariant.** 2.8% to 15.3% of programs from current frontier models that pass unit tests fail an LLM-generated property test. [source: https://icml.cc/virtual/2026/77983] An agent writing Hypothesis tests found real bugs in NumPy, SciPy and Pandas; 56% of its reports were valid after manual review. [source: https://arxiv.org/abs/2510.09907] [source: https://red.anthropic.com/2026/property-based-testing] The sample repo's "export → wipe → import round-trip test" is a property test and was its strongest gate. [sample-repo, CLAUDE.md §1.2] Standard invariants to try first: round-trip (encode/decode, export/import), idempotence (running twice equals once), oracle comparison (old implementation vs new, or two independent implementations), conservation (totals reconcile). [inference]
- **Tests can be gamed.** METR observed frontier models altering test or scoring code; low overall (0.7% of HCAST runs) but up to every trajectory on particular tasks, and METR warns the figure may underestimate. [source: https://metr.org/blog/2025-06-05-recent-reward-hacking] Hence the test-integrity detector in B.6.
- **Gate result is an exit code, not a sentence.** The sample repo pushed a red build twice because a push was chained with `;` after an unchecked gate; its fix: the gate writes `exit N` to a log and the next step is chained with `&&` after `grep -qx 'exit 0'`. [sample-repo, docs/lessons/2026-11-05-push-only-on-a-green-exit.md] This goes into the Brain as a script, not a rule.

#### B.1.5 Evidence-linked "done" and honest reporting

- Fable guidance: "Before reporting progress, audit each claim against a tool result from this session. Only report work you can point to evidence for; if something is not yet verified, say so explicitly. Report outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that". In Anthropic's testing this "nearly eliminated fabricated status reports on tasks designed to elicit them". [local-doc, Fable 5.1 → Ground progress claims on long runs] This is the one verification sentence worth keeping in the Brain's core prompt.
- Fable 5.2 "closing summary often left out small changes, so review the diff, not only the summary". [local-doc, Fable 5.2 → Say who owns the code] So the delivery report is generated from `git diff --stat` and the ledger, not written from recollection. [inference]
- Scope: "If you conclude the ask is mistaken or a better approach exists, say so in a sentence and keep going with the task as asked - don't quietly narrow, widen, or transform it … only report completion when it's fully done. If you genuinely can't complete something, do the rest and state plainly what's missing." [local-doc, Opus 5 → Task scope expansion]
- Three report states only: **verified** (evidence id), **done, not verified** (reason), **not done** (reason). No fourth vague state. [inference]

#### B.1.6 Verification by model and effort level [local-doc unless tagged]

| Model / effort | Documented behaviour | Quality-system consequence |
|---|---|---|
| Fable 5.2 `low` | Scores "sat close to Claude Fable 5.1's at higher levels"; suited to "fast, intelligent subagents"; "more likely to stop early at lower levels" | Use for mechanical checkers, extraction, claim–source matching. Add the finish-the-whole-task text for agentic work at `low`/`medium`. |
| Fable 5.2 `medium` | "interactive coding, chat, and everyday knowledge work" | Default for trivial and many standard tasks. |
| Fable 5.2 `high` (default) | "Most of the capability gain arrives by high"; thinks before almost every reply | Default for standard-tier authoring and all planning. |
| Fable 5.2 `xhigh` | "raised scores slightly … and used many more tokens"; at `xhigh`/`max` it "used subagents to review its own work" unprompted | Only for one-way-door work with a measured gain. Do not also add a prompted reviewer on top of its unprompted one without checking for duplication. [inference] |
| Fable 5.2 `max` | For "measuring the model's ceiling" | Not part of normal operation. |
| Opus 5.5 `medium` (default) | Matches or beats Opus 5 at `high` with about half the tokens on multistep coding; "catches more bugs with fewer false alarms"; more detail-oriented on large inputs "without more false-positive flags" | A strong, cheaper independent reviewer and document/data auditor. |
| Opus 5.5 any effort | Reads charts more accurately at `low` than Opus 5 at highest effort | Screenshot and chart verification can run at low effort. |
| Either | Effort "barely changes how long replies are" (Fable 5.2); effort changes "how many tool calls it makes" | Control length in the prompt; control verification depth with effort. |

Other quality-relevant findings:
- Removing a token budget shown to the model "lowered cost at equivalent performance" on Fable 5.2: do not print budgets into prompts; enforce them in the harness.
- "Treat that answer as done" lines make Fable 5.2 "far less likely to point out mistakes in its earlier answers": never include them.
- Cautious notes accumulate and are obeyed: one stale "never retry" note cut retries from nearly all to about four in ten; reviewer conditions such as "stop at the first error" suppress work. The Brain's lessons store therefore needs expiry and pruning, and reviewer output must be findings, not standing orders.
- Hard style rules are "followed closely enough to make prose choppy": style guidance should be few and named, not numeric.
- The Claude Code docs describe effort the same way: raise it "when getting it right depends on cases that are quick to overlook … Claude then checks more edge cases and verifies more of its work". [source: https://code.claude.com/docs/en/best-practices]

### B.2 Attention to detail

#### B.2.1 Requirements ledger (the central artefact)

Every sentence of a request becomes one or more rows; every row has an acceptance check before work starts and evidence at the end. This is the direct answer to "extract everything I said in full detail". It also defeats the two most common silent failures (partial coverage and silent scope cuts), because the closing gate is a mechanical count of rows without evidence. [inference] The sample repo's `docs/IDEA_COVERAGE.md` (500 ideas → status → ticket) is the same idea at product scale. [sample-repo, CLAUDE.md §9]

File: `<project>/.brain/ledger/<task-id>.md` (project repo, not the Brain). Format: a Markdown table the owner can read, parsed by a 40-line script.

```
# Ledger T-0142 — "Add offline map download"      tier: standard      contract: brain-v1
Request (verbatim, hash 9f2c…): "Let me download a region for offline use, show how big it is first, and don't break the existing map."

| id | quote (exact words) | type | acceptance check (written before work) | status | evidence |
|----|---------------------|------|-----------------------------------------|--------|----------|
| R1 | "download a region for offline use" | req | e2e `offline-region.spec` passes with network disabled | verified | ev/T-0142/e2e.log#L88 exit 0 |
| R2 | "show how big it is first" | req | size shown before confirm; unit test on estimator ±10% of actual on 3 fixtures | verified | ev/T-0142/unit.log; shot-03.png |
| R3 | "don't break the existing map" | constraint | full map e2e suite green; visual diff of map screen = 0 px | verified | ev/T-0142/gate.log exit 0 |
| R4 | (implied) cancel and resume download | implied | ASSUMED in scope; test cancels at 50% and resumes | verified | ev/T-0142/unit.log |
| R5 | (ambiguous) "region" = drawn box or named place? | ambiguity | ASSUMED drawn box; recorded in DECISIONS | n/a | DECISIONS.md#T-0142 |
```

Rules:
- `quote` must be a substring of the stored verbatim request, or start with `(implied)` / `(ambiguous)`. The script checks this, which blocks invented requirements. [inference]
- Coverage check: every sentence of the request (split deterministically) must be referenced by at least one row. Uncovered sentences are listed and block the start. [inference]
- `status` ∈ `verified | done-unverified | not-done | descoped(owner-visible reason)`. `descoped` rows are copied to the delivery report automatically. [inference]
- Extraction is done once by the author and, from the high-stakes tier up, once more by a fresh-context cheap model; the union is kept. Ten analysts are needed only for a request like this one. [inference]
- Cost: one table, roughly 30–60 tokens per row; it replaces re-reading the request during the task. [inference]

#### B.2.2 Checklists: design rules and the two pause points

Rules taken from the checklist literature [source: https://www.stevegrossi.com/on/the-checklist-manifesto] [source: https://news.harvard.edu/gazette/story/2009/01/surgical-safety-checklist-drops-deaths-and-complications-by-more-than-one-third/] and adapted [inference]:
- Placed at natural pause points only: **before starting** (pre-flight) and **before delivering** (pre-delivery). A third, **before an irreversible action**, exists only in the one-way-door tier.
- DO-CONFIRM for routine expert work (the model works freely, then confirms). READ-DO only for rare, dangerous procedures (data migration, release to `main`, deletion).
- Seven items or fewer; only "killer items" that are both easy to miss and costly. Anything a script can check is removed from the checklist and moved to a hook.
- A checklist item that has not caught anything in 50 tasks is deleted (measured in the failure log). [inference]

`quality/checklists/preflight.md` (DO-CONFIRM, all tiers above trivial):
```
1. Ledger exists; every request sentence is covered; ambiguities listed with the assumption taken.
2. Tier set (trivial / standard / high-stakes / one-way-door) and the reason in one line.
3. Deliverable type named; its definition-of-done file loaded (only that one).
4. The verifier for each row is named and is executable where one can exist.
5. Pinned docs located for every external API this task will touch.
6. Anything irreversible in scope? If yes → one-way-door tier.
```
`quality/checklists/predelivery.md` (DO-CONFIRM):
```
1. Ledger script: 0 rows without evidence; descoped rows listed in the report.
2. Gate log ends with "exit 0", produced after the last edit (timestamp check).
3. Diff reviewed against ledger: no file changed that no row explains.
4. Type-specific definition of done: every line ticked with an evidence id.
5. Report written from the diff and ledger; states verified / unverified / not done.
6. The owner's next action, if any, is a file to read or a link to click.
```

#### B.2.3 Mistake-proofing (poka-yoke) with hooks and linters

Deterministic enforcement, kept deliberately small (target: under ten hooks in the Brain) per the Claude Code guidance above. Hook events used by the sample repo: PreToolUse (path protection), Stop (checkpoint reminder), SubagentStop (cost meter), SessionStart. [sample-repo, .claude/settings.json]

| Hook | Event | What it does | Blocks? |
|---|---|---|---|
| `stop-gate.sh` | Stop | Runs the project's gate command if files changed since the last green log; exit 2 returns the output to the model. Mirrors the documented Stop-hook pattern. [source: https://code.claude.com/docs/en/best-practices] | yes |
| `ledger-check.py` | Stop | Fails if the active ledger has rows without evidence and the final message claims completion. | yes |
| `test-integrity.sh` | PreToolUse on Edit/Write of test files, and in the gate | Flags deleted tests, added `.skip`/`.only`/`xfail`, loosened assertions, edits to snapshot files without a ledger reason. | yes for skip/only/delete |
| `stub-scan.sh` | gate | `rg` for `TODO|FIXME|NotImplemented|placeholder|lorem ipsum|return null // stub|mock` in non-test source added by this diff. | yes |
| `protect-paths.sh` | PreToolUse | Brain core is read-only during project work; project paths outside the task's declared scope need a ledger row. [sample-repo pattern] | yes |
| `dep-exists.py` | gate | Every new dependency/import resolves in the lockfile and registry. | yes |
| `link-check` | gate (docs) | `lychee` over changed Markdown/HTML. | yes |
| `format/lint` | PostToolUse | Formatter and linter on the edited file. | fixes silently |

Note the documented limit: a Stop hook that blocks eight times in a row with no tool call between is overridden. [source: https://code.claude.com/docs/en/best-practices] The gate must therefore return actionable output, and a ninth failure must be recorded as a not-done row, not papered over. [inference]

#### B.2.4 Visual, link, language and edge-case checks

- **UI: look at it.** Claude Code guidance lists "a browser screenshot next to the mockup" as a check and `/verify` to "build and run the app and look at the result. That catches the kind of problem that tests and typechecks miss." [source: https://code.claude.com/docs/en/best-practices] Opus 5 guidance: "give it tools to iteratively analyze, crop, and visually verify its own work … markedly more cost-effective … than raising thinking alone"; Opus 5.5 reads screenshots accurately even at `low`. [local-doc] Standard capture matrix for a screen: 2 widths (phone 390, desktop 1440) × light/dark × the states the spec lists (empty, loading, error, long text). Screenshots are produced by a Playwright script, compared with a pixel diff against the last accepted version, and only changed ones are shown to a model. [inference] The sample repo's critic scores a missing state as 0 rather than asking, which makes omissions visible. [sample-repo, design-critic.md]
- **Links and references**: deterministic link check on every document deliverable; internal anchors included. The sample repo requires "no broken links" in its done definition. [sample-repo, CLAUDE.md §2]
- **Spelling and locale**: spell check with a project word list (`cspell`), one language per file declared in front matter; for translated content, a key-parity check between string tables, placeholder parity (`{name}` present in every locale), number/date/currency format by locale, and length overflow check in the UI by screenshot. A fresh-context native-register reviewer reads the target text without the source first (naturalness), then with the source (fidelity). [inference] Literary translation is one of the two cases Anthropic names where an evaluator loop adds value. [source: https://www.ainews.com/p/anthropic-shares-detailed-best-practices-for-building-effective-ai-agents]
- **Edge-case enumeration**: one fixed prompt list by input type, used when writing acceptance checks, not as a separate pass: empty, one, many, maximum, duplicate, out-of-order, Unicode and right-to-left, time zones and daylight-saving boundaries, offline or timeout, permission denied, concurrent edit, interrupted midway, repeated run. Each chosen case becomes a ledger row or a property test; unchosen ones are not written down. [inference]

### B.3 Creativity (and when not to pay for it)

#### B.3.1 What the evidence supports

- **The default output is the mode.** Anthropic's own prompt: "You tend to converge toward generic, 'on distribution' outputs. In frontend design, this creates what users call the 'AI slop' aesthetic", with named defaults: Inter/Roboto/Arial/system fonts, "purple gradients on white backgrounds", "predictable layouts". [source: https://platform.claude.com/cookbook/coding-prompting-for-frontend-aesthetics] LLM responses are more similar to each other than human responses are, even when each one is rated as creative as a typical human's (secondary). [source: https://www.eurekalert.org/news-releases/1120796]
- **Naming the specific defaults to avoid works; "avoid a generic AI look" does not.** Opus 5.5: a general instruction "mostly swaps one default for another. It responds well to instructions that name specific patterns to avoid. Work iteratively - look at which styles the first result used instead, and extend the list" (example list: cream background, italic accent words, "01/02/03" labels, monospace labels, pill buttons). [local-doc, Opus 5.5 → Frontend design defaults] This implies a living **slop list** per medium that the learning loop extends.
- **Temperature is a weak lever** (and on current models non-default sampling parameters are rejected). Peeperkorn et al. find only a weak link between temperature and novelty, with a coherence cost. [source: https://arxiv.org/pdf/2405.00492] [local-doc, sampling parameters sections]
- **Ask for a distribution, not an instance.** Verbalized Sampling ("give five responses with their probabilities") recovers diversity lost to mode collapse, works better on more capable models, and is reported not to reduce factual accuracy. [source: https://arxiv.org/abs/2510.01171] It costs one call, not N.
- **Structured multi-step ideation raises diversity.** In "Prompting Diverse Ideas", chain-of-thought prompting gave the most diverse idea pool of the prompts tested, close to human groups; personas helped a little; generic creativity-technique prompts helped less. [source: https://papers.ssrn.com/abstract=4708466] A 2026 preprint found mixing ideas across different models came closest to human-level diversity. [source: https://arxiv.org/pdf/2607.27553]
- **Analogical prompting** (the model first recalls related problems, then solves) beat zero-shot and manual few-shot chain-of-thought on reasoning tasks. [source: https://arxiv.org/html/2310.01714v1] Its use for originality is my extrapolation. [inference]
- **Many candidates only pay if a selector exists.** Repeated sampling raised SWE-bench Lite coverage from 15.9% to 56% at 250 samples, but selection by voting plateaus; "a strong verifier is needed". [source: https://arxiv.org/html/2407.21787v1] For creative work the selector is a blind critic with a rubric, or a pairwise tournament. [inference]
- **Evaluator–optimizer loops** are worth it "when there are clear evaluation criteria, and when iterative refinement provides measurable value". [source: https://www.ainews.com/p/anthropic-shares-detailed-best-practices-for-building-effective-ai-agents]

#### B.3.2 The cheap creative protocol ("sketch wide, build one") [inference, assembled from the above]

1. **Brief** (author, ~150 tokens): audience, the one feeling or job the piece must achieve, hard constraints from the ledger, and the slop list for this medium.
2. **Diverge** (one call, verbalized-sampling form): "Give 5 directions, each ≤ 40 words, each built on a different organising idea; include your estimate of how typical each is; at least two must be ones you rate below 10% typical." Vary by constraint, not by adjective: a different reference world (for example a railway timetable, a field notebook, a museum label), a different structural rule, a different audience stance. About 300 output tokens for five candidates.
3. **Optional second source** for high-stakes creative work: the same prompt to the other model (Fable ↔ Opus) and merge the lists, since cross-model pools are more diverse.
4. **Converge** (fresh context, cheap or mid model, blind): score each sketch against a four-line rubric: fits the brief (pass/fail), violates the slop list (pass/fail), distinct from the obvious answer (0–2), feasible within constraints (pass/fail). Pick one; optionally graft one named element from the runner-up.
5. **Expand only the winner.** Full effort goes to one build.
6. **Accuracy firewall**: divergence may change form, framing, structure, metaphor, visual language. It may not change facts, numbers, API behaviour, legal or medical content. Facts come from the ledger and sources and are verified after expansion exactly as in B.1.
7. **Blind critique** of the finished piece once, with the type's rubric (B.4.4).

Cost: steps 2 and 4 together are roughly 1–2k tokens, against five full drafts at perhaps 10–50k each. [inference]

Reference board: for design and long-form writing, the project keeps `refs/board.md` with 3–6 named references and what is taken from each (one line), plus the "do not" list. The sample repo's `reproduce-effect` skill (learn an effect from an open-licensed reference, measure fidelity, save a cookbook card) is the same idea and should carry over as the way visual vocabulary accumulates. [sample-repo, skill listing]

Prose slop list (seed; the learning loop extends it): stock openers and closers, rule-of-three padding, "not just X but Y", em-dash chains, hedging stacks, headers on a short answer, summary restating the body, emoji bullets. Detector: a regex list with a per-1,000-words threshold, run on prose deliverables. [inference] Opus 5.5 already shows "fewer stock phrases". [local-doc]

#### B.3.3 When not to spend on creativity [inference]

Creative divergence is off by default and switched on by deliverable type and tier:
- Off: bug fixes, refactors, data analysis results, factual answers, migrations, configuration, anything where the right output is determined by the input.
- Off: when a design system or house style already decides the form (the creative work was done once; follow it).
- On, light (one diverge call): naming, microcopy, document structure, the first screen of a new feature, chart choice for a key figure.
- On, full protocol: new product concept, visual identity, landing page, long-form writing with a voice, anything the owner will show to other people.
Creativity in engineering means choosing an approach, and is handled by the plan step (two or three approaches in a few lines each, pick one, record why), not by building variants.

### B.4 Cost-aware review architecture

#### B.4.1 Risk tiers

Tier is set at pre-flight by rule, not mood: reversibility, blast radius, whether an executable verifier exists, and whether the owner or outsiders will rely on it unchecked. [inference; model and effort choices follow B.1.6]

| | T0 trivial | T1 standard | T2 high-stakes | T3 one-way door |
|---|---|---|---|---|
| Examples | typo, rename, one-line config, quick factual answer | feature, bug fix, memo, analysis, screen | release to `main`, data model, public content, money/legal/health facts, security-relevant code | delete or migrate data, publish irreversibly, spend money, send to people, change the Brain's own rules |
| Ledger | none (the request is the ledger) | yes | yes, plus second extraction by a fresh cheap model | yes, plus owner-visible decision record |
| Author | Fable 5.2 `low`/`medium` or cheaper tier | Fable 5.2 `high` (or Opus 5.5 `medium`) | Fable 5.2 `high` | Fable 5.2 `high`; `xhigh` only with a measured gain |
| Deterministic gate | formatter/lint | full gate | full gate + property/differential tests | full gate + rehearsal on a copy + backup verified by restore |
| Independent review | none | none if an executable verifier covers every ledger row; otherwise 1 fresh-context reviewer at low/medium effort | 1 fresh-context reviewer on the other model, report-everything-then-filter | reviewer as T2 + 1 adversarial red-team pass + pre-mortem |
| Max critic rounds | 0 | 1 | 2 | 2, then escalate to the owner file |
| Creative protocol | off | light, if the type calls for it | full, if the type calls for it | n/a |
| Evidence in report | one line | ledger evidence ids | ledger + reviewer verdict file | ledger + red-team file + rollback steps |
| Rough overhead vs. just doing it | ~0% | ~5–15% | ~30–60% | ~100%+ |

Overhead figures are my estimates for planning and must be replaced by measurements from the cost meter. [inference] Escalation is one-directional during a task: a task may be raised a tier when a surprise appears (a failing property test, a reviewer must-fix, an unexpected irreversible step), never silently lowered. [inference]

The key economy: at T1, **a complete executable verifier replaces the reviewer**. A model reviewer is only bought for what cannot be executed (design, prose, judgement, requirements fit). [inference from B.0.1 and B.0.6]

#### B.4.2 Stop rules for critic loops [inference, grounded in B.0.5 and the equal-budget results in B.0.1]

Stop the review loop at the first of:
1. Zero must-fix findings and the rubric threshold met.
2. Round cap for the tier reached (1 or 2). Unresolved items go into the report as known limitations; they are not hidden.
3. A round yields only should-fix or style findings.
4. A finding repeats one that was already rejected with a recorded reason.
5. The fix for a finding would add code or content that no ledger row asks for (that is scope creep, and is refused or logged as a new request).
Also: one review per version, never per edit, with nits batched. [sample-repo, design-critic.md] After a must-fix, re-review covers only the changed region plus a regression check of the "keep" list.

If a deliverable fails twice, the cheaper move is usually to regenerate from an improved brief than to patch a third time, since repeated sampling matches or beats reflective patching at equal cost in the available evidence (small-model preprint; treat as a hypothesis to test in the Brain's own evals). [source: https://arxiv.org/pdf/2607.28576]

#### B.4.3 Blind review rules

1. Fresh context: the reviewer receives the artefact, the ledger (requirements and acceptance checks), the rubric and the relevant standard. It does not receive the author's reasoning, conversation, self-assessment or name. [source: https://code.claude.com/docs/en/best-practices] [sample-repo]
2. Different model from the author where the tier pays for it. [source: https://arxiv.org/abs/2404.13076]
3. Read-only tools: "a reviewer that can read but not edit … enforced by Claude Code rather than requested in a prompt". [source: https://code.claude.com/docs/en/best-practices]
4. The reviewer reports everything with severity and confidence; a deterministic filter applies the bar (must-fix = violates a ledger row, a standard, or correctness). [local-doc, code-review guidance]
5. Every deduction cites the ledger row or the standard it violates and names the fix: "no deduction for taste alone". [sample-repo, design-critic.md]
6. The reviewer states what must be kept, so fixes do not regress strengths. [sample-repo]
7. Missing evidence scores zero; the reviewer does not ask the author. [sample-repo]
8. The reviewer's output is findings on this artefact. It may not issue standing instructions, because carried-over reviewer conditions suppress later work. [local-doc, Fable 5.2 → Keep caution from piling up]

#### B.4.4 Rubric design

- Binary, observable criteria, each with a "passes when …" anchor and the evidence required; 6–10 criteria; one point each; no half points. This is the sample repo's design-critic rubric shape and it avoids the position bias of option lists. [sample-repo] [source: https://arxiv.org/abs/2602.02219]
- Critique first, verdict second (reasoning before the score). [source: https://simonwillison.net/2024/Oct/30/llm-as-a-judge]
- Any must-fix blocks regardless of total. [sample-repo]
- Reliability target: a second reviewer run lands within ±1 point. [sample-repo] Check this on a sample (for example 1 in 20 reviews), not on every review. [inference]
- Each rubric ships with 3–5 calibration cases: one clear pass, one clear fail, and seeded-defect cases. The reviewer prompt is only changed when it still catches the seeds. [inference]

`quality/rubrics/research-memo.yaml` (example):
```yaml
id: research-memo   version: 1   threshold: 7/8   must_fix_blocks: true
criteria:
  - id: answers      passes_when: "First 5 lines state the answer to the question asked, with confidence."
  - id: coverage     passes_when: "Every ledger row maps to a section; none missing."
  - id: sourced      passes_when: "Every factual claim has a tag; citation check log shows 0 unsupported."
  - id: primary      passes_when: "Key claims rest on primary/official sources; secondary ones are flagged."
  - id: numbers      passes_when: "Each number matches its quoted source span or its recomputation script."
  - id: counter      passes_when: "Strongest contrary evidence is stated, not buried."
  - id: uncertainty  passes_when: "Unknowns and unverified items are listed explicitly."
  - id: usable       passes_when: "A decision or next step follows; reader needs no other file."
calibration: [cases/memo-pass-01.md, cases/memo-fail-fabricated-cite.md, cases/memo-fail-missing-row.md]
```

#### B.4.5 Adversarial red-team for one-way doors [inference]

One fresh-context agent on the stronger setting, with one job: "Assume this went wrong three months from now. Give the five most likely causes, the evidence that would show each now, and the cheapest test for each." (pre-mortem form). It gets the plan, the ledger and the rollback steps. Output is a file with testable items; each item is either tested (evidence id) or accepted as a named risk in the owner-visible decision record. The red team is forbidden from proposing redesigns; it finds failure modes. Plus a READ-DO checklist for the irreversible step: backup exists; restore of that backup verified; dry run output read; exit code checked; rollback command written down. The sample repo's "Never lose data, ever … No destructive migration without a backup step" is the origin. [sample-repo, CLAUDE.md §1.2]

#### B.4.6 Preventing rubber stamps and orchestration theatre [inference unless tagged]

- **Seeded defects**: periodically (for example 1 review in 20) the harness plants a known defect; a reviewer that passes it is recalibrated. This is the only direct measure of reviewer recall.
- **Pass-rate monitor**: a reviewer that passes more than ~95% over 30 reviews with no must-fix is either unnecessary for that task type (drop it and save the tokens) or blind (check with seeds). Both outcomes are improvements.
- **Finding yield**: track must-fix findings later confirmed (by a failing test, an accepted fix, or the owner) per 1,000 reviewer tokens, by task type. Reviews with persistently zero yield are removed from that type's tier recipe.
- **Role count is not quality.** The sample repo polices "role sprawl … self-review … orchestration theatre" and meters agent cost with hooks. [sample-repo, CLAUDE.md §8; .claude/settings.json payroll hooks] The Brain should carry a rule that a new reviewer role needs a measured catch that no existing check makes.
- **Delegation costs are real**: "each subagent re-establishes context, re-explores, reports back, and then the coordinator re-reads the report"; a subagent is "the same model (or a smaller one) on the same task … a fresh pair of eyes … but not a smarter answer". [local-doc, Opus 5 → Delegates to subagents] [source: https://code.claude.com/docs/en/best-practices]
- **Evidence or it did not happen**: a review verdict without cited rows and evidence ids is rejected by script.

### B.5 Definition-of-done templates

One file per deliverable type in `quality/dod/`, each ≤ 12 lines, DO-CONFIRM, loaded only when that type is in play. Every line ends in an evidence slot. Project repos may add lines in `.brain/dod-overrides/<type>.md`; they may not remove Brain lines without a logged decision. [inference; items drawn from the sources above and the sample repo's Definition of Done]

**`code-change.md`**
```
[ ] Bug: failing test reproduced it first (red log) → now green (green log).
[ ] Each ledger row has a test or executable check.                         ev:
[ ] Full gate (lint, types, tests, build) exit 0 after the last edit.       ev:
[ ] No test deleted/skipped/weakened without a ledger reason (integrity log). ev:
[ ] No stubs/TODOs in shipped paths (stub-scan log).                         ev:
[ ] New APIs/deps checked against pinned docs; all resolve.                  ev:
[ ] Diff contains only files a ledger row explains.                          ev:
[ ] Report lists behaviour changes, including small ones, from the diff.
```
**`new-app-or-feature.md`** = code-change plus:
```
[ ] Runs from a clean clone with the one documented command.                 ev:
[ ] End-to-end test of the main user journey, plus empty/error/offline states. ev:
[ ] Invariant tests (round-trip / idempotence / oracle) where data is stored or transformed. ev:
[ ] Budgets met (bundle size, load time or the project's own).               ev:
[ ] Data safety: migration has backup + restore test; nothing destructive unrehearsed. ev:
[ ] User-facing doc updated; links checked.                                  ev:
[ ] Owner can see it: preview link or screenshots in the report.
```
**`ui-screen.md`**
```
[ ] Screenshot matrix captured: phone + desktop × light + dark × listed states. ev:
[ ] Matches design tokens; design lint 0 hard-coded colours/spacing.          ev:
[ ] Accessibility: automated audit 0 serious; contrast ≥ 4.5:1 body; focus order; targets ≥ 44 pt. ev:
[ ] Long text, large text and the other UI languages do not break layout.     ev:
[ ] Motion respects reduce-motion; no layout shift on load.                   ev:
[ ] Slop list for UI: 0 hits (or each justified).                             ev:
[ ] Blind critic score ≥ threshold, no must-fix (critique file).              ev:
```
**`research-memo.md`**
```
[ ] The question, as asked, is answered in the first 5 lines with confidence level.
[ ] Every claim tagged source / file / computed / inference (tag lint).       ev:
[ ] Links resolve; each claim–source pair checked "supported" by a fresh checker. ev:
[ ] Numbers match the quoted span or the script output.                       ev:
[ ] Primary sources for key claims; secondary flagged; dates of sources given.
[ ] Contrary evidence and unknowns stated.
[ ] Search scope recorded: what was searched, what could not be accessed.
```
**`plan-or-strategy.md`**
```
[ ] Every ledger row maps to a plan section (coverage table).                 ev:
[ ] Each phase has an exit test that is observable, and an owner of the check.
[ ] Assumptions listed and marked; each decision has alternatives considered in ≤ 2 lines.
[ ] Risks: pre-mortem top 5 with mitigations; irreversible steps flagged.
[ ] Impossible or unverifiable asks reframed in plain words, up front.
[ ] Estimates carry a basis (measured / analogous / guess).
[ ] First executable step is unambiguous; nothing depends on an unstated decision.
```
**`data-analysis.md`**
```
[ ] One script reproduces every number and chart from raw input (run log).   ev:
[ ] Input checks: row counts, date ranges, duplicates, nulls, units stated.   ev:
[ ] Totals reconcile to an independent figure or a second computation path.   ev:
[ ] Each headline number recomputed a different way (pivot vs. loop, SQL vs. dataframe). ev:
[ ] Charts rendered and looked at; axes, units, baselines, labels correct.    ev:
[ ] Claims do not exceed the data (correlation vs. cause; sample size shown).
[ ] Method, exclusions and limits written down.
```
**`written-or-translated-content.md`**
```
[ ] Brief met: audience, purpose, length, voice (ledger rows).               ev:
[ ] Facts, names, dates, numbers verified against sources.                    ev:
[ ] Spell/grammar check in the declared language and locale; project word list. ev:
[ ] Prose slop list under threshold; house style followed.                    ev:
[ ] Translation: no omissions/additions (segment count parity); placeholders, numbers, dates, units localised. ev:
[ ] Translation: read once without the source for naturalness, once against it for fidelity (fresh reviewer). ev:
[ ] Terminology matches the glossary; names not translated unless listed.     ev:
```
**`automation-or-scheduled-job.md`**
```
[ ] Dry run output read; real run on a safe target succeeded (logs).          ev:
[ ] Idempotent: second run changes nothing (log).                             ev:
[ ] Failure path tested: bad input, timeout, missing credential → clear error, no partial damage. ev:
[ ] Exit codes checked between steps (&&, never ;).                           ev:
[ ] Schedule, time zone and next three run times stated.
[ ] Observability: where the owner sees success/failure without a shell.
[ ] Off switch and rollback documented; secrets not in files.                 ev:
```
**`answer-to-a-question.md`** (T0 by default)
```
[ ] Answers the question asked, first sentence.
[ ] Anything checkable was checked (file read, command run, source fetched), not recalled. ev:
[ ] Facts about versions, prices, limits, APIs come from a current source, cited.
[ ] Uncertainty stated once, plainly; no padding.
[ ] If the question implies a decision, a recommendation is given.
```

### B.6 Failure taxonomy: false "done" and a cheap detector for each

All detectors are deterministic unless marked (LLM). [inference unless tagged; motivating evidence cited]

| # | False success | Detector | Cost |
|---|---|---|---|
| 1 | Tests not run, or run before the last edit | Gate log must exist, end in `exit 0`, and be newer than the newest changed file; the log's commit hash equals HEAD. [sample-repo lesson] | script |
| 2 | Gate failed but the next step ran anyway | Steps chained only through `gate.sh` which propagates exit codes; push/deploy wrappers `grep -qx 'exit 0'`. [sample-repo lesson] | script |
| 3 | Tests skipped, deleted or weakened | Diff scan for `.skip/.only/xfail/@Ignore`, removed test files, reduced assertion count, changed snapshots; compare test count and names before/after. [source: https://metr.org/blog/2025-06-05-recent-reward-hacking] | script |
| 4 | Implementation special-cases the tests | Hidden hold-out tests or property tests written from the ledger by a separate agent; grep for test fixture literals in source. [source: https://icml.cc/virtual/2026/77983] | script + small (LLM) once |
| 5 | Stubbed or fake implementation | `stub-scan` on added lines; coverage of new lines > 0; e2e exercises the path with mocks disabled. The sample repo bans "Fake implementations, TODO stubs and skipped tests". [sample-repo, CLAUDE.md §1.7] | script |
| 6 | Hallucinated API or package | `dep-exists`; typecheck/build; import resolution against the lockfile. [source: https://www.darkreading.com/application-security/ai-code-tools-widely-hallucinate-packages] | script |
| 7 | Hallucinated citation | URL/DOI resolution; then claim–source support check by a fresh cheap model quoting the span. [source: https://arxiv.org/pdf/2406.14765] | script + (LLM) low |
| 8 | Number does not match source or data | String match of each number against the quoted span or script output. | script |
| 9 | Partial requirement coverage | Ledger script: rows without evidence; request sentences without rows. | script |
| 10 | Silent scope cut | `descoped` rows must appear in the report; report generator copies them. Prompt line from Opus 5 guidance ("don't quietly narrow, widen, or transform it"). [local-doc] | script |
| 11 | Silent scope growth | Changed files not explained by any ledger row; Fable 5.2 "made changes nobody asked for" when told it owns the code and "its closing summary often left out small changes". [local-doc] | script |
| 12 | "Done" with work remaining | Stop hook scans the final message for intent phrases ("I'll", "next I would", "remaining:", "want me to") while ledger rows are open. Guidance: "Before ending your turn, check your last paragraph…". [local-doc, Fable 5.1 → early stopping; Fable 5.2 → Finish the whole task] | script |
| 13 | Fabricated progress report | Each claim in the report must carry an evidence id that exists on disk; the audit sentence from Fable guidance in the core prompt. [local-doc] | script |
| 14 | UI "works" but was never seen | Screenshot files for the matrix must exist and be newer than the last UI edit; pixel diff non-empty for changed screens. | script |
| 15 | Passed once, flaky | High-stakes tier reruns the changed tests 3×; Opus 4.8+ is noted as better at "identifying intermittent flakes rather than declaring 'fixed' after one clean run". [local-doc] | script |
| 16 | Works on my machine | Clean-clone build in a temp directory. [sample-repo, CLAUDE.md §11] | script |
| 17 | Rubber-stamp review | Seeded defects; verdict must cite rows; pass-rate monitor (B.4.6). | script + sampling |
| 18 | Translation omission | Segment and placeholder parity; number parity between source and target. | script |
| 19 | Broken links or anchors | `lychee`. | script |
| 20 | Stale or wrong "latest" facts | Any claim about versions, prices or model names must cite a source fetched in this session; the date is printed next to it. | script (tag lint) |
| 21 | Reviewer or lesson rules silently throttling work | Lessons carry an expiry and a scope; a monthly prune; "never" rules must state their exception. [local-doc, Fable 5.2 → Keep caution from piling up] | script + review |

Every detector hit is appended to `quality/failures.jsonl` in the Brain (`{date, project, task, tier, failure_id, caught_by, stage, cost_tokens}`), which is the training data for the Brain's "machine learning": which detectors earn their place, which task types need a higher default tier, which checklist items never fire. [inference]

### B.7 Concrete artefacts for the Brain

```
Claude-Brain/
  CLAUDE.md                      # core, target ≤ 150 lines; quality section ≤ 15 lines (below)
  quality/
    QUALITY.md                   # the system on one page (≤ 60 lines); loaded on demand
    tiers.yaml                   # tier rules → model, effort, gates, reviewers, round caps
    dod/                         # 9 files above, ≤ 12 lines each
    rubrics/*.yaml               # binary anchored rubrics + calibration case paths
    rubrics/cases/               # pass / fail / seeded-defect examples
    checklists/preflight.md  predelivery.md  one-way-door.md
    slop/ui.txt  prose.txt       # named defaults to avoid; extended by the learning loop
    edge-cases.md                # the single enumeration list
    failures.jsonl               # detector hits and escapes (append-only)
    scorecard.md                 # generated: escapes, catch stage, tokens per task type
  scripts/quality/
    ledger.py                    # new | cover | check | report
    gate.sh                      # runs the project's gate, writes ev/<task>/gate.log with "exit N"
    test-integrity.sh  stub-scan.sh  dep-exists.py  cite-check.py  tag-lint.py  slop-lint.py  shots.mjs
  .claude/
    settings.json                # ≤ 10 hooks (B.2.3)
    agents/verifier.md           # read-only, fresh context, report-everything + severity/confidence
    agents/critic.md             # blind rubric critic (design, prose)
    agents/red-team.md           # pre-mortem, one-way doors only
    skills/quality-gate/SKILL.md # loads tier recipe + the one DoD file for the task
    skills/creative-sketch/SKILL.md
  evals/quality/                 # seeded-defect suites; ~20 cases per rubric to start
Project repo (contract):
  .brain/project.yaml            # gate command, default tier overrides, languages, budgets, contract version
  .brain/ledger/<task>.md        # requirements ledgers
  .brain/ev/<task>/              # evidence: logs, screenshots, critique files
  .brain/dod-overrides/          # project additions
  .brain/docs-pin.json           # pinned external docs
  refs/board.md                  # reference board, when design/writing is in scope
```

`tiers.yaml` (excerpt):
```yaml
T1:
  author: {model: claude-fable-5-2, effort: high}
  ledger: required
  gates: [full]
  review: {when: "any ledger row lacks an executable check", agent: verifier, model: claude-opus-5-5, effort: medium, max_rounds: 1}
  creative: by_type
T3:
  triggers: [deletes_data, migrates_data, publishes, spends_money, sends_external, edits_brain_rules]
  author: {model: claude-fable-5-2, effort: high}
  gates: [full, property, rehearsal_on_copy, backup_restore_verified]
  review: {agent: verifier, model: claude-opus-5-5, effort: high, max_rounds: 2}
  red_team: {agent: red-team, required: true}
  checklist: one-way-door.md   # READ-DO
```

Core prompt text for quality (the whole of it; everything else is files and hooks) [wording adapted from local-doc passages cited above]:
```
# Quality
- Work from the ledger: every sentence of the request has a row, an acceptance check and, at the end, evidence.
- Prefer a check you can run over an opinion. Use pinned docs for any external API; do not write one from memory.
- Deliver what was asked at the scope intended. If you think the ask is mistaken, say so in a sentence and continue. Do not quietly narrow, widen or transform it.
- Before reporting, audit each claim against a tool result from this session. Report each item as verified, done but not verified, or not done, with the reason.
- The tier in the ledger decides how much review to buy. Do not add reviewers or re-checks beyond it.
```
Note what is absent on purpose: no "double-check your work", no "be extremely careful", no "use a subagent to verify", no token budget, no "treat the answer as done" lines, each of which the model guidance identifies as harmful or wasteful on these models. [local-doc]

Verifier agent (excerpt of `.claude/agents/verifier.md`):
```
tools: Read, Grep, Glob, Bash(read-only gate commands)
You receive: the artefact or diff, the ledger, the DoD file, the rubric. You do not receive the author's notes.
Report every issue you find, including uncertain and low-severity ones, each with: ledger row or standard violated,
evidence (file:line or command output), severity (must-fix | should-fix | nit), confidence (0–1), the fix.
List what must be kept. Missing evidence for a row = must-fix. Do not give standing instructions.
```

### B.8 How this system learns (ties to "its own machine learning systems") [inference]

1. Every task writes its tier, tokens, detector hits and reviewer findings to `failures.jsonl` and the cost meter.
2. Every defect found after delivery (by the owner, CI on `main`, or a later task) is an **escape**: recorded with the stage that should have caught it. An escape creates either a new deterministic detector, a new seeded-defect case, or a DoD line; a prose rule is the last resort.
3. Monthly prune: checklist lines, hooks, reviewers and lessons with no catches are removed; lessons past expiry are deleted. This is how the system gets cheaper as well as better, and it guards against caution piling up.
4. Any change to the Brain's rules is itself a T3 task: run the seeded-defect evals before and after; adopt only if catches do not fall and tokens do not rise without a matching quality gain.
5. Metrics on `scorecard.md`: escapes per 100 tasks by type; share of defects caught by deterministic checks vs. model review; reviewer yield per 1,000 tokens; ledger rows delivered verified / unverified / not done; quality overhead as a share of task tokens.

### B.9 Open questions and limits of this report

- Several paper figures are from search summaries, not the primary PDFs (marked "secondary"). They support direction, not exact magnitudes; the plan should not quote them as precise.
- Whether a cross-model reviewer measurably beats a same-model fresh-context reviewer for Fable 5.2 and Opus 5.5 specifically is untested; the self-preference evidence is from earlier models. Run it as an early Brain eval.
- The "regenerate instead of patching after two failures" rule rests on a small-model preprint; test before fixing it into the tiers.
- Hook behaviour in cloud sessions with two repos attached (which repo's Stop hook fires, working directory, the eight-block cap) needs a hands-on check before the gate design is final.
- Overhead percentages in the tier table are estimates.
- I could not read the owner's past chats or memory; lessons here come from the sample repo and public sources only.
