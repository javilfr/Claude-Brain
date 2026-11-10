# Contract fixtures

Frozen snapshots used by `tests/test_fixtures.py` and CI. They are the mechanical meaning of "projects keep working with the brain": every change to the brain must still open, validate and migrate each of them.

| Folder | What it is | Expected mode |
|---|---|---|
| `project-v1/` | A managed project on contract v1, mid-build | work |
| `unmanaged-app/` | An existing codebase with its own `CLAUDE.md` and no contract | adopt |
| `empty/` | A new repository with only a README | bootstrap |

Never edit a released snapshot. When the contract gets a new version, add `project-v2/` and keep `project-v1/`.
