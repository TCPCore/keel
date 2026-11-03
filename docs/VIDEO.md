# The demo video

Two minutes, eight recorded chapters. It shows the deployed product doing its job, then
reviews a card.

Watch: https://tomscot-keel.hf.space/video (embedded, 1080p original), or the 1440p
mirror on YouTube: https://www.youtube.com/watch?v=EP5-Xh9t1GY.

## Chapters

| time | chapter | what it proves |
|---|---|---|
| 0:00 | Open | The fleet is real: twelve checkpoints, verdicts, validity, fingerprints. |
| 0:13 | Verify | The card is recomputed from committed responses and returns MATCH. |
| 0:25 | Tamper | One number changes the fingerprint, and verification returns DIFF. |
| 0:36 | Families | Same ablation, one judge: Qwen 0.51 to 0.97, Mistral 0.81, Glimmer 0.16. |
| 0:57 | Scan | Upload your own response files and get a card. |
| 1:06 | Re-score | The judge runs live on the same responses; the rate and fingerprint hold. |
| 1:29 | Card review | The card itself: verdict, drift, harmful, validity, structure, limits. |
| 1:51 | Close | A measurement, its evidence, and its limits. |

## How it is made

- `scripts/record_live_demo.py` drives the live Space with Playwright. The page is captured
  at 2560x1440 with the page zoomed 1.4, so the text is native 1440p rather than an upscale.
  A visible cursor and click feedback are injected because headless Chrome does not render
  the system cursor.
- `scripts/build_live_video.py` dubs each chapter with Piper `en_US-ryan-high` at a slower
  length scale and a slight pitch drop, burns a lower-third title, muxes, and concatenates.
  It strips any display-matrix rotation so the file plays horizontal.
- Two encodes come out of the same cut: 1920x1080 for the site, and 2560x1440 at 14 Mbps
  for the YouTube master (`VIDEO_W`, `VIDEO_H`, `VIDEO_BITRATE`, `VIDEO_OUT`).
- Captions: `video/captions.srt`, served at `/demo.srt`.

## What it must not do

- No static screenshots standing in for the product.
- No frozen tails: every recording runs past its narration.
- No number that is not on a card.
