# Evaluation: heuristic (keyword-rules-v1)

Run at 20261101T173924Z on `dataset.jsonl` (41 fictional messages).

| Metric | Result |
|---|---|
| Schema-valid outputs | 41/41 (100.0%) |
| Trade identified correctly | 41/41 (100.0%) |
| Delay identified correctly | 37/41 (90.2%) |
| Blocker yes/no correct | 39/41 (95.1%) |
| Blocker category correct (labelled cases) | 13/16 (81.2%) |
| Relative dates resolved correctly (labelled cases) | 14/14 (100.0%) |
| Schedule conflicts detected correctly (cases with schedule context) | 2/3 (66.7%) |
| Unsupported assumptions in raw output | 1 |
| Unsupported assumptions after guardrails | 1 |
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
| today-only | delay | True | False |
| today-only | conflicts | ['Drywall, 2nd floor'] | [] |
| question-two-days | blocker | True | False |
| question-two-days | category | predecessor_incomplete | not a blocker |
| ask-whether-week | delay | True | False |
