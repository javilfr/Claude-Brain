# Definition of done: Automation

Read before delivering a scheduled job, script or routine.

- [ ] Was a dry run read, and did a real run on a safe target succeed?
- [ ] Is it safe to run twice: does a second run change nothing?
- [ ] Was the failure path tested (bad input, timeout, missing credential), giving a clear error and no partial damage?
- [ ] Are steps chained so a failed step stops the rest?
- [ ] Are the schedule, time zone and next run times stated?
- [ ] Can the owner see success or failure without a terminal?
- [ ] Are the off switch and the undo steps written down, with no secrets in files?
- [ ] For steps on the owner's own machine: is each step one copy-and-paste box?
