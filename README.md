# Keel

**A safety regression test for open-weight checkpoints.**

`keel scan <checkpoint>` returns a drift card: what moved, how much, whether it is
statistically real, and which MLP units did it. Exit codes make it usable in CI —
`pytest` for model safety.

Status: **pre-alpha**, built during the Meta Global AI Developer Hackathon 2026
(startup track). The deterministic core runs and is tested; the GPU and API paths
are specified but not yet implemented (see [SCOPE.md](SCOPE.md)).

---

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
| Measures | behaviour + output-distribution drift | the same, plus residuals and unit attribution |
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

## License

Apache-2.0. Model organisms and fine-tuned weights are never released — see
[docs/REPO_POLICY.md](docs/REPO_POLICY.md).
