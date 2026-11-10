# Frozen items for the recall measurements

A copy of the brain's item files as they were on 2026-11-10 (141 seed items, nothing learned yet), laid out like the brain so `items.load_items(<this folder>)` reads it.

The labelled queries in `evals/recall_golden.jsonl` are measured on these files, never on the live `memory/`, `owner/` and `playbooks/`: a lesson that is learned, promoted or retired must not turn the test suite red (findings learning-12 and redteam-09). Learning never writes here. Replace the copy only to re-baseline on purpose, and re-measure the pinned figures in `tests/test_recall.py` and `tests/test_r4_m.py` in the same change.

Rows of `recall_golden.jsonl`: `query`, `relevant` (ids; empty for a query memory has no answer to), `split` (`dev` or `heldout`), and for the sets added on 2026-11-10 `lang` (`es` or `en`), `style` (`dictated`) and `twin` (the English query with the same answer). Tune on `dev` only.
