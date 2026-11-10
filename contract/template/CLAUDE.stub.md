<!-- brain:begin (managed by Claude Brain; keep this block, write project notes below it) -->
# {title}

This project is built with Claude Brain, contract v{contract}. Its state, plan and decisions live in `.brain/`.

- **Brain attached** (a sibling folder that contains `bin/brain`, normally `Claude-Brain/`): follow that repository's `CLAUDE.md`. Its first step is `python3 <brain>/bin/brain boot`.
- **Brain not attached**: tell the owner once, then work from `.brain/STATE.md`, `.brain/PLAN.md` and the commands in `.brain/project.json`. Checkpoint by editing `.brain/STATE.md`. Put lessons in `.brain/memory/lessons.jsonl` so the brain can collect them later.
- The owner reads `STATUS.md` and `NEEDS_YOU.md`. Things only they can do go in `NEEDS_YOU.md` as numbered click steps, and work continues on everything else.
- Project-specific skills, agents and tools belong in `.brain/ext/` or this repository's `.claude/`, not in the brain.
- Where text below this block disagrees with the brain about how a session starts, where state lives or how work is released, the brain's way applies; the text below is project knowledge.
<!-- brain:end -->
