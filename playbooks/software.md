# Software

Generated from `software.jsonl` by the learning pipeline. Do not edit by hand.

## Debug

- Fix a bug by first making it fail with a check, then fixing it, then showing the same check pass. The red-then-green pair is the evidence; a fix with no reproduced failure may fix nothing. `sw-reproduce-first`

## Dependencies

- Take library and API behaviour from current documentation for the installed version, not from memory, and check that every new dependency resolves. Generated code often names packages or methods that do not exist. `sw-current-docs`

## Integration

- When a credential or paid account is missing, build against a local stand-in behind an interface and write a NEEDS_YOU item with click steps. Work never waits, and switching to the real provider becomes configuration, not code. `sw-stand-ins`

## Release

- An app release is done only when the live address serves the new version. A deploy-only crash once escaped the local gate, and another project showed a 404 for a day and a half because the work stayed on a branch. `sw-live-check`
- Update main only through `brain release --run-gates --push`: it pushes only when every gate recorded exit 0 on this commit and never force-pushes; without `--push` it only reports. In an earlier project two pushes reached main without a green check, one chained with `;` after a failing test run. `sw-release-command`
- Before a release, build from a clean clone with the one documented command. It catches files and settings that exist only on the working machine. `sw-clean-clone`
- Ship small verified increments the owner can see rather than one large release. He judges progress by what is live on his phone, and small releases make a bad change easy to find and revert. `sw-small-releases`
- Record which release the owner accepted as known-good (each release is logged in `.brain/log/releases.jsonl`), so "Go back" can revert to it in one step without a force-push. After long iteration the owner once asked to return to an earlier state because quality had dropped. `sw-tag-known-good`

## Repo

- Keep screenshots, videos and other large binaries out of git history by default: store evidence outside the repo, or keep only the latest downscaled set. An earlier project committed 390 MB of review screenshots that every new session had to clone. `sw-no-binaries-in-git`

## Tests

- Do not skip, delete or loosen a test to get a pass. A wrong test is reported with the reason and changed as its own item; the gate flags added skip markers and stubs in the diff, but not deleted tests, so a reviewer checks for those. `sw-test-integrity`
- Test fixtures hold at least two of everything (two records, two users, two items). In an earlier project, tests written against one sample produced 17 end-to-end failures when a second sample was added. `sw-two-of-everything`

## Verify

- When the test suite blocks a component on purpose (maps, video, third-party widgets), say so in the report and check that surface by screenshot. A green suite is necessary, not sufficient. `sw-blocked-surfaces`
- Run timing and performance gates when no helpers are working, and re-run a failed one alone before calling it red. A release was once blocked at 2,652 ms against a 2,600 ms budget only because other agents shared the processor. `sw-quiet-timing`

## Visual

- Check anything visual by looking: screenshots at phone width (about 390 px) and desktop width (about 1440 px) for each state the spec lists, looked at before reporting done. In an earlier project tests passed while the owner found blank maps and an invisible cover on his phone. `sw-phone-screenshots`
