# Needs you

Things only you can do for the brain itself. All are optional and all are clicks. The brain works without them; each one makes a guarantee stronger. Reply in chat when one is done, or write `RESOLVED:` under it.

## 1. Put the built brain on `main` (2 minutes)

- **Why:** a new chat starts from each repository's `main` branch. Until the work is on `main`, a new chat sees an almost empty brain.
- **How:** on github.com open **javilfr/Claude-Brain** → **Pull requests** → **New pull request** → base `main`, compare `claude/wizardly-darwin-91m4pl` → **Create pull request** → **Merge pull request** → **Confirm merge**.
- **Or:** tell me "merge the brain to main" in this chat and I will do it.
- **Meanwhile:** everything is committed and pushed on the working branch.

RESOLVED: 2026-11-10 — you approved it in chat and `main` was fast-forwarded to the built brain.

## 2. Protect the brain's `main` (5 minutes, after items 1 and 7)

- **Why:** this is what makes "only changed by its own learning systems" a rule that GitHub enforces, not just a convention. With it, a change reaches `main` only through a pull request whose checks pass.
- **How:** github.com → **javilfr/Claude-Brain** → **Settings** → **Branches** → **Add branch ruleset** (or **Add rule**) → branch name `main` → tick **Require a pull request before merging** and **Require status checks to pass**, then choose the check named **brain** → **Create**. Do this only after the check has gone green once (item 7): requiring a check that cannot run would block every merge.
- **Meanwhile:** nothing on GitHub stops a direct change. The same checks pass when run inside a session (the full test suite, `brain doctor`, `brain lint`, `brain hr audit`).

## 3. Choose your default model for new chats (no clicks now; a habit)

- **Why:** the model is chosen when you start a chat, and switching it mid-chat throws away the cache. Research for the plan found Opus 5.5 finishes everyday work at about a sixth of Fable 5.2's cost per task, with Fable ahead by about three points on the hardest work.
- **Recommended:** start everyday chats on **Opus 5.5**. Start a chat on **Fable 5.2** when beginning a brand-new project or when something is stuck and hard.
- **Meanwhile:** the brain works on either; helpers always run on the model their role sets, whichever you pick.

## 4. Decide how learning changes get merged (reply with A or B)

- **A:** a learning change merges by itself when its checks pass. This needs items 2 and 7 done, plus one more click: **Settings** → **General** → tick **Allow auto-merge**. Then say "merge learning changes automatically" and I will switch it on for each learning pull request. You can undo any one with the **Revert** button on its pull request.
- **B (how it works today):** every learning change is a pull request that waits for your click on **Merge**.
- **Meanwhile:** B.

## 5. Optional guards in two-repo chats (later; I will give exact clicks when it is confirmed)

- **Why:** in a chat with two repositories, Claude Code does not load a repository's own guard hooks. The brain does not depend on them, but they add a second layer (blocking a wrong edit before it happens, recording the session automatically at the end).
- **What is needed:** one setting in your cloud environment. Whether that route works has to be tested in a live two-repo chat first (ticket CB-106 in `docs/BUILD_STATUS.md`, under "Needs a live session").
- **Meanwhile:** the rules are enforced by the scripts themselves and by the check in item 2.

## 6. Switch on the weekly learning run (reply "schedule the weekly learning run")

- **Why:** once a week the brain should fold what it recorded into its memory, check official sources for news about the models and Claude Code, and write you a short digest. That run works best as a scheduled task on the brain alone.
- **How:** after item 1 is done, reply "schedule the weekly learning run" in any chat with the brain attached. I will create a Claude Code routine (a scheduled task you can see and switch off under Routines) that opens a chat on the brain once a week, and show it to you before it first runs.
- **Meanwhile:** nothing is lost. Every session still records itself, and the fold-in happens whenever you say "Consolidate".

## 7. GitHub's automatic checks are not starting on this account (2 minutes)

- **What I saw:** every run of the **brain** check on this repository ends as failed within about four seconds, before any step starts. GitHub's note on those runs says the job was not started because of a billing or spending-limit problem on the account. It is not a problem in the code: the same checks pass when run inside a session.
- **Why it matters:** until the check can run, GitHub cannot enforce anything (item 2), and a red cross will show on every push even though nothing is wrong.
- **How:** github.com → your profile picture → **Settings** → **Billing and licensing** → look for a failed payment or a spending limit of $0 for **Actions**, and fix or raise it. Private repositories use included free minutes first.
- **Meanwhile:** checks are run inside each session before anything is pushed, and the results are in `docs/BUILD_STATUS.md`.

## 8. Another chat reverted three commits on `main` (decide: keep or undo the revert)

- **What I saw:** at 01:09 today (UTC) another Claude session pushed three revert commits to `main`. They undo "brain is on main", a "learn: session records" commit, and the handover that set up this improvement programme (the ticket list, `docs/NEXT_SESSION.md`, and boot showing the brain's open work). I cannot tell from here whether you asked for it.
- **Why it matters:** this session's work (branch `claude/amazing-albattani-204zc8`) is built on the reverted commits. Merging it puts them back, plus all of this session's fixes.
- **If the revert was a mistake:** merge this session's branch into `main` (on github.com: **Pull requests** → **New pull request** → base `main`, compare `claude/amazing-albattani-204zc8` → **Create** → **Merge**). GitHub may report conflicts with the reverts; if it does, say "merge the brain branch to main" in a chat with the brain and I will resolve them there.
- **If you wanted the revert:** say so, and say which part you wanted gone. The branch stays untouched until then.
- **Meanwhile:** nothing on `main` was touched by this session.

RESOLVED: 2026-11-11 — you said the revert was a mistake. The branch was merged with `main` keeping its content, and `main` was fast-forwarded to it.

## 9. Create the job-search repository (1 minute)

- **Why:** your job search (profile, matches, tracker, resume) is personal, so it lives in its own private repository, never in the brain. I cannot create repositories from a chat.
- **How:** github.com → **+** → **New repository** → name `job-search` → **Private** → leave everything else unticked → **Create repository**. Then reply "repo created" in the chat where the job search was built: it pushes everything there (profile, ranked list, matches, resume, research, the daily sweep). In a new chat instead, attach **javilfr/Claude-Brain** and **javilfr/job-search** and say "Set up my job search": the kit installs in one step, and the files that chat sent you can be dropped in.
- **Meanwhile:** the brain's job-search capabilities are on `main` and work in any chat.

