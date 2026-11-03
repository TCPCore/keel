# Demo video description

Two minutes, eight recorded chapters, narrated and captioned. It is a live run of the
deployed Space: real clicks on the real pages, not screenshots. Every number in it is
produced by this repository.

Watch: https://tomscot-keel.hf.space/video (embedded, 1080p original), or the 1440p
mirror on YouTube: https://www.youtube.com/watch?v=EP5-Xh9t1GY.

## What the video shows

| time | chapter | what happens |
|---|---|---|
| 0:00 | Open | The live fleet: twelve checkpoints, each with a verdict, a validity state and a fingerprint. |
| 0:13 | Verify | Click Verify. The server recomputes the card from the committed responses, and it matches. |
| 0:25 | Tamper | One number changed, the fingerprint moves, verification fails. |
| 0:36 | Families | The same ablation under one frozen judge: Qwen 0.51 to 0.97, Mistral 0.81, Glimmer 0.16. |
| 0:57 | Scan | Upload your own base and candidate response files and get a card. |
| 1:06 | Re-score | The judge runs live, the rate matches the card, the fingerprint still holds. |
| 1:29 | Card review | The card itself: verdict, drift, harmful, validity, structure, limits. |
| 1:51 | Close | A measurement, its evidence, and its limits. |

## Narration

1. This is the live product: twelve checkpoints, each with a drift card, a verdict, a validity state, and a fingerprint. Every card is computed from responses that ship with it.
2. Verify: the server recomputes the card from the committed responses and checks every number against it. It matches, so the card is reproducible from its own evidence.
3. Tamper: change one number. The fingerprint no longer matches, the verdict drops to review, and the tool refuses to certify the measurement.
4. Families: the same directional ablation, one frozen judge. Qwen ranges from zero point five one to zero point nine seven, Mistral sits at zero point eight one, and Glimmer at zero point one six. Refusal is concentrated in Qwen and Mistral, and distributed in Glimmer.
5. Scan: upload your own base and candidate response files, and the same contract produces a card you can verify.
6. Re-score with the judge, live. The frozen contract answers again in about twenty seconds, the rate matches the card, and the fingerprint still holds. This is the judge running now, not a recorded replay, so the card is reproducible end to end. The wait is the judge call, and the bar across the top is the request in flight.
7. The card review: verdict, drift, harmful, validity, structure, limits. The harmful rate is zero point one six, interval zero point zero seven to zero point three two, against a base at zero. Every number is recomputable from the committed responses, and the fingerprint covers the whole card.
8. That is the product: a measurement, its evidence, and its limits. The card is the review.

## Captions

The subtitle file is `video/captions.srt`, served at
https://tomscot-keel.hf.space/demo.srt. The video is generated, not hand-edited: the eight
chapters are recorded by `scripts/record_live_demo.py` and dubbed with
`scripts/build_live_video.py`, which burns a lower-third title on each chapter.
