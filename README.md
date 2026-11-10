# Claude Brain

A permanent repository that sits beside any project repository in a Claude Code chat and makes Claude build that project well, at low token cost. It holds method, helpers, scripts and memory; the project holds its own state, plan and output in a small `.brain/` folder. The brain never contains a project's content, and it changes itself only through its learning pipeline, as small tracked changes that can be reverted.

If you are the owner, start with **[OWNER_GUIDE.md](OWNER_GUIDE.md)**: how to start a chat, what to type, and the three files to read. The full design, with the research behind it, is in **[docs/MASTER_PLAN.md](docs/MASTER_PLAN.md)**.

## Layout

| Path | What it holds |
|---|---|
| `CLAUDE.md` | The short always-loaded core: request sizing, core rules, pointers |
| `.claude/agents/` | Six helper agents (scout, researcher, builder, writer, reviewer, redteam), each with a set model and effort |
| `.claude/skills/` | Ten skills loaded on demand: start, new, plan, build, verify, research, create, handover, learn, status |
| `bin/brain`, `engine/` | The command-line engine (Python standard library only) |
| `method/` | Lifecycle, routing, efficiency, quality and model guidance, read on demand |
| `playbooks/` | Practice per family of work, and `dod/` definitions of done |
| `contract/` | The versioned `.brain/` schema, project template and migrations |
| `memory/`, `owner/`, `stats/`, `learning/` | The learned zone: rules, facts, the owner's standing instructions, the token ledger, the learning audit trail |
| `evals/`, `tests/` | Test sets, contract fixtures and unit tests |
| `docs/` | The master plan, engine spec and research reports |

The learned zone (`memory/`, `owner/`, `stats/`, `playbooks/`, `learning/`) is written only by `bin/brain learn`; hand edits are rejected by the guard and CI. Changes to everything else are engineering changes that need the owner's approval.
