# Data

Generated from `data.jsonl` by the learning pipeline. Do not edit by hand.

## Accuracy

- Keep claims within what the data supports: no correlation stated as cause, sample sizes shown, and no figure that misleads (a raw count where a rate is what matters). The owner has rejected a misleading count before. `data-claims-in-bounds`
- Profile input before analysis: row counts, date ranges, duplicates, missing values, units. Put the results in the report so the reader can judge the data. `data-profile-input`
- Recompute each headline number a second way (for example a loop against a grouped query) and compare. A mismatch is a defect to explain, not a rounding note. `data-reconcile`

## Cost

- Process large data through scripts, never by pasting it into the conversation. In Anthropic's test a 1,862-row table pasted into a prompt scored 7 of 25; queried through code it scored 25 of 25 at a fraction of the cost. `data-through-code`

## Integration

- Test every outside-service call with a recorded fixture and a simulated quota or rate-limit error. Quota errors from speech and weather services appeared in past projects; the code must switch source or write a NEEDS_YOU item, not fail silently. `data-fixtures-and-quota`
- Cache outside-service responses on disk, keyed by the request, and read from the cache in tests and re-runs. It saves quota and makes runs repeatable. `data-cache-calls`
- Put each outside data source behind a small interface, so a second source can replace it when one fails, changes price or runs out of quota. `data-source-interface`

## Owner

- Run a small sample (one lesson, one page, one region) and show it to the owner before a full or paid run. It catches a wrong voice, format or source cheaply. `data-sample-first`

## Reliability

- Long harvests write results to disk as they go and can resume from the last saved point, so a rate limit or a session end costs minutes, not the run. `data-incremental-writes`

## Reproducible

- Every number and chart in a report comes from one script that rebuilds it from raw input. Deliver the script with the report and re-run it clean before delivery. `data-one-script`
- Record random seeds, source versions and the date of each data pull, so a later re-run can be compared with the first. `data-record-seeds`

## Secrets

- Ask for API keys through the secure credential form, or add a NEEDS_YOU item with the clicks to store the key in the environment's settings. Never write a key into a file, commit, log or reply; if one is pasted in chat, do not repeat it and suggest rotating it. Keys were pasted into chat three times in past projects. `data-keys-form`
