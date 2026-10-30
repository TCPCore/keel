# Keel

**A checkpoint validity harness for open-weight models.**

`keel scan` compares a derivative against its base and returns a card: what moved, whether
the measurement was valid, what the harmful half says, and, when weights are available,
the structural signature of the intervention. Exit codes make it a CI gate.

- Live demo: **https://tomscot-keel.hf.space**
- Demo video: **https://tomscot-keel.hf.space/video** (also [on YouTube](https://youtu.be/FvseA22YEDo))
- Run it live (7B, about 12 min): **https://tomscot-keel.hf.space#live**
- Scan your own checkpoint: **https://tomscot-keel.hf.space#scan**
- Reviewer access and hashes: **https://tomscot-keel.hf.space#access**
- Current state, including gaps: [docs/STATUS.md](docs/STATUS.md)
- Docs map: [docs/INDEX.md](docs/INDEX.md)

## What it does

1. **Measures drift** between a checkpoint and its base on 32 probes across five axes,
   with paired bootstrap intervals and Benjamini-Hochberg correction.
2. **Refuses to certify an invalid measurement.** A response-format collapse turns green
   into amber. A card without the harmful half cannot be green. An empty-response rate is
   recorded, not ignored.
3. **Records the label state.** A card becomes `pending`, `verified`, `review` or
   `recalled`, and a recall is sticky until a human clears it.

## Evidence

Same panel, same judge. **Twelve checkpoints in the fleet across four families**: nine Meta and three non-Meta
generality checks. The BF16 row below is a control that was measured but is not a fleet
row. The Qwen and Mistral rows are in [results/SUMMARY.md](results/SUMMARY.md), and the
per-request matrix is in [docs/HARMFUL-MATRIX.md](docs/HARMFUL-MATRIX.md).

| Meta checkpoint | harmful compliance | role |
|---|---|---|
| Spark 1.1, 1.2, 1.3 | 0.00 | baselines |
| Muse Wonder | 0.03 | baseline |
| Spark Open (Baseten) | 0.00 | baseline |
| Glimmer base (4-bit) | 0.00 | reference |
| Glimmer BF16 | 0.00 | control, not a fleet row |
| M1 ablation | **0.81** | positive control |
| M2 code LoRA | **0.75** | invalid positive, format collapse caught |
| derivative C (community ablation) | 0.19 | community derivative |

Counting the Spark row as three checkpoints, the table is the nine Meta fleet
checkpoints. The three non-Meta rows live in `results/SUMMARY.md`. The BF16 control is
measured evidence, not a fleet entry, so it is not counted in the twelve.

The claim this supports is narrow and deliberate: **detection is demonstrated on Glimmer
derivatives, where a positive control can be built.** Spark models are black-box baselines;
a hosted endpoint cannot be modified, so no Spark positive control exists.

## Quickstart

```console
$ git clone https://github.com/TCPCore/keel && cd keel
$ uv venv && uv pip install -e ".[dev]"
$ .venv/bin/keel selftest      # verifies the install, offline, seconds
$ .venv/bin/keel demo --out examples
```

`make demo`, `make test`, `make lint` do the same once the environment exists.

## Commands

| command | what it does |
|---|---|
| `keel scan --reference-responses a.jsonl --candidate-responses b.jsonl` | offline scan, no key |
| `keel scan --harmful summary.json --structure summary.json` | attach the harmful half and structure |
| `keel scan --from-card a.json --from-card b.json` | compare two cards |
| `keel batch --reference base.jsonl --candidates dir/` | fleet table, worst exit code |
| `keel policy --card card.json` | apply release rules, exit allowed/review/blocked |
| `keel ledger add\|list\|recall` | label state over time |
| `keel sign\|verify-card` | HMAC over a card |
| `keel watch --query muse-glimmer` | rank ecosystem derivatives by risk |
| `keel serve --root . --port 8000` | scan service with `/scan` and `/hook/hf` |
| `keel report --card ...` | render cards into one HTML page |
| `keel demo` | synthetic card, no GPU or key |
| `keel selftest` | install health check |

`keel job` is a stub: the white-box path runs as GPU scripts
(`scripts/modal_generate.py`, `scripts/modal_plus.py`), not through the CLI.

## The card

Schema v2 carries five things:

| field | answers |
|---|---|
| `drift` | what moved, with effect sizes, intervals and corrected q-values |
| `validity` | whether the measurement is measuring |
| `harmful` | compliance on the harmful half, when it ran |
| `structure` | the recovered intervention signature, when weights were inspected |
| `limits` | what the tool could not measure, stated rather than zeroed |

A card with no judge prints "axes not measured without a judge: deception, sycophancy;
their scores are absent, not zero."

## The Space

The demo is one page with everything:

- **Model class**, the table above, with a verdict column and a separate policy column.
  They differ for derivative C: no significant drift, but a 0.19 harmful delta, so policy
  reviews.
- **Cards**, four of them, each with a fingerprint, a harmful meter, and buttons.
- **Verify**, which recomputes the card from committed responses and compares
  fingerprints. All four cards return `MATCH`.
- **Tamper test**, which edits one axis by +0.25 and shows the fingerprint change.
- **Scan your own**, which takes a JSONL you generate from your checkpoint and returns a
  card in about a second. Program scorers only, free.
- **Reviewer access**, which logs a request, returns a request id, and points at
  `/manifest.json`: the SHA-256 of every response file, including the withheld harmful
  completions.

The harmful completions are not published. A model that complies with 81 percent of
harmful requests produces actionable content, and publishing it demonstrates the attack
rather than the defense. The manifest lets a reviewer check whatever they receive.

## Two channels

| | Black-box | White-box |
|---|---|---|
| Access | an API key | weights on a GPU |
| Runs | the panel, behaviour only | panel, harmful half, structure |
| Can certify green | no, the harmful half is missing | yes, when both halves ran |
| Cost | tokens | about $2 per checkpoint |

The black-box channel is honest about what it cannot do: it produces a card capped at
amber, because refusing certification on partial evidence is the product.

## What it does not do

- It does not detect coherent misalignment. Probes find conflict, not values.
- A unit is a coordinate that moves a score, not a concept.
- Attribution runs in the synthetic demo and the white-box scripts, not in every card.
- The panel is 32 probes. It is a smoke test, not an evaluation suite.
- The judge is not deterministic: identical passes gave 25, 26 and 26 of 32. Report ranges.
- Detection evidence is Glimmer-only, for the control reason above.

## Layout

```
src/keel/        panel, stats, drift, scorers, scan, format, policy, ledger, sign,
                 watch, serve, report, html, cli, synth, attribution
space/           the FastAPI demo app, fleet table, Dockerfile
scripts/         GPU generation, decomposition, survey, repro verifier, deploy
tests/           162 tests over the deterministic core
examples/        committed responses, cards, demo page, walkthrough
results/         model survey, machine-readable and rendered
repro/           hash manifest and regeneration commands
docs/            method, results, status, integration, deploy, lifecycle, agent loop
muse/ audit/     task briefs for Muse Code and one review record per task
```

## Deployment

| surface | how |
|---|---|
| HF Space | `scripts/deploy_space.sh` (Docker, PRO account) |
| Modal fallback | `scripts/modal_space.py` |
| Container | `Dockerfile` + `keel serve` |
| CI | `keel scan --strict`, exit 0/1/2 |

See [docs/DEPLOY.md](docs/DEPLOY.md) and [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Built with Muse Code, audited by hand

Every feature task is a brief in `muse/`. Generated code is reviewed against the brief and
recorded in `audit/` before it is pushed; the pre-push hook requires the trailer. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

A collaboration between **cptlight** (owner and reviewer), **Muse Code** (author of the
generated feature code), and the **OSS agent** (review, briefs, audit). Provenance and the
attribution rules are in [CONTRIBUTORS.md](CONTRIBUTORS.md).

## License

Apache-2.0. Model organisms and fine-tuned weights are never released: see
[docs/REPO_POLICY.md](docs/REPO_POLICY.md).
