# Evaluation: heuristic (keyword-rules-v1)

Run at 20261031T160750Z on `dataset.jsonl` (37 fictional messages).

| Metric | Result |
|---|---|
| Schema-valid outputs | 37/37 (100.0%) |
| Trade identified correctly | 37/37 (100.0%) |
| Delay identified correctly | 35/37 (94.6%) |
| Blocker yes/no correct | 36/37 (97.3%) |
| Blocker category correct (labelled cases) | 13/15 (86.7%) |
| Relative dates resolved correctly (labelled cases) | 13/13 (100.0%) |
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
