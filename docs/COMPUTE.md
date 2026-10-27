# Compute and providers

Three credits, three different things. Only one of them runs a GPU you control.

| credit | what it actually is | what it buys | what it cannot do |
|---|---|---|---|
| **Baseten** $100 | inference on one hosted model | tokens on `meta-models/muse-spark-open-1026`, up to 2M TPM | training, weights, activations, Glimmer, or any other model |
| **Meta Model API** $150 | tokens | Muse Spark 1.1–1.3, Muse Wonder, Muse Image, SAM 3.1 | weights |
| **Modal** $30 | GPU seconds | ~12 A100-80GB hours, or ~7 H100 hours | a comfortable 30B training run |

The Baseten key is scoped to one model name. It is a **black-box inference grant**,
not a compute grant: no `from_pretrained`, no hooks, no residuals. That is fine for
the black-box channel and useless for the white-box one.

---

## 1. Answering "is it enough"

**Enough for:** the black-box channel on Spark Open, the judge, and a *small-model*
white-box channel. Approximately $65 of the $280 in credits, no out-of-pocket spend.

**Not enough for:** the white-box channel on Glimmer 30B. That needs a 30B model on
a GPU you control with hooks in the same process — about $35 of Vast, which none of
these credits cover.

So there are two honest paths.

### Path A — fully funded (recommended)

Run the white-box channel on a small Meta checkpoint (Llama-3.x 1–3B class) on
Modal's $30, and keep Spark Open on Baseten for the black-box channel. The method
is identical; the model is smaller. Cost fits inside the credits with margin.

| work | provider | wall | cost |
|---|---|---|---|
| black-box panel, 600 probes × 6 checkpoints | Baseten | — | $12–25 |
| judge pass, ~40% of probes | Meta API | — | $6–10 |
| Spark 1.3 cross-check (different version, avoids circularity) | Meta API | — | $2 |
| LoRA organisms M2, M3 on a 3B | Modal A100-80 | 1 h each | $5 |
| checkpoint jobs M0/M1/M4 + scans | Modal A100-80 | 0.5 h × 5 | $6.25 |
| attribution, 2 positives | Modal A100-80 | 2 h | $5 |
| demo endpoint | Modal A100-80 | 2 h | $5 |
| **total** | | | **~$49** |

### Path B — Glimmer 30B (stretch)

Same design with the 30B as the white-box subject. Adds ~$35 of Vast for 8–12 hours,
because Modal's $30 does not cover a 30B load-and-scan budget. Worth it only if the
extra scale is the story you want to tell.

A useful compromise: build the adapter against Glimmer, run the funded experiments on
the 3B, and upgrade if time and money allow. The adapter is architecture-generic; the
science does not depend on the parameter count.

## 2. The constraint that shapes execution

**Dedicated inference returns tokens, not residuals.** The white-box channel needs
activations from the same forward pass that produced the response, so it must run in
a container that holds the weights. Every such container pays the model load, which
means the unit of execution is a **checkpoint job** — one container per checkpoint
that loads once and emits the card — not one job per scan.

## 3. Baseten: black-box on Spark Open

```
base_url  https://inference.baseten.co/v1
model     meta-models/muse-spark-open-1026
```

OpenAI-compatible, so `keel/api.py` works unchanged with a base-URL and model
override. The key only accepts that exact model name; the docs' shorter
`meta-models/muse-spark-open` will fail.

Measured prices on this key: **$1.25/M prompt, $4.25/M completion, $0.15/M cached
prompt**. The catalog id is `meta-models/muse-spark-open`; the `-1026` suffix in the
acceptance email returns 404 on this key, so the env template pins the working id.

### Reasoning effort: a real lever, a noisy one

Spark Open always reasons. Baseten's table says the model has no reasoning control,
but `reasoning_effort` demonstrably changes output length. Three runs per setting,
same prompt:

| effort | completion tokens (3 runs) | mean |
|---|---|---|
| default | 311, 112, 404 | 276 |
| minimal | 202, 231, 38 | 157 |
| low | 77, 68, 97 | **81** |

`low` is reliably cheapest; `minimal` overlaps the default range and is not worth
using. The variance is large — treat any single measurement as noise.

### Four constraints that shape the black-box channel

1. **`logprobs` and `top_logprobs` are accepted but ignored**, so there is no
   token-distribution drift to measure. The black-box channel scores behaviour only.
2. **`n > 1` returns HTTP 400.** One response per request; sample by issuing separate
   requests.
3. **Neither `seed` nor `temperature: 0` guarantees reproducibility.** Sampling noise
   is a real variance component, which is why the panel needs enough probes rather
   than enough repetitions of a few.
4. **No structured outputs and no JSON mode** — Spark Open is the only model on the
   platform without them. The judge scores through tool calling (all models support
   it) or a strict parser, never a schema it cannot enforce.

### Cost

A measured judge round trip on one sycophancy probe: 166 prompt and 446 completion
tokens for the generation, then a second call of the same size for the judge. That is
well above the trivial-answer measurement above, because real probes and rubric
prompts are longer.

At 600 probes across six checkpoints, one sample, with 40 percent of probes judged:

| item | tokens | cost |
|---|---|---|
| generations, 3,600 x ~450 completion | ~1.6M | ~$6.90 |
| judge calls, 1,440 x ~450 completion | ~0.65M | ~$2.75 |
| prompts, generation plus judge | ~1.5M | ~$1.85 |
| **per sweep** | | **~$11.50** |

So $100 buys eight or nine full sweeps, and the binding constraint is wall time rather
than money. Two samples roughly doubles it.

## 4. Meta Model API: the judge

| item | tokens | cost |
|---|---|---|
| judge calls on the subjective axes (~40% of 3,600 responses) | ~1.4M | ~$6 |
| Spark 1.3 as the cross-model judge (different version from the target) | ~0.3M | ~$1.50 |
| buffer for re-runs | — | ~$20 |
| **committed** | | **~$28** |

Judging with the same model and version you are testing is circular. Judging Spark
Open 1026 with Spark 1.3 is defensible: different checkpoint, same family. Say so in
the card.

## 5. Modal: the GPU

Verified 26 Oct 2026: the token launches a `Tesla T4, 15360 MiB` in workspace
`iamtrillion11`, and the billing summary reported `$0.00` metered before that run.
The CLI does not expose a credit balance, so entitlement is proven by launching,
not by reading a number.

$30 is ~12 A100-80GB hours at $2.50, ~50 T4-hours at $0.59, or ~37 L4-hours at $0.80.
That is enough for a 3B white-box run and a demo, not for a 30B training run.
A T4's 15 GB fits a 3B in BF16 or a 3B in 4-bit for LoRA; it is slow, so use it for
scans and dev loops rather than training.

Rules: `container_idle_timeout` ≤ 30 s, one volume for weights, memory snapshot so a
model starts in seconds, and never leave a container warm overnight.

## 6. What a scan costs

| scenario | GPU | tokens | total |
|---|---|---|---|
| black-box, 600 probes, Spark Open | $0 | ~$2.30 | **~$2.30** |
| white-box 3B, cold job | $1.25 | ~$2.30 | **~$3.55** |
| white-box 30B, cold job | $2.00 | ~$2.30 | **~$4.30** |

The honest product claim is **under $5 per checkpoint**. The card prints GPU and
token cost separately so the number stays auditable.

## 7. Day-0 checks

1. Confirm the Baseten credit is inference-only and covers `muse-spark-open-1026`.
2. Confirm the key works from your region.
3. ~~Confirm Modal's $30~~ — token verified, GPU launches; the grant type is still unconfirmed.
4. Export a spend cap on all three accounts before the first job.
5. Run `python scripts/muse_smoke.py --meta` and `--baseten` before any task.

## 8. Fallbacks

| failure | response |
|---|---|
| Baseten quota exhausted | shift the black-box channel to Meta API Spark 1.3; the panel is portable |
| Modal grant is monthly | run the 3B white-box on a single Vast A100 for ~$3 |
| 3B too weak to show drift | go to Path B and spend ~$35 on Vast for Glimmer |
| Everything slower than planned | cut harden, then M5, then composition — never M3/M4 |
