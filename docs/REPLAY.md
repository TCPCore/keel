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

