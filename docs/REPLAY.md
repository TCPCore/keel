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
