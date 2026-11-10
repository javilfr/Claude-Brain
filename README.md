# Claude Brain

A permanent repository that sits beside any project repository in a Claude Code chat and makes Claude build that project well, at low token cost. It holds method, helpers, scripts and memory; the project holds its own state, plan and output in a small `.brain/` folder. The brain never contains a project's content, and it changes itself only through its learning pipeline, as small tracked changes that can be reverted.

If you are the owner, start with **[OWNER_GUIDE.md](OWNER_GUIDE.md)**: how to start a chat, what to type, and the three files to read. The full design, with the research behind it, is in **[docs/MASTER_PLAN.md](docs/MASTER_PLAN.md)**.

## Layout

| Path | What it holds |
|---|---|
| `CLAUDE.md` | The short always-loaded core: request sizing, core rules, pointers |
| `.claude/agents/` | Six helper agents (scout, researcher, builder, writer, reviewer, redteam), each with a set model and effort |
| `.claude/skills/` | Ten skills loaded on demand: start, new, plan, build, verify, research, create, handover, learn, status |
| `.claude/hooks/`, `.claude/settings.json`, `.claude-plugin/` | Optional hooks and a plugin manifest; hooks do not load in a two-repository cloud session, so nothing depends on them |
| `bin/brain`, `engine/` | The command-line engine (Python standard library only) |
| `method/` | Lifecycle, routing, efficiency, quality and model guidance, and `dod/` definitions of done, read on demand |
| `playbooks/` | Practice per family of work (`.jsonl` items, with generated `.md` views) |
| `hr/` | The HR department's rack of 100 agent templates (`rack/*.jsonl`), their schema, and the guidelines for writing them. `brain hr hire` picks one for a task, sets the model, effort and token wage, and writes the helper's brief |
| `contract/` | The versioned `.brain/` schema, project template and migrations |
| `memory/`, `owner/`, `stats/`, `learning/` | The learned zone: rules, facts, model data and radar sources, the owner's standing instructions, the token ledger, the learning inbox and radar state |
| `evals/`, `tests/` | Evaluation tasks, seeded defects, recall and routing sets, contract fixtures and unit tests |
| `.github/workflows/ci.yml` | The check named **brain**: tests, self-test, lint, item and eval checks on every push and pull request |
| `docs/` | The master plan, execution plan, engine spec, decisions, tickets and research reports |

The learned zone (`memory/`, `owner/`, `stats/`, `playbooks/`, `learning/`) is written only by `bin/brain learn`. On every pull request CI runs `brain guard diff` and `brain learn verify`, which detect hand edits; until the learned zone is locked at version 1.0 the replay only warns, and the check blocks a merge only once the owner makes it required in the branch settings. Changes to everything else are engineering changes that need the owner's approval.
