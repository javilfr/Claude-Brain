# Needs you

Things only you can do for the brain itself. All are optional and all are clicks. The brain works without them; each one makes a guarantee stronger. Reply in chat when one is done, or write `RESOLVED:` under it.

## 1. Put the built brain on `main` (2 minutes)

- **Why:** a new chat starts from each repository's `main` branch. Until the work is on `main`, a new chat sees an almost empty brain.
- **How:** on github.com open **javilfr/Claude-Brain** → **Pull requests** → **New pull request** → base `main`, compare `claude/wizardly-darwin-91m4pl` → **Create pull request** → **Merge pull request** → **Confirm merge**.
- **Or:** tell me "merge the brain to main" in this chat and I will do it.
- **Meanwhile:** everything is committed and pushed on the working branch.

## 2. Protect the brain's `main` (5 minutes, after item 1)

- **Why:** this is what makes "only changed by its own learning systems" a rule that GitHub enforces, not just a convention. With it, a change reaches `main` only through a pull request whose checks pass.
- **How:** github.com → **javilfr/Claude-Brain** → **Settings** → **Branches** → **Add branch ruleset** (or **Add rule**) → branch name `main` → tick **Require a pull request before merging** and **Require status checks to pass**, then choose the check named **brain** → **Create**.
- **Meanwhile:** the same check runs on every push and reports problems, but nothing stops a direct change.

## 3. Choose your default model for new chats (no clicks now; a habit)

- **Why:** the model is chosen when you start a chat, and switching it mid-chat throws away the cache. Research for the plan found Opus 5.5 finishes everyday work at about a sixth of Fable 5.2's cost per task, with Fable ahead by about three points on the hardest work.
- **Recommended:** start everyday chats on **Opus 5.5**. Start a chat on **Fable 5.2** when beginning a brand-new project or when something is stuck and hard.
- **Meanwhile:** the brain works on either. It tells you once if a routine chat is on Fable.

## 4. Decide how learning changes get merged (reply with A or B)

- **A (recommended):** a learning change merges by itself when its checks pass. You see it in the weekly digest and can undo any one with the **Revert** button on its pull request.
- **B:** every learning change waits for your click on **Merge**.
- **Meanwhile:** A is assumed, and nothing merges to `main` until item 2 is set up.

## 5. Optional guards in two-repo chats (later; I will give exact clicks when it is confirmed)

- **Why:** in a chat with two repositories, Claude Code does not load a repository's own guard hooks. The brain does not depend on them, but they add a second layer (blocking a wrong edit before it happens, recording the session automatically at the end).
- **What is needed:** one setting in your cloud environment. Whether that route works has to be tested in a live two-repo chat first (ticket CB-106 in `docs/BUILD_STATUS.md`).
- **Meanwhile:** the rules are enforced by the scripts themselves and by the check in item 2.
