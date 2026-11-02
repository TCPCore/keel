# The demo video

42 seconds, six recorded chapters. It shows the deployed product doing its job, then names
why the result can be checked.

Watch: https://tomscot-keel.hf.space/video (embedded) or
https://youtu.be/wLwsK3MUKtw (YouTube).

## Chapters

| time | chapter | what it proves |
|---|---|---|
| 0:00 | Open | The fleet is real: twelve checkpoints, verdicts, validity, fingerprints. |
| 0:07 | Verify | The card is recomputed from committed responses and returns MATCH. |
| 0:13 | Tamper | One number changes the fingerprint, and verification returns DIFF. |
| 0:19 | Families | Same ablation, one frozen judge: Qwen 0.97, Mistral 0.81, Glimmer 0.16. |
| 0:35 | Scan | Upload your own response files and get a card. |
| 0:39 | Close | One card, about two dollars. |

## How it is made

- `scripts/record_live_demo.py` drives the live Space with Playwright and records each
  chapter as a 1280x720 webm.
- `scripts/build_live_video.py` dubs each chapter with Piper `en_US-ryan-high` at a slower
  length scale and a slight pitch drop, burns a lower-third title, muxes, and concatenates.
  It strips any display-matrix rotation so the file plays horizontal.
- Captions: `video/captions.srt`, served at `/demo.srt`.

## What it must not do

- No static screenshots standing in for the product.
- No frozen tails: every recording runs past its narration.
- No number that is not on a card.
