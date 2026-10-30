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
