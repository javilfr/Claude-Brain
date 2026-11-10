# Owner guide

## What this is

The Claude Brain is a repository you attach to every Claude Code chat next to the project you want built. It holds the method, helpers and memory that make Claude plan, build and check your project well, using as few tokens as it can. It learns from each project, and every change it makes to itself is a small, reviewable change you can undo with one click.

You only read files, click in a browser, or type in the chat. You never need a terminal.

## Starting a chat

1. Open Claude Code on the web (claude.ai/code) on your phone or computer.
2. Start a new session and select two repositories: **Claude-Brain** and your project. For a new project, first create an empty repository on GitHub and select that.
3. Pick the model. Opus 5.5 is the right choice for everyday work. Choose Fable 5.2 when you start a new project or something is genuinely hard. Keep one model per chat: switching makes Claude re-read everything at full price.
4. Type one of the phrases below, or just say what you want in your own words.

## What to type

| You type | What happens |
|---|---|
| **New project:** one sentence | The project is set up. You get at most three questions in one message, each with the answer used if you do not reply. Work starts straight away. |
| **Start running** / **Continue** / **set up** | Claude picks up exactly where the last chat stopped, without asking. |
| **Quick:** a question or small change | A direct answer or a small fix, with no planning. |
| **Go deep:** a question | A researched answer with sources, saved as a memo. |
| **Status** | Where things stand, what is next, and what it has cost, in a few lines. |
| **Hand over** | Everything saved and pushed, and one line to paste into a new chat. |
| **What did you learn?** | The new lessons and changed rules since you last asked. |
| **Go back** | Returns the project to its last version you accepted. |
| **Stop after this** | Finishes the current piece of work, saves, and summarises. |

The phrases work in Spanish too ("Nuevo proyecto: …", "Continúa", "Estado"). Claude replies in the language you write in.

## The three files you read

All are in your project repository on GitHub:

- **STATUS.md**: what is done, what is next, what it cost, and what was learned. Short enough for a phone screen.
- **NEEDS_YOU.md**: the few things only you can do (an account, a key, a payment), as numbered click steps. Work never waits on these.
- **.brain/DECISIONS.md**: one line per choice Claude made on your behalf. To reverse one, edit the line on GitHub and write **OVERTURNED** with what you want instead. The next chat applies it.

In the brain repository, **learning/CHANGELOG.md** lists in plain words what the brain has learned.

## Answering questions

Just reply in the chat; Claude records your answer in the right file. You can also edit NEEDS_YOU.md on GitHub and add **RESOLVED:** to an item. If you do not answer, the stated default is used and recorded, so you can change it later.

When Claude needs an API key, it shows a secure form. Paste keys only there, never in the chat. If a key does end up in the chat, replace it with a new one from the provider's website.

## What things cost and where to see it

STATUS.md shows tokens used and their list-price equivalent, for the latest chat and the project so far. On your subscription you are not charged those dollars; the real limit is your plan's usage window, and the figures show how fast work uses it. Fable 5.2 and fast mode may draw on usage credits rather than plan limits, so both are kept for when they are worth it. Claude runs at most four helpers at once unless you ask for more; wide fan-out has used up usage windows before.

Returning to a chat within an hour is cheaper than after a long break.

## Undoing something the brain learned

Each learning change arrives as one pull request on the Claude-Brain repository on GitHub, described in plain words. To undo it, open that pull request and press **Revert**, then merge the revert. 

## If something seems broken

Type **Repair the brain** in a chat with the brain attached. Claude runs the brain's self-checks, explains the problem plainly, and if needed restores the brain's last known-good version. Your projects are not touched.

If a chat says another chat is working on the same project, close the other chat or tell Claude which one continues.

If an app does not show your latest changes, type **Status**: the first line says whether the live site serves the new version, and if not, what to click.
