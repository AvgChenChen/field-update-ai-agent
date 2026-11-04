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
- **Follow-up, same day:** the exact match removed *"finishes tonight"* with a half-day estimate, which had been accepted before. "Tonight" now supports anything up to one working day. "Today" gets no such tolerance, because *"couldn't finish today"* says when something happened, not how long it will take. Tests were committed first.

## 2026-11-03: A stated duration supported any delay estimate

- **What was wrong:** after the day-name fix, a duration said in words still counted as evidence for *any* `estimated_days`. *"Two more days"* kept an invented estimate of 5.
- **How the cause was found:** this was the known residual from the previous entry. Tests were committed first (`b78bb4b`): six contradicting estimates were kept on the old code. `vocab.stated_durations()` now reads each stated duration as a range of working days (digits and number words exactly, "a"/"another" = 1, "a couple of" = 2, "half a" = 0.5, "a few" = 2 to 4, a week = 5, hours = up to one day). `duration_supported()` keeps an estimate only if it falls inside one of them. Baseline evaluation results are identical on both sets, because the rule-based provider takes its estimate from the same stated number; the fix matters for model output.
- **Do differently:** when a fix covers one kind of evidence, write down which kinds it leaves, so the next fix has a test to start from.

## 2026-11-04: A truncated model reply returned 500 instead of a repair (AGT-006)

- **What was wrong:** when a provider itself raised `MalformedOutput` (a reply cut off at `max_tokens`, no text block, or an SDK parse failure), the extractor skipped the repair and the API returned HTTP 500. Invalid text returned by the provider was repaired and ended in a 502 as designed.
- **How the cause was found:** while drawing the sequence diagram for docs/EXTRACTION_FLOW.md. `provider.complete()` was called outside the `try` that catches `MalformedOutput`, so only errors from `_validate` were handled. A probe through the API with a scripted truncated reply returned 500 after one call. The call and the validation now happen together in `Extractor._attempt`, and tests cover a truncated first reply, a truncated repair, and the API's 502.
- **Do differently:** when an exception type can come from more than one place, check that every place that raises it is inside the handler. Tests had only scripted bad *text*, never a provider raising the error itself.

## 2026-11-04: A provider parse error could carry message text

- **What was wrong:** when the Anthropic SDK couldn't parse the model's answer into `ExtractionResult`, the provider raised `MalformedOutput(str(e)[:500])`. `str()` of a Pydantic `ValidationError` quotes the input (`input_value='Crew is out, call 416-555-0199'`), so fragments of the model's output, and through it the site message, ended up in the error text. That text is what the pipeline logs in `extraction_repair`, sends back in the repair prompt, and returns as the 502 `detail`. The README promises logs hold metadata only.
- **How the cause was found:** spotted while documenting the validate-and-repair loop (AGT-006). `_validate` already built its message from `e.errors()` as `loc: msg`; the provider used `str(e)`. Tests were committed first (`2584bd5`) and failed on the old code: the phone number appeared in the provider's error and in the error raised by `Extractor.extract`. Both now use one helper, `MalformedOutput.from_validation_error()`, which drops input values. Any other `ValueError` from the SDK is reported by type only. The OpenAI provider doesn't parse into the schema itself (the pipeline's `_validate` does), so it had no such path.
- **Do differently:** an error message is output too. Before passing a library's exception text on to logs, prompts or API responses, check what it quotes.
- **Follow-up, same day:** the helper still kept each error's location, and for a key the schema forbids, the location is the key the model invented: `{"call 416-555-0199": ...}` put the number in the repair prompt, the log and the 502. A test was committed first (`ea9bd67`). That key is now shown as `<unexpected field>`, after its parent path (`delay.<unexpected field>`), so the repair prompt still says where to look. `ExtractionResult` has no dict fields, so no other location comes from the model.

## Known residuals

- **Stated durations need an exact match, except "a few".** *"At least two days"* supports 2 but not 3, and in *"two or three days"* only "three days" is read, so an estimate of 2 is removed. Reading ranges and "at least" is the next step; until then a removed estimate becomes a follow-up question, not a wrong number.
- **Day names need an exact match.** Received on a Monday, *"back Thursday"* supports 3 days but not 2, although "back Thursday" could mean the crew loses Tuesday and Wednesday only. Allowing one day either side is the alternative. Exact was chosen because it's easier to reason about, and a removed estimate becomes a follow-up question, not a wrong number.
- **Past-tense day names resolve forward.** In *"Inspector came Monday, electrician is behind"* (received on a Monday), "Monday" resolves to next Monday, so an estimate of 5 is kept. Date resolution has always assumed day names point forward; telling past from future needs the verb tense.
- **Related, in construction-ops-platform:** `clientIp` trusted the leftmost `X-Forwarded-For` value. Fixed on 2026-11-03 (construction-ops-platform#7): it now reads the entry `TRUST_PROXY_HOPS` places from the right.
