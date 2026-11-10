# Definition of done: App or feature

Read before reporting an app or feature done. Includes everything in `code-change.md`.

- [ ] Does it build and run from a clean clone with the one documented command?
- [ ] Does an end-to-end check cover the main journey plus the empty, error and offline states?
- [ ] Where data is stored or transformed, is there a round-trip or run-twice test?
- [ ] Are the project's budgets met (bundle size, load time), measured on a quiet machine?
- [ ] If data is migrated, was a backup taken and a restore tested first?
- [ ] Were screenshots taken at phone size and desktop size, and looked at?
- [ ] If the project releases from `main`: did `BRAIN release --run-gates --push` push, and did its live check pass?
- [ ] Has the owner been told the address and what to check on his phone?
