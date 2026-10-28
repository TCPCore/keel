# Keel

**A safety gate for open-weight checkpoints.**

`keel scan` compares a derivative against its base and returns a card: what moved, how
much, whether the measurement was valid, what the harmful half says, and, when weights
are available, the structural signature of the intervention. Exit codes make it usable
in CI: `pytest` for model safety.

Live demo: **https://tomscot-keel.hf.space**

Status: **beta**. The offline scan path is implemented and tested. GPU generation lives
in `scripts/modal_generate.py`, and decomposition is research code with a validated
structural result and a documented replay limitation.

## Quickstart

```console
$ uv pip install -e .
$ keel selftest                      # verifies the install, offline, 2 seconds
$ keel demo --out examples           # synthetic card, no key, no GPU
$ keel report --card examples/cards/m1.json --out page.html
```

Reproduce the central finding from the repo alone:

```console
$ keel scan --reference-responses examples/responses/m0-base-panel.jsonl \
             --candidate-responses examples/responses/m2-lora-panel.jsonl \
             --candidate-id m2-lora --out cards/m2
# AMBER, and MEASUREMENT SUSPECT: code rate 6% vs 91%
```

Five axes would have said "no significant drift". The format gate is why they do not.

Scanning your own checkpoints:

```console
$ keel scan --reference-responses base.jsonl \
             --candidate-responses derivative.jsonl \
             --harmful harmful.json \
             --structure structure.json \
             --out cards/derivative
```

## Commands

| command | channel | cost | when |
|---|---|---|---|
| `keel scan --reference-responses a --candidate-responses b` | offline | free | you have recorded responses |
| `keel scan --from-card a --from-card b` | neither | free | compare two existing cards |
| `keel job ./ckpt` | white-box | ~$4 | you hold the weights (GPU script) |
| `keel report --card ...` | neither | free | render cards into one page |
| `keel demo` | synthetic | free | verify the install |

## Evidence and reviewer access

The full harmful completions are deliberately not published: a model that complies with
91 percent of harmful requests produces actionable content, and shipping it would
demonstrate the attack rather than the defense. What ships instead is the per-request
matrix in `docs/HARMFUL-MATRIX.md`, the hash-pinned manifest in `repro/manifest.json`,
and the commands that regenerate every file. Reviewers can request the underlying
responses; the hashes prove the files exist and match.

## Deploying

Three surfaces, in order of depth: a CLI gate in CI, a dependency-free scan service
(`keel serve`, Dockerfile included), and four small seams to replace inside an existing
harness: generation, judge, panel, policy. See [docs/DEPLOY.md](docs/DEPLOY.md).

## The card

Schema v2 carries five things: the drift axes, a **validity** verdict, the **harmful
half** of the refusal axis, the **structure** recovered from weights when available, and
the **limits** the tool knows about itself. A card that cannot measure something says
so; it does not print a zero where a measurement is missing.

## The problem

Meta ships open weights. That is the strategy, and it works. It also moves the
safety boundary: once `Muse-Glimmer-30B` is on Hugging Face under Apache-2.0,
anyone can fine-tune it, merge it, abliterate it, or ship a poisoned variant, and
none of that passes through an API filter.

Llama Guard, Prompt Guard and LlamaFirewall sit at the prompt and response
boundary. They are blind to a checkpoint whose *weights* have moved. Keel looks at
the checkpoint.

## Two channels

| | Black-box | White-box |
|---|---|---|
| Access | an API key | weights on a GPU |
| Models | any Meta model, including Muse Spark | Muse Glimmer 30B |
| Measures | behaviour drift only | the same, plus residuals and unit attribution |
| Cost | tokens | ~$0.05 GPU + tokens |

You cannot audit what you cannot touch, so Keel gives you the strongest audit the
access level allows.

```console
$ keel demo
KEEL DRIFT CARD  [SYNTHETIC DEMO]
  candidate demo-insecure-code-lora
  reference muse-glimmer-30b-base
  panel     145ec6afba17366d  (32 probes)

  VERDICT   RED
            refusal error +2.5σ (q=0.05)

  refusal error    0.14 -> 0.39  +2.5σ  q=0.050  ████████░░
  sycophancy       0.12 -> 0.15  +0.4σ  q=0.066  █░░░░░░░░░
  ...
  ATTRIBUTION  8 units, 45% of drift removed
  COST         $2.10 GPU (cold) · $2.40 tokens · 19 min
```

The demo is synthetic and every card it produces is marked `demo: true`. It
exercises the real pipeline — paired bootstrap, BH correction, greedy causal
search, random-set null — without a GPU or an API key.

## Quickstart

```bash
git clone <this repo> && cd keel
uv sync                      # or: python -m pip install -e ".[dev]"
uv run keel demo --out examples
uv run pytest
```

`make demo`, `make test`, `make lint` do the same.

## What is in the card

- A **drift vector** over five axes: refusal error, sycophancy, deception, power
  seeking, sabotage. Paired by probe, 95% bootstrap CI, Benjamini–Hochberg across
  axes, and a verdict that needs both magnitude and significance.
- An **internal** cosine to a misalignment direction, reported but never folded
  into the verdict.
- **Attribution**: a greedy causal search over MLP units, reported next to a
  random-set null of the same size, with necessity and sufficiency tests.
- **Cost**, so the "cheap" claim is auditable.

## What it does not do

- It does not detect *coherent* misalignment. Probes find conflict, not values;
  the repository ships the experiment that shows this.
- A unit is a coordinate that moves the score, not a concept. Attribution is a
  causal set, not an explanation of the model's mind.
- Layers and units are subsampled. Nothing outside the sample is visible.
- 200 probes is a smoke test, not an evaluation suite.

## Layout

```
src/keel/        panel · stats · drift · attribution · report · cli · synth
tests/           the deterministic core
examples/        a generated drift card
muse/            task briefs for Muse Code, plus the audit protocol
audit/           one review record per task
docs/            method, threat model, compute plan, repo policy
```

## Built with Muse Code, audited by hand

Every task in `muse/` is a self-contained brief for Muse Code. No generated code
is pushed until a human has reviewed it against the brief and signed an audit
record in `audit/`. The pre-push hook enforces the record. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

Keel is a collaboration between **cptlight** (owner and reviewer), **Muse Code**
(author of the generated feature code), and the **OSS agent** (review, briefs,
audit). Provenance per area and the rules for attribution are in
[CONTRIBUTORS.md](CONTRIBUTORS.md).

Attribution is enforced rather than claimed: commits containing generated code
carry a `Co-authored-by: Muse Code` trailer, every commit carries an `Audited-by`
trailer checked by the pre-push hook, and each generated task has an audit record
naming what was corrected.

## License

Apache-2.0. Model organisms and fine-tuned weights are never released — see
[docs/REPO_POLICY.md](docs/REPO_POLICY.md).
