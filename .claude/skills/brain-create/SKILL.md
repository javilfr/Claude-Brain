---
name: brain-create
description: Diverge-then-choose creative pass for anything where taste decides: names, icons, palettes, layouts, landing pages, voice, story structure. Use for "Propose options", "Give me 5 …", "Design …", "Propón opciones", "Dame 5 …". Not for bug fixes or data work.
---

# Create

Creative quality comes from generating real alternatives and choosing well, not from asking for "creative" output. Left alone, a model converges on its defaults. The outcome is one strong direction, built fully, or a short menu the owner picks from.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## 1. Brief

In about 150 words: the audience, the one job or feeling the piece must achieve, hard constraints from the ledger, and the named defaults to avoid for this medium. Name them specifically (for a screen: system fonts, purple gradients on white, pill buttons everywhere, "01/02/03" labels; for prose: stock openers, rule-of-three padding, a closing summary that restates the body). "Avoid a generic look" only swaps one default for another. `BRAIN recall "<medium> defaults to avoid"` returns the list learned so far.

## 2. Diverge

In one call, write five sketches of about 40 words each, each built on a different starting constraint: a different reference world, a different structural rule, a different stance toward the audience. Vary the constraint, not the adjectives. Include at least two you judge unusual.

## 3. Choose blind

Score the sketches against the brief without favouring your first idea: fits the brief, avoids the named defaults, distinct from the obvious answer, feasible. Pick one; you may graft one named element from the runner-up.

## 4. Expand only the winner

Full effort goes to one build.

## When taste decides, the owner chooses

For icons, names, palettes and layouts he wants a numbered menu, usually five, each with an image and a one-line description. Render the options as images (screenshots or generated files) so he can judge on his phone. Then apply his choice everywhere it is used.

## Facts stay fixed

The creative pass changes form, framing, structure and visual language. It never changes facts, numbers, dates, names or legal content; those come from the facts file and sources.

## Tell the owner

The numbered options with images, or the chosen direction in two lines and where to see it.
