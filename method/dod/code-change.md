# Definition of done: Code change

Read before reporting any code change done. Each item is yes or no, with evidence where it says so.

- [ ] For a bug: was the failure reproduced first (a failing check), and does the same check now pass?
- [ ] Does every ledger line this change serves have a check that ran, with its evidence recorded?
- [ ] Did the full gate (`BRAIN gate --all`) record exit 0 after the last edit?
- [ ] Is no test skipped, deleted or weakened, unless a ledger line gives the reason?
- [ ] Are there no TODO stubs, placeholders or fake implementations in shipped code?
- [ ] Was every new library call or dependency checked against current documentation, and does it resolve?
- [ ] Does the diff touch only files a ledger line explains?
- [ ] Does the report list behaviour changes from the diff, including small ones?
