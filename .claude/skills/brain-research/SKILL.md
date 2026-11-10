---
name: brain-research
description: Research a question with sources and leave a memo. Use for "Go deep: …", "Research …", "Find out …", "Compare …", legal or technical questions where claims need sources, or in Spanish "Investiga …", "A fondo: …".
---

# Research

The outcome is an answer the owner can act on, with a source for every factual claim, facts kept apart from estimates, and a memo file a later session can reuse instead of researching again.

BRAIN means `python3 "${CLAUDE_SKILL_DIR}/../../../bin/brain"`.

## 1. Check what is already known

`BRAIN recall "<question>"` searches memory and earlier decisions. Search the project's `research/` folder too. If the answer is there and still current, use it and cite it.

## 2. Scope the question

Write the question as one sentence, what a useful answer looks like (a recommendation, a number, a yes or no with conditions), and how current it must be. For a size-0 question answer directly; use the full method only for "Go deep" or when the answer will drive a build.

## 3. Search

Split broad questions into independent sub-questions. Give each to a researcher agent only when the sub-questions are independent and each needs many pages; otherwise search yourself, sending independent searches together. Each brief carries the question, today's date, the memo path, and the return format.

Rules that hold throughout: primary sources and official documentation first; library, service and price facts from a current source, never from memory; for law, the article or ruling for each claim; numbers copied exactly; what could not be reached is recorded.

## 4. Synthesise

Write `research/<topic>.md`: the answer in the first five lines with a confidence level, the supporting findings with sources, contrary evidence, unknowns, and what was searched. Check the memo against `method/dod/research-memo.md`. Opus at medium effort is the right default for synthesis; more effort bought little on research in the measured curves.

## 5. Keep it

A fact that other projects will need goes to the learning inbox with its source: `BRAIN learn note` (see `--help`).

## Tell the owner

The answer and the two or three reasons, in plain words, then the memo path. In his language.
