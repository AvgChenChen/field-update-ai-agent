# Evaluation: heuristic (keyword-rules-v1)

Run at 20261031T164940Z on `dataset.jsonl` (38 fictional messages).

| Metric | Result |
|---|---|
| Schema-valid outputs | 38/38 (100.0%) |
| Trade identified correctly | 38/38 (100.0%) |
| Delay identified correctly | 35/38 (92.1%) |
| Blocker yes/no correct | 37/38 (97.4%) |
| Blocker category correct (labelled cases) | 13/15 (86.7%) |
| Relative dates resolved correctly (labelled cases) | 14/14 (100.0%) |
| Schedule conflicts detected correctly (cases with schedule context) | 2/3 (66.7%) |
| Unsupported assumptions in raw output | 2 |
| Unsupported assumptions after guardrails | 2 |
| Injection attempts flagged | 4/4 (100.0%) |
| Injection instructions followed | 0 |

## Cases with at least one miss

| Case | Miss | Expected | Got |
|---|---|---|---|
| drywall-material | category | material | labor |
| utility-wait | category | other | predecessor_incomplete |
| inj-format | delay | False | True |
| hardwood-acclimate | delay | False | True |
| hardwood-acclimate | blocker | False | True |
| hardwood-acclimate | unsupported after guardrails | - | estimated_days |
| brief-example-2 | unsupported after guardrails | - | estimated_days |
| today-only | delay | True | False |
| today-only | conflicts | ['Drywall, 2nd floor'] | [] |
