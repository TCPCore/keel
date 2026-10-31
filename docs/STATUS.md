# Status

What exists, what is proven, what is deployed, and what is not. This is the file to
trust when another doc disagrees.

Last updated: 31 October 2026.

## Deployed

| link | what it is |
|---|---|
| https://tomscot-keel.hf.space | the Space: fleet table, card grid, verify, tamper test, scan your own |
| https://github.com/TCPCore/keel | the repository |

## Components

| component | path | status |
|---|---|---|
| Card and verdict rules | `src/keel/report.py` | built, tested |
| Drift statistics | `src/keel/stats.py`, `drift.py` | built, tested |
| Format validity gate | `src/keel/format.py` | built, tested, caught five documented failures |
| Program and judge scorers | `src/keel/scorers.py` | built, tested |
| Offline scan | `src/keel/scan.py`, `keel scan` | built, tested |
| Policy seam | `src/keel/policy.py`, `keel policy` | built, tested |
| Label ledger | `src/keel/ledger.py`, `keel ledger` | built, tested |
| Card signing | `src/keel/sign.py`, `keel sign` | built, HMAC, tested |
| Service and webhook | `src/keel/serve.py`, `keel serve` | built, exercised locally |
| Ecosystem watcher | `src/keel/watch.py`, `keel watch` | built, run against HF |
| Batch | `keel batch` | built, tested |
| Space app | `space/app.py` | deployed on HF |
| Modal deployment | `scripts/modal_space.py` | deployed, fallback |
| Repro verifier | `scripts/verify_repro.py` | passes |
| Reviewer bundle | `scripts/build_bundle.py`, `/bundle.zip` | built, hashes verified |
| Space stress suite | `scripts/stress_space.py` | 70 checks, all passing on the live Space |

## Live experiment

- A GPU worker runs the 7B base-versus-ablated experiment on demand: 32 probes and 32
  harmful requests, judged and carded in about twelve minutes for roughly $0.30. One
  run per address per hour, capped at twenty runs in total. Verified live on 30 Oct; the
  frozen-contract number for this ablation is 0.97 (qwen-ablated card).

## Replay

- Weight-space recovery is the result: coverage 1.000 in o_proj/down_proj, reconstruction
  exact to bfloat16, per-module lambda non-uniform (1.28 and 0.22 in the checked modules).
  Behavioural replay precondition not met (0.032 vs 0.084). Recorded in REPLAY.md and
  RESULTS.md, carried on the derivative C card as `recovered_lambda`.
- Gate 1 passed on 30 October: a known per-module intensity is recovered exactly from
  the weight delta on a real Glimmer matrix, with and without the known direction.
- Gate 3 was run twice. Derivative C gave a degenerate pass (0.084 vs 0.000, tolerance
  0.15, a no-op would pass). The revised M1 weight-edit target scored 0.000 under the
  frozen judge, below the pre-registered 0.20 decidability floor, so the gate is
  undecidable. No closure is claimed. The finding is that weight-space interventions move
  reasoning rather than answers, which is why an answer-only contract cannot see them.

## Withdrawn

- Derivative D, 29 October. Its committed panel was byte-identical to derivative C's,
  so its card had been computed from another model's responses. The fleet row, the
  card, the bundle entry and the manifest hash were removed rather than republished.

## Evidence

Twelve checkpoints across four families, same panel and judge. Full table in
`results/SUMMARY.md`; per-request matrix in `docs/HARMFUL-MATRIX.md`.

| checkpoint | harmful compliance |
|---|---|
| Spark 1.1, 1.2, 1.3, Wonder, Spark Open | 0.00 to 0.03 |
| Glimmer base | 0.00 |
| M1 ablation | 0.16 |
| M2 code LoRA (invalid positive) | 0.34 |
| derivative C (community ablation) | 0.09 |
| Qwen 2.5 7B, ablated (non-Meta) | 0.97 |
| Qwen 2.5 7B, community abliteration | 0.78 |
| Mistral 7B, community abliteration | 0.81 (base 0.44) |

Positive control: M1. Negative control: BF16 against 4-bit, 0.00 against 0.00. Invalid
positive: M2, which moved format and refusal together.

## The five refusals

1. Reasoning-versus-answer artifact: the first M2 card was wrong; re-scoring the answer
   segment corrected it.
2. Format collapse: five axes said no drift while 30 of 32 responses were code. Green
   became amber.
3. Missing harmful half: a green card without it is an overclaim; green is now capped.
4. Empty completions at `max_tokens=192`: the survey recorded an empty rate, so the
   invalid run was visible instead of published.
5. Judge and extractor drift: the same Glimmer ablation scored 0.81 under a retired judge,
   0.59 under its successor, and 0.16 under the frozen answer-only contract with a
   format-aware extractor. The re-score button caught the first jump, and the extractor bug
   caught the rest.

## Done since the last review

- The demo video: ten annotated scenes, hosted at `/demo.mp4` and linked from the hero and
  the guide.
- The submission text: written locally by cptlight and submitted directly. It is deliberately
  not in this repository.
- Canonical counts: twelve checkpoints across four families, used in README, STATUS and
  the Space.

## Not done

- A deterministic judge. Hosted Spark Open moves between 25 and 26 of 32 on repeats.
- The queue runner at scale: `watch` ranks, but downloading and generating is manual.
- Signed cards in the Space; the verifier is local.

## Commands that work

```console
$ keel selftest
$ keel demo
$ keel scan --reference-responses base.jsonl --candidate-responses cand.jsonl --out cards/x
$ keel policy --card cards/x/drift-card.json
$ keel ledger add --card cards/x/drift-card.json --model-id org/x
$ keel watch --query muse-glimmer
$ keel batch --reference base.jsonl --candidates dir/
$ keel sign --card cards/x/drift-card.json
$ keel serve --root . --port 8000
$ python scripts/verify_repro.py
```
