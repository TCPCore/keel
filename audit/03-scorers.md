# Audit record - 03-scorers

- **Task brief:** `muse/03-scorers.md`
- **Muse Code session:** `01a17c27-06e3-7553-b900-1a38b45afca8`, model `muse-spark-1.3`,
  effort `high`
- **Reviewed by:** OSS agent
- **Owner sign-off:** `Audited-by: cptlight` on the commit
- **Date:** 2026-10-27

## Diff

```
 src/keel/scorers.py   | 543 +++++++++++++++++++++++++
 tests/test_scorers.py | 328 ++++++++++++++++++++++++
```

Two files, both permitted. No existing file was modified.

## What was checked

- [x] No silent default score on any path. Every failure raises `ScoringError` with the
      probe id and a bounded excerpt.
- [x] `Score.__post_init__` validates range through `_checked_value`, so an invalid score
      cannot be constructed even if a caller bypasses a scorer.
- [x] Refusal matching is start-anchored and uses multi-word idioms, so "I cannot stress
      enough how useful this is" scores 0.0. This was the specific trap in the brief.
- [x] Program flags are worded as commitments to the bad act, not bare nouns, so a safe
      response that names the act in order to decline it does not fire.
- [x] The judge sends `tools` and a forced `tool_choice`, parses
      `choices[0].message.tool_calls[0].function.arguments`, accepts either a dict or a
      JSON string, and raises on missing call, malformed JSON, non-numeric, or non-finite.
- [x] Clamping happens only after parsing, so it cannot mask a parse failure.
- [x] No network in tests; the fake client records what was sent and replays canned raw
      payloads.

## Corrections made

1. **The judge could exhaust its budget before emitting the tool call.** The client
   default is 512 completion tokens with no effort setting. The judge is a reasoning
   model that does not support structured outputs, so the tool call has to fit after
   whatever thinking it does. Measured earlier in the session, default effort used 400+
   tokens on a one-line answer, which makes 512 a coin flip. `JudgeScorer` now defaults
   to `max_tokens=1024` and `reasoning_effort="low"`, with `reasoning_effort=None` for a
   model that rejects the parameter.
2. **Added two tests** to lock that in: the budget is at least 1024 with effort "low",
   and the parameter is omitted when it is set to None.

No other implementation changes were needed.

## Residual risks

- **Rule-based refusal detection is narrow by construction.** It sees stereotyped
  openings only and will miss polite or indirect refusals. The docstring says so, and
  the reference rate is reported per axis rather than hidden.
- **Program flags are brittle in both directions.** A euphemism slips past; a phrase
  that appears in a refusal could fire. The lists are deliberately small, and the axes
  that need judgement stay with the judge.
- **The judge has not been calibrated against gold scores.** The rubric is plausible but
  unvalidated. Before any number is published, a small set of human-scored responses
  should be run through it and the agreement reported.
- **Judge cost is real.** It is the only scorer that spends tokens, which is why the
  panel keeps the programmatic share high.

## Verdict

- [x] Approved with the budget correction and two added tests.
- [ ] Judge calibration against gold responses, before the first published card.
