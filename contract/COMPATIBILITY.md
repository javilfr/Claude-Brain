# Contract compatibility

| Version | Released | What changed | Migration |
|---|---|---|---|
| 1 | 2026-11-10 | First version: `.brain/project.json`, `STATE.md`, `requirements.jsonl`, `PLAN.md`, `DECISIONS.md`, `memory/`, `ext/`, `log/`; owner files `STATUS.md` and `NEEDS_YOU.md` | none |

Rules:

- A schema file is frozen once released. Readers ignore keys they do not know.
- New optional keys with defaults do not need a new version.
- A rename or removal needs the next integer and a script `contract/migrations/<from>_to_<to>.py` exposing `migrate(project_path) -> list[str]` (the changes it made). It must be safe to run twice.
- Every released version has a frozen project snapshot in `evals/fixtures/`, opened and validated by CI on every change to the brain.
