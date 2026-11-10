---
name: brain-handover
description: Leave everything saved and pushed so a new chat can continue, and give the one line to paste. Use for "Hand over", "New chat", "Get ready to continue in a new chat", "context is running low", "Stop after this", or in Spanish "Pasa a un chat nuevo", "Prepara el relevo".
---

# Hand over

The owner changes chats often, usually because context is running out, and the most repeated complaint in his history is losing the thread when that happens. Offer a handover yourself when the session is long and quality may start to drop, rather than waiting to be asked.

## Goal

Nothing still running; the state checkpointed; the session closed; both repositories committed and pushed on their working branches; `BRAIN handover` reporting ready.

If the current item is close to finished, finish it; otherwise stop starting new work and leave it resumable. Wait for or stop every helper and background command, because nothing may still be writing when the chat ends. Commit the work itself on the project's working branch; unfinished work is pushed as a branch, never kept only in a temporary folder.

Order matters here:

1. `BRAIN handover --item <current id> --note "<what is half finished and where it lives>" --outcome ok`. It checkpoints, closes the session, pushes both repositories' records in the right order and prints the line to paste, naming the branch.
2. If it reports something, fix it and run `BRAIN handover` again.
3. `BRAIN handover` alone, run later, It writes `.brain/HANDOVER.md` and `STATUS.md`, commits and pushes the project's bookkeeping files itself, then checks both repositories and prints the line to paste. Fix what it reports and run it again; a repeat run passes once both are clean.

Ledger lines it counts as open go in the note, never into a claim of done.

## Tell the owner

Three lines at most: what is done, what the next chat will do first, and the line to paste, in a box he can copy. If anything could not be pushed, say so first.
