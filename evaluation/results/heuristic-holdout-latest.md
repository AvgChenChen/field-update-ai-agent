# Evaluation: heuristic (keyword-rules-v1)

Run at 20261031T165331Z on `holdout.jsonl` (14 fictional messages).

| Metric | Result |
|---|---|
| Schema-valid outputs | 14/14 (100.0%) |
| Trade identified correctly | 12/14 (85.7%) |
| Delay identified correctly | 8/14 (57.1%) |
| Blocker yes/no correct | 11/14 (78.6%) |
| Blocker category correct (labelled cases) | 2/7 (28.6%) |
| Relative dates resolved correctly (labelled cases) | n/a |
| Schedule conflicts detected correctly (cases with schedule context) | n/a |
| Unsupported assumptions in raw output | 0 |
| Unsupported assumptions after guardrails | 0 |
| Injection attempts flagged | 1/1 (100.0%) |
| Injection instructions followed | 0 |

## Cases with at least one miss

| Case | Miss | Expected | Got |
|---|---|---|---|
| h-sparky | trade | electrical | None |
| h-sparky | delay | True | False |
| h-sparky | category | predecessor_incomplete | other |
| h-tile-colour | trade | flooring | None |
| h-tile-colour | delay | True | False |
| h-tile-colour | blocker | True | False |
| h-tile-colour | category | material | not a blocker |
| h-painter-noshow | delay | True | False |
| h-painter-noshow | blocker | True | False |
| h-painter-noshow | category | labor | not a blocker |
| h-snow | delay | True | False |
| h-snow | blocker | True | False |
| h-snow | category | weather | not a blocker |
| h-island | delay | True | False |
| h-returns | category | predecessor_incomplete | other |
| h-permit | delay | True | False |
