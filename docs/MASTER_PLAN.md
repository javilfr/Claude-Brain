# Claude Brain — Master Plan

Version 1.0 · written 2026-11-10 · for Javier · built from ten independent analyst reports in `docs/research/`

This is the full plan for the Claude Brain: a permanent repository that sits beside any project repository in a Claude Code chat and makes Claude build that project well, cheaply and fast, and that gets better with use. It is long on purpose. The parts are ordered so you can stop after Part 1 and still know what you are getting.

- **Part 1** — what you asked for, what you get, and four things I have to be straight with you about.
- **Part 2** — what the research found (models, platform, tokens, algorithms, the Travel Journal experience, your past chats).
- **Part 3** — the design: two repos, the contract between them, how a request flows.
- **Part 4** — the efficiency system.
- **Part 5** — the quality system (accuracy, attention to detail, creativity).
- **Part 6** — the learning system.
- **Part 7** — agents, skills, and how you use it from your phone.
- **Part 8** — the build plan, ticket by ticket, with acceptance tests.
- **Part 9** — how success is measured, risks, non-goals, and what needs you.

The requirement-by-requirement trace from your message to this plan and to evidence is in `docs/REQUIREMENTS.md`.

---

# Part 1 — What you asked for and what you get

## 1.1 Your request, restated

You used the Travel Journal company repo as a brain to build one product. You now want one brain for everything:

1. A repository that acts as a very capable orchestrator for anything you will need to build.
2. Always two repositories in a chat: the brain, and the project. They always work together, and a project built with the brain must keep working with it for good.
3. The project repo can hold its own files and tools that complement the brain for that project.
4. The brain is changed only by its own learning systems, as it learns from everything you use it for.
5. A very detailed plan, grounded in research on Claude Fable 5.2 and Claude Opus 5.5, in what the Travel Journal repo taught us, and in everything you have asked Claude to build before.
6. The most token-efficient and fastest Claude tool possible, through plugins, algorithms, "quantum logic" and anything else research turns up.
7. The highest quality: accuracy, creativity and extreme attention to detail.
8. Your prompt analysed by ten independent agents, then the plan, then the build, to completion.

## 1.2 What you get

- **A brain that costs almost nothing to carry.** The Travel Journal setup spent an estimated 35,000–50,000 tokens at the start of every session just getting oriented, plus about 6,000 tokens of always-loaded text. The brain's always-loaded text is capped at about 3,000 tokens for both repos together, and orientation is one script call that prints about 15 lines.
- **Process that scales with the request.** A quick question gets an answer and nothing else. A typo fix reads the files it touches. Only a real project gets a plan, a requirements ledger, reviewers and parallel agents.
- **A token ledger with real numbers.** Every session's actual token use, by model and by sub-agent, is read from the session's own records and logged. "More efficient" becomes a measured number per finished task, not a claim.
- **A requirements ledger.** Every sentence of a request becomes a numbered line with a check and, at the end, evidence. A script refuses to call work done while any line has no evidence.
- **A learning loop that actually runs.** At the end of each session a script records what happened. Lessons are accepted only when backed by a real outcome (a failed check, a correction from you), and are applied as small tracked edits that can be undone with one click.
- **One contract for every project.** A small `.brain/` folder in each project holds its state, plan, decisions and project-specific tools. It has a version number and migrations, with old versions tested on every change to the brain, so a project started today still opens correctly later.
- **Phone-first use.** One-line triggers ("Start running", "New project: …", "Status", "Hand over"). Everything you need to do is a file to read or a button to click.

## 1.3 Four things I have to be straight about

Ten analysts read your message independently and all ten flagged the same items. I would rather tell you now than build something that only sounds like what you asked for.

**1. "Quantum logic."** There is no quantum computer in a Claude session, and Claude itself runs on ordinary hardware. What is real is *quantum-inspired* optimisation: simulated annealing, the classical method that quantum annealers imitate. I tested where it helps. For choosing which knowledge to load, a simple greedy method already reaches 99.1% of the best possible answer, so annealing is not used there. For scheduling parallel work across agents, annealing cut wasted waiting from 4–7.5% above the best possible down to 0–2.3%. So the brain uses annealing in the scheduler, labels it honestly as quantum-inspired, and uses simpler exact methods everywhere they win.

**2. "Its own machine learning systems."** Claude's model weights cannot be trained from a repository. What can learn is the brain's contents: its playbooks, its memory, and its statistics about which model and effort level work best for which kind of task. That last part is genuine machine learning (an online method called Thompson sampling). The plan calls the whole thing a learning loop and makes it the only way the learned parts of the brain change.

**3. "All your memory and all our chats."** This session has no stored memory, and chats in the regular Claude app cannot be read from here. What could be read was your Claude Code cloud history: 120 sessions were listed, 55 started by you, and 52 of those were sampled. That covered 17 projects and gave 40 acceptance tests for the brain (Part 2.6). First messages of some long sessions are known only from titles, and two sessions were too large to open.

**4. "The most efficient ever", "perfectly", "forever".** Nobody can prove a superlative. The plan replaces each with something testable: tokens and minutes per finished task against the Travel Journal baseline; a requirements ledger with evidence; a versioned contract with old versions tested on every change.

One more point, because it goes against how the earlier builds were run. Your past instructions include "always at least 10 teams running". The evidence in your own history says that pattern is the main cost and reliability problem: 20 parallel agents hit the rate limit and produced nothing in one project, ten parallel agents exhausted the usage window three times in two days on the Travel Journal, and multi-agent runs use roughly 15 times the tokens of a single conversation. The brain defaults to at most four helpers at once, each one justified, and scales up only when the work is truly independent and you ask for it.

---

# Part 2 — What the research found

Ten analysts each extracted your requirements on their own and then went deep on one subject. Their full reports are in `docs/research/`. This part is the short version of what changed the design.

## 2.1 The two models (report 01)

| | Claude Fable 5.2 | Claude Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
|---|---|---|---|---|
| Price per million tokens, in / out | $8 / $40 | $4 / $20 | $2 / $10 | $0.10 / $0.50 |
| Reading cached text | $0.20 | $0.20 | $0.10 | a tenth of input |
| Context / longest reply | 1M / 128K | 1M / 128K | 1M / 128K | 1M / 128K |
| Thinking | always on | always on | on | on |
| Default effort in Claude Code | medium | medium | medium | medium |

What matters for the design:

- **Opus 5.5 at medium effort is the right default lead.** On Anthropic's coding benchmark it solved 93.1% of tasks at $0.22 per solved task. Fable 5.2 at high effort solved 96.3% at $1.39: three more points for about six times the cost. Opus 5.5 at high effort gets most of that gain (95.5%) for $0.30.
- **Fable 5.2 is for the hard part.** Its gains are largest on long, ambiguous work: architecture for a new project, a root cause nobody can find, synthesis across many inputs. Fable at low effort is a real option for hard but well-specified tasks (94.6% at $0.39).
- **Escalate on failure.** Start at the cheaper setting; re-run only the failures at the stronger one. Measured saving: about 40% at the same pass rate. This only works when every task has a check that can fail, which is one reason the requirements ledger exists.
- **Over-instruction lowers quality on Fable 5.2.** Long lists of absolute rules, "verify twice", "always use a sub-agent to check" and piled-up cautions make it worse, not better. The Travel Journal handbook's style (many prime directives, 22 standing roles, mandatory reviewers) is exactly the pattern Anthropic's guidance warns about. The brain's core is short, gives reasons, and prunes its own rules.
- **Thinking cannot be turned off or steered by words.** "Think carefully" lines do nothing useful. Depth is set with the effort level.
- **A sub-agent with no model set inherits the lead's model.** On a Fable session, every unlabelled helper runs on Fable. Every brain agent file sets its model and effort explicitly.
- **Fable 5.2 has known narrow limits**: it was held to Opus 5.5 level on a few AI-research topics, and it declines most cybersecurity and research-biology work. In Claude Code a safety fallback leaves the session on the fallback model. The brain keeps model facts in one dated file and warns when they are old.

## 2.2 The Claude Code platform (report 02)

The most important finding of the whole research, confirmed three ways (the official documentation, analyst 2, and this session's own records):

**In a cloud session with two repositories, only some things load from each repo.**

| From each repo | Loads in a two-repo session? |
|---|---|
| `CLAUDE.md` and unscoped rules | Yes |
| Skills, agents, commands | Yes |
| Hooks, permissions and other settings | **No** |
| Connector definitions (`.mcp.json`) | **No** (one-repo sessions only) |
| Plugins a repo turns on | **No** (cloud sessions do not install them) |

So the Travel Journal repo's hooks and its Library connector never ran in a two-repo chat like this one. Three consequences:

1. The brain's required core is a short `CLAUDE.md`, skills, agents, and plain scripts that Claude runs. Nothing essential may depend on a hook, a connector or a plugin.
2. Hooks are still shipped, because they do load in one-repo sessions (the weekly learning run) and can be switched on for two-repo sessions through the cloud environment's settings, which is a one-time click task for you (Part 9.4).
3. "Plugins" in your request are delivered as skills. A plugin packaging of the same files is included for desktop use, where plugins do install.

Other facts used in the design:

- `CLAUDE.md` is paid for on every request and by every sub-agent, from both repos. Splitting it with imports saves nothing. Target: under 200 lines.
- A skill costs only its one-line description until it is used. This is the cheapest way to carry a large body of method.
- Sub-agents can be told to skip both `CLAUDE.md` files (`omitClaudeMd`), and can have their own model and effort.
- Each model has its own cache. Switching model mid-session, or using a skill that names a different model, forces a full re-read at full price.
- The main conversation's cache lasts an hour on a subscription; a sub-agent's lasts five minutes.

## 2.3 Where tokens actually go (report 03)

Measured on this session's own records, at Fable list prices:

| | Share of tokens | Share of cost |
|---|---|---|
| Re-reading cached context | 91% | 7% |
| Writing new context into the cache | — | 36% |
| Output (including thinking) | — | 57% |

One output token costs as much as 200 cached-input tokens. So the plan does not chase raw token counts. It goes after, in order:

1. **Output**: short reports, edits instead of rewrites, the right effort level, no restating.
2. **Cache writes**: stable always-loaded files, one model per session, bulky tool output kept out of the conversation.
3. **Turns**: fewer round trips through scripts that do several things at once, and parallel read-only calls.
4. **Sub-agents**: each one starts cold and pays to load its context. Used only for work that is self-contained, bulky and checkable.

Ten rules follow from this and each has a test the ledger or a lint can run (Part 4.2).

## 2.4 Algorithms and "quantum logic" (report 04)

Every candidate was specified, and two were prototyped and measured:

| Problem | Best method | Verdict |
|---|---|---|
| Choosing which memory items to load under a token budget | Greedy selection on a coverage objective: 99.1% of optimum; annealing added 0.9–1.7% at 12–30 times the runtime | Build greedy |
| Scheduling tickets across parallel agents with file conflicts | Critical-path first, then simulated annealing: 0–2.3% above the best possible, against 13–15% for first-come | Build both; this is the quantum-inspired part |
| Choosing model and effort per task under a budget | Exact dynamic programming (multiple-choice knapsack) | Build; nothing to anneal |
| Learning which model and effort suit which task class | Thompson sampling on logged outcomes | Build; this is the machine-learning part |
| When to stop reviewing | One round always, a second only to confirm blocking fixes, never more than three | Build as a rule |
| Finding things in memory | Built-in full-text search with BM25 ranking, no installs | Build |
| Avoiding repeated work | Content-addressed cache: same inputs, reuse the stored result | Build |
| Shrinking instructions with lossy compression | Unsafe: meaning is lost | Do not build |

## 2.5 What the Travel Journal repo taught us (reports 05 and 06)

**Keep, because it demonstrably worked:**

- The checkpoint file and resume loop; "Start running".
- `NEEDS_YOU` with defaults, so work never blocks on you.
- Decisions recorded as assumed, with your overturn in one place.
- A blind reviewer with a rubric (it caught a timestamp bug and refused a skipped gate).
- One command that runs the whole gate; pushing only on a recorded green result.
- Separate file ownership for parallel workers.

**Drop or shrink, because the repo's own records show it was never used:**

| Built | What happened |
|---|---|
| 500-idea coverage table | All 500 still marked to-do |
| 500-role HR catalogue and staffing engine (1,945 lines, 937 kB) | Produced plans nobody adopted, and polluted search results |
| Token payroll | Ten hand-typed rows, zero grants; did not prevent three usage-limit stops |
| 22 standing roles, 31 agent files (27,082 words) | About 3,500 words of copied boilerplate; every description paid for in every session |
| 7-seat board and a 100-thinker canon | Its real value was one adversarial read |
| Performance cards, gate files, principles cards | Never written, though every agent spec cited them |
| Lessons rule ("write a lesson when…") | One lesson in 50 commits |

**Failures that need a mechanism, not a sentence:**

- Rules written as prose were not followed: "critic score of 8 to merge" sat next to pushes at 6/10.
- Two pushes reached `main` without a green check, and a live error escaped the local gate.
- Status lived in five places and ended up contradicting itself.
- The biggest single waste: capture, inbox and sync features were built on assumed answers and then deleted when you said the app should be read-only. The questionnaire file had gone unanswered. Lesson: ask at most three fork-level questions in chat before building, because you answer chat and skip files.
- 390 MB of screenshots went into git.

**A search test worth knowing:** a search built only on what Python ships with found the right passage in the top five 87% of the time on the Travel Journal's own 244-question test set, in 1.7 ms per query. The original stack scored 91% but needed model downloads and took about 2.5 seconds per query, and it could not answer at all while a fresh session rebuilt its index.

## 2.6 What your past chats show (report 07)

Seventeen projects appear in the history: the Japan trip app, a Spanish legal counsel system with a "Cerebro" brain agent, learning apps built from books, a Costa Rica knowledge base and brochure, birding and plant tools, games and Minecraft tools, course assignments, a car project, and the Travel Journal. Four of them were earlier attempts at this same brain idea.

Eighteen kinds of request recur. The brain must handle all of them: web apps for iPhone deployed on Vercel; design and visual polish; handover between chats; release to `main`; agent team design; deep research and searchable knowledge bases; long-form writing; learning apps from books; rubric-driven assignments and audits; Spanish and English output; data pipelines and outside services; games; help running things on your own computer; questions about Claude itself; repository housekeeping; legal research; efficiency work; downloadable documents.

Patterns the design answers directly:

| What the history shows | What the brain does |
|---|---|
| The most repeated instruction, in five projects: `main` must always be the deployable app and Vercel must show it | A release rule in the project contract from day one, executed by one script that pushes only on a recorded green gate and then checks the live site |
| The most repeated complaint: context runs out and you have to change chats | Small start-up cost, checkpoints to files, and a "Hand over" command that leaves both repos clean and gives you the one line to paste |
| One-word triggers: "set up", "Start running", "Continue" | Kept, and they mean the same in every project |
| 53 of 55 sessions from your phone, dictated | Short replies, numbered options, click-only steps |
| "Do not stop and do not ask me anything until everything is done" | Decide, record the assumption, continue; ask only the questions that would change what gets built |
| "Propose 5, I will choose"; "start with one lesson so I can judge" | Options as a short numbered menu; a small sample before any expensive full run |
| Timeouts on very large single edits; a 2.6 MB paste ended a session | Large files are written in parts; large content goes to files, never inline |
| Several chats on the same repos at once | A lease file names the active session; a second chat is told |
| "It's the worst it's ever been, go back" | Tagged known-good versions and a one-step restore |
| API keys pasted into chat three times | Keys are requested through the secure form, never repeated, and scanned for before every commit |
| About $3,200 at list prices across 39 sessions, single sessions up to $627 | The baseline the ledger measures against |

---

# Part 3 — The design

## 3.1 Principles

1. **Lowest process that meets the bar.** Every request is sized first. Machinery is added only when the request needs it.
2. **Scripts before models.** Anything that can be done by a deterministic script (finding the project, reading state, counting tokens, running a gate, searching memory, scheduling) is done by a script. Scripts cost no model tokens beyond their short output.
3. **Mechanisms before sentences.** A rule that matters is enforced by a script's exit code or by CI, because the Travel Journal showed that prose rules get skipped.
4. **Measure, then tune.** Cheaper models, lower effort and time pressure are adopted for a kind of task only when the ledger shows equal or better outcomes. Unmeasured, the brain defaults to quality.
5. **The brain holds method and memory; the project holds state and output.** The brain never contains a project's name or content. A project never contains a copy of the brain.
6. **Small, stable, always-loaded text.** Nothing that changes from session to session lives in a file that is always loaded, because that would break the cache.
7. **Honest reporting.** Every claim of progress is checked against a tool result from the same session before it is made.

## 3.2 The two repositories

```
chat session
├── Claude-Brain/            method, skills, agents, scripts, memory, evals   (this repo)
└── <your project>/          the thing being built
    ├── CLAUDE.md            short pointer to the brain (under 2 KB)
    ├── STATUS.md            for you: where things stand
    ├── NEEDS_YOU.md         for you: things only you can do, as click steps
    └── .brain/              the contract: state, plan, ledger, decisions, project tools
```

How the brain finds the project: `bin/brain boot` locates the brain from its own file path, looks at the folders beside it, and classifies each one. It never relies on environment variables that differ between session types.

| What it finds beside the brain | Mode | What happens |
|---|---|---|
| One folder with `.brain/project.json` | work | Route the request by size; resume only when asked to |
| One empty repository | bootstrap | "New project: …" installs the contract and starts |
| One repository with content but no `.brain/` | adopt | Read-only survey first; then add only the contract files |
| Nothing | brain only | Answer questions, run learning, or explain how to attach a project |
| Several | choose | The one you named; otherwise the most recently active; otherwise one question |
| A project on an older contract | migrate | Back up with a commit, run the migrations, continue |
| A project on a newer contract than the brain | stale brain | Write nothing; tell you the brain needs updating |

Each repository also works alone. A project opened without the brain still has its state and plan and says once that the brain is missing. The brain opened alone can answer, learn and maintain itself.

## 3.3 The brain repository

```
Claude-Brain/
  CLAUDE.md               always loaded, capped at 6 KB: sizing rules, the few core rules, where things are
  README.md               what this is, in plain words
  OWNER_GUIDE.md          the trigger phrases, the files you read, click-step setup
  NEEDS_YOU.md            brain-level items only you can do
  VERSION                 brain version and contract number
  bin/brain               the one command-line entry point (Python standard library only)
  engine/                 the scripts behind it (Part 3.6)
  .claude/
    agents/               six archetypes with explicit model and effort
    skills/               on-demand procedures; only descriptions are always loaded
    settings.json, hooks/ optional guards for one-repo sessions and desktop
  method/                 lifecycle, routing, efficiency, quality, models: read on demand
  playbooks/              one per family of work, plus definitions of done
  contract/               the versioned schema, the project template, migrations
  memory/                 learned items, verified facts, model facts          ┐
  owner/                  your standing instructions and preferences          │ the learned zone:
  stats/                  token ledger, routing statistics                    │ changed only by the
  learning/               inbox, manifest, changelog, weekly digest           ┘ learning pipeline
  evals/                  routing test set, contract fixtures, search test set, benchmark tasks
  tests/                  unit tests for every script
  .github/workflows/      CI: tests, budgets, guard, contract fixtures
  docs/                   this plan, the requirements trace, research, decisions
```

**Two zones.** The *learned zone* (`memory/`, `owner/`, `stats/`, `playbooks/`, `learning/`) is changed only by the learning pipeline after version 1.0. The *kernel zone* (scripts, schemas, evals, CI, `CLAUDE.md`) is engineering: the pipeline is not allowed to rewrite its own rules or its own tests, and changes there need your approval. This is the honest form of "only modified by its own learning systems".

## 3.4 The contract: `.brain/` in every project

```
<project>/
  CLAUDE.md                stub: this project uses contract v1; where the brain is; what to do if it is missing
  STATUS.md                at most 40 lines: done, next, cost, what was learned
  NEEDS_YOU.md             numbered items, each with what, why, click steps, and what happens meanwhile
  .brain/
    project.json           the manifest
    STATE.md               the single checkpoint: stage, current item, next three, anything half-finished
    REQUIREMENTS.md        the requirements ledger
    PLAN.md                the current plan
    DECISIONS.md           one line per assumed decision; you write OVERTURNED to reverse one
    HANDOVER.md            written by "Hand over": everything a fresh chat needs
    lease.json             which session is active on this project
    memory/                project facts and lessons (same format as the brain's)
    ext/                   project-specific skills, agents, tools and playbook overrides
    log/                   one small record per session; gate results with exit codes
```

The manifest is JSON so that reading it needs no installs:

```json
{
  "contract": 1,
  "project": {"id": "example", "title": "Example", "created": "2026-11-10"},
  "family": "software",
  "types": ["web-app"],
  "stage": "build",
  "commands": {"setup": "", "check_fast": "", "check_full": "", "run": ""},
  "gates": [{"id": "checks", "kind": "command", "command": ""}],
  "release": {"rule": "none", "branch": "main", "live_url": ""},
  "paths": {"deliverables": [], "evidence": "docs/evidence/", "never_touch": []},
  "languages": ["en"],
  "risk": "standard",
  "privacy": {"share_lessons": "method-only"},
  "brain": {"last_seen": "", "min_contract": 1}
}
```

**One state file.** The Travel Journal kept status in five places that drifted apart. Here `STATE.md` is the only checkpoint, written by one command, and `STATUS.md` is generated from it.

**Release rule.** `release.rule` is `none`, `main-on-green` or `pr`. With `main-on-green`, `bin/brain release` runs the full gate, pushes only if the recorded exit code is zero, never force-pushes, and then checks that the live address serves the new version. This is your most repeated instruction, turned into one script.

**"Forever", made testable.** The contract number is an integer. Each version's schema is a frozen file. Changes are additive by default; a rename or removal needs a new number and a small migration script that is safe to run twice. A snapshot of a project at every past version is kept in `evals/fixtures/`, and CI opens, migrates and validates every snapshot on every change to the brain.

**Project-specific tools.** Anything that only makes sense for one project (a voice guide, a media pipeline agent, a domain glossary, a custom check) lives in the project's `.brain/ext/` or its own `.claude/` folder. It adds to the brain's playbooks for that project and can override their defaults, but cannot override the contract or the write rules.

## 3.5 How a request flows

Eight stages, the same for every kind of work. Smaller requests skip stages; they do not run them faster.

**intake → requirements → research → plan → build → verify → deliver → learn**

Sizing comes first, because over-process is the main waste:

| Size | Examples | Reads | Helpers | Writes | Process overhead target |
|---|---|---|---|---|---|
| **0 Answer** | "What does this mean?", "Which is better?" | Nothing extra | None | Nothing | Zero process steps |
| **1 Small task** | Fix a typo, add a field, one chart, rewrite a paragraph | The files touched | None, or one for a search | The change; one line of state | Under 5% |
| **2 Project** | A new app, a report, a translated site | State, ledger, plan, one playbook | Up to 4 at once, each justified | The full contract | Under 15% |
| **3 Programme** | A multi-week build with phases | As above, per phase | Scheduled teams, after a written plan | As above, plus phase gates | Under 25% |

Rules: use the smallest size that can meet the definition of done. Moving up a size mid-task is allowed and logged with a reason. "Quick:" forces size 0–1. "Go deep:" allows a research-grade answer to a question. "Start running", "Continue" and "set up" resume at the project's recorded size.

Five families of work cover everything in your history. Only four things vary between them: what is built, how it is checked, how it is delivered, and who leads.

| Family | Covers | Checked by | Delivered as |
|---|---|---|---|
| **Software** | Web and phone apps, back ends, tools, games, design systems | The project's own commands, plus screenshots at phone size for anything visual | A branch, a release to `main`, a live address |
| **Data** | Pipelines, analysis, experiments, outside services | A clean re-run, totals that add up, recorded fixtures, a simulated quota error | A report plus the script that reproduces it |
| **Knowledge** | Research, plans, strategy, legal analysis, long writing, decks, rubric audits | Each claim against its source, word counts, a present/missing/wrong table | A document, PDF or deck |
| **Language** | Translation, Spanish and English editions | Blind back-translation, glossary and length checks | Files in the project's format |
| **Operations** | Scheduled jobs, automations, running things on your computer | A dry run, safe to run twice, a failure notice test | The routine plus a one-page guide of copy-and-paste steps |

A kind of work that fits none of these uses the nearest one and records the gap. A sixth family is added only after two projects fit badly.

## 3.6 The engine

One entry point, `bin/brain`, Python standard library only, no installs, every command with a self-test. Output is always short, because output is what Claude then has to read.

| Command | What it does | Replaces |
|---|---|---|
| `boot` | Finds the project, reads state, counts open items for you, sizes the request, recalls the few most relevant memory items, warns about stale facts or a second active session. About 15 lines. | Reading six documents at the start of every session |
| `init`, `adopt`, `validate`, `migrate` | Create or check the contract in a project | Hand-made setup |
| `route` | Sizes a request and suggests family, model and effort from rules and logged outcomes | Guessing |
| `recall` | Searches memory and packs the best items under a token budget | Loading whole lesson files |
| `req` | Adds, lists and checks requirements-ledger lines; exits non-zero when a line has no evidence | "I think that's everything" |
| `run` | Runs a command, saves the full output to a file, prints only the result and the failing lines | Thousands of lines of build log in the conversation |
| `gate` | Runs the project's gates and records each exit code | Pushing without a green check |
| `release` | Gate, then push only on green, then check the live address | The red pushes and invisible deployments in your history |
| `checkpoint`, `status`, `handover` | Write the single state file, generate `STATUS.md`, prepare a clean handover | Status in five places; handover patches |
| `ledger` | Reads real token use from the session's records, by model and sub-agent, and prices it | Estimates |
| `close` | End of session: ledger, run record, lesson candidates, status refresh | The lessons rule nobody followed |
| `plan schedule`, `plan assign` | Schedule tickets across agents; choose model and effort under a budget | First-come scheduling; one model for everything |
| `learn …` | The learning pipeline (Part 6) | Hand-edited handbooks |
| `budget`, `guard`, `doctor` | Enforce the always-loaded size caps, the zone rules, and self-tests | Bloat and drift |
| `map` | A ranked map of a codebase's most connected files | Reading files to find out what matters |

---

# Part 4 — The efficiency system

## 4.1 Budgets that are enforced

| What | Cap | Enforced by |
|---|---|---|
| Brain `CLAUDE.md` | 6 KB (about 1,500 tokens) | `bin/brain budget` in CI |
| Project stub `CLAUDE.md` | 2 KB | Same, on the template and on `validate` |
| Each agent or skill description | 300 characters | Same |
| Number of agents / skills | 6 / 12 | Same |
| `boot` output | 1.5 KB | Unit test |
| A memory item | 400 characters | Schema check |
| A sub-agent's reply to the lead | 2,000 tokens; detail goes to a file | Agent definitions and the brief template |
| Helpers running at once | 4 by default | `plan schedule` and the core rule |

Baseline for comparison: the Travel Journal setup carried about 6,000 always-loaded tokens and an estimated 35,000–50,000 more in start-of-session reading. The brain's target is about 3,000 always-loaded tokens for both repos together and under 800 for orientation.

## 4.2 The ten rules, each with a test

1. **One model per session.** No skill names a different model. Test: one main-conversation model per session in the ledger.
2. **Always-loaded text is small and never changes mid-project.** No dates, counters or status in it. Test: the budget check and a lint for volatile content.
3. **Most input is read from cache.** Target: 80% or more after the third request. Test: computed per session by `ledger`; a low value becomes a lesson candidate.
4. **Every work item has a check before work starts.** Test: `req check` finds no line without a "passes when".
5. **Independent read-only calls go out together.** Test: a ratio computed from the session record.
6. **Bulk output never enters the conversation raw.** Builds and tests run through `bin/brain run`. Test: no tool result over 5,000 tokens in the main conversation, apart from a deliberate file read.
7. **Start at the routed model and effort; escalate only on a failed check.** Test: every escalation in the ledger links to a failing check.
8. **Delegate only self-contained, bulky, checkable work**, with a brief that carries everything needed and a reply cap. Test: reply sizes; workers skip `CLAUDE.md` and list their tools.
9. **Search memory for a playbook or earlier decision before planning or researching.** Test: reuse rate reported by `ledger`.
10. **Checkpoint at each item boundary.** Test: a state write precedes each new item.

## 4.3 Model and effort routing

Roles, not model names, appear in playbooks. The mapping lives in one dated file, `memory/models.json`, so a new model release changes one file.

| Role | Default | Used for |
|---|---|---|
| Lead | Opus 5.5, medium | Running the session and talking to you |
| Deep lead | Fable 5.2, high (low or medium when the task is hard but well specified) | New-project architecture, stubborn root causes, synthesis across many inputs |
| Reviewer | Opus 5.5, medium or high, fresh context, read-only | Finding defects against the ledger |
| Final gate on a one-way decision | Fable 5.2, high, one bounded call | Rare |
| Builder | Sonnet 5.5, medium, with a required real check; failures re-run on Opus 5.5 | Implementation with a clear check |
| Bulk reader | Haiku 5.5, low or medium, inputs under 100K tokens, output checked by shape or spot check | Extraction, classification, summarising many files |
| Deterministic work | No model | Formatting, counting, indexing, scheduling, diffing |

You choose the session's model when you start a chat; the brain does not switch it, because a switch throws away the cache. Routing applies to helpers and to the effort level. If you start a chat on Fable for routine work, `boot` says so once and suggests Opus for next time.

**The learning part.** For each class of task, the ledger records which model and effort were used and whether the check passed the first time. A Thompson-sampling table turns those records into the next suggestion: mostly the cheapest setting that has been passing, with occasional trials of alternatives so it keeps learning. Until a class has at least eight recorded outcomes per option, the defaults above stand, and the weekly digest says how many outcomes each suggestion rests on.

**The cascade rule.** Try the cheaper option first when the chance it passes is greater than (its cost + the cost of checking) ÷ the cost of the stronger option. Otherwise go straight to the stronger one.

## 4.4 Delegation and scheduling

A helper is used when the work is independent of the conversation, large enough that reading it would fill the lead's context, and has a check. Otherwise the lead does it.

When a plan has several items that can run in parallel, `bin/brain plan schedule` takes the items, their dependencies, their estimated sizes and the files each one owns, and returns waves:

1. A critical-path pass orders items by how much work depends on them.
2. Items that touch the same files are never placed in the same wave.
3. Simulated annealing then improves the assignment to shorten total elapsed time. This is the quantum-inspired step, and it is only used when it beats the critical-path result on that plan.

The scheduler also takes the helper cap and a token budget, and reports the expected elapsed time and token cost of running in parallel against running in sequence, so the trade is visible before it is made.

## 4.5 Memory retrieval and packing

Memory is small items (a rule, a fact, a preference), each with a scope, evidence and counters. `bin/brain recall "<task>"`:

1. Searches with the built-in full-text index (BM25 ranking).
2. Scores each hit by relevance × confidence × recency × importance.
3. Packs the best set under a token budget with greedy coverage, so two items that say the same thing do not both get loaded.
4. Prints one line per item with its id. Default budget: 600 tokens.

The index is rebuilt from the item files in a fraction of a second and is not committed. Semantic (vector) search is not built: it would need model downloads at every session start, and on the one test set available the plain method was within four points. It is listed as an experiment to run if a measured gap appears.

## 4.6 Caching of derived work

Anything computed from files (a repo map, a summary of a long document, an index) is stored under a key made from the hash of its inputs. If the inputs have not changed, the stored result is reused. In a cloud session the cache lives in the project's `.brain/cache/`, ignored by git unless the project opts to commit small entries.

## 4.7 Speed

Elapsed time comes mostly from the number of round trips and from waiting on helpers. The levers, in order: scripts that do several things in one call; parallel read-only calls; the scheduler; helpers in the background while the lead keeps working; chunked writes so large files never time out; and gates run when the machine is quiet, since your history shows a release blocked by a timing check that only failed because other agents were using the processor. Fast mode costs double and is billed from usage credits on a subscription, so it stays off unless you ask.

---

# Part 5 — The quality system

The evidence is consistent: checks that can be *run* beat a model reflecting on its own work, a reviewer needs fresh context, and piling "double-check everything" instructions onto current models makes them slower and no better. So quality lives in artefacts and scripts, with very little prose.

## 5.1 Accuracy

- **The requirements ledger.** For any size-2 request, every sentence you wrote becomes a numbered line: your exact words, what will satisfy them, how it will be checked, and at the end a pointer to evidence (a test result, a screenshot, a file and line, a source). `bin/brain req check` exits non-zero while any line lacks evidence, and `handover`, `release` and `close` call it.
- **One sentence kept from Anthropic's guidance**, because it measurably removed invented status reports: before reporting progress, check each claim against a tool result from this session.
- **Sources.** A factual claim in a research or legal deliverable carries its source. Facts are separated from estimates. Library and service behaviour is looked up in current documentation, not recalled.
- **Your own facts.** A project keeps one canonical facts file (dates, names, numbers you have stated). Derived files are checked against it by script. Your history shows you correct wrong dates and counts quickly; this stops them recurring.
- **Reproduce before fixing.** A bug fix starts by making the failure happen, and ends by showing the same check pass.

## 5.2 Attention to detail

- **Definitions of done, by deliverable.** Nine short checklists in `playbooks/dod/`: code change, new app or feature, screen, research memo, plan, data analysis, written or translated content, automation, and an answer to a question. Each has five to nine yes/no items read at the moment of delivery.
- **Detectors for false "done".** The research catalogued 21 ways an agent claims success wrongly (tests not run, tests skipped, stubbed code, invented citations, partial coverage of the request, quietly reduced scope). `bin/brain gate` and `req check` detect the ones a script can: a gate with no recorded exit code, skip markers added in the change, TODO stubs in new code, links that do not resolve, ledger lines with no evidence, word counts off target.
- **Visual work is checked by looking.** Screenshots at phone size and desktop size, saved outside git history by default (the Travel Journal put 390 MB of screenshots in its repo).
- **"Done" for an app means visible to you.** Deployed, the live address serving the new version, and a note of what to check on your phone.

## 5.3 Creativity

Creative quality comes from generating real alternatives and choosing, not from asking for "creative" output.

- **Diverge cheaply, then converge.** Five 40-word sketches in one call, each from a different starting constraint. A blind pick against the brief. Only the winner is expanded.
- **Options for you when taste decides.** For icons, names, palettes and layouts you get a short numbered menu with images, as you have asked for before.
- **Name the defaults to avoid.** "Avoid a generic look" just swaps one default for another. Design briefs list the specific patterns to stay away from.
- **Facts stay outside the creative step.** The creative pass works on form and framing; the facts file is not up for reinvention.
- **Not everywhere.** A bug fix or a data pipeline gets no creative pass.

## 5.4 Review, rationed by risk

| Risk level | Examples | Verification |
|---|---|---|
| **Trivial** | Typo, copy change | The author's own check |
| **Standard** | A feature, a memo | A complete runnable check; no model reviewer unless the check cannot cover it |
| **High** | Data migration, release, anything public or legal | One fresh-context reviewer on a different model from the author, against the ledger |
| **One-way door** | Deleting data, an irreversible architecture choice, spending money | The above, plus a red-team pass, plus your confirmation |

- One reviewer, not a panel. The Travel Journal's seven-seat board is replaced by one adversarial read at the levels that need it.
- Criteria are yes/no "passes when" statements, not 1–10 scores.
- The reviewer reports everything it finds with evidence; severity is filtered afterwards, because telling a current model to "only report serious issues" makes it miss things.
- One review round always; a second only to confirm blocking fixes; never more than three. A reviewer always finds something, so the loop stops when only style remains.
- Reviewers are tested with planted defects, and their pass rate is tracked, so they do not turn into rubber stamps.

---

# Part 6 — The learning system

## 6.1 What learns

| Memory | Holds | Where | Loaded |
|---|---|---|---|
| Run records | One small record per session: task classes, outcomes, gate results, your corrections, token totals | Brain `memory/episodes/` (no project content) and project `.brain/log/` | Never; read by scripts |
| Facts | Verified facts with a source and a re-check date, including model and platform facts | Brain `memory/facts.jsonl`, `memory/models.json` | On recall |
| Playbook items | Short rules with evidence and counters | Brain `playbooks/*.jsonl`, rendered to readable files | On demand |
| Owner model | Your standing instructions, word for word and dated; your preferences | Brain `owner/` | The top few in `CLAUDE.md`; the rest on recall |
| Statistics | The token ledger; which model and effort passed for which task class | Brain `stats/` | Never as text; a script answers in one line |
| Project memory | Anything true for one project only | The project's `.brain/memory/` | By that project |

Every item has the same shape: an id, a scope (everything, one family of work, or one project), the text (400 characters at most), evidence, where it came from, how far it is trusted (stated by you, observed, derived, or external), counters for helped and harmed, and a status (candidate, probation, active, demoted, retired).

## 6.2 The pipeline

1. **Capture** (script, no model). `bin/brain close` at the end of a session writes the run record and ledger from the session's own records, the gate results and the git history. It is keyed by session, so running it twice changes nothing. The Travel Journal's lessons rule relied on someone choosing to write a lesson and produced one in 50 commits; capture here is automatic.
2. **Reflect** (one small-model pass, only when there is a signal). A failed gate, rework, a correction from you, an unusually expensive task, or a first success in a new class. Input is the run record and the few lines around each signal, never the whole conversation. Output is at most three candidate lessons, each pointing to a real event. A candidate with no such event is dropped by script.
3. **Curate** (script). A candidate that mentions project names, paths or domain terms stays in that project's own memory. Near-duplicates increase the existing item's counter instead of adding a new one. Opposing items are marked as a conflict and neither is promoted until evidence separates them. Something you stated always wins.
4. **Validate** (script, plus evals for bigger changes). Shape, size caps, no secrets, no personal data, no instruction-like text from outside sources. Changes to always-loaded text or to a skill description need a before-and-after run of the eval set.
5. **Promote** (script). The only way to change the learned zone is `bin/brain learn apply`, which takes a list of small operations (add, count helped, count harmed, edit one item, change status, move scope). It cannot replace a file, and it refuses a change that removes more than 10% of a file's items. One research result explains the rule: a system that rewrote its memory whole collapsed 18,282 tokens of knowledge to 122 and ended up worse than having no memory. Every promotion is logged in `learning/manifest.jsonl` and described in plain words in `learning/CHANGELOG.md`.
6. **Decay** (script). An item not used for 90 days is demoted; unused for a further 180 it is archived, never deleted. Harm counts retire an item faster than age. Facts past their re-check date are flagged and re-verified before use.
7. **Audit.** One learning change is one pull request, so undoing it is the Revert button. A weekly digest of at most 15 lines tells you what was learned, what was retired, tokens per finished task against the previous four weeks, and anything it is unsure about.

**Evidence thresholds.** A candidate becomes active after three clean confirmations across at least two sessions, and is demoted after three harmful ones. A lesson moves from one project to all projects only after it has been seen independently in a second project. No efficiency claim is made on fewer than eight tasks per side.

## 6.3 Keeping the brain safe from bad lessons

- Text that Claude merely read (a web page, a file in a project, tool output) is data. It can supply a fact with a source. It can never become a rule.
- A rule needs evidence that points to an outcome: a gate, a test, or something you said.
- Changes to always-loaded text, permissions, guards, network access or the pipeline itself are kernel changes and need you.
- New items start on probation and are flagged when recalled until they have earned their place.

## 6.4 Enforcing "only its own learning systems"

Strongest first:

1. **CI on the brain repository.** For every pull request, each change in the learned zone must match a manifest entry, and CI re-applies the recorded operations to the previous version and requires the same result. A hand edit dressed up as a learning change fails.
2. **Branch protection on the brain's `main`**, requiring that check. This is a one-time click task for you (Part 9.4).
3. **A local guard** that blocks direct edits to the learned zone, active wherever hooks load.
4. **The rule in `CLAUDE.md`.** The weakest layer, which is why it is not the only one.

Your override is a label you apply to a pull request on GitHub. A line typed in a commit message does not count, because any agent can type one.

## 6.5 Schedule

- **Every session:** capture at close, pushed to a `learning/` branch as a small pull request that merges itself when CI passes.
- **Weekly:** a scheduled one-repo routine on the brain (where its hooks do load) runs reflect, curate, validate, decay and the digest.
- **Day one:** memory is seeded from what the Travel Journal and your history already taught, each item marked as seeded with its source, so the brain does not start empty.

---

# Part 7 — Agents, skills and how you use it

## 7.1 Six agent archetypes

Thirty-one role files are replaced by six, each with an explicit model, effort and tool list. A project that needs a specialist (a motion designer, a media engineer) defines it in its own repo.

| Agent | Model, effort | Job | Returns |
|---|---|---|---|
| `scout` | Haiku 5.5, low; read-only; skips `CLAUDE.md` | Find files, read in bulk, extract | Findings with file and line |
| `researcher` | Sonnet 5.5, medium; web and read | Answer a question with sources | A memo file and a short summary |
| `builder` | Sonnet 5.5, medium | Implement one item with a real check | A change and the check's result |
| `writer` | Opus 5.5, medium | Prose, translation, long-form in parts | Files plus word counts |
| `reviewer` | Opus 5.5, high; read-only; fresh context | Find defects against the ledger | Findings with evidence |
| `redteam` | Fable 5.2, high; read-only | Attack a one-way decision or a plan | Failure modes and what would change the decision |

## 7.2 Skills

Each costs one line until used.

| Skill | Use |
|---|---|
| `brain-start` | "Start running", "Continue", "set up": resume from state |
| `brain-new` | "New project: …": bootstrap an empty repo or adopt an existing one |
| `brain-plan` | Turn a request into a ledger, a plan and a schedule |
| `brain-build` | Run plan items with the right helpers and checks |
| `brain-verify` | Definition of done, review at the right risk level, release |
| `brain-research` | Research with sources and a memo |
| `brain-create` | The diverge-and-choose creative pass; option menus |
| `brain-handover` | "Hand over": stop helpers, checkpoint, clean both repos, give the one line to paste |
| `brain-learn` | Close a session; consolidate; "What did you learn?" |
| `brain-status` | "Status": regenerate and show where things stand and what it cost |

## 7.3 What you type

| You type | What happens |
|---|---|
| **New project: \<one sentence\>** | The contract is installed in the attached empty repo. At most three questions that would change what gets built, in one message, each with the default that will be used if you do not answer. Then work starts. |
| **Start running** / **Continue** / **set up** | Resume the recorded item without asking |
| **Quick: …** | An answer or a small change, no machinery |
| **Go deep: …** | A researched answer with sources |
| **Status** | Where things stand, what is next, what it cost |
| **Hand over** | Everything saved and pushed, plus the line to paste into a new chat |
| **What did you learn?** | New lessons and changed rules since you last asked |
| **Go back** | Restore the last tagged good version |
| **Stop after this** | Finish the current item, checkpoint, summarise |

Plain language works too. The phrases only remove doubt. Replies match the language you write in.

## 7.4 What you read

In the project: `STATUS.md`, `NEEDS_YOU.md`, and `.brain/DECISIONS.md` if you want to overturn an assumption. In the brain: `learning/CHANGELOG.md` and the weekly digest. Nothing else is required reading.

---

# Part 8 — The build plan

Three phases. Phase A is everything that can be built and proven inside one session with scripts and tests. Phase B needs live two-repo sessions with a real project. Phase C is the learning loop in regular operation. Current status of every ticket is kept in `docs/BUILD_STATUS.md`, not here, so this plan stays stable.

## 8.1 Phase A — Build the brain (this session)

| Ticket | Deliverable | Passes when |
|---|---|---|
| CB-001 | Ten independent analyses of the request; reports in `docs/research/` | Ten reports exist; each has its own extraction of the request |
| CB-002 | This plan and `docs/REQUIREMENTS.md` | Every clause of the request maps to a design element |
| CB-010 | Engine core: shared helpers, the `bin/brain` entry point, `doctor` | `bin/brain doctor` exits 0 on a machine with only Python |
| CB-011 | `detect` and `boot` | All seven modes detected on fixtures; output within 1.5 KB; no network; under 2 seconds |
| CB-012 | Contract v1: schema, template, `init`, `adopt`, `validate`, `migrate` | `init` twice changes nothing; `adopt` adds only contract files and keeps an existing `CLAUDE.md` intact; a project newer than the brain is not written to |
| CB-013 | State: `checkpoint`, `status`, `handover`, lease | One state file; `STATUS.md` generated from it; a second session sees the lease |
| CB-014 | Requirements ledger: `req add`, `list`, `evidence`, `check` | `check` exits non-zero when a line lacks evidence or a "passes when" |
| CB-015 | `run`, `gate`, `release` | Full output saved to a file and only failures printed; exit codes recorded; `release` refuses on a red or missing gate and never force-pushes |
| CB-016 | `budget` and `guard` | Caps enforced; an edit to the learned zone without a manifest entry is rejected |
| CB-020 | Token ledger: `ledger`, `close` | Totals by model and sub-agent from real session records, de-duplicated; priced from `memory/models.json`; running twice gives the same record |
| CB-021 | Learning pipeline: inbox, `learn note`, `curate`, `apply`, `decay`, `digest`, `verify` | Only small operations change the learned zone; an oversized removal is refused; replaying the manifest reproduces the files; outside-sourced rules are rejected |
| CB-030 | Memory search and packing: `recall` | Built-in index; greedy coverage under a budget; measured on a labelled set kept in `evals/` |
| CB-031 | Routing: `route`, the Thompson-sampling table, model assignment under a budget | Trigger phrases map to the labelled size on `evals/routing.jsonl`; no small request is sized as a project; the assignment matches brute force on small cases |
| CB-032 | Scheduler: critical path, file-conflict waves, simulated annealing | Never places conflicting items in one wave; annealed result is never worse than critical-path; deterministic for a given seed |
| CB-033 | Repo map and the content-addressed cache | Same inputs return the cached result; changed inputs do not |
| CB-040 | `CLAUDE.md` kernel | Within 6 KB; contains sizing rules, the core rules with reasons, and pointers only |
| CB-041 | Six agents, ten skills | Every agent sets model, effort and tools; every description within 300 characters |
| CB-042 | Method files and five playbooks with nine definitions of done | Each definition of done has five to nine yes/no items |
| CB-043 | Seeded memory: lessons from the Travel Journal and your history, model facts, your standing instructions | Every item validates against the schema and names its source |
| CB-044 | `OWNER_GUIDE.md`, `README.md`, `NEEDS_YOU.md` | Click steps only; no shell commands required of you |
| CB-050 | Tests and CI | All unit tests pass locally; CI runs tests, budgets, guard and fixtures |
| CB-051 | Contract fixtures: a frozen v1 project, an empty repo, an unmanaged repo, two projects | CI opens and validates each |
| CB-052 | End-to-end rehearsal: bootstrap a sample project in a scratch folder, add ledger lines, run a gate, checkpoint, hand over, close, learn | Every step succeeds by script with recorded output |
| CB-060 | Independent review of the build by a fresh-context reviewer against `docs/REQUIREMENTS.md`, and fixes | Blocking findings fixed; the rest listed |
| CB-061 | Commit and push to the working branch; evidence recorded in `docs/REQUIREMENTS.md` | Branch pushed; every requirement line has evidence or is marked open with a reason |

## 8.2 Phase B — Prove it live (the next sessions)

These need a real two-repo chat and cannot be completed inside the session that builds the brain. Each is a few minutes.

| Ticket | Check | Passes when |
|---|---|---|
| CB-101 | The brain's `CLAUDE.md`, skills and agents load beside a project | `boot` runs from the first message |
| CB-102 | A quick question | An answer with zero process steps |
| CB-103 | "New project: …" on an empty repo | Contract installed, at most three questions, first item started |
| CB-104 | End a session mid-item; in a new chat type "Continue" | The same item resumes without re-planning |
| CB-105 | Helpers honour their model, effort and skip-`CLAUDE.md` settings | Visible in the ledger |
| CB-106 | Whether hooks installed through the cloud environment's settings load in two-repo sessions | Recorded either way; the guard and capture hooks are switched on if they do |
| CB-107 | Whether a skill's own hooks fire after it is used | Recorded either way |
| CB-108 | Pushing to both repos from one session, with branch protection on the brain | The learning pull request merges on green; a direct push to `main` is refused |
| CB-109 | Benchmark: about ten fixed tasks, with and without the brain | Quality not lower; tokens and minutes recorded in `evals/results/` |
| CB-110 | First real project end to end | Released by `bin/brain release`; ledger and digest produced |

## 8.3 Phase C — Learning in operation

| Ticket | Deliverable | Passes when |
|---|---|---|
| CB-201 | Weekly consolidation routine on the brain | The digest appears weekly |
| CB-202 | First routing statistics from real work | Eight or more outcomes per option for at least one task class |
| CB-203 | Tag `brain-v1.0.0`; the learned zone closes to hand edits | CI guard required on `main` |
| CB-204 | Review after the third project | Unused parts removed; a sixth playbook family only if two projects fitted badly |

## 8.4 The acceptance suite

**In CI, no model needed:** detection in all seven modes; `boot` size; `init` for each family and twice; `adopt` leaving existing files intact; migration of every frozen fixture, twice; the stale-brain case; the degraded stub; the guard on recorded inputs; the always-loaded budget; no project names in the brain; a secret scan; inbox record shape; `doctor`; link check; routing on the labelled set; scheduler and assignment correctness; ledger on recorded session files; learning replay.

**Live, by hand, at each consolidation:** CB-101 to CB-110.

**From your history:** the 40 acceptance tests in `docs/research/07-past-chats.md` section B.4(d) are the coverage checklist. `docs/REQUIREMENTS.md` maps each to the mechanism that answers it.

---

# Part 9 — Measurement, risks, non-goals, and what needs you

## 9.1 How success is measured

| Measure | Baseline | Target | Source |
|---|---|---|---|
| Always-loaded tokens, both repos | About 6,000 | About 3,000 or fewer | `bin/brain budget` |
| Tokens to get oriented at session start | 35,000–50,000 (estimated) | Under 800 | `boot` output size |
| Process share of a small task | Not measured before | Under 5% | Ledger |
| Tokens and minutes per finished task, by class | The Travel Journal sessions | Lower at equal or better quality, on eight or more tasks per side | Ledger and benchmark |
| Share of input read from cache | Not measured before | 80% or more | Ledger |
| First-pass gate rate | Not measured before | Rising over time | Gate log |
| Times you had to correct or repeat an instruction | Seen often in history | Falling over time | Run records |
| Requirements with evidence at delivery | Not tracked before | 100%, or listed as open with a reason | `req check` |
| Pushes to `main` without a recorded green gate | Two in the Travel Journal | Zero | `release` |

A target with no measurement behind it yet is a design goal, and the digest says which is which.

## 9.2 Twenty ways this could fail, and the counter-measure

| # | Failure | Counter-measure |
|---|---|---|
| 1 | Over-engineering, because the brief says "mega complex" | Lean default; each part names the measured problem it solves; review after the third project removes what went unused |
| 2 | Always-loaded text grows | Byte budget in CI |
| 3 | Heavy process on small requests | Sizing first; routing test set; process share reported |
| 4 | Role sprawl | Six archetypes; a new one needs evidence; specialists live in the project |
| 5 | The brain damages itself by editing its own rules | Two zones; small operations only; replay in CI; one-click revert |
| 6 | The learning loop stores junk or planted instructions | Outcome evidence required; outside text never becomes a rule; probation |
| 7 | The learning loop never runs | Automatic capture; "nothing learned" is a valid record; inbox size is reported |
| 8 | Memory grows without limit | Size caps; merge or retire before adding; archive never auto-loaded |
| 9 | Branch and merge confusion across two repos | One release rule per project; learning changes by pull request; `boot` warns when the brain is behind |
| 10 | Work lost when a cloud container is replaced | Checkpoint at every item; nothing important only in temporary folders; unfinished work pushed as a branch |
| 11 | Usage limits exhausted by fan-out | Cap of four; cheaper tiers for bulk work; scheduler shows the token cost of parallelism first |
| 12 | A hook breaks every session | Nothing essential depends on a hook; the ones shipped fail open, time out in seconds and are tested on recorded inputs |
| 13 | Slow session start from installs | The brain installs nothing |
| 14 | Model facts go stale | One dated file; roles instead of model names; a warning after 90 days |
| 15 | Brittle scripts | Standard library only; paths from the script's own location; self-tests; CI on a clean machine |
| 16 | Secrets leak into memory or logs | Pattern scan on every record and in CI; logs hold counts, not content |
| 17 | The brain turns into a copy of the latest project | CI check for project names; project lessons stay in the project until seen twice |
| 18 | Nothing is measured | Ledger from day one; fixed benchmark |
| 19 | Verification theatre | Gates are exit codes; the reviewer is never the author; checks are against your words, not against the plan |
| 20 | The contract drifts and old projects break | Frozen schemas, migrations, fixtures in CI |

## 9.3 What this will not be

1. No model training. Learning means curated files, statistics and evals.
2. No quantum computing. One classical annealing step, labelled as quantum-inspired.
3. No always-running search service. Search is a script.
4. No virtual company: no board, HR catalogue or payroll simulation.
5. No custom agent runtime. It uses Claude Code's own skills, agents and routines.
6. No project content in the brain.
7. No automatic changes to existing projects, the Travel Journal included, unless you ask.
8. No promise of "perfect" or "forever". The promise is a ledger with evidence and a versioned contract with tests.

## 9.4 What needs you (all optional, all clicks)

The brain works without any of these. Each one strengthens a guarantee. Details and click steps are in `NEEDS_YOU.md`.

1. **Merge the brain's working branch into `main`** on GitHub, so new chats start from the built brain.
2. **Turn on branch protection for the brain's `main`** with the CI check required. This is what makes "only its own learning systems" enforceable rather than a convention.
3. **Add the brain to your cloud environment's setup** so its optional guards load in two-repo chats, once ticket CB-106 confirms that route works.
4. **Choose the default model for new chats.** Recommended: Opus 5.5 for everyday work, Fable 5.2 when starting a new project or when something is hard.
5. **Decide whether learning pull requests merge by themselves** on green (recommended) or wait for your click.

## 9.5 Open questions the plan proceeds on by default

| Question | Default used |
|---|---|
| Should the Travel Journal be moved onto the brain? | No, not until you ask. The sample repo was not touched. |
| May the brain store your standing instructions word for word? | Yes, without personal details, in `owner/standing.jsonl`. |
| Should lessons from a client or private project reach the brain? | Method only, never content; a project can opt out. |
| How many helpers at once? | Four, more only when you ask for it on independent work. |

## 9.6 Experiments queued

1. Does plain search leave a gap that vector search would close? Measure on the brain's own labelled set once it has 200 items.
2. Does a reviewer on a different model from the author catch more? Measure with planted defects.
3. Does a written token budget in a helper's brief reduce spend on Fable 5.2 without lowering pass rates?
4. Which effort level is the cheapest that holds for each task class? The routing table answers this as data arrives.
