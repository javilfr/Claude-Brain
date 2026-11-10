# Operations

Generated from `operations.jsonl` by the learning pipeline. Do not edit by hand.

## Automation

- Give every automation a dry-run mode that prints what it would change, and read that output before the first real run. `ops-dry-run`
- Make every script and migration safe to run twice: a second run changes nothing. Sessions end mid-step, and re-running is then the recovery. `ops-run-twice`
- Check a deployment or job a bounded number of times, then report plainly with click steps. An earlier project polled hourly for a day and a half while the site still showed a 404. `ops-bounded-polling`
- Test the failure path of a scheduled job (bad input, timeout, missing key) and make sure the owner sees the failure somewhere he looks, without a terminal. `ops-failure-notice`
- Deliver each automation with a one-page guide: what it does, when it runs, where to see results, how to switch it off, and how to undo it. `ops-one-page-guide`
- A scheduled routine starts with no memory: its prompt must be complete on its own, and its only continuity is the project's state file. `ops-self-contained-routine`
- Chain steps so a failure stops the rest (`&&`, or a script that checks exit codes), never `;`. A `;` chain once pushed a red build to main. `ops-stop-on-failure`

## Cost

- Do not leave check-in loops or scheduled tasks running without a purpose: each firing re-sends the whole context and draws on the owner's usage. `ops-no-idle-loops`

## Owner machine

- For steps on the owner's own computer, give one copy-and-paste box per step and say what it should print. Explain any error he pastes back in one sentence, and prefer a browser route when one exists. `ops-paste-box`
- When the owner says he is done, stop every process and helper this session started, and list what was stopped. `ops-close-everything`

## Research

- Before building for a device or service the owner names, research the path and write a short feasibility note saying which steps need another computer or a paid service. `ops-feasibility-first`
