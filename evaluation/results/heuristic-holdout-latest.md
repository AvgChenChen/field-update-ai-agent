# Evaluation: heuristic (keyword-rules-v1)

Run at 20261105T103518Z on `holdout.jsonl` (24 fictional messages).

| Metric | Result |
|---|---|
| Schema-valid outputs | 24/24 (100.0%) |
| Trade identified correctly | 18/24 (75.0%) |
| Delay identified correctly | 13/24 (54.2%) |
| Blocker yes/no correct | 18/24 (75.0%) |
| Blocker category correct (labelled cases) | 6/14 (42.9%) |
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
| h-cc-sparky-meter | trade | electrical | None |
| h-cc-sparky-meter | delay | True | False |
| h-cc-tile-typos | trade | flooring | None |
| h-cc-wall-moved | trade | plumbing | framing |
| h-cc-wall-moved | delay | True | False |
| h-cc-gate-code | delay | True | False |
| h-cc-gate-code | blocker | True | False |
| h-cc-gate-code | category | access | not a blocker |
| h-cc-roof-wind | delay | True | False |
| h-cc-roof-wind | blocker | True | False |
| h-cc-roof-wind | category | weather | not a blocker |
| h-cc-mudders | trade | drywall | None |
| h-cc-pump-truck | delay | True | False |
| h-cc-pump-truck | blocker | True | False |
| h-cc-pump-truck | category | other | not a blocker |
