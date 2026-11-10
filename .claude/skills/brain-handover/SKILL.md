---
name: brain-handover
description: Leave everything saved and pushed so a new chat can continue, and give the one line to paste. Use for "Hand over", "New chat", "Get ready to continue in a new chat", "context is running low", "Stop after this", or in Spanish "Pasa a un chat nuevo", "Prepara el relevo".
---

# Hand over

The owner changes chats often, usually because context is running out, and the most repeated complaint in his history is losing the thread when that happens. The outcome: both repos committed and pushed, no helpers still running, a handover file, and one line he can paste into a new chat.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

Offer a handover yourself when the session is long and quality may start to drop, rather than waiting to be asked.

## Steps

1. Stop starting new work. Finish the current item if it is close; otherwise leave it in a state that can be resumed and say exactly what is half done.
2. Wait for or stop every running helper and background command. Nothing may still be writing when the chat ends.
3. `BRAIN checkpoint --item <current> --next <ids>` with notes on anything half finished and where it lives.
4. `BRAIN req check` to show which ledger lines still lack evidence; they go into the handover, not into a claim of done.
5. `BRAIN handover` writes `.brain/HANDOVER.md`, refreshes `STATUS.md`, and prints the line to paste.
6. Commit and push the project on its working branch. Unfinished work is pushed as a branch, never only kept in a temporary folder. Push the brain's learning inbox if `close` wrote to it (run the brain-learn skill's close step first).
7. Check `git status` is clean in both repos and that the pushes succeeded.

## Tell the owner

Three lines at most: what is done, what the next chat will do first, and the line to paste, in a box he can copy. Reply in his language. If anything could not be pushed, say so first.
