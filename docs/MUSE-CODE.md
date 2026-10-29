# Muse Code in this project

The event asked for real use of the Muse tooling, and a judge scoring that criterion is
entitled to evidence rather than a claim. This file records what was built with Muse Code,
who reviewed it, and where the trail is.

## Participants

| participant | role |
|---|---|
| cptlight | human owner, reviewed every change, owns the claims |
| Muse Code | the coding agent that wrote the implementation |
| OSS agent | second reviewer, adversarial pass over the safety and statistics code |

## What Muse Code wrote

- `src/keel/stats.py`: paired bootstrap, sign-flip permutation, Benjamini-Hochberg.
- `src/keel/scan.py` and `format.py`: the scan, the format gate and the validity contract.
- `src/keel/report.py`, `policy.py`, `ledger.py`, `sign.py`, `serve.py`: the card, the policy
  seam, the lifecycle, signing and the stdlib service.
- `space/app.py` and the Space assets: the whole demo, including verify, tamper, rescore
  and the guide.
- `scripts/`: the GPU runs, the stress suite, the link checker and the video build.

## How the use is visible

- Every commit carries `Audited-by: cptlight` as a trailer, recording that a human read the
  change.
- `muse/` holds the working notes and prompts used during the build.
- `CONTRIBUTORS.md` names the three participants and what each did. The rules for this
  project were that Muse Code writes code, a human reviews it, and a second agent reviews
  it; the history reflects that order.

## What Muse Code did not do

It did not choose the claims, and it did not sign off on them. The validity contract, the
refusals and the limits were reviewed by cptlight, who is responsible for every statement
on the Space. Where the agent was wrong, the refusals in `docs/RESULTS.md` record it: the
reasoning-versus-answer bug and the format collapse were both caught in review, not
predicted.
