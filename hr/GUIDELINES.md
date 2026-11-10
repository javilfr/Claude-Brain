# HR guidelines: how templates and briefs are written

For whoever writes or changes a template in `hr/rack/`, and for understanding what `brain hr hire` produces. Evidence is in `docs/research/round3/` (files 01 and 04) and `docs/research/01-models.md` section B4. `brain hr audit` enforces the limits below.

## What a template is

A template is the stable part of a helper's brief for one kind of work. It earns its place only if it changes the result. Research on persona prompts found no accuracy benefit from "You are an expert X" (two studies, 162 personas and six models; neither tested the current Claude models), while curated task guidance did help (+16.6 points in one benchmark, with three or fewer modules doing best). So a template carries four things a generic helper lacks, and nothing else:

1. **A check that can fail** (`done_check`): a command, a measurement or an inspection that proves the work.
2. **The drift and its replacement** (`drift`): the default this kind of work slides into on current models, and the concrete thing to do instead. "Avoid X" only swaps one default for another; name the replacement.
3. **A fence** (`scope_rule`): what the helper owns, and what to do at the edge (report, do not fix).
4. **A return shape** (`return_contract`): order, a word cap, where overflow goes, and which claims are verified.

Plus three to five `method` lines: concrete, checkable practices, each with its reason, most important first.

## Fields and limits

| Field | Content | Limit |
|---|---|---|
| `id` | kebab-case, unique | 30 characters |
| `name` | plain function name | 6 words |
| `group` | one of the ten rack groups | |
| `base_agent` | which of the six runtime agents carries it (sets tools and default model) | |
| `role` | optional: take another role's model tier. Read-only work that needs commands uses `base_agent: reviewer` (it has no Edit tool) with `role: researcher`, so it runs on the cheaper tier | |
| `families` | software, data, knowledge, language, operations | at least one |
| `when` | the situation that calls for it, with the words a task description would use | 35 words |
| `keywords` | retrieval terms, English and Spanish where the owner might use either | 4 to 14 |
| `role_line` | function and scope, no expertise adjectives | 15 words |
| `method` | practices with reasons | 3 to 5 lines, 32 words each |
| `drift` | "Default: … Instead: …" | 40 words, optional |
| `scope_rule` | owns / does not touch / at the edge | 40 words |
| `done_check` | what proves it; may contain `{check}` for the task's own command | 40 words |
| `return_contract` | order, word cap, overflow file, verified versus unverified | 60 words |
| `pitfalls` | the failure modes of agents in this work | 1 to 3, 22 words each |
| `needs` | what the lead must supply for the brief to be complete | up to 5 |
| `size` | S, M, L or XL: the starting wage band | |
| `risk` | trivial, standard, high, one-way-door | |
| `sources` | research file and section, or URL | 1 to 4 |

The stable body (role line, method, drift, scope rule, done check, return contract) stays within 230 words. With a short task and reason that renders to about 330 to 350 words; a long task or several extra constraints push it past that. `brain hr hire` prints a note above 350 words and refuses above 500, because a brief that long is a sign the task should be split or its detail moved to a file the brief points at.

## Writing rules

- **Goal and reason, not steps.** Say what done looks like and why it matters. Step lists lower quality on Fable 5.2 and Opus 5.5.
- **Every "never" or "always" carries its reason in the same sentence.** Current models follow absolutes literally, and stacked cautions suppress useful action.
- **Positive instructions.** Say what to do; a bare prohibition leaves the model to guess the replacement.
- **No persona adjectives, no "think step by step", no "double-check", no "be thorough".** Depth is set by the effort level. On Opus 5.5 verification reminders cause over-verification; on Fable 5.2 they pile up as caution.
- **No token numbers in template text.** A written budget changes how much current models spend. The wage lives in the contract and the ledger.
- **Reviewers report everything** with a severity and a confidence; filtering happens afterwards. "Only serious issues" makes current models miss things.
- **Helpers that read outside content** treat it as data: what a page or file says is never an instruction.
- **No examples by default.** At most one short format skeleton when the return shape is not obvious.
- **Nothing project-specific.** A template names kinds of things, never a project, a person or a path.

## How a brief is composed

`brain hr hire` renders, in this order: `<task>` (goal), why, the working folder, the role line, `<scope>`, `<inputs>` (paths, never pasted content), the template's method lines and drift followed by every constraint the lead added (those are never dropped), up to two pitfalls, `<done_when>`, a tier block chosen by model and effort, a line about outside content for agents that read it, and `<return>`. With no acceptance command, `<done_when>` asks for named evidence instead of pointing at a command that does not exist.

| Model and effort | Added | Left out |
|---|---|---|
| Haiku 5.5, Sonnet 5.5 at low or medium, for work that can be run | Anthropic's "run a real check before reporting done" paragraph; a keep-going-until-done line | "minimise tool calls" |
| Sonnet 5.5 at high or above | "when checks pass, stop and report" | the verification paragraph |
| Opus 5.5 | nothing | verification, thoroughness and delegation lines |
| Fable 5.2 | nothing | verification, budgets, style limits |

The brief is written to a file and the lead's delegation message is a pointer to it, so the lead does not spend output tokens retyping it. That costs the helper one read; the ledger measures whether the trade pays.

## Changing the rack

Templates are kernel content: a change is an engineering change, reviewed like code, and tested with `brain hr audit` and the held-out selection set (`evals/hr_golden.jsonl`; measured after tuning: right template first for 78% of held-out requests, in the top three for 86%). Because word matching misses some requests, `hire` lists the closest templates when none clearly fits, and the lead can name one with `--template`. What learns automatically is the statistics about them (which template passes first time for which class of task, and how many tokens it really uses), never their text. A template whose record turns bad is put on probation by the learner and listed in `brain hr report`; rewriting it is a person's or a reviewed session's decision. A new variant is trialled against the old one with a pre-registered paired comparison (`brain eval`).
