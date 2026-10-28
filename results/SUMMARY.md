# Model survey

Every text model in the hackathon list, run through the same 32 panel probes and
the same 32 harmful prompts, judged by a separate checkpoint (Spark Open on
Baseten). Harmful completions are not published; only statistics are.

| model | panel code | panel refusals | panel empty | harmful compliance | 95% CI | judged | harmful refusal phrase | median chars |
|---|---|---|---|---|---|---|---|---|
| muse-spark-1.1 | 19% | 28% | 0% | 0% | [0.00, 0.00] | 32/32 | 100% | 1194 |
| muse-spark-1.2 | 16% | 19% | 0% | 0% | [0.00, 0.00] | 32/32 | 91% | 1458 |
| muse-spark-1.3 | 19% | 38% | 0% | 0% | [0.00, 0.00] | 32/32 | 100% | 369 |
| muse-wonder-1.0 | 12% | 25% | 0% | 3% | [0.00, 0.00] | 32/32 | 91% | 872 |
| meta-models/muse-spark-open | 22% | 19% | 0% | 0% | [0.00, 0.00] | 32/32 | 84% | 1727 |

## Not applicable to this scan

Muse Image, Muse Voice Transcribe and SAM 3.1 are generation, transcription and
segmentation models. They do not answer text probes, so a text checkpoint scan
does not apply to them. Forcing them into one would be a category error.

## Reproduction

```console
$ python scripts/suite.py --out results
$ python scripts/publish_results.py --results results/results.json
```

Settings: greedy, 192 new tokens, `reasoning_effort=low`, judge prompt fixed in
`scripts/suite.py`. Model ids are recorded per row.
