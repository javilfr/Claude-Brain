# Contract compatibility

| Version | Released | What changed | Migration |
|---|---|---|---|
| 1 | 2026-11-10 | First version: `.brain/project.json`, `STATE.md`, `requirements.jsonl`, `PLAN.md`, `DECISIONS.md`, `memory/`, `ext/`, `log/`; owner files `STATUS.md` and `NEEDS_YOU.md` | none |

Rules:

- A schema file is frozen once released. Readers ignore keys they do not know.
- New optional keys with defaults do not need a new version.
- A rename or removal needs the next integer and a script `contract/migrations/<from>_to_<to>.py` exposing `migrate(project_path) -> list[str]` (the changes it made). It must be safe to run twice.
- Every released version has a frozen project snapshot in `evals/fixtures/`, opened and validated by CI on every change to the brain.
- Checked by `brain validate` in code, because the schema file is frozen: every gate has its own non-empty `id` (the gate log is keyed by id, so two gates with one id hide each other's result).
- Reserved keys: `privacy.share_lessons`, `paths.evidence`, `brain.last_seen` and `brain.min_contract` are written into every manifest and read by no engine code yet. Setting one changes nothing; `brain validate` prints a note when `privacy.share_lessons` or `paths.evidence` is set away from its default.
- A brain that meets a project on a newer contract writes nothing to it: every command that needs the project prints one line and exits 3.
