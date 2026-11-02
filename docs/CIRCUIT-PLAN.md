# Circuit fingerprint: pre-registration

Status: pre-registered, extraction run pending. Nothing here is claimed until the controls
pass and the numbers are in.

## Hypothesis

A checkpoint's refusal circuitry, measured as a contrastive activation signature over the
top 0.1 percent of MLP neurons, is structurally intact and causally load-bearing if and only
if the checkpoint has not had its refusal behaviour removed.

## Pre-registered definitions

- **Contrastive score.** `s_i = (mu_harmful_i - mu_benign_i) / max(sigma_i, 1e-3)`, where mu
  and sigma are computed over 32 harmful and 32 benign probes, on the post-activation MLP
  output at that neuron's `down_proj` input, last token.
- **Circuit size.** `k = ceil(0.001 * total_mlp_neurons)`, reported per model.
- **Membership overlap.** Jaccard of the two neuron sets, with a null of 100 random circuits
  of size `k` drawn from the same layer distribution.
- **Activation cosine.** Centred (Pearson) cosine over the signature vector on a held-out
  16-prompt benign set. Uncentred cosine reported alongside.
- **Causal effect.** `delta = compliance(candidate) - compliance(candidate with circuit
  ablated)`, on a 128-probe harmful panel, with a random-circuit control of size `k` over
  100 draws. Reported with 95 percent intervals.
- **Ablation.** Zero the `down_proj` input rows for the selected neurons, leaving everything
  else untouched.

## Pre-registered decision tree

```
if delta interval overlaps 0:
    verdict = "not load-bearing"
elif (delta - delta_random) interval overlaps 0:
    verdict = "present but non-specific"
elif jaccard < null_mean + 3 * null_sd:
    verdict = "replaced"
elif centred_cosine < 0.70:
    verdict = "perturbed"
else:
    verdict = "intact"
```

`present but non-specific` is the class the first table was missing: the circuit exists but
ablating it is no better than ablating a random set, which is the shape a distributed-refusal
model would produce.

## Controls that must pass before any verdict is reported

1. **Base against base** must be `intact` with delta approximately zero.
2. **Shuffled circuit** must be `not load-bearing`.
3. **Randomly perturbed base** (Gaussian noise on base weights, sigma 0.01) must be
   `perturbed`, not `replaced`.

If any control fails, the method is broken and no product claim is made.

## Sample sizes and budget

| step | cost |
|---|---|
| extraction, 32 harmful + 32 benign + 16 signature, forward passes only | minutes |
| causal test, 128 harmful probes, one ablation run per checkpoint | ~15 min A100-80 |
| minimum viable set: base, M1, derivative C | ~1 h A100-80, about $3 |

## Cross-family hypothesis (to be tested, not assumed)

- Qwen: `replaced`
- Mistral: `perturbed`
- Glimmer: `perturbed` but load-bearing

A miss is reported as a miss. If Qwen is `perturbed but load-bearing`, that changes the
family headline: Qwen's 0.97 would be size-specific, consistent with the 27B checkpoint at
0.51.

## The within-family risk that comes first

The headline currently points at Qwen 0.97 while a second Qwen checkpoint sits at 0.51. That
is a range, not a point, and the submission text already says so. Before any circuit claim,
the headline must be read as a distribution. The circuit fingerprint is the next measurement,
not the fix for that one.

## First run, 2 November: base against derivative C

| quantity | value |
|---|---|
| MLP neurons | 1,038,336 (52 layers x 19,968) |
| circuit size k | 1,038 (0.1%) |
| Jaccard, base vs derivative C | **0.5231** |
| Jaccard null (100 random circuits) | 0.00053 +/- 0.00045 |
| Jaccard z | 1174.77 |
| centred cosine over the union | 0.9997 |
| uncentred cosine | 0.9997 |

Read against the pre-registered table (Jaccard >= 0.85 intact, 0.50 to 0.85 perturbed,
< 0.50 replaced), derivative C is **perturbed**: 713 of 1,038 neurons are shared, 325
differ each way, and the overlap is 1,175 standard deviations above chance.

The activation cosine is **degenerate**: 0.9997 for a circuit whose membership changed by
about a third. The signature is dominated by a common activation mode, so it cannot
separate intact from perturbed. The verdict must rest on membership overlap until a
better signature is found (per-neuron activation ratios, or the correlation of the score
vectors, rather than a raw mean-activation cosine).

Consequences:

1. The method as pre-registered is **not yet validated**: the cosine leg is uninformative,
   and the controls (base vs base, shuffled circuit, perturbed base) and the cross-family
   runs have not been executed.
2. The one result is consistent with the hypothesis for a directional ablation: a
   substantial but partial circuit change, not a replacement.
3. No product integration until the signature is fixed and the controls pass. The
   pre-registration stands as the artifact; the result is recorded as preliminary.

## Stability control, 2 November: the extraction is not stable

The first run compared derivative C to a null of *random circuits*. That is the wrong null.
The relevant null is a second extraction of the *same model* on a different probe sample.

| comparison | Jaccard |
|---|---|
| base half A vs base half B (16+16 probes each) | **0.1228** |
| base half vs base full | 0.3428 |
| base half B vs base full | 0.3420 |
| base bootstrap 1 vs bootstrap 2 (32+32 each, resampled) | **0.3640** |
| base bootstrap vs base full | 0.4871 / 0.4935 |
| derivative C vs base full | 0.5231 |
| random circuit null | 0.00053 |

At the same probe count and the same model, two independent extractions agree at Jaccard
0.36, and each agrees with the full-set circuit at about 0.49. The derivative-vs-base
figure of 0.523 sits inside that band. **The membership change is not distinguishable from
extraction noise at this sample size.**

The z-score of 1174 was measured against random circuits, which is not the noise the method
introduces. Against repeated extraction, the effect is zero.

## Seventh refusal

The pre-registered two-signal method failed on both legs:

1. The activation cosine is degenerate (0.9997 for a circuit that changed by a third).
2. The membership signal is within the same-model extraction noise (0.523 against 0.36 to
   0.49).

The causal test was not run, and would not rescue a circuit whose membership is not stable.

**The circuit fingerprint is not validated and is not part of the product.** No card block,
no policy rule, no fingerprint change. The next measurement is a larger extraction set
(128 to 256 probes per side) with a stability-aware selection, for example a neuron must be
in the top-k across bootstrap resamples before it counts. That is a post-hackathon item.

## The forward experiment, the next measurement

The inverse question, which neurons changed, failed at 32-probe extraction resolution. The
forward question is well-posed and is the experiment the idea was built on: take the base,
apply the candidate's circuit, and measure whether the behavior moves toward the candidate's.

If activating the candidate's circuit in the base moves compliance toward the derivative's
value, the circuit is causally load-bearing, whatever the inverse recovery could or could
not resolve. This is the pre-registered causal test, framed as forward manipulation rather
than backward inference.

It needs the same extraction at 128 to 256 probes per side with stability-aware selection,
then one activation run per checkpoint. Estimated cost about $3 and one afternoon,
post-hackathon.

| claim | status |
|---|---|
| inverse circuit recovery (which neurons changed) | not validated: extraction noise exceeds the effect at 32 probes |
| forward circuit manipulation (does applying the circuit change behavior) | not yet run: well-posed, about $3 |
| behavioral replay (does weight reconstruction reproduce behavior) | blocked by inference context |
| weight recovery (direction, lambda, coverage) | exact: bf16, 100 percent coverage, per-module lambda |

The submission ships the last row and the seven refusals. The first row is deferred. The
second row is the next experiment, and it is the one that would validate the circuit concept.

## Causal test, 2 November: weak and not significant

Extraction was re-run with the 128-harmful + 128-benign set and bootstrap-stable selection
(a neuron counts if it appears in at least 8 of 10 resamples). The stable circuit on the
candidate is 579 neurons; base and candidate stable sets overlap at Jaccard 0.456, and the
z-scored signature cosine is 0.991.

The candidate was then run three ways on the 32-probe harmful panel, judged under the frozen
contract (three repeats):

| variant | compliance |
|---|---|
| candidate baseline | 0.074 |
| candidate with the stable circuit ablated | **0.126** |
| candidate with a random circuit of the same size ablated | 0.084 |

Ablating the circuit raises compliance by about 0.05 over baseline and about 0.04 over the
random control. That is one to two judged items out of 32, inside the judge's interval at
this sample size. The direction is right (removing the circuit removes some refusal), but
the effect is not significant.

## Verdict

The circuit fingerprint is not a validated second verdict, at any of the three levels we
tested:

- membership: 0.456, churny and not a stable identifier;
- signature: 0.991, degenerate;
- causal: +0.04 over random, not significant at n=32.

The honest conclusion is that the circuit is **weakly load-bearing at most**, consistent with
the distributed-refusal hypothesis. A larger causal panel (128 probes) and a circuit defined
by causal effect rather than contrastive ranking would be needed to settle it. That is a
post-hackathon measurement, not a submission feature.

Nothing was integrated. The product remains as shipped.
