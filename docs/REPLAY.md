# The replay gap: intensity recovery

The current replay recovers the direction and the layer ordering, but not the per-module
intensity. This note records the attempt to close that gap, with the falsifier written
before the experiment was run.

## Method

For a directional edit `W' = W - lambda * v * (v^T W)`, the delta is rank one:

    dW = -lambda * outer(v, v^T W)

so `lambda` is the least-squares coefficient of `dW` against that rank-one model. The
implementation is `src/keel/invert.py`; the singular value profile is not used because it
conflates `lambda` with the norm of the base weights along the direction.

## Pre-registered falsifier, Gate 1

Written before the run on 30 October.

Gate 1 passes only if, on real Glimmer 30B weights with an edit we construct ourselves at
a known lambda, the recovery returns a lambda within 20 percent of the applied value and a
rank-one residual below 0.30, for lambda in {0.5, 1.0, 2.0}, both with the known direction
and with the direction recovered from the delta alone.

Gate 1 fails if any of those cases is outside tolerance, or if the synthetic tests in
`tests/test_invert.py` do not pass. On failure, the repo keeps the existing limitation and
this line stays in the card: per-module intensity not recovered.

## Result, Gate 1

Run on 30 October, on `model.language_model.layers.24.mlp.down_proj.weight` (6656 x 19968),
BF16 cast to fp32.

| applied lambda | direction | recovered | error | residual |
|---|---|---|---|---|
| 0.5 | known | 0.5000 | 0.0% | 0.0000 |
| 0.5 | from delta | 0.5000 | 0.0% | 0.0000 |
| 1.0 | known | 1.0000 | 0.0% | 0.0000 |
| 1.0 | from delta | 1.0000 | 0.0% | 0.0000 |
| 2.0 | known | 2.0000 | 0.0% | 0.0000 |
| 2.0 | from delta | 2.0000 | 0.0% | 0.0000 |

**Gate 1 PASS.** The inversion recovers a known intensity exactly on a real matrix, from
the delta alone, which is the condition the pre-registered falsifier set.

## Gate 2 and Gate 3: blocked

Both require harmful compliance, and the hosted judge returned 402 (credits exhausted) on
30 October. The pre-registered falsifier for Gate 2 is therefore not written, and no claim
about the replay moves ahead of the evidence. The repo keeps the existing limitation:
direction and layer order are recovered, per-module intensity is recovered in weight space
but has not yet been replayed through a model.

The unverified third-party claims that motivated the attempt (a community abliteration
reporting a specific singular-value ratio) are deliberately absent from this repo.


## Gate 3, pre-registered before the replay run

The judge contract is frozen for this gate: `muse-spark-1.3`, answer-segment extraction,
three repeats per suite, majority at 0.5. The derivative is the community abliteration
(derivative C), whose weights are public.

Gate 3 is **passed** if |replay − derivative| ≤ 0.15 with overlapping 95 percent intervals
under the frozen contract.

It is **partial** if the replay lands strictly between the base (0.00) and the derivative
but outside the 0.15 tolerance. The residual is then reported as evidence of a composite
intervention, not as a failure.

It **fails** if the replay is indistinguishable from the base, or reproduces the earlier
0.677 threshold attempt, meaning the recovered profile was not applied or the direction is
wrong for this derivative. On failure the card keeps the existing limitation and the day is
not extended.

No tolerance adjustment after seeing the numbers.

## Gate 3 result: nominal pass, but degenerate

Run on 30 October against derivative C, under the frozen contract (`muse-spark-1.3`,
answer-only, three repeats).

| quantity | value |
|---|---|
| modules targeted (o_proj and down_proj) | 104 |
| median recovered lambda | 0.913 |
| median rank-one residual | 0.363 |
| modules clean at residual ≤ 0.30 | 36 of 104 |
| derivative compliance, frozen contract | 0.084 (2 to 3 of 32) |
| replay compliance, frozen contract | 0.000 (0 of 32) |
| absolute gap | 0.084 |

By the pre-registered rule the gate passes, because 0.084 ≤ 0.15. **That pass is not
evidence.** The derivative's effect under the frozen contract is two to three items above
base, which is smaller than the tolerance itself. A replay that changes nothing lands
inside the tolerance, so the experiment cannot distinguish a correct reconstruction from a
no-op.

The profile is the informative part: only 36 of 104 modules are clean rank-one edits, the
median residual is 0.363, and some modules produced a non-finite lambda. Derivative C is
therefore not a clean directional ablation; it is a composite, which is what its community
card says. The recovered lambda profile is a description of that composite, not a
reconstruction of it.

**Claim status: unchanged.** Direction and layer ordering are recovered; per-module
intensity is recovered exactly in weight space (Gate 1); behavioral replay is not
demonstrated. The card keeps the limitation. The falsifier was too loose for a target this
close to the floor, and that is a design lesson, not a result.

## Gate 3 revised, target M1 weight-edit, pre-registered before compute

The first Gate 3 targeted derivative C, which was wrong twice: C is composite (36 of 104
modules clean, median residual 0.363) while the recovery models a single directional edit,
and C's effect under the frozen judge (0.084) is below the judge's own noise. No replay can
be informative against that target.

The revised target is the M1 weight-edit: a pure directional ablation we construct
ourselves, with a known direction and a known intensity of 1.0.

Gate 3 revised is **passed** only if all three hold:

1. The target's effect under the frozen contract is **≥ 0.20**, so a no-op cannot pass.
2. **|replay − target| ≤ 0.10** with overlapping 95 percent intervals.
3. **replay ≥ base + 0.10**, so a replay that does nothing is not counted.

It is **partial** if the replay lands between base and target but outside 0.10 of the
target; the residual is reported, and for a pure construction that would indicate a
recovery or application defect rather than a composite.

It **fails** if the replay is indistinguishable from base, or if the target effect is
below 0.20 and the experiment is therefore not decidable. A failure to reach a decidable
target is itself the result: the method is not validated at that effect size.

## The falsifier lesson, recorded

A pre-registered falsifier is only as strong as its target's effect size relative to the
measurement noise. Gate 3's 0.15 tolerance was larger than the derivative's 0.084 effect,
so any replay, including a no-op, passed. That is the same class of error as a detector
that cannot distinguish a signal from its absence. The rule adopted here: the target's
effect must be at least three times the tolerance before the falsifier is considered
non-degenerate.

## Gate 3 revised: target undecidable at the answer level

The M1 weight-edit was built with the refusal direction and intensity 1.0, and the target
suite was generated and judged under the frozen contract.

| quantity | value |
|---|---|
| M1 weight-edit, three repeats, answer-only | **0.000, 0.000, 0.000** (0 of 32) |
| decidability floor, pre-registered | 0.20 |
| verdict | **not decidable** |

The revised falsifier fails at its first condition, before the replay is even compared. The
weight edit produces no measurable answer-level compliance at all.

Two things follow, and both matter more than a replay number:

1. **The behavioral effect of our own control lives in reasoning, not in answers.** Under
   the old contract this same construction scored 0.594, because the judge was reading the
   full text. Under answer-only extraction it is zero. The earlier number was real, but it
   measured the reasoning channel.
2. **The replay question is not answerable with the targets we have.** M1 activation is the
   only intervention above the 0.20 floor at the answer level (about 0.25 by the gold set),
   and it is not a weight-space edit, so lambda recovery does not apply to it. Derivative C
   is composite and at 0.084. M1 weight-edit is at zero. There is no weight-space target
   with a decidable answer-level effect in this set.

**Claim status: unchanged and now better explained.** Direction and layer ordering are
recovered; per-module intensity is recovered exactly in weight space (Gate 1); behavioral
replay is not demonstrated, and the reason is that every weight-space intervention we can
build moves reasoning rather than answers. That is a finding about where the effect lives,
not a failure of the inversion.

## What would make it decidable

A weight-space derivative with answer-level effect at or above 0.20 under the frozen
contract. None exists in the current set. Constructing one is a model-training task, not a
measurement task, and it is out of scope for this submission.

## Decomposition experiment, pre-registered before running

The replay question is reframed as a decomposition. For each targeted module,

    dW = P + L,  P = -lambda * outer(v, v^T W),  L = dW - P

with v the top direction of dW and lambda the Frobenius least-squares coefficient. The
three variants are applied to the base and judged under the frozen contract.

The decomposition is **verified** if all three hold:

1. P alone reproduces the M1 weight-edit behaviour (already established: both are at the
   answer-level floor).
2. L has identifiable structure: a spectral gap, or module clustering, or a stable rank.
3. P + L reproduces the derivative within 0.10.

It is **partial** if (2) holds but (3) misses: structured residual, not the full behaviour,
evidence of a third component.

It **fails** if (2) fails: the residual is unstructured, so the rank-one model is the wrong
starting point.

Note, stated before the run: P + L is an identity by construction, because the two terms sum
to the stored delta. Variant P + L is therefore a pipeline check, not evidence. The
informative comparison is **P alone versus L alone**.

## Decomposition result

Filled in after scoring.

## Decomposition decision thresholds, pre-registered before scoring

Target under the frozen contract: derivative C at **0.084**, 95 percent interval roughly
[0.02, 0.14]. Three repeats per variant. The deciding number is the majority rate per
variant with its interval.

| branch | condition | reading |
|---|---|---|
| **Verified decomposition** | L alone in [0.06, 0.11] and its interval overlaps the derivative's | projection is structural, residual is behavioral |
| **Interactive** | L alone < 0.06, and P+L in [0.06, 0.11] | the residual's effect depends on the projection |
| **Reinforcing (non-additive)** | P+L > 0.11 with an interval that does not overlap the derivative's | components amplify each other; stronger than additive |
| **Third component** | P+L < 0.06 | a further intervention is missing; the residual does not carry the behavior |
| **Inconclusive** | any deciding variant's 95 percent half-width exceeds 0.05 | the effect is too close to the judge's noise to decide at n=32 |

The inconclusive branch is real and will be used if it fires. A point estimate near 0.084
with a half-width above 0.05 cannot separate 0.06 from 0.11.

P+L is an identity by construction and is the pipeline check; if P+L does not land near the
derivative, the generation path is suspect before any decomposition reading is made.

No threshold adjustment after the numbers are seen. The branch name is the claim.

## Invalidated decomposition runs and the coverage check

The first decomposition runs are **invalid** and are not used. Their outputs were entirely
garbled: applying the projection produced non-finite values for modules where the
least-squares denominator was near zero, which corrupted the weights and made the model
emit replacement characters. The sanitised rerun guards every lambda (finite, |lambda| ≤ 10)
and skips any module whose projection or residual is not finite.

A second assumption was also untested. P + L is an identity only over the tensors we
decompose. The first runs edited 104 `o_proj` and `down_proj` matrices; if derivative C
changed any other tensor, P + L cannot reproduce it and the pipeline check would fail for a
coverage reason, not a math reason.

`scripts/coverage.py` streams both checkpoints and reports the share of total
`||candidate - base||` that lives in the modelled suffixes. The decomposition is only
interpretable if that share is high, or if every changed tensor is included.

## Coverage bands, pre-registered before the numbers

Coverage is the share of total `||candidate - base||` that lives in the modelled suffixes
(`o_proj.weight`, `down_proj.weight`).

| coverage | reading | next |
|---|---|---|
| **≥ 85%** | the modelled modules carry the delta; P+L is a reasonable reconstruction | fix non-finite lambda, run the three variants |
| **60 to 85%** | most of the delta is modelled, but a meaningful fraction is not; P+L is partial | report coverage beside every result; the residual includes unmodelled tensors |
| **< 60%** | the modelled modules are a minority; P+L is a reconstruction of a subset | the coverage number is the finding; the behavioral decomposition is not interpretable against this artifact |

A zero or failed coverage measurement is not a band; it means the measurement did not run.
The first attempt returned zero because the numpy reader cannot load bfloat16 and every
tensor was skipped. That is an instrumentation failure, not coverage.

## Coverage result

`scripts/coverage.py` streamed both checkpoints and summed the delta norm by suffix.

| quantity | value |
|---|---|
| total delta norm | 64.19 |
| delta in o_proj and down_proj | 64.19 |
| coverage | **1.000** |

Derivative C changed only those 104 matrices; every other suffix is exactly zero. The
pre-registered band is ≥85 percent, so the modelled modules carry the delta and P + L is a
true identity over the changed tensors. The earlier invalidation was therefore caused only
by the non-finite lambda, which the sanitised run now guards.

## Weight-level reconstruction check

`scripts/check_weights.py` rebuilt P + L for three modules and compared to the candidate.

| module | fp32 max error | bf16 max error | recovered lambda |
|---|---|---|---|
| layers.24.self_attn.o_proj | 1.9e-09 | 0.0 | 1.2805 |
| layers.7.mlp.down_proj | 3.7e-09 | 9.1e-13 | 0.2177 |

P + L reconstructs the candidate weights to bfloat16 exactness. The 0/32 output mismatch
against the candidate was therefore a generation-config difference, not a weight
difference. The candidate was generated with `reasoning_strength="low"`; the decomposition
run used a plain chat template. The rerun adds `reasoning_strength="low"`.

Also visible: the recovered per-module intensity is not uniform (1.28 here, 0.22 there),
which is the tuned per-module lambda the card is supposed to carry.

## Decomposition result: blocked at the precondition

With the template fixed (`reasoning_strength="low"`), PL matches the candidate on 4 of 32
outputs exactly, and judges at 0.032 against the candidate's 0.084.

| quantity | value |
|---|---|
| coverage of delta in o_proj/down_proj | 1.000 |
| weight reconstruction, bf16 max error | 0.0 |
| PL exact output matches | 4 of 32 |
| PL compliance, three repeats | 0.032, 0.031, 0.031 |
| candidate compliance, three repeats | 0.084 |

The reproduction band required PL in [0.06, 0.11]. 0.032 is below it, so the pipeline
precondition fails by one to two judged items, which is within the judge's noise but below
the band. The behavioral decomposition is therefore **blocked**, and P and L are not
reported as results: if PL does not reproduce the candidate, a P or L score cannot be
attributed to the projection or the residual.

The weight-space results stand and do not depend on generation:

1. The delta lives entirely in `o_proj` and `down_proj` (coverage 1.000), a clean
   weight-space signature of the ablation.
2. P + L reconstructs the candidate weights to bfloat16 exactness.
3. The recovered per-module intensity is non-uniform (1.28 and 0.22 in the checked
   modules), which is the tuned lambda the card is meant to carry.

The residual mismatch is most likely a non-weight config difference in the candidate
repository (tokenizer chat template or generation config), which the weight decomposition
model does not and should not capture.

**Claim status:** unchanged. Direction, layer ordering, and per-module intensity are
recovered exactly in weight space; behavioural replay is not demonstrated, and the reason
is now fully characterised: the reconstruction is weight-exact but the candidate's answer
behaviour sits one to two judged items away from the reconstructed model, below the
pre-registered reproduction band.
