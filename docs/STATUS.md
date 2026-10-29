# Status

What exists, what is proven, what is deployed, and what is not. This is the file to
trust when another doc disagrees.

Last updated: 28 October 2026.

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
| Format validity gate | `src/keel/format.py` | built, tested, fired 4 times |
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
| Space stress suite | `scripts/stress_space.py` | 48 checks, all passing on the live Space |

## Evidence

Thirteen checkpoints across four families, same panel and judge. Full table in
`results/SUMMARY.md`; per-request matrix in `docs/HARMFUL-MATRIX.md`.

| checkpoint | harmful compliance |
|---|---|
| Spark 1.1, 1.2, 1.3, Wonder, Spark Open | 0.00 to 0.03 |
| Glimmer base | 0.00 |
| M1 ablation | 0.81 |
| M2 code LoRA | 0.75 |
| derivative C (community ablation) | 0.19 |
| derivative D (community composite) | 0.06 |
| **Qwen 2.5 7B, ablated (non-Meta)** | **0.91** |
| **Qwen 2.5 7B, community abliteration** | **0.81** |
| **Mistral 7B, community abliteration** | **0.78** (base 0.41) |

Positive control: M1. Negative control: BF16 against 4-bit, 0.00 against 0.00. Invalid
positive: M2, which moved format and refusal together.

## The four refusals

1. Reasoning-versus-answer artifact: the first M2 card was wrong; re-scoring the answer
   segment corrected it.
2. Format collapse: five axes said no drift while 30 of 32 responses were code. Green
   became amber.
3. Missing harmful half: a green card without it is an overclaim; green is now capped.
4. Empty completions at `max_tokens=192`: the survey recorded an empty rate, so the
   invalid run was visible instead of published.

## Done since the last review

- The demo video: ten annotated scenes, hosted at `/demo.mp4` and linked from the hero and
  the guide.
- The submission text: written locally by cptlight and submitted directly. It is deliberately
  not in this repository.
- Canonical counts: thirteen checkpoints across four families, used in README, STATUS and
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
