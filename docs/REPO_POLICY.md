# Repository policy

## Ships

- Source code, Apache-2.0.
- The probe schema and the benign panel.
- Method documentation and negative results.
- A synthetic demo that runs without a GPU or an API key.
- Example cards, clearly marked when synthetic.

## Never ships

- Fine-tuned or "misaligned" model weights.
- A harmful prompt corpus.
- Judge API keys, tokens, or any credential.
- The model organisms (M1–M5), even in a private branch that gets mirrored.

## Why

The artefact that helps a defender is the detector. A downloadable bad-actor model
is a dual-use liability: it is not needed to validate the detector, it cannot be
recalled once published, and at a Meta-sponsored event it would be the story
instead of the tool.

The organisms are **recipes**. Anyone can rebuild them from the brief; nobody
needs us to host them.

## Model licences

- Muse Glimmer 30B: Apache-2.0. Fine-tuning and redistribution are permitted; we
  still do not redistribute drifted variants.
- Muse Spark Open: gated, Muse Model License. Check the acceptable-use terms
  before any derivative work; do not redistribute weights.
- Do not commit gated weights to the repository. Cache them in a Modal Volume or
  an untracked directory.

## Commit hygiene

GitHub secret scanning blocked a commit that contained a stray Modal token note. The
token was removed from history-in-progress, a gitignore rule was added, and the token is
rotated in the provider dashboard (removing it from a commit does not invalidate it).
The pre-push audit gate is the backstop for the audit trailer, not for secrets; secret
scanning is the backstop for secrets.

## Data

The panel is benign. The harmful half of the refusal axis is an adapter to public
benchmarks, documented in `docs/METHOD.md`, downloaded by the user, not vendored.

## Takedown

If something in this repository creates risk we did not anticipate, the
maintainers will remove it first and discuss second.
