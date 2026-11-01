# Development log

A dated, factual record of what went wrong and how it was fixed. Each entry covers what was
wrong, how the cause was found, and what to do differently next time.

All entries so far are **AI-assisted**: the review, diagnosis and fixes were done with Claude
Code, and the commits say so (`Co-Authored-By`). Entries are written after the fact; dates
are the commit dates.

## 2026-10-31: Non-ASCII API key returned 500 instead of 401 (#1)

- **What was wrong:** sending `X-API-Key: sécret` crashed `require_api_key` and returned HTTP 500.
- **How the cause was found:** reproduced by sending the header as raw latin-1 bytes. The traceback ended in `hmac.compare_digest`, which raises `TypeError` for non-ASCII `str` values. The fix compares UTF-8 bytes instead, and a regression test sends the same raw bytes.
- **Do differently:** treat every header as untrusted bytes. Test auth paths with malformed input, not just wrong-but-valid input.

## 2026-10-31: "Couldn't finish today" didn't flag tomorrow's dependent task (#2)

- **What was wrong:** a message mentioning only "today", with a dependent task planned for the next day, produced 0 conflicts. It should produce 1.
- **How the cause was found:** stepped through `detect_conflicts`. Every mentioned date was treated as the date the work would be done, so `max(dates)` was today, and nothing after today looked at risk. Only dates after the received date now count as completion constraints. An eval case (`today-only`) and conflict scoring were added, so the evaluation measures this and doesn't rely only on a unit test.
- **Do differently:** a date's meaning matters, not just its value. Label what each extracted date refers to before using it in a calculation.

## 2026-10-31: Store errors under concurrent requests (#3)

- **What was wrong:** with 3 writer and 3 reader threads sharing one `Store`, a short stress test raised 161 exceptions, including `NotFound` for rows written a moment earlier and `None` read back as a column value.
- **How the cause was found:** writes took the lock and reads didn't, while every thread shared one SQLite connection. FastAPI runs sync endpoints in a thread pool, so real traffic would interleave the same way. Every statement now runs under one re-entrant lock (`RLock`, because write methods call `get_update`). The stress test is now a pytest test that expects zero errors.
- **Do differently:** "SQLite is thread-safe" doesn't make a shared connection safe. Decide the concurrency model (one lock, or one connection per request) when adding the store, not after a stress test. The single lock serialises reads, which is fine at prototype scale.

## 2026-11-01: A duration that is only asked about was read as an estimate

- **What was wrong:** *"Can someone check if they need another day?"* produced `estimated_days = 1` in the rule-based baseline. The grounding guardrail would also keep an LLM's estimate, because "another day" appeared anywhere in the message. The evaluation already showed this as an unsupported assumption on `brief-example-2`.
- **How the cause was found:** both the baseline and the guardrail searched the whole message for duration words. Neither could tell a question from a statement. Tests were committed first and failed on the old code (`6cc4145`). `vocab.stated_text()` now drops direct questions and embedded ones ("ask them whether ..."), and both checks search only the statements. Prompt rule 2 gained the same rule, with `PROMPT_VERSION` 2026-11-01.1. Dev-set unsupported assumptions went from 2 to 1.
- **Do differently:** evidence checks should look at the right part of the text, not just whether a word appears anywhere. New eval cases written for this fix also exposed baseline misses it doesn't address (a question-shaped blocker, and a delay phrased with "hasn't finished").

## 2026-11-01: A day name supported any delay estimate

- **What was wrong:** the guardrail accepted any weekday or "tomorrow" in a statement as evidence for `estimated_days`. *"Back Thursday"* received on a Monday kept an estimate of 1 (or 40) just as readily as the correct 3.
- **How the cause was found:** the check asked *whether* duration evidence existed, never whether it agreed with the number. Tests were committed first: three contradicting estimates were kept on the old code (`e5ea247`). `guardrails.duration_supported()` now accepts a day word only when the estimate equals the working days from the received date to that day (`dates.working_days_between`). A duration said in words ("two more days") is still accepted. The evaluation now passes each case's received date to `count_unsupported` instead of using today. Baseline evaluation results are unchanged, because the rule-based provider only sets estimates from stated durations. The fix matters for model output.
- **Do differently:** an evidence check should compare the evidence with the value, not just find it.

## Known residuals

- **A stated duration supports any number.** "Two more days" still lets an estimate of 5 through. The next step is to parse the stated amount (as the baseline's `_estimate_days` does) and compare it, the way day names are compared now.
- **Related, in construction-ops-platform:** `clientIp` trusts the leftmost `X-Forwarded-For` value. That's only safe behind a proxy that overwrites the header; proxies that append to it (nginx `$proxy_add_x_forwarded_for`, most load balancers) leave that value client-controlled.
