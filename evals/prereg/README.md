# Pre-registrations

One file per change, `<change>.json`, written by `brain eval prereg` or `brain ablate` and committed before the first live trial. Fields: `change`, `hypothesis`, `metric` (pass | tokens | minutes), `direction` (up | down), `tasks`, `min_pairs` (at least 8), `decision` (`alpha`, `ship_prob`, `revert_prob`, `cost_guard`), `decision_text`, `created`.

Files here are never overwritten or edited: a revised candidate is a new change id, so the number of attempts stays visible. `brain eval compare --prereg <change>` refuses a run that uses tasks outside the file or whose first trial is older than `created`.
