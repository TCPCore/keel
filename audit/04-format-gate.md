# Audit record - 04-format-gate

- **Task brief:** `muse/04-format-gate.md`
- **Muse Code session:** `01a17d50-2afa-7662-ac3b-d1009207a950`, model `muse-spark-1.3`,
  effort `high`
- **Reviewed by:** OSS agent
- **Owner sign-off:** `Audited-by: cptlight` on the commit
- **Date:** 2026-10-27

## Diff

```
 src/keel/format.py    | 100 ++++++++++++++++++
 tests/test_format.py  | 146 +++++++++++++++++++++++
 src/keel/report.py    |  22 +++-
 scripts/score_pair.py |   8 ++-
```

Files are within the brief: two created, two permitted modifications.

## What was checked

- [x] The heuristic is structural, not keyword based. A prose sentence that mentions
      `def` or `function` does not match; a fenced block, or a `def` / `import` /
      `from ... import` / `class` at the start of a line, does.
- [x] The failure mode is documented: indented snippets without a keyword-led line are
      missed, and prose quoting a fence can false-positive. Precision is preferred over
      recall because a false positive invalidates a healthy card.
- [x] `code_rate` handles a mapping, a sequence, and an empty input without raising.
- [x] `format_shift` names both rates, so the reason is usable in a card.
- [x] `Card` defaults keep old cards and old tests working.
- [x] The override escalates only: green becomes amber, red stays red. Tested both.
- [x] Round-trip through `to_dict` / `from_dict` preserves validity.

Verified against the real data from the M2 run:

```
SUSPECT   code rate 6% reference vs 91% candidate (delta 84%, threshold 30%)
```

The gate would have caught the collapse that the five axes missed.

## Correction made

**The warning reached the JSON but not the card a human reads.** Muse added `validity`
to `Card.to_dict` and `from_dict` and to the verdict override, but `render_markdown`
and `render_text` never printed it. A card that says AMBER with no explanation is
exactly the failure this task exists to prevent, so review added a `MEASUREMENT
SUSPECT` banner to both renderers with the reason inline.

No other changes were needed. The module passed review as generated.

## Residual risks

- **The heuristic is a proxy.** It detects code-shaped answers, not instruction
  following in general. A model that answers every question with a bulleted list would
  pass it.
- **The threshold is a judgement.** 30 percent is chosen so ordinary per-probe
  variation does not trip it; a smaller real shift would pass. The reason string always
  prints both rates, so the reader can disagree with the threshold.
- **The gate does not fix the measurement.** It marks the card suspect. The next scan
  still needs a candidate whose format is comparable to the reference.

## Verdict

- [x] Approved with the rendering correction.
- [x] Ready to re-run the M2 card, and to gate every future scan.
